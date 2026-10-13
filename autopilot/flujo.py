"""Flujo por elemento: Investigador → Clasificador → Extractor → Verificador → Redactor/SEO →
Editor de calidad → Publicador. Cada función trabaja dentro de una transacción que el motor confirma."""
import json
import re
from datetime import timedelta

from sqlalchemy import or_

from consultas import buscar_zona
from extensions import db
from models import Articulo, ahora, hoy
from tipos import TIPOS
from autopilot import adaptadores, calidad, clasificador, dedup, extraccion, publicador, redactor, verificador
from autopilot.modelos import Hallazgo, Evidencia, Tarea, Verificacion, VersionArticulo
from autopilot.red import Bloqueado, ErrorRed

MAX_TEXTO = 60_000
TIPO_PAGINA = {"empleo": "convocatoria", "convocatoria": "convocatoria", "beca": "convocatoria",
               "educativa": "convocatoria", "curso": "convocatoria"}


def _regiones_mencionadas(texto):
    from models import Ubicacion
    from utils import normalizar
    t = f" {normalizar(texto)} "
    return sum(1 for u in Ubicacion.query.filter_by(tipo="region").all() if f" {normalizar(u.nombre)} " in t)


def encolar(tipo, objetivo_id, clave, prioridad=3, ejecucion_id=None):
    """Crea la tarea si su clave no existe (idempotente)."""
    if Tarea.query.filter_by(clave=clave).first():
        return None
    t = Tarea(tipo=tipo, objetivo_id=objetivo_id, clave=clave, prioridad=prioridad, ejecucion_id=ejecucion_id)
    db.session.add(t)
    return t


# ---------- 1. Investigador ----------
def consultar_fuente(fuente, descargador, ejecucion_id=None):
    """Lee el listado de la fuente y registra hallazgos nuevos. Devuelve (nuevos, vistos)."""
    items = adaptadores.listar(fuente, descargador)
    nuevos = 0
    for it in items:
        url_n = dedup.normalizar_url(it.url)
        h = Hallazgo.query.filter_by(url_normalizada=url_n).first()
        if h is None and it.id_externo:
            h = Hallazgo.query.filter_by(fuente_id=fuente.id, id_externo=it.id_externo).first()
        if h is not None:
            h.ultima_consulta = ahora()
            # Re-verificación periódica de lo ya convertido en ficha (como máximo cada 3 días)
            if h.articulo_id and h.articulo and h.articulo.estado in ("publicado", "revision") and h.articulo.vigente:
                encolar("revisar_hallazgo", h.id, f"revisar:{h.id}:{ahora().toordinal() // 3}", 3, ejecucion_id)
            continue
        h = Hallazgo(fuente_id=fuente.id, url=it.url[:1000], url_normalizada=url_n[:1000],
                     id_externo=(it.id_externo or None) and it.id_externo[:200], titulo=it.titulo[:400],
                     resumen_fuente=it.resumen[:2000] or None, fecha_fuente=it.fecha, estado="nuevo",
                     extra_json=json.dumps(it.extra, ensure_ascii=False) if it.extra else None)
        db.session.add(h)
        db.session.flush()
        encolar("procesar_hallazgo", h.id, f"procesar:{h.id}", 2, ejecucion_id)
        nuevos += 1
    fuente.ultima_consulta = ahora()
    fuente.errores_consecutivos, fuente.ultimo_error = 0, None
    if fuente.estado == "error":
        fuente.estado = "activa"
    if nuevos:
        fuente.ultima_novedad = ahora()
    return nuevos, len(items)


# ---------- 2–7. Procesamiento de un hallazgo ----------
RE_DOC_CLAVE = re.compile(r"^(cronograma|bases|perfil)", re.I)


def _pdf_de_pagina(url, descargador):
    """En gob.pe, «Bases» o «Cronograma» suelen ser una página con el PDF dentro: se sigue un salto."""
    try:
        r = descargador.obtener(url)
    except (Bloqueado, ErrorRed):
        return None
    _t, _x, enlaces = extraccion.texto_html(r.texto, r.url)
    pdfs = extraccion.pdfs_de(enlaces)
    return pdfs[0] if pdfs else None


def _descargar_evidencia(h, descargador):
    """(titulo, texto, enlaces, paginas_pdf, url_pdf, bytes_pdf). Las páginas PDF son (n, texto, url)."""
    fuente = h.fuente
    extra = [(t, u) for t, u in h.extra.get("enlaces", []) if isinstance(u, str)]
    if re.search(r"\.pdf(\?|$)", h.url, re.I):
        r = descargador.obtener_pdf(h.url)
        paginas = [(n, t, h.url) for n, t in extraccion.texto_pdf(r.contenido)]
        return h.titulo or "", "\n".join(p[1] for p in paginas), extra, paginas, h.url, r.contenido
    if fuente.config.get("seguir_detalle", True):
        r = descargador.obtener(h.url)
        titulo, texto, enlaces = extraccion.texto_html(r.texto, r.url)
    else:
        titulo, texto, enlaces = h.titulo or "", h.resumen_fuente or "", []
    if h.resumen_fuente and h.resumen_fuente not in texto:
        texto = h.resumen_fuente + "\n" + texto      # descripción del bloque o fila del listado
    if extra and h.extra.get("bloque"):
        titulo = h.titulo or titulo                    # el título del bloque es más preciso que el de la página
    titulo = titulo or h.titulo or ""
    enlaces = enlaces + [e for e in extra if e not in enlaces]
    pdfs = extraccion.pdfs_de([(t, u) for t, u in enlaces if re.search(r"cronograma|bases?", t + u, re.I)])
    # Documentos clave que son páginas (no PDF): un salto para obtener su PDF
    for t, u in extra:
        if RE_DOC_CLAVE.match(t.strip()) and not re.search(r"\.pdf(\?|$)", u, re.I) and len(pdfs) < 3:
            pdf = _pdf_de_pagina(u, descargador)
            if pdf and pdf not in pdfs:
                pdfs.insert(0 if t.lower().startswith("cronograma") else len(pdfs), pdf)
    if not pdfs:
        pdfs = extraccion.pdfs_de(enlaces)
    paginas, url_pdf, datos_pdf = [], None, None
    if fuente.config.get("leer_pdf", True):
        for pdf in pdfs[:2]:   # cronograma y bases como máximo
            try:
                rp = descargador.obtener_pdf(pdf)
            except (Bloqueado, ErrorRed):
                continue   # PDF demasiado grande o no permitido: se sigue con lo demás
            if datos_pdf is None:
                datos_pdf, url_pdf = rp.contenido, pdf
            paginas += [(n, t, pdf) for n, t in extraccion.texto_pdf(rp.contenido)]
    return titulo, texto, enlaces, paginas, url_pdf, datos_pdf


def _candidatos_duplicado(h):
    filtros = [Hallazgo.url_normalizada == h.url_normalizada]
    if h.huella:
        filtros.append(Hallazgo.huella == h.huella)
    if h.huella_documento:
        filtros.append(Hallazgo.huella_documento == h.huella_documento)
    if h.codigo_convocatoria:
        filtros.append(Hallazgo.codigo_convocatoria == h.codigo_convocatoria)
    if h.id_externo:
        filtros.append(Hallazgo.id_externo == h.id_externo)
    exactos = Hallazgo.query.filter(Hallazgo.id != h.id, Hallazgo.estado.notin_(("nuevo", "error", "duplicado")),
                                    or_(*filtros)).limit(50).all()
    recientes = Hallazgo.query.filter(Hallazgo.id != h.id, Hallazgo.estado.in_(("borrador", "extraido")),
                                      Hallazgo.tipo_detectado == h.tipo_detectado,
                                      Hallazgo.descubierto >= ahora() - timedelta(days=120)) \
        .order_by(Hallazgo.id.desc()).limit(200).all()
    return exactos + [x for x in recientes if x not in exactos]


def analizar(h, descargador, cfg, ia=None):
    """Descarga, extrae, verifica y compone. No escribe en el CMS. Devuelve un dict con todo."""
    hoy_ = hoy()
    fuente = h.fuente
    titulo, texto, enlaces_pagina, paginas, url_pdf, datos_pdf = _descargar_evidencia(h, descargador)
    tipo = fuente.tipo_contenido if fuente.tipo_contenido in TIPOS else "noticia"
    datos = extraccion.extraer(tipo, titulo, texto, h.url, hoy_, paginas, url_pdf)
    vac = datos["vacantes"].valor if datos["vacantes"].util else None
    tipo_det = clasificador.detectar_tipo(titulo, texto, tipo, vac)
    if tipo_det == "convocatoria" and vac == 1 and datos.get("cargo") is not None and datos["cargo"].util:
        tipo_det = "empleo"   # una sola vacante con puesto definido: es una oferta concreta
    if tipo_det != tipo:
        tipo = tipo_det
        datos = extraccion.extraer(tipo, titulo, texto, h.url, hoy_, paginas, url_pdf)
    sospechas = clasificador.inyeccion(texto + "\n" + "\n".join(p[1] for p in paginas))

    # IA opcional: solo completa campos faltantes y queda marcada como «inferido»
    if ia is not None:
        for campo, dato in ia.completar(tipo, titulo, texto, datos).items():
            datos[campo] = dato

    zona = fuente.ubicacion
    if zona is None:
        z = buscar_zona(titulo + " " + texto[:4000])
        if z is not None and _regiones_mencionadas(titulo + " " + texto[:4000]) > 1:
            z = None   # menciona varias regiones: alcance nacional o múltiple
        if z is not None:
            zona = z
            datos["region"] = extraccion.Dato(z.nombre, "derivado", "Mencionada en la fuente", h.url, None, "regla")
    else:
        datos["region"] = extraccion.Dato(zona.nombre, "derivado", "Configurada en la fuente", h.url, None, "fuente")
    institucion = fuente.institucion
    if institucion is not None:
        datos["institucion"] = extraccion.Dato(institucion.nombre, "derivado", "Configurada en la fuente",
                                               fuente.url_principal, None, "fuente")

    enlaces = extraccion.clasificar_enlaces(enlaces_pagina, h.url, TIPO_PAGINA.get(tipo, "oficial"))
    cta = TIPOS[tipo]["cta"]
    if cta in ("inscripcion", "consulta"):
        # «Inscríbete» / «Postula» en un curso o un beneficio = su botón principal propio
        enlaces = [(cta if t == "postular" else t, e, u) for t, e, u in enlaces]
    verificados = verificador.verificar_enlaces(enlaces, descargador)
    problemas = verificador.verificar_fechas(datos, hoy_, tipo, h.fecha_fuente.date() if h.fecha_fuente else None,
                                             titulo)
    fl_dudosa = datos["fecha_limite"]
    if fl_dudosa.util and fl_dudosa.valor > hoy_ + timedelta(days=400):
        # Una «fecha límite» a más de un año suele ser otra fecha (fin de estudios, vigencia…): no se usa
        datos["fecha_limite"] = extraccion.Dato(fl_dudosa.valor, "contradictorio", fl_dudosa.fragmento,
                                                fl_dudosa.origen, fl_dudosa.pagina, "regla")
    # Si ya hay DOCUMENTOS de resultados o de cancelación, la postulación terminó aunque un
    # cronograma antiguo muestre una fecha futura.
    etapa = verificador.etapa_concluida(enlaces_pagina)
    if etapa:
        problemas.append(("bloqueo", etapa))
    if paginas and not any(p[1].strip() for p in paginas):
        problemas.append(("revision", "Las bases son un PDF escaneado (imagen): revisa a mano el cronograma y la "
                                      "fecha límite."))
    relev, motivos_rel = clasificador.relevancia(datos, tipo, enlaces, hoy_, titulo, h.resumen_fuente or "")
    borrador = redactor.componer(tipo, datos, titulo, institucion, zona,
                                 [(t, e, u) for t, e, u, ok, _d in verificados if ok])
    decision, checklist, motivos = calidad.evaluar(tipo, borrador, datos, verificados, problemas, sospechas,
                                                   relev, fuente, institucion, cfg)
    if sospechas:
        motivos = motivos + ["Texto sospechoso en la fuente: " + "; ".join(sospechas)]
    return dict(tipo=tipo, titulo=titulo, texto=texto, datos=datos, enlaces=verificados, borrador=borrador,
                decision=decision, checklist=checklist, motivos=motivos, relevancia=relev,
                motivos_relevancia=motivos_rel, zona=zona, institucion=institucion,
                huella=dedup.huella_texto(texto), huella_doc=dedup.huella_bytes(datos_pdf),
                codigo=dedup.normalizar_codigo(datos["codigo"].valor) if datos["codigo"].util else None,
                sospechas=sospechas, url_pdf=url_pdf)


def _guardar_analisis(h, r):
    h.tipo_detectado, h.relevancia = r["tipo"], r["relevancia"]
    fl = r["datos"]["fecha_limite"]
    h.prioridad = clasificador.prioridad(r["relevancia"], fl.valor if fl.util else None, hoy())
    h.titulo = (r["titulo"] or h.titulo or "")[:400]
    h.texto = r["texto"][:MAX_TEXTO]
    h.huella, h.huella_documento, h.codigo_convocatoria = r["huella"], r["huella_doc"], r["codigo"]
    h.datos_json = json.dumps({k: d.a_dict() for k, d in r["datos"].items()}, ensure_ascii=False, default=str)
    h.advertencias_json = json.dumps(r["motivos"] + r["motivos_relevancia"], ensure_ascii=False)
    h.enlaces_json = json.dumps([list(e) for e in r["enlaces"]], ensure_ascii=False)
    h.ultima_consulta = ahora()
    h.evidencias = [Evidencia(campo=k, valor=str(d.valor)[:4000] if d.valor is not None else None,
                              estado=d.estado, fragmento=(d.fragmento or "")[:600],
                              origen=(d.origen or "")[:1000], pagina=d.pagina, metodo=d.metodo)
                    for k, d in r["datos"].items()]


def procesar_hallazgo(h, descargador, cfg, ia=None):
    """Devuelve el resultado: rechazado | duplicado | revision | autopublicado | programado | actualizacion."""
    h.intentos += 1
    r = analizar(h, descargador, cfg, ia)
    _guardar_analisis(h, r)
    db.session.flush()

    otro, motivo = dedup.buscar_duplicado(h, _candidatos_duplicado(h))
    if otro is not None:
        h.estado, h.duplicado_de_id, h.motivo = "duplicado", otro.id, f"Duplicado: {motivo}"
        if otro.articulo is not None and r["huella"] != otro.huella:
            nuevos = _datos_actualizables(r)
            if publicador.proponer_actualizacion(otro.articulo, nuevos, h):
                h.estado = "actualizacion"
                return "actualizacion"
        return "duplicado"

    if r["decision"] == "rechazar":
        h.estado, h.motivo = "descartado", "; ".join(r["motivos"])[:2000]
        return "rechazado"
    a = publicador.crear_publicacion(h, r["borrador"], r["enlaces"], r["decision"], r["checklist"], r["motivos"],
                                     h.fuente, r["institucion"], r["zona"], cfg)
    h.articulo_id, h.estado = a.id, "borrador"
    h.motivo = "; ".join(r["motivos"])[:2000] or None
    if a.estado == "publicado":
        return "programado" if a.programada else "autopublicado"
    return "revision"


def _datos_actualizables(r):
    b = r["borrador"]
    return {"fecha_limite": b["fecha_limite"], "detalle": {k: v for k, v in b["detalle"].items()},
            "enlaces": [(t, e, u) for t, e, u, ok, _d in r["enlaces"] if ok]}


def revisar_hallazgo(h, descargador, cfg):
    """Vuelve a leer la fuente de una ficha existente y propone cambios si los hay."""
    a = h.articulo
    if a is None:
        return "sin_ficha"
    r = analizar(h, descargador, cfg)
    if r["huella"] == h.huella:
        db.session.add(Verificacion(articulo_id=a.id, tipo="fuente", resultado="ok", detalle="Sin cambios en la fuente."))
        h.ultima_consulta = ahora()
        return "sin_cambios"
    v = publicador.proponer_actualizacion(a, _datos_actualizables(r), h)
    _guardar_analisis(h, r)
    db.session.add(Verificacion(articulo_id=a.id, tipo="fuente", resultado="cambio",
                                detalle=(v.resumen_cambios if v else "Cambió el texto, sin cambios en los datos clave.")[:2000]))
    return "actualizacion" if v else "sin_cambios"


# ---------- Mantenimiento ----------
def revisar_vigencias(descargador, limite_enlaces=15):
    """Cierra convocatorias vencidas (con versión para revertir) y comprueba enlaces de las vigentes."""
    servicio = publicador.usuario_servicio()
    cerradas = 0
    vencidas = Articulo.query.filter(Articulo.estado == "publicado", Articulo.fecha_limite < hoy(),
                                     Articulo.vigencia == "abierta").all()
    for a in vencidas:
        antes = publicador.snapshot(a)
        a.vigencia = "cerrada"
        db.session.add(VersionArticulo(articulo_id=a.id, origen="autopilot", tipo="aplicada", estado="aplicada",
                                       usuario_id=servicio.id, datos_antes=json.dumps(antes, ensure_ascii=False),
                                       datos_despues=json.dumps(publicador.snapshot(a), ensure_ascii=False),
                                       resumen_cambios=f"vigencia: abierta → cerrada (venció el {a.fecha_limite:%d/%m/%Y})"))
        db.session.add(Verificacion(articulo_id=a.id, tipo="vigencia", resultado="cambio",
                                    detalle="Fecha límite pasada: marcada como cerrada."))
        cerradas += 1
    rotos = 0
    vigentes = (Articulo.query.filter(Articulo.estado == "publicado",
                                      or_(Articulo.fecha_limite.is_(None), Articulo.fecha_limite >= hoy()))
                .order_by(Articulo.actualizado.asc()).limit(limite_enlaces).all())
    for a in vigentes:
        principal = a.enlace_principal
        if principal is None or not principal.url:
            continue
        ok, estado, detalle = descargador.comprobar_enlace(principal.url)
        db.session.add(Verificacion(articulo_id=a.id, tipo="enlace", resultado="ok" if ok else "error",
                                    detalle=f"{principal.texto}: {'HTTP ' + str(estado) if estado else detalle}"))
        rotos += 0 if ok else 1
    return cerradas, rotos



# ---------- Reevaluación tras mejorar las reglas ----------
def _intacta(a, servicio):
    """Ficha del Autopilot que ninguna persona editó, aprobó ni rechazó."""
    from autopilot.modelos import DecisionEditorial
    humana = DecisionEditorial.query.filter_by(articulo_id=a.id, actor="humano").first()
    return (a.origen == "autopilot" and a.estado == "revision" and a.editado_por_id == servicio.id
            and a.publicado_por_id is None and humana is None)


def reevaluar_borradores(descargador, cfg, incluir_descartados_de=()):
    """Vuelve a analizar las fichas del Autopilot aún intactas con las reglas actuales.
    Las que ya no pasan se retiran (nunca se publicaron); las demás se rehacen. Devuelve un resumen."""
    from autopilot.modelos import DecisionEditorial
    from models import Registro
    servicio = publicador.usuario_servicio()
    resumen = {"retiradas": [], "rehechas": [], "omitidas": 0, "reabiertas": 0}
    if incluir_descartados_de:
        # Los descartados de esas fuentes se vuelven a procesar (nunca tuvieron ficha)
        for h in Hallazgo.query.filter(Hallazgo.estado.in_(("descartado", "error")),
                                       Hallazgo.fuente_id.in_(list(incluir_descartados_de))).all():
            h.estado, h.motivo = "nuevo", None
            encolar("procesar_hallazgo", h.id, f"procesar:{h.id}:re{ahora():%Y%m%d%H%M}", 2)
            resumen["reabiertas"] += 1
    for h in Hallazgo.query.filter(Hallazgo.estado.in_(("duplicado", "actualizacion"))).all():
        # Los duplicados se recalculan con las reglas nuevas (p. ej. PDF compartido entre becas distintas)
        VersionArticulo.query.filter_by(hallazgo_id=h.id, estado="pendiente").update({"estado": "rechazada"})
        h.estado, h.duplicado_de_id, h.motivo = "nuevo", None, None
        encolar("procesar_hallazgo", h.id, f"procesar:{h.id}:re{ahora():%Y%m%d%H%M}", 2)
        resumen["reabiertas"] += 1
    db.session.commit()
    for h in Hallazgo.query.filter(Hallazgo.estado == "borrador", Hallazgo.articulo_id.isnot(None)).all():
        a = h.articulo
        if a is None or not _intacta(a, servicio):
            resumen["omitidas"] += 1
            continue
        titulo_previo = a.titulo
        DecisionEditorial.query.filter_by(articulo_id=a.id).update({"articulo_id": None})
        VersionArticulo.query.filter_by(articulo_id=a.id).delete()
        h.articulo_id = None
        db.session.delete(a)
        db.session.flush()
        h.estado = "nuevo"
        resultado = procesar_hallazgo(h, descargador, cfg)
        if resultado == "rechazado":
            resumen["retiradas"].append((titulo_previo, h.motivo))
            db.session.add(Registro(usuario_id=servicio.id, accion="autopilot_ficha_retirada",
                                    detalle=f"{titulo_previo}: {h.motivo or ''}"[:300]))
        else:
            resumen["rehechas"].append((titulo_previo, resultado))
        db.session.commit()
    return resumen

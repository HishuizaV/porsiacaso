"""Panel editorial: resumen, publicaciones y formularios especializados por tipo."""
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import render_template, request, redirect, url_for, flash, abort, current_app, g
from flask_login import current_user
from sqlalchemy import or_

from admin import admin, solo_admin, puede_editar, bitacora, slug_unico_modelo, regiones_con_ciudades
from consultas import actualizar_busqueda
from extensions import db
from models import (Articulo, Categoria, Ubicacion, Institucion, Enlace, Pagina,
                    MODELOS_DETALLE, ahora, hoy)
from tipos import TIPOS, ORDEN, ENLACES, VIGENCIAS, ESTADOS, SECTORES, RUTAS_RESERVADAS
from utils import (limpiar_html, contenido_vacio, minutos_lectura, url_valida, guardar_imagen,
                   guardar_logo, guardar_pdf, borrar_archivo, slugify, normalizar)
import ajustes
import os
import seo

POR_PAGINA_ADMIN = 25


def carpeta(sub=""):
    return os.path.join(current_app.config["UPLOAD_FOLDER"], sub) if sub \
        else current_app.config["UPLOAD_FOLDER"]


def mis_publicaciones():
    q = Articulo.query
    if not current_user.es_admin:
        q = q.filter_by(autor_id=current_user.id)
    return q


# ---------- Panel principal ----------
@admin.route("/")
def panel():
    base = mis_publicaciones()
    conteo_estado = {k: base.filter(Articulo.estado == k).count() for k, _ in ESTADOS}
    conteo_tipo = dict(base.with_entities(Articulo.tipo, db.func.count(Articulo.id))
                       .group_by(Articulo.tipo).all())
    publicadas = base.filter(Articulo.estado == "publicado")
    por_vencer = (publicadas.filter(Articulo.fecha_limite >= hoy(),
                                    Articulo.fecha_limite <= hoy() + timedelta(days=7))
                  .order_by(Articulo.fecha_limite).all())
    alertas = []
    vencidas_abiertas = publicadas.filter(Articulo.fecha_limite < hoy(),
                                          Articulo.vigencia == "abierta").count()
    if vencidas_abiertas:
        alertas.append((f"{vencidas_abiertas} publicación(es) con fecha límite pasada siguen "
                        "marcadas como «Abierta». El sitio ya las muestra como vencidas; "
                        "revisa si debes archivarlas.",
                        url_for("admin.publicaciones", alerta="vencidas")))
    sin_fuente = publicadas.filter(Articulo.tipo.in_([k for k, d in TIPOS.items() if d["oportunidad"]]),
                                   or_(Articulo.fuente_url.is_(None), Articulo.fuente_url == "")).count()
    if sin_fuente:
        alertas.append((f"{sin_fuente} oportunidad(es) publicadas no indican la fuente oficial.",
                        url_for("admin.publicaciones", alerta="sin_fuente")))
    antiguas = publicadas.filter(Articulo.tipo.in_([k for k, d in TIPOS.items() if d["oportunidad"]]),
                                 or_(Articulo.verificado_en.is_(None),
                                     Articulo.verificado_en < hoy() - timedelta(days=30)),
                                 or_(Articulo.fecha_limite.is_(None), Articulo.fecha_limite >= hoy())
                                 ).count()
    if antiguas:
        alertas.append((f"{antiguas} oportunidad(es) vigentes no se verifican hace más de 30 días.",
                        url_for("admin.publicaciones", alerta="sin_verificar")))
    if current_user.es_admin:
        if not ajustes.obtener("contacto_email"):
            alertas.append(("Falta el correo de contacto del sitio (Sitio → Configuración).",
                            url_for("admin.configuracion")))
        pend = [p for p in Pagina.query.all() if "[PENDIENTE" in p.contenido or "tudominio" in p.contenido]
        if pend:
            alertas.append((f"{len(pend)} página(s) institucional(es) tienen datos de ejemplo o "
                            "pendientes: " + ", ".join(p.titulo for p in pend),
                            url_for("admin.paginas")))
    recientes = base.order_by(Articulo.actualizado.desc()).limit(8).all()
    return render_template("admin/panel.html", conteo_estado=conteo_estado,
                           conteo_tipo=conteo_tipo, por_vencer=por_vencer, alertas=alertas,
                           recientes=recientes, total=sum(conteo_estado.values()))


# ---------- Listado ----------
@admin.route("/publicaciones")
def publicaciones():
    query = mis_publicaciones()
    f = {"q": request.args.get("q", "").strip()[:100], "tipo": request.args.get("tipo", ""),
         "estado": request.args.get("estado", ""), "orden": request.args.get("orden", "actualizado"),
         "alerta": request.args.get("alerta", "")}
    if f["q"]:
        like = f"%{normalizar(f['q'])}%"
        query = query.filter(or_(Articulo.busqueda.like(like), Articulo.titulo.ilike(f"%{f['q']}%")))
    if f["tipo"] in TIPOS:
        query = query.filter(Articulo.tipo == f["tipo"])
    if f["estado"] in dict(ESTADOS):
        query = query.filter(Articulo.estado == f["estado"])
    if f["alerta"] == "vencidas":
        query = query.filter(Articulo.estado == "publicado", Articulo.fecha_limite < hoy())
    elif f["alerta"] == "sin_fuente":
        query = query.filter(Articulo.estado == "publicado",
                             or_(Articulo.fuente_url.is_(None), Articulo.fuente_url == ""))
    elif f["alerta"] == "sin_verificar":
        query = query.filter(Articulo.estado == "publicado",
                             or_(Articulo.verificado_en.is_(None),
                                 Articulo.verificado_en < hoy() - timedelta(days=30)))
    orden = {"creado": Articulo.creado.desc(), "publicado": Articulo.fecha_publicacion.desc(),
             "limite": Articulo.fecha_limite.asc(), "titulo": Articulo.titulo.asc()}
    query = query.order_by(orden.get(f["orden"], Articulo.actualizado.desc()))
    pag = query.paginate(page=request.args.get("page", 1, type=int),
                         per_page=POR_PAGINA_ADMIN, error_out=False)
    return render_template("admin/publicaciones.html", pag=pag, f=f, estados=ESTADOS)


@admin.route("/nueva")
def nueva():
    return render_template("admin/nueva.html", orden=ORDEN)


# Compatibilidad con las direcciones anteriores del panel
@admin.route("/articulo/nuevo")
def articulo_nuevo_antiguo():
    return redirect(url_for("admin.nueva"))


@admin.route("/articulo/<int:id>/editar")
def articulo_editar_antiguo(id):
    return redirect(url_for("admin.publicacion_form", id=id))


# ---------- Lectura y validación de campos ----------
def leer_decimal(texto):
    t = (texto or "").replace("S/", "").replace("US$", "").replace("$", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(",", "")
    elif "," in t:
        t = t.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+", t) else t.replace(",", ".")
    try:
        n = Decimal(t)
    except InvalidOperation:
        raise ValueError
    if n < 0 or n > Decimal("10000000"):
        raise ValueError
    return n.quantize(Decimal("0.01"))


def leer_fecha(texto):
    texto = (texto or "").strip()
    if not texto:
        return None
    return date.fromisoformat(texto)


def leer_detalle(tipo, form, errores):
    """Valores del detalle según la especificación del tipo."""
    valores = {}
    for _titulo, campos in TIPOS[tipo]["campos"]:
        for c in campos:
            bruto = form.get("d_" + c["nombre"], "")
            n, etiqueta = c["nombre"], c["etiqueta"]
            try:
                if c["tipo"] in ("texto",):
                    valores[n] = bruto.strip()[:c["maximo"] or 300] or None
                elif c["tipo"] in ("lineas", "parrafo"):
                    valores[n] = bruto.replace("\r\n", "\n").strip()[:5000] or None
                elif c["tipo"] == "opcion":
                    valores[n] = bruto if bruto in dict(c["opciones"]) else None
                elif c["tipo"] == "numero":
                    valores[n] = int(bruto) if bruto.strip() else None
                    if valores[n] is not None and not (0 < valores[n] < 100000):
                        raise ValueError
                elif c["tipo"] == "decimal":
                    valores[n] = leer_decimal(bruto)
                elif c["tipo"] == "fecha":
                    valores[n] = leer_fecha(bruto)
            except ValueError:
                errores.append(f"«{etiqueta}» no tiene un valor válido.")
                valores[n] = None
    return valores


def leer_enlaces(form, files, actuales, errores):
    """Filas enlace-N-*. Devuelve lista de dicts (sin guardar archivos todavía)."""
    indices = sorted({int(m.group(1)) for k in form for m in [re.match(r"enlace-(\d+)-tipo$", k)] if m})
    filas = []
    for i in indices[:20]:
        tipo = form.get(f"enlace-{i}-tipo", "otro")
        tipo = tipo if tipo in ENLACES else "otro"
        etiqueta = form.get(f"enlace-{i}-etiqueta", "").strip()[:80]
        url = form.get(f"enlace-{i}-url", "").strip()
        archivo = form.get(f"enlace-{i}-archivo", "").strip()
        if archivo not in actuales:   # solo se conservan PDFs que ya eran de esta publicación
            archivo = ""
        pdf = files.get(f"enlace-{i}-pdf")
        if form.get(f"enlace-{i}-quitar"):
            continue
        if not url and not archivo and not (pdf and pdf.filename):
            continue
        if url and not url_valida(url):
            errores.append(f"El enlace «{etiqueta or ENLACES[tipo]}» no es una dirección web "
                           "válida (debe empezar con https://).")
        if tipo == "otro" and not etiqueta:
            errores.append("Escribe el texto del botón para los enlaces de tipo «Otro».")
        filas.append(dict(tipo=tipo, etiqueta=etiqueta, url=url, archivo=archivo, pdf=pdf))
    return filas


def leer_faq(form):
    indices = sorted({int(m.group(1)) for k in form for m in [re.match(r"faq-(\d+)-p$", k)] if m})
    faq = []
    for i in indices[:15]:
        p = form.get(f"faq-{i}-p", "").strip()[:300]
        r = form.get(f"faq-{i}-r", "").strip()[:2000]
        if p and r:
            faq.append({"p": p, "r": r})
    return faq


def buscar_o_crear_institucion(nombre, sector):
    nombre = re.sub(r"\s+", " ", nombre or "").strip()[:200]
    if not nombre:
        return None
    slug = slugify(nombre)
    inst = Institucion.query.filter_by(slug=slug).first()
    if not inst:
        clave = normalizar(nombre)
        inst = next((i for i in Institucion.query.all()
                     if normalizar(i.nombre) == clave or normalizar(i.siglas or "") == clave), None)
    if not inst:
        inst = Institucion(slug=slug_unico_modelo(Institucion, nombre), nombre=nombre,
                           sector=sector if sector in dict(SECTORES) else None)
        db.session.add(inst)
    return inst


def validar_publicacion(tipo, v, det, filas, inst):
    """Errores que impiden PUBLICAR (los borradores se guardan aunque estén incompletos)."""
    info, errores = TIPOS[tipo], []
    if not v["resumen"]:
        errores.append("Escribe un resumen: se muestra en las tarjetas y en Google.")
    for _t, campos in info["campos"]:
        for c in campos:
            if c["requerido"] and det.get(c["nombre"]) in (None, ""):
                errores.append(f"Completa «{c['etiqueta']}».")
    if tipo in ("noticia", "guia", "otro", "empleo") and contenido_vacio(v["contenido"]):
        errores.append(f"Completa «{info['etiqueta_contenido']}».")
    if info["institucion"] and info["oportunidad"] and not inst:
        errores.append("Indica la empresa o institución responsable.")
    if info["oportunidad"] and not v["fuente_url"] and not any(f["url"] or f["archivo"] or
                                                               (f["pdf"] and f["pdf"].filename)
                                                               for f in filas):
        errores.append("Agrega la fuente oficial o al menos un enlace oficial: no se publican "
                       "oportunidades sin fuente verificable.")
    if tipo == "curso" and det.get("costo") == "gratuito" and not v["fuente_url"]:
        errores.append("Para marcar un curso como gratuito, indica la fuente oficial que lo dice.")
    return errores


def advertencias_publicacion(tipo, v, a):
    info, avisos = TIPOS[tipo], []
    if info["oportunidad"]:
        if not v["fecha_limite"]:
            avisos.append("No indicaste fecha límite. Si existe, agrégala para que el sitio "
                          "marque la convocatoria como vencida automáticamente.")
        if not v["verificado_en"]:
            avisos.append("No marcaste la fecha de verificación en la fuente oficial.")
        if v["fecha_limite"] and v["fecha_limite"] < hoy():
            avisos.append("La fecha límite ya pasó: se mostrará como vencida.")
    if len(v["titulo"]) > 90:
        avisos.append("El título es largo; en Google se verá cortado (ideal: menos de 70 letras).")
    if not a.imagen:
        avisos.append("La publicación no tiene imagen: se mostrará una ilustración genérica.")
    if tipo == "empleo":
        motivos = seo.motivos_sin_jobposting(a)
        if motivos and a.estado == "publicado":
            avisos.append("Esta oferta no aparecerá en Google Empleos: " + " ".join(motivos))
    return avisos


def valores_formulario(a, tipo):
    """Valores iniciales del formulario (publicación existente o nueva)."""
    if a:
        d = a.detalle
        det = {c["nombre"]: getattr(d, c["nombre"]) for _t, cs in TIPOS[tipo]["campos"] for c in cs} \
            if d else {}
        return dict(
            titulo=a.titulo, resumen=a.resumen or "", contenido=a.contenido or "",
            categoria_id=a.categoria_id, ubicacion_id=a.ubicacion_id,
            institucion=a.institucion.nombre if a.institucion else "",
            institucion_sector=a.institucion.sector if a.institucion else "",
            datos_texto=a.datos_texto or "", fuente_url=a.fuente_url or "",
            fuente_nombre=a.fuente_nombre or "", fecha_limite=a.fecha_limite,
            vigencia=a.vigencia or "", verificado_en=a.verificado_en, aviso=a.aviso or "",
            notas_internas=a.notas_internas or "", destacado=a.destacado,
            imagen_alt=a.imagen_alt or "", imagen_credito=a.imagen_credito or "",
            programar=a.fecha_publicacion if a.programada else None,
        ), det, [dict(tipo=e.tipo, etiqueta=e.etiqueta or "", url=e.url or "",
                      archivo=e.archivo or "") for e in a.enlaces], a.faq
    cat = Categoria.query.filter_by(slug=TIPOS[tipo]["categoria"]).first() \
        if TIPOS[tipo]["categoria"] else None
    enlaces = [dict(tipo=t, etiqueta="", url="", archivo="") for t in TIPOS[tipo]["enlaces"]]
    return dict(titulo="", resumen="", contenido="", categoria_id=cat.id if cat else None,
                ubicacion_id=None, institucion="", institucion_sector="", datos_texto="",
                fuente_url="", fuente_nombre="", fecha_limite=None,
                vigencia="abierta" if TIPOS[tipo]["oportunidad"] else "",
                verificado_en=None, aviso="", notas_internas="", destacado=False,
                imagen_alt="", imagen_credito="", programar=None), {}, enlaces, []


# ---------- Formulario ----------
@admin.route("/nueva/<tipo>", methods=["GET", "POST"])
@admin.route("/publicacion/<int:id>/editar", methods=["GET", "POST"])
def publicacion_form(tipo=None, id=None):
    a = db.get_or_404(Articulo, id) if id else None
    if a:
        if not puede_editar(a):
            abort(403)
        tipo = a.tipo if a.tipo in TIPOS else "noticia"
    elif tipo not in TIPOS:
        abort(404)
    info = TIPOS[tipo]
    v, det, enlaces, faq = valores_formulario(a, tipo)
    errores, avisos = [], []

    if request.method == "POST":
        f = request.form
        accion = f.get("accion", "borrador")
        accion = accion if accion in ("borrador", "revision", "publicar") else "borrador"
        try:
            fecha_limite = leer_fecha(f.get("fecha_limite"))
        except ValueError:
            fecha_limite = None
            errores.append("La fecha límite no es válida.")
        try:
            verificado_en = leer_fecha(f.get("verificado_en"))
        except ValueError:
            verificado_en = None
            errores.append("La fecha de verificación no es válida.")
        if f.get("verificado_hoy"):
            verificado_en = hoy()
        if verificado_en and verificado_en > hoy():
            errores.append("La fecha de verificación no puede estar en el futuro.")
        programar = None
        if f.get("programar", "").strip():
            try:
                programar = datetime.fromisoformat(f["programar"].strip())
            except ValueError:
                errores.append("La fecha de programación no es válida.")

        v = dict(
            titulo=f.get("titulo", "").strip()[:200], resumen=f.get("resumen", "").strip()[:400],
            contenido=limpiar_html(f.get("contenido", "")),
            categoria_id=f.get("categoria_id", type=int), ubicacion_id=f.get("ubicacion_id", type=int),
            institucion=f.get("institucion", "").strip()[:200],
            institucion_sector=f.get("institucion_sector", ""),
            datos_texto=f.get("datos_texto", "").strip()[:3000],
            fuente_url=f.get("fuente_url", "").strip(), fuente_nombre=f.get("fuente_nombre", "").strip()[:150],
            fecha_limite=fecha_limite, verificado_en=verificado_en,
            vigencia=f.get("vigencia", "") if f.get("vigencia", "") in dict(VIGENCIAS) else "",
            aviso=f.get("aviso", "").strip()[:1000], notas_internas=f.get("notas_internas", "").strip()[:3000],
            destacado=bool(f.get("destacado")),
            imagen_alt=f.get("imagen_alt", "").strip()[:200],
            imagen_credito=f.get("imagen_credito", "").strip()[:200], programar=programar,
        )
        det = leer_detalle(tipo, f, errores)
        actuales = {e.archivo for e in a.enlaces if e.archivo} if a else set()
        filas = leer_enlaces(f, request.files, actuales, errores)
        enlaces = [dict(tipo=x["tipo"], etiqueta=x["etiqueta"], url=x["url"], archivo=x["archivo"])
                   for x in filas]
        faq = leer_faq(f)

        if not v["titulo"]:
            errores.append("El título es obligatorio.")
        categoria = db.session.get(Categoria, v["categoria_id"]) if v["categoria_id"] else None
        if not categoria:
            errores.append("Elige una categoría.")
        ubicacion = db.session.get(Ubicacion, v["ubicacion_id"]) if v["ubicacion_id"] else None
        if v["ubicacion_id"] and not ubicacion:
            errores.append("La zona elegida no existe.")
        if v["fuente_url"] and not url_valida(v["fuente_url"]):
            errores.append("El enlace de la fuente debe ser una dirección web válida (https://…).")
        if det.get("sueldo_min") is not None and det.get("sueldo_max") is not None \
                and det["sueldo_max"] < det["sueldo_min"]:
            errores.append("El sueldo máximo no puede ser menor que el sueldo.")
        if det.get("sueldo_max") is not None and det.get("sueldo_min") is None:
            errores.append("Si indicas un sueldo máximo, indica también el sueldo.")
        if det.get("sueldo_min") is not None and not det.get("moneda"):
            det["moneda"] = "PEN"

        inst_existente = None
        if v["institucion"]:
            inst_existente = Institucion.query.filter_by(slug=slugify(v["institucion"])).first()
        if accion == "publicar" and not errores:
            errores += validar_publicacion(tipo, v, det, filas,
                                           inst_existente or (v["institucion"] or None))

        # Archivos (solo si no hay errores, para no dejar basura)
        imagen = None
        archivo_img = request.files.get("imagen")
        if not errores and archivo_img and archivo_img.filename:
            imagen = guardar_imagen(archivo_img.stream, carpeta())
            if not imagen:
                errores.append("La imagen no es válida (usa JPG, PNG o WEBP).")
        logo = None
        archivo_logo = request.files.get("institucion_logo")
        if not errores and archivo_logo and archivo_logo.filename:
            logo = guardar_logo(archivo_logo.stream, carpeta("logos"))
            if not logo:
                errores.append("El logo no es una imagen válida.")
        if not errores:
            for x in filas:
                if x["pdf"] and x["pdf"].filename:
                    nombre = guardar_pdf(x["pdf"], carpeta("docs"))
                    if not nombre:
                        errores.append("Uno de los documentos no es un PDF válido o supera 8 MB.")
                        break
                    x["archivo"], x["url"] = nombre, ""

        if not errores:
            nuevo = a is None
            if nuevo:
                a = Articulo(autor_id=current_user.id, tipo=tipo,
                             slug=slug_unico_modelo(Articulo, v["titulo"], reservados=RUTAS_RESERVADAS))
                db.session.add(a)
            a.titulo, a.resumen = v["titulo"], v["resumen"]
            a.contenido = v["contenido"] if not contenido_vacio(v["contenido"]) else ""
            a.categoria, a.ubicacion = categoria, ubicacion
            a.datos_texto, a.aviso, a.notas_internas = v["datos_texto"], v["aviso"], v["notas_internas"]
            a.fuente_url, a.fuente_nombre = v["fuente_url"], v["fuente_nombre"]
            a.imagen_alt, a.imagen_credito = v["imagen_alt"], v["imagen_credito"]
            a.fecha_limite, a.verificado_en = v["fecha_limite"], v["verificado_en"]
            a.vigencia = v["vigencia"] or None
            a.faq_json = json.dumps(faq, ensure_ascii=False) if faq else None
            a.institucion = buscar_o_crear_institucion(v["institucion"], v["institucion_sector"]) \
                if info["institucion"] else None
            if logo and a.institucion:
                anterior_logo = a.institucion.logo
                a.institucion.logo = logo
                if anterior_logo:
                    borrar_archivo(carpeta("logos"), anterior_logo)
            if current_user.es_admin:
                a.destacado = v["destacado"]
            d = a.asegurar_detalle()
            if d is not None:
                for k, val in det.items():
                    setattr(d, k, val)

            # Enlaces: se reemplazan por los del formulario; los PDFs que ya no se usan se borran
            anteriores = {e.archivo for e in a.enlaces if e.archivo}
            a.enlaces = [Enlace(tipo=x["tipo"], etiqueta=x["etiqueta"] or None, url=x["url"] or None,
                                archivo=x["archivo"] or None, orden=i) for i, x in enumerate(filas)]
            nuevos_pdf = {x["archivo"] for x in filas if x["archivo"]}

            imagen_anterior = None
            if imagen:
                imagen_anterior = a.imagen
                a.imagen, a.imagen_ancho, a.imagen_alto = imagen
            elif f.get("quitar_imagen") and a.imagen:
                imagen_anterior, a.imagen, a.imagen_ancho, a.imagen_alto = a.imagen, None, None, None

            a.lectura = minutos_lectura(a.contenido)
            a.actualizado = ahora()
            if accion == "publicar":
                a.estado = "publicado"
                if programar and programar > ahora():
                    a.fecha_publicacion = programar
                elif not a.fecha_publicacion or a.fecha_publicacion > ahora():
                    a.fecha_publicacion = ahora()
            elif accion == "revision":
                a.estado = "revision"
            elif a.estado != "archivado":
                a.estado = "borrador"
            db.session.flush()
            actualizar_busqueda(a)
            bitacora("publicacion_" + ("creada" if nuevo else "editada") + f"_{a.estado}",
                     f"#{a.id} {a.titulo}")
            db.session.commit()

            for nombre in anteriores - nuevos_pdf:
                if not Enlace.query.filter_by(archivo=nombre).first():
                    borrar_archivo(carpeta("docs"), nombre)
            if imagen_anterior and not Articulo.query.filter_by(imagen=imagen_anterior).first():
                borrar_archivo(carpeta(), imagen_anterior)

            mensajes = {"publicar": "Publicación publicada.", "revision": "Enviada a revisión.",
                        "borrador": "Borrador guardado."}
            if a.programada:
                flash(f"Publicación programada para el {a.fecha_publicacion:%d/%m/%Y a las %H:%M}.", "ok")
            else:
                flash(mensajes[accion], "ok")
            for aviso in advertencias_publicacion(tipo, v, a):
                flash(aviso, "aviso")
            if f.get("seguir"):
                return redirect(url_for("admin.publicacion_form", id=a.id))
            return redirect(url_for("admin.publicaciones"))

        for e in errores:
            flash(e, "error")

    instituciones = Institucion.query.order_by(Institucion.nombre).all()
    return render_template("admin/publicacion_form.html", a=a, tipo=tipo, info=info, v=v, det=det,
                           enlaces=enlaces, faq=faq, categorias=Categoria.query.order_by(Categoria.orden).all(),
                           regiones=regiones_con_ciudades(), instituciones=instituciones,
                           vigencias=VIGENCIAS, enlaces_tipos=ENLACES, sectores=SECTORES,
                           hoy=hoy())


# ---------- Vista previa y acciones ----------
@admin.route("/publicacion/<int:id>/vista")
def vista_previa(id):
    """Vista previa fiel (sirve para borradores). Nadie más la ve ni Google la indexa."""
    a = db.get_or_404(Articulo, id)
    if not puede_editar(a):
        abort(403)
    from web import render_publicacion
    g.vista_publica = True
    return render_publicacion(a, vista_previa=True)


@admin.route("/articulo/<int:id>/vista")
def articulo_vista(id):
    return redirect(url_for("admin.vista_previa", id=id))


def duplicar(a):
    copia = Articulo(
        tipo=a.tipo, titulo=(a.titulo + " (copia)")[:200], resumen=a.resumen, contenido=a.contenido,
        imagen=a.imagen, imagen_alt=a.imagen_alt, imagen_credito=a.imagen_credito,
        imagen_ancho=a.imagen_ancho, imagen_alto=a.imagen_alto, datos_texto=a.datos_texto,
        fuente_url=a.fuente_url, fuente_nombre=a.fuente_nombre, estado="borrador",
        vigencia=a.vigencia, aviso=a.aviso, faq_json=a.faq_json, lectura=a.lectura,
        categoria_id=a.categoria_id, ubicacion_id=a.ubicacion_id, institucion_id=a.institucion_id,
        autor_id=current_user.id, creado=ahora(), actualizado=ahora(),
        slug=slug_unico_modelo(Articulo, a.titulo + " copia", reservados=RUTAS_RESERVADAS))
    db.session.add(copia)
    d = a.detalle
    if d is not None:
        nuevo = MODELOS_DETALLE[a.info["detalle"]]()
        for col in d.__table__.columns:
            if col.name != "articulo_id":
                setattr(nuevo, col.name, getattr(d, col.name))
        setattr(copia, "detalle_" + a.info["detalle"], nuevo)
    copia.enlaces = [Enlace(tipo=e.tipo, etiqueta=e.etiqueta, url=e.url, archivo=e.archivo,
                            orden=e.orden) for e in a.enlaces]
    db.session.flush()
    actualizar_busqueda(copia)
    return copia


@admin.route("/publicacion/<int:id>/accion", methods=["POST"])
def publicacion_accion(id):
    a = db.get_or_404(Articulo, id)
    if not puede_editar(a):
        abort(403)
    accion = request.form.get("accion")
    volver = request.form.get("volver") or url_for("admin.publicaciones")
    if not volver.startswith("/admin"):
        volver = url_for("admin.publicaciones")

    if accion == "publicar":
        tipo = a.tipo
        v = dict(resumen=a.resumen, contenido=a.contenido, fuente_url=a.fuente_url)
        det = {c["nombre"]: getattr(a.detalle, c["nombre"]) for _t, cs in TIPOS[tipo]["campos"]
               for c in cs} if a.detalle else {}
        filas = [dict(url=e.url, archivo=e.archivo, pdf=None) for e in a.enlaces]
        errores = validar_publicacion(tipo, v, det, filas, a.institucion)
        if errores:
            for e in errores:
                flash(e, "error")
            flash("No se publicó. Edita la publicación y completa lo indicado.", "error")
            return redirect(volver)
        a.estado = "publicado"
        if not a.fecha_publicacion:
            a.fecha_publicacion = ahora()
        msg = "Publicada."
    elif accion == "despublicar":
        a.estado = "borrador"
        msg = "Retirada del sitio (ahora es borrador)."
    elif accion == "archivar":
        a.estado = "archivado"
        msg = "Archivada: sigue accesible por su dirección, pero sale de listados y buscadores."
    elif accion == "revision":
        a.estado = "revision"
        msg = "Marcada como pendiente de revisión."
    elif accion == "verificada":
        a.verificado_en = hoy()
        msg = "Marcada como verificada hoy."
    elif accion == "duplicar":
        copia = duplicar(a)
        bitacora("publicacion_duplicada", f"#{a.id} → #{copia.id}")
        db.session.commit()
        flash("Copia creada como borrador. Revisa y cambia lo necesario.", "ok")
        return redirect(url_for("admin.publicacion_form", id=copia.id))
    elif accion == "eliminar":
        if a.estado == "publicado" and not current_user.es_admin:
            flash("Para eliminar una publicación publicada, primero retírala o pide ayuda a un "
                  "administrador.", "error")
            return redirect(volver)
        imagen, pdfs = a.imagen, [e.archivo for e in a.enlaces if e.archivo]
        bitacora("publicacion_eliminada", f"#{a.id} {a.titulo}")
        db.session.delete(a)
        db.session.commit()
        if imagen and not Articulo.query.filter_by(imagen=imagen).first():
            borrar_archivo(carpeta(), imagen)
        for p in pdfs:
            if not Enlace.query.filter_by(archivo=p).first():
                borrar_archivo(carpeta("docs"), p)
        flash("Publicación eliminada.", "ok")
        return redirect(url_for("admin.publicaciones"))
    else:
        abort(400)
    a.actualizado = ahora()
    bitacora("publicacion_" + accion, f"#{a.id} {a.titulo}")
    db.session.commit()
    flash(msg, "ok")
    return redirect(volver)

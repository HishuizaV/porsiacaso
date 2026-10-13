"""Autopilot: flujo completo, deduplicación, extracción, verificación, calidad y publicación.
Todo con una web simulada: ninguna prueba depende de sitios externos."""
import json

import pytest

from ap_web import WebSimulada, BASE, pdf_con_texto
from extensions import db
from models import Articulo, Institucion, Ubicacion
from autopilot import adaptadores, calidad, flujo, extraccion, dedup
from autopilot.modelos import Fuente, Hallazgo, Tarea, Evidencia, DecisionEditorial, VersionArticulo
from autopilot.red import validar_url, Bloqueado, ip_publica
from ap_web import resolver_publico


@pytest.fixture
def web():
    return WebSimulada()


def fuente_gobpe(**kw):
    inst = Institucion.query.filter_by(nombre="Municipalidad de Prueba").first() or \
        Institucion(slug="muni-prueba", nombre="Municipalidad de Prueba", siglas="MPP", sector="publico")
    datos = dict(nombre="Muni prueba CAS", institucion=inst, url_principal=BASE,
                 url_listado=f"{BASE}/colecciones/1-convocatorias-cas", tipo_contenido="convocatoria",
                 ubicacion=Ubicacion.query.filter_by(slug="chiclayo").first(), formato="html",
                 estado="activa", permite_extraccion=True, confianza="alta",
                 config_json=json.dumps({"patron_enlace": r"/informes-publicaciones/\d+",
                                         "patron_id": r"/informes-publicaciones/(\d+)",
                                         "palabras_clave": ["convocatoria"]}))
    datos.update(kw)
    f = Fuente(**datos)
    db.session.add(f)
    db.session.commit()
    return f


def procesar_todo(desc, cfg=None):
    cfg = cfg or calidad.configuracion()
    resultados = {}
    for h in Hallazgo.query.filter_by(estado="nuevo").order_by(Hallazgo.id).all():
        resultados[h.titulo] = flujo.procesar_hallazgo(h, desc, cfg)
        db.session.commit()
    return resultados


# ---------- Flujo completo ----------
def test_flujo_fuente_a_borradores(app, web):
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        nuevos, vistos = flujo.consultar_fuente(f, desc)
        db.session.commit()
        assert (nuevos, vistos) == (3, 3)   # el TUPA queda fuera por las palabras clave
        assert Tarea.query.filter_by(tipo="procesar_hallazgo").count() == 3
        r = procesar_todo(desc)
        assert r["Convocatoria CAS N° 003-2026-MPP"] == "revision"
        assert r["Convocatoria CAS: Asistente administrativo"] == "revision"
        assert r["Convocatoria CAS N° 001-2026-MPP"] == "rechazado"   # vencida

        conv = Articulo.query.filter_by(tipo="convocatoria").one()
        assert conv.estado == "revision" and conv.origen == "autopilot"
        assert conv.detalle_empleo.vacantes == 12
        assert conv.fecha_limite == web.fecha_limite        # leída del cronograma del PDF de bases
        assert conv.titulo.startswith("Convocatoria CAS N° 003-2026-MPP: 12 plazas")
        tipos = [e.tipo for e in conv.enlaces]
        assert tipos[:2] == ["convocatoria", "bases"] and "anexo" in tipos
        assert all(e.url.startswith("https://") for e in conv.enlaces)

        emp = Articulo.query.filter_by(tipo="empleo").one()   # una sola vacante -> empleo
        d = emp.detalle_empleo
        assert d.cargo == "Asistente administrativo" and float(d.sueldo_min) == 2500 and d.vacantes == 1
        assert "Registrar y archivar documentos" in d.funciones
        assert emp.enlace_principal.url == "https://postula.muniprueba.gob.pe/cas/2"
        assert emp.autor.rol == "servicio" and emp.publicado_por_id is None


def test_evidencia_y_trazabilidad(app, web):
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        h = Hallazgo.query.filter(Hallazgo.titulo.like("%003-2026%")).one()
        ev = {e.campo: e for e in h.evidencias}
        assert ev["vacantes"].estado == "confirmado" and "12" in ev["vacantes"].fragmento
        assert ev["fecha_limite"].estado == "confirmado" and ev["fecha_limite"].pagina == 1
        assert ev["fecha_limite"].origen.endswith(".pdf?v=1")
        assert ev["region"].estado == "derivado"
        assert DecisionEditorial.query.filter_by(hallazgo_id=h.id).one().decision == "revision"


def test_rechaza_vencidas_y_no_oportunidades(app, web):
    with app.app_context():
        inst = Institucion(slug="becas", nombre="Programa de Becas", sector="publico")
        f = Fuente(nombre="Becas RSS", institucion=inst, url_principal="https://becas.prueba.gob.pe/",
                   url_listado="https://becas.prueba.gob.pe/feed/", tipo_contenido="beca", formato="rss",
                   estado="activa", permite_extraccion=True)
        db.session.add(f)
        db.session.commit()
        desc = web.descargador()
        assert flujo.consultar_fuente(f, desc) == (2, 2)
        r = procesar_todo(desc)
        assert r["Ana: «Gracias a la beca cumplí mi sueño»"] == "rechazado"   # testimonio
        assert r["Convocatoria Beca Talento 2026"] == "revision"
        beca = Articulo.query.filter_by(tipo="beca").one()
        assert beca.detalle_beca.publico.startswith("Egresados de secundaria")
        assert "Matrícula y pensiones" in beca.detalle_beca.cobertura
        assert {e.tipo for e in beca.enlaces} >= {"postular", "bases"}


def test_adaptador_json_y_curso_gratuito(app, web):
    with app.app_context():
        inst = Institucion(slug="instituto", nombre="Instituto de Prueba", sector="publico")
        f = Fuente(nombre="API cursos", institucion=inst, url_principal="https://datos.prueba.gob.pe/",
                   url_listado="https://datos.prueba.gob.pe/api/cursos", tipo_contenido="curso", formato="json",
                   estado="activa", permite_extraccion=True,
                   config_json=json.dumps({"ruta_lista": "data.items", "campos": {"url": "enlace", "titulo": "nombre",
                                                                                   "id": "id", "fecha": "publicado"}}))
        db.session.add(f)
        db.session.commit()
        desc = web.descargador()
        assert flujo.consultar_fuente(f, desc) == (1, 1)
        assert Hallazgo.query.one().id_externo == "77"
        assert procesar_todo(desc)["Curso gratuito de Excel básico"] == "revision"
        c = Articulo.query.filter_by(tipo="curso").one()
        assert c.detalle_curso.costo == "gratuito" and c.detalle_curso.modalidad == "virtual"
        assert "gratuito" in c.titulo.lower() and not c.titulo.lower().startswith("curso gratuito: curso")
        assert c.detalle_curso.fecha_inicio.month == 11


def test_procesar_pdf_directo(app, web):
    with app.app_context():
        web.agregar("https://www.gob.pe/aviso.pdf", "application/pdf",
                    pdf_con_texto(["CONVOCATORIA CAS N 010-2026-GR", "Se convoca a 4 plazas", "hasta el 1 de enero de 2099"]))
        f = fuente_gobpe(nombre="PDF directo", formato="pdf", url_listado="https://www.gob.pe/aviso.pdf")
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        h = Hallazgo.query.one()
        r = flujo.analizar(h, desc, calidad.configuracion())
        assert r["datos"]["vacantes"].valor == 4
        assert r["datos"]["codigo"].valor.startswith("CAS N 010-2026")


# ---------- Duplicados e idempotencia ----------
def test_repetir_consulta_no_duplica(app, web):
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        antes = Articulo.query.count()
        assert flujo.consultar_fuente(f, desc)[0] == 0
        assert procesar_todo(desc) == {}
        assert Articulo.query.count() == antes and Hallazgo.query.count() == 3
        assert flujo.encolar("procesar_hallazgo", 1, "procesar:1") is None   # clave idempotente


def test_duplicado_por_documento_y_codigo(app, web):
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        # La misma convocatoria publicada en otra URL (p. ej. otra sección) con el mismo PDF
        otra = f"{BASE}/noticias/555-se-abre-la-convocatoria-cas-003-2026"
        web.paginas[otra] = web.paginas[f"{BASE}/informes-publicaciones/9001-convocatoria-cas-n-003-2026-mpp"]
        h = Hallazgo(fuente_id=f.id, url=otra, url_normalizada=dedup.normalizar_url(otra), titulo="Se abre la CAS 003")
        db.session.add(h)
        db.session.commit()
        assert flujo.procesar_hallazgo(h, desc, calidad.configuracion()) == "duplicado"
        assert "documento" in h.motivo or "convocatoria" in h.motivo or "contenido" in h.motivo
        assert Articulo.query.filter_by(tipo="convocatoria").count() == 1


def test_normalizar_url_y_similitud():
    a = dedup.normalizar_url("HTTPS://WWW.Gob.pe/a/b/?utm_source=x&b=2&a=1#frag")
    assert a == "https://www.gob.pe/a/b?a=1&b=2"
    texto = "La municipalidad convoca a doce plazas para diversas dependencias con requisitos y bases " * 3
    assert dedup.similitud(texto, texto + " Actualizado.") > 0.85
    assert dedup.similitud(texto, "Curso gratuito de Excel para emprendedores de la región norte") < 0.2


def test_cambio_en_convocatoria_genera_propuesta_no_sobrescribe(app, web):
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        emp = Articulo.query.filter_by(tipo="empleo").one()
        h = Hallazgo.query.filter_by(articulo_id=emp.id).one()
        url = h.url
        estado, tipo, cuerpo, cab = web.paginas[url]
        web.agregar(url, tipo, cuerpo.decode().replace("S/ 2,500", "S/ 2,900"))
        assert flujo.revisar_hallazgo(h, desc, calidad.configuracion()) == "actualizacion"
        db.session.commit()
        assert float(emp.detalle_empleo.sueldo_min) == 2500        # no se sobrescribió
        v = VersionArticulo.query.filter_by(articulo_id=emp.id, estado="pendiente").one()
        assert "sueldo_min" in v.resumen_cambios
        # Repetir la revisión no crea otra propuesta igual
        flujo.revisar_hallazgo(h, desc, calidad.configuracion())
        assert VersionArticulo.query.filter_by(articulo_id=emp.id, estado="pendiente").count() == 1


# ---------- Extracción y clasificación ----------
def test_extraccion_fechas_y_listas():
    from datetime import date
    t = "Fechas de las sesiones: Lunes y miércoles, 19, 21, 26 y 28 de octubre de 2026"
    assert extraccion._fecha_inicio(t, "u", date(2026, 10, 1)).valor == date(2026, 10, 19)
    d = extraccion.fecha_limite("Registro de postulantes del 2 al 6 de noviembre de 2026", "u", date(2026, 10, 1))
    assert d.valor == date(2026, 11, 6)
    d = extraccion.fecha_limite("Sin fechas aquí", "u", date(2026, 10, 1))
    assert d.estado == "no_encontrado" and d.valor is None


def test_sueldos_distintos_en_empleo_es_contradictorio():
    d = extraccion._sueldo("Remuneración: S/ 2,500 ... remuneración mensual S/ 3,000", "u", "empleo")
    assert d.estado == "contradictorio"


def test_clasificacion_tipo():
    from autopilot.clasificador import detectar_tipo, parece_no_oportunidad
    assert detectar_tipo("Convocatoria CAS N° 1", "cubrir 30 plazas", "empleo", 30) == "convocatoria"
    assert detectar_tipo("Curso virtual de Excel", "taller y capacitación", "empleo") == "curso"
    assert parece_no_oportunidad("Exbecarios trabajan para contribuir al éxito")


# ---------- Seguridad del contenido externo ----------
def test_instrucciones_maliciosas_no_se_obedecen(app, web):
    with app.app_context():
        f = fuente_gobpe(permite_autopublicacion=True)
        url = "https://www.gob.pe/institucion/muniprueba/informes-publicaciones/9666-convocatoria-cas-trampa"
        h = Hallazgo(fuente_id=f.id, url=url, url_normalizada=dedup.normalizar_url(url), titulo="Chofer")
        db.session.add(h)
        db.session.commit()
        cfg = dict(calidad.configuracion(), modo="C", politica_completa=True, tipos_auto=["empleo", "convocatoria"])
        r = flujo.procesar_hallazgo(h, web.descargador(), cfg)
        assert r == "revision"   # nunca se autopublica, aunque la política lo permitiría
        a = Articulo.query.one()
        assert a.estado == "revision" and "sospechoso" in a.notas_internas


def test_ssrf_bloqueado():
    for url in ("http://localhost/x", "http://127.0.0.1/admin", "http://169.254.169.254/latest/meta-data",
                "http://interno.test/", "http://metadata.test/", "file:///etc/passwd", "ftp://x.gob.pe/",
                "http://usuario:clave@x.gob.pe/", "http://x.gob.pe:8080/", "http://[::1]/", "http://10.0.0.5/"):
        with pytest.raises(Bloqueado):
            validar_url(url, resolver_publico)
    assert validar_url("https://www.gob.pe/x", resolver_publico) == "www.gob.pe"
    assert not ip_publica("192.168.1.10") and ip_publica("8.8.8.8")


def test_redireccion_a_red_interna_bloqueada(web):
    web.agregar("https://www.gob.pe/salto", "text/html", "", estado=302,
                cabeceras={"location": "http://169.254.169.254/latest/meta-data"})
    with pytest.raises(Bloqueado):
        web.descargador().obtener("https://www.gob.pe/salto")
    assert not any("169.254" in u for _m, u in web.pedidos)


def test_robots_y_tamano_maximo(web):
    web.agregar("https://cerrado.gob.pe/robots.txt", "text/plain", "User-agent: *\nDisallow: /\n")
    web.agregar("https://cerrado.gob.pe/x", "text/html", "<html>no</html>")
    with pytest.raises(Bloqueado):
        web.descargador().obtener("https://cerrado.gob.pe/x")
    assert ("GET", "https://cerrado.gob.pe/x") not in web.pedidos
    web.agregar("https://www.gob.pe/enorme", "text/html", "x" * 5000)
    with pytest.raises(Bloqueado):
        web.descargador(max_bytes=1000).obtener("https://www.gob.pe/enorme")
    web.agregar("https://www.gob.pe/programa.exe", "application/octet-stream", b"MZ")
    with pytest.raises(Bloqueado):
        web.descargador().obtener("https://www.gob.pe/programa.exe")


def test_enlaces_rotos_no_se_publican(app, web):
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        del web.paginas["https://postula.muniprueba.gob.pe/cas/2"]   # el botón de postular da 404
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        emp = Articulo.query.filter_by(tipo="empleo").one()
        assert all("postula.muniprueba" not in (e.url or "") for e in emp.enlaces)
        assert emp.estado == "revision"


# ---------- Regresiones detectadas en la jornada real (13/10/2026) ----------
def test_pdf_grande_no_se_reporta_como_roto(web):
    web.agregar("https://cdn.www.gob.pe/grande.pdf", "application/pdf", b"%PDF-1.4" + b"0" * 2_000_000)
    ok, estado, _ = web.descargador().comprobar_enlace("https://cdn.www.gob.pe/grande.pdf")
    assert ok and estado == 200


def test_pagina_antigua_sin_cierre_se_descarta(app, web):
    from ap_web import pagina_gobpe
    url = f"{BASE}/informes-publicaciones/7777-convocatoria-cas-n-002-2025-mpp"
    web.agregar(url, "text/html", pagina_gobpe("Convocatoria CAS N° 002-2025-MPP", "Municipalidad de Prueba",
                "<p>Concurso público</p><p>1 de setiembre de 2025</p><p>Proceso para cubrir 50 plazas en diversas "
                "dependencias de la municipalidad.</p><p><a href='https://cdn.www.gob.pe/x/7777-base.pdf'>Descargar</a></p>"))
    web.agregar("https://cdn.www.gob.pe/x/7777-base.pdf", "application/pdf", pdf_con_texto([""]))
    with app.app_context():
        f = fuente_gobpe()
        h = Hallazgo(fuente_id=f.id, url=url, url_normalizada=dedup.normalizar_url(url), titulo="CAS 002-2025")
        db.session.add(h)
        db.session.commit()
        assert flujo.procesar_hallazgo(h, web.descargador(), calidad.configuracion()) == "rechazado"
        assert "probablemente ya no está vigente" in h.motivo


def test_bases_escaneadas_se_advierten(app, web):
    url = f"{BASE}/informes-publicaciones/9001-convocatoria-cas-n-003-2026-mpp"
    web.agregar("https://cdn.www.gob.pe/uploads/document/file/1/9001-base-de-la-convocatoria-cas-003-2026-mpp.pdf?v=1",
                "application/pdf", pdf_con_texto([""]))   # PDF sin texto (imagen escaneada)
    with app.app_context():
        f = fuente_gobpe()
        h = Hallazgo(fuente_id=f.id, url=url, url_normalizada=dedup.normalizar_url(url), titulo="CAS 003")
        db.session.add(h)
        db.session.commit()
        r = flujo.analizar(h, web.descargador(), calidad.configuracion())
        assert any("PDF escaneado" in m for m in r["motivos"]) or any("escaneado" in t for t, ok, g in r["checklist"])


def test_documentos_administrativos_y_notas_no_son_oportunidades():
    from autopilot.clasificador import parece_no_oportunidad
    for t in ("ACTA N° 14-2026-GR.LAMB-COM-OXI del Proceso de selección", "CIRCULAR Nº 003-2026-GR.LAMB",
              "CONVENIO DE INVERSION N° 000004-2026-GR.LAMB/GR", "RESULTADOS | Curso: Gestión de APP"):
        assert parece_no_oportunidad(t), t
    assert not parece_no_oportunidad("Convocatoria CAS N° 003-2026-MPP")


def test_nota_institucional_sin_accion_se_descarta():
    from datetime import date
    from autopilot.clasificador import relevancia
    rel, motivos = relevancia({}, "beca", [("convocatoria", None, "https://x.gob.pe")], date(2026, 10, 13),
                              "Pronabec y Derrama Magisterial coordinan acciones para impulsar becas")
    assert rel < 30 and any("no parece una convocatoria abierta" in m for m in motivos)


def test_un_solo_boton_por_tipo():
    enlaces = [("Inscríbete aquí", "https://a.gob.pe/1"), ("Inscríbete aquí", "https://a.gob.pe/2"),
               *[("Anexo", f"https://a.gob.pe/anexo{i}.pdf") for i in range(7)]]
    cls = extraccion.clasificar_enlaces(enlaces, "https://a.gob.pe/pagina")
    tipos = [t for t, _e, _u in cls]
    assert tipos.count("postular") == 1 and tipos.count("anexo") == 4

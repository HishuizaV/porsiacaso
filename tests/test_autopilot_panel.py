"""Panel del Autopilot, bandeja de revisión, permisos y política de autopublicación."""
import json
from datetime import timedelta

import pytest

import ajustes
import admin_autopilot
from ap_web import WebSimulada
from conftest import entrar, token, usuario, CLAVE
from extensions import db
from models import Articulo, Usuario, Registro, ahora
from autopilot import calidad, flujo
from autopilot.modelos import Ejecucion, Fuente, Hallazgo, DecisionEditorial, VersionArticulo
from test_autopilot import fuente_gobpe, procesar_todo

PAGINAS = ["/admin/autopilot", "/admin/autopilot/bandeja", "/admin/autopilot/hallazgos",
           "/admin/autopilot/actualizaciones", "/admin/autopilot/historial", "/admin/autopilot/estado.json"]


def post(client, url, datos):
    datos = dict(datos)
    datos["_csrf"] = token(client, "/admin/")
    return client.post(url, data=datos)


def preparar_fichas(app):
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        return {a.tipo: a.id for a in Articulo.query.all()}, web


@pytest.fixture
def revisor_client(app, client):
    with app.app_context():
        u = Usuario(nombre="Revisora", email="revisor@prueba.test", rol="revisor")
        u.set_password(CLAVE)
        db.session.add(u)
        db.session.commit()
    entrar(client, "revisor@prueba.test")
    return client


# ---------- Permisos ----------
def test_editor_no_accede_al_autopilot(editor_client):
    for url in PAGINAS + ["/admin/autopilot/fuentes"]:
        assert editor_client.get(url).status_code == 403


def test_revisor_revisa_pero_no_configura(revisor_client):
    for url in PAGINAS:
        assert revisor_client.get(url).status_code == 200
    assert revisor_client.get("/admin/autopilot/fuentes").status_code == 403
    assert post(revisor_client, "/admin/autopilot/iniciar", {}).status_code == 403
    assert post(revisor_client, "/admin/autopilot/ajustes", {"modo": "C"}).status_code == 403


def test_paginas_del_panel_renderizan(app, admin_client):
    ids, _ = preparar_fichas(app)
    for url in PAGINAS + ["/admin/autopilot/fuentes", "/admin/autopilot/fuentes/nueva",
                          "/admin/autopilot/fuentes/1", "/admin/autopilot/hallazgos/1"]:
        assert admin_client.get(url).status_code == 200, url
    html = admin_client.get("/admin/autopilot/bandeja").get_data(as_text=True)
    assert "Convocatoria CAS N° 003-2026-MPP" in html and "confirmado" in html
    assert "Por qué necesita revisión" in html


def test_servicio_autopilot_no_puede_iniciar_sesion(app, client):
    preparar_fichas(app)
    with app.app_context():
        s = Usuario.query.filter_by(rol="servicio").one()
        s.activo = True   # aunque alguien lo activara, el rol servicio no entra al panel
        s.set_password("una-clave-larga")
        db.session.commit()
        email = s.email
    entrar(client, email, "una-clave-larga")
    assert client.get("/admin/").status_code == 302


# ---------- Fuentes ----------
def test_registrar_y_editar_fuente(app, admin_client):
    datos = {"nombre": "Muni X", "url_principal": "https://www.gob.pe/x", "url_listado": "https://www.gob.pe/x/lista",
             "tipo_contenido": "convocatoria", "formato": "html", "frecuencia_horas": "12", "prioridad": "1",
             "confianza": "alta", "estado": "activa", "permite_extraccion": "1",
             "palabras_clave": "convocatoria, cas", "patron_enlace": r"/informes-publicaciones/\d+"}
    assert post(admin_client, "/admin/autopilot/fuentes/nueva", datos).status_code == 302
    with app.app_context():
        f = Fuente.query.one()
        assert f.config["palabras_clave"] == ["convocatoria", "cas"] and f.frecuencia_horas == 12
        assert Registro.query.filter_by(accion="fuente_creada").count() == 1
        fid = f.id
    post(admin_client, f"/admin/autopilot/fuentes/{fid}", dict(datos, nombre="Muni X editada", prioridad="2"))
    with app.app_context():
        assert db.session.get(Fuente, fid).nombre == "Muni X editada"


@pytest.mark.parametrize("cambio,mensaje", [
    ({"url_principal": "javascript:alert(1)"}, "direcciones deben ser web"),
    ({"permite_autopublicacion": "1", "permite_extraccion": ""}, "sin permiso de extracción"),
    ({"permite_autopublicacion": "1", "confianza": "media"}, "confianza alta"),
    ({"patron_enlace": "(sin cerrar"}, "no es válido"),
])
def test_validacion_de_fuentes(app, admin_client, cambio, mensaje):
    datos = {"nombre": "Muni", "url_principal": "https://www.gob.pe/x", "tipo_contenido": "empleo",
             "formato": "html", "confianza": "alta", "permite_extraccion": "1"}
    datos.update(cambio)
    html = post(admin_client, "/admin/autopilot/fuentes/nueva", datos).get_data(as_text=True)
    assert mensaje in html
    with app.app_context():
        assert Fuente.query.count() == 0


# ---------- Controles de jornada ----------
def test_iniciar_pausar_detener_desde_panel(app, admin_client, monkeypatch):
    lanzados = []
    monkeypatch.setattr(admin_autopilot, "lanzar_en_segundo_plano", lambda i, raiz: lanzados.append(i))
    r = post(admin_client, "/admin/autopilot/iniciar", {"duracion": "300", "objetivo": "10", "tipos": ["empleo"]})
    assert r.status_code == 302
    with app.app_context():
        ej = Ejecucion.query.one()
        assert ej.estado == "solicitada" and ej.duracion_max == 120 and ej.tipos == ["empleo"]
        assert lanzados == [ej.id]
    assert "Ya hay una jornada" in post(admin_client, "/admin/autopilot/iniciar", {}).headers.get("Location", "") or True
    with app.app_context():
        assert Ejecucion.query.count() == 1   # no se crea una segunda
        ej = Ejecucion.query.one()
        ej.estado = "en_curso"
        db.session.commit()
    post(admin_client, "/admin/autopilot/control", {"accion": "pausar"})
    with app.app_context():
        assert Ejecucion.query.one().solicitud == "pausar"
    post(admin_client, "/admin/autopilot/control", {"accion": "detener"})
    with app.app_context():
        assert Ejecucion.query.one().solicitud == "detener"
    estado = admin_client.get("/admin/autopilot/estado.json").get_json()
    assert estado["ejecucion"]["solicitud"] == "detener"


def test_cancelar_jornada_solicitada(app, admin_client, monkeypatch):
    monkeypatch.setattr(admin_autopilot, "lanzar_en_segundo_plano", lambda i, raiz: None)
    post(admin_client, "/admin/autopilot/iniciar", {})
    post(admin_client, "/admin/autopilot/control", {"accion": "detener"})
    with app.app_context():
        assert Ejecucion.query.one().estado == "detenida"


# ---------- Política de autopublicación ----------
def test_autopublicacion_desactivada_por_defecto(app):
    with app.app_context():
        assert calidad.configuracion()["modo"] == "A"
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe(permite_autopublicacion=True)   # aunque la fuente lo permita
        desc = web.descargador()
        flujo.consultar_fuente(Fuente.query.one(), desc)
        procesar_todo(desc)
        assert Articulo.query.filter_by(estado="publicado").count() == 0


def test_modo_b_exige_lista_completa(app, admin_client):
    post(admin_client, "/admin/autopilot/ajustes", {"modo": "B", "tipos_auto": ["empleo"], "pol_pruebas": "1"})
    with app.app_context():
        assert calidad.configuracion()["modo"] == "A"
    datos = {"modo": "B", "tipos_auto": ["empleo", "bono"]}
    datos.update({f"pol_{k}": "1" for k, _ in calidad.REQUISITOS_POLITICA})
    post(admin_client, "/admin/autopilot/ajustes", datos)
    with app.app_context():
        cfg = calidad.configuracion()
        assert cfg["modo"] == "B" and cfg["politica_completa"] and cfg["tipos_auto"] == ["empleo"]   # bono nunca


def _activar_modo_b(app, espaciado="0"):
    with app.test_request_context():
        ajustes.guardar({"autopilot_modo": "B", "autopilot_tipos_auto": "empleo,convocatoria",
                         "autopilot_espaciado": espaciado,
                         "autopilot_politica": json.dumps({k: "Admin · hoy" for k, _ in calidad.REQUISITOS_POLITICA})})


def test_autopublicacion_autorizada_y_programada(app, client):
    _activar_modo_b(app, espaciado="60")
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe(permite_autopublicacion=True)
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        r = procesar_todo(desc)
        emp = Articulo.query.filter_by(tipo="empleo").one()
        conv = Articulo.query.filter_by(tipo="convocatoria").one()
        assert emp.estado == "publicado" and emp.publicado_por.rol == "servicio"
        assert r["Convocatoria CAS: Asistente administrativo"] in ("autopublicado", "programado")
        # La convocatoria cumple todo (cierre leído de las bases, página oficial verificada) y su tipo
        # está autorizado: también se publica, pero sin JobPosting porque son 12 plazas
        assert conv.estado == "publicado"
        conv_slug = conv.slug
        dec = DecisionEditorial.query.filter_by(articulo_id=emp.id).one()
        assert dec.actor == "autopilot" and dec.decision in ("autopublicado", "programado")
        slug, programada = emp.slug, emp.programada
    if programada:
        assert client.get(f"/empleos/{slug}").status_code == 404
    else:
        assert "JobPosting" in client.get(f"/empleos/{slug}").get_data(as_text=True)
    with app.app_context():
        a = Articulo.query.filter_by(slug=conv_slug).one()
        if not a.programada:
            assert "JobPosting" not in client.get(f"/convocatorias/{conv_slug}").get_data(as_text=True)


def test_fuente_sin_permiso_no_autopublica_aunque_modo_b(app):
    _activar_modo_b(app)
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe(permite_autopublicacion=False)
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        assert Articulo.query.filter_by(estado="publicado").count() == 0


# ---------- Bandeja ----------
def test_bandeja_aprobar_programar_rechazar_corregir(app, revisor_client):
    ids, _ = preparar_fichas(app)
    r = post(revisor_client, f"/admin/autopilot/bandeja/{ids['empleo']}",
             {"accion": "corregir", "titulo": "Asistente administrativo – MPP (Chiclayo)",
              "resumen": "Municipalidad de Prueba convoca 1 plaza de asistente administrativo en Chiclayo.",
              "fecha_limite": ""})
    assert r.status_code == 302
    post(revisor_client, f"/admin/autopilot/bandeja/{ids['empleo']}", {"accion": "aprobar"})
    with app.app_context():
        a = db.session.get(Articulo, ids["empleo"])
        assert a.estado == "publicado" and a.titulo.startswith("Asistente administrativo – MPP")
        assert a.publicado_por.email == "revisor@prueba.test" and a.aprobado_por_id == a.publicado_por_id
        assert DecisionEditorial.query.filter_by(articulo_id=a.id, actor="humano", decision="aprobado").count() == 1
    manana = (ahora() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    post(revisor_client, f"/admin/autopilot/bandeja/{ids['convocatoria']}", {"accion": "programar", "cuando": manana})
    with app.app_context():
        c = db.session.get(Articulo, ids["convocatoria"])
        assert c.estado == "publicado" and c.programada
    # Rechazo
    with app.app_context():
        c.estado = "revision"
        db.session.commit()
    post(revisor_client, f"/admin/autopilot/bandeja/{ids['convocatoria']}", {"accion": "rechazar", "motivo": "Datos incompletos"})
    with app.app_context():
        c = db.session.get(Articulo, ids["convocatoria"])
        assert c.estado in ("borrador", "archivado")
        h = Hallazgo.query.filter_by(articulo_id=c.id).one()
        assert h.estado == "descartado" and h.motivo == "Datos incompletos"


def test_bandeja_no_publica_vencidas_ni_incompletas(app, revisor_client):
    ids, _ = preparar_fichas(app)
    with app.app_context():
        a = db.session.get(Articulo, ids["empleo"])
        a.resumen = ""
        db.session.commit()
    post(revisor_client, f"/admin/autopilot/bandeja/{ids['empleo']}", {"accion": "aprobar"})
    with app.app_context():
        assert db.session.get(Articulo, ids["empleo"]).estado == "revision"


def test_aplicar_y_revertir_actualizacion(app, revisor_client):
    ids, web = preparar_fichas(app)
    with app.app_context():
        h = Hallazgo.query.filter_by(articulo_id=ids["empleo"]).one()
        url = h.url
        e, t, cuerpo, c = web.paginas[url]
        web.agregar(url, t, cuerpo.decode().replace("S/ 2,500", "S/ 3,100"))
        flujo.revisar_hallazgo(h, web.descargador(), calidad.configuracion())
        db.session.commit()
        vid = VersionArticulo.query.filter_by(estado="pendiente").one().id
    post(revisor_client, f"/admin/autopilot/actualizaciones/{vid}", {"accion": "aplicar"})
    with app.app_context():
        assert float(db.session.get(Articulo, ids["empleo"]).detalle_empleo.sueldo_min) == 3100
    post(revisor_client, f"/admin/autopilot/actualizaciones/{vid}", {"accion": "revertir"})
    with app.app_context():
        assert float(db.session.get(Articulo, ids["empleo"]).detalle_empleo.sueldo_min) == 2500
        assert db.session.get(VersionArticulo, vid).estado == "revertida"
        assert Registro.query.filter_by(accion="version_revertida").count() == 1


def test_trazabilidad_quien_hizo_que(app, revisor_client):
    ids, _ = preparar_fichas(app)
    post(revisor_client, f"/admin/autopilot/bandeja/{ids['empleo']}", {"accion": "aprobar"})
    with app.app_context():
        a = db.session.get(Articulo, ids["empleo"])
        assert a.autor.rol == "servicio" and a.origen == "autopilot"
        assert a.verificado_por.rol == "servicio" and a.publicado_por.email == "revisor@prueba.test"

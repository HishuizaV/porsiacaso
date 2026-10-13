"""Publicaciones programadas: invisibles en todos los canales hasta su hora; sincronización con el servidor."""
import json
import time
from datetime import timedelta

import httpx
import pytest

import ajustes
from conftest import crear, empleo_valido, DESCRIPCION_LARGA
from extensions import db
from models import Articulo, ahora
from autopilot import calidad
from autopilot.sincronizar import enviar_pendientes, firmar

SECRETO = "s" * 40


def programada(app, horas=5):
    with app.app_context():
        a = empleo_valido(titulo="Empleo programado en Chiclayo", fecha_publicacion=ahora() + timedelta(hours=horas))
        return a.slug


def test_programada_invisible_en_todos_los_canales(app, client):
    slug = programada(app)
    with app.app_context():
        crear(tipo="empleo", titulo="Otro empleo visible", zona="chiclayo", institucion="Municipalidad de Chiclayo",
              detalle=dict(cargo="Auxiliar"), dias_limite=5)
    assert client.get(f"/empleos/{slug}").status_code == 404                     # URL directa
    assert client.get(f"/articulo/{slug}").status_code == 404
    for url in ("/", "/empleos", "/empleos/region/lambayeque", "/zona/chiclayo", "/categoria/empleo",
                "/buscar?q=programado", "/sitemap.xml", "/empleos/otro-empleo-visible"):
        html = client.get(url).get_data(as_text=True).lower()
        assert "empleo programado en chiclayo" not in html and slug not in html, url   # listados, buscador, sitemap, relacionados
    r = client.post("/api/asistente", json={"mensaje": "trabajo programado en Chiclayo"})
    assert all("programado" not in x["titulo"].lower() for x in r.get_json()["resultados"])   # asistente


def test_programada_aparece_sola_a_su_hora(app, client):
    slug = programada(app)
    assert client.get(f"/empleos/{slug}").status_code == 404
    with app.app_context():   # simula el paso del tiempo: nadie tiene que «activarla»
        a = Articulo.query.filter_by(slug=slug).one()
        a.fecha_publicacion = ahora() - timedelta(minutes=1)
        db.session.commit()
    assert client.get(f"/empleos/{slug}").status_code == 200
    assert slug in client.get("/sitemap.xml").get_data(as_text=True)


def test_las_respuestas_publicas_no_se_cachean_en_el_servidor(app, client):
    programada(app)
    r = client.get("/empleos")
    assert "max-age" not in r.headers.get("Cache-Control", "")


# ---------- Sincronización laptop -> servidor ----------
@pytest.fixture
def servidor(tmp_path, monkeypatch):
    """Segunda app (el «servidor público») con su propia base."""
    monkeypatch.setenv("AUTOPILOT_TOKEN", SECRETO)
    from app import crear_app
    from models import Categoria, Ubicacion, Usuario
    from datos_iniciales import CATEGORIAS_INICIALES
    srv = crear_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'servidor.db'}",
                     "UPLOAD_FOLDER": str(tmp_path / "up2"), "SECRET_KEY": "srv"})
    with srv.app_context():
        db.create_all()
        for i, (s, c, n, ic, d) in enumerate(CATEGORIAS_INICIALES):
            db.session.add(Categoria(slug=s, corto=c, nombre=n, icono=ic, descripcion=d, orden=i))
        lam = Ubicacion(slug="lambayeque", nombre="Lambayeque", tipo="region")
        db.session.add(lam)
        db.session.flush()
        db.session.add(Ubicacion(slug="chiclayo", nombre="Chiclayo", tipo="ciudad", padre_id=lam.id))
        db.session.commit()
    return srv


def ficha_autopilot(app, estado="revision", horas=0, titulo="Asistente administrativo – MPP"):
    with app.app_context():
        a = empleo_valido(titulo=titulo, estado=estado,
                          fecha_publicacion=ahora() + timedelta(hours=horas) if estado == "publicado" else None)
        a.origen, a.clave_externa = "autopilot", "ap-" + str(a.id).zfill(6) + "x" * 10
        db.session.commit()
        return a.clave_externa


def test_sincronizacion_guarda_en_revision_por_defecto(app, servidor):
    clave = ficha_autopilot(app, estado="publicado", horas=6)
    with app.app_context():
        r = enviar_pendientes("https://servidor.test", transporte=httpx.WSGITransport(app=servidor), secreto=SECRETO)
        assert r["enviadas"] == 1 and r["resultados"][0]["estado"] == "revision"   # el servidor está en modo A
        assert "política del servidor" in r["resultados"][0]["motivo"]
        assert Articulo.query.filter_by(clave_externa=clave).one().sincronizado_en is not None
        assert enviar_pendientes("https://servidor.test", transporte=httpx.WSGITransport(app=servidor),
                                 secreto=SECRETO)["enviadas"] == 0                  # idempotente
    with servidor.app_context():
        a = Articulo.query.filter_by(clave_externa=clave).one()
        assert a.estado == "revision" and a.institucion.verificada is False
        assert a.detalle_empleo.cargo == "Asistente administrativo"
        assert [e.tipo for e in a.enlaces] == ["postular", "bases"]


def test_servidor_publica_programada_si_su_politica_lo_permite(app, servidor):
    with servidor.test_request_context():
        ajustes.guardar({"autopilot_modo": "B", "autopilot_tipos_auto": "empleo",
                         "autopilot_politica": json.dumps({k: "x" for k, _ in calidad.REQUISITOS_POLITICA})})
    clave = ficha_autopilot(app, estado="publicado", horas=6)
    with app.app_context():
        r = enviar_pendientes("https://servidor.test", transporte=httpx.WSGITransport(app=servidor), secreto=SECRETO)
        assert r["resultados"][0]["estado"] == "publicado"
    with servidor.app_context():
        a = Articulo.query.filter_by(clave_externa=clave).one()
        assert a.programada and a.fecha_publicacion > ahora() + timedelta(hours=5)
        slug = a.slug
    c = servidor.test_client()
    assert c.get(f"/empleos/{slug}").status_code == 404           # aún no es su hora
    with servidor.app_context():
        Articulo.query.filter_by(clave_externa=clave).one().fecha_publicacion = ahora() - timedelta(minutes=1)
        db.session.commit()
    assert c.get(f"/empleos/{slug}").status_code == 200           # aparece sin la laptop


def test_reenvio_de_ficha_ya_publicada_es_propuesta(app, servidor):
    with servidor.test_request_context():
        ajustes.guardar({"autopilot_modo": "B", "autopilot_tipos_auto": "empleo",
                         "autopilot_politica": json.dumps({k: "x" for k, _ in calidad.REQUISITOS_POLITICA})})
    clave = ficha_autopilot(app, estado="publicado")
    t = httpx.WSGITransport(app=servidor)
    with app.app_context():
        enviar_pendientes("https://servidor.test", transporte=t, secreto=SECRETO)
        a = Articulo.query.filter_by(clave_externa=clave).one()
        a.titulo, a.actualizado = "Título cambiado en la laptop", ahora() + timedelta(seconds=5)
        db.session.commit()
        r = enviar_pendientes("https://servidor.test", transporte=t, secreto=SECRETO)
        assert r["resultados"][0]["estado"] == "propuesta"
    with servidor.app_context():
        assert Articulo.query.filter_by(clave_externa=clave).one().titulo != "Título cambiado en la laptop"


def test_firma_invalida_o_vieja_rechazada(servidor):
    c = servidor.test_client()
    cuerpo = json.dumps({"publicaciones": []}).encode()
    marca = str(int(time.time()))
    assert c.post("/api/autopilot/recibir", data=cuerpo, headers={"X-Autopilot-Fecha": marca,
                                                                   "X-Autopilot-Firma": "0" * 64}).status_code == 403
    vieja = str(int(time.time()) - 3600)
    assert c.post("/api/autopilot/recibir", data=cuerpo, headers={
        "X-Autopilot-Fecha": vieja, "X-Autopilot-Firma": firmar(cuerpo, vieja, SECRETO)}).status_code == 403
    assert c.post("/api/autopilot/recibir", data=cuerpo, headers={
        "X-Autopilot-Fecha": marca, "X-Autopilot-Firma": firmar(cuerpo, marca, SECRETO)}).status_code == 200


def test_endpoint_desactivado_sin_token(app, client, monkeypatch):
    monkeypatch.delenv("AUTOPILOT_TOKEN", raising=False)
    assert client.post("/api/autopilot/recibir", data=b"{}").status_code == 404


def test_servidor_sanitiza_lo_recibido(app, servidor):
    with servidor.app_context():
        cuerpo = json.dumps({"publicaciones": [{
            "clave": "ap-maliciosa000000000000", "tipo": "empleo", "titulo": "Empleo",
            "contenido": "<p>ok</p><script>alert(1)</script>", "estado": "publicado",
            "enlaces": [["postular", None, "javascript:alert(1)"], ["bases", None, "https://www.gob.pe/b.pdf"]]}]}).encode()
    marca = str(int(time.time()))
    r = servidor.test_client().post("/api/autopilot/recibir", data=cuerpo, headers={
        "X-Autopilot-Fecha": marca, "X-Autopilot-Firma": firmar(cuerpo, marca, SECRETO)})
    assert r.get_json()["resultados"][0]["estado"] == "revision"
    with servidor.app_context():
        a = Articulo.query.filter_by(clave_externa="ap-maliciosa000000000000").one()
        assert "<script" not in a.contenido and [e.url for e in a.enlaces] == ["https://www.gob.pe/b.pdf"]

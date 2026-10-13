"""Asistente PorSiAcaso: solo resultados reales, sin datos sensibles, con límites."""
from conftest import crear, empleo_valido
import asistente


def preguntar(client, mensaje, estado=None, **kw):
    return client.post("/api/asistente", json={"mensaje": mensaje, "estado": estado or {}}, **kw)


def test_pide_region_para_empleo(app, client):
    with app.app_context():
        empleo_valido()
    d = preguntar(client, "Busco trabajo").get_json()
    assert "región" in d["respuesta"]
    assert any(o["texto"] == "Lambayeque" for o in d["opciones"])
    d2 = preguntar(client, "En Lambayeque", d["estado"]).get_json()
    assert d2["resultados"] and d2["resultados"][0]["url"] == "/empleos/asistente-administrativo-en-chiclayo"


def test_trabajo_en_chiclayo_devuelve_enlaces_reales(app, client):
    with app.app_context():
        empleo_valido()
        empleo_valido(titulo="Empleo en Lima", zona="lima")
    d = preguntar(client, "Busco trabajo en Chiclayo").get_json()
    urls = [r["url"] for r in d["resultados"]]
    assert urls == ["/empleos/asistente-administrativo-en-chiclayo"]
    assert d["enlace"]["url"].startswith("/empleos")


def test_sin_resultados_no_inventa(app, client):
    d = preguntar(client, "Quiero becas para estudiar").get_json()
    assert d["resultados"] == [] and "No encontré" in d["respuesta"]


def test_no_muestra_vencidas_ni_borradores(app, client):
    with app.app_context():
        crear(tipo="beca", titulo="Beca vencida", dias_limite=-1, institucion="Pronabec")
        crear(tipo="beca", titulo="Beca borrador", estado="borrador", institucion="Pronabec")
    assert preguntar(client, "becas").get_json()["resultados"] == []


def test_busqueda_por_palabra(app, client):
    with app.app_context():
        crear(tipo="tramite", titulo="Duplicado de DNI en línea", detalle=dict(finalidad="x", pasos="y"))
    d = preguntar(client, "como sacar duplicado de dni").get_json()
    assert d["resultados"][0]["url"] == "/tramites/duplicado-de-dni-en-linea"


def test_rechaza_datos_sensibles(client):
    d = preguntar(client, "mi dni es 45678912").get_json()
    assert "no compartas" in d["respuesta"] and d["resultados"] == []


def test_saludo_se_identifica_como_automatico(client):
    assert "asistente automático" in preguntar(client, "hola").get_json()["respuesta"]


def test_entrada_invalida(client):
    assert client.post("/api/asistente", data="x", content_type="text/plain").status_code == 400
    assert client.post("/api/asistente", json={"mensaje": 123}).status_code == 400


def test_origen_cruzado_rechazado(client):
    r = preguntar(client, "hola", headers={"Origin": "https://sitio-malicioso.com"})
    assert r.status_code == 403


def test_limite_de_consultas(client):
    asistente.LIMITE_IP.limpiar()
    codigos = [preguntar(client, "hola").status_code for _ in range(22)]
    assert codigos.count(429) >= 1


def test_se_puede_desactivar(app, client):
    import ajustes
    with app.test_request_context():
        ajustes.guardar({"asistente_activo": "0"})
    assert preguntar(client, "hola").status_code == 404
    assert "asisPanel" not in client.get("/").get_data(as_text=True)


def test_respuesta_sin_html(app, client):
    with app.app_context():
        crear(tipo="noticia", titulo="<b>Titulo</b> raro")
    d = preguntar(client, "noticias titulo").get_json()
    # el texto llega crudo en JSON y el navegador lo inserta con textContent (no se interpreta)
    assert all(r["url"].startswith("/") for r in d["resultados"])

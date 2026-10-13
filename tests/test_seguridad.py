"""CSRF, sanitización, cabeceras, publicidad y configuración segura."""
import os

import pytest

from conftest import crear, token, entrar
from utils import limpiar_html, url_valida, borrar_archivo


def test_csrf_obligatorio_en_formularios(client, admin_client):
    r = admin_client.post("/admin/nueva/noticia", data={"titulo": "x", "categoria_id": "1"})
    assert r.status_code == 400
    r = admin_client.post("/admin/logout")
    assert r.status_code == 400
    r = admin_client.post("/admin/login", data={"_csrf": "falso", "email": "a", "password": "b"})
    assert r.status_code == 400


def test_sanitizacion_html():
    sucio = ('<p onclick="x()">Hola<script>alert(1)</script></p><img src=x onerror=alert(1)>'
             '<a href="javascript:alert(1)">mal</a><a href="https://gob.pe">bien</a>'
             '<iframe src="https://evil"></iframe><p><br></p>')
    limpio = limpiar_html(sucio)
    for prohibido in ("<script", "onclick", "onerror", "<img", "javascript:", "<iframe"):
        assert prohibido not in limpio
    assert 'href="https://gob.pe"' in limpio and 'rel="noopener noreferrer nofollow"' in limpio
    assert not limpio.endswith("<p><br></p>")


def test_contenido_publicado_se_guarda_sanitizado(app, admin_client):
    datos = {"_csrf": token(admin_client, "/admin/nueva/noticia"), "titulo": "XSS",
             "categoria_id": "7", "contenido": "<p>ok</p><script>alert(1)</script>",
             "resumen": "<b>resumen</b>", "accion": "borrador"}
    admin_client.post("/admin/nueva/noticia", data=datos)
    from models import Articulo
    with app.app_context():
        a = Articulo.query.one()
        assert "<script" not in a.contenido
    # el resumen se escapa al mostrarse (Jinja autoescape)
    html = admin_client.get(f"/admin/publicacion/{a.id}/vista").get_data(as_text=True)
    assert "&lt;b&gt;resumen&lt;/b&gt;" in html


@pytest.mark.parametrize("url,ok", [
    ("https://www.gob.pe/x", True), ("http://servir.gob.pe", True), ("javascript:alert(1)", False),
    ("data:text/html,x", False), ("https://localhost", False), ("https://a b.pe", False),
    ("ftp://x.pe", False), ("", False), ("https://" + "a" * 600 + ".pe", False)])
def test_url_valida(url, ok):
    assert url_valida(url) is ok


def test_borrar_archivo_no_sale_de_la_carpeta(tmp_path):
    fuera = tmp_path / "secreto.txt"
    fuera.write_text("x")
    carpeta = tmp_path / "uploads"
    carpeta.mkdir()
    borrar_archivo(str(carpeta), "../secreto.txt")
    assert fuera.exists()


def test_cabeceras_de_seguridad(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "no-store" in client.get("/admin/login").headers.get("Cache-Control", "")


def test_produccion_exige_secret_key(monkeypatch):
    from app import crear_app
    monkeypatch.setenv("PRODUCCION", "1")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        crear_app()


def test_errores_sin_detalles_internos(client):
    r = client.get("/no-existe-esta-pagina")
    assert r.status_code == 404 and "Traceback" not in r.get_data(as_text=True)


# ---------- Publicidad ----------
def _guardar_ajustes(app, **valores):
    import ajustes
    with app.test_request_context():
        ajustes.guardar(valores)


def test_publicidad_desactivada_por_defecto(app, client):
    with app.app_context():
        crear()
    html = client.get("/articulo/publicacion-de-prueba").get_data(as_text=True)
    assert "adsbygoogle" not in html and "publicidad-maqueta" not in html


def test_maqueta_solo_para_administradores(app, client):
    with app.app_context():
        crear()
    _guardar_ajustes(app, anuncios_modo="maqueta")
    assert "publicidad-maqueta" not in client.get("/articulo/publicacion-de-prueba").get_data(as_text=True)
    entrar(client)
    html = client.get("/articulo/publicacion-de-prueba").get_data(as_text=True)
    assert "publicidad-maqueta" in html and "adsbygoogle" not in html


def test_adsense_requiere_id_valido(app, client):
    with app.app_context():
        crear()
    _guardar_ajustes(app, anuncios_modo="adsense", adsense_cliente="ca-pub-falso")
    assert "adsbygoogle" not in client.get("/articulo/publicacion-de-prueba").get_data(as_text=True)
    _guardar_ajustes(app, adsense_cliente="ca-pub-1234567890123456", adsense_slot_articulo="1234567890")
    html = client.get("/articulo/publicacion-de-prueba").get_data(as_text=True)
    assert "pagead2.googlesyndication.com" in html
    assert 'data-ad-slot="1234567890"' in html
    assert '<meta name="google-adsense-account" content="ca-pub-1234567890123456">' in html


def test_ads_txt_configurable(app, client):
    assert client.get("/ads.txt").status_code == 404
    _guardar_ajustes(app, ads_txt="google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0")
    r = client.get("/ads.txt")
    assert r.status_code == 200 and r.mimetype == "text/plain" and "pub-1234567890123456" in r.get_data(as_text=True)


def test_sin_enlaces_falsos_de_redes(client):
    html = client.get("/").get_data(as_text=True)
    assert 'href="#"' not in html

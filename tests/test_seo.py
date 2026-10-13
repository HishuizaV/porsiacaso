"""Metadatos, sitemap, robots y datos estructurados."""
import json
import re

from conftest import crear, empleo_valido
from extensions import db
from models import Articulo


def jsonlds(html):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def tipos_ld(html):
    return [d.get("@type") for d in jsonlds(html)]


def test_metadatos_basicos(app, client):
    with app.app_context():
        crear(titulo="Noticia con metadatos", resumen="Resumen que sirve como descripción.")
    html = client.get("/articulo/noticia-con-metadatos").get_data(as_text=True)
    assert "<title>Noticia con metadatos | Por Si Acaso</title>" in html
    assert '<meta name="description" content="Resumen que sirve como descripción.">' in html
    assert '<link rel="canonical" href="https://porsiacaso.test/articulo/noticia-con-metadatos">' in html
    assert 'property="og:type" content="article"' in html
    assert 'og-portada.jpg' in html  # imagen social por defecto cuando no hay foto


def test_jsonld_por_tipo(app, client):
    with app.app_context():
        empleo_valido()
        crear(tipo="noticia", titulo="Nota")
        crear(tipo="convocatoria", titulo="Convocatoria CAS con 30 plazas", institucion="Gobierno Regional",
              detalle=dict(cargo="Varios"), enlaces=[("convocatoria", "https://x.gob.pe")])
        crear(tipo="beca", titulo="Beca X", institucion="Pronabec", detalle=dict(publico="Jóvenes"))
    inicio = client.get("/").get_data(as_text=True)
    assert set(tipos_ld(inicio)) == {"WebSite", "Organization"}
    assert "NewsArticle" in tipos_ld(client.get("/articulo/nota").get_data(as_text=True))
    assert "JobPosting" in tipos_ld(client.get("/empleos/asistente-administrativo-en-chiclayo").get_data(as_text=True))
    conv = tipos_ld(client.get("/convocatorias/convocatoria-cas-con-30-plazas").get_data(as_text=True))
    assert "JobPosting" not in conv and "BreadcrumbList" in conv   # varias plazas: no es una vacante
    beca = tipos_ld(client.get("/becas/beca-x").get_data(as_text=True))
    assert beca == ["BreadcrumbList"]   # sin marcado que Google no admite
    assert "JobPosting" not in client.get("/empleos").get_data(as_text=True)  # nunca en listados


def test_jobposting_contenido_correcto(app, client):
    with app.app_context():
        a = empleo_valido()
        limite = a.fecha_limite.isoformat()
    datos = [d for d in jsonlds(client.get("/empleos/asistente-administrativo-en-chiclayo").get_data(as_text=True))
             if d["@type"] == "JobPosting"][0]
    assert datos["title"] == "Asistente administrativo"
    assert datos["hiringOrganization"]["name"] == "Municipalidad de Chiclayo"
    assert datos["hiringOrganization"]["sameAs"] == "https://www.entidad.gob.pe"
    assert datos["jobLocation"]["address"] == {"@type": "PostalAddress", "addressCountry": "PE",
                                               "addressRegion": "Lambayeque", "addressLocality": "Chiclayo"}
    assert datos["validThrough"] == limite + "T23:59:59-05:00"
    assert datos["baseSalary"]["currency"] == "PEN" and datos["baseSalary"]["value"]["value"] == 2500.0
    assert datos["employmentType"] == "FULL_TIME"
    assert datos["totalJobOpenings"] == 2
    assert "Registrar documentos" in datos["description"]
    assert datos["directApply"] is False


def test_jobposting_sin_datos_inventados(app, client):
    with app.app_context():
        empleo_valido(titulo="Sin sueldo", detalle=dict(cargo="Auxiliar", modalidad="remoto"), zona=None,
                      dias_limite=None)
    datos = [d for d in jsonlds(client.get("/empleos/sin-sueldo").get_data(as_text=True))
             if d["@type"] == "JobPosting"][0]
    assert "baseSalary" not in datos and "validThrough" not in datos and "employmentType" not in datos
    assert datos["jobLocationType"] == "TELECOMMUTE" and "jobLocation" not in datos


def test_jobposting_se_retira_si_no_cumple(app, client):
    with app.app_context():
        empleo_valido(titulo="Vencido", dias_limite=-1)
        empleo_valido(titulo="Cerrado", vigencia="cerrada")
        empleo_valido(titulo="No verificado", verificado=False)
        empleo_valido(titulo="Por confirmar", vigencia="por_confirmar")
        empleo_valido(titulo="Sin institucion", institucion=None)
        empleo_valido(titulo="Sin lugar", zona=None)
        empleo_valido(titulo="Descripcion corta", contenido="<p>Corto</p>",
                      detalle=dict(cargo="X", modalidad="presencial"))
    for slug in ("vencido", "cerrado", "no-verificado", "por-confirmar", "sin-institucion",
                 "sin-lugar", "descripcion-corta"):
        assert "JobPosting" not in tipos_ld(client.get(f"/empleos/{slug}").get_data(as_text=True)), slug


def test_breadcrumbs(app, client):
    with app.app_context():
        empleo_valido()
    migas = [d for d in jsonlds(client.get("/empleos/asistente-administrativo-en-chiclayo").get_data(as_text=True))
             if d["@type"] == "BreadcrumbList"][0]
    nombres = [i["name"] for i in migas["itemListElement"]]
    assert nombres == ["Inicio", "Empleos", "Asistente administrativo en Chiclayo"]
    assert "item" not in migas["itemListElement"][-1]


def test_sitemap(app, client):
    with app.app_context():
        empleo_valido()
        crear(titulo="Borrador", estado="borrador")
        empleo_valido(titulo="Archivado", estado="archivado")
    xml = client.get("/sitemap.xml").get_data(as_text=True)
    assert "https://porsiacaso.test/empleos/asistente-administrativo-en-chiclayo" in xml
    assert "https://porsiacaso.test/empleos</loc>" in xml
    assert "/empleos/region/lambayeque" in xml
    assert "/contacto" in xml
    assert "borrador" not in xml and "archivado" not in xml
    assert "/becas</loc>" not in xml   # secciones vacías no entran


def test_robots(client):
    txt = client.get("/robots.txt").get_data(as_text=True)
    assert "Disallow: /admin/" in txt and "Disallow: /api/" in txt
    assert "Sitemap: https://porsiacaso.test/sitemap.xml" in txt


def test_404_real(client):
    r = client.get("/esto-no-existe")
    assert r.status_code == 404 and "noindex" in r.get_data(as_text=True)


def test_verificacion_search_console(app, client):
    import ajustes
    with app.test_request_context():
        ajustes.guardar({"google_verificacion": "AbCdEf1234567890"})
    assert '<meta name="google-site-verification" content="AbCdEf1234567890">' in client.get("/").get_data(as_text=True)

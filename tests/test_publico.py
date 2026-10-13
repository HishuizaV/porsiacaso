"""Sitio público: inicio, secciones, filtros, fichas, vencidas, búsqueda, conservación de URLs."""
from datetime import timedelta

from conftest import crear, empleo_valido
from models import ahora


def test_inicio_vacio_no_inventa_contenido(client):
    r = client.get("/")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Estamos preparando las primeras publicaciones" in html
    assert "Cierran esta semana" not in html  # no se muestran bloques vacíos


def test_inicio_con_contenido_y_secciones_reales(app, client):
    with app.app_context():
        empleo_valido()
        crear(tipo="noticia", titulo="Noticia de prueba")
    html = client.get("/").get_data(as_text=True)
    assert "Asistente administrativo en Chiclayo" in html
    assert "Noticia de prueba" in html
    assert 'href="/empleos"' in html and 'href="/becas"' not in html  # solo secciones con contenido


def test_ficha_empleo_muestra_datos_y_botones_reales(app, client):
    with app.app_context():
        empleo_valido()
    r = client.get("/empleos/asistente-administrativo-en-chiclayo")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Municipalidad de Chiclayo" in html
    assert "S/ 2,500" in html
    assert 'href="https://www.entidad.gob.pe/postular"' in html
    assert "Postular en sitio oficial" in html and "Ver bases" in html
    assert 'rel="noopener noreferrer nofollow"' in html
    assert "Registrar documentos" in html


def test_sin_enlaces_no_hay_botones_vacios(app, client):
    with app.app_context():
        crear(tipo="tramite", titulo="Duplicado de DNI", enlaces=[], fuente=None,
              detalle=dict(finalidad="Obtener duplicado", pasos="Ir a RENIEC\nPagar la tasa"))
    html = client.get("/tramites/duplicado-de-dni").get_data(as_text=True)
    assert 'class="boton boton-primario boton-bloque" href=""' not in html
    assert "Ir a la página oficial" not in html
    assert "no publicó un enlace directo" not in html  # trámite sin vigencia no es oportunidad vigente
    assert 'class="pasos"' in html


def test_borrador_y_programada_no_son_publicas(app, client):
    with app.app_context():
        crear(titulo="Borrador oculto", estado="borrador")
        crear(titulo="Programada futura", fecha_publicacion=ahora() + timedelta(days=2))
    assert client.get("/articulo/borrador-oculto").status_code == 404
    assert client.get("/articulo/programada-futura").status_code == 404
    assert "Programada futura" not in client.get("/noticias").get_data(as_text=True)


def test_url_antigua_articulo_redirige_301(app, client):
    with app.app_context():
        empleo_valido()
        crear(tipo="noticia", titulo="Nota antigua")
    r = client.get("/articulo/asistente-administrativo-en-chiclayo")
    assert r.status_code == 301 and r.headers["Location"].endswith("/empleos/asistente-administrativo-en-chiclayo")
    assert client.get("/articulo/nota-antigua").status_code == 200
    # tipo equivocado en la sección también redirige a la URL correcta
    r = client.get("/becas/asistente-administrativo-en-chiclayo")
    assert r.status_code == 301


def test_vencida_muestra_aviso_y_oculta_postular(app, client):
    with app.app_context():
        empleo_valido(titulo="Empleo vencido", dias_limite=-3)
    html = client.get("/empleos/empleo-vencido").get_data(as_text=True)
    assert "Esta convocatoria venció" in html
    assert "Postular en sitio oficial" not in html
    assert "JobPosting" not in html
    # no aparece en vigentes, sí en vencidas
    assert "Empleo vencido" not in client.get("/empleos").get_data(as_text=True)
    assert "Empleo vencido" in client.get("/empleos?vigencia=vencidas").get_data(as_text=True)


def test_archivada_noindex_y_fuera_de_listados(app, client):
    with app.app_context():
        empleo_valido(titulo="Empleo archivado", estado="archivado")
    html = client.get("/empleos/empleo-archivado").get_data(as_text=True)
    assert "noindex" in html and "Publicación archivada" in html
    assert "Empleo archivado" not in client.get("/empleos?vigencia=todas").get_data(as_text=True)


def test_filtros_de_empleo(app, client):
    with app.app_context():
        empleo_valido(titulo="Empleo Chiclayo presencial")
        empleo_valido(titulo="Empleo Lima remoto", zona="lima", institucion="Empresa SAC",
                      detalle=dict(cargo="Analista", modalidad="remoto", sector="privado",
                                   nivel_educativo="titulado"))
    def titulos(url):
        return client.get(url).get_data(as_text=True)
    assert "Empleo Lima remoto" not in titulos("/empleos?region=lambayeque")
    assert "Empleo Chiclayo presencial" in titulos("/empleos?region=lambayeque")  # ciudad dentro de región
    assert "Empleo Chiclayo presencial" not in titulos("/empleos?modalidad=remoto")
    assert "Empleo Lima remoto" in titulos("/empleos?sector=privado")
    assert "Empleo Lima remoto" not in titulos("/empleos?nivel=bachiller")
    assert "Empleo Lima remoto" in titulos("/empleos?institucion=empresa-sac")
    # valores inválidos se ignoran (no error)
    assert client.get("/empleos?modalidad=<script>&orden=x&vigencia=y").status_code == 200
    # página filtrada no indexable; la normal sí
    assert "noindex" in titulos("/empleos?modalidad=remoto")
    assert 'content="index, follow"' in titulos("/empleos")


def test_pagina_regional(app, client):
    with app.app_context():
        empleo_valido()
    r = client.get("/empleos/region/lambayeque")
    assert r.status_code == 200 and "Empleos en Lambayeque" in r.get_data(as_text=True)
    vacia = client.get("/empleos/region/lima").get_data(as_text=True)
    assert "noindex" in vacia  # región sin resultados no se indexa
    assert client.get("/empleos/region/no-existe").status_code == 404


def test_paginacion_real(app, client):
    with app.app_context():
        for i in range(14):
            crear(tipo="noticia", titulo=f"Noticia numero {i}")
    p1 = client.get("/noticias").get_data(as_text=True)
    p2 = client.get("/noticias?page=2").get_data(as_text=True)
    assert p1.count('class="tarjeta"') == 12 and p2.count('class="tarjeta"') == 2
    assert 'rel="next"' in p1
    assert client.get("/noticias?page=9").status_code == 404


def test_buscador_sin_tildes_y_relevancia(app, client):
    with app.app_context():
        crear(tipo="tramite", titulo="Trámite de licencia de conducir", enlaces=[],
              detalle=dict(finalidad="Licencia", pasos="Paso uno"))
        crear(tipo="noticia", titulo="Otra noticia", contenido="<p>Menciona tramite al pasar.</p>")
    html = client.get("/buscar?q=tramite").get_data(as_text=True)
    assert "Trámite de licencia de conducir" in html
    assert html.index("Trámite de licencia") < html.index("Otra noticia")  # título pesa más
    assert "noindex" in html
    assert "No encontramos resultados" in client.get("/buscar?q=zzzzzz").get_data(as_text=True)


def test_curso_beca_bono_fichas_especializadas(app, client):
    with app.app_context():
        crear(tipo="beca", titulo="Beca de prueba", dias_limite=5, vigencia="abierta",
              institucion="Pronabec", detalle=dict(publico="Jóvenes", requisitos="Ser peruano"),
              enlaces=[("postular", "https://www.pronabec.gob.pe")])
        crear(tipo="curso", titulo="Curso gratis", institucion="Ministerio X",
              detalle=dict(costo="gratuito", duracion="20 horas", certificado="gratuito"),
              enlaces=[("inscripcion", "https://www.x.gob.pe/curso")])
        crear(tipo="bono", titulo="Bono pendiente", vigencia="por_confirmar", institucion="MIDIS",
              detalle=dict(poblacion="Hogares vulnerables", monto="S/ 350"))
    beca = client.get("/becas/beca-de-prueba").get_data(as_text=True)
    assert "¿A quién está dirigida?" in beca and "Quedan 5 días" in beca
    curso = client.get("/cursos/curso-gratis").get_data(as_text=True)
    assert "Inscribirme en sitio oficial" in curso and "20 horas" in curso
    bono = client.get("/bonos/bono-pendiente").get_data(as_text=True)
    assert "pendiente de verificación" in bono.lower()


def test_zona_y_categoria(app, client):
    with app.app_context():
        empleo_valido()
    assert client.get("/zona/lambayeque").status_code == 200
    assert "Asistente administrativo" in client.get("/zona/chiclayo").get_data(as_text=True)
    assert client.get("/categoria/empleo").status_code == 200
    assert client.get("/categoria/no-existe").status_code == 404


def test_pagina_oculta_solo_admin(app, client):
    from extensions import db
    from models import Pagina
    with app.app_context():
        db.session.add(Pagina(slug="publicidad", titulo="Publicidad", contenido="<p>x</p>", visible=False))
        db.session.commit()
    assert client.get("/publicidad").status_code == 404
    assert client.get("/contacto").status_code == 200

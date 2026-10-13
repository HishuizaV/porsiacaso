"""Panel: login, permisos, formularios especializados, estados, duplicar, archivar, subidas."""
import io
import json

from PIL import Image

from conftest import crear, empleo_valido, entrar, token, usuario, CLAVE
from extensions import db
from models import Articulo, Institucion, Enlace, Registro


def form_empleo(**cambios):
    datos = {
        "titulo": "Contador junior – Empresa Norte",
        "resumen": "Empresa privada busca contador junior en Chiclayo con experiencia mínima.",
        "institucion": "Empresa Norte SAC", "institucion_sector": "privado",
        "categoria_id": "1", "ubicacion_id": "3",
        "d_cargo": "Contador junior", "d_modalidad": "hibrido", "d_jornada": "completa",
        "d_sueldo_min": "2,800", "d_moneda": "PEN", "d_vacantes": "1", "d_sector": "privado",
        "d_formacion": "Bachiller en Contabilidad\nManejo de Excel",
        "d_funciones": "Registrar operaciones\nPreparar reportes",
        "fecha_limite": "2099-12-31", "vigencia": "abierta", "verificado_hoy": "1",
        "enlace-0-tipo": "postular", "enlace-0-url": "https://empresa-norte.pe/empleos/123",
        "enlace-1-tipo": "otro", "enlace-1-etiqueta": "Ver ficha completa",
        "enlace-1-url": "https://empresa-norte.pe/ficha",
        "contenido": "<p>Buscamos un contador junior para el área de finanzas, encargado del registro "
                     "contable, conciliaciones bancarias y elaboración de reportes mensuales.</p>",
        "fuente_url": "https://empresa-norte.pe/empleos", "fuente_nombre": "Web de Empresa Norte",
        "accion": "publicar",
    }
    datos.update(cambios)
    return datos


def enviar(client, url, datos, **kw):
    datos = dict(datos)
    solo_post = url.endswith(("/accion", "/rol", "/activo"))
    datos["_csrf"] = token(client, "/admin/" if solo_post else url)
    return client.post(url, data=datos, content_type="multipart/form-data", **kw)


# ---------- Login y acceso ----------
def test_login_correcto_e_incorrecto(client):
    r = entrar(client, clave="mala")
    assert "incorrectos" in client.get("/admin/login").get_data(as_text=True) or r.status_code == 200
    r = entrar(client)
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin/")


def test_bloqueo_tras_5_intentos(client):
    for _ in range(5):
        entrar(client, clave="mala")
    entrar(client)   # clave correcta, pero bloqueado
    assert client.get("/admin/").status_code == 302


def test_panel_requiere_sesion(client):
    for url in ("/admin/", "/admin/publicaciones", "/admin/nueva/empleo", "/admin/configuracion"):
        r = client.get(url)
        assert r.status_code == 302 and "/admin/login" in r.headers["Location"]


def test_editor_sin_acceso_a_zonas_de_admin(editor_client):
    for url in ("/admin/configuracion", "/admin/usuarios", "/admin/categorias", "/admin/registros",
                "/admin/paginas"):
        assert editor_client.get(url).status_code == 403


def test_editor_no_edita_publicaciones_ajenas(app, editor_client):
    with app.app_context():
        ajena = crear(titulo="De otro", autor="editor2@prueba.test", estado="borrador")
        propia = crear(titulo="Mía", autor="editor@prueba.test", estado="borrador")
        ids = ajena.id, propia.id
    assert editor_client.get(f"/admin/publicacion/{ids[0]}/editar").status_code == 403
    assert editor_client.get(f"/admin/publicacion/{ids[1]}/editar").status_code == 200
    assert "De otro" not in editor_client.get("/admin/publicaciones").get_data(as_text=True)


# ---------- Formularios ----------
def test_selector_de_tipos(admin_client):
    html = admin_client.get("/admin/nueva").get_data(as_text=True)
    for texto in ("Publicar empleo", "Publicar beca", "Publicar curso", "Publicar bono o beneficio",
                  "Publicar trámite", "Publicar guía práctica", "Publicar noticia"):
        assert texto in html


def test_formularios_especializados(admin_client):
    assert "Nombre del puesto" in admin_client.get("/admin/nueva/empleo").get_data(as_text=True)
    assert "¿A quién está dirigida?" in admin_client.get("/admin/nueva/beca").get_data(as_text=True)
    assert "¿Otorga certificado?" in admin_client.get("/admin/nueva/curso").get_data(as_text=True)
    assert "¿Quiénes lo reciben?" in admin_client.get("/admin/nueva/bono").get_data(as_text=True)
    assert "Paso a paso" in admin_client.get("/admin/nueva/tramite").get_data(as_text=True)
    noticia = admin_client.get("/admin/nueva/noticia").get_data(as_text=True)
    assert "Nombre del puesto" not in noticia and "Datos clave" in noticia
    assert admin_client.get("/admin/nueva/inventado").status_code == 404


def test_editor_publica_empleo_sin_html(app, editor_client):
    r = enviar(editor_client, "/admin/nueva/empleo", form_empleo())
    assert r.status_code == 302
    with app.app_context():
        a = Articulo.query.filter_by(tipo="empleo").one()
        assert a.estado == "publicado" and a.autor.email == "editor@prueba.test"
        assert a.detalle_empleo.cargo == "Contador junior"
        assert float(a.detalle_empleo.sueldo_min) == 2800.0
        assert a.institucion.nombre == "Empresa Norte SAC" and a.institucion.sector == "privado"
        assert [e.tipo for e in a.enlaces] == ["postular", "otro"]
        assert a.verificado_en is not None and "contador" in a.busqueda
        slug = a.slug
    html = editor_client.get(f"/empleos/{slug}").get_data(as_text=True)
    assert 'href="https://empresa-norte.pe/empleos/123"' in html
    assert "Ver ficha completa" in html
    assert '"@type": "JobPosting"' in html


def test_borrador_incompleto_se_guarda_pero_no_se_publica(app, admin_client):
    r = enviar(admin_client, "/admin/nueva/empleo",
               {"titulo": "Solo título", "categoria_id": "1", "accion": "borrador"})
    assert r.status_code == 302
    with app.app_context():
        a = Articulo.query.filter_by(titulo="Solo título").one()
        assert a.estado == "borrador"
        aid = a.id
    r = enviar(admin_client, f"/admin/publicacion/{aid}/editar",
               {"titulo": "Solo título", "categoria_id": "1", "accion": "publicar"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Completa «Nombre del puesto»" in html
    assert "fuente oficial" in html
    with app.app_context():
        assert db.session.get(Articulo, aid).estado == "borrador"


def test_curso_gratuito_exige_fuente(app, admin_client):
    datos = {"titulo": "Curso de Excel", "resumen": "Curso básico de Excel para principiantes.",
             "categoria_id": "2", "institucion": "Instituto X", "d_costo": "gratuito",
             "enlace-0-tipo": "inscripcion", "enlace-0-url": "https://x.edu.pe/inscripcion",
             "accion": "publicar"}
    html = enviar(admin_client, "/admin/nueva/curso", datos).get_data(as_text=True)
    assert "Para marcar un curso como gratuito" in html


def test_validacion_de_urls_y_numeros(app, admin_client):
    datos = form_empleo(**{"enlace-0-url": "javascript:alert(1)", "d_sueldo_min": "abc",
                           "fuente_url": "ftp://x.com"})
    html = enviar(admin_client, "/admin/nueva/empleo", datos).get_data(as_text=True)
    assert "no es una dirección web válida" in html
    assert "«Sueldo» no tiene un valor válido" in html
    assert "El enlace de la fuente debe ser una dirección web válida" in html
    with app.app_context():
        assert Articulo.query.count() == 0


def test_sueldo_maximo_menor_rechazado(admin_client):
    html = enviar(admin_client, "/admin/nueva/empleo",
                  form_empleo(d_sueldo_max="1000")).get_data(as_text=True)
    assert "no puede ser menor" in html


def test_edicion_conserva_slug_e_institucion_existente(app, admin_client):
    enviar(admin_client, "/admin/nueva/empleo", form_empleo())
    with app.app_context():
        a = Articulo.query.one()
        aid, slug = a.id, a.slug
    enviar(admin_client, f"/admin/publicacion/{aid}/editar",
           form_empleo(titulo="Título cambiado por completo", institucion="empresa norte sac"))
    with app.app_context():
        a = db.session.get(Articulo, aid)
        assert a.slug == slug and a.titulo == "Título cambiado por completo"
        assert Institucion.query.count() == 1


def test_programar_publicacion(app, admin_client):
    enviar(admin_client, "/admin/nueva/noticia",
           {"titulo": "Noticia programada", "resumen": "Resumen suficiente de la noticia programada.",
            "categoria_id": "7", "contenido": "<p>Texto de la noticia.</p>",
            "programar": "2099-01-01T08:00", "accion": "publicar"})
    with app.app_context():
        a = Articulo.query.one()
        assert a.estado == "publicado" and a.programada
    assert admin_client.get("/articulo/noticia-programada").status_code == 404


def test_acciones_archivar_despublicar_duplicar_eliminar(app, admin_client):
    with app.app_context():
        aid = empleo_valido().id
    def accion(nombre, id_=None):
        return enviar(admin_client, f"/admin/publicacion/{id_ or aid}/accion", {"accion": nombre})
    accion("archivar")
    with app.app_context():
        assert db.session.get(Articulo, aid).estado == "archivado"
    accion("despublicar")
    with app.app_context():
        assert db.session.get(Articulo, aid).estado == "borrador"
    r = accion("duplicar")
    with app.app_context():
        copia = Articulo.query.filter(Articulo.id != aid).one()
        assert copia.estado == "borrador" and copia.detalle_empleo.cargo == "Asistente administrativo"
        assert len(copia.enlaces) == 2 and copia.slug != db.session.get(Articulo, aid).slug
        cid = copia.id
    accion("publicar")
    with app.app_context():
        assert db.session.get(Articulo, aid).estado == "publicado"
    accion("eliminar", cid)
    with app.app_context():
        assert db.session.get(Articulo, cid) is None
        assert Enlace.query.filter_by(articulo_id=cid).count() == 0
        assert Registro.query.filter_by(accion="publicacion_eliminada").count() == 1


def test_editor_no_elimina_publicada_ni_destaca(app, editor_client):
    with app.app_context():
        aid = crear(titulo="Publicada del editor", autor="editor@prueba.test").id
    enviar(editor_client, f"/admin/publicacion/{aid}/accion", {"accion": "eliminar"})
    with app.app_context():
        assert db.session.get(Articulo, aid) is not None
    enviar(editor_client, f"/admin/publicacion/{aid}/editar",
           {"titulo": "Publicada del editor", "resumen": "Resumen suficiente para publicar esto.",
            "categoria_id": "7", "contenido": "<p>Texto</p>", "destacado": "1", "accion": "publicar"})
    with app.app_context():
        assert db.session.get(Articulo, aid).destacado is False


def test_vista_previa_borrador(app, admin_client, client):
    with app.app_context():
        aid = empleo_valido(estado="borrador").id
    html = admin_client.get(f"/admin/publicacion/{aid}/vista").get_data(as_text=True)
    assert "Vista previa" in html and "noindex" in html
    assert "JobPosting" not in html.split("Para el equipo")[0]  # nunca se marca una vista previa


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (800, 500), (200, 30, 30)).save(buf, "PNG")
    buf.seek(0)
    return buf


def test_subida_de_imagen_valida_e_invalida(app, admin_client):
    datos = {"titulo": "Con imagen", "categoria_id": "7", "accion": "borrador",
             "imagen_alt": "Descripción", "imagen": (_png(), "foto.png")}
    assert enviar(admin_client, "/admin/nueva/noticia", datos).status_code == 302
    with app.app_context():
        a = Articulo.query.one()
        assert a.imagen.endswith(".jpg") and a.imagen_ancho == 800 and a.imagen_alto == 500
    falso = {"titulo": "Imagen falsa", "categoria_id": "7", "accion": "borrador",
             "imagen": (io.BytesIO(b"<?php echo 1; ?>"), "foto.png")}
    html = enviar(admin_client, "/admin/nueva/noticia", falso).get_data(as_text=True)
    assert "La imagen no es válida" in html


def test_subida_pdf_valido_e_invalido(app, admin_client):
    datos = form_empleo(**{"enlace-2-tipo": "bases",
                           "enlace-2-pdf": (io.BytesIO(b"%PDF-1.4\n%prueba\n"), "bases.pdf")})
    assert enviar(admin_client, "/admin/nueva/empleo", datos).status_code == 302
    with app.app_context():
        e = Enlace.query.filter_by(tipo="bases").one()
        assert e.archivo.endswith(".pdf") and e.url is None
    malo = form_empleo(titulo="Otro empleo", **{"enlace-2-tipo": "bases",
                                               "enlace-2-pdf": (io.BytesIO(b"MZ ejecutable"), "x.pdf")})
    assert "no es un PDF válido" in enviar(admin_client, "/admin/nueva/empleo", malo).get_data(as_text=True)


def test_faq_y_aviso(app, admin_client):
    enviar(admin_client, "/admin/nueva/guia",
           {"titulo": "Guía para postular al Estado", "resumen": "Pasos y consejos para postular en el Estado.",
            "categoria_id": "4", "contenido": "<p>Contenido de la guía.</p>", "aviso": "Revisa las bases.",
            "faq-0-p": "¿Cuesta postular?", "faq-0-r": "No, es gratuito.", "accion": "publicar"})
    with app.app_context():
        a = Articulo.query.one()
        assert json.loads(a.faq_json) == [{"p": "¿Cuesta postular?", "r": "No, es gratuito."}]
    html = admin_client.get("/guias/guia-para-postular-al-estado").get_data(as_text=True)
    assert "¿Cuesta postular?" in html and "Revisa las bases." in html


def test_panel_resumen_con_cifras_reales(app, admin_client):
    with app.app_context():
        empleo_valido()
        crear(titulo="Borrador", estado="borrador")
    html = admin_client.get("/admin/").get_data(as_text=True)
    assert "<strong>1</strong><span>Publicadas</span>" in html
    assert "<strong>1</strong><span>Borradores</span>" in html


def test_listado_admin_filtra(app, admin_client):
    with app.app_context():
        empleo_valido()
        crear(titulo="Nota cualquiera")
    html = admin_client.get("/admin/publicaciones?tipo=empleo").get_data(as_text=True)
    assert "Asistente administrativo" in html and "Nota cualquiera" not in html
    html = admin_client.get("/admin/publicaciones?q=chiclayo").get_data(as_text=True)
    assert "Asistente administrativo" in html


def test_paginas_institucionales_editables(app, admin_client):
    r = enviar(admin_client, "/admin/paginas/nueva",
               {"titulo": "Empleos", "contenido": "<p>Intento de chocar con una sección</p>", "visible": "1"})
    assert r.status_code == 302
    from models import Pagina
    with app.app_context():
        p = Pagina.query.filter_by(titulo="Empleos").one()
        assert p.slug != "empleos"   # dirección reservada
    html = enviar(admin_client, "/admin/paginas/nueva",
                  {"titulo": "Correcciones", "contenido": "<p>Correo: [PENDIENTE]</p>", "visible": "1"}
                  ).get_data(as_text=True)
    assert "Complétalos antes de hacerla visible" in html


def test_configuracion_valida_ids(app, admin_client):
    html = enviar(admin_client, "/admin/configuracion",
                  {"anuncios_modo": "adsense", "adsense_cliente": "ca-pub-123"}).get_data(as_text=True)
    assert "16 números" in html
    r = enviar(admin_client, "/admin/configuracion",
               {"anuncios_modo": "maqueta", "contacto_email": "hola@porsiacaso.pe",
                "asistente_activo": "1"})
    assert r.status_code == 302


def test_cambio_de_rol_y_desactivar(app, admin_client):
    with app.app_context():
        uid = usuario("editor@prueba.test").id
    enviar(admin_client, f"/admin/usuarios/{uid}/rol", {"rol": "admin"})
    with app.app_context():
        assert usuario("editor@prueba.test").rol == "admin"
    enviar(admin_client, f"/admin/usuarios/{uid}/activo", {})
    with app.app_context():
        assert usuario("editor@prueba.test").activo is False


def test_editor_desactivado_no_entra(app, client):
    with app.app_context():
        usuario("editor@prueba.test").activo = False
        db.session.commit()
    entrar(client, "editor@prueba.test", CLAVE)
    assert client.get("/admin/").status_code == 302

"""Fixtures: cada prueba usa una base SQLite temporal y una carpeta de subidas temporal.
Nunca se toca porsiacaso.db ni static/uploads."""
import os
import re
import sys
from datetime import timedelta

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import crear_app  # noqa: E402
from extensions import db  # noqa: E402
from models import (Usuario, Categoria, Ubicacion, Articulo, Institucion, Enlace, Pagina,  # noqa: E402
                    DetalleEmpleo, ahora, hoy)
from datos_iniciales import CATEGORIAS_INICIALES  # noqa: E402
from consultas import actualizar_busqueda  # noqa: E402
from utils import slugify  # noqa: E402
import asistente  # noqa: E402

CLAVE = "clave-de-prueba-123"


@pytest.fixture
def app(tmp_path):
    app = crear_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///" + str(tmp_path / "prueba.db"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "SITE_URL": "https://porsiacaso.test",
        "SECRET_KEY": "pruebas",
    })
    with app.app_context():
        db.create_all()
        for i, (slug, corto, nombre, icono, desc) in enumerate(CATEGORIAS_INICIALES):
            db.session.add(Categoria(slug=slug, corto=corto, nombre=nombre, icono=icono,
                                     descripcion=desc, orden=i))
        lam = Ubicacion(slug="lambayeque", nombre="Lambayeque", tipo="region")
        lima = Ubicacion(slug="lima", nombre="Lima", tipo="region")
        db.session.add_all([lam, lima])
        db.session.flush()
        db.session.add(Ubicacion(slug="chiclayo", nombre="Chiclayo", tipo="ciudad", padre_id=lam.id))
        for email, rol in (("admin@prueba.test", "admin"), ("editor@prueba.test", "editor"),
                           ("editor2@prueba.test", "editor")):
            u = Usuario(nombre=email.split("@")[0].capitalize(), email=email, rol=rol)
            u.set_password(CLAVE)
            db.session.add(u)
        db.session.add(Pagina(slug="contacto", titulo="Contacto", contenido="<p>Escríbenos.</p>"))
        db.session.commit()
    asistente.LIMITE_IP.limpiar()
    asistente.LIMITE_GLOBAL.limpiar()
    import admin as modulo_admin
    modulo_admin.INTENTOS.clear()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, url="/admin/login"):
    r = client.get(url)
    m = re.search(r'name="_csrf" value="([^"]+)"', r.get_data(as_text=True))
    assert m, f"sin token CSRF en {url}"
    return m.group(1)


def entrar(client, email="admin@prueba.test", clave=CLAVE):
    t = token(client)
    return client.post("/admin/login", data={"_csrf": t, "email": email, "password": clave})


@pytest.fixture
def admin_client(client):
    entrar(client)
    return client


@pytest.fixture
def editor_client(client):
    entrar(client, "editor@prueba.test")
    return client


def usuario(email):
    return Usuario.query.filter_by(email=email).first()


def crear(tipo="noticia", titulo="Publicación de prueba", estado="publicado", autor="admin@prueba.test",
          dias_limite=None, vigencia=None, zona=None, institucion=None, detalle=None, enlaces=(),
          contenido="<p>Contenido de prueba con información suficiente para el lector.</p>",
          verificado=True, fuente="https://www.gob.pe/fuente", resumen="Resumen de prueba", **extra):
    """Crea una publicación directamente en la base (para preparar escenarios)."""
    cat = Categoria.query.filter_by(slug="empleo").first()
    a = Articulo(tipo=tipo, titulo=titulo, slug=extra.pop("slug", None) or
                 slugify(titulo),
                 resumen=resumen, contenido=contenido, estado=estado, categoria=cat,
                 autor=usuario(autor), fuente_url=fuente, vigencia=vigencia,
                 fecha_publicacion=extra.pop("fecha_publicacion", ahora() - timedelta(hours=1))
                 if estado in ("publicado", "archivado") else None,
                 verificado_en=hoy() if verificado else None, **extra)
    db.session.add(a)
    if dias_limite is not None:
        a.fecha_limite = hoy() + timedelta(days=dias_limite)
    if zona:
        a.ubicacion = Ubicacion.query.filter_by(slug=zona).first()
    if institucion:
        inst = Institucion.query.filter_by(slug=institucion.lower().replace(" ", "-")).first() or \
            Institucion(slug=institucion.lower().replace(" ", "-"), nombre=institucion,
                        web="https://www.entidad.gob.pe")
        a.institucion = inst
    if detalle is not None:
        d = a.asegurar_detalle()
        for k, v in detalle.items():
            setattr(d, k, v)
    a.enlaces = [Enlace(tipo=t, url=u, orden=i) for i, (t, u) in enumerate(enlaces)]
    db.session.flush()
    actualizar_busqueda(a)
    db.session.commit()
    return a


DESCRIPCION_LARGA = ("<p>La Municipalidad requiere un asistente administrativo para apoyar en la "
                     "gestión documentaria, atención al público y registro de expedientes en el "
                     "área de trámite documentario durante el periodo de contratación.</p>")


def empleo_valido(**extra):
    datos = dict(tipo="empleo", titulo="Asistente administrativo en Chiclayo", zona="chiclayo",
                 institucion="Municipalidad de Chiclayo", dias_limite=10, vigencia="abierta",
                 contenido=DESCRIPCION_LARGA,
                 detalle=dict(cargo="Asistente administrativo", modalidad="presencial",
                              jornada="completa", sector="publico", sueldo_min=2500, moneda="PEN",
                              nivel_educativo="bachiller", funciones="Registrar documentos\nAtender al público",
                              vacantes=2),
                 enlaces=[("postular", "https://www.entidad.gob.pe/postular"),
                          ("bases", "https://www.entidad.gob.pe/bases.pdf")])
    datos.update(extra)
    return crear(**datos)

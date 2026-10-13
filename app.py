import hashlib
import os
import sqlite3

import click
from flask import Flask, render_template, url_for, request
from werkzeug.middleware.proxy_fix import ProxyFix

from extensions import db, login_manager, migrate
from models import Usuario, Categoria, Ubicacion, Pagina, ahora, lineas
from utils import slugify
from datos_iniciales import (CATEGORIAS_INICIALES, PAGINAS_INICIALES, PAGINAS_NUEVAS,
                             REGIONES_INICIALES, CIUDADES_INICIALES)
import seguridad

BASE = os.path.abspath(os.path.dirname(__file__))
CLAVE_EJEMPLO = "cambia-esto-antes-de-publicar"


def crear_app(config=None):
    app = Flask(__name__)
    produccion = os.environ.get("PRODUCCION") == "1"
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", CLAVE_EJEMPLO),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL", "sqlite:///" + os.path.join(BASE, "porsiacaso.db")),
        UPLOAD_FOLDER=os.path.join(BASE, "static", "uploads"),
        MAX_CONTENT_LENGTH=12 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=produccion,
        REMEMBER_COOKIE_SECURE=produccion,
        REMEMBER_COOKIE_HTTPONLY=True,
        SITE_URL=os.environ.get("SITE_URL", "http://127.0.0.1:5000").rstrip("/"),
        PRODUCCION=produccion,
        POR_PAGINA=12,
    )
    if config:
        app.config.update(config)

    if app.config["PRODUCCION"] and app.config["SECRET_KEY"] in (CLAVE_EJEMPLO, "", None):
        raise RuntimeError("Define SECRET_KEY en el entorno antes de iniciar en producción.")
    if os.environ.get("CONFIAR_PROXY") == "1":   # detrás de Nginx / proveedor con proxy
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.session_protection = "strong"

    from admin import admin
    import admin_contenido  # noqa: F401  (registra rutas en el blueprint admin)
    import admin_sitio      # noqa: F401
    from web import web
    from asistente import api
    app.register_blueprint(admin)
    app.register_blueprint(web)
    app.register_blueprint(api)

    registrar_plantillas(app)
    registrar_errores(app)
    registrar_comandos(app)

    @app.before_request
    def _csrf():
        seguridad.verificar_csrf(app)

    @app.after_request
    def cabeceras(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.path.startswith("/admin"):
            resp.headers["Cache-Control"] = "no-store"
        if app.config["PRODUCCION"]:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        return resp

    return app


def registrar_plantillas(app):
    from web import contexto_publico, url_publicacion, url_enlace, url_imagen, url_con

    def abs_url(endpoint, **valores):
        """URL absoluta (para SEO, Open Graph y sitemap)."""
        return app.config["SITE_URL"] + url_for(endpoint, **valores)

    import tipos as T
    opciones = {n: dict(getattr(T, n)) for n in (
        "MODALIDADES", "MODALIDADES_CURSO", "SECTORES", "NIVELES_EDUCATIVOS", "TIPOS_CONVOCATORIA",
        "JORNADAS", "CONTRATOS", "COSTOS", "CERTIFICADOS", "CANALES", "VIGENCIAS", "ESTADOS")}
    app.jinja_env.filters["lineas"] = lineas
    app.jinja_env.filters["dict_sin_page"] = lambda d: {k: v for k, v in d.items() if k != "page"}
    app.jinja_env.globals["TIPOS_ADMIN"] = T.TIPOS
    app.jinja_env.globals.update(OPC=opciones, abs_url=abs_url, csrf_token=seguridad.csrf_token,
                                 url_publicacion=url_publicacion, url_enlace=url_enlace,
                                 url_imagen=url_imagen, url_con=url_con)
    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True
    app.context_processor(contexto_publico)


def registrar_errores(app):
    mensajes = {
        400: ("Solicitud no válida", "El formulario caducó o tiene datos incorrectos. "
                                      "Vuelve atrás, recarga la página e inténtalo de nuevo."),
        403: ("Sin permiso", "No tienes permiso para hacer esto."),
        404: ("Página no encontrada", "Lo que buscas no existe o fue movido."),
        413: ("Archivo demasiado grande", "El archivo supera el tamaño permitido (12 MB en total)."),
        429: ("Demasiadas solicitudes", "Espera un momento antes de volver a intentarlo."),
        500: ("Error del servidor", "Ocurrió un problema inesperado. Inténtalo más tarde."),
    }

    def manejador(codigo):
        def vista(e):
            if codigo == 500:
                db.session.rollback()
            titulo, texto = mensajes[codigo]
            if request.path.startswith("/api/"):
                return {"error": titulo}, codigo
            try:
                return render_template("error.html", titulo=titulo, texto=texto, codigo=codigo), codigo
            except Exception:   # la propia plantilla falló: respuesta mínima, sin detalles internos
                db.session.rollback()
                return f"{codigo} · {titulo}. {texto}", codigo, {"Content-Type": "text/plain; charset=utf-8"}
        return vista

    for codigo in mensajes:
        app.register_error_handler(codigo, manejador(codigo))


def registrar_comandos(app):
    @app.cli.command("iniciar")
    def iniciar():
        """Carga categorías, zonas y páginas iniciales (después de: flask db upgrade)."""
        if Categoria.query.count() == 0:
            for i, (slug, corto, nombre, icono, desc) in enumerate(CATEGORIAS_INICIALES):
                db.session.add(Categoria(slug=slug, corto=corto, nombre=nombre,
                                         icono=icono, descripcion=desc, orden=i))
        if Pagina.query.count() == 0:
            for slug, titulo, contenido in PAGINAS_INICIALES:
                db.session.add(Pagina(slug=slug, titulo=titulo, contenido=contenido.strip()))
        if Ubicacion.query.count() == 0:
            regiones = {}
            for nombre in REGIONES_INICIALES:
                u = Ubicacion(slug=slugify(nombre), nombre=nombre, tipo="region")
                db.session.add(u)
                regiones[nombre] = u
            db.session.flush()
            for ciudad, region in CIUDADES_INICIALES:
                db.session.add(Ubicacion(slug=slugify(ciudad), nombre=ciudad, tipo="ciudad",
                                         padre_id=regiones[region].id))
        db.session.commit()
        click.echo("Datos iniciales listos.")

    @app.cli.command("completar-paginas")
    def completar_paginas():
        """Agrega las páginas institucionales que falten, OCULTAS para que las revises.
        Nunca modifica las páginas existentes."""
        nuevas = 0
        for slug, titulo, contenido in PAGINAS_NUEVAS:
            if not Pagina.query.filter_by(slug=slug).first():
                db.session.add(Pagina(slug=slug, titulo=titulo, contenido=contenido.strip(),
                                      visible=False))
                nuevas += 1
        db.session.commit()
        click.echo(f"{nuevas} página(s) agregada(s) como ocultas. Revísalas en el panel → Páginas.")

    @app.cli.command("crear-admin")
    @click.option("--nombre", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def crear_admin(nombre, email, password):
        """Crea el usuario administrador."""
        if len(password) < 8:
            raise click.ClickException("La contraseña debe tener mínimo 8 caracteres.")
        u = Usuario(nombre=nombre, email=email.strip().lower(), rol="admin")
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.echo("Administrador creado.")

    @app.cli.command("respaldo")
    @click.option("--carpeta", default=os.path.join(BASE, "respaldos"))
    def respaldo(carpeta):
        """Copia verificada de la base SQLite en respaldos/ (no sobrescribe nada)."""
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if not uri.startswith("sqlite:///"):
            raise click.ClickException("Solo para SQLite. En PostgreSQL usa pg_dump.")
        origen = uri.replace("sqlite:///", "", 1)
        os.makedirs(carpeta, exist_ok=True)
        destino = os.path.join(carpeta, f"porsiacaso_{ahora():%Y%m%d_%H%M%S}.db")
        if os.path.exists(destino):
            raise click.ClickException("Ya existe un respaldo con ese nombre; espera un segundo.")
        src, dst = sqlite3.connect(origen), sqlite3.connect(destino)
        with dst:
            src.backup(dst)
        estado = dst.execute("pragma integrity_check").fetchone()[0]
        src.close()
        dst.close()
        with open(destino, "rb") as f:
            huella = hashlib.sha256(f.read()).hexdigest()
        click.echo(f"Respaldo: {destino}\nIntegridad: {estado}\nSHA-256: {huella}")


app = crear_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")

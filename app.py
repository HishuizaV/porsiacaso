import os
import click
from flask import Flask, render_template, request, Response, url_for
from sqlalchemy import or_

from extensions import db, login_manager, migrate
from models import Usuario, Categoria, Articulo, Pagina
from admin import admin
from datos_iniciales import CATEGORIAS_INICIALES, PAGINAS_INICIALES

BASE = os.path.abspath(os.path.dirname(__file__))
SITE_URL = os.environ.get("SITE_URL", "http://127.0.0.1:5000").rstrip("/")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "cambia-esto-antes-de-publicar"),
    SQLALCHEMY_DATABASE_URI=os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE, "porsiacaso.db")),
    UPLOAD_FOLDER=os.path.join(BASE, "static", "uploads"),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("PRODUCCION") == "1",   # solo con HTTPS
)

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
app.register_blueprint(admin)


def abs_url(endpoint, **valores):
    """URL absoluta (para SEO, Open Graph y sitemap)."""
    return SITE_URL + url_for(endpoint, **valores)


app.jinja_env.globals["abs_url"] = abs_url


# ---------- Comandos ----------
@app.cli.command("iniciar")
def iniciar():
    """Carga categorías y páginas iniciales (después de: flask db upgrade)."""
    if Categoria.query.count() == 0:
        for i, (slug, corto, nombre, icono, desc) in enumerate(CATEGORIAS_INICIALES):
            db.session.add(Categoria(slug=slug, corto=corto, nombre=nombre,
                                     icono=icono, descripcion=desc, orden=i))
    if Pagina.query.count() == 0:
        for slug, titulo, contenido in PAGINAS_INICIALES:
            db.session.add(Pagina(slug=slug, titulo=titulo, contenido=contenido.strip()))
    db.session.commit()
    click.echo("Datos iniciales listos.")


@app.cli.command("crear-admin")
@click.option("--nombre", prompt=True)
@click.option("--email", prompt=True)
@click.password_option()
def crear_admin(nombre, email, password):
    """Crea el usuario administrador."""
    u = Usuario(nombre=nombre, email=email.strip().lower(), rol="admin")
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    click.echo("Administrador creado.")


# ---------- Consultas y contexto ----------
def publicados():
    return Articulo.query.filter_by(estado="publicado")


@app.context_processor
def globales():
    return {
        "CATEGORIAS": Categoria.query.order_by(Categoria.orden).all(),
        "RECIENTES": publicados().order_by(Articulo.fecha_publicacion.desc()).limit(4).all(),
        "PAGINAS": Pagina.query.order_by(Pagina.id).all(),
        "ANUNCIOS": os.environ.get("ANUNCIOS", "maqueta"),   # maqueta | off | adsense
        "SITE_URL": SITE_URL,
    }


@app.after_request
def cabeceras(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return resp


# ---------- Rutas públicas ----------
@app.route("/")
def inicio():
    destacados = (publicados()
                  .order_by(Articulo.destacado.desc(), Articulo.fecha_publicacion.desc())
                  .limit(3).all())
    recientes = publicados().order_by(Articulo.fecha_publicacion.desc()).limit(8).all()
    return render_template("inicio.html", destacados=destacados, recientes=recientes)


@app.route("/categoria/<slug>")
def categoria(slug):
    cat = Categoria.query.filter_by(slug=slug).first_or_404()
    lista = (publicados().filter_by(categoria_id=cat.id)
             .order_by(Articulo.fecha_publicacion.desc()).all())
    return render_template("categoria.html", cat=cat, articulos=lista)


@app.route("/articulo/<slug>")
def articulo(slug):
    a = publicados().filter_by(slug=slug).first_or_404()
    a.visitas = (a.visitas or 0) + 1
    db.session.commit()

    orden = Articulo.fecha_publicacion.desc()
    rel = (publicados().filter(Articulo.id != a.id, Articulo.categoria_id == a.categoria_id)
           .order_by(orden).limit(3).all())
    if len(rel) < 3:
        excluir = [a.id] + [r.id for r in rel]
        rel += publicados().filter(Articulo.id.notin_(excluir)).order_by(orden).limit(3 - len(rel)).all()
    return render_template("articulo.html", a=a, cat=a.categoria, relacionados=rel)


@app.route("/buscar")
def buscar():
    q = request.args.get("q", "").strip()
    lista = []
    if q:
        like = f"%{q}%"
        lista = (publicados()
                 .filter(or_(Articulo.titulo.ilike(like), Articulo.resumen.ilike(like)))
                 .order_by(Articulo.fecha_publicacion.desc()).all())
    return render_template("categoria.html", cat=None, articulos=lista, q=q)


# ---------- SEO ----------
@app.route("/sitemap.xml")
def sitemap():
    urls = [(abs_url("inicio"), None)]
    for c in Categoria.query.order_by(Categoria.orden).all():
        if publicados().filter_by(categoria_id=c.id).count():
            urls.append((abs_url("categoria", slug=c.slug), None))
    for p in Pagina.query.all():
        urls.append((abs_url("pagina", slug=p.slug), p.actualizado))
    for a in publicados().order_by(Articulo.fecha_publicacion.desc()).all():
        urls.append((abs_url("articulo", slug=a.slug), a.actualizado or a.creado))
    return Response(render_template("sitemap.xml", urls=urls), mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    txt = f"User-agent: *\nDisallow: /admin/\n\nSitemap: {abs_url('sitemap')}\n"
    return Response(txt, mimetype="text/plain")


# ---------- Páginas fijas (al final, es la ruta comodín) ----------
@app.route("/<slug>")
def pagina(slug):
    p = Pagina.query.filter_by(slug=slug).first_or_404()
    return render_template("pagina.html", titulo=p.titulo, contenido=p.contenido)


@app.errorhandler(404)
def no_encontrado(e):
    return render_template("pagina.html", titulo="Página no encontrada", noindex=True,
                           contenido="<p>Lo que buscas no existe o fue movido.</p>"), 404


@app.errorhandler(403)
def prohibido(e):
    return render_template("pagina.html", titulo="Sin permiso", noindex=True,
                           contenido="<p>No tienes permiso para hacer esto.</p>"), 403


if __name__ == "__main__":
    app.run(debug=True)
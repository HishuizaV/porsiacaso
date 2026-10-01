import os
import click
from flask import Flask, render_template, request, Response, url_for
from sqlalchemy import or_

from extensions import db, login_manager, migrate
from models import Usuario, Categoria, Ubicacion, Articulo, Pagina
from admin import admin
from utils import slugify
from datos_iniciales import (CATEGORIAS_INICIALES, PAGINAS_INICIALES,
                             REGIONES_INICIALES, CIUDADES_INICIALES)

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
    SESSION_COOKIE_SECURE=os.environ.get("PRODUCCION") == "1",
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


def ubicaciones_activas():
    """Zonas con al menos un artículo publicado, agrupadas por región."""
    ids = [i for (i,) in db.session.query(Articulo.ubicacion_id)
           .filter(Articulo.estado == "publicado", Articulo.ubicacion_id.isnot(None))
           .distinct()]
    if not ids:
        return []
    grupos = {}
    for u in Ubicacion.query.filter(Ubicacion.id.in_(ids)).all():
        region = u if (u.tipo == "region" or u.padre is None) else u.padre
        g = grupos.setdefault(region.id, {"region": region, "ciudades": []})
        if u.tipo == "ciudad" and u.padre is not None:
            g["ciudades"].append(u)
    lista = sorted(grupos.values(), key=lambda g: g["region"].nombre)
    for g in lista:
        g["ciudades"].sort(key=lambda c: c.nombre)
    return lista


@app.context_processor
def globales():
    return {
        "CATEGORIAS": Categoria.query.filter_by(visible=True).order_by(Categoria.orden).all(),
        "RECIENTES": publicados().order_by(Articulo.fecha_publicacion.desc()).limit(4).all(),
        "PAGINAS": Pagina.query.order_by(Pagina.id).all(),
        "ZONAS": ubicaciones_activas(),
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


@app.route("/zona/<slug>")
def zona(slug):
    u = Ubicacion.query.filter_by(slug=slug).first_or_404()
    ids = [u.id] + [h.id for h in u.hijas]
    orden = Articulo.fecha_publicacion.desc()
    locales = publicados().filter(Articulo.ubicacion_id.in_(ids)).order_by(orden).all()
    nacionales = publicados().filter(Articulo.ubicacion_id.is_(None)).order_by(orden).limit(6).all()
    ciudades = [h for h in u.hijas
                if publicados().filter_by(ubicacion_id=h.id).first() is not None]
    return render_template("zona.html", ubic=u, locales=locales,
                           nacionales=nacionales, ciudades=ciudades)


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
    for c in Categoria.query.filter_by(visible=True).order_by(Categoria.orden).all():
        if publicados().filter_by(categoria_id=c.id).count():
            urls.append((abs_url("categoria", slug=c.slug), None))
    for g in ubicaciones_activas():
        urls.append((abs_url("zona", slug=g["region"].slug), None))
        for c in g["ciudades"]:
            urls.append((abs_url("zona", slug=c.slug), None))
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
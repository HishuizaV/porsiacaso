"""Rutas públicas del portal."""
from flask import (Blueprint, render_template, request, Response, url_for, redirect, abort,
                   current_app, send_from_directory, g)
from flask_login import current_user
from sqlalchemy import or_

import ajustes
import seguridad
import seo
from consultas import (publicados, listar, filtro_vigentes, zonas_con_contenido,
                       fichas_por_vencer, conteo_por_tipo, instituciones_con_contenido)
from extensions import db
from models import Articulo, Categoria, Ubicacion, Pagina, Institucion, hoy
from tipos import (TIPOS, TIPOS_ARTICULO, ORDEN, SECTORES, MODALIDADES, NIVELES_EDUCATIVOS,
                   COSTOS, OPORTUNIDADES)

web = Blueprint("web", __name__)

LIMITE_BUSCAR = 30   # búsquedas por minuto por visitante
VIGENCIAS_FILTRO = [("vigentes", "Vigentes"), ("todas", "Todas"), ("vencidas", "Vencidas o cerradas")]
ORDENES = [("recientes", "Más recientes"), ("cierre", "Cierran pronto"), ("relevancia", "Relevancia")]


# ---------- Ayudas para plantillas ----------
def url_publicacion(a, absoluta=False):
    if a.tipo in TIPOS_ARTICULO or a.tipo not in TIPOS:
        ruta = url_for("web.articulo", slug=a.slug)
    else:
        ruta = url_for("web.ficha", tipo=a.tipo, slug=a.slug)
    return current_app.config["SITE_URL"] + ruta if absoluta else ruta


def url_enlace(e):
    if e.url:
        return e.url
    if e.archivo:
        return url_for("static", filename="uploads/docs/" + e.archivo)
    return None


def url_imagen(a, miniatura=False, absoluta=False):
    if not a.imagen:
        return None
    nombre = a.imagen
    if miniatura and nombre.endswith(".jpg"):
        nombre = nombre[:-4] + "_m.jpg"
    ruta = url_for("static", filename="uploads/" + nombre)
    return current_app.config["SITE_URL"] + ruta if absoluta else ruta


def url_con(**cambios):
    """URL de la página actual cambiando algunos parámetros (filtros, paginación)."""
    args = request.args.to_dict()
    args.update(cambios)
    if "page" not in cambios:
        args.pop("page", None)
    args = {k: v for k, v in args.items() if v not in (None, "")}
    if str(args.get("page")) == "1":
        args.pop("page")
    return url_for(request.endpoint, **(request.view_args or {}), **args)


def es_admin():
    return current_user.is_authenticated and current_user.es_admin


def contexto_publico():
    if request.blueprint == "admin" and not g.get("vista_publica"):
        return {}
    conteos = conteo_por_tipo()
    return {
        "CATEGORIAS": Categoria.query.filter_by(visible=True).order_by(Categoria.orden).all(),
        "PAGINAS": Pagina.query.filter_by(visible=True).order_by(Pagina.id).all(),
        "MENU": [(k, TIPOS[k]) for k in ORDEN if conteos.get(k)],
        "CONTEOS": conteos,
        "TIPOS": TIPOS,
        "PUBLICIDAD": ajustes.publicidad(),
        "AJUSTES": ajustes.todos(),
        "ES_ADMIN": es_admin(),
        "SITE_URL": current_app.config["SITE_URL"],
        "JSONLD_ORG": seo.organizacion(_abs),
        "JSONLD_WEB": seo.sitio_web(_abs),
        "HOY": hoy(),
    }


def _abs(endpoint, **valores):
    return current_app.config["SITE_URL"] + url_for(endpoint, **valores)


def paginar(query):
    pagina = request.args.get("page", 1, type=int) or 1
    if pagina < 1:
        abort(404)
    p = query.paginate(page=pagina, per_page=current_app.config["POR_PAGINA"], error_out=False)
    if pagina > 1 and pagina > (p.pages or 1):
        abort(404)
    return p


def _opcion(nombre, opciones):
    v = request.args.get(nombre, "")
    return v if v in dict(opciones) else ""


# ---------- Inicio ----------
@web.route("/")
def inicio():
    base = publicados()
    destacados = (base.filter(Articulo.destacado.is_(True), filtro_vigentes())
                  .order_by(Articulo.fecha_publicacion.desc()).limit(3).all())
    # Cada publicación aparece una sola vez en la portada
    por_vencer = [a for a in fichas_por_vencer() if a not in destacados]
    mostrados = [a.id for a in destacados + por_vencer]
    oportunidades = base.filter(Articulo.tipo.in_(OPORTUNIDADES), filtro_vigentes())
    if mostrados:
        oportunidades = oportunidades.filter(Articulo.id.notin_(mostrados))
    oportunidades = oportunidades.order_by(Articulo.fecha_publicacion.desc()).limit(6).all()
    guias = (base.filter(Articulo.tipo.in_(["guia", "tramite"]))
             .order_by(Articulo.fecha_publicacion.desc()).limit(4).all())
    noticias = base.filter(Articulo.tipo.in_(TIPOS_ARTICULO))
    if mostrados:
        noticias = noticias.filter(Articulo.id.notin_(mostrados))
    noticias = noticias.order_by(Articulo.fecha_publicacion.desc()).limit(4).all()
    return render_template("inicio.html", destacados=destacados, oportunidades=oportunidades,
                           por_vencer=por_vencer, guias=guias, noticias=noticias,
                           regiones=zonas_con_contenido()[:12])


# ---------- Secciones por tipo ----------
def _seccion(tipo, zona=None):
    info = TIPOS[tipo]
    es_empleo = info["detalle"] == "empleo"
    filtros = {
        "q": request.args.get("q", "").strip()[:100],
        "vigencia": _opcion("vigencia", VIGENCIAS_FILTRO) or ("vigentes" if info["oportunidad"]
                                                              else "todas"),
        "orden": _opcion("orden", ORDENES) or "recientes",
        "sector": _opcion("sector", SECTORES) if es_empleo else "",
        "modalidad": _opcion("modalidad", MODALIDADES) if es_empleo else "",
        "nivel": _opcion("nivel", NIVELES_EDUCATIVOS) if es_empleo else "",
        "costo": _opcion("costo", COSTOS) if tipo == "curso" else "",
        "region": "", "institucion": "",
    }
    if zona is None and request.args.get("region"):
        zona = Ubicacion.query.filter_by(slug=request.args["region"]).first()
        filtros["region"] = zona.slug if zona else ""
    institucion = None
    if request.args.get("institucion"):
        institucion = Institucion.query.filter_by(slug=request.args["institucion"]).first()
        filtros["institucion"] = institucion.slug if institucion else ""
    if filtros["orden"] == "relevancia" and not filtros["q"]:
        filtros["orden"] = "recientes"

    query = listar(tipo=tipo, q=filtros["q"], zona=zona, institucion=institucion,
                   sector=filtros["sector"], modalidad=filtros["modalidad"],
                   nivel=filtros["nivel"], costo=filtros["costo"],
                   vigencia=filtros["vigencia"], orden=filtros["orden"])
    pag = paginar(query)

    # Página filtrada = no indexable (evita miles de combinaciones duplicadas)
    activos = {k: v for k, v in filtros.items() if v and k not in ("vigencia", "orden")}
    por_defecto = filtros["vigencia"] == ("vigentes" if info["oportunidad"] else "todas") \
        and filtros["orden"] == "recientes"
    indexable = not activos and por_defecto and pag.total > 0
    if zona is not None:
        indexable = por_defecto and not activos and pag.total > 0
    vencidas = 0
    if info["oportunidad"] and filtros["vigencia"] == "vigentes":
        vencidas = listar(tipo=tipo, q=filtros["q"], zona=zona, institucion=institucion,
                          sector=filtros["sector"], modalidad=filtros["modalidad"],
                          nivel=filtros["nivel"], costo=filtros["costo"],
                          vigencia="vencidas").count()
    migas = [("Inicio", _abs("web.inicio")), (info["plural"], _abs("web.seccion", tipo=tipo))]
    if zona is not None:
        migas.append((zona.nombre, None))
    return render_template(
        "seccion.html", tipo=tipo, info=info, pag=pag, filtros=filtros, zona=zona,
        jsonld_migas=seo.migas(migas),
        institucion=institucion, indexable=indexable, vencidas=vencidas,
        regiones=zonas_con_contenido(tipo),
        instituciones=instituciones_con_contenido(tipo) if info["institucion"] else [],
        es_empleo=es_empleo, opciones=dict(sector=SECTORES[:2], modalidad=MODALIDADES,
                                           nivel=NIVELES_EDUCATIVOS, costo=COSTOS,
                                           vigencia=VIGENCIAS_FILTRO, orden=ORDENES))


def seccion(tipo):
    return _seccion(tipo)


def seccion_region(tipo, zona_slug):
    zona = Ubicacion.query.filter_by(slug=zona_slug).first_or_404()
    return _seccion(tipo, zona)


# ---------- Fichas ----------
def _cargar_publica(slug):
    a = Articulo.query.filter_by(slug=slug).first_or_404()
    visible = a.estado in ("publicado", "archivado") and a.fecha_publicacion is not None \
        and not a.programada
    if not visible:
        abort(404)
    return a


def _relacionados(a):
    base = publicados().filter(Articulo.id != a.id, Articulo.tipo == a.tipo)
    if a.es_oportunidad:
        base = base.filter(filtro_vigentes())
    rel = []
    if a.ubicacion:
        rel = (base.filter(Articulo.ubicacion_id.in_([a.ubicacion.region.id] +
                                                     [h.id for h in a.ubicacion.region.hijas]))
               .order_by(Articulo.fecha_publicacion.desc()).limit(3).all())
    if len(rel) < 3:
        resto = base.filter(Articulo.id.notin_([r.id for r in rel])) if rel else base
        rel += resto.order_by(Articulo.fecha_publicacion.desc()).limit(3 - len(rel)).all()
    return rel


def _contar_visita(a):
    if current_user.is_authenticated:
        return
    db.session.query(Articulo).filter_by(id=a.id).update(
        {Articulo.visitas: Articulo.visitas + 1}, synchronize_session=False)
    db.session.commit()


def render_publicacion(a, vista_previa=False):
    url = url_publicacion(a, absoluta=True)
    imagen = url_imagen(a, absoluta=True) or _abs("static", filename="img/og-portada.jpg")
    info = a.info
    migas = [("Inicio", url_for("web.inicio")),
             (info["plural"], url_for("web.seccion", tipo=a.tipo)), (a.titulo, None)]
    jsonld = [seo.migas([("Inicio", _abs("web.inicio")),
                         (info["plural"], _abs("web.seccion", tipo=a.tipo)), (a.titulo, None)])]
    if a.tipo == "empleo":
        logo = (_abs("static", filename="uploads/logos/" + a.institucion.logo)
                if a.institucion and a.institucion.logo else None)
        oferta = None if vista_previa else seo.oferta_empleo(a, url, _abs, logo)
        if oferta:
            jsonld.append(oferta)
    elif a.tipo in ("noticia", "guia", "otro"):
        jsonld.append(seo.articulo(a, url, imagen, _abs))
    return render_template("publicacion.html", a=a, info=info, d=a.detalle, url=url,
                           imagen_og=imagen, jsonld=jsonld, migas=migas,
                           relacionados=[] if vista_previa else _relacionados(a),
                           vista_previa=vista_previa,
                           motivos_jobposting=seo.motivos_sin_jobposting(a)
                           if (vista_previa and a.tipo == "empleo") else [])


def ficha(tipo, slug):
    a = _cargar_publica(slug)
    if a.tipo != tipo:
        return redirect(url_publicacion(a), 301)
    _contar_visita(a)
    return render_publicacion(a)


@web.route("/articulo/<slug>")
def articulo(slug):
    a = _cargar_publica(slug)
    if a.tipo not in TIPOS_ARTICULO:
        return redirect(url_publicacion(a), 301)
    _contar_visita(a)
    return render_publicacion(a)


for _tipo, _d in TIPOS.items():
    web.add_url_rule(f"/{_d['seccion']}", "seccion", seccion, defaults={"tipo": _tipo})
    web.add_url_rule(f"/{_d['seccion']}/region/<zona_slug>", "seccion_region", seccion_region,
                     defaults={"tipo": _tipo})
    if _tipo not in TIPOS_ARTICULO:
        web.add_url_rule(f"/{_d['seccion']}/<slug>", "ficha", ficha, defaults={"tipo": _tipo})


# ---------- Categorías, zonas y búsqueda ----------
@web.route("/categoria/<slug>")
def categoria(slug):
    cat = Categoria.query.filter_by(slug=slug).first_or_404()
    query = publicados().filter_by(categoria_id=cat.id).order_by(Articulo.fecha_publicacion.desc())
    return render_template("listado.html", cat=cat, pag=paginar(query), modo="categoria")


@web.route("/zona/<slug>")
def zona(slug):
    u = Ubicacion.query.filter_by(slug=slug).first_or_404()
    ids = [u.id] + [h.id for h in u.hijas]
    query = (publicados().filter(Articulo.ubicacion_id.in_(ids))
             .order_by(Articulo.fecha_publicacion.desc()))
    ciudades = [h for h in u.hijas if publicados().filter_by(ubicacion_id=h.id).first()]
    secciones = [(k, TIPOS[k]) for k in ORDEN
                 if publicados().filter(Articulo.tipo == k, Articulo.ubicacion_id.in_(ids)).first()]
    return render_template("listado.html", ubic=u, pag=paginar(query), modo="zona",
                           ciudades=ciudades, secciones=secciones)


@web.route("/buscar")
def buscar():
    q = request.args.get("q", "").strip()[:100]
    tipo = request.args.get("tipo", "")
    tipo = tipo if tipo in TIPOS else None
    pag = None
    if q and not seguridad.permitir_persistente("buscar", seguridad.ip_cliente(), LIMITE_BUSCAR):
        abort(429)
    if q:
        orden = "relevancia"
        pag = paginar(listar(tipo=tipo, q=q, vigencia="todas", orden=orden))
    return render_template("buscar.html", q=q, tipo=tipo, pag=pag)


# ---------- SEO y archivos especiales ----------
@web.route("/sitemap.xml")
def sitemap():
    urls = [(_abs("web.inicio"), None)]
    conteos = conteo_por_tipo()
    for k in ORDEN:
        if conteos.get(k):
            urls.append((_abs("web.seccion", tipo=k), None))
            for region, _n in zonas_con_contenido(k):
                urls.append((_abs("web.seccion_region", tipo=k, zona_slug=region.slug), None))
    for c in Categoria.query.filter_by(visible=True).order_by(Categoria.orden).all():
        if publicados().filter_by(categoria_id=c.id).first():
            urls.append((_abs("web.categoria", slug=c.slug), None))
    ids_con = {i for (i,) in publicados().with_entities(Articulo.ubicacion_id).distinct() if i}
    for u in Ubicacion.query.filter(or_(Ubicacion.id.in_(ids_con),
                                        Ubicacion.hijas.any(Ubicacion.id.in_(ids_con)))).all():
        urls.append((_abs("web.zona", slug=u.slug), None))
    for p in Pagina.query.filter_by(visible=True).all():
        urls.append((_abs("web.pagina", slug=p.slug), p.actualizado))
    for a in publicados().order_by(Articulo.fecha_publicacion.desc()).all():
        urls.append((url_publicacion(a, absoluta=True), a.actualizado or a.creado))
    return Response(render_template("sitemap.xml", urls=urls), mimetype="application/xml")


@web.route("/robots.txt")
def robots():
    txt = ("User-agent: *\nDisallow: /admin/\nDisallow: /api/\n\n"
           f"Sitemap: {_abs('web.sitemap')}\n")
    return Response(txt, mimetype="text/plain")


@web.route("/ads.txt")
def ads_txt():
    contenido = ajustes.obtener("ads_txt")
    if not contenido:
        abort(404)
    return Response(contenido.strip() + "\n", mimetype="text/plain")


@web.route("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "img/favicon-32.png",
                               mimetype="image/png", max_age=86400)


# ---------- Páginas fijas (al final, es la ruta comodín) ----------
@web.route("/<slug>")
def pagina(slug):
    p = Pagina.query.filter_by(slug=slug).first_or_404()
    if not p.visible and not es_admin():
        abort(404)
    return render_template("pagina.html", p=p, titulo=p.titulo, contenido=p.contenido,
                           noindex=not p.visible)

"""Consultas reutilizables sobre publicaciones (sitio público, buscador y asistente)."""
from datetime import timedelta

from sqlalchemy import or_, and_, case, func

from extensions import db
from models import (Articulo, Ubicacion, Institucion, DetalleEmpleo, DetalleCurso,
                    ahora, hoy, lineas)
from tipos import TIPOS
from utils import normalizar, texto_plano

PALABRAS_VACIAS = set("""a al algo algun alguna alguno ante con como cual de del desde donde el en
entre es esa ese esta este hay la las le lo los me mi mis o para pero por que quiero se sin sobre
su sus te tu un una uno unos unas y ya yo busco buscar necesito informacion quisiera hola favor
puedo puedes ver saber dame dime hay""".split())


def publicados():
    """Publicadas, visibles (no programadas a futuro) y no archivadas."""
    return Articulo.query.filter(Articulo.estado == "publicado",
                                 Articulo.fecha_publicacion.isnot(None),
                                 Articulo.fecha_publicacion <= ahora())


def filtro_vigentes():
    return and_(or_(Articulo.fecha_limite.is_(None), Articulo.fecha_limite >= hoy()),
                or_(Articulo.vigencia.is_(None), Articulo.vigencia != "cerrada"))


def filtro_no_vigentes():
    return or_(Articulo.fecha_limite < hoy(), Articulo.vigencia == "cerrada")


def ids_zona(u):
    """La zona y, si es región, sus ciudades."""
    return [u.id] + [h.id for h in u.hijas]


def conteo_por_tipo():
    filas = (db.session.query(Articulo.tipo, func.count(Articulo.id))
             .filter(Articulo.id.in_(publicados().with_entities(Articulo.id)))
             .group_by(Articulo.tipo).all())
    return dict(filas)


def fichas_por_vencer(dias=7, limite=6):
    return (publicados().filter(Articulo.fecha_limite.isnot(None),
                                Articulo.fecha_limite >= hoy(),
                                Articulo.fecha_limite <= hoy() + timedelta(days=dias),
                                or_(Articulo.vigencia.is_(None), Articulo.vigencia != "cerrada"))
            .order_by(Articulo.fecha_limite.asc()).limit(limite).all())


def terminos(q):
    return [p for p in normalizar(q).split() if p not in PALABRAS_VACIAS and len(p) > 1][:8]


def aplicar_busqueda(query, palabras):
    """Todas las palabras deben aparecer (sin tildes). Devuelve (query, expresión de relevancia)."""
    for p in palabras:
        query = query.filter(Articulo.busqueda.like(f"%{p}%"))
    puntaje = sum((case((Articulo.busqueda_titulo.like(f"%{p}%"), 3), else_=0) for p in palabras),
                  start=0) if palabras else None
    return query, puntaje


def actualizar_busqueda(a):
    """Recalcula el texto normalizado de una publicación (se llama al guardar)."""
    partes = [a.titulo, a.resumen, texto_plano(a.contenido)]
    if a.institucion:
        partes += [a.institucion.nombre, a.institucion.siglas]
    if a.ubicacion:
        partes += [a.ubicacion.nombre, a.ubicacion.region.nombre]
    if a.categoria:
        partes.append(a.categoria.nombre)
    partes.append(TIPOS.get(a.tipo, {}).get("plural", ""))
    d = a.detalle
    if d is not None:
        for col in d.__table__.columns:
            v = getattr(d, col.name)
            if isinstance(v, str):
                partes.append(v)
    a.busqueda_titulo = normalizar(a.titulo)[:300]
    a.busqueda = normalizar(" ".join(p for p in partes if p))


def listar(tipo=None, q="", zona=None, institucion=None, sector=None, modalidad=None,
           nivel=None, costo=None, vigencia="vigentes", orden="recientes"):
    """Consulta filtrada para las secciones y el buscador."""
    query = publicados()
    if tipo:
        query = query.filter(Articulo.tipo.in_(tipo) if isinstance(tipo, (list, tuple))
                             else Articulo.tipo == tipo)
    palabras = terminos(q)
    query, puntaje = aplicar_busqueda(query, palabras)
    if zona is not None:
        query = query.filter(Articulo.ubicacion_id.in_(ids_zona(zona)))
    if institucion is not None:
        query = query.filter(Articulo.institucion_id == institucion.id)
    if sector or modalidad or nivel:
        query = query.join(DetalleEmpleo, DetalleEmpleo.articulo_id == Articulo.id)
        if sector:
            query = query.filter(DetalleEmpleo.sector == sector)
        if modalidad:
            query = query.filter(DetalleEmpleo.modalidad == modalidad)
        if nivel:
            query = query.filter(DetalleEmpleo.nivel_educativo == nivel)
    if costo:
        query = query.join(DetalleCurso, DetalleCurso.articulo_id == Articulo.id) \
            .filter(DetalleCurso.costo == costo)
    if vigencia == "vigentes":
        query = query.filter(filtro_vigentes())
    elif vigencia == "vencidas":
        query = query.filter(filtro_no_vigentes())

    if orden == "cierre":
        query = query.order_by(Articulo.fecha_limite.is_(None), Articulo.fecha_limite.asc(),
                               Articulo.fecha_publicacion.desc())
    elif orden == "relevancia" and puntaje is not None:
        query = query.order_by(puntaje.desc(), Articulo.destacado.desc(),
                               Articulo.fecha_publicacion.desc())
    else:
        query = query.order_by(Articulo.fecha_publicacion.desc())
    return query


def buscar_zona(texto):
    """Encuentra una zona mencionada en un texto libre ('trabajo en chiclayo')."""
    t = f" {normalizar(texto)} "
    mejor = None
    for u in Ubicacion.query.all():
        n = normalizar(u.nombre)
        if n and f" {n} " in t and (mejor is None or len(n) > len(normalizar(mejor.nombre))):
            mejor = u
    return mejor


def zonas_con_contenido(tipo=None):
    """Regiones con publicaciones vigentes (y su conteo), para accesos por región."""
    query = publicados().filter(Articulo.ubicacion_id.isnot(None), filtro_vigentes())
    if tipo:
        query = query.filter(Articulo.tipo == tipo)
    conteo = {}
    for a in query.with_entities(Articulo.ubicacion_id).all():
        conteo[a.ubicacion_id] = conteo.get(a.ubicacion_id, 0) + 1
    if not conteo:
        return []
    regiones = {}
    for u in Ubicacion.query.filter(Ubicacion.id.in_(conteo)).all():
        r = u.region
        regiones[r.id] = (r, regiones.get(r.id, (r, 0))[1] + conteo[u.id])
    return sorted(regiones.values(), key=lambda x: (-x[1], x[0].nombre))


def instituciones_con_contenido(tipo):
    return (Institucion.query.join(Articulo)
            .filter(Articulo.id.in_(publicados().filter(Articulo.tipo == tipo)
                                    .with_entities(Articulo.id)))
            .distinct().order_by(Institucion.nombre).all())


__all__ = ["publicados", "filtro_vigentes", "listar", "terminos", "actualizar_busqueda",
           "buscar_zona", "zonas_con_contenido", "fichas_por_vencer", "conteo_por_tipo",
           "instituciones_con_contenido", "lineas"]

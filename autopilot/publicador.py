"""Agente publicador: crea fichas en el CMS existente con sus mismas validaciones.

El Autopilot actúa con una cuenta técnica (rol «servicio», sin acceso al panel ni permisos de
administrador). Solo puede publicar cuando la política lo autoriza; en cualquier otro caso deja
la ficha «Pendiente de revisión».
"""
import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, time as dtime
from decimal import Decimal

from extensions import db
from models import (Articulo, Categoria, Enlace, Usuario, Registro, MODELOS_DETALLE, ahora, hoy)
from tipos import TIPOS, RUTAS_RESERVADAS
from autopilot.modelos import DecisionEditorial, VersionArticulo

EMAIL_SERVICIO = "autopilot@servicio.local"
VENTANA = (dtime(7, 0), dtime(21, 0))   # horario de publicación automática (hora de Lima)
CAMPOS_VERSION = ("titulo", "resumen", "contenido", "fecha_limite", "vigencia", "fuente_url")


def usuario_servicio():
    u = Usuario.query.filter_by(email=EMAIL_SERVICIO).first()
    if not u:
        u = Usuario(nombre="Autopilot", email=EMAIL_SERVICIO, rol="servicio", activo=False)
        u.set_password(secrets.token_urlsafe(32))   # nadie conoce esta clave; además no puede iniciar sesión
        db.session.add(u)
        db.session.flush()
    return u


def clave_para(url_normalizada):
    return "ap-" + hashlib.sha1(url_normalizada.encode()).hexdigest()[:24]


def siguiente_horario(espaciado_min):
    """Próximo hueco para publicar, separado de la última publicación automática programada."""
    inicio = ahora()
    ultima = (db.session.query(db.func.max(Articulo.fecha_publicacion))
              .filter(Articulo.origen == "autopilot", Articulo.estado == "publicado").scalar())
    if ultima and ultima + timedelta(minutes=espaciado_min) > inicio:
        inicio = ultima + timedelta(minutes=espaciado_min)
    if inicio.time() < VENTANA[0]:
        inicio = datetime.combine(inicio.date(), VENTANA[0])
    elif inicio.time() > VENTANA[1]:
        inicio = datetime.combine(inicio.date() + timedelta(days=1), VENTANA[0])
    return inicio.replace(second=0, microsecond=0)


def _serializar(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def snapshot(a):
    datos = {c: _serializar(getattr(a, c)) for c in CAMPOS_VERSION}
    d = a.detalle
    datos["detalle"] = {col.name: _serializar(getattr(d, col.name)) for col in d.__table__.columns
                        if col.name != "articulo_id"} if d is not None else {}
    datos["enlaces"] = [[e.tipo, e.etiqueta, e.url] for e in a.enlaces if e.url]
    return datos


def _leer(campo, valor):
    if valor is None:
        return None
    if campo in ("fecha_limite", "fecha_inicio") and isinstance(valor, str):
        return date.fromisoformat(valor[:10])
    if campo in ("sueldo_min", "sueldo_max") and valor is not None:
        return Decimal(str(valor))
    return valor


def aplicar_datos(a, datos):
    for c in CAMPOS_VERSION:
        if c in datos:
            setattr(a, c, _leer(c, datos[c]))
    if "detalle" in datos:
        d = a.asegurar_detalle()
        if d is not None:
            for k, v in datos["detalle"].items():
                if hasattr(d, k):
                    setattr(d, k, _leer(k, v))
    if "enlaces" in datos:
        a.enlaces = [Enlace(tipo=t, etiqueta=e, url=u, orden=i) for i, (t, e, u) in enumerate(datos["enlaces"])]
    a.actualizado = ahora()


def _registro(usuario, accion, detalle):
    db.session.add(Registro(usuario_id=usuario.id if usuario else None, accion=accion, detalle=detalle[:300]))


def crear_publicacion(h, borrador, enlaces_verificados, decision, checklist, motivos, fuente, institucion,
                      zona, cfg):
    """Crea la ficha en el CMS. Devuelve el Articulo."""
    from admin_contenido import validar_publicacion   # mismas reglas que el formulario
    from admin import slug_unico_modelo
    from consultas import actualizar_busqueda

    servicio = usuario_servicio()
    tipo = borrador["tipo"]
    info = TIPOS[tipo]
    cat = Categoria.query.filter_by(slug=info["categoria"]).first() or Categoria.query.order_by(Categoria.orden).first()
    enlaces = [(t, e, u) for t, e, u, ok, _d in enlaces_verificados if ok is not False]

    a = Articulo(tipo=tipo, titulo=borrador["titulo"], resumen=borrador["resumen"],
                 contenido=borrador["contenido"], categoria=cat, autor_id=servicio.id, origen="autopilot",
                 slug=slug_unico_modelo(Articulo, borrador["titulo"], reservados=RUTAS_RESERVADAS),
                 clave_externa=clave_para(h.url_normalizada), fuente_url=h.url, fuente_nombre=fuente.nombre,
                 fecha_limite=borrador["fecha_limite"], vigencia="abierta" if borrador["fecha_limite"] else None,
                 verificado_en=hoy(), verificado_por_id=servicio.id, editado_por_id=servicio.id,
                 estado="revision", creado=ahora(), actualizado=ahora())
    a.institucion, a.ubicacion = institucion, zona
    notas = ["Preparada por el Autopilot desde: " + h.url]
    if motivos:
        notas.append("Pendiente: " + "; ".join(motivos))
    if borrador.get("enlaces_internos"):
        notas.append("Enlaces internos sugeridos: " + ", ".join(borrador["enlaces_internos"]))
    a.notas_internas = "\n".join(notas)[:3000]
    db.session.add(a)
    d = a.asegurar_detalle()
    if d is not None:
        for k, v in borrador["detalle"].items():
            if hasattr(d, k):
                setattr(d, k, Decimal(str(v)) if k in ("sueldo_min", "sueldo_max") else v)
    a.enlaces = [Enlace(tipo=t, etiqueta=e, url=u, orden=i) for i, (t, e, u) in enumerate(enlaces)]

    final = "revision"
    if decision == "autopublicable":
        errores = validar_publicacion(
            tipo, dict(resumen=a.resumen, contenido=a.contenido, fuente_url=a.fuente_url),
            borrador["detalle"], [dict(url=u, archivo=None, pdf=None) for _t, _e, u in enlaces], institucion)
        if errores:
            motivos = motivos + errores
        else:
            a.estado = "publicado"
            a.fecha_publicacion = siguiente_horario(cfg["espaciado"]) if cfg["espaciado"] else ahora()
            a.aprobado_por_id = a.publicado_por_id = servicio.id
            final = "programado" if a.fecha_publicacion > ahora() else "autopublicado"
    db.session.flush()
    actualizar_busqueda(a)
    db.session.add(DecisionEditorial(articulo_id=a.id, hallazgo_id=h.id, decision=final,
                                     motivo="; ".join(motivos)[:2000] or None,
                                     checklist_json=json.dumps(checklist, ensure_ascii=False),
                                     actor="autopilot", usuario_id=servicio.id))
    _registro(servicio, f"autopilot_{final}", f"#{a.id} {a.titulo}")
    return a


def proponer_actualizacion(a, nuevos, h):
    """Si la fuente cambió algo importante, se propone el cambio (no se sobrescribe)."""
    antes = snapshot(a)
    despues = {c: _serializar(nuevos[c]) for c in CAMPOS_VERSION if c in nuevos}
    if "detalle" in nuevos:
        despues["detalle"] = {k: _serializar(v) for k, v in nuevos["detalle"].items()}
    if "enlaces" in nuevos:
        despues["enlaces"] = [list(x) for x in nuevos["enlaces"]]
    cambios = []
    for c, v in despues.items():
        if c in ("detalle",):
            for k, x in v.items():
                if antes["detalle"].get(k) != x and x not in (None, ""):
                    cambios.append(f"{k}: {antes['detalle'].get(k)!r} → {x!r}")
        elif antes.get(c) != v and v not in (None, ""):
            cambios.append(f"{c}: cambió")
    if not cambios:
        return None
    pendiente = VersionArticulo.query.filter_by(articulo_id=a.id, estado="pendiente").first()
    if pendiente and pendiente.despues == despues:
        return pendiente   # idempotente: la misma propuesta no se repite
    v = VersionArticulo(articulo_id=a.id, hallazgo_id=h.id if h else None, origen="autopilot",
                        tipo="propuesta", estado="pendiente", datos_antes=json.dumps(antes, ensure_ascii=False),
                        datos_despues=json.dumps(despues, ensure_ascii=False),
                        resumen_cambios="\n".join(cambios)[:4000])
    db.session.add(v)
    return v


def aplicar_version(v, usuario):
    a = v.articulo
    v.datos_antes = json.dumps(snapshot(a), ensure_ascii=False)   # estado real justo antes de aplicar
    aplicar_datos(a, v.despues)
    a.editado_por_id = usuario.id
    v.estado, v.usuario_id = "aplicada", usuario.id
    from consultas import actualizar_busqueda
    actualizar_busqueda(a)
    _registro(usuario, "version_aplicada", f"#{a.id} versión {v.id}")


def revertir_version(v, usuario):
    if v.estado != "aplicada":
        raise ValueError("Solo se puede revertir una versión aplicada")
    a = v.articulo
    aplicar_datos(a, v.antes)
    a.editado_por_id = usuario.id
    v.estado = "revertida"
    from consultas import actualizar_busqueda
    actualizar_busqueda(a)
    _registro(usuario, "version_revertida", f"#{a.id} versión {v.id}")


__all__ = ["usuario_servicio", "crear_publicacion", "proponer_actualizacion", "aplicar_version",
           "revertir_version", "snapshot", "siguiente_horario", "clave_para", "MODELOS_DETALLE"]

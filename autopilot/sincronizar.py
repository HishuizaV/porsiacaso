"""Sincronización laptop → servidor público.

La jornada corre en la laptop; el sitio público vive en un servidor. Este módulo envía las fichas
preparadas (en revisión o programadas) para que el servidor las guarde y las muestre a su hora,
aunque la laptop esté apagada.

Seguridad:
- Firma HMAC-SHA256 con un secreto compartido (AUTOPILOT_TOKEN, mín. 32 caracteres) y marca de
  tiempo: se rechazan firmas inválidas o con más de 5 minutos de diferencia (repetición).
- El servidor NO confía en la laptop: vuelve a sanitizar el HTML, valida URLs y reglas del CMS y
  solo acepta fichas «publicadas» si SU PROPIA política del Autopilot (modo B/C con requisitos
  completos) lo permite. En otro caso las guarda en revisión.
- Idempotente por `clave_externa`: reenviar no duplica. Si la ficha del servidor ya está
  publicada, el cambio llega como propuesta (no sobrescribe).
"""
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime
from decimal import Decimal

import httpx
from flask import Blueprint, request, jsonify, abort

from extensions import db
from models import Articulo, Categoria, Institucion, Ubicacion, Enlace, Registro, ahora
from tipos import TIPOS, ENLACES, RUTAS_RESERVADAS
from utils import limpiar_html, url_valida
from seguridad import exento_csrf

api_sync = Blueprint("api_sync", __name__, url_prefix="/api/autopilot")
TOLERANCIA = 300
LIMITE_LOTE = 50


def token():
    t = os.environ.get("AUTOPILOT_TOKEN", "")
    return t if len(t) >= 32 else None


def firmar(cuerpo: bytes, marca: str, secreto: str):
    return hmac.new(secreto.encode(), marca.encode() + b"." + cuerpo, hashlib.sha256).hexdigest()


def _iso(v):
    if isinstance(v, datetime):
        return v.isoformat() + "-05:00"
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def empaquetar(a):
    d = a.detalle
    return {
        "clave": a.clave_externa, "tipo": a.tipo, "titulo": a.titulo, "resumen": a.resumen, "contenido": a.contenido,
        "detalle": {c.name: _iso(getattr(d, c.name)) for c in d.__table__.columns if c.name != "articulo_id"} if d else {},
        "enlaces": [[e.tipo, e.etiqueta, e.url] for e in a.enlaces if e.url],
        "fecha_limite": _iso(a.fecha_limite), "vigencia": a.vigencia, "fuente_url": a.fuente_url,
        "fuente_nombre": a.fuente_nombre, "estado": a.estado, "fecha_publicacion": _iso(a.fecha_publicacion),
        "institucion": {"nombre": a.institucion.nombre, "siglas": a.institucion.siglas,
                        "sector": a.institucion.sector, "web": a.institucion.web} if a.institucion else None,
        "ubicacion": a.ubicacion.slug if a.ubicacion else None,
        "categoria": a.categoria.slug if a.categoria else None,
        "verificado_en": _iso(a.verificado_en), "notas": a.notas_internas,
    }


# ---------- Cliente (laptop) ----------
def enviar_pendientes(destino, transporte=None, secreto=None):
    secreto = secreto or token()
    if not secreto:
        raise RuntimeError("Define AUTOPILOT_TOKEN (mínimo 32 caracteres), igual en la laptop y en el servidor.")
    if not (destino.startswith("https://") or destino.startswith("http://127.0.0.1") or transporte is not None):
        raise RuntimeError("El destino debe usar https://")
    pendientes = (Articulo.query.filter(Articulo.origen == "autopilot", Articulo.clave_externa.isnot(None),
                                        Articulo.estado.in_(("revision", "publicado")))
                  .filter((Articulo.sincronizado_en.is_(None)) | (Articulo.actualizado > Articulo.sincronizado_en))
                  .order_by(Articulo.id).limit(LIMITE_LOTE).all())
    if not pendientes:
        return {"enviadas": 0, "resultados": []}
    cuerpo = json.dumps({"publicaciones": [empaquetar(a) for a in pendientes]}, ensure_ascii=False).encode()
    marca = str(int(time.time()))
    with httpx.Client(transport=transporte, timeout=60) as c:
        r = c.post(destino.rstrip("/") + "/api/autopilot/recibir", content=cuerpo,
                   headers={"Content-Type": "application/json", "X-Autopilot-Fecha": marca,
                            "X-Autopilot-Firma": firmar(cuerpo, marca, secreto)})
    r.raise_for_status()
    resultados = r.json().get("resultados", [])
    aceptadas = {x["clave"] for x in resultados if x.get("estado") in ("revision", "publicado", "propuesta", "sin_cambios")}
    for a in pendientes:
        if a.clave_externa in aceptadas:
            a.sincronizado_en = ahora()
    db.session.commit()
    return {"enviadas": len(pendientes), "resultados": resultados}


# ---------- Servidor ----------
def _fecha(v):
    if not v:
        return None
    return date.fromisoformat(str(v)[:10])


def _fecha_hora(v):
    if not v:
        return None
    dt = datetime.fromisoformat(str(v))
    if dt.tzinfo is not None:   # se guarda en hora de Lima sin zona
        from models import LIMA
        dt = dt.astimezone(LIMA).replace(tzinfo=None)
    return dt


def _recibir_una(p, servicio, cfg):
    from admin import slug_unico_modelo
    from admin_contenido import validar_publicacion, buscar_o_crear_institucion
    from consultas import actualizar_busqueda
    from autopilot.publicador import proponer_actualizacion

    clave, tipo = str(p.get("clave") or "")[:80], p.get("tipo")
    if not clave.startswith("ap-") or tipo not in TIPOS:
        return {"clave": clave, "estado": "rechazada", "motivo": "clave o tipo no válidos"}
    enlaces = [(t if t in ENLACES else "otro", (e or None) and str(e)[:80], u) for t, e, u in p.get("enlaces", [])
               if isinstance(u, str) and url_valida(u)][:20]
    detalle = {k: v for k, v in (p.get("detalle") or {}).items() if isinstance(k, str)}
    for k in ("fecha_inicio",):
        if detalle.get(k):
            detalle[k] = _fecha(detalle[k])
    fuente_url = p.get("fuente_url") if url_valida(p.get("fuente_url") or "") else None
    datos = dict(titulo=str(p.get("titulo") or "")[:200], resumen=str(p.get("resumen") or "")[:400],
                 contenido=limpiar_html(p.get("contenido") or ""), fecha_limite=_fecha(p.get("fecha_limite")),
                 vigencia=p.get("vigencia") if p.get("vigencia") in ("abierta", "cerrada", "por_confirmar") else None,
                 fuente_url=fuente_url)
    if not datos["titulo"]:
        return {"clave": clave, "estado": "rechazada", "motivo": "sin título"}

    a = Articulo.query.filter_by(clave_externa=clave).first()
    if a is not None and a.estado in ("publicado", "archivado"):
        v = proponer_actualizacion(a, dict(datos, detalle=detalle, enlaces=enlaces), None)
        return {"clave": clave, "estado": "propuesta" if v else "sin_cambios", "id": a.id}

    inst = None
    if p.get("institucion") and p["institucion"].get("nombre"):
        inst = buscar_o_crear_institucion(str(p["institucion"]["nombre"])[:200], p["institucion"].get("sector"),
                                          verificada=False)
    nueva = a is None
    if nueva:
        cat = Categoria.query.filter_by(slug=p.get("categoria") or "").first() or \
            Categoria.query.filter_by(slug=TIPOS[tipo]["categoria"] or "").first() or Categoria.query.first()
        a = Articulo(tipo=tipo, clave_externa=clave, origen="autopilot", autor_id=servicio.id, categoria=cat,
                     slug=slug_unico_modelo(Articulo, datos["titulo"], reservados=RUTAS_RESERVADAS), creado=ahora())
        db.session.add(a)
    a.titulo, a.resumen, a.contenido = datos["titulo"], datos["resumen"], datos["contenido"]
    a.fecha_limite, a.vigencia, a.fuente_url = datos["fecha_limite"], datos["vigencia"], fuente_url
    a.fuente_nombre = str(p.get("fuente_nombre") or "")[:150] or None
    a.verificado_en = _fecha(p.get("verificado_en"))
    a.notas_internas = str(p.get("notas") or "")[:3000] or None
    a.institucion = inst
    a.ubicacion = Ubicacion.query.filter_by(slug=p.get("ubicacion") or "").first()
    d = a.asegurar_detalle()
    if d is not None:
        for k, v in detalle.items():
            if hasattr(d, k) and k != "articulo_id":
                setattr(d, k, Decimal(str(v)) if k in ("sueldo_min", "sueldo_max") and v is not None else v)
    a.enlaces = [Enlace(tipo=t, etiqueta=e, url=u, orden=i) for i, (t, e, u) in enumerate(enlaces)]
    a.editado_por_id, a.actualizado = servicio.id, ahora()

    # Solo se publica si la política DEL SERVIDOR lo permite y pasa las validaciones del CMS
    from autopilot.calidad import NUNCA_AUTOPUBLICAR
    quiere_publicar = p.get("estado") == "publicado"
    permitido = (quiere_publicar and cfg["modo"] in ("B", "C") and cfg["politica_completa"]
                 and tipo in cfg["tipos_auto"] and tipo not in NUNCA_AUTOPUBLICAR and not a.vencida)
    errores = validar_publicacion(tipo, dict(resumen=a.resumen, contenido=a.contenido, fuente_url=a.fuente_url),
                                  detalle, [dict(url=u, archivo=None, pdf=None) for _t, _e, u in enlaces], inst) \
        if permitido else []
    if permitido and not errores:
        a.estado = "publicado"
        a.fecha_publicacion = max(_fecha_hora(p.get("fecha_publicacion")) or ahora(), ahora())
        a.aprobado_por_id = a.publicado_por_id = servicio.id
    else:
        a.estado, a.fecha_publicacion = "revision", None
    db.session.flush()
    actualizar_busqueda(a)
    return {"clave": clave, "estado": a.estado, "id": a.id,
            "motivo": "; ".join(errores) or (None if a.estado == "publicado" or not quiere_publicar
                                            else "la política del servidor no permite publicar automáticamente")}


@api_sync.route("/recibir", methods=["POST"])
@exento_csrf
def recibir():
    secreto = token()
    if not secreto:
        abort(404)   # desactivado si el servidor no tiene AUTOPILOT_TOKEN
    cuerpo = request.get_data(cache=False)
    if len(cuerpo) > 5 * 1024 * 1024:
        abort(413)
    marca = request.headers.get("X-Autopilot-Fecha", "")
    firma = request.headers.get("X-Autopilot-Firma", "")
    try:
        desfase = abs(time.time() - int(marca))
    except ValueError:
        abort(403)
    if desfase > TOLERANCIA or not hmac.compare_digest(firmar(cuerpo, marca, secreto), firma):
        abort(403)
    try:
        datos = json.loads(cuerpo)
    except ValueError:
        abort(400)
    publicaciones = datos.get("publicaciones") if isinstance(datos, dict) else None
    if not isinstance(publicaciones, list) or len(publicaciones) > LIMITE_LOTE:
        abort(400)
    from autopilot.calidad import configuracion
    from autopilot.publicador import usuario_servicio
    servicio, cfg = usuario_servicio(), configuracion()
    resultados = []
    for p in publicaciones:
        if not isinstance(p, dict):
            continue
        try:
            with db.session.begin_nested():
                resultados.append(_recibir_una(p, servicio, cfg))
        except (ValueError, TypeError, KeyError) as e:
            resultados.append({"clave": str(p.get("clave"))[:80], "estado": "rechazada", "motivo": str(e)[:200]})
    db.session.add(Registro(usuario_id=servicio.id, accion="autopilot_sincronizacion",
                            detalle=f"{len(resultados)} ficha(s) recibidas"))
    db.session.commit()
    return jsonify({"resultados": resultados})

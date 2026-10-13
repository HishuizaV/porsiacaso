"""Panel del Autopilot: control de jornadas, fuentes, bandeja de revisión, hallazgos,
actualizaciones propuestas e historial. Las cifras salen de la base de datos."""
import json
import os
from datetime import datetime, timedelta

from flask import render_template, request, redirect, url_for, flash, abort, current_app, jsonify
from flask_login import current_user
from sqlalchemy import func

import ajustes
from admin import admin, solo_admin, solo_publicadores, bitacora
from extensions import db
from models import Articulo, Institucion, Ubicacion, ahora, hoy
from tipos import TIPOS, ORDEN
from utils import url_valida
from autopilot import calidad
from autopilot.modelos import (Fuente, Hallazgo, Evidencia, Ejecucion, Tarea, DecisionEditorial, VersionArticulo,
                               Verificacion, FORMATOS, CONFIANZA, ESTADOS_FUENTE)
from autopilot.motor import jornada_activa, lanzar_en_segundo_plano

RAIZ = os.path.dirname(os.path.abspath(__file__))


def lanzar_permitido():
    valor = os.environ.get("AUTOPILOT_LANZAR_DESDE_PANEL")
    if valor is None:
        return not current_app.config.get("PRODUCCION")
    return valor == "1"


def resumen_estado():
    ej = Ejecucion.query.order_by(Ejecucion.id.desc()).first()
    activa = ej is not None and ej.activa and (ej.estado == "solicitada" or jornada_activa())
    restante = None
    if ej is not None and ej.estado in ("en_curso", "pausada") and ej.iniciada:
        restante = max(0, round(ej.duracion_max - ej.minutos_transcurridos, 1))
    autop = Articulo.query.filter_by(origen="autopilot")
    return {
        "ejecucion": ej, "activa": activa, "restante": restante,
        "hallazgos": Hallazgo.query.count(),
        "hallazgos_hoy": Hallazgo.query.filter(Hallazgo.descubierto >= datetime.combine(hoy(), datetime.min.time())).count(),
        "duplicados": Hallazgo.query.filter(Hallazgo.estado.in_(("duplicado", "actualizacion"))).count(),
        "descartados": Hallazgo.query.filter_by(estado="descartado").count(),
        "borradores": autop.filter(Articulo.estado.in_(("borrador", "revision"))).count(),
        "pendientes_revision": Articulo.query.filter_by(estado="revision").count(),
        "aprobadas": DecisionEditorial.query.filter_by(decision="aprobado").count(),
        "programadas": autop.filter(Articulo.estado == "publicado", Articulo.fecha_publicacion > ahora()).count(),
        "publicadas": autop.filter(Articulo.estado == "publicado", Articulo.fecha_publicacion <= ahora()).count(),
        "tareas_pendientes": Tarea.query.filter_by(estado="pendiente").count(),
        "errores": Tarea.query.filter_by(estado="fallida").count(),
        "fuentes_problema": Fuente.query.filter((Fuente.estado == "error") | (Fuente.errores_consecutivos > 0)).all(),
        "actualizaciones": VersionArticulo.query.filter_by(estado="pendiente").count(),
    }


# ---------- Panel principal ----------
@admin.route("/autopilot")
def autopilot():
    solo_publicadores()
    cfg = calidad.configuracion()
    regiones = Ubicacion.query.filter_by(tipo="region").order_by(Ubicacion.nombre).all()
    return render_template("admin/autopilot/panel.html", e=resumen_estado(), cfg=cfg, orden=ORDEN, regiones=regiones,
                           requisitos=calidad.REQUISITOS_POLITICA, nunca=calidad.NUNCA_AUTOPUBLICAR,
                           lanzar=lanzar_permitido(),
                           historial=Ejecucion.query.order_by(Ejecucion.id.desc()).limit(5).all())


@admin.route("/autopilot/estado.json")
def autopilot_estado_json():
    solo_publicadores()
    e = resumen_estado()
    ej = e["ejecucion"]
    return jsonify({
        "activa": e["activa"], "restante": e["restante"],
        "ejecucion": None if ej is None else {
            "id": ej.id, "estado": ej.estado, "etapa": ej.etapa, "solicitud": ej.solicitud,
            "minutos": ej.minutos_transcurridos, "duracion": ej.duracion_max, "contadores": ej.contadores},
        "cifras": {k: e[k] for k in ("hallazgos", "duplicados", "borradores", "pendientes_revision", "programadas",
                                      "tareas_pendientes", "errores", "actualizaciones")},
    })


@admin.route("/autopilot/iniciar", methods=["POST"])
def autopilot_iniciar():
    solo_admin()
    if resumen_estado()["activa"]:
        flash("Ya hay una jornada en curso o solicitada.", "error")
        return redirect(url_for("admin.autopilot"))
    f = request.form
    cfg = calidad.configuracion()
    minutos = max(10, min(120, f.get("duracion", type=int) or cfg["duracion"]))
    objetivo = max(1, min(30, f.get("objetivo", type=int) or cfg["objetivo"]))
    tipos = [t for t in f.getlist("tipos") if t in TIPOS]
    regiones = [r for r in f.getlist("regiones") if Ubicacion.query.filter_by(slug=r, tipo="region").first()]
    ej = Ejecucion(estado="solicitada", origen="panel", duracion_max=minutos, objetivo=objetivo,
                   tipos_json=json.dumps(tipos), regiones_json=json.dumps(regiones), usuario_id=current_user.id)
    db.session.add(ej)
    db.session.flush()
    bitacora("autopilot_jornada_solicitada", f"#{ej.id} {minutos} min, meta {objetivo}")
    db.session.commit()
    if lanzar_permitido():
        try:
            lanzar_en_segundo_plano(ej.id, RAIZ)
            flash(f"Jornada #{ej.id} iniciada: trabajará como máximo {minutos} minutos y se cerrará sola.", "ok")
        except OSError as e:
            ej.estado, ej.error = "fallida", f"No se pudo iniciar el proceso: {e}"
            db.session.commit()
            flash("No se pudo iniciar el proceso del Autopilot en este equipo.", "error")
    else:
        flash(f"Jornada #{ej.id} registrada. En este servidor se ejecuta con el comando: "
              f"flask autopilot jornada --ejecucion {ej.id}", "aviso")
    return redirect(url_for("admin.autopilot"))


@admin.route("/autopilot/control", methods=["POST"])
def autopilot_control():
    solo_admin()
    accion = request.form.get("accion")
    ej = Ejecucion.query.filter(Ejecucion.estado.in_(("solicitada", "en_curso", "pausada"))) \
        .order_by(Ejecucion.id.desc()).first()
    if ej is None or accion not in ("pausar", "continuar", "detener"):
        flash("No hay una jornada activa.", "error")
        return redirect(url_for("admin.autopilot"))
    if ej.estado == "solicitada" and accion == "detener":
        ej.estado, ej.finalizada = "detenida", ahora()     # aún no empezó: se cancela
    else:
        ej.solicitud = accion
    bitacora("autopilot_" + accion, f"jornada #{ej.id}")
    db.session.commit()
    flash({"pausar": "Pausa solicitada: se aplicará al terminar la tarea actual.",
           "continuar": "La jornada continuará.",
           "detener": "Detención solicitada: termina la tarea actual, guarda y se cierra."}[accion], "ok")
    return redirect(url_for("admin.autopilot"))


@admin.route("/autopilot/ajustes", methods=["POST"])
def autopilot_ajustes():
    solo_admin()
    f = request.form
    modo = f.get("modo") if f.get("modo") in ("A", "B", "C") else "A"
    politica = {k: (f"{current_user.nombre} · {ahora():%d/%m/%Y %H:%M}" if f.get("pol_" + k) else "")
                for k, _t in calidad.REQUISITOS_POLITICA}
    if modo != "A" and not all(politica.values()):
        flash("Para activar la autopublicación (modo B o C) marca todos los requisitos de la lista. "
              "Se mantiene el modo A (solo borradores).", "error")
        modo = "A"
    valores = {
        "autopilot_modo": modo,
        "autopilot_duracion": str(max(10, min(120, f.get("duracion", type=int) or 120))),
        "autopilot_objetivo": str(max(1, min(30, f.get("objetivo", type=int) or 12))),
        "autopilot_espaciado": str(max(0, min(240, f.get("espaciado", type=int) or 0))),
        "autopilot_concurrencia": str(max(1, min(4, f.get("concurrencia", type=int) or 2))),
        "autopilot_tipos": ",".join(t for t in f.getlist("tipos") if t in TIPOS),
        "autopilot_regiones": ",".join(r for r in f.getlist("regiones")
                                       if Ubicacion.query.filter_by(slug=r, tipo="region").first()),
        "autopilot_tipos_auto": ",".join(t for t in f.getlist("tipos_auto")
                                         if t in TIPOS and t not in calidad.NUNCA_AUTOPUBLICAR),
        "autopilot_ia": "1" if f.get("ia") else "0",
        "autopilot_ia_modelo": (f.get("ia_modelo") or "llama3.2:3b").strip()[:60],
        "autopilot_politica": json.dumps(politica, ensure_ascii=False),
    }
    ajustes.guardar(valores)
    bitacora("autopilot_configuracion", f"modo={modo} tipos_auto={valores['autopilot_tipos_auto']}")
    db.session.commit()
    flash("Configuración del Autopilot guardada.", "ok")
    return redirect(url_for("admin.autopilot"))


# ---------- Fuentes ----------
@admin.route("/autopilot/fuentes")
def autopilot_fuentes():
    solo_admin()
    return render_template("admin/autopilot/fuentes.html",
                           fuentes=Fuente.query.order_by(Fuente.prioridad, Fuente.nombre).all(),
                           estados=dict(ESTADOS_FUENTE), formatos=dict(FORMATOS))


@admin.route("/autopilot/fuentes/nueva", methods=["GET", "POST"])
@admin.route("/autopilot/fuentes/<int:id>", methods=["GET", "POST"])
def autopilot_fuente_form(id=None):
    solo_admin()
    fu = db.get_or_404(Fuente, id) if id else None
    if request.method == "POST":
        f = request.form
        errores = []
        datos = dict(nombre=f.get("nombre", "").strip()[:150], url_principal=f.get("url_principal", "").strip(),
                     url_listado=f.get("url_listado", "").strip() or None,
                     tipo_contenido=f.get("tipo_contenido") if f.get("tipo_contenido") in TIPOS else "empleo",
                     formato=f.get("formato") if f.get("formato") in dict(FORMATOS) else "html",
                     frecuencia_horas=max(1, min(720, f.get("frecuencia_horas", type=int) or 24)),
                     prioridad=max(1, min(5, f.get("prioridad", type=int) or 3)),
                     confianza=f.get("confianza") if f.get("confianza") in dict(CONFIANZA) else "media",
                     estado=f.get("estado") if f.get("estado") in dict(ESTADOS_FUENTE) else "pausada",
                     condiciones_acceso=f.get("condiciones_acceso", "").strip()[:3000] or None,
                     permite_extraccion=bool(f.get("permite_extraccion")),
                     permite_autopublicacion=bool(f.get("permite_autopublicacion")),
                     observaciones=f.get("observaciones", "").strip()[:3000] or None)
        if not datos["nombre"]:
            errores.append("El nombre es obligatorio.")
        for campo in ("url_principal", "url_listado"):
            if datos[campo] and not url_valida(datos[campo]):
                errores.append("Las direcciones deben ser web completas (https://…).")
                break
        if not datos["url_principal"]:
            errores.append("La URL principal es obligatoria.")
        if datos["permite_autopublicacion"] and not datos["permite_extraccion"]:
            errores.append("No se puede autorizar la autopublicación sin permiso de extracción.")
        if datos["permite_autopublicacion"] and datos["confianza"] != "alta":
            errores.append("Solo las fuentes de confianza alta pueden autopublicar.")
        cfg_texto = {}
        for clave in ("patron_enlace", "patron_id", "selector", "ruta_lista"):
            if f.get(clave, "").strip():
                cfg_texto[clave] = f[clave].strip()[:300]
        for clave in ("palabras_clave", "excluir"):
            lista = [x.strip() for x in f.get(clave, "").split(",") if x.strip()]
            if lista:
                cfg_texto[clave] = lista[:30]
        import re as _re
        for clave in ("patron_enlace", "patron_id"):
            if clave in cfg_texto:
                try:
                    _re.compile(cfg_texto[clave])
                except _re.error:
                    errores.append(f"El patrón «{clave}» no es válido.")
        if f.get("max_items", type=int):
            cfg_texto["max_items"] = max(1, min(100, f.get("max_items", type=int)))
        cfg_texto["seguir_detalle"] = not f.get("no_seguir_detalle")
        cfg_texto["leer_pdf"] = not f.get("no_leer_pdf")
        inst = db.session.get(Institucion, f.get("institucion_id", type=int) or 0)
        zona = db.session.get(Ubicacion, f.get("ubicacion_id", type=int) or 0)
        if errores:
            for e in errores:
                flash(e, "error")
        else:
            nueva = fu is None
            if nueva:
                fu = Fuente()
                db.session.add(fu)
            for k, v in datos.items():
                setattr(fu, k, v)
            fu.institucion, fu.ubicacion = inst, zona
            fu.config_json = json.dumps(cfg_texto, ensure_ascii=False)
            fu.actualizado = ahora()
            if fu.estado == "activa":
                fu.errores_consecutivos = 0
            bitacora("fuente_" + ("creada" if nueva else "editada"),
                     f"{fu.nombre} · extracción={fu.permite_extraccion} autopublicación={fu.permite_autopublicacion}")
            db.session.commit()
            flash("Fuente guardada.", "ok")
            return redirect(url_for("admin.autopilot_fuentes"))
    return render_template("admin/autopilot/fuente_form.html", fu=fu, cfg=fu.config if fu else {},
                           instituciones=Institucion.query.order_by(Institucion.nombre).all(),
                           regiones=Ubicacion.query.filter_by(tipo="region").order_by(Ubicacion.nombre).all(),
                           formatos=FORMATOS, confianzas=CONFIANZA, estados=ESTADOS_FUENTE, orden=ORDEN)


@admin.route("/autopilot/fuentes/<int:id>/probar", methods=["POST"])
def autopilot_fuente_probar(id):
    """Lee el listado sin guardar nada (máx. 20 s). Sirve para comprobar la configuración."""
    solo_admin()
    fu = db.get_or_404(Fuente, id)
    from autopilot import adaptadores
    from autopilot.red import Descargador, Bloqueado, ErrorRed
    d = Descargador(timeout=20, reintentos=0)
    try:
        items, error = adaptadores.listar(fu, d), None
    except (Bloqueado, ErrorRed, ValueError) as e:
        items, error = [], str(e)
    finally:
        d.cerrar()
    return render_template("admin/autopilot/fuente_prueba.html", fu=fu, items=items, error=error)


# ---------- Bandeja de revisión ----------
@admin.route("/autopilot/bandeja")
def autopilot_bandeja():
    solo_publicadores()
    origen = request.args.get("origen", "")
    q = Articulo.query.filter(Articulo.estado == "revision")
    if origen in ("autopilot", "manual"):
        q = q.filter(Articulo.origen == origen)
    articulos = q.order_by(Articulo.fecha_limite.is_(None), Articulo.fecha_limite, Articulo.creado.desc()).limit(60).all()
    fichas = []
    for a in articulos:
        h = Hallazgo.query.filter_by(articulo_id=a.id).order_by(Hallazgo.id.desc()).first()
        dec = DecisionEditorial.query.filter_by(articulo_id=a.id).order_by(DecisionEditorial.id.desc()).first()
        faltan = [c["etiqueta"] for _t, cs in TIPOS[a.tipo]["campos"] for c in cs
                  if c["requerido"] and (a.detalle is None or getattr(a.detalle, c["nombre"]) in (None, ""))]
        if a.es_oportunidad and not a.fecha_limite:
            faltan.append("Fecha límite")
        fichas.append(dict(a=a, h=h, dec=dec, faltan=faltan))
    return render_template("admin/autopilot/bandeja.html", fichas=fichas, origen=origen, hoy=hoy())


@admin.route("/autopilot/bandeja/<int:id>", methods=["POST"])
def autopilot_bandeja_accion(id):
    solo_publicadores()
    from admin_contenido import validar_publicacion
    from consultas import actualizar_busqueda
    a = db.get_or_404(Articulo, id)
    accion = request.form.get("accion")
    h = Hallazgo.query.filter_by(articulo_id=a.id).first()

    if accion == "corregir":
        titulo = request.form.get("titulo", "").strip()[:200]
        resumen = request.form.get("resumen", "").strip()[:400]
        fl = request.form.get("fecha_limite", "").strip()
        if not titulo:
            flash("El título no puede quedar vacío.", "error")
            return redirect(url_for("admin.autopilot_bandeja"))
        a.titulo, a.resumen = titulo, resumen
        try:
            a.fecha_limite = datetime.strptime(fl, "%Y-%m-%d").date() if fl else None
        except ValueError:
            flash("La fecha límite no es válida.", "error")
            return redirect(url_for("admin.autopilot_bandeja"))
        if a.fecha_limite and not a.vigencia:
            a.vigencia = "abierta"
        a.editado_por_id, a.actualizado = current_user.id, ahora()
        actualizar_busqueda(a)
        bitacora("bandeja_corregida", f"#{a.id} {a.titulo}")
        db.session.commit()
        flash("Corrección guardada.", "ok")
        return redirect(url_for("admin.autopilot_bandeja") + f"#ficha-{a.id}")

    if accion == "rechazar":
        motivo = request.form.get("motivo", "").strip()[:500] or "Rechazada en la bandeja de revisión"
        a.estado = "archivado" if a.fecha_publicacion else "borrador"
        a.notas_internas = ((a.notas_internas or "") + f"\nRechazada por {current_user.nombre}: {motivo}")[:3000]
        if h is not None:
            h.estado, h.motivo = "descartado", motivo
        db.session.add(DecisionEditorial(articulo_id=a.id, hallazgo_id=h.id if h else None, decision="rechazado",
                                         motivo=motivo, actor="humano", usuario_id=current_user.id))
        bitacora("bandeja_rechazada", f"#{a.id} {a.titulo}")
        db.session.commit()
        flash("Ficha rechazada: no se publicará.", "ok")
        return redirect(url_for("admin.autopilot_bandeja"))

    if accion in ("aprobar", "programar"):
        if a.vencida:
            flash("No se puede publicar: la fecha límite ya pasó.", "error")
            return redirect(url_for("admin.autopilot_bandeja"))
        det = {c["nombre"]: getattr(a.detalle, c["nombre"]) for _t, cs in TIPOS[a.tipo]["campos"] for c in cs} \
            if a.detalle else {}
        errores = validar_publicacion(a.tipo, dict(resumen=a.resumen, contenido=a.contenido, fuente_url=a.fuente_url),
                                      det, [dict(url=e.url, archivo=e.archivo, pdf=None) for e in a.enlaces],
                                      a.institucion)
        if errores:
            for e in errores:
                flash(e, "error")
            flash("Completa lo indicado con «Editar» antes de aprobar.", "error")
            return redirect(url_for("admin.autopilot_bandeja") + f"#ficha-{a.id}")
        cuando = ahora()
        if accion == "programar":
            try:
                cuando = datetime.fromisoformat(request.form.get("cuando", ""))
            except ValueError:
                flash("Elige la fecha y hora de publicación.", "error")
                return redirect(url_for("admin.autopilot_bandeja"))
            if cuando <= ahora():
                flash("La fecha programada debe ser futura.", "error")
                return redirect(url_for("admin.autopilot_bandeja"))
        a.estado, a.fecha_publicacion = "publicado", cuando
        a.aprobado_por_id = a.publicado_por_id = current_user.id
        a.actualizado = ahora()
        db.session.add(DecisionEditorial(articulo_id=a.id, hallazgo_id=h.id if h else None,
                                         decision="programado" if accion == "programar" else "aprobado",
                                         actor="humano", usuario_id=current_user.id))
        bitacora("bandeja_" + accion, f"#{a.id} {a.titulo}")
        db.session.commit()
        flash("Publicada." if accion == "aprobar" else f"Programada para el {cuando:%d/%m/%Y %H:%M}.", "ok")
        return redirect(url_for("admin.autopilot_bandeja"))
    abort(400)


# ---------- Hallazgos y evidencias ----------
@admin.route("/autopilot/hallazgos")
def autopilot_hallazgos():
    solo_publicadores()
    estado = request.args.get("estado", "")
    q = Hallazgo.query
    if estado:
        q = q.filter_by(estado=estado)
    pag = q.order_by(Hallazgo.id.desc()).paginate(page=request.args.get("page", 1, type=int), per_page=40,
                                                  error_out=False)
    conteo = dict(db.session.query(Hallazgo.estado, func.count(Hallazgo.id)).group_by(Hallazgo.estado).all())
    return render_template("admin/autopilot/hallazgos.html", pag=pag, estado=estado, conteo=conteo)


@admin.route("/autopilot/hallazgos/<int:id>")
def autopilot_hallazgo(id):
    solo_publicadores()
    h = db.get_or_404(Hallazgo, id)
    return render_template("admin/autopilot/hallazgo.html", h=h,
                           evidencias=Evidencia.query.filter_by(hallazgo_id=h.id).order_by(Evidencia.id).all(),
                           decisiones=DecisionEditorial.query.filter_by(hallazgo_id=h.id).all())


# ---------- Actualizaciones propuestas y versiones ----------
@admin.route("/autopilot/actualizaciones")
def autopilot_actualizaciones():
    solo_publicadores()
    pendientes = VersionArticulo.query.filter_by(estado="pendiente").order_by(VersionArticulo.fecha).all()
    recientes = VersionArticulo.query.filter(VersionArticulo.estado.in_(("aplicada", "revertida", "rechazada"))) \
        .order_by(VersionArticulo.id.desc()).limit(30).all()
    verificaciones = Verificacion.query.filter_by(resultado="error").order_by(Verificacion.id.desc()).limit(20).all()
    return render_template("admin/autopilot/actualizaciones.html", pendientes=pendientes, recientes=recientes,
                           verificaciones=verificaciones)


@admin.route("/autopilot/actualizaciones/<int:id>", methods=["POST"])
def autopilot_version_accion(id):
    solo_publicadores()
    from autopilot.publicador import aplicar_version, revertir_version
    v = db.get_or_404(VersionArticulo, id)
    accion = request.form.get("accion")
    if accion == "aplicar" and v.estado == "pendiente":
        aplicar_version(v, current_user)
        flash("Cambio aplicado. Puedes revertirlo desde esta misma página.", "ok")
    elif accion == "rechazar" and v.estado == "pendiente":
        v.estado, v.usuario_id = "rechazada", current_user.id
        flash("Propuesta rechazada.", "ok")
    elif accion == "revertir" and v.estado == "aplicada":
        revertir_version(v, current_user)
        flash("Cambio revertido.", "ok")
    else:
        abort(400)
    db.session.commit()
    return redirect(url_for("admin.autopilot_actualizaciones"))


# ---------- Historial ----------
@admin.route("/autopilot/historial")
def autopilot_historial():
    solo_publicadores()
    return render_template("admin/autopilot/historial.html",
                           ejecuciones=Ejecucion.query.order_by(Ejecucion.id.desc()).limit(60).all())


@admin.route("/autopilot/historial/<int:id>")
def autopilot_ejecucion(id):
    solo_publicadores()
    ej = db.get_or_404(Ejecucion, id)
    tareas = Tarea.query.filter_by(ejecucion_id=ej.id, estado="fallida").limit(50).all()
    return render_template("admin/autopilot/ejecucion.html", ej=ej, fallidas=tareas)


__all__ = ["timedelta"]

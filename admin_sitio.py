"""Panel: instituciones, configuración del sitio y bitácora."""
import os
import re

from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import current_user

import ajustes
from admin import admin, solo_admin, bitacora, slug_unico_modelo
from extensions import db
from models import Institucion, Registro, Articulo
from autopilot.modelos import PropuestaInstitucion, Fuente
from tipos import SECTORES
from utils import url_valida, guardar_logo, borrar_archivo


# ---------- Instituciones ----------
@admin.route("/instituciones")
def instituciones():
    lista = Institucion.query.order_by(Institucion.verificada, Institucion.nombre).all()
    propuestas = PropuestaInstitucion.query.filter_by(estado="pendiente") \
        .order_by(PropuestaInstitucion.fecha).all() if current_user.es_admin else []
    return render_template("admin/instituciones.html", instituciones=lista, sectores=dict(SECTORES),
                           propuestas=propuestas)


@admin.route("/instituciones/<int:id>/proponer", methods=["POST"])
def institucion_proponer(id):
    """Los editores no modifican datos compartidos: proponen la corrección a un administrador."""
    i = db.get_or_404(Institucion, id)
    texto = request.form.get("texto", "").strip()[:2000]
    if len(texto) < 5:
        flash("Describe la corrección que propones.", "error")
    else:
        db.session.add(PropuestaInstitucion(institucion_id=i.id, usuario_id=current_user.id, texto=texto))
        bitacora("institucion_propuesta", i.nombre)
        db.session.commit()
        flash("Propuesta enviada. Un administrador la revisará.", "ok")
    return redirect(url_for("admin.instituciones"))


@admin.route("/instituciones/propuestas/<int:id>", methods=["POST"])
def institucion_propuesta_resolver(id):
    solo_admin()
    pr = db.get_or_404(PropuestaInstitucion, id)
    pr.estado = "aplicada" if request.form.get("resultado") == "aplicada" else "rechazada"
    bitacora("institucion_propuesta_" + pr.estado, pr.institucion.nombre)
    db.session.commit()
    flash("Propuesta marcada como " + pr.estado + ". Si la aplicaste, edita la institución.", "ok")
    return redirect(url_for("admin.instituciones"))


@admin.route("/instituciones/<int:id>/verificar", methods=["POST"])
def institucion_verificar(id):
    solo_admin()
    i = db.get_or_404(Institucion, id)
    i.verificada = True
    bitacora("institucion_verificada", i.nombre)
    db.session.commit()
    flash("Institución verificada.", "ok")
    return redirect(url_for("admin.instituciones"))


@admin.route("/instituciones/<int:id>/fusionar", methods=["POST"])
def institucion_fusionar(id):
    """Une una institución duplicada con otra: mueve publicaciones y fuentes y borra la duplicada."""
    solo_admin()
    origen = db.get_or_404(Institucion, id)
    destino = db.session.get(Institucion, request.form.get("destino_id", type=int) or 0)
    if not destino or destino.id == origen.id:
        flash("Elige otra institución como destino.", "error")
        return redirect(url_for("admin.instituciones"))
    Articulo.query.filter_by(institucion_id=origen.id).update({"institucion_id": destino.id})
    Fuente.query.filter_by(institucion_id=origen.id).update({"institucion_id": destino.id})
    PropuestaInstitucion.query.filter_by(institucion_id=origen.id).update({"institucion_id": destino.id})
    bitacora("institucion_fusionada", f"{origen.nombre} → {destino.nombre}")
    if origen.logo and not destino.logo:
        destino.logo, origen.logo = origen.logo, None
    db.session.delete(origen)
    db.session.commit()
    flash(f"«{origen.nombre}» se unió a «{destino.nombre}».", "ok")
    return redirect(url_for("admin.instituciones"))


@admin.route("/instituciones/nueva", methods=["GET", "POST"])
@admin.route("/instituciones/<int:id>/editar", methods=["GET", "POST"])
def institucion_form(id=None):
    solo_admin()   # datos compartidos: solo administradores
    i = db.get_or_404(Institucion, id) if id else None
    v = dict(nombre=i.nombre, siglas=i.siglas or "", sector=i.sector or "", web=i.web or "",
             descripcion=i.descripcion or "") if i else \
        dict(nombre="", siglas="", sector="", web="", descripcion="")
    if request.method == "POST":
        f = request.form
        v = dict(nombre=f.get("nombre", "").strip()[:200], siglas=f.get("siglas", "").strip()[:40],
                 sector=f.get("sector", "") if f.get("sector") in dict(SECTORES) else "",
                 web=f.get("web", "").strip(), descripcion=f.get("descripcion", "").strip()[:2000])
        errores = []
        if not v["nombre"]:
            errores.append("El nombre es obligatorio.")
        if v["web"] and not url_valida(v["web"]):
            errores.append("La web oficial debe ser una dirección válida (https://…).")
        logo = None
        archivo = request.files.get("logo")
        if not errores and archivo and archivo.filename:
            logo = guardar_logo(archivo.stream, os.path.join(current_app.config["UPLOAD_FOLDER"], "logos"))
            if not logo:
                errores.append("El logo no es una imagen válida.")
        if errores:
            for e in errores:
                flash(e, "error")
        else:
            if not i:
                i = Institucion(slug=slug_unico_modelo(Institucion, v["nombre"]), verificada=True)
                db.session.add(i)
            i.nombre, i.siglas, i.sector = v["nombre"], v["siglas"] or None, v["sector"] or None
            i.web, i.descripcion = v["web"] or None, v["descripcion"] or None
            if logo:
                if i.logo:
                    borrar_archivo(os.path.join(current_app.config["UPLOAD_FOLDER"], "logos"), i.logo)
                i.logo = logo
            bitacora("institucion_guardada", i.nombre)
            db.session.commit()
            flash("Institución guardada.", "ok")
            return redirect(url_for("admin.instituciones"))
    return render_template("admin/institucion_form.html", i=i, v=v, sectores=SECTORES)


@admin.route("/instituciones/<int:id>/eliminar", methods=["POST"])
def institucion_eliminar(id):
    solo_admin()
    i = db.get_or_404(Institucion, id)
    if i.articulos:
        flash(f"No se puede eliminar: tiene {len(i.articulos)} publicación(es).", "error")
    else:
        if i.logo:
            borrar_archivo(os.path.join(current_app.config["UPLOAD_FOLDER"], "logos"), i.logo)
        bitacora("institucion_eliminada", i.nombre)
        db.session.delete(i)
        db.session.commit()
        flash("Institución eliminada.", "ok")
    return redirect(url_for("admin.instituciones"))


# ---------- Configuración del sitio ----------
REDES = ("facebook_url", "instagram_url", "tiktok_url", "youtube_url")


@admin.route("/configuracion", methods=["GET", "POST"])
def configuracion():
    solo_admin()
    valores = ajustes.todos()
    if request.method == "POST":
        f = request.form
        nuevos = {k: f.get(k, "").strip() for k in ajustes.CLAVES_SITIO}
        nuevos["asistente_activo"] = "1" if f.get("asistente_activo") else "0"
        errores = []
        if nuevos["anuncios_modo"] not in ("off", "maqueta", "adsense"):
            errores.append("Modo de publicidad no válido.")
        if nuevos["adsense_cliente"] and not ajustes.RE_CLIENTE.match(nuevos["adsense_cliente"]):
            errores.append("El ID de editor de AdSense tiene el formato ca-pub- seguido de 16 números.")
        if nuevos["anuncios_modo"] == "adsense" and not nuevos["adsense_cliente"]:
            errores.append("Para activar AdSense necesitas el ID de editor que te da Google "
                           "después de aprobar tu sitio.")
        for k in ("adsense_slot_superior", "adsense_slot_articulo", "adsense_slot_lateral"):
            if nuevos[k] and not ajustes.RE_SLOT.match(nuevos[k]):
                errores.append("Los ID de bloque de anuncio son solo números.")
                break
        for k in REDES:
            if nuevos[k] and not url_valida(nuevos[k]):
                errores.append("Los enlaces de redes sociales deben ser direcciones completas (https://…).")
                break
        if nuevos["contacto_email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}",
                                                         nuevos["contacto_email"]):
            errores.append("El correo de contacto no es válido.")
        if nuevos["google_verificacion"] and not re.fullmatch(r"[A-Za-z0-9_\-]{10,100}",
                                                              nuevos["google_verificacion"]):
            errores.append("Pega solo el código de verificación (lo que va dentro de content=\"…\").")
        lineas_ads = [x for x in nuevos["ads_txt"].splitlines() if x.strip() and not x.strip().startswith("#")]
        if any(len(x.split(",")) < 3 for x in lineas_ads):
            errores.append("Cada línea de ads.txt debe tener al menos 3 campos separados por comas, "
                           "tal como te lo indica AdSense.")
        if errores:
            for e in errores:
                flash(e, "error")
            valores = nuevos
        else:
            ajustes.guardar(nuevos)
            bitacora("configuracion", f"publicidad={nuevos['anuncios_modo']}, "
                                      f"asistente={nuevos['asistente_activo']}")
            db.session.commit()
            flash("Configuración guardada.", "ok")
            return redirect(url_for("admin.configuracion"))
    return render_template("admin/configuracion.html", v=valores)


# ---------- Bitácora ----------
@admin.route("/registros")
def registros():
    solo_admin()
    pag = Registro.query.order_by(Registro.fecha.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False)
    return render_template("admin/registros.html", pag=pag)

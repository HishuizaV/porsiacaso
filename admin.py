import os
import time
import secrets
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, abort, current_app)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import Usuario, Categoria, Ubicacion, Articulo, Pagina
from utils import slugify, limpiar_html, minutos_lectura, guardar_imagen

admin = Blueprint("admin", __name__, url_prefix="/admin")

# Límite de intentos de login: 5 fallos => bloqueo de 10 minutos
INTENTOS = {}
MAX_INTENTOS = 5
BLOQUEO_SEG = 600


# ---------- Seguridad CSRF ----------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@admin.app_context_processor
def inyectar_csrf():
    return {"csrf_token": csrf_token}


@admin.before_request
def verificar_csrf():
    if request.method == "POST":
        token = session.get("_csrf")
        enviado = request.form.get("_csrf", "")
        if not token or not secrets.compare_digest(token, enviado):
            abort(400)


# ---------- Ayudas ----------
def solo_admin():
    if not current_user.es_admin:
        abort(403)


def puede_editar(a):
    return current_user.es_admin or a.autor_id == current_user.id


def slug_unico_modelo(modelo, texto, alternativa=None):
    """Devuelve un slug que no exista aún en el modelo."""
    candidatos = [slugify(texto)]
    if alternativa:
        candidatos.append(slugify(alternativa))
    for base in candidatos:
        if not modelo.query.filter_by(slug=base).first():
            return base
    base, n = candidatos[-1], 2
    while modelo.query.filter_by(slug=f"{base}-{n}").first():
        n += 1
    return f"{base}-{n}"


def borrar_imagen(nombre):
    if nombre:
        ruta = os.path.join(current_app.config["UPLOAD_FOLDER"], nombre)
        if os.path.exists(ruta):
            os.remove(ruta)


def regiones_con_ciudades():
    return Ubicacion.query.filter_by(tipo="region").order_by(Ubicacion.nombre).all()


def valores(a):
    if a:
        return dict(titulo=a.titulo, resumen=a.resumen or "", contenido=a.contenido,
                    categoria_id=a.categoria_id, ubicacion_id=a.ubicacion_id,
                    datos_texto=a.datos_texto or "", fuente_url=a.fuente_url or "",
                    estado=a.estado, destacado=a.destacado,
                    imagen_alt=a.imagen_alt or "", imagen_credito=a.imagen_credito or "")
    return dict(titulo="", resumen="", contenido="", categoria_id=None, ubicacion_id=None,
                datos_texto="", fuente_url="", estado="borrador", destacado=False,
                imagen_alt="", imagen_credito="")


# ---------- Login ----------
@admin.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.panel"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        clave = f"{request.remote_addr}|{email}"
        intentos, bloqueado_hasta = INTENTOS.get(clave, [0, 0])

        if bloqueado_hasta > time.time():
            flash("Demasiados intentos fallidos. Espera 10 minutos.", "error")
        else:
            u = Usuario.query.filter_by(email=email).first()
            if u and u.activo and u.check_password(request.form.get("password", "")):
                INTENTOS.pop(clave, None)
                login_user(u)
                return redirect(url_for("admin.panel"))
            intentos += 1
            if intentos >= MAX_INTENTOS:
                INTENTOS[clave] = [0, time.time() + BLOQUEO_SEG]
            else:
                INTENTOS[clave] = [intentos, 0]
            flash("Correo o contraseña incorrectos.", "error")
    return render_template("admin/login.html")


@admin.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("admin.login"))


# ---------- Panel de artículos ----------
@admin.route("/")
@login_required
def panel():
    q = Articulo.query
    if not current_user.es_admin:
        q = q.filter_by(autor_id=current_user.id)
    articulos = q.order_by(Articulo.creado.desc()).all()
    return render_template("admin/panel.html", articulos=articulos)


@admin.route("/articulo/nuevo", methods=["GET", "POST"])
@admin.route("/articulo/<int:id>/editar", methods=["GET", "POST"])
@login_required
def articulo_form(id=None):
    a = db.get_or_404(Articulo, id) if id else None
    if a and not puede_editar(a):
        abort(403)
    categorias = Categoria.query.order_by(Categoria.orden).all()
    v = valores(a)

    if request.method == "POST":
        f = request.form
        titulo = f.get("titulo", "").strip()
        contenido = limpiar_html(f.get("contenido", ""))
        cat_id = f.get("categoria_id", type=int)
        ubic_id = f.get("ubicacion_id", type=int)
        fuente = f.get("fuente_url", "").strip()
        archivo = request.files.get("imagen")

        v = dict(titulo=titulo, resumen=f.get("resumen", "").strip(), contenido=contenido,
                 categoria_id=cat_id, ubicacion_id=ubic_id,
                 datos_texto=f.get("datos_texto", "").strip(),
                 fuente_url=fuente, estado=f.get("estado", "borrador"),
                 destacado=bool(f.get("destacado")),
                 imagen_alt=f.get("imagen_alt", "").strip()[:200],
                 imagen_credito=f.get("imagen_credito", "").strip()[:200])

        errores = []
        if not titulo:
            errores.append("El título es obligatorio.")
        if not cat_id:
            errores.append("Elige una categoría.")
        if ubic_id and not db.session.get(Ubicacion, ubic_id):
            errores.append("La zona elegida no existe.")
        if not contenido.strip():
            errores.append("Escribe el contenido del artículo.")
        if fuente and not fuente.startswith(("http://", "https://")):
            errores.append("El enlace de la fuente debe empezar con http:// o https://")

        nombre_img = None
        if archivo and archivo.filename and not errores:
            nombre_img = guardar_imagen(archivo.stream, current_app.config["UPLOAD_FOLDER"])
            if not nombre_img:
                errores.append("La imagen no es válida (usa JPG, PNG o WEBP).")

        if errores:
            for e in errores:
                flash(e, "error")
        else:
            if not a:
                a = Articulo(autor_id=current_user.id, slug=slug_unico_modelo(Articulo, titulo))
                db.session.add(a)
            a.titulo = titulo
            a.resumen = v["resumen"]
            a.contenido = contenido
            a.categoria_id = cat_id
            a.ubicacion_id = ubic_id
            a.datos_texto = v["datos_texto"]
            a.fuente_url = fuente
            a.imagen_alt = v["imagen_alt"]
            a.imagen_credito = v["imagen_credito"]
            a.estado = "publicado" if v["estado"] == "publicado" else "borrador"
            a.lectura = minutos_lectura(contenido)
            a.actualizado = datetime.now()
            if current_user.es_admin:
                a.destacado = v["destacado"]
            if a.estado == "publicado" and not a.fecha_publicacion:
                a.fecha_publicacion = datetime.now()
            if nombre_img:
                borrar_imagen(a.imagen)
                a.imagen = nombre_img
            db.session.commit()
            flash("Artículo guardado.", "ok")
            return redirect(url_for("admin.panel"))

    return render_template("admin/articulo_form.html", a=a, v=v, categorias=categorias,
                           regiones=regiones_con_ciudades())


@admin.route("/articulo/<int:id>/vista")
@login_required
def articulo_vista(id):
    """Vista previa (sirve para borradores). Nadie más la ve ni Google la indexa."""
    a = db.get_or_404(Articulo, id)
    if not puede_editar(a):
        abort(403)
    return render_template("articulo.html", a=a, cat=a.categoria,
                           relacionados=[], vista_previa=True)


@admin.route("/articulo/<int:id>/estado", methods=["POST"])
@login_required
def articulo_estado(id):
    a = db.get_or_404(Articulo, id)
    if not puede_editar(a):
        abort(403)
    if a.estado == "publicado":
        a.estado = "borrador"
    else:
        a.estado = "publicado"
        if not a.fecha_publicacion:
            a.fecha_publicacion = datetime.now()
    db.session.commit()
    return redirect(url_for("admin.panel"))


@admin.route("/articulo/<int:id>/eliminar", methods=["POST"])
@login_required
def articulo_eliminar(id):
    a = db.get_or_404(Articulo, id)
    if not puede_editar(a):
        abort(403)
    borrar_imagen(a.imagen)
    db.session.delete(a)
    db.session.commit()
    flash("Artículo eliminado.", "ok")
    return redirect(url_for("admin.panel"))


# ---------- Categorías (solo admin) ----------
@admin.route("/categorias")
@login_required
def categorias_lista():
    solo_admin()
    lista = Categoria.query.order_by(Categoria.orden).all()
    return render_template("admin/categorias.html", categorias=lista)


@admin.route("/categorias/nueva", methods=["GET", "POST"])
@admin.route("/categorias/<int:id>/editar", methods=["GET", "POST"])
@login_required
def categoria_editar(id=None):
    solo_admin()
    c = db.get_or_404(Categoria, id) if id else None
    if c:
        v = dict(nombre=c.nombre, corto=c.corto, icono=c.icono or "",
                 descripcion=c.descripcion or "", orden=c.orden, visible=c.visible)
    else:
        siguiente = (db.session.query(db.func.max(Categoria.orden)).scalar() or 0) + 1
        v = dict(nombre="", corto="", icono="📌", descripcion="",
                 orden=siguiente, visible=True)

    if request.method == "POST":
        f = request.form
        v = dict(nombre=f.get("nombre", "").strip(), corto=f.get("corto", "").strip(),
                 icono=f.get("icono", "").strip(), descripcion=f.get("descripcion", "").strip(),
                 orden=f.get("orden", type=int) or 0, visible=bool(f.get("visible")))
        if not v["nombre"] or not v["corto"]:
            flash("El nombre y el nombre corto del menú son obligatorios.", "error")
        else:
            if not c:
                c = Categoria(slug=slug_unico_modelo(Categoria, v["nombre"]))
                db.session.add(c)
            c.nombre = v["nombre"][:80]
            c.corto = v["corto"][:40]
            c.icono = v["icono"][:10]
            c.descripcion = v["descripcion"]
            c.orden = v["orden"]
            c.visible = v["visible"]
            db.session.commit()
            flash("Categoría guardada.", "ok")
            return redirect(url_for("admin.categorias_lista"))
    return render_template("admin/categoria_form.html", c=c, v=v)


@admin.route("/categorias/<int:id>/eliminar", methods=["POST"])
@login_required
def categoria_eliminar(id):
    solo_admin()
    c = db.get_or_404(Categoria, id)
    if c.articulos:
        flash(f"No se puede eliminar: tiene {len(c.articulos)} artículo(s). "
              "Ocúltala o mueve sus artículos a otra categoría.", "error")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Categoría eliminada.", "ok")
    return redirect(url_for("admin.categorias_lista"))


# ---------- Zonas: regiones y ciudades (solo admin) ----------
@admin.route("/zonas")
@login_required
def ubicaciones_lista():
    solo_admin()
    return render_template("admin/ubicaciones.html", regiones=regiones_con_ciudades())


@admin.route("/zonas/nueva", methods=["GET", "POST"])
@admin.route("/zonas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def ubicacion_editar(id=None):
    solo_admin()
    u = db.get_or_404(Ubicacion, id) if id else None
    regiones = regiones_con_ciudades()
    if u:
        v = dict(nombre=u.nombre, tipo=u.tipo, padre_id=u.padre_id)
    else:
        v = dict(nombre="", tipo="ciudad", padre_id=None)

    if request.method == "POST":
        f = request.form
        nombre = f.get("nombre", "").strip()
        tipo = "region" if f.get("tipo") == "region" else "ciudad"
        padre_id = f.get("padre_id", type=int)
        v = dict(nombre=nombre, tipo=tipo, padre_id=padre_id)
        padre = db.session.get(Ubicacion, padre_id) if padre_id else None

        errores = []
        if not nombre:
            errores.append("El nombre es obligatorio.")
        if tipo == "ciudad":
            if not padre or padre.tipo != "region":
                errores.append("Elige la región a la que pertenece la ciudad.")
            if u and u.hijas:
                errores.append("Esta zona tiene ciudades dentro; no puede pasar a ser ciudad.")
        else:
            padre = None

        if errores:
            for e in errores:
                flash(e, "error")
        else:
            if not u:
                alternativa = f"{nombre} {padre.nombre}" if padre else None
                u = Ubicacion(slug=slug_unico_modelo(Ubicacion, nombre, alternativa))
                db.session.add(u)
            u.nombre = nombre[:80]
            u.tipo = tipo
            u.padre_id = padre.id if padre else None
            db.session.commit()
            flash("Zona guardada.", "ok")
            return redirect(url_for("admin.ubicaciones_lista"))
    return render_template("admin/ubicacion_form.html", u=u, v=v, regiones=regiones)


@admin.route("/zonas/<int:id>/eliminar", methods=["POST"])
@login_required
def ubicacion_eliminar(id):
    solo_admin()
    u = db.get_or_404(Ubicacion, id)
    if u.articulos:
        flash(f"No se puede eliminar: tiene {len(u.articulos)} artículo(s).", "error")
    elif u.hijas:
        flash("No se puede eliminar: tiene ciudades dentro. Elimina primero las ciudades.", "error")
    else:
        db.session.delete(u)
        db.session.commit()
        flash("Zona eliminada.", "ok")
    return redirect(url_for("admin.ubicaciones_lista"))


# ---------- Páginas fijas (solo admin) ----------
@admin.route("/paginas")
@login_required
def paginas():
    solo_admin()
    return render_template("admin/paginas.html",
                           paginas=Pagina.query.order_by(Pagina.id).all())


@admin.route("/paginas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def pagina_form(id):
    solo_admin()
    p = db.get_or_404(Pagina, id)
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()
        contenido = limpiar_html(request.form.get("contenido", ""))
        if not titulo or not contenido.strip():
            flash("Título y contenido son obligatorios.", "error")
        else:
            p.titulo = titulo
            p.contenido = contenido
            p.actualizado = datetime.now()
            db.session.commit()
            flash("Página actualizada.", "ok")
            return redirect(url_for("admin.paginas"))
    return render_template("admin/pagina_form.html", p=p)


# ---------- Usuarios (solo admin) ----------
@admin.route("/usuarios", methods=["GET", "POST"])
@login_required
def usuarios():
    solo_admin()
    if request.method == "POST":
        f = request.form
        nombre = f.get("nombre", "").strip()
        email = f.get("email", "").strip().lower()
        password = f.get("password", "")
        rol = "admin" if f.get("rol") == "admin" else "editor"
        if not nombre or not email or len(password) < 8:
            flash("Completa nombre, correo y una contraseña de mínimo 8 caracteres.", "error")
        elif Usuario.query.filter_by(email=email).first():
            flash("Ese correo ya está registrado.", "error")
        else:
            u = Usuario(nombre=nombre, email=email, rol=rol)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
            flash(f"Usuario {nombre} creado.", "ok")
    lista = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("admin/usuarios.html", usuarios=lista)


@admin.route("/usuarios/<int:id>/activo", methods=["POST"])
@login_required
def usuario_activo(id):
    solo_admin()
    u = db.get_or_404(Usuario, id)
    if u.id == current_user.id:
        flash("No puedes desactivar tu propia cuenta.", "error")
    else:
        u.activo = not u.activo
        db.session.commit()
    return redirect(url_for("admin.usuarios"))


# ---------- Mi cuenta ----------
@admin.route("/cuenta", methods=["GET", "POST"])
@login_required
def cuenta():
    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        if not current_user.check_password(actual):
            flash("La contraseña actual no es correcta.", "error")
        elif len(nueva) < 8:
            flash("La nueva contraseña debe tener mínimo 8 caracteres.", "error")
        else:
            current_user.set_password(nueva)
            db.session.commit()
            flash("Contraseña actualizada.", "ok")
    return render_template("admin/cuenta.html")
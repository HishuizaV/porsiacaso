import time

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, current_app)
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import Usuario, Categoria, Ubicacion, Articulo, Pagina, Registro, ahora
from tipos import RUTAS_RESERVADAS
from utils import slugify, limpiar_html, contenido_vacio

admin = Blueprint("admin", __name__, url_prefix="/admin")

# Límite de intentos de login: 5 fallos => bloqueo de 10 minutos
INTENTOS = {}
MAX_INTENTOS = 5
BLOQUEO_SEG = 600


@admin.before_request
def exigir_login():
    """Todo el panel requiere sesión, salvo la pantalla de ingreso."""
    if request.endpoint in ("admin.login",):
        return None
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()


# ---------- Ayudas ----------
def solo_admin():
    if not current_user.es_admin:
        abort(403)


def puede_editar(a):
    return current_user.es_admin or a.autor_id == current_user.id


def bitacora(accion, detalle=""):
    """Agrega una línea a la bitácora (el commit lo hace quien llama)."""
    db.session.add(Registro(usuario_id=current_user.id, accion=accion, detalle=(detalle or "")[:300]))


def slug_unico_modelo(modelo, texto, alternativa=None, reservados=()):
    """Devuelve un slug que no exista aún en el modelo."""
    candidatos = [slugify(texto)]
    if alternativa:
        candidatos.append(slugify(alternativa))
    for base in candidatos:
        if base not in reservados and not modelo.query.filter_by(slug=base).first():
            return base
    base, n = candidatos[-1], 2
    while modelo.query.filter_by(slug=f"{base}-{n}").first():
        n += 1
    return f"{base}-{n}"


def regiones_con_ciudades():
    return Ubicacion.query.filter_by(tipo="region").order_by(Ubicacion.nombre).all()


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


# ---------- Categorías (solo admin) ----------
@admin.route("/categorias")
def categorias_lista():
    solo_admin()
    lista = Categoria.query.order_by(Categoria.orden).all()
    return render_template("admin/categorias.html", categorias=lista)


@admin.route("/categorias/nueva", methods=["GET", "POST"])
@admin.route("/categorias/<int:id>/editar", methods=["GET", "POST"])
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
            bitacora("categoria_guardada", c.nombre)
            db.session.commit()
            flash("Categoría guardada.", "ok")
            return redirect(url_for("admin.categorias_lista"))
    return render_template("admin/categoria_form.html", c=c, v=v)


@admin.route("/categorias/<int:id>/eliminar", methods=["POST"])
def categoria_eliminar(id):
    solo_admin()
    c = db.get_or_404(Categoria, id)
    if c.articulos:
        flash(f"No se puede eliminar: tiene {len(c.articulos)} publicación(es). "
              "Ocúltala o mueve sus publicaciones a otra categoría.", "error")
    else:
        bitacora("categoria_eliminada", c.nombre)
        db.session.delete(c)
        db.session.commit()
        flash("Categoría eliminada.", "ok")
    return redirect(url_for("admin.categorias_lista"))


# ---------- Zonas: regiones y ciudades (solo admin) ----------
@admin.route("/zonas")
def ubicaciones_lista():
    solo_admin()
    return render_template("admin/ubicaciones.html", regiones=regiones_con_ciudades())


@admin.route("/zonas/nueva", methods=["GET", "POST"])
@admin.route("/zonas/<int:id>/editar", methods=["GET", "POST"])
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
def ubicacion_eliminar(id):
    solo_admin()
    u = db.get_or_404(Ubicacion, id)
    if u.articulos:
        flash(f"No se puede eliminar: tiene {len(u.articulos)} publicación(es).", "error")
    elif u.hijas:
        flash("No se puede eliminar: tiene ciudades dentro. Elimina primero las ciudades.", "error")
    else:
        db.session.delete(u)
        db.session.commit()
        flash("Zona eliminada.", "ok")
    return redirect(url_for("admin.ubicaciones_lista"))


# ---------- Páginas fijas (solo admin) ----------
@admin.route("/paginas")
def paginas():
    solo_admin()
    lista = Pagina.query.order_by(Pagina.id).all()
    pendientes = {p.id for p in lista if "[PENDIENTE" in p.contenido or "tudominio" in p.contenido}
    return render_template("admin/paginas.html", paginas=lista, pendientes=pendientes)


@admin.route("/paginas/nueva", methods=["GET", "POST"])
@admin.route("/paginas/<int:id>/editar", methods=["GET", "POST"])
def pagina_form(id=None):
    solo_admin()
    p = db.get_or_404(Pagina, id) if id else None
    if request.method == "POST":
        titulo = request.form.get("titulo", "").strip()[:120]
        contenido = limpiar_html(request.form.get("contenido", ""))
        visible = bool(request.form.get("visible"))
        if not titulo or contenido_vacio(contenido):
            flash("Título y contenido son obligatorios.", "error")
        elif visible and ("[PENDIENTE" in contenido or "tudominio" in contenido):
            flash("La página todavía tiene datos de ejemplo o marcados como [PENDIENTE]. "
                  "Complétalos antes de hacerla visible.", "error")
        else:
            if not p:
                p = Pagina(slug=slug_unico_modelo(Pagina, titulo, reservados=RUTAS_RESERVADAS))
                db.session.add(p)
            p.titulo = titulo
            p.contenido = contenido
            p.visible = visible
            p.actualizado = ahora()
            bitacora("pagina_guardada", p.titulo)
            db.session.commit()
            flash("Página guardada.", "ok")
            return redirect(url_for("admin.paginas"))
        p_tmp = p or Pagina(titulo=titulo, contenido=contenido, visible=visible)
        return render_template("admin/pagina_form.html", p=p_tmp, nueva=p is None)
    return render_template("admin/pagina_form.html",
                           p=p or Pagina(titulo="", contenido="", visible=False), nueva=p is None)


# ---------- Usuarios (solo admin) ----------
@admin.route("/usuarios", methods=["GET", "POST"])
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
            bitacora("usuario_creado", f"{email} ({rol})")
            db.session.commit()
            flash(f"Usuario {nombre} creado.", "ok")
    lista = Usuario.query.order_by(Usuario.nombre).all()
    conteo = dict(db.session.query(Articulo.autor_id, db.func.count(Articulo.id))
                  .group_by(Articulo.autor_id).all())
    return render_template("admin/usuarios.html", usuarios=lista, conteo=conteo)


@admin.route("/usuarios/<int:id>/activo", methods=["POST"])
def usuario_activo(id):
    solo_admin()
    u = db.get_or_404(Usuario, id)
    if u.id == current_user.id:
        flash("No puedes desactivar tu propia cuenta.", "error")
    else:
        u.activo = not u.activo
        bitacora("usuario_activo" if u.activo else "usuario_desactivado", u.email)
        db.session.commit()
    return redirect(url_for("admin.usuarios"))


@admin.route("/usuarios/<int:id>/rol", methods=["POST"])
def usuario_rol(id):
    solo_admin()
    u = db.get_or_404(Usuario, id)
    if u.id == current_user.id:
        flash("No puedes cambiar tu propio rol.", "error")
    else:
        u.rol = "admin" if request.form.get("rol") == "admin" else "editor"
        bitacora("usuario_rol", f"{u.email} → {u.rol}")
        db.session.commit()
        flash(f"Rol de {u.nombre} actualizado.", "ok")
    return redirect(url_for("admin.usuarios"))


# ---------- Mi cuenta ----------
@admin.route("/cuenta", methods=["GET", "POST"])
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
            bitacora("cambio_contrasena", current_user.email)
            db.session.commit()
            flash("Contraseña actualizada.", "ok")
    return render_template("admin/cuenta.html")

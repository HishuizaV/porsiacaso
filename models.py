from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "setiembre", "octubre", "noviembre", "diciembre"]


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(10), default="editor")   # admin | editor
    activo = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"

    @property
    def is_active(self):
        return self.activo


class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    corto = db.Column(db.String(40), nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    icono = db.Column(db.String(10))
    descripcion = db.Column(db.Text)
    orden = db.Column(db.Integer, default=0)
    articulos = db.relationship("Articulo", backref="categoria", lazy=True)


class Articulo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    titulo = db.Column(db.String(200), nullable=False)
    resumen = db.Column(db.String(400))
    contenido = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.String(120))
    imagen_alt = db.Column(db.String(200))
    imagen_credito = db.Column(db.String(200))
    datos_texto = db.Column(db.Text)
    fuente_url = db.Column(db.String(300))
    estado = db.Column(db.String(12), default="borrador")   # borrador | publicado
    destacado = db.Column(db.Boolean, default=False)
    visitas = db.Column(db.Integer, default=0)
    lectura = db.Column(db.Integer, default=1)
    fecha_publicacion = db.Column(db.DateTime)
    creado = db.Column(db.DateTime, default=datetime.now)
    actualizado = db.Column(db.DateTime, default=datetime.now)   # se cambia solo al editar
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    autor = db.relationship("Usuario")

    @property
    def fecha(self):
        d = self.fecha_publicacion or self.creado
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"

    @property
    def iso_publicado(self):
        return (self.fecha_publicacion or self.creado).isoformat()

    @property
    def iso_actualizado(self):
        return (self.actualizado or self.creado).isoformat()

    @property
    def fuente(self):
        return self.fuente_url

    @property
    def datos(self):
        pares = []
        for linea in (self.datos_texto or "").splitlines():
            if ":" in linea:
                k, v = linea.split(":", 1)
                if k.strip() and v.strip():
                    pares.append((k.strip(), v.strip()))
        return pares


class Pagina(db.Model):
    """Páginas fijas: sobre nosotros, privacidad, contacto..."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    titulo = db.Column(db.String(120), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    actualizado = db.Column(db.DateTime, default=datetime.now)


@login_manager.user_loader
def cargar_usuario(user_id):
    return db.session.get(Usuario, int(user_id))
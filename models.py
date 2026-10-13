import json
from datetime import datetime, date, timedelta, timezone

import sqlalchemy as sa
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager
from tipos import TIPOS, ENLACES, OPORTUNIDADES

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "setiembre", "octubre", "noviembre", "diciembre"]

# Perú no usa horario de verano: UTC-5 fijo (evita depender de tzdata en Windows)
LIMA = timezone(timedelta(hours=-5), "PET")


def ahora():
    """Hora actual de Lima, sin zona (así se guardan todas las fechas)."""
    return datetime.now(LIMA).replace(tzinfo=None)


def hoy():
    return ahora().date()


def fecha_larga(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}" if d else ""


def lineas(texto):
    """Convierte un texto 'uno por línea' en lista (sin viñetas ni líneas vacías)."""
    salida = []
    for linea in (texto or "").splitlines():
        linea = linea.strip().lstrip("-•*·").strip()
        if linea:
            salida.append(linea)
    return salida


ROLES = {"admin": "Administrador", "revisor": "Revisor", "editor": "Editor",
         "servicio": "Servicio Autopilot"}


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(10), default="editor")   # admin | revisor | editor | servicio
    activo = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def es_admin(self):
        return self.rol == "admin"

    @property
    def es_revisor(self):
        return self.rol == "revisor"

    @property
    def puede_publicar(self):
        """Publicar, aprobar y editar cualquier publicación: administrador o revisor."""
        return self.rol in ("admin", "revisor")

    @property
    def es_servicio(self):
        return self.rol == "servicio"

    @property
    def nombre_rol(self):
        return ROLES.get(self.rol, self.rol)

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
    visible = db.Column(db.Boolean, nullable=False, default=True,
                        server_default=sa.true())
    articulos = db.relationship("Articulo", backref="categoria", lazy=True)


class Ubicacion(db.Model):
    """Regiones y ciudades. Una ciudad apunta a su región con padre_id."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    tipo = db.Column(db.String(10), nullable=False, default="region")   # region | ciudad
    padre_id = db.Column(db.Integer, db.ForeignKey("ubicacion.id"))
    padre = db.relationship(
        "Ubicacion", remote_side=[id],
        backref=db.backref("hijas", order_by="Ubicacion.nombre"))
    articulos = db.relationship("Articulo", backref="ubicacion", lazy=True)

    @property
    def region(self):
        return self.padre if (self.tipo == "ciudad" and self.padre) else self


class Institucion(db.Model):
    """Empresas y entidades que publican convocatorias, becas, cursos, etc."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    nombre = db.Column(db.String(200), nullable=False)
    siglas = db.Column(db.String(40))
    sector = db.Column(db.String(20))   # ver tipos.SECTORES
    web = db.Column(db.String(300))
    logo = db.Column(db.String(120))
    descripcion = db.Column(db.Text)
    creado = db.Column(db.DateTime, default=ahora)
    # Las creadas por editores o por el Autopilot quedan sin verificar hasta que un admin las revise
    verificada = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.true())
    articulos = db.relationship("Articulo", backref="institucion", lazy=True)

    @property
    def nombre_corto(self):
        return self.siglas or self.nombre


class Articulo(db.Model):
    """Publicación editorial. `tipo` decide su formulario, su ficha y su tabla de detalle."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, default="noticia",
                     server_default="noticia", index=True)
    titulo = db.Column(db.String(200), nullable=False)
    resumen = db.Column(db.String(400))
    contenido = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.String(120))
    imagen_alt = db.Column(db.String(200))
    imagen_credito = db.Column(db.String(200))
    imagen_ancho = db.Column(db.Integer)
    imagen_alto = db.Column(db.Integer)
    datos_texto = db.Column(db.Text)
    fuente_url = db.Column(db.String(300))
    fuente_nombre = db.Column(db.String(150))
    estado = db.Column(db.String(12), default="borrador")   # borrador | revision | publicado | archivado
    destacado = db.Column(db.Boolean, default=False)
    visitas = db.Column(db.Integer, default=0)
    lectura = db.Column(db.Integer, default=1)
    fecha_publicacion = db.Column(db.DateTime)   # futura = publicación programada
    creado = db.Column(db.DateTime, default=ahora)
    actualizado = db.Column(db.DateTime, default=ahora)
    # Comunes a las oportunidades (empleo, beca, curso, bono…)
    fecha_limite = db.Column(db.Date, index=True)
    vigencia = db.Column(db.String(15))   # abierta | por_confirmar | cerrada
    verificado_en = db.Column(db.Date)
    aviso = db.Column(db.Text)            # recuadro de advertencia visible
    faq_json = db.Column(db.Text)         # [{"p": ..., "r": ...}]
    notas_internas = db.Column(db.Text)   # solo para el equipo
    busqueda = db.Column(db.Text)         # texto normalizado (sin tildes) para buscar
    busqueda_titulo = db.Column(db.String(300))
    categoria_id = db.Column(db.Integer, db.ForeignKey("categoria.id"), nullable=False)
    ubicacion_id = db.Column(db.Integer, db.ForeignKey("ubicacion.id"))   # None = todo el Perú
    institucion_id = db.Column(db.Integer, db.ForeignKey("institucion.id"), index=True)
    autor_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)
    autor = db.relationship("Usuario", foreign_keys=[autor_id])
    # Trazabilidad: quién creó (autor), editó, verificó, aprobó y publicó
    origen = db.Column(db.String(12), nullable=False, default="manual", server_default="manual")
    clave_externa = db.Column(db.String(80), unique=True)   # idempotencia de sincronización
    editado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    verificado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    aprobado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    publicado_por_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    editado_por = db.relationship("Usuario", foreign_keys=[editado_por_id])
    verificado_por = db.relationship("Usuario", foreign_keys=[verificado_por_id])
    aprobado_por = db.relationship("Usuario", foreign_keys=[aprobado_por_id])
    publicado_por = db.relationship("Usuario", foreign_keys=[publicado_por_id])

    detalle_empleo = db.relationship("DetalleEmpleo", uselist=False, cascade="all, delete-orphan",
                                     back_populates="articulo")
    detalle_beca = db.relationship("DetalleBeca", uselist=False, cascade="all, delete-orphan",
                                   back_populates="articulo")
    detalle_curso = db.relationship("DetalleCurso", uselist=False, cascade="all, delete-orphan",
                                    back_populates="articulo")
    detalle_beneficio = db.relationship("DetalleBeneficio", uselist=False,
                                        cascade="all, delete-orphan", back_populates="articulo")
    detalle_tramite = db.relationship("DetalleTramite", uselist=False,
                                      cascade="all, delete-orphan", back_populates="articulo")
    enlaces = db.relationship("Enlace", cascade="all, delete-orphan", order_by="Enlace.orden",
                              back_populates="articulo")

    __table_args__ = (db.Index("ix_articulo_estado_fecha", "estado", "fecha_publicacion"),)

    # ----- tipo y detalle -----
    @property
    def info(self):
        return TIPOS.get(self.tipo) or TIPOS["noticia"]

    @property
    def es_oportunidad(self):
        return self.tipo in OPORTUNIDADES

    @property
    def detalle(self):
        clave = self.info["detalle"]
        return getattr(self, "detalle_" + clave) if clave else None

    def asegurar_detalle(self):
        clave = self.info["detalle"]
        if clave and getattr(self, "detalle_" + clave) is None:
            setattr(self, "detalle_" + clave, MODELOS_DETALLE[clave]())
        return self.detalle

    # ----- fechas -----
    @property
    def fecha(self):
        return fecha_larga(self.fecha_publicacion or self.creado)

    @property
    def iso_publicado(self):
        return (self.fecha_publicacion or self.creado).isoformat()

    @property
    def iso_actualizado(self):
        return (self.actualizado or self.creado).isoformat()

    @property
    def programada(self):
        return (self.estado == "publicado" and self.fecha_publicacion is not None
                and self.fecha_publicacion > ahora())

    @property
    def fecha_limite_larga(self):
        return fecha_larga(self.fecha_limite)

    @property
    def verificado_largo(self):
        return fecha_larga(self.verificado_en)

    @property
    def vencida(self):
        return self.fecha_limite is not None and self.fecha_limite < hoy()

    @property
    def dias_restantes(self):
        if self.fecha_limite is None or self.vencida:
            return None
        return (self.fecha_limite - hoy()).days

    @property
    def situacion(self):
        """abierta | por_confirmar | cerrada | vencida | archivada | None (si no aplica)."""
        if self.estado == "archivado":
            return "archivada"
        if not self.es_oportunidad and not self.fecha_limite:
            return None
        if self.vigencia == "cerrada":
            return "cerrada"
        if self.vencida:
            return "vencida"
        if self.vigencia == "por_confirmar":
            return "por_confirmar"
        return "abierta" if (self.vigencia == "abierta" or self.fecha_limite) else None

    @property
    def vigente(self):
        return self.situacion not in ("cerrada", "vencida", "archivada")

    # ----- contenido -----
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

    @property
    def faq(self):
        try:
            datos = json.loads(self.faq_json or "[]")
        except ValueError:
            return []
        return [d for d in datos if isinstance(d, dict) and d.get("p") and d.get("r")]

    @property
    def enlace_principal(self):
        cta = self.info["cta"]
        for e in self.enlaces:
            if e.tipo == cta and e.destino:
                return e
        return None

    @property
    def enlaces_secundarios(self):
        principal = self.enlace_principal
        return [e for e in self.enlaces if e is not principal and e.destino]


class DetalleEmpleo(db.Model):
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), primary_key=True)
    cargo = db.Column(db.String(200))
    codigo = db.Column(db.String(80))
    tipo_convocatoria = db.Column(db.String(20))
    sector = db.Column(db.String(20))
    vacantes = db.Column(db.Integer)
    modalidad = db.Column(db.String(15), index=True)
    jornada = db.Column(db.String(15))
    tipo_contrato = db.Column(db.String(20))
    sueldo_min = db.Column(db.Numeric(10, 2))
    sueldo_max = db.Column(db.Numeric(10, 2))
    moneda = db.Column(db.String(3))
    lugar = db.Column(db.String(200))
    nivel_educativo = db.Column(db.String(20), index=True)
    formacion = db.Column(db.Text)
    experiencia = db.Column(db.Text)
    competencias = db.Column(db.Text)
    funciones = db.Column(db.Text)
    articulo = db.relationship("Articulo", back_populates="detalle_empleo")

    @property
    def sueldo_texto(self):
        if self.sueldo_min is None:
            return ""
        simbolo = "US$" if self.moneda == "USD" else "S/"

        def fmt(n):
            n = float(n)
            return f"{n:,.0f}" if n == int(n) else f"{n:,.2f}"
        if self.sueldo_max is not None and self.sueldo_max != self.sueldo_min:
            return f"{simbolo} {fmt(self.sueldo_min)} – {fmt(self.sueldo_max)}"
        return f"{simbolo} {fmt(self.sueldo_min)}"


class DetalleBeca(db.Model):
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), primary_key=True)
    publico = db.Column(db.String(300))
    nivel = db.Column(db.String(120))
    lugar_estudio = db.Column(db.String(200))
    modalidad = db.Column(db.String(15))
    vacantes = db.Column(db.Integer)
    requisitos = db.Column(db.Text)
    cobertura = db.Column(db.Text)
    beneficios = db.Column(db.Text)
    pasos = db.Column(db.Text)
    articulo = db.relationship("Articulo", back_populates="detalle_beca")


class DetalleCurso(db.Model):
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), primary_key=True)
    nivel = db.Column(db.String(80))
    modalidad = db.Column(db.String(15))
    costo = db.Column(db.String(15), index=True)   # gratuito | pagado | por_confirmar
    costo_detalle = db.Column(db.String(200))
    duracion = db.Column(db.String(120))
    fecha_inicio = db.Column(db.Date)
    horario = db.Column(db.String(200))
    certificado = db.Column(db.String(15))
    requisitos = db.Column(db.Text)
    temario = db.Column(db.Text)
    articulo = db.relationship("Articulo", back_populates="detalle_curso")


class DetalleBeneficio(db.Model):
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), primary_key=True)
    poblacion = db.Column(db.String(300))
    monto = db.Column(db.String(120))
    cronograma = db.Column(db.Text)
    requisitos = db.Column(db.Text)
    pasos = db.Column(db.Text)
    articulo = db.relationship("Articulo", back_populates="detalle_beneficio")


class DetalleTramite(db.Model):
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), primary_key=True)
    finalidad = db.Column(db.String(300))
    costo = db.Column(db.String(150))
    plazo = db.Column(db.String(150))
    canal = db.Column(db.String(15))
    lugar_atencion = db.Column(db.String(250))
    documentos = db.Column(db.Text)
    requisitos = db.Column(db.Text)
    pasos = db.Column(db.Text)
    articulo = db.relationship("Articulo", back_populates="detalle_tramite")


MODELOS_DETALLE = {"empleo": DetalleEmpleo, "beca": DetalleBeca, "curso": DetalleCurso,
                   "beneficio": DetalleBeneficio, "tramite": DetalleTramite}


class Enlace(db.Model):
    """Botón de una publicación: enlace externo oficial o PDF subido."""
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), nullable=False, index=True)
    tipo = db.Column(db.String(20), nullable=False, default="otro")   # ver tipos.ENLACES
    etiqueta = db.Column(db.String(80))
    url = db.Column(db.String(500))
    archivo = db.Column(db.String(120))   # PDF en static/uploads/docs
    orden = db.Column(db.Integer, default=0)
    articulo = db.relationship("Articulo", back_populates="enlaces")

    @property
    def texto(self):
        return self.etiqueta or ENLACES.get(self.tipo, "Más información")

    @property
    def destino(self):
        """URL final (externa) o None si es un PDF local (se resuelve en la plantilla)."""
        return self.url or self.archivo


class Pagina(db.Model):
    """Páginas fijas: sobre nosotros, privacidad, contacto..."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    titulo = db.Column(db.String(120), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    actualizado = db.Column(db.DateTime, default=ahora)
    visible = db.Column(db.Boolean, nullable=False, default=True, server_default=sa.true())


class Ajuste(db.Model):
    """Configuración editable desde el panel (publicidad, asistente, contacto…)."""
    clave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(db.Text)


class Registro(db.Model):
    """Bitácora de acciones importantes del panel."""
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=ahora, index=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    usuario = db.relationship("Usuario")
    accion = db.Column(db.String(40), nullable=False)
    detalle = db.Column(db.String(300))


@login_manager.user_loader
def cargar_usuario(user_id):
    return db.session.get(Usuario, int(user_id))

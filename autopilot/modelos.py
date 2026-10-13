"""Modelos del Autopilot: fuentes, hallazgos, evidencias, jornadas, cola, decisiones e historial."""
import json

import sqlalchemy as sa

from extensions import db
from models import ahora

FORMATOS = [("html", "Página web (HTML)"), ("rss", "RSS / Atom"), ("json", "API JSON"),
            ("pdf", "Documento PDF"), ("otro", "Otro / manual")]
CONFIANZA = [("alta", "Alta (fuente oficial)"), ("media", "Media"), ("baja", "Baja")]
ESTADOS_FUENTE = [("activa", "Activa"), ("pausada", "Pausada"), ("manual", "Solo consulta manual"),
                  ("error", "Con errores")]
ESTADOS_DATO = ("confirmado", "derivado", "inferido", "no_encontrado", "contradictorio")


def _json(texto, defecto):
    try:
        v = json.loads(texto) if texto else defecto
    except ValueError:
        return defecto
    return v if isinstance(v, type(defecto)) else defecto


class Fuente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    institucion_id = db.Column(db.Integer, db.ForeignKey("institucion.id"))
    institucion = db.relationship("Institucion")
    url_principal = db.Column(db.String(500), nullable=False)
    url_listado = db.Column(db.String(500))
    tipo_contenido = db.Column(db.String(20), nullable=False, default="empleo")
    ubicacion_id = db.Column(db.Integer, db.ForeignKey("ubicacion.id"))
    ubicacion = db.relationship("Ubicacion")
    formato = db.Column(db.String(10), nullable=False, default="html")
    frecuencia_horas = db.Column(db.Integer, nullable=False, default=24)
    prioridad = db.Column(db.Integer, nullable=False, default=3)   # 1 = más alta
    confianza = db.Column(db.String(10), nullable=False, default="alta")
    estado = db.Column(db.String(12), nullable=False, default="pausada", index=True)
    ultima_consulta = db.Column(db.DateTime)
    ultima_novedad = db.Column(db.DateTime)
    condiciones_acceso = db.Column(db.Text)
    permite_extraccion = db.Column(db.Boolean, nullable=False, default=False)
    permite_autopublicacion = db.Column(db.Boolean, nullable=False, default=False)
    observaciones = db.Column(db.Text)
    config_json = db.Column(db.Text)   # patron_enlace, palabras_clave, max_items, seguir_detalle…
    errores_consecutivos = db.Column(db.Integer, nullable=False, default=0)
    ultimo_error = db.Column(db.Text)
    creado = db.Column(db.DateTime, default=ahora)
    actualizado = db.Column(db.DateTime, default=ahora)

    @property
    def config(self):
        return _json(self.config_json, {})

    @property
    def toca_consultar(self):
        if self.ultima_consulta is None:
            return True
        return (ahora() - self.ultima_consulta).total_seconds() >= self.frecuencia_horas * 3600

    @property
    def consultable(self):
        return self.estado in ("activa", "error") and self.permite_extraccion


class Hallazgo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fuente_id = db.Column(db.Integer, db.ForeignKey("fuente.id"), nullable=False, index=True)
    fuente = db.relationship("Fuente")
    url = db.Column(db.String(1000), nullable=False)
    url_normalizada = db.Column(db.String(1000), nullable=False, unique=True)
    id_externo = db.Column(db.String(200))
    titulo = db.Column(db.String(400))
    resumen_fuente = db.Column(db.Text)
    fecha_fuente = db.Column(db.DateTime)
    descubierto = db.Column(db.DateTime, default=ahora, index=True)
    ultima_consulta = db.Column(db.DateTime, default=ahora)
    huella = db.Column(db.String(64), index=True)
    huella_documento = db.Column(db.String(64), index=True)
    codigo_convocatoria = db.Column(db.String(120), index=True)
    # nuevo | extraido | borrador | duplicado | descartado | error | actualizacion
    estado = db.Column(db.String(15), nullable=False, default="nuevo", index=True)
    tipo_detectado = db.Column(db.String(20))
    relevancia = db.Column(db.Integer, default=0)
    prioridad = db.Column(db.Integer, default=3)
    motivo = db.Column(db.Text)
    texto = db.Column(db.Text)              # texto plano de la evidencia (recortado)
    datos_json = db.Column(db.Text)         # campos extraídos {campo: {valor, estado, ...}}
    advertencias_json = db.Column(db.Text)
    enlaces_json = db.Column(db.Text)       # enlaces oficiales detectados
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), index=True)
    articulo = db.relationship("Articulo")
    duplicado_de_id = db.Column(db.Integer, db.ForeignKey("hallazgo.id"))
    intentos = db.Column(db.Integer, nullable=False, default=0)

    evidencias = db.relationship("Evidencia", cascade="all, delete-orphan", back_populates="hallazgo",
                                 order_by="Evidencia.id")
    __table_args__ = (db.UniqueConstraint("fuente_id", "id_externo", name="uq_hallazgo_fuente_externo"),)

    @property
    def datos(self):
        return _json(self.datos_json, {})

    @property
    def advertencias(self):
        return _json(self.advertencias_json, [])

    @property
    def enlaces(self):
        return _json(self.enlaces_json, [])


class Evidencia(db.Model):
    """Respaldo de cada dato: de dónde salió y con qué grado de certeza."""
    id = db.Column(db.Integer, primary_key=True)
    hallazgo_id = db.Column(db.Integer, db.ForeignKey("hallazgo.id"), nullable=False, index=True)
    hallazgo = db.relationship("Hallazgo", back_populates="evidencias")
    campo = db.Column(db.String(40), nullable=False)
    valor = db.Column(db.Text)
    estado = db.Column(db.String(15), nullable=False)   # ver ESTADOS_DATO
    fragmento = db.Column(db.String(600))
    origen = db.Column(db.String(1000))
    pagina = db.Column(db.Integer)
    metodo = db.Column(db.String(20))   # regla | fuente | ia | verificacion


class Ejecucion(db.Model):
    """Una jornada del Autopilot."""
    id = db.Column(db.Integer, primary_key=True)
    # solicitada | en_curso | pausada | completada | detenida | interrumpida | fallida
    estado = db.Column(db.String(15), nullable=False, default="solicitada", index=True)
    solicitud = db.Column(db.String(10))   # pausar | continuar | detener
    origen = db.Column(db.String(15), default="manual")   # panel | programador | manual
    iniciada = db.Column(db.DateTime)
    finalizada = db.Column(db.DateTime)
    latido = db.Column(db.DateTime)
    duracion_max = db.Column(db.Integer, nullable=False, default=120)   # minutos
    objetivo = db.Column(db.Integer, nullable=False, default=12)
    tipos_json = db.Column(db.Text)
    regiones_json = db.Column(db.Text)
    etapa = db.Column(db.String(20))
    contadores_json = db.Column(db.Text)
    informe_json = db.Column(db.Text)
    error = db.Column(db.Text)
    pid = db.Column(db.Integer)
    creada = db.Column(db.DateTime, default=ahora)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    usuario = db.relationship("Usuario")

    @property
    def contadores(self):
        return _json(self.contadores_json, {})

    @property
    def informe(self):
        return _json(self.informe_json, {})

    @property
    def tipos(self):
        return _json(self.tipos_json, [])

    @property
    def regiones(self):
        return _json(self.regiones_json, [])

    @property
    def minutos_transcurridos(self):
        if not self.iniciada:
            return 0
        fin = self.finalizada or ahora()
        return round((fin - self.iniciada).total_seconds() / 60, 1)

    @property
    def activa(self):
        return self.estado in ("solicitada", "en_curso", "pausada")


class Tarea(db.Model):
    """Cola persistente. `clave` única = idempotencia (repetir no duplica trabajo)."""
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False)   # consultar_fuente | procesar_hallazgo | revisar_vigencia
    objetivo_id = db.Column(db.Integer)
    clave = db.Column(db.String(120), nullable=False, unique=True)
    estado = db.Column(db.String(12), nullable=False, default="pendiente", index=True)
    prioridad = db.Column(db.Integer, nullable=False, default=3)
    intentos = db.Column(db.Integer, nullable=False, default=0)
    max_intentos = db.Column(db.Integer, nullable=False, default=3)
    proximo_intento = db.Column(db.DateTime)
    ultimo_error = db.Column(db.Text)
    ejecucion_id = db.Column(db.Integer, db.ForeignKey("ejecucion.id"))
    creada = db.Column(db.DateTime, default=ahora)
    actualizada = db.Column(db.DateTime, default=ahora)


class Bloqueo(db.Model):
    """Impide dos jornadas simultáneas. Se considera abandonado si el latido es viejo."""
    nombre = db.Column(db.String(40), primary_key=True)
    propietario = db.Column(db.String(64), nullable=False)
    adquirido = db.Column(db.DateTime, default=ahora)
    latido = db.Column(db.DateTime, default=ahora)


class DecisionEditorial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), index=True)
    hallazgo_id = db.Column(db.Integer, db.ForeignKey("hallazgo.id"), index=True)
    # rechazado | revision | autopublicado | programado | aprobado | devuelto
    decision = db.Column(db.String(20), nullable=False)
    motivo = db.Column(db.Text)
    checklist_json = db.Column(db.Text)
    actor = db.Column(db.String(12), nullable=False, default="autopilot")   # autopilot | humano
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    usuario = db.relationship("Usuario")
    fecha = db.Column(db.DateTime, default=ahora, index=True)

    @property
    def checklist(self):
        return _json(self.checklist_json, [])


class VersionArticulo(db.Model):
    """Antes/después de cambios automáticos o propuestas de actualización. Permite revertir."""
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), nullable=False, index=True)
    articulo = db.relationship("Articulo")
    hallazgo_id = db.Column(db.Integer, db.ForeignKey("hallazgo.id"))
    fecha = db.Column(db.DateTime, default=ahora)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    usuario = db.relationship("Usuario")
    origen = db.Column(db.String(12), nullable=False, default="autopilot")
    tipo = db.Column(db.String(15), nullable=False, default="propuesta")   # propuesta | aplicada
    estado = db.Column(db.String(12), nullable=False, default="pendiente")  # pendiente|aplicada|rechazada|revertida
    datos_antes = db.Column(db.Text)
    datos_despues = db.Column(db.Text)
    resumen_cambios = db.Column(db.Text)

    @property
    def antes(self):
        return _json(self.datos_antes, {})

    @property
    def despues(self):
        return _json(self.datos_despues, {})


class Verificacion(db.Model):
    """Historial de comprobaciones de una publicación (enlaces, vigencia, cambios en la fuente)."""
    id = db.Column(db.Integer, primary_key=True)
    articulo_id = db.Column(db.Integer, db.ForeignKey("articulo.id"), nullable=False, index=True)
    fecha = db.Column(db.DateTime, default=ahora)
    tipo = db.Column(db.String(20), nullable=False)        # enlace | vigencia | fuente
    resultado = db.Column(db.String(12), nullable=False)   # ok | error | cambio
    detalle = db.Column(db.Text)


class PropuestaInstitucion(db.Model):
    """Corrección sugerida por un editor; solo un administrador la aplica."""
    id = db.Column(db.Integer, primary_key=True)
    institucion_id = db.Column(db.Integer, db.ForeignKey("institucion.id"), nullable=False)
    institucion = db.relationship("Institucion")
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    usuario = db.relationship("Usuario")
    texto = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(10), nullable=False, default="pendiente")
    fecha = db.Column(db.DateTime, default=ahora)


class LimiteContador(db.Model):
    """Límite de peticiones persistente (ventana fija por minuto), compartido entre procesos."""
    clave = db.Column(db.String(150), primary_key=True)
    ventana = db.Column(db.Integer, nullable=False)
    cuenta = db.Column(db.Integer, nullable=False, default=0)


__all__ = ["Fuente", "Hallazgo", "Evidencia", "Ejecucion", "Tarea", "Bloqueo", "DecisionEditorial",
           "VersionArticulo", "Verificacion", "PropuestaInstitucion", "LimiteContador", "sa"]

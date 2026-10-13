"""Registro de tipos de publicación.

Cada tipo define su sección pública, su tabla de detalle, el botón principal
y los campos que verá el editor. Para agregar un tipo nuevo basta con
añadir una entrada aquí (y, si necesita campos propios, un modelo Detalle*).
"""

# ---------- Opciones reutilizables ----------
MODALIDADES = [("presencial", "Presencial"), ("remoto", "Remoto"), ("hibrido", "Híbrido")]
MODALIDADES_CURSO = [("presencial", "Presencial"), ("virtual", "Virtual"),
                     ("semipresencial", "Semipresencial")]
SECTORES = [("publico", "Público"), ("privado", "Privado"), ("ong", "ONG / sin fines de lucro"),
            ("internacional", "Organismo internacional"), ("educativo", "Institución educativa")]
NIVELES_EDUCATIVOS = [
    ("sin_requisito", "Sin requisito de estudios"),
    ("secundaria", "Secundaria completa"),
    ("tecnico", "Técnico"),
    ("universitario", "Estudiante universitario"),
    ("bachiller", "Bachiller"),
    ("titulado", "Titulado / licenciado"),
    ("posgrado", "Maestría o doctorado"),
]
TIPOS_CONVOCATORIA = [
    ("cas", "CAS (D. Leg. 1057)"), ("728", "Régimen 728"), ("276", "Régimen 276"),
    ("servir", "Ley SERVIR"), ("practicas", "Prácticas pre o profesionales"),
    ("privada", "Empresa privada"), ("otra", "Otra"),
]
JORNADAS = [("completa", "Tiempo completo"), ("parcial", "Medio tiempo"),
            ("por_horas", "Por horas"), ("turnos", "Por turnos")]
CONTRATOS = [("indeterminado", "Plazo indeterminado"), ("plazo_fijo", "Plazo fijo / temporal"),
             ("cas", "Contrato CAS"), ("practicas", "Convenio de prácticas"),
             ("locacion", "Locación de servicios"), ("otro", "Otro")]
MONEDAS = [("PEN", "Soles (S/)"), ("USD", "Dólares (US$)")]
COSTOS = [("gratuito", "Gratuito"), ("pagado", "De pago"), ("por_confirmar", "Por confirmar")]
CERTIFICADOS = [("gratuito", "Sí, gratuito"), ("pagado", "Sí, con costo"),
                ("no", "No otorga"), ("por_confirmar", "Por confirmar")]
CANALES = [("presencial", "Presencial"), ("virtual", "Virtual"), ("ambos", "Presencial y virtual")]

VIGENCIAS = [("abierta", "Abierta"), ("por_confirmar", "Pendiente de verificación"),
             ("cerrada", "Cerrada")]
ESTADOS = [("borrador", "Borrador"), ("revision", "Pendiente de revisión"),
           ("publicado", "Publicado"), ("archivado", "Archivado")]

ENLACES = {
    "postular": "Postular en sitio oficial",
    "convocatoria": "Ver convocatoria",
    "bases": "Ver bases",
    "anexo": "Descargar anexo",
    "inscripcion": "Inscribirme en sitio oficial",
    "consulta": "Consultar en sitio oficial",
    "oficial": "Ir a la página oficial",
    "otro": "Más información",
}


def c(nombre, tipo, etiqueta, ayuda="", requerido=False, opciones=None, ejemplo="", maximo=None):
    return dict(nombre=nombre, tipo=tipo, etiqueta=etiqueta, ayuda=ayuda, requerido=requerido,
                opciones=opciones or [], ejemplo=ejemplo, maximo=maximo)


# Tipos de campo: texto, lineas (una por línea → lista), parrafo, opcion, numero, decimal, fecha
CAMPOS_EMPLEO = [
    ("Puesto", [
        c("cargo", "texto", "Nombre del puesto", "Tal como figura en la convocatoria.", True,
          ejemplo="Asistente administrativo", maximo=200),
        c("codigo", "texto", "Código o N.° de convocatoria", "Solo si la entidad lo indica.",
          ejemplo="CAS N.° 045-2026", maximo=80),
        c("tipo_convocatoria", "opcion", "Tipo de convocatoria", opciones=TIPOS_CONVOCATORIA),
        c("sector", "opcion", "Sector", opciones=SECTORES[:2]),
        c("vacantes", "numero", "Número de vacantes", "Déjalo vacío si no se sabe."),
    ]),
    ("Condiciones", [
        c("modalidad", "opcion", "Modalidad de trabajo", opciones=MODALIDADES),
        c("jornada", "opcion", "Jornada", opciones=JORNADAS),
        c("tipo_contrato", "opcion", "Tipo de contrato", opciones=CONTRATOS),
        c("sueldo_min", "decimal", "Sueldo", "Monto mensual. Solo si la convocatoria lo indica.",
          ejemplo="2500"),
        c("sueldo_max", "decimal", "Sueldo máximo (si es un rango)", ejemplo="3000"),
        c("moneda", "opcion", "Moneda", opciones=MONEDAS),
        c("lugar", "texto", "Distrito o dirección de trabajo", "Opcional. Ej: Distrito de José Leonardo Ortiz.",
          maximo=200),
    ]),
    ("Requisitos y funciones", [
        c("nivel_educativo", "opcion", "Nivel de estudios mínimo", opciones=NIVELES_EDUCATIVOS),
        c("formacion", "lineas", "Formación requerida", "Escribe un requisito por línea.",
          ejemplo="Bachiller en Administración o Contabilidad"),
        c("experiencia", "lineas", "Experiencia requerida", "Un requisito por línea.",
          ejemplo="1 año en el sector público"),
        c("competencias", "lineas", "Competencias y conocimientos", "Una por línea.",
          ejemplo="Manejo de Excel a nivel intermedio"),
        c("funciones", "lineas", "Funciones y responsabilidades", "Una por línea.",
          ejemplo="Registrar y archivar documentos"),
    ]),
]

CAMPOS_BECA = [
    ("Datos de la convocatoria", [
        c("publico", "texto", "¿A quién está dirigida?", "Público objetivo en una frase.", True,
          ejemplo="Egresados de secundaria de colegios públicos", maximo=300),
        c("nivel", "texto", "Nivel de estudios", ejemplo="Pregrado universitario", maximo=120),
        c("lugar_estudio", "texto", "Lugar de estudios", ejemplo="Universidades del Perú", maximo=200),
        c("modalidad", "opcion", "Modalidad", opciones=MODALIDADES_CURSO),
        c("vacantes", "numero", "Número de vacantes", "Solo si está publicado oficialmente."),
    ]),
    ("Requisitos y beneficios", [
        c("requisitos", "lineas", "Requisitos", "Uno por línea.", True),
        c("cobertura", "lineas", "Qué cubre", "Uno por línea. Ej: Matrícula y pensiones."),
        c("beneficios", "lineas", "Otros beneficios", "Uno por línea."),
        c("pasos", "lineas", "Cómo postular (pasos)", "Un paso por línea, en orden."),
    ]),
]

CAMPOS_CURSO = [
    ("Datos del curso", [
        c("nivel", "texto", "Nivel", ejemplo="Básico", maximo=80),
        c("modalidad", "opcion", "Modalidad", opciones=MODALIDADES_CURSO),
        c("costo", "opcion", "Costo", "Marca «Gratuito» solo si la fuente oficial lo dice.", True,
          opciones=COSTOS),
        c("costo_detalle", "texto", "Detalle del costo", ejemplo="S/ 50 por el certificado", maximo=200),
        c("duracion", "texto", "Duración", ejemplo="40 horas académicas", maximo=120),
        c("fecha_inicio", "fecha", "Fecha de inicio"),
        c("horario", "texto", "Horario", ejemplo="Martes y jueves, 7 a 9 p. m.", maximo=200),
        c("certificado", "opcion", "¿Otorga certificado?", opciones=CERTIFICADOS),
    ]),
    ("Contenido y requisitos", [
        c("requisitos", "lineas", "Requisitos", "Uno por línea."),
        c("temario", "lineas", "Temas que se enseñan", "Uno por línea."),
    ]),
]

CAMPOS_BONO = [
    ("Datos del beneficio", [
        c("poblacion", "texto", "¿Quiénes lo reciben?", "Población beneficiaria.", True,
          ejemplo="Hogares en pobreza registrados en el SISFOH", maximo=300),
        c("monto", "texto", "Monto", "Solo si es oficial.", ejemplo="S/ 350", maximo=120),
        c("cronograma", "parrafo", "Cronograma o fechas de pago", "Escribe lo que indique la fuente."),
    ]),
    ("Requisitos y pasos", [
        c("requisitos", "lineas", "Requisitos", "Uno por línea."),
        c("pasos", "lineas", "Cómo consultar o cobrar (pasos)", "Un paso por línea, en orden."),
    ]),
]

CAMPOS_TRAMITE = [
    ("Datos del trámite", [
        c("finalidad", "texto", "¿Para qué sirve?", "Explícalo en una frase.", True,
          ejemplo="Obtener el duplicado del DNI por pérdida o robo", maximo=300),
        c("costo", "texto", "Costo", ejemplo="S/ 30 (tasa oficial)", maximo=150),
        c("plazo", "texto", "Tiempo de atención", ejemplo="Hasta 7 días hábiles", maximo=150),
        c("canal", "opcion", "Forma de atención", opciones=CANALES),
        c("lugar_atencion", "texto", "Lugar de atención", ejemplo="Agencias RENIEC o en línea", maximo=250),
    ]),
    ("Requisitos y pasos", [
        c("documentos", "lineas", "Documentos necesarios", "Uno por línea."),
        c("requisitos", "lineas", "Otros requisitos", "Uno por línea."),
        c("pasos", "lineas", "Paso a paso", "Un paso por línea, en orden.", True),
    ]),
]


def t(nombre, plural, seccion, icono, categoria, detalle, cta, descripcion, campos=None,
      etiqueta_contenido="Contenido", oportunidad=False, institucion=False, enlaces=()):
    return dict(nombre=nombre, plural=plural, seccion=seccion, icono=icono, categoria=categoria,
                detalle=detalle, cta=cta, descripcion=descripcion, campos=campos or [],
                etiqueta_contenido=etiqueta_contenido, oportunidad=oportunidad,
                institucion=institucion, enlaces=list(enlaces))


TIPOS = {
    "empleo": t("Empleo", "Empleos", "empleos", "💼", "empleo", "empleo", "postular",
                "Ofertas de trabajo verificadas en el sector público y privado del Perú.",
                CAMPOS_EMPLEO, "Descripción general del puesto", True, True,
                ("postular", "convocatoria", "bases")),
    "convocatoria": t("Convocatoria pública", "Convocatorias públicas", "convocatorias", "🏛️",
                      "empleo", "empleo", "convocatoria",
                      "Procesos de selección de entidades públicas con varias plazas.",
                      CAMPOS_EMPLEO, "Descripción de la convocatoria", True, True,
                      ("convocatoria", "bases", "postular")),
    "beca": t("Beca", "Becas", "becas", "🎓", "educacion", "beca", "postular",
              "Becas para estudiar en el Perú y el extranjero, con requisitos y fechas.",
              CAMPOS_BECA, "Descripción de la beca", True, True, ("postular", "bases")),
    "educativa": t("Convocatoria educativa", "Convocatorias educativas", "convocatorias-educativas",
                   "🏫", "educacion", "beca", "postular",
                   "Admisiones, concursos y programas educativos con fecha de inscripción.",
                   CAMPOS_BECA, "Descripción de la convocatoria", True, True, ("postular", "bases")),
    "curso": t("Curso", "Cursos", "cursos", "📚", "educacion", "curso", "inscripcion",
               "Cursos y capacitaciones con su costo, duración y certificado.",
               CAMPOS_CURSO, "Descripción del curso", True, True, ("inscripcion",)),
    "bono": t("Bono o beneficio", "Bonos y beneficios", "bonos", "💰", "beneficios", "beneficio",
              "consulta", "Bonos, subsidios y programas sociales: quién califica y cómo consultar.",
              CAMPOS_BONO, "Explicación del beneficio", True, True, ("consulta",)),
    "tramite": t("Trámite", "Trámites", "tramites", "📋", "tramites", "tramite", "oficial",
                 "Trámites paso a paso: documentos, costos, plazos y dónde hacerlos.",
                 CAMPOS_TRAMITE, "Información adicional", False, True, ("oficial",)),
    "guia": t("Guía práctica", "Guías prácticas", "guias", "🧭", "tramites", None, None,
              "Guías y consejos prácticos para resolver dudas del día a día."),
    "noticia": t("Noticia", "Noticias", "noticias", "📰", "actualidad", None, None,
                 "Noticias y artículos explicados de forma clara."),
    "otro": t("Otro contenido", "Otros contenidos", "informacion", "📌", None, None, None,
              "Otra información útil."),
}

# Tipos cuya URL pública sigue siendo /articulo/<slug> (compatibilidad con lo ya publicado)
TIPOS_ARTICULO = ("noticia", "otro")
SECCIONES = {d["seccion"]: k for k, d in TIPOS.items()}
OPORTUNIDADES = tuple(k for k, d in TIPOS.items() if d["oportunidad"])
# Orden del menú y del selector "+ Nueva publicación"
ORDEN = ["empleo", "convocatoria", "beca", "educativa", "curso", "bono", "tramite", "guia",
         "noticia", "otro"]

# Direcciones que no pueden usarse como página fija (chocan con secciones o rutas del sistema)
RUTAS_RESERVADAS = set(SECCIONES) | {
    "admin", "api", "static", "buscar", "articulo", "categoria", "zona", "sitemap.xml",
    "robots.txt", "ads.txt", "favicon.ico", "region",
}


def nombre_opcion(opciones, valor):
    return dict(opciones).get(valor, "")

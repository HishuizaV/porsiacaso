"""Fuentes iniciales investigadas el 13/10/2026 (ver docs/AUTOPILOT_FUENTES.md).

Se cargan PAUSADAS y SIN permiso de extracción: el administrador decide activarlas desde el panel
después de revisar las condiciones de uso de cada sitio. Nunca se cargan con autopublicación.
"""

INSTITUCIONES = {
    "mpch": ("Municipalidad Provincial de Chiclayo", "MPCH", "publico", "https://www.gob.pe/munichiclayo"),
    "gorel": ("Gobierno Regional de Lambayeque", None, "publico", "https://www.gob.pe/regionlambayeque"),
    "enap": ("Escuela Nacional de Administración Pública", "ENAP", "publico", "https://www.gob.pe/enap"),
    "pronabec": ("Programa Nacional de Becas y Crédito Educativo", "PRONABEC", "publico",
                 "https://www.gob.pe/pronabec"),
    "servir": ("Autoridad Nacional del Servicio Civil", "SERVIR", "publico", "https://www.gob.pe/servir"),
}

ROBOTS_GOBPE = ("robots.txt de gob.pe (13/10/2026) solo bloquea /admin/ y parámetros ?sheet=. "
                "Revisar los términos de uso de gob.pe antes de activar.")

FUENTES = [
    dict(nombre="MPCH – Convocatorias CAS 2025 (gob.pe)", inst="mpch", zona="chiclayo",
         url_principal="https://www.gob.pe/institucion/munichiclayo/colecciones/81032-convocatorias-laborales",
         url_listado="https://www.gob.pe/institucion/munichiclayo/colecciones/77604-convocatorias-cas-2025",
         tipo="convocatoria", formato="html", frecuencia=24, prioridad=1,
         config={"patron_enlace": r"/institucion/munichiclayo/informes-publicaciones/\d+",
                 "patron_id": r"/informes-publicaciones/(\d+)", "palabras_clave": ["convocatoria", "cas"],
                 "max_items": 20},
         condiciones=ROBOTS_GOBPE,
         observaciones="Cada año la municipalidad crea una colección nueva (CAS 2025). Cuando aparezca la de 2026, "
                       "registrarla como fuente. Las bases están en PDF (cronograma con fecha límite).")
    ,
    dict(nombre="MPCH – Convocatorias D. Leg. 728 (gob.pe)", inst="mpch", zona="chiclayo",
         url_principal="https://www.gob.pe/institucion/munichiclayo/colecciones/81032-convocatorias-laborales",
         url_listado="https://www.gob.pe/institucion/munichiclayo/colecciones/81036-convocatorias-decreto-legislativo-n-728",
         tipo="convocatoria", formato="html", frecuencia=48, prioridad=2,
         config={"patron_enlace": r"/institucion/munichiclayo/informes-publicaciones/\d+",
                 "patron_id": r"/informes-publicaciones/(\d+)", "palabras_clave": ["convocatoria"]},
         condiciones=ROBOTS_GOBPE, observaciones="Al 13/10/2026 la colección no mostraba convocatorias abiertas."),
    dict(nombre="Gobierno Regional de Lambayeque – Avisos de convocatoria (gob.pe)", inst="gorel", zona="lambayeque",
         url_principal="https://www.gob.pe/regionlambayeque",
         url_listado="https://www.gob.pe/institucion/regionlambayeque/informes-publicaciones",
         tipo="convocatoria", formato="html", frecuencia=24, prioridad=1,
         config={"patron_enlace": r"/institucion/regionlambayeque/informes-publicaciones/\d+",
                 "patron_id": r"/informes-publicaciones/(\d+)", "palabras_clave": ["convocatoria", "cas", "proceso"]},
         condiciones=ROBOTS_GOBPE, observaciones="Lista general de publicaciones; el filtro de palabras clave "
                                                 "deja solo los avisos de convocatoria."),
    dict(nombre="ENAP – Cursos y convocatorias (gob.pe)", inst="enap", zona=None,
         url_principal="https://www.gob.pe/enap",
         url_listado="https://www.gob.pe/institucion/enap/campa%C3%B1as",
         tipo="curso", formato="html", frecuencia=48, prioridad=2,
         config={"patron_enlace": r"/institucion/(enap|servir)/campa(%C3%B1|ñ)as/\d+",
                 "patron_id": r"/campa(?:%C3%B1|ñ)as/(\d+)", "palabras_clave": ["curso", "convocatoria", "mooc"]},
         condiciones=ROBOTS_GOBPE,
         observaciones="Cursos para servidores públicos (muchos gratuitos y remotos). El costo solo se marca "
                       "gratuito cuando la página lo dice."),
    dict(nombre="PRONABEC – Noticias (gob.pe)", inst="pronabec", zona=None,
         url_principal="https://www.gob.pe/pronabec",
         url_listado="https://www.gob.pe/institucion/pronabec/noticias",
         tipo="beca", formato="html", frecuencia=24, prioridad=2,
         config={"patron_enlace": r"/institucion/pronabec/noticias/\d+", "patron_id": r"/noticias/(\d+)",
                 "palabras_clave": ["convocatoria", "postula", "postulacion", "inscripcion", "inscribete", "becas"],
                 "excluir": ["ganadores", "historia", "testimonio", "exbecario"]},
         condiciones=ROBOTS_GOBPE,
         observaciones="Mezcla convocatorias con notas institucionales; el clasificador descarta testimonios y resultados."),
    dict(nombre="PRONABEC – RSS del sitio institucional", inst="pronabec", zona=None,
         url_principal="https://www.pronabec.gob.pe/", url_listado="https://www.pronabec.gob.pe/feed/",
         tipo="beca", formato="rss", frecuencia=72, prioridad=4, config={"palabras_clave": ["convocatoria", "postula"]},
         condiciones="robots.txt solo bloquea /wp-admin/ e /inicio/*.",
         observaciones="RSS real (WordPress) pero desactualizado: el último elemento era de marzo de 2025 y "
                       "eran testimonios, no convocatorias. Baja prioridad."),
    dict(nombre="SERVIR – Talento Perú (convocatorias del Estado)", inst="servir", zona=None,
         url_principal="https://app.servir.gob.pe/DifusionOfertasExterno/faces/consultas/ofertas_laborales.xhtml",
         url_listado=None, tipo="empleo", formato="otro", frecuencia=24, prioridad=1, config={},
         estado="manual",
         condiciones="El sitio usa protección antibots (Incapsula). PorSiAcaso NO la elude: consulta manual.",
         observaciones="Fuente principal de empleo público. Revisar manualmente y publicar con el formulario."),
]


# ---------------------------------------------------------------------------
# Segunda tanda (pedida por el propietario el 13/10/2026). Verificadas con el descargador del
# Autopilot: todas responden 200 y su robots.txt permite la lectura automatizada.
INSTITUCIONES.update({
    "cultura": ("Ministerio de Cultura", "MINCUL", "publico", "https://www.gob.pe/cultura"),
    "agrorural": ("Programa de Desarrollo Productivo Agrario Rural", "AGRO RURAL", "publico",
                  "https://www.gob.pe/agrorural"),
    "grtpe": ("Gerencia Regional de Trabajo y Promoción del Empleo – Lambayeque", "GRTPE Lambayeque", "publico",
              "https://www.gob.pe/institucion/regionlambayeque-grtpe"),
    "gre": ("Gerencia Regional de Educación - Lambayeque", "GRE Lambayeque", "publico",
            "https://www.gob.pe/institucion/regionlambayeque-gre"),
    "geresa": ("Gerencia Regional de Salud Lambayeque", "GERESA Lambayeque", "publico",
               "https://www.gob.pe/institucion/regionlambayeque-geresa"),
    "mtpe": ("Ministerio de Trabajo y Promoción del Empleo", "MTPE", "publico", "https://www.gob.pe/mtpe"),
    "proinnovate": ("Programa Nacional de Innovación y Desarrollo Productivo - ProInnóvate", "ProInnóvate", "publico",
                    "https://www.gob.pe/institucion/proinnovate"),
    "ue008": ("Ministerio de Cultura – Unidad Ejecutora N° 008", "MINCUL UE 008", "publico",
              "https://www.proyectoscultura.gob.pe/"),
})
CAMPANAS = r"campa(?:%C3%B1|ñ)as/(\d+)"

FUENTES += [
    dict(nombre="PRONABEC – Becas (campañas de gob.pe)", inst="pronabec", zona=None,
         url_principal="https://www.gob.pe/pronabec",
         url_listado="https://www.gob.pe/institucion/pronabec/campa%C3%B1as",
         tipo="beca", formato="html", frecuencia=24, prioridad=1,
         config={"patron_enlace": r"/institucion/pronabec/campa(%C3%B1|ñ)as/\d+", "patron_id": CAMPANAS,
                 "excluir": ["resultados", "ganadores", "seleccionados"], "max_items": 30},
         condiciones=ROBOTS_GOBPE, observaciones="Cada campaña es una beca. Las páginas permanentes sin fecha de "
                                                 "cierre ni enlace de postulación se descartan."),
    dict(nombre="Ministerio de Cultura – CAS vigentes", inst="cultura", zona=None,
         url_principal="https://convocatorias.cultura.gob.pe/cas-vigente",
         url_listado="https://plataformamincu.cultura.gob.pe/POST_CAST/Gestion/LISTADO_PUBLICACION?NTC=1&NOPT=1",
         tipo="empleo", formato="json", frecuencia=24, prioridad=1,
         config={"plantilla_url": "{RUTA_CARPETA}{BASES}", "plantilla_titulo": "Convocatoria CAS N° {SPROCESO} – {SSERVICIO}",
                 "plantilla_resumen": "{NPLAZAS} plaza(s) en {SEDE}. {SOFICINA}.", "campos": {"id": "SPROCESO"},
                 "excluir": ["cancelado"], "enlace_extra": "https://plataformamincu.cultura.gob.pe/POST_CAST/User/Login",
                 "texto_enlace_extra": "Postulación en línea"},
         condiciones="La página convocatorias.cultura.gob.pe carga su lista desde el listado público "
                     "plataformamincu.cultura.gob.pe/POST_CAST/Gestion/LISTADO_PUBLICACION (NTC=1 CAS, NOPT=1 vigentes). "
                     "robots.txt permite todo. No se usa ninguna sesión.",
         observaciones="Adaptador JSON con plantillas. Al 13/10/2026 la lista de vigentes estaba vacía "
                       "(22 en evaluación, 1733 finalizadas)."),
    dict(nombre="AGRO RURAL – Convocatorias CAS 2026 (gob.pe)", inst="agrorural", zona=None,
         url_principal="https://www.gob.pe/agrorural", url_listado="https://www.gob.pe/109656-convocatorias-cas-2026",
         tipo="empleo", formato="html", frecuencia=24, prioridad=1,
         config={"modo": "procesos", "patron_bloque": r"Proceso de Selecci[oó]n N", "excluir_bloque": ["resultado"]},
         condiciones=ROBOTS_GOBPE,
         observaciones="Página con un bloque por proceso. Se omiten los procesos que ya muestran resultados; "
                       "se sigue un salto a «Bases» y «Cronograma» para leer sus PDF."),
    dict(nombre="GRTPE Lambayeque – Concursos (campañas de gob.pe)", inst="grtpe", zona="lambayeque",
         url_principal="https://www.gob.pe/institucion/regionlambayeque-grtpe",
         url_listado="https://www.gob.pe/institucion/regionlambayeque-grtpe/campa%C3%B1as",
         tipo="convocatoria", formato="html", frecuencia=24, prioridad=1,
         config={"patron_enlace": r"/institucion/regionlambayeque-grtpe/campa(%C3%B1|ñ)as/\d+", "patron_id": CAMPANAS,
                 "palabras_clave": ["concurso", "convocatoria", "cas", "practicas"],
                 "excluir": ["suspension", "sindicato", "integridad", "tiempo parcial"]},
         condiciones=ROBOTS_GOBPE, observaciones="Las campañas mezclan convocatorias con avisos laborales."),
    dict(nombre="GRE Lambayeque – Convocatoria CAS (página única)", inst="gre", zona="lambayeque",
         url_principal="https://www.gob.pe/institucion/regionlambayeque-gre",
         url_listado="https://www.gob.pe/institucion/regionlambayeque-gre/campa%C3%B1as/140091-convocatoria-cas",
         tipo="convocatoria", formato="html", frecuencia=24, prioridad=2, config={"modo": "pagina_unica"},
         condiciones=ROBOTS_GOBPE, observaciones="La URL es una sola convocatoria; se revisa si publicó resultados."),
    dict(nombre="GERESA Lambayeque – Proceso CAS N° 001-2026 (página única)", inst="geresa", zona="lambayeque",
         url_principal="https://www.gob.pe/institucion/regionlambayeque-geresa",
         url_listado="https://www.gob.pe/institucion/regionlambayeque-geresa/informes-publicaciones/7923140-proceso-de-convocatoria-cas-n-001-2026",
         tipo="convocatoria", formato="html", frecuencia=24, prioridad=2, config={"modo": "pagina_unica"},
         condiciones=ROBOTS_GOBPE, observaciones="La URL es una sola convocatoria; se revisa si publicó resultados."),
    dict(nombre="MTPE – Eventos Empleos Perú", inst="mtpe", zona=None,
         url_principal="https://www.gob.pe/institucion/mtpe/pages/110489-eventos-empleos-peru",
         url_listado="https://eventosempleosperu.trabajo.gob.pe", tipo="empleo", formato="otro", frecuencia=72,
         prioridad=3, config={}, estado="manual",
         condiciones="La página de gob.pe describe el servicio; los eventos están en eventosempleosperu.trabajo.gob.pe, "
                     "una aplicación JavaScript sin texto ni fuente de datos pública identificable.",
         observaciones="Consulta manual: no lista eventos concretos que se puedan leer de forma automatizada."),
    dict(nombre="ProInnóvate – Concursos (campañas de gob.pe)", inst="proinnovate", zona=None,
         url_principal="https://www.gob.pe/institucion/proinnovate",
         url_listado="https://www.gob.pe/institucion/proinnovate/campa%C3%B1as",
         tipo="bono", formato="html", frecuencia=48, prioridad=3,
         config={"patron_enlace": r"/institucion/proinnovate/campa(%C3%B1|ñ)as/\d+", "patron_id": CAMPANAS,
                 "palabras_clave": ["concurso", "convocatoria", "fondo", "financiamiento", "iniciativa"],
                 "excluir": ["resultados", "ganadores"]},
         condiciones=ROBOTS_GOBPE,
         observaciones="Concursos de financiamiento para empresas y emprendedores (tipo «beneficio»): siempre revisión humana."),
    dict(nombre="Ministerio de Cultura UE 008 – CAS del año (tabla)", inst="ue008", zona=None,
         url_principal="https://www.proyectoscultura.gob.pe/cas.php",
         url_listado="https://www.proyectoscultura.gob.pe/controladores/cas.controlador.php?operacion=listabasica&anio={anio}",
         tipo="empleo", formato="html", frecuencia=24, prioridad=2,
         config={"modo": "tabla", "base_enlaces": "https://www.proyectoscultura.gob.pe/",
                 "excluir_fila_enlace": r"EVAL|FINALIZADO|RESULT",
                 "enlace_extra": "https://plataformamincu.cultura.gob.pe/POST_CAST/User/Login",
                 "texto_enlace_extra": "Postulación en línea"},
         condiciones="cas.php carga su tabla desde controladores/cas.controlador.php (misma web, robots.txt permite). "
                     "{anio} se reemplaza por el año en curso.",
         observaciones="Se omiten las filas con evaluaciones o finalizadas. Cada fila apunta al PDF del perfil."),
]

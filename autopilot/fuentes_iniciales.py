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

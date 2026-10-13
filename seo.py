"""Datos estructurados JSON-LD. Solo se genera marcado con datos reales y aplicables.

JobPosting sigue https://developers.google.com/search/docs/appearance/structured-data/job-posting
"""
from models import lineas
from utils import texto_plano
from tipos import TIPOS, NIVELES_EDUCATIVOS, nombre_opcion

SITIO = "Por Si Acaso"

# Correspondencia con los valores admitidos por Google (EducationalOccupationalCredential)
CREDENCIALES = {"secundaria": "high school", "tecnico": "associate degree",
                "bachiller": "bachelor degree", "titulado": "bachelor degree",
                "posgrado": "postgraduate degree"}
JORNADA_A_TIPO = {"completa": "FULL_TIME", "parcial": "PART_TIME", "por_horas": "PER_DIEM"}
CONTRATO_A_TIPO = {"practicas": "INTERN", "plazo_fijo": "TEMPORARY", "cas": "TEMPORARY",
                   "locacion": "CONTRACTOR"}
LARGO_MINIMO_DESCRIPCION = 150


def organizacion(abs_url):
    return {"@context": "https://schema.org", "@type": "Organization", "name": SITIO,
            "url": abs_url("web.inicio"),
            "logo": abs_url("static", filename="img/logo-600.png")}


def sitio_web(abs_url):
    return {"@context": "https://schema.org", "@type": "WebSite", "name": SITIO,
            "alternateName": "PorSiAcaso", "url": abs_url("web.inicio")}


def migas(items):
    """items = [(nombre, url_absoluta_o_None), ...]"""
    elementos = []
    for i, (nombre, url) in enumerate(items, 1):
        e = {"@type": "ListItem", "position": i, "name": nombre}
        if url:
            e["item"] = url
        elementos.append(e)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": elementos}


def articulo(a, url, imagen_url, abs_url):
    return {
        "@context": "https://schema.org",
        "@type": "NewsArticle" if a.tipo == "noticia" else "Article",
        "headline": a.titulo[:110],
        "description": a.resumen or a.titulo,
        "image": [imagen_url],
        "datePublished": a.iso_publicado,
        "dateModified": a.iso_actualizado,
        "author": {"@type": "Person", "name": a.autor.nombre},
        "publisher": {"@type": "Organization", "name": SITIO,
                      "logo": {"@type": "ImageObject",
                               "url": abs_url("static", filename="img/logo-600.png")}},
        "mainEntityOfPage": url,
    }


def descripcion_empleo_html(a):
    """Descripción completa (contenido + listas estructuradas) para JobPosting."""
    d = a.detalle_empleo
    partes = [a.contenido or ""]
    for titulo, campo in (("Funciones", "funciones"), ("Formación", "formacion"),
                          ("Experiencia", "experiencia"), ("Competencias", "competencias")):
        items = lineas(getattr(d, campo))
        if items:
            partes.append(f"<p><strong>{titulo}</strong></p><ul>"
                          + "".join(f"<li>{_esc(i)}</li>" for i in items) + "</ul>")
    return "".join(partes)


def _esc(texto):
    return (texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def motivos_sin_jobposting(a):
    """Lista de motivos por los que una publicación NO lleva JobPosting (vacía = sí lo lleva)."""
    motivos = []
    d = a.detalle_empleo
    if a.tipo != "empleo":
        return ["Solo las publicaciones de tipo Empleo (una vacante concreta) usan JobPosting."]
    if a.estado != "publicado":
        motivos.append("No está publicada.")
    if a.situacion in ("vencida", "cerrada", "archivada"):
        motivos.append("La convocatoria ya no está vigente.")
    if a.situacion == "por_confirmar":
        motivos.append("Está marcada como pendiente de verificación.")
    if not a.verificado_en:
        motivos.append("Falta la fecha de verificación en la fuente oficial.")
    if not a.institucion:
        motivos.append("Falta la empresa o institución.")
    if not d or not d.cargo:
        motivos.append("Falta el nombre del puesto.")
    if d and d.modalidad != "remoto" and not a.ubicacion:
        motivos.append("Falta la ubicación (o marca la modalidad como remota).")
    if d and len(texto_plano(descripcion_empleo_html(a))) < LARGO_MINIMO_DESCRIPCION:
        motivos.append("La descripción del puesto es demasiado corta.")
    if not (a.enlace_principal or a.fuente_url):
        motivos.append("Falta el enlace para postular o la fuente oficial.")
    return motivos


def oferta_empleo(a, url, abs_url, logo_url=None):
    """JSON-LD JobPosting o None si no cumple todas las condiciones."""
    if motivos_sin_jobposting(a):
        return None
    d, inst = a.detalle_empleo, a.institucion
    org = {"@type": "Organization", "name": inst.nombre}
    if inst.web:
        org["sameAs"] = inst.web
    if logo_url:
        org["logo"] = logo_url

    datos = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": d.cargo,
        "description": descripcion_empleo_html(a),
        "datePosted": a.fecha_publicacion.date().isoformat(),
        "hiringOrganization": org,
        "directApply": False,
        "url": url,
    }
    if a.fecha_limite:
        datos["validThrough"] = a.fecha_limite.isoformat() + "T23:59:59-05:00"

    if d.modalidad in ("remoto", "hibrido"):
        datos["jobLocationType"] = "TELECOMMUTE"
        datos["applicantLocationRequirements"] = {"@type": "Country", "name": "Perú"}
    if d.modalidad != "remoto" and a.ubicacion:
        u = a.ubicacion
        direccion = {"@type": "PostalAddress", "addressCountry": "PE",
                     "addressRegion": u.region.nombre}
        if u.tipo == "ciudad":
            direccion["addressLocality"] = u.nombre
        if d.lugar:
            direccion["streetAddress"] = d.lugar
        datos["jobLocation"] = {"@type": "Place", "address": direccion}

    tipos_empleo = [x for x in (JORNADA_A_TIPO.get(d.jornada), CONTRATO_A_TIPO.get(d.tipo_contrato))
                    if x]
    if tipos_empleo:
        datos["employmentType"] = tipos_empleo if len(tipos_empleo) > 1 else tipos_empleo[0]

    if d.sueldo_min is not None:
        valor = {"@type": "QuantitativeValue", "unitText": "MONTH"}
        if d.sueldo_max is not None and d.sueldo_max != d.sueldo_min:
            valor.update(minValue=float(d.sueldo_min), maxValue=float(d.sueldo_max))
        else:
            valor["value"] = float(d.sueldo_min)
        datos["baseSalary"] = {"@type": "MonetaryAmount", "currency": d.moneda or "PEN",
                               "value": valor}
    if d.codigo:
        datos["identifier"] = {"@type": "PropertyValue", "name": inst.nombre, "value": d.codigo}
    if d.vacantes:
        datos["totalJobOpenings"] = d.vacantes
    if d.nivel_educativo in CREDENCIALES:
        datos["educationRequirements"] = {
            "@type": "EducationalOccupationalCredential",
            "credentialCategory": CREDENCIALES[d.nivel_educativo]}
    elif d.nivel_educativo == "sin_requisito":
        datos["educationRequirements"] = "no requirements"
    if a.imagen:
        datos["image"] = abs_url("static", filename="uploads/" + a.imagen)
    return datos


def tipo_nombre(tipo):
    return TIPOS.get(tipo, TIPOS["noticia"])["nombre"]


def nivel_nombre(clave):
    return nombre_opcion(NIVELES_EDUCATIVOS, clave)

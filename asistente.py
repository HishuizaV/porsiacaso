"""Asistente PorSiAcaso: orientación por reglas sobre el contenido publicado.

No usa servicios de IA: detecta la intención con palabras clave, reconoce la zona,
busca en las publicaciones vigentes y devuelve solo enlaces internos reales.
No guarda las conversaciones.
"""
import re
from urllib.parse import urlparse

from flask import Blueprint, request, jsonify, url_for, abort

import ajustes
from consultas import listar, buscar_zona, zonas_con_contenido, terminos
from models import Ubicacion
from seguridad import Limitador, exento_csrf, ip_cliente
from tipos import TIPOS
from utils import normalizar
from web import url_publicacion

api = Blueprint("api", __name__, url_prefix="/api")

LIMITE_IP = Limitador(20, 60)       # 20 mensajes por minuto por visitante
LIMITE_GLOBAL = Limitador(600, 60)  # protección general
MAX_LARGO = 300

# Palabra clave (normalizada) -> tipos de publicación
INTENCIONES = [
    (("trabajo", "trabajos", "empleo", "empleos", "chamba", "chambas", "vacante", "vacantes",
      "puesto", "puestos", "laboral", "laborales", "cas", "practicas", "practicante",
      "practicantes", "contratan", "sueldo"), ("empleo", "convocatoria")),
    (("convocatoria", "convocatorias", "concurso"), ("convocatoria", "empleo", "educativa")),
    (("beca", "becas", "pronabec", "estudiar", "estudios", "universidad"), ("beca", "educativa")),
    (("admision", "ingreso", "docente", "docentes"), ("educativa",)),
    (("curso", "cursos", "capacitacion", "capacitaciones", "taller", "talleres", "aprender",
      "diplomado", "certificacion"), ("curso",)),
    (("bono", "bonos", "subsidio", "subsidios", "beneficio", "beneficios", "ayuda", "apoyo",
      "pension", "programa", "social"), ("bono",)),
    (("tramite", "tramites", "dni", "partida", "brevete", "licencia", "pasaporte", "ruc",
      "antecedentes", "duplicado", "reniec", "sunat", "sacar", "renovar"), ("tramite", "guia")),
    (("guia", "guias", "consejo", "consejos"), ("guia",)),
    (("noticia", "noticias", "actualidad"), ("noticia",)),
]
PALABRAS_INTENCION = {p for claves, _ in INTENCIONES for p in claves}
SALUDOS = {"hola", "buenas", "buenos", "dias", "tardes", "noches", "hey", "saludos", "ola"}
TODO_PERU = ("todo el peru", "todo peru", "nacional", "cualquier lugar", "cualquier region",
             "remoto", "en todo el pais")
RE_SENSIBLE = re.compile(r"\b\d{8}\b|\b(?:\d[ -]?){13,19}\b|contrasena|password|clave secreta|"
                         r"cuenta bancaria|tarjeta de credito|cvv", re.I)
OPCIONES_INICIO = [("Busco trabajo", "Busco trabajo"), ("Becas", "Quiero becas para estudiar"),
                   ("Cursos", "Cursos"), ("Bonos", "Bonos y beneficios"), ("Trámites", "Trámites")]


def detectar_tipos(texto_norm):
    """La intención con más palabras clave gana; en empate, la primera de la lista."""
    palabras = set(texto_norm.split())
    mejor, puntos = [], 0
    for claves, tipos in INTENCIONES:
        n = len(palabras & set(claves))
        if n > puntos:
            mejor, puntos = list(tipos), n
    return mejor


def _resultado(a):
    meta = []
    if a.institucion:
        meta.append(a.institucion.nombre_corto)
    if a.ubicacion:
        meta.append(a.ubicacion.nombre)
    if a.fecha_limite:
        meta.append("Cierra: " + a.fecha_limite.strftime("%d/%m/%Y"))
    return {"titulo": a.titulo, "url": url_publicacion(a), "tipo": a.info["nombre"],
            "meta": " · ".join(meta)}


def _opciones(pares):
    return [{"texto": t, "valor": v} for t, v in pares]


def responder(mensaje, estado):
    """Lógica principal. Devuelve un dict serializable (sin HTML)."""
    texto = normalizar(mensaje)
    if not texto:
        return {"respuesta": "Escribe qué necesitas, por ejemplo: «trabajo en Chiclayo».",
                "opciones": _opciones(OPCIONES_INICIO)}

    if RE_SENSIBLE.search(mensaje) or RE_SENSIBLE.search(texto):
        return {"respuesta": "Por tu seguridad, no compartas tu DNI, contraseñas ni datos "
                             "bancarios. No los necesito: solo dime qué tipo de información "
                             "buscas y en qué región.",
                "opciones": _opciones(OPCIONES_INICIO)}

    palabras = set(texto.split())
    if palabras <= SALUDOS or texto in ("ayuda", "quien eres", "que eres", "menu"):
        return {"respuesta": "Hola, soy el Asistente PorSiAcaso, un asistente automático. "
                             "Te ayudo a encontrar empleos, becas, cursos, bonos y trámites "
                             "publicados en este sitio. ¿Qué buscas?",
                "opciones": _opciones(OPCIONES_INICIO)}

    tipos = detectar_tipos(texto)
    if not tipos and estado.get("intencion") in TIPOS:
        tipos = [t for t in estado.get("tipos", []) if t in TIPOS] or [estado["intencion"]]

    zona = buscar_zona(mensaje)
    if zona is None and estado.get("region"):
        zona = Ubicacion.query.filter_by(slug=str(estado["region"])[:80]).first()
    todo_peru = any(f in texto for f in TODO_PERU) or estado.get("todo_peru") is True

    zona_palabras = set(normalizar(zona.nombre).split()) if zona else set()
    clave = [p for p in terminos(mensaje)
             if p not in PALABRAS_INTENCION and p not in zona_palabras and p not in SALUDOS
             and p not in ("peru", "todo", "region", "ciudad", "nacional")]

    nuevo_estado = {"intencion": tipos[0] if tipos else None, "tipos": tipos,
                    "region": zona.slug if zona else None, "todo_peru": todo_peru}

    # Para empleo la región es clave: se pregunta una vez si no se indicó
    if tipos and tipos[0] == "empleo" and zona is None and not todo_peru and not clave:
        regiones = zonas_con_contenido("empleo")[:6]
        opciones = [(r.nombre, f"En {r.nombre}") for r, _ in regiones] + [("Todo el Perú", "Todo el Perú")]
        return {"respuesta": "Puedo mostrarte las ofertas de empleo vigentes. ¿En qué región "
                             "buscas trabajo? También puedes decirme el puesto (ej.: «secretaria»).",
                "opciones": _opciones(opciones), "estado": nuevo_estado}

    q = " ".join(clave)
    consulta = listar(tipo=tipos or None, q=q, zona=zona, vigencia="vigentes",
                      orden="relevancia" if q else "recientes")
    encontrados = consulta.limit(5).all()
    total = consulta.count() if encontrados else 0
    aviso_sin_palabras = False
    if not encontrados and q and tipos:
        consulta = listar(tipo=tipos, zona=zona, vigencia="vigentes")
        encontrados = consulta.limit(5).all()
        total = consulta.count() if encontrados else 0
        aviso_sin_palabras = bool(encontrados)

    nombre = TIPOS[tipos[0]]["plural"].lower() if tipos else "publicaciones"
    lugar = f" en {zona.nombre}" if zona else ""
    enlace = None
    if tipos:
        args = {"tipo": tipos[0]}
        if q:
            args["q"] = q
        if zona is not None:
            args["region"] = zona.slug
        enlace = {"texto": f"Ver todo en {TIPOS[tipos[0]]['plural']}",
                  "url": url_for("web.seccion", **args)}
    elif q:
        enlace = {"texto": "Ver resultados en el buscador", "url": url_for("web.buscar", q=q)}

    if not encontrados:
        texto_resp = (f"No encontré {nombre} vigentes{lugar}"
                      + (f" que coincidan con «{q}»" if q else "")
                      + " publicadas ahora mismo. No invento resultados: puedes revisar la "
                        "sección completa o probar con otra región.")
        return {"respuesta": texto_resp, "resultados": [], "enlace": enlace,
                "opciones": _opciones(OPCIONES_INICIO), "estado": nuevo_estado}

    if aviso_sin_palabras:
        texto_resp = (f"No hallé coincidencias exactas con «{q}», pero estas son {nombre} "
                      f"vigentes{lugar}:")
    else:
        texto_resp = f"Encontré {total} {nombre if total != 1 else 'resultado'} vigente(s){lugar}"
        texto_resp += f" para «{q}»:" if q else ":"
    if total > 5:
        texto_resp += " Te muestro las 5 más relevantes."
    return {"respuesta": texto_resp, "resultados": [_resultado(a) for a in encontrados],
            "enlace": enlace, "estado": nuevo_estado}


def _mismo_origen():
    origen = request.headers.get("Origin") or request.headers.get("Referer")
    if not origen:
        return True
    return urlparse(origen).netloc == request.host


@api.route("/asistente", methods=["POST"])
@exento_csrf
def asistente():
    if ajustes.obtener("asistente_activo") == "0":
        abort(404)
    if not _mismo_origen():
        abort(403)
    if (request.content_length or 0) > 4096 or not request.is_json:
        abort(400)
    if not LIMITE_GLOBAL.permitir("global") or not LIMITE_IP.permitir(ip_cliente()):
        return jsonify({"respuesta": "Estás enviando muchos mensajes. Espera un minuto.",
                        "error": "limite"}), 429
    datos = request.get_json(silent=True) or {}
    mensaje = datos.get("mensaje")
    estado = datos.get("estado") if isinstance(datos.get("estado"), dict) else {}
    if not isinstance(mensaje, str):
        abort(400)
    mensaje = re.sub(r"[\x00-\x1f\x7f]", " ", mensaje)[:MAX_LARGO]
    resp = responder(mensaje, estado)
    resp.setdefault("resultados", [])
    resp.setdefault("estado", estado)
    return jsonify(resp)

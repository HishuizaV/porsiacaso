"""Agente editor de calidad y política de autopublicación.

Decisiones posibles:
  rechazar      -> no se crea ficha (vencida, sin institución, no es oportunidad, sin evidencia)
  revision      -> se crea borrador en «Pendiente de revisión» para una persona
  autopublicable-> cumple TODAS las comprobaciones y la política autorizada por el administrador

La puntuación de relevancia sirve para ordenar; nunca autoriza por sí sola una publicación.
"""
import json

import ajustes
from tipos import TIPOS

NUNCA_AUTOPUBLICAR = {"bono", "noticia", "guia", "otro"}   # siempre revisión humana
TIPOS_MODO_B = {"empleo", "convocatoria", "curso"}
REQUISITOS_POLITICA = [
    ("pruebas", "Ejecuté las pruebas automáticas y pasaron"),
    ("muestras", "Revisé muestras reales generadas por el Autopilot"),
    ("fuentes", "Las fuentes con autopublicación están autorizadas para extracción y reutilización"),
    ("botones", "Comprobé que los botones llevan a las páginas oficiales correctas"),
    ("duplicados", "Comprobé que no se crean publicaciones duplicadas"),
    ("politica", "Leí y acepto la política editorial de autopublicación"),
]


def configuracion():
    def entero(clave, defecto, minimo, maximo):
        try:
            return max(minimo, min(maximo, int(ajustes.obtener(clave) or defecto)))
        except ValueError:
            return defecto
    try:
        politica = json.loads(ajustes.obtener("autopilot_politica") or "{}")
    except ValueError:
        politica = {}
    lista = lambda c: [x for x in (ajustes.obtener(c) or "").split(",") if x]  # noqa: E731
    return {
        "modo": ajustes.obtener("autopilot_modo") if ajustes.obtener("autopilot_modo") in ("A", "B", "C") else "A",
        "tipos_auto": [t for t in lista("autopilot_tipos_auto") if t in TIPOS and t not in NUNCA_AUTOPUBLICAR],
        "duracion": entero("autopilot_duracion", 120, 10, 120),
        "objetivo": entero("autopilot_objetivo", 12, 1, 30),
        "tipos": [t for t in lista("autopilot_tipos") if t in TIPOS],
        "regiones": lista("autopilot_regiones"),
        "espaciado": entero("autopilot_espaciado", 30, 0, 240),
        "concurrencia": entero("autopilot_concurrencia", 2, 1, 4),
        "ia": ajustes.obtener("autopilot_ia") == "1",
        "ia_modelo": ajustes.obtener("autopilot_ia_modelo") or "llama3.2:3b",
        "politica": politica,
        "politica_completa": all(politica.get(k) for k, _ in REQUISITOS_POLITICA),
    }


def puede_autopublicar(tipo, fuente, cfg):
    """(bool, motivo). La autopublicación exige modo B/C, política aceptada y fuente autorizada."""
    if cfg["modo"] == "A":
        return False, "Modo A: todo queda para revisión humana."
    if not cfg["politica_completa"]:
        return False, "El administrador no completó la lista de requisitos para autopublicar."
    if tipo in NUNCA_AUTOPUBLICAR:
        return False, f"Las publicaciones de tipo «{TIPOS[tipo]['nombre']}» siempre requieren revisión."
    if not (fuente and fuente.permite_autopublicacion and fuente.permite_extraccion and fuente.confianza == "alta"):
        return False, "La fuente no está autorizada para autopublicación."
    if tipo not in cfg["tipos_auto"]:
        return False, f"El tipo «{TIPOS[tipo]['nombre']}» no está autorizado para autopublicación."
    if cfg["modo"] == "B" and tipo not in TIPOS_MODO_B:
        return False, "El modo B solo autopublica empleos, convocatorias y cursos."
    return True, ""


def evaluar(tipo, borrador, datos, enlaces_verificados, problemas_fechas, sospechas, relev, fuente,
            institucion, cfg):
    """Devuelve (decision, checklist[(texto, ok, gravedad)], motivos)."""
    info = TIPOS[tipo]
    lista = []

    def check(texto, ok, gravedad="revision"):
        lista.append((texto, bool(ok), gravedad))

    check("Fuente oficial de confianza alta", fuente.confianza == "alta")
    check("Institución identificada", institucion is not None, "bloqueo")
    check("Título descriptivo (20–90 caracteres)", 20 <= len(borrador["titulo"]) <= 90)
    check("Resumen útil (60 caracteres o más)", len(borrador["resumen"]) >= 60)
    for _t, campos in info["campos"]:
        for c in campos:
            if c["requerido"]:
                check(f"Dato obligatorio «{c['etiqueta']}»", borrador["detalle"].get(c["nombre"]) not in (None, ""))
    if info["oportunidad"]:
        check("Fecha límite encontrada en la fuente", borrador["fecha_limite"] is not None)
    principal = [e for e in enlaces_verificados if e[0] in (info["cta"], "convocatoria", "oficial")]
    check("La página oficial de la convocatoria responde", any(e[3] for e in principal), "bloqueo")
    if info["cta"]:
        check(f"Botón principal «{info['cta']}» verificado",
              any(e[0] == info["cta"] and e[3] for e in enlaces_verificados))
    check("Todos los botones mostrados responden", all(e[3] is not False for e in enlaces_verificados))
    check("Sin datos contradictorios", not any(d.estado == "contradictorio" for d in datos.values()))
    # Lo que aporta la IA (aunque el texto aparezca en la fuente) siempre lo revisa una persona:
    # la IA eligió qué fragmento corresponde a cada dato.
    check("Sin datos aportados por IA", not any(d.estado == "inferido" or (d.metodo or "").startswith("ia")
                                                for d in datos.values()))
    check("Sin instrucciones sospechosas en la fuente", not sospechas)
    check("Es una oportunidad o información útil (no testimonio ni nota)", relev >= 30, "bloqueo")
    largo = len(borrador["contenido"]) + sum(len(str(v)) for v in borrador["detalle"].values())
    check("Información suficiente (no es una página vacía)", largo >= 250)
    if info["oportunidad"] and borrador["fecha_limite"] is None and largo < 250:
        # Sin fecha de cierre y casi sin datos: no hay evidencia suficiente para una ficha útil
        check("Hay evidencia suficiente (fecha de cierre o información sustancial)", False, "bloqueo")
    for gravedad, msg in problemas_fechas:
        check(msg, False, "bloqueo" if gravedad == "bloqueo" else "revision")

    motivos = [t for t, ok, g in lista if not ok]
    if any(not ok and g == "bloqueo" for _t, ok, g in lista):
        return "rechazar", lista, motivos
    if motivos:
        return "revision", lista, motivos
    permitido, motivo = puede_autopublicar(tipo, fuente, cfg)
    if not permitido:
        return "revision", lista, [motivo]
    return "autopublicable", lista, []

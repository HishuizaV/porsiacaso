"""Agente clasificador: tipo, región, relevancia, prioridad y señales de riesgo.

Solo reglas deterministas. El texto de las fuentes se trata como dato: nunca se ejecutan
ni se obedecen instrucciones que contenga.
"""
import re

from utils import normalizar

# Frases típicas de intentos de manipular un sistema automático (inyección de instrucciones)
PATRONES_INYECCION = [
    r"ignora(r)? (todas )?(las )?instrucciones", r"ignore (all |any )?(previous |prior )?instructions",
    r"olvida (todo|las instrucciones)", r"system prompt", r"prompt del sistema", r"eres un modelo",
    r"you are (an? )?(ai|assistant|language model)", r"act[uú]a como", r"publica (esto|inmediatamente)",
    r"desactiva (la )?(revision|verificacion)", r"disable (the )?(review|verification)",
    r"<\s*/?\s*(system|assistant|instruction)", r"\bBEGIN (SYSTEM|INSTRUCTIONS)\b",
    r"aprob(ar|ado) autom[aá]ticamente", r"sin revisi[oó]n humana",
]
RE_INYECCION = re.compile("|".join(PATRONES_INYECCION), re.I)

SENALES = {
    "convocatoria": r"\b(convocatoria (cas|728|276|publica)|concurso publico|proceso de seleccion|plazas)\b",
    "empleo": r"\b(empleo|puesto|vacante|se requiere|ofrecemos|remuneracion|trabaja con nosotros)\b",
    "beca": r"\b(beca|becas|becario|pronabec|credito educativo)\b",
    "educativa": r"\b(admision|examen de admision|concurso docente|nombramiento docente)\b",
    "curso": r"\b(curso|cursos|taller|capacitacion|diplomado|mooc|ficha academica)\b",
    "bono": r"\b(bono|subsidio|beneficiarios|padron|cobro|programa social)\b",
    "tramite": r"\b(tramite|tramitar|requisitos para obtener|procedimiento administrativo|tupa)\b",
}
# Textos que no son oportunidades: testimonios, notas institucionales, ganadores…
NO_OPORTUNIDAD = r"\b(testimonio|historia de|conoce a|ganadores|ganador|resultados finales|lista de ganadores|" \
                 r"exbecarios?|gracias a|egresad[oa]s? (cuenta|comparte))\b|[«“\"][^»”\"]{15,}[»”\"]\s*$"


def inyeccion(texto):
    """Fragmentos sospechosos (para advertir y forzar revisión humana)."""
    return [m.group(0) for m in RE_INYECCION.finditer(texto or "")][:5]


def detectar_tipo(titulo, texto, tipo_fuente, vacantes=None):
    t = normalizar(titulo) + " " + normalizar((texto or "")[:3000])
    puntos = {k: len(re.findall(p, t)) for k, p in SENALES.items()}
    puntos[tipo_fuente] = puntos.get(tipo_fuente, 0) + 2   # la fuente configurada pesa
    tipo = max(puntos, key=puntos.get)
    if tipo == "empleo" and vacantes and vacantes > 1:
        tipo = "convocatoria"   # varias plazas: una sola ficha de convocatoria, no N páginas
    if tipo == "convocatoria" and vacantes == 1 and tipo_fuente == "empleo":
        tipo = "empleo"
    return tipo


DOCUMENTO_ADMINISTRATIVO = r"^(acta|circular|convenio|fe de erratas|comunicado|resultados?|lista de|resolucion|" \
                           r"informe|oficio|memorando|ordenanza|acuerdo de concejo|suspension|cancelacion|sindicatos|contratos tiempo parcial|" \
                           r"servir con integridad)\b"


def parece_no_oportunidad(titulo, resumen=""):
    t = normalizar(titulo)
    return bool(re.search(NO_OPORTUNIDAD, t + " " + normalizar(resumen)) or re.search(DOCUMENTO_ADMINISTRATIVO, t))


def relevancia(datos, tipo, enlaces, hoy, titulo="", resumen=""):
    """Puntaje 0–100 con motivos legibles. Sirve para ordenar, NO para autorizar publicaciones."""
    puntos, motivos = 30, []
    fl = datos.get("fecha_limite")
    if fl is not None and fl.util:
        if fl.valor < hoy:
            return 0, ["La fecha límite ya pasó."]
        puntos += 25
        motivos.append("Tiene fecha límite vigente.")
    if any(t in ("postular", "bases") for t, _e, _u in enlaces):
        puntos += 20
        motivos.append("Tiene enlace de postulación o bases oficiales.")
    if any(d.util for k, d in datos.items() if k in ("requisitos", "formacion", "experiencia", "pasos")):
        puntos += 15
        motivos.append("Incluye requisitos o pasos.")
    if parece_no_oportunidad(titulo, resumen):
        puntos -= 60
        motivos.append("Parece una nota, acta, resultado o documento administrativo, no una oportunidad abierta.")
    tiene_accion = (fl is not None and fl.util) or any(t in ("postular", "bases", "inscripcion") for t, _e, _u in enlaces)
    if tipo in ("empleo", "convocatoria", "beca", "educativa", "curso") and not tiene_accion:
        puntos -= 40
        motivos.append("No tiene fecha de cierre ni enlace de postulación o bases: no parece una convocatoria abierta.")
    return max(0, min(100, puntos)), motivos


def prioridad(relev, fecha_lim, hoy):
    if fecha_lim and 0 <= (fecha_lim - hoy).days <= 5:
        return 1   # cierra pronto: se procesa primero
    return 2 if relev >= 60 else 3

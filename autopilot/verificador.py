"""Agente verificador: comprueba enlaces y fechas y detecta datos contradictorios.

Una respuesta de IA nunca convierte un dato en «confirmado»: solo la evidencia de la fuente.
"""
import re
from datetime import timedelta

from utils import url_valida


def verificar_enlaces(enlaces, descargador, limite=6):
    """[(tipo, etiqueta, url)] -> [(tipo, etiqueta, url, ok, detalle)].

    Se comprueban como máximo `limite` enlaces (los primeros son los más importantes)."""
    salida = []
    for i, (tipo, etiqueta, url) in enumerate(enlaces):
        if not url_valida(url):
            salida.append((tipo, etiqueta, url, False, "URL no válida"))
            continue
        if i >= limite:
            salida.append((tipo, etiqueta, url, None, "no comprobado (límite por ficha)"))
            continue
        ok, estado, detalle = descargador.comprobar_enlace(url)
        salida.append((tipo, etiqueta, url, ok, f"HTTP {estado}" if estado else detalle))
    return salida


DIAS_ANTIGUEDAD = 60
TIPOS_CON_CIERRE = ("empleo", "convocatoria", "beca", "educativa")


def anio_anterior_en_titulo(titulo, hoy):
    """«Beca Perú 2023» en 2026: la convocatoria de ese año ya pasó."""
    anios = [int(a) for a in re.findall(r"\b(20[1-9]\d)\b", titulo or "")]
    return max(anios) if anios and max(anios) < hoy.year else None


def verificar_fechas(datos, hoy, tipo=None, fecha_fuente=None, titulo=""):
    """Lista de (gravedad, mensaje). gravedad: bloqueo | revision | aviso."""
    problemas = []
    anio = anio_anterior_en_titulo(titulo, hoy)
    fl0 = datos.get("fecha_limite")
    if anio and tipo in TIPOS_CON_CIERRE + ("curso",) and not (fl0 is not None and fl0.util and fl0.valor >= hoy):
        problemas.append(("bloqueo", f"Es la convocatoria {anio} (un año anterior) y no tiene una fecha de cierre "
                                     "vigente: ya no está abierta."))
    fl, fi = datos.get("fecha_limite"), datos.get("fecha_inicio")
    fp = datos.get("fecha_publicacion")
    publicada = fp.valor if fp is not None and fp.util else fecha_fuente
    sin_cierre = fl is None or not fl.valor
    if sin_cierre and publicada and (hoy - publicada).days > DIAS_ANTIGUEDAD:
        if tipo in TIPOS_CON_CIERRE:
            problemas.append(("bloqueo", f"Publicada el {publicada:%d/%m/%Y} (hace más de {DIAS_ANTIGUEDAD} días) y sin "
                                         "fecha de cierre visible: probablemente ya no está vigente."))
        else:
            problemas.append(("revision", f"Publicada el {publicada:%d/%m/%Y} y sin fecha de cierre: confirma que sigue abierta."))
    if fl is not None and fl.valor:
        if fl.valor < hoy:
            problemas.append(("bloqueo", f"La convocatoria venció el {fl.valor:%d/%m/%Y}."))
        elif fl.valor > hoy + timedelta(days=400):
            problemas.append(("revision", "La fecha límite está a más de un año: puede ser un error de lectura."))
        if fl.estado == "contradictorio":
            problemas.append(("revision", "La fuente menciona fechas de cierre distintas."))
    if fi is not None and fi.valor and fl is not None and fl.valor and fi.valor < fl.valor - timedelta(days=60):
        problemas.append(("aviso", "La fecha de inicio es muy anterior al cierre."))
    return problemas


RE_ETAPA_CONCLUIDA = re.compile(
    r"resultados?[ _-]+(finales?|preliminares?|de[ _-]+(la[ _-]+)?(evaluaci|entrevista|etapa)|del[ _-]+proceso)|"
    r"cuadro[ _-]+(preliminar|final)|cuadro[ _-]+de[ _-]+resultados|resultado[ _-]+final|"
    r"declarad[oa][ _-]+desiert|(comunicado[ _-]+(de[ _-]+)?)?cancelaci[oó]n|proceso[ _-]+cancelado|\(cancelado\)|"
    r"postergaci[oó]n[ _-]+indefinida|suspensi[oó]n|(pre)?seleccionados|no[ _-]+aptos|postulantes[ _-]+aptos|"
    r"relaci[oó]n[ _-]+de[ _-]+becarios|lista[ _-]+de[ _-]+(ganadores|becarios)|ganadores", re.I)


def etapa_concluida(enlaces):
    """Si la convocatoria ya publicó resultados de evaluación o fue cancelada, la postulación terminó.
    Se mira solo el texto y la dirección de los DOCUMENTOS publicados (no los cronogramas futuros)."""
    for texto, url in enlaces:
        nombre = (texto or "") + " " + url.rsplit("/", 1)[-1]
        m = RE_ETAPA_CONCLUIDA.search(nombre)
        if m:
            motivo = "fue cancelada o suspendida" if re.search(r"cancel|suspens|postergaci", m.group(0), re.I) \
                else "ya publicó resultados de evaluación"
            return f"La convocatoria {motivo} («{m.group(0)}»): la etapa de postulación terminó."
    return None


def contradicciones(datos):
    return [f"El dato «{k}» aparece con valores distintos en la fuente." for k, d in datos.items()
            if d.estado == "contradictorio"]

"""Agente verificador: comprueba enlaces y fechas y detecta datos contradictorios.

Una respuesta de IA nunca convierte un dato en «confirmado»: solo la evidencia de la fuente.
"""
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


def verificar_fechas(datos, hoy, tipo=None, fecha_fuente=None):
    """Lista de (gravedad, mensaje). gravedad: bloqueo | revision | aviso."""
    problemas = []
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


def contradicciones(datos):
    return [f"El dato «{k}» aparece con valores distintos en la fuente." for k, d in datos.items()
            if d.estado == "contradictorio"]

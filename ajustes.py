"""Ajustes del sitio guardados en la tabla `ajuste` y editables desde el panel."""
import os
import re

from flask import g

from extensions import db
from models import Ajuste

# clave: (valor por defecto, descripción)
DEFINICION = {
    "anuncios_modo": ("off", "off | maqueta | adsense"),
    "adsense_cliente": ("", "ID de editor: ca-pub-XXXXXXXXXXXXXXXX"),
    "adsense_slot_superior": ("", "ID de bloque (solo números)"),
    "adsense_slot_articulo": ("", "ID de bloque (solo números)"),
    "adsense_slot_lateral": ("", "ID de bloque (solo números)"),
    "ads_txt": ("", "Contenido exacto de ads.txt indicado por AdSense"),
    "asistente_activo": ("1", "1 = visible, 0 = oculto"),
    "contacto_email": ("", "Correo público de contacto"),
    "facebook_url": ("", ""),
    "instagram_url": ("", ""),
    "tiktok_url": ("", ""),
    "youtube_url": ("", ""),
    "google_verificacion": ("", "Código de la etiqueta meta de Search Console"),
}

RE_CLIENTE = re.compile(r"^ca-pub-\d{16}$")
RE_SLOT = re.compile(r"^\d{6,12}$")


def _cargar():
    if "_ajustes" not in g:
        datos = {k: v for k, (v, _) in DEFINICION.items()}
        # Compatibilidad: la variable ANUNCIOS=off|maqueta|adsense sigue sirviendo como valor inicial
        entorno = os.environ.get("ANUNCIOS")
        if entorno in ("off", "maqueta", "adsense"):
            datos["anuncios_modo"] = entorno
        for a in Ajuste.query.all():
            datos[a.clave] = a.valor or ""
        g._ajustes = datos
    return g._ajustes


def obtener(clave):
    return _cargar().get(clave, "")


def todos():
    return dict(_cargar())


def guardar(valores):
    for clave, valor in valores.items():
        if clave not in DEFINICION:
            continue
        a = db.session.get(Ajuste, clave) or Ajuste(clave=clave)
        a.valor = (valor or "").strip()
        db.session.add(a)
    db.session.commit()
    g.pop("_ajustes", None)


def publicidad():
    """Estado efectivo de la publicidad. AdSense solo se activa con un ID válido."""
    modo = obtener("anuncios_modo")
    cliente = obtener("adsense_cliente")
    cliente_ok = bool(RE_CLIENTE.match(cliente))
    if modo == "adsense" and not cliente_ok:
        modo = "off"
    slots = {k: obtener("adsense_slot_" + k) for k in ("superior", "articulo", "lateral")}
    slots = {k: v for k, v in slots.items() if RE_SLOT.match(v)}
    return {"modo": modo, "cliente": cliente if cliente_ok else "", "slots": slots}

import os
import re
import unicodedata
import uuid

import bleach
from PIL import Image

TAGS = ["p", "br", "strong", "em", "u", "h2", "h3", "ul", "ol", "li", "a", "blockquote"]


def slugify(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:180] or "articulo"


def limpiar_html(html):
    """Deja solo etiquetas seguras (evita código malicioso)."""
    return bleach.clean(
        html, tags=TAGS,
        attributes={"a": ["href", "target", "rel"]},
        protocols=["http", "https", "mailto"], strip=True,
    )


def minutos_lectura(html):
    texto = re.sub(r"<[^>]+>", " ", html)
    return max(1, round(len(texto.split()) / 200))


def guardar_imagen(stream, carpeta):
    """Valida, reduce a máx. 1400px y guarda como JPG optimizado. Devuelve el nombre o None."""
    try:
        Image.open(stream).verify()
        stream.seek(0)
        img = Image.open(stream).convert("RGB")
    except Exception:
        return None
    img.thumbnail((1400, 1400))
    os.makedirs(carpeta, exist_ok=True)
    nombre = uuid.uuid4().hex + ".jpg"
    img.save(os.path.join(carpeta, nombre), "JPEG", quality=82, optimize=True)
    return nombre
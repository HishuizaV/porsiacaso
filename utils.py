import os
import re
import unicodedata
import uuid
from urllib.parse import urlparse

import bleach
from PIL import Image

# Evita imágenes gigantes que agoten la memoria ("decompression bomb")
Image.MAX_IMAGE_PIXELS = 40_000_000

TAGS = ["p", "br", "strong", "em", "u", "h2", "h3", "ul", "ol", "li", "a", "blockquote"]


def slugify(texto):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:180].strip("-") or "articulo"


def normalizar(texto):
    """Minúsculas, sin tildes ni signos: 'Trámite DNI' -> 'tramite dni'."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def texto_plano(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _atributos_enlace(attrs, new=False):
    """Todo enlace del contenido sale con rel seguro; los externos abren en otra pestaña."""
    href = attrs.get((None, "href"), "")
    if href.startswith(("http://", "https://")):
        attrs[(None, "target")] = "_blank"
        attrs[(None, "rel")] = "noopener noreferrer nofollow"
    else:
        attrs.pop((None, "target"), None)
        attrs.pop((None, "rel"), None)
    return attrs


def limpiar_html(html):
    """Deja solo etiquetas seguras (evita código malicioso)."""
    limpio = bleach.clean(
        html or "", tags=TAGS,
        attributes={"a": ["href", "target", "rel"]},
        protocols=["http", "https", "mailto"], strip=True,
    )
    limpio = _LINKER.linkify(limpio)
    # Quill deja párrafos vacíos al final
    return re.sub(r"(<p><br></p>\s*)+$", "", limpio).strip()


# Reescribe los <a> existentes con _atributos_enlace sin convertir texto en enlaces nuevos
_LINKER = bleach.Linker(callbacks=[_atributos_enlace], parse_email=False,
                        url_re=re.compile(r"(?!x)x"))


def contenido_vacio(html):
    return not texto_plano(html)


def minutos_lectura(html):
    return max(1, round(len(texto_plano(html).split()) / 200))


def url_valida(url):
    """True si es una dirección web http(s) con dominio. No inventa ni corrige nada."""
    if not url or len(url) > 500 or any(ch.isspace() for ch in url):
        return False
    try:
        p = urlparse(url)
    except ValueError:
        return False
    host = p.hostname or ""
    return p.scheme in ("http", "https") and "." in host and not host.startswith(".")


def guardar_imagen(stream, carpeta, max_lado=1400, miniatura=640):
    """Valida, reduce y guarda como JPG optimizado (+ miniatura '_m').
    Devuelve (nombre, ancho, alto) o None si no es una imagen válida."""
    try:
        Image.open(stream).verify()
        stream.seek(0)
        img = Image.open(stream)
        img.load()
        img = img.convert("RGB")
    except Exception:
        return None
    img.thumbnail((max_lado, max_lado))
    os.makedirs(carpeta, exist_ok=True)
    base = uuid.uuid4().hex
    nombre = base + ".jpg"
    img.save(os.path.join(carpeta, nombre), "JPEG", quality=82, optimize=True, progressive=True)
    if miniatura:
        m = img.copy()
        m.thumbnail((miniatura, miniatura))
        m.save(os.path.join(carpeta, base + "_m.jpg"), "JPEG", quality=78, optimize=True,
               progressive=True)
    return nombre, img.width, img.height


def guardar_logo(stream, carpeta):
    """Logo cuadrado pequeño en PNG (respeta transparencia)."""
    try:
        Image.open(stream).verify()
        stream.seek(0)
        img = Image.open(stream)
        img.load()
        img = img.convert("RGBA")
    except Exception:
        return None
    img.thumbnail((240, 240))
    os.makedirs(carpeta, exist_ok=True)
    nombre = uuid.uuid4().hex + ".png"
    img.save(os.path.join(carpeta, nombre), "PNG", optimize=True)
    return nombre


def guardar_pdf(archivo, carpeta, max_bytes=8 * 1024 * 1024):
    """Acepta solo PDF reales (cabecera %PDF-). Devuelve el nombre o None."""
    datos = archivo.stream.read(max_bytes + 1)
    if len(datos) > max_bytes or not datos.startswith(b"%PDF-"):
        return None
    os.makedirs(carpeta, exist_ok=True)
    nombre = uuid.uuid4().hex + ".pdf"
    with open(os.path.join(carpeta, nombre), "wb") as f:
        f.write(datos)
    return nombre


def borrar_archivo(carpeta, nombre):
    """Borra un archivo subido. Solo nombres simples (nunca rutas)."""
    if not nombre or os.path.basename(nombre) != nombre:
        return
    for n in (nombre, nombre.replace(".jpg", "_m.jpg") if nombre.endswith(".jpg") else None):
        if n:
            ruta = os.path.join(carpeta, n)
            if os.path.isfile(ruta):
                os.remove(ruta)

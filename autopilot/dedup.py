"""Deduplicación en varias capas: URL, identificador externo, código de convocatoria,
documento idéntico, texto idéntico y texto casi idéntico (shingles)."""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from utils import normalizar

PARAMETROS_RASTREO = re.compile(r"^(utm_.*|fbclid|gclid|mc_cid|mc_eid|_ga|ref|source)$", re.I)
UMBRAL_SIMILITUD = 0.85


def normalizar_url(url):
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower()
    if p.port and p.port not in (80, 443):
        host = f"{host}:{p.port}"
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                             if not PARAMETROS_RASTREO.match(k)))
    ruta = re.sub(r"/{2,}", "/", p.path or "/")
    if len(ruta) > 1:
        ruta = ruta.rstrip("/")
    return urlunsplit((p.scheme.lower(), host, ruta, query, ""))


def huella_texto(texto):
    t = normalizar(texto or "")
    return hashlib.sha256(t.encode()).hexdigest() if len(t) >= 40 else None


def huella_bytes(datos):
    return hashlib.sha256(datos).hexdigest() if datos else None


def normalizar_codigo(codigo):
    return re.sub(r"[^a-z0-9]", "", normalizar(codigo or "")) or None


def shingles(texto, k=5):
    palabras = normalizar(texto or "").split()
    if len(palabras) < k:
        return {" ".join(palabras)} if palabras else set()
    return {hash(" ".join(palabras[i:i + k])) for i in range(len(palabras) - k + 1)}


def similitud(a, b):
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def similitud_titulos(a, b):
    """Jaccard de palabras significativas (sin años ni números)."""
    pa = {p for p in normalizar(a or "").split() if len(p) > 2 and not p.isdigit()}
    pb = {p for p in normalizar(b or "").split() if len(p) > 2 and not p.isdigit()}
    return len(pa & pb) / len(pa | pb) if pa and pb else 0.0


def buscar_duplicado(h, candidatos):
    """Devuelve (hallazgo_existente, motivo) o (None, None).

    `h` es el hallazgo nuevo (ya con huellas y código); `candidatos` otros hallazgos ya
    procesados (no duplicados) con los que compararlo.
    """
    for otro in candidatos:
        if otro.id == h.id:
            continue
        if otro.url_normalizada == h.url_normalizada:
            return otro, "misma URL"
        if h.id_externo and otro.fuente_id == h.fuente_id and otro.id_externo == h.id_externo:
            return otro, "mismo identificador de la fuente"
        if h.huella_documento and otro.huella_documento == h.huella_documento and \
                similitud_titulos(h.titulo, otro.titulo) >= 0.5:
            return otro, "mismo documento oficial (PDF idéntico) y título equivalente"
        if h.codigo_convocatoria and otro.codigo_convocatoria == h.codigo_convocatoria and \
                otro.fuente and h.fuente and otro.fuente.institucion_id == h.fuente.institucion_id:
            return otro, "misma institución y número de convocatoria"
        if h.huella and otro.huella == h.huella:
            return otro, "mismo contenido"
    for otro in candidatos:
        if otro.fuente_id == h.fuente_id and h.id_externo and otro.id_externo and h.id_externo != otro.id_externo:
            continue   # misma fuente, identificadores distintos: procesos distintos (aunque usen la misma plantilla)
        if h.codigo_convocatoria and otro.codigo_convocatoria and h.codigo_convocatoria != otro.codigo_convocatoria:
            continue
        if otro.id != h.id and otro.texto and h.texto and otro.tipo_detectado == h.tipo_detectado:
            if similitud(otro.texto, h.texto) >= UMBRAL_SIMILITUD:
                return otro, "contenido casi idéntico"
    return None, None

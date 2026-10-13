"""Adaptadores: leen el listado de una fuente y devuelven elementos candidatos.

Orden de preferencia (ver docs): API JSON documentada > RSS/Atom > HTML autorizado > PDF directo.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from utils import normalizar


@dataclass
class Item:
    url: str
    titulo: str = ""
    fecha: datetime = None
    id_externo: str = None
    resumen: str = ""
    extra: dict = field(default_factory=dict)


def _id_desde_url(url, patron):
    if not patron:
        return None
    m = re.search(patron, url)
    return (m.group("id") if "id" in m.re.groupindex else m.group(1)) if m else None


def _filtrar(items, cfg):
    claves = [normalizar(p) for p in cfg.get("palabras_clave", []) if p.strip()]
    excluir = [normalizar(p) for p in cfg.get("excluir", []) if p.strip()]
    salida, vistos = [], set()
    for it in items:
        t = normalizar(it.titulo + " " + it.resumen)
        if claves and not any(c in t for c in claves):
            continue
        if any(e in t for e in excluir):
            continue
        if it.url in vistos:
            continue
        vistos.add(it.url)
        salida.append(it)
    return salida[: int(cfg.get("max_items", 30))]


def listar_rss(contenido, base_url, cfg):
    feed = feedparser.parse(contenido)
    items = []
    for e in feed.entries:
        url = e.get("link")
        if not url:
            continue
        fecha = None
        if e.get("published_parsed"):
            fecha = datetime(*e.published_parsed[:6])
        resumen = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ", strip=True)
        items.append(Item(url=urljoin(base_url, url), titulo=e.get("title", "").strip(), fecha=fecha,
                          id_externo=e.get("id") or None, resumen=resumen[:1000],
                          extra={"categorias": [t.get("term") for t in e.get("tags", [])]}))
    return items


def listar_html(contenido, base_url, cfg):
    sopa = BeautifulSoup(contenido, "html.parser")
    zona = sopa.select_one(cfg["selector"]) if cfg.get("selector") else (sopa.find("main") or sopa)
    if zona is None:
        return []
    patron = re.compile(cfg["patron_enlace"]) if cfg.get("patron_enlace") else None
    items = []
    for a in zona.find_all("a", href=True):
        url = urljoin(base_url, a["href"].strip())
        if not url.startswith(("http://", "https://")):
            continue
        if patron and not patron.search(url):
            continue
        titulo = a.get_text(" ", strip=True)
        if not titulo or len(titulo) < 6:
            continue
        items.append(Item(url=url, titulo=titulo[:400],
                          id_externo=_id_desde_url(url, cfg.get("patron_id"))))
    return items


def _ruta(datos, ruta):
    for parte in [p for p in (ruta or "").split(".") if p]:
        datos = datos.get(parte, []) if isinstance(datos, dict) else []
    return datos


class _Fila(dict):
    """Permite usar plantillas «{CAMPO}» con campos que faltan (quedan vacíos)."""
    def __missing__(self, clave):
        return ""


def listar_json(contenido, base_url, cfg):
    """Lista JSON. Admite plantillas para armar la URL y el título a partir de varios campos:
    {"plantilla_url": "{RUTA_CARPETA}{BASES}", "plantilla_titulo": "CAS {SPROCESO}: {SSERVICIO}"}."""
    datos = json.loads(contenido)
    lista = _ruta(datos, cfg.get("ruta_lista", "")) if cfg.get("ruta_lista") else datos
    campos = cfg.get("campos", {})
    items = []
    for d in lista if isinstance(lista, list) else []:
        if not isinstance(d, dict):
            continue
        fila = _Fila({k: ("" if v is None else str(v).strip()) for k, v in d.items()})
        url = cfg["plantilla_url"].format_map(fila) if cfg.get("plantilla_url") else d.get(campos.get("url", "url"))
        if not isinstance(url, str) or not url.strip():
            continue
        titulo = cfg["plantilla_titulo"].format_map(fila) if cfg.get("plantilla_titulo") \
            else str(d.get(campos.get("titulo", "titulo"), ""))
        fecha = None
        texto_fecha = d.get(campos.get("fecha", "fecha"))
        if isinstance(texto_fecha, str):
            try:
                fecha = datetime.fromisoformat(texto_fecha[:19])
            except ValueError:
                pass
        ident = d.get(campos.get("id", "id"))
        resumen = cfg["plantilla_resumen"].format_map(fila) if cfg.get("plantilla_resumen") \
            else str(d.get(campos.get("resumen", "resumen"), "") or "")
        items.append(Item(url=urljoin(base_url, url.strip()), titulo=re.sub(r"\s+", " ", titulo).strip()[:400],
                          fecha=fecha, id_externo=str(ident) if ident not in (None, "") else None,
                          resumen=resumen[:1000],
                          extra={"enlaces": [(cfg.get("texto_enlace_extra", "Postulación"), cfg["enlace_extra"])]}
                          if cfg.get("enlace_extra") else {}))
    return items


RE_PUESTO = re.compile(r"Contrataci[oó]n de (?:un|una|uno|01)\s+(?:\(\d+\)\s*)?(.+?)\s+(?:para|en)\s+(?:la|el|los|las)\b",
                       re.I)


def listar_procesos(contenido, base_url, cfg):
    """Página con varios procesos seguidos (p. ej. «Convocatorias CAS 2026» de AGRO RURAL en gob.pe).

    Cada bloque empieza con `patron_bloque`. Se omiten los bloques que ya muestran etapas de
    evaluación (`excluir_bloque`, p. ej. «Resultado»): significa que la postulación terminó."""
    sopa = BeautifulSoup(contenido, "html.parser")
    zona = sopa.find("main") or sopa
    patron = re.compile(cfg.get("patron_bloque", r"Proceso de Selecci[oó]n N"), re.I)
    excluir = [normalizar(x) for x in cfg.get("excluir_bloque", ["resultado"])]
    bloques, actual = [], None
    for el in zona.find_all(["h1", "h2", "h3", "h4", "p", "li", "a", "strong", "span", "div"]):
        texto = el.get_text(" ", strip=True)
        if el.name != "a" and texto and patron.match(texto) and len(texto) < 160 and not el.find(["p", "div", "li"]):
            actual = {"titulo": texto, "descripcion": "", "enlaces": [], "textos": []}
            bloques.append(actual)
            continue
        if actual is None:
            continue
        if el.name == "a" and el.get("href"):
            url = urljoin(base_url, el["href"].strip())
            if url.startswith(("http://", "https://")) and (texto, url) not in actual["enlaces"]:
                actual["enlaces"].append((texto, url))
        elif el.name in ("p", "li", "span", "strong", "div") and not el.find(["p", "div", "a"]) and len(texto) > 20:
            if texto not in actual["textos"]:
                actual["textos"].append(texto)
    items = []
    for b in bloques:
        textos = normalizar(" ".join(t for t, _u in b["enlaces"]))
        if any(x in textos for x in excluir):
            continue
        principal = next((u for t, u in b["enlaces"] if normalizar(t).startswith("bases")), None) or \
            (b["enlaces"][0][1] if b["enlaces"] else None)
        if not principal:
            continue
        m = re.search(r"N[°ºo.]*\s*([0-9]{1,4}-[0-9]{4}[A-Z0-9\-]*)", b["titulo"], re.I)
        texto_bloque = " ".join(b["textos"])
        puesto = RE_PUESTO.search(texto_bloque)
        b["descripcion"] = next((t for t in b["textos"] if RE_PUESTO.search(t)), b["textos"][0] if b["textos"] else "")
        titulo = b["titulo"] + (f" – {puesto.group(1).strip()}" if puesto else "")
        items.append(Item(url=principal, titulo=titulo[:400], id_externo=m.group(1) if m else None,
                          resumen=b["descripcion"][:1000], extra={"enlaces": b["enlaces"], "bloque": b["titulo"]}))
    return items


def listar_tabla(contenido, base_url, cfg):
    """Tabla HTML (fila = proceso). Se omiten las filas que ya tienen documentos de evaluación."""
    sopa = BeautifulSoup(contenido, "html.parser")
    base_url = cfg.get("base_enlaces") or base_url   # la tabla se inserta en otra página
    excluir = re.compile(cfg.get("excluir_fila_enlace", r"EVAL|FINALIZADO|RESULT"), re.I)
    items = []
    for fila in sopa.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in fila.find_all(["td", "th"])]
        enlaces = [(a.get_text(" ", strip=True) or "Documento", urljoin(base_url, a["href"].strip()))
                   for a in fila.find_all("a", href=True)]
        if len(celdas) < 2 or not enlaces:
            continue
        if any(excluir.search(u) for _t, u in enlaces):
            continue
        codigo, puesto = celdas[0], celdas[1]
        titulo = cfg.get("plantilla_titulo", "Convocatoria CAS N° {codigo} – {puesto}").format(codigo=codigo, puesto=puesto)
        extra = list(enlaces)
        if cfg.get("enlace_extra"):
            extra.append((cfg.get("texto_enlace_extra", "Postulación"), cfg["enlace_extra"]))
        items.append(Item(url=enlaces[0][1], titulo=re.sub(r"\s+", " ", titulo)[:400], id_externo=codigo[:200],
                          extra={"enlaces": [(t if t != "Documento" else "Perfil y bases", u) for t, u in extra]}))
    return items


def listar(fuente, descargador):
    """Consulta el listado de una fuente y devuelve los elementos filtrados."""
    cfg = fuente.config
    url = (fuente.url_listado or fuente.url_principal).replace("{anio}", str(date.today().year))
    if fuente.formato == "pdf":
        return [Item(url=url, titulo=fuente.nombre)]
    r = descargador.obtener(url)
    modo = cfg.get("modo")
    if fuente.formato == "html" and modo == "pagina_unica":
        # La URL configurada ya es la convocatoria (no un listado)
        from autopilot.extraccion import texto_html
        titulo, _t, _e = texto_html(r.texto, r.url)
        return [Item(url=r.url, titulo=titulo or fuente.nombre)]
    if fuente.formato == "html" and modo == "procesos":
        return _filtrar(listar_procesos(r.texto, r.url, cfg), cfg)
    if fuente.formato == "html" and modo == "tabla":
        return _filtrar(listar_tabla(r.texto, r.url, cfg), cfg)
    if fuente.formato == "rss":
        items = listar_rss(r.contenido, r.url, cfg)
    elif fuente.formato == "json":
        items = listar_json(r.texto, r.url, cfg)
    elif fuente.formato == "html":
        items = listar_html(r.texto, r.url, cfg)
    else:
        raise ValueError(f"Formato sin adaptador automático: {fuente.formato}")
    return _filtrar(items, cfg)

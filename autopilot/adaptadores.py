"""Adaptadores: leen el listado de una fuente y devuelven elementos candidatos.

Orden de preferencia (ver docs): API JSON documentada > RSS/Atom > HTML autorizado > PDF directo.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
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


def listar_json(contenido, base_url, cfg):
    datos = json.loads(contenido)
    lista = _ruta(datos, cfg.get("ruta_lista", ""))
    campos = cfg.get("campos", {})
    items = []
    for d in lista if isinstance(lista, list) else []:
        if not isinstance(d, dict):
            continue
        url = d.get(campos.get("url", "url"))
        if not isinstance(url, str):
            continue
        fecha = None
        texto_fecha = d.get(campos.get("fecha", "fecha"))
        if isinstance(texto_fecha, str):
            try:
                fecha = datetime.fromisoformat(texto_fecha[:19])
            except ValueError:
                pass
        ident = d.get(campos.get("id", "id"))
        items.append(Item(url=urljoin(base_url, url), titulo=str(d.get(campos.get("titulo", "titulo"), ""))[:400],
                          fecha=fecha, id_externo=str(ident) if ident is not None else None,
                          resumen=str(d.get(campos.get("resumen", "resumen"), ""))[:1000]))
    return items


def listar(fuente, descargador):
    """Consulta el listado de una fuente y devuelve los elementos filtrados."""
    cfg = fuente.config
    url = fuente.url_listado or fuente.url_principal
    if fuente.formato == "pdf":
        return [Item(url=url, titulo=fuente.nombre)]
    r = descargador.obtener(url)
    if fuente.formato == "rss":
        items = listar_rss(r.contenido, r.url, cfg)
    elif fuente.formato == "json":
        items = listar_json(r.texto, r.url, cfg)
    elif fuente.formato == "html":
        items = listar_html(r.texto, r.url, cfg)
    else:
        raise ValueError(f"Formato sin adaptador automático: {fuente.formato}")
    return _filtrar(items, cfg)

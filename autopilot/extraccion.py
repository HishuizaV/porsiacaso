"""Extracción de texto (HTML/PDF) y de datos estructurados con evidencia.

Cada dato devuelto lleva su estado:
  confirmado    -> aparece literalmente en la fuente (se guarda el fragmento)
  derivado      -> se obtiene con una regla verificable (p. ej. región de la fuente configurada)
  inferido      -> lo propuso la IA (nunca cuenta como prueba)
  no_encontrado -> no está en la evidencia
  contradictorio-> la fuente da valores distintos
"""
import io
import re
from dataclasses import dataclass, asdict
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from utils import normalizar

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
RE_FECHA_TEXTO = re.compile(r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")(?:\s+(?:de|del)\s+(\d{4}))?", re.I)
RE_FECHA_LISTA = re.compile(r"\b(\d{1,2}(?:\s*,\s*\d{1,2})*(?:\s*,?\s*y\s+\d{1,2})?)\s+de\s+("
                            + "|".join(MESES) + r")(?:\s+(?:de|del)\s+(\d{4}))?", re.I)
RE_FECHA_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
RE_CODIGO = re.compile(r"\b((?:CAS|PROCESO\s+CAS|CONVOCATORIA|CONCURSO|PR[AÁ]CTICAS)\s*N[°º.oO]*\s*"
                       r"\d{1,4}\s*[-–]\s*\d{4}(?:\s*[-–/]\s*[A-Z0-9][A-Z0-9/-]{1,20})?)", re.I)
RE_VACANTES = re.compile(r"\b(\d{1,4})\s*(?:\([^)]{1,25}\)\s*,?\s*)?(?:plazas|vacantes|puestos)\b", re.I)
RE_VACANTES_ETIQUETA = re.compile(r"(?:n[°º.]?\s*de\s*)?vacantes\s*:?\s*(\d{1,4})\b", re.I)
RE_SUELDO = re.compile(r"S/\.?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)")
CLAVES_LIMITE = ("fecha limite", "fecha de cierre", "cierre de", "hasta el", "plazo", "inscripciones hasta",
                 "postulacion hasta", "vence", "ultimo dia", "inscripcion hasta", "postulaciones hasta",
                 "registro de postulantes")
ENCABEZADOS = re.compile(r"^(requisitos|perfil|funciones|beneficios|cobertura|cronograma|contenidos?|experiencia|"
                         r"formacion|competencias|conocimientos|metodologia|horario|"
                         r"dirigido a|documentos|pasos|como postular|procedimiento|bases)\b", re.I)


@dataclass
class Dato:
    valor: object = None
    estado: str = "no_encontrado"
    fragmento: str = ""
    origen: str = ""
    pagina: int = None
    metodo: str = "regla"

    @property
    def util(self):
        return self.estado in ("confirmado", "derivado") and self.valor not in (None, "", [])

    def a_dict(self):
        d = asdict(self)
        if isinstance(self.valor, date):
            d["valor"] = self.valor.isoformat()
        return d


def confirmado(valor, fragmento, origen, pagina=None):
    return Dato(valor, "confirmado", _recortar(fragmento), origen, pagina, "regla")


def _recortar(t, n=300):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


# ---------- Texto ----------
def texto_html(html, url_base):
    """(titulo, texto_con_saltos, enlaces[(texto, url)]) del contenido principal."""
    sopa = BeautifulSoup(html, "html.parser")
    for t in sopa(["script", "style", "noscript", "nav", "header", "footer", "form", "iframe", "svg"]):
        t.decompose()
    principal = sopa.find("main") or sopa.find("article") or sopa.body or sopa
    h1 = principal.find("h1") or sopa.find("h1")
    titulo_h1 = h1.get_text(" ", strip=True) if h1 else ""
    segmentos = [x.strip() for x in sopa.title.get_text(" ", strip=True).split(" - ")] if sopa.title else []
    # gob.pe: <title>«Elemento - Sección - Entidad»</title> y <h1> = Entidad -> el título real es el 1.er segmento
    if len(segmentos) > 1 and normalizar(titulo_h1) in [normalizar(x) for x in segmentos[1:]]:
        titulo = segmentos[0]
    else:
        titulo = titulo_h1 or (segmentos[0] if segmentos else "")
    enlaces = []
    for a in principal.find_all("a", href=True):
        url = urljoin(url_base, a["href"].strip())
        if url.startswith(("http://", "https://")):
            enlaces.append((a.get_text(" ", strip=True)[:200], url))
    lineas = [re.sub(r"\s+", " ", l).strip() for l in principal.get_text("\n").splitlines()]
    texto = "\n".join(l for l in lineas if l)
    return titulo, texto, enlaces


def texto_pdf(datos, max_paginas=40):
    """Lista de (página, texto). Un PDF escaneado (imagen) devuelve textos vacíos."""
    from pypdf import PdfReader
    try:
        lector = PdfReader(io.BytesIO(datos))
        if lector.is_encrypted:
            return []
        paginas = []
        for i, pag in enumerate(lector.pages[:max_paginas], 1):
            try:
                paginas.append((i, pag.extract_text() or ""))
            except Exception:
                paginas.append((i, ""))
        return paginas
    except Exception:
        return []


# ---------- Utilidades de búsqueda ----------
def _contexto(texto, inicio, fin, ancho=120):
    return texto[max(0, inicio - ancho): min(len(texto), fin + ancho)]


def fechas_en(texto, anio_defecto=None):
    """Lista de (fecha, inicio, fin) en el orden en que aparecen."""
    salida = []
    for m in RE_FECHA_LISTA.finditer(texto):   # "19, 21 y 26 de octubre" -> tres fechas
        anio = int(m.group(3)) if m.group(3) else anio_defecto
        if not anio:
            continue
        for dia in re.findall(r"\d{1,2}", m.group(1)):
            try:
                salida.append((date(anio, MESES[m.group(2).lower()], int(dia)), m.start(), m.end()))
            except ValueError:
                pass
    for m in RE_FECHA_NUM.finditer(texto):
        try:
            salida.append((date(int(m.group(3)), int(m.group(2)), int(m.group(1))), m.start(), m.end()))
        except ValueError:
            pass
    return sorted(salida, key=lambda x: x[1])


def _anio_de(texto, hoy):
    m = re.search(r"\b(20\d{2})\b", texto)
    return int(m.group(1)) if m else hoy.year


def fecha_limite(texto, origen, hoy):
    """Fecha que sigue a una frase de cierre ("hasta el…", "fecha límite…").

    En un rango ("del 2 al 6 de octubre") se toma la fecha final. Si la fuente menciona
    cierres distintos se usa el más tardío y se marca como contradictorio para revisión humana.
    """
    anio = _anio_de(texto, hoy)
    base = normalizar_conservando(texto)
    candidatos = []
    for clave in CLAVES_LIMITE:
        for m in re.finditer(re.escape(clave), base):
            ventana = texto[m.start(): m.start() + 160]
            fs = fechas_en(ventana, anio)
            if not fs:
                continue
            es_rango = " al " in base[m.start(): m.start() + fs[-1][1]]
            candidatos.append((fs[-1][0] if es_rango else fs[0][0], ventana))
    if not candidatos:
        return Dato()
    f, frag = max(candidatos, key=lambda x: x[0])
    if len({c[0] for c in candidatos}) > 1:
        return Dato(f, "contradictorio", _recortar(frag), origen, metodo="regla")
    return confirmado(f, frag, origen)


def normalizar_conservando(texto):
    """Minúsculas y sin tildes, pero con la MISMA longitud (para mapear posiciones)."""
    import unicodedata
    salida = []
    for ch in texto:
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c)) or ch
        salida.append(base[0].lower() if base else ch)
    return "".join(salida)


def _es_limite_de_seccion(s):
    """¿Empieza aquí otra sección? (encabezado conocido, etiqueta «Algo:», título en MAYÚSCULAS,
    fechas de inscripción o enlaces de descarga)."""
    n = normalizar(s)
    if ENCABEZADOS.match(n) and len(s) < 80:
        return True
    if re.match(r"^[^\s:][^:]{1,40}:\s*\S?", s) and len(s.split(":", 1)[0].split()) <= 5:
        return True   # «Experiencia: …», «Remuneración mensual: …»
    letras = [c for c in s if c.isalpha()]
    if len(letras) >= 12 and sum(c.isupper() for c in letras) / len(letras) > 0.85:
        return True   # «BASE DE LA CONVOCATORIA CAS 003-2026»
    return bool(re.match(r"^(inscripciones?|postulaciones?|registro de postulantes|cierre|descargar|"
                         r"cronograma|remuneracion|vacantes|modalidad|lugar)\b", n))


def seccion(texto, nombres, max_items=15):
    """Viñetas o líneas bajo un encabezado (p. ej. «Requisitos»)."""
    lineas = texto.split("\n")
    for i, l in enumerate(lineas):
        ln = normalizar(l)
        if any(ln.startswith(normalizar(n)) for n in nombres) and len(ln) < 60:
            items = []
            resto = l.split(":", 1)[1].strip() if ":" in l else ""
            if resto:
                items.append(resto)
            for sig in lineas[i + 1: i + 40]:
                s = sig.strip(" ●•·-–*\t")
                if not s:
                    continue
                if items and _es_limite_de_seccion(s):
                    break
                if len(s) > 300:
                    break
                items.append(re.sub(r"^\d{1,2}[.)]\s*", "", s))
                if len(items) >= max_items:
                    break
            return [x for x in items if len(x) > 2], "\n".join([l] + lineas[i + 1: i + 1 + len(items)])
    return [], ""


def valor_etiquetado(texto, etiquetas):
    """'Dirigido a: X' -> X."""
    for et in etiquetas:
        m = re.search(r"(?im)^[ \t]*" + et + r"[ \t]*:[ \t]*\n?[ \t]*(\S.{2,300})$", texto)
        if m:
            return m.group(1).strip(), m.group(0)
    return None, ""


# ---------- Enlaces ----------
REGLAS_ENLACE = [
    ("postular", re.compile(r"postula|inscr[ií]b|inscripci[oó]n|reg[ií]strate|formulario de postulaci", re.I)),
    ("bases", re.compile(r"\bbases?\b", re.I)),
    ("anexo", re.compile(r"anexo|formato", re.I)),
]


def clasificar_enlaces(enlaces, url_pagina, tipo_pagina="convocatoria"):
    """[(tipo, etiqueta, url)] solo con enlaces que existen en la página oficial."""
    salida, vistos = [], set()
    for texto, url in enlaces:
        if url in vistos or url.split("#")[0] == url_pagina.split("#")[0]:
            continue
        ya = {t for t, _e, _u in salida}
        es_pdf = bool(re.search(r"\.pdf(\?|$)", url, re.I))
        ruta = url.rsplit("/", 1)[-1].lower()
        for tipo, patron in REGLAS_ENLACE:
            if patron.search(texto) or (es_pdf and tipo != "postular" and patron.search(ruta)):
                if (tipo != "anexo" and tipo in ya) or (tipo == "anexo" and
                                                         sum(1 for t, _e, _u in salida if t == "anexo") >= 4):
                    break
                etiqueta = None
                if tipo == "anexo":
                    n = sum(1 for x in salida if x[0] == "anexo") + 1
                    etiqueta = f"Descargar anexo {n}"
                salida.append((tipo, etiqueta, url))
                vistos.add(url)
                break
    # el botón de la página oficial consultada: «Ver convocatoria» o «Ir a la página oficial»
    salida.insert(0, (tipo_pagina, None, url_pagina))
    return [(t, (e if t != "anexo" or re.search(r"\.pdf(\?|$)", u, re.I) else "Ver formatos y documentos"), u)
            for t, e, u in salida]


def pdfs_de(enlaces):
    return [u for _t, u in enlaces if re.search(r"\.pdf(\?|$)", u, re.I)]


# ---------- Extracción por tipo ----------
def extraer(tipo, titulo, texto, origen, hoy, paginas_pdf=None, url_pdf=None):
    """Devuelve {campo: Dato}. Busca primero en la página y luego en el PDF de bases."""
    fuentes = [((titulo + "\n" + texto) if titulo else texto, origen, None)]
    for pag, t in (paginas_pdf or []):
        if t.strip():
            fuentes.append((t, url_pdf, pag))
    datos = {}

    def primero(func):
        for t, o, p in fuentes:
            d = func(t, o)
            if d.estado != "no_encontrado":
                if p and d.pagina is None:
                    d.pagina = p
                return d
        return Dato()

    datos["descripcion"] = _descripcion(titulo, texto, origen)
    datos["fecha_publicacion"] = _fecha_publicacion(texto, origen, hoy)
    datos["fecha_limite"] = primero(lambda t, o: fecha_limite(t, o, hoy))
    datos["codigo"] = primero(lambda t, o: _regex(RE_CODIGO, t, o, grupo=1,
                                                  limpiar=lambda v: re.sub(r"\s+", " ", v).strip().upper()))
    datos["vacantes"] = primero(_vacantes)
    datos["sueldo_min"] = primero(lambda t, o: _sueldo(t, o, tipo))
    datos["modalidad"] = primero(lambda t, o: _modalidad(t, o, tipo))

    if tipo in ("empleo", "convocatoria"):
        datos["cargo"] = _cargo(titulo, texto, origen, tipo)
        for campo, nombres in (("formacion", ["formacion academica", "formacion", "nivel educativo"]),
                               ("experiencia", ["experiencia"]),
                               ("competencias", ["competencias", "conocimientos"]),
                               ("funciones", ["funciones", "principales funciones"]),
                               ("requisitos", ["requisitos", "perfil del puesto", "perfil"])):
            datos[campo] = primero(lambda t, o, n=nombres: _lista(t, o, n))
    elif tipo in ("beca", "educativa"):
        publico, frag = valor_etiquetado(texto, ["dirigido a", "dirigida a", "publico objetivo", "público objetivo"])
        datos["publico"] = confirmado(publico, frag, origen) if publico else Dato()
        for campo, nombres in (("requisitos", ["requisitos"]), ("cobertura", ["cobertura", "beneficios", "que cubre"]),
                               ("pasos", ["como postular", "pasos", "procedimiento"])):
            datos[campo] = primero(lambda t, o, n=nombres: _lista(t, o, n))
    elif tipo == "curso":
        datos["costo"] = primero(_costo)
        publico, frag = valor_etiquetado(texto, ["dirigido a", "dirigida a"])
        datos["publico"] = confirmado(publico, frag, origen) if publico else Dato()
        datos["fecha_inicio"] = primero(lambda t, o: _fecha_inicio(t, o, hoy))
        datos["duracion"] = primero(lambda t, o: _regex(re.compile(r"(\d{1,3}\s*(?:horas(?:\s+acad[eé]micas|\s+cronol[oó]gicas)?|semanas|sesiones))", re.I), t, o))
        datos["certificado"] = primero(_certificado)
        datos["temario"] = primero(lambda t, o: _lista(t, o, ["contenidos", "temario", "contenido"]))
        datos["requisitos"] = primero(lambda t, o: _lista(t, o, ["requisitos"]))
    elif tipo in ("tramite", "bono"):
        datos["requisitos"] = primero(lambda t, o: _lista(t, o, ["requisitos"]))
        datos["pasos"] = primero(lambda t, o: _lista(t, o, ["pasos", "procedimiento", "como hacerlo", "como realizar"]))
        datos["costo_texto"] = primero(lambda t, o: _regex(re.compile(r"((?:costo|tasa|pago)[^\n]{0,15}S/\.?\s*[\d.,]+)", re.I), t, o))
    return datos


def _fecha_publicacion(texto, origen, hoy):
    """Fecha que la entidad muestra al inicio de la página (p. ej. gob.pe: «1 de setiembre de 2025»)."""
    cabecera = "\n".join(texto.split("\n")[:12])
    for f, a, b in fechas_en(cabecera, None):
        if f <= hoy:
            return confirmado(f, cabecera[max(0, a - 40): b + 20], origen)
    return Dato()


def _descripcion(titulo, texto, origen):
    """Primera frase sustancial de la página (evidencia breve, no se publica completa)."""
    nt = normalizar(titulo)
    for linea in texto.split("\n"):
        if 60 <= len(linea) <= 600 and normalizar(linea) != nt and not linea.lower().startswith(("http", "selecciona")):
            frase = re.split(r"(?<=[.!?])\s", linea)[0]
            return confirmado(_recortar(frase, 300), linea, origen)
    return Dato()


def _regex(patron, texto, origen, grupo=1, limpiar=None):
    m = patron.search(texto)
    if not m:
        return Dato()
    v = m.group(grupo)
    return confirmado(limpiar(v) if limpiar else v.strip(), _contexto(texto, m.start(), m.end(), 60), origen)


def _vacantes(texto, origen):
    m = RE_VACANTES_ETIQUETA.search(texto) or RE_VACANTES.search(texto)
    if not m:
        return Dato()
    n = int(m.group(1))
    if not 0 < n < 5000:
        return Dato()
    return confirmado(n, _contexto(texto, m.start(), m.end(), 60), origen)


def _sueldo(texto, origen, tipo):
    encontrados = []
    for m in RE_SUELDO.finditer(texto):
        ctx = normalizar(_contexto(texto, m.start(), m.end(), 80))
        if not any(k in ctx for k in ("remuneracion", "sueldo", "honorario", "retribucion", "contraprestacion",
                                      "salario", "mensual")):
            continue
        bruto = m.group(1)
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", bruto):
            valor = int(re.sub(r"[.,]", "", bruto))
        else:
            valor = float(bruto.replace(",", "."))
        if 300 <= valor <= 100000:
            encontrados.append((valor, m))
    if not encontrados:
        return Dato()
    valores = sorted({v for v, _ in encontrados})
    v, m = encontrados[0]
    frag = _contexto(texto, m.start(), m.end(), 60)
    if len(valores) > 1 and tipo == "empleo":
        return Dato(v, "contradictorio", _recortar(frag), origen, metodo="regla")
    if len(valores) > 1:
        return Dato(None, "no_encontrado")   # varias plazas con sueldos distintos: no se resume en uno
    return confirmado(v, frag, origen)


def _modalidad(texto, origen, tipo):
    n = normalizar(texto)
    reglas = [("hibrido", r"\b(hibrid[oa]|semipresencial|mixta)\b"),
              ("remoto", r"\b(remot[oa]|teletrabajo|virtual|en linea|a distancia)\b"),
              ("presencial", r"\bpresencial\b")]
    hallados = [(k, re.search(p, n)) for k, p in reglas if re.search(p, n)]
    if not hallados:
        return Dato()
    if len(hallados) > 1 and not any(k == "hibrido" for k, _ in hallados):
        return Dato(None, "contradictorio", "", origen)
    k, m = hallados[0]
    if tipo == "curso":
        k = {"remoto": "virtual", "hibrido": "semipresencial"}.get(k, k)
    return Dato(k, "confirmado", _recortar(n[max(0, m.start() - 60): m.end() + 60]), origen)


def _costo(texto, origen):
    n = normalizar(texto)
    m = re.search(r"\b(gratuit[oa]s?|gratis|sin costo|libre de costo|costo cero)\b", n)
    if m:
        return Dato("gratuito", "confirmado", _recortar(n[max(0, m.start() - 80): m.end() + 60]), origen)
    m = RE_SUELDO.search(texto)
    if m and "costo" in normalizar(_contexto(texto, m.start(), m.end(), 40)):
        return confirmado("pagado", _contexto(texto, m.start(), m.end(), 60), origen)
    return Dato()


def _certificado(texto, origen):
    n = normalizar(texto)
    m = re.search(r"certificad[oa]s?\s+(gratuit[oa]|digital|sin costo)", n)
    if m:
        return Dato("gratuito", "confirmado", _recortar(n[max(0, m.start() - 40): m.end() + 40]), origen)
    m = re.search(r"(constancia|certificado)", n)
    if m:
        return Dato("por_confirmar", "derivado", _recortar(n[max(0, m.start() - 40): m.end() + 60]), origen)
    return Dato()


def _fecha_inicio(texto, origen, hoy):
    for clave in ("fecha de inicio", "inicio de clases", "inicia el", "fechas de las sesiones", "inicio:"):
        i = normalizar_conservando(texto).find(clave)
        if i >= 0:
            fs = fechas_en(texto[i: i + 200], _anio_de(texto, hoy))
            if fs:
                return confirmado(fs[0][0], texto[i: i + 200], origen)
    return Dato()


def _lista(texto, origen, nombres):
    items, frag = seccion(texto, nombres)
    if not items:
        return Dato()
    return confirmado("\n".join(items), frag, origen)


def _cargo(titulo, texto, origen, tipo):
    v, frag = valor_etiquetado(texto, ["puesto", "cargo", "denominacion del puesto", "denominación del puesto",
                                       "nombre del puesto"])
    if v:
        return confirmado(v[:200], frag, origen)
    if tipo == "empleo":
        m = re.search(r"(?:convocatoria|proceso)[^:–-]{0,60}[:–-]\s*(.{5,120})$", titulo or "", re.I)
        if m:
            return confirmado(m.group(1).strip(), titulo, origen)
    return Dato()

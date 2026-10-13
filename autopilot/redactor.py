"""Agentes redactor y SEO: arman la ficha solo con datos respaldados (confirmados o derivados).

No se copian párrafos de la fuente: se redactan frases breves a partir de campos estructurados.
No se agregan párrafos genéricos ni cifras que no estén en la evidencia.
"""
import re
from html import escape

from models import fecha_larga
from tipos import TIPOS, NIVELES_EDUCATIVOS  # noqa: F401
from utils import normalizar

MAX_TITULO = 90


def _v(datos, campo):
    d = datos.get(campo)
    return d.valor if d is not None and d.util else None


def _lista_html(texto):
    items = [l.strip() for l in (texto or "").split("\n") if l.strip()]
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>" if items else ""


def limpiar_titulo_fuente(t):
    t = re.sub(r"^\s*(convocatoria|aviso|comunicado)\s*[|:–-]\s*", "", t or "", flags=re.I)
    t = re.sub(r"^\s*curso\s*(remoto|virtual)?\s*:\s*", "", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" .|-–")


def recortar(t, n=MAX_TITULO):
    return t if len(t) <= n else t[: n - 1].rsplit(" ", 1)[0] + "…"


def _plazas(n):
    return f"{n} plaza{'s' if n != 1 else ''}"


def titulo_seo(tipo, datos, titulo_fuente, inst, lugar):
    base = limpiar_titulo_fuente(titulo_fuente)
    corto = inst.siglas if inst and inst.siglas else (inst.nombre if inst else "")
    cargo, codigo, vac = _v(datos, "cargo"), _v(datos, "codigo"), _v(datos, "vacantes")
    if tipo == "empleo" and cargo:
        t = f"{cargo} – {corto}" if corto else cargo
        return recortar(t + (f" ({lugar})" if lugar and len(t) + len(lugar) < 84 else ""))
    if tipo == "convocatoria":
        if codigo and vac:
            return recortar(f"Convocatoria {codigo}: {_plazas(vac)}" + (f" en {corto}" if corto and codigo.find(corto) < 0 else ""))
        return recortar(f"{base} – {corto}" if corto and normalizar(corto) not in normalizar(base) else base)
    if tipo == "curso":
        gratis = _v(datos, "costo") == "gratuito"
        return recortar(("Curso gratuito: " if gratis else "Curso: ") + base)
    if tipo == "tramite" and inst:
        return recortar(f"{base}: requisitos y pasos en {corto}")
    return recortar(base)


def resumen(tipo, datos, inst, lugar, titulo_fuente):
    nombre_inst = inst.nombre if inst else "La entidad"
    fl = _v(datos, "fecha_limite")
    hasta = f" Postulación hasta el {fecha_larga(fl)}." if fl else ""
    if tipo in ("empleo", "convocatoria"):
        vac, cargo, cod = _v(datos, "vacantes"), _v(datos, "cargo"), _v(datos, "codigo")
        partes = [f"{nombre_inst} convoca"]
        partes.append(f" {_plazas(vac)}" if vac else (" a postulantes"))
        if cargo and tipo == "empleo":
            partes.append(f" para el puesto de {cargo}")
        if cod:
            partes.append(f" ({cod})")
        if lugar:
            partes.append(f" en {lugar}")
        return ("".join(partes) + "." + hasta)[:400]
    if tipo == "curso":
        costo = "gratuito " if _v(datos, "costo") == "gratuito" else ""
        mod = _v(datos, "modalidad")
        modo = {"virtual": "virtual ", "presencial": "presencial ", "semipresencial": "semipresencial "}.get(mod, "")
        txt = f"{nombre_inst} ofrece un curso {costo}{modo}«{limpiar_titulo_fuente(titulo_fuente)}»."
        inicio = _v(datos, "fecha_inicio")
        if inicio:
            txt += f" Inicia el {fecha_larga(inicio)}."
        return (txt + (f" Inscripciones hasta el {fecha_larga(fl)}." if fl else "")).replace("  ", " ")[:400]
    if tipo in ("beca", "educativa"):
        pub = _v(datos, "publico")
        return (f"{nombre_inst}: {limpiar_titulo_fuente(titulo_fuente)}." + (f" Dirigida a {pub[0].lower() + pub[1:]}." if pub else "") + hasta)[:400]
    if tipo == "tramite":
        return f"Requisitos y pasos para {limpiar_titulo_fuente(titulo_fuente)[0].lower() + limpiar_titulo_fuente(titulo_fuente)[1:]} ante {nombre_inst}, según su página oficial."[:400]
    return limpiar_titulo_fuente(titulo_fuente)[:400]


def contenido(tipo, datos, inst, enlaces):
    """HTML breve con lo que el visitante necesita para actuar. Solo datos respaldados."""
    partes = []
    fl = _v(datos, "fecha_limite")
    tipos_enlace = {t for t, _e, _u in enlaces}
    if tipo in ("empleo", "convocatoria"):
        req = _v(datos, "requisitos")
        if req and tipo == "convocatoria":
            partes.append("<h2>Requisitos generales</h2>" + _lista_html(req))
    if tipo in ("empleo", "convocatoria", "beca", "educativa", "curso"):
        pasos = []
        if "bases" in tipos_enlace:
            pasos.append("Lee las bases oficiales (botón «Ver bases»): ahí están el cronograma y las condiciones.")
        if "anexo" in tipos_enlace and tipo in ("empleo", "convocatoria"):
            pasos.append("Revisa los perfiles y formatos en los anexos oficiales.")
        if "postular" in tipos_enlace:
            pasos.append("Postula o inscríbete en el enlace oficial" + (f" antes del {fecha_larga(fl)}." if fl else "."))
        else:
            pasos.append("Sigue el procedimiento de postulación indicado en la convocatoria oficial.")
        partes.append("<h2>Cómo postular</h2><ol>" + "".join(f"<li>{escape(p)}</li>" for p in pasos) + "</ol>")
    return "".join(partes)


def detalle(tipo, datos, inst):
    """Campos para la tabla de detalle del CMS (solo valores respaldados)."""
    v = lambda c: _v(datos, c)  # noqa: E731
    if TIPOS[tipo]["detalle"] == "empleo":
        cod = v("codigo") or ""
        sueldo = v("sueldo_min")
        d = dict(cargo=v("cargo") or ("Varios puestos" if tipo == "convocatoria" else None), codigo=cod or None,
                 vacantes=v("vacantes"), modalidad=v("modalidad"), sueldo_min=sueldo,
                 moneda="PEN" if sueldo else None, formacion=v("formacion"), experiencia=v("experiencia"),
                 competencias=v("competencias"), funciones=v("funciones"),
                 tipo_convocatoria="cas" if cod.upper().startswith("CAS") else None,
                 sector=inst.sector if inst and inst.sector in ("publico", "privado") else None)
        return {k: x for k, x in d.items() if x is not None}
    if TIPOS[tipo]["detalle"] == "beca":
        return {k: x for k, x in dict(publico=v("publico"), requisitos=v("requisitos"), cobertura=v("cobertura"),
                                      pasos=v("pasos"), vacantes=v("vacantes"), modalidad=v("modalidad")).items()
                if x is not None}
    if tipo == "curso":
        cert = v("certificado")
        return {k: x for k, x in dict(costo=v("costo"), modalidad=v("modalidad"), duracion=v("duracion"),
                                      fecha_inicio=v("fecha_inicio"), certificado=cert if cert == "gratuito" else None,
                                      requisitos=v("requisitos"), temario=v("temario")).items() if x is not None}
    if tipo == "tramite":
        return {k: x for k, x in dict(finalidad=v("descripcion"), requisitos=v("requisitos"), pasos=v("pasos"),
                                      costo=v("costo_texto")).items() if x is not None}
    if tipo == "bono":
        return {k: x for k, x in dict(poblacion=v("publico"), requisitos=v("requisitos"), pasos=v("pasos")).items()
                if x is not None}
    return {}


def enlaces_internos(tipo, zona):
    """Sugerencias de enlazado interno (se muestran al revisor; no se insertan solas)."""
    s = [f"Sección {TIPOS[tipo]['plural']}"]
    if zona:
        s.append(f"{TIPOS[tipo]['plural']} en {zona.region.nombre}")
    return s


def componer(tipo, datos, titulo_fuente, inst, zona, enlaces):
    lugar = zona.nombre if zona else ""
    return {
        "tipo": tipo,
        "titulo": titulo_seo(tipo, datos, titulo_fuente, inst, lugar),
        "resumen": resumen(tipo, datos, inst, lugar, titulo_fuente),
        "contenido": contenido(tipo, datos, inst, enlaces),
        "detalle": detalle(tipo, datos, inst),
        "fecha_limite": _v(datos, "fecha_limite"),
        "enlaces_internos": enlaces_internos(tipo, zona),
    }

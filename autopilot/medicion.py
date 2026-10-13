"""Medición objetiva: ¿la IA local mejora lo que ya extraen las reglas? (no modifica datos)."""
import time
from datetime import date

from autopilot import extraccion
from autopilot.ia import CAMPOS_IA
from autopilot.modelos import Hallazgo
from utils import normalizar


def comparar(ia, casos):
    """casos: [(tipo, titulo, texto, esperado{campo: valor_correcto})]."""
    filas, aciertos_regla, aciertos_ia, verificables, total = [], 0, 0, 0, 0
    inicio = time.monotonic()
    for tipo, titulo, texto, esperado in casos:
        datos = extraccion.extraer(tipo, titulo, texto, "", date.today())
        campos = CAMPOS_IA.get(tipo, {})
        propuesta = ia.extraer_json(campos, f"{titulo}\n{texto}") if campos else {}
        for campo in campos:
            regla = datos[campo].valor if campo in datos and datos[campo].util else None
            valor_ia = propuesta.get(campo)
            correcto = esperado.get(campo)
            literal = bool(valor_ia) and normalizar(valor_ia) in normalizar(titulo + " " + texto)
            ok_r = _coincide(regla, correcto)
            ok_i = _coincide(valor_ia, correcto)
            total += 1
            aciertos_regla += ok_r
            aciertos_ia += ok_i
            verificables += literal
            filas.append({"tipo": tipo, "campo": campo, "esperado": correcto, "reglas": regla, "ia": valor_ia,
                          "ia_literal_en_fuente": literal, "acierto_reglas": ok_r, "acierto_ia": ok_i})
    return {"modelo": ia.modelo, "casos": total, "aciertos_reglas": aciertos_regla, "aciertos_ia": aciertos_ia,
            "ia_verificable_literalmente": verificables, "llamadas": ia.llamadas, "errores_ia": ia.errores,
            "segundos_ia": round(ia.segundos, 1), "segundos_por_llamada": round(ia.segundos / max(1, ia.llamadas), 1),
            "segundos_totales": round(time.monotonic() - inicio, 1), "detalle": filas}


def _coincide(valor, correcto):
    if correcto in (None, ""):
        return valor in (None, "")
    return bool(valor) and normalizar(correcto) in normalizar(valor) or \
        (bool(valor) and normalizar(valor) in normalizar(correcto) and len(normalizar(valor)) > 5)


def medir(ia, limite=20):
    """Usa los hallazgos guardados; el valor «esperado» es el que confirmaron las reglas (si lo hay)."""
    casos = []
    for h in Hallazgo.query.filter(Hallazgo.texto.isnot(None), Hallazgo.tipo_detectado.in_(list(CAMPOS_IA))) \
            .order_by(Hallazgo.id.desc()).limit(limite).all():
        esperado = {k: (v.get("valor") if v.get("estado") == "confirmado" else None) for k, v in h.datos.items()}
        casos.append((h.tipo_detectado, h.titulo or "", h.texto[:6000], esperado))
    return comparar(ia, casos)

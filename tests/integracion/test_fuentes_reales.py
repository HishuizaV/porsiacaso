"""Integración con fuentes REALES (gob.pe). No forma parte de la batería normal.

Ejecutar a mano:   set PORSIACASO_INTEGRACION=1   y   python -m pytest tests/integracion -s
Usa una base temporal: nunca escribe en porsiacaso.db ni publica nada.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytestmark = pytest.mark.skipif(os.environ.get("PORSIACASO_INTEGRACION") != "1",
                                reason="Integración real desactivada (define PORSIACASO_INTEGRACION=1)")


def test_jornada_real_corta(app):
    from extensions import db
    from models import Articulo, Ubicacion
    from autopilot.modelos import Fuente, Hallazgo, Evidencia
    from autopilot.motor import Motor
    from autopilot.red import Descargador
    from autopilot.fuentes_iniciales import FUENTES, INSTITUCIONES
    from models import Institucion

    with app.app_context():
        # En la base temporal se autoriza la extracción SOLO para esta prueba
        insts = {k: Institucion(slug=k, nombre=n, siglas=s, sector=sec, web=w, verificada=False)
                 for k, (n, s, sec, w) in INSTITUCIONES.items()}
        db.session.add_all(insts.values())
        for f in FUENTES:
            if f["formato"] not in ("html", "rss") or f.get("estado") == "manual":
                continue
            db.session.add(Fuente(nombre=f["nombre"], institucion=insts[f["inst"]], url_principal=f["url_principal"],
                                  url_listado=f["url_listado"], tipo_contenido=f["tipo"], formato=f["formato"],
                                  ubicacion=Ubicacion.query.filter_by(slug=f["zona"]).first() if f["zona"] else None,
                                  frecuencia_horas=f["frecuencia"], prioridad=f["prioridad"], confianza="alta",
                                  estado="activa", permite_extraccion=True, config_json=json.dumps(f["config"])))
        db.session.commit()
        motor = Motor(descargador=Descargador(pausa_dominio=2.0), registrar=print)
        ej = motor.ejecutar(minutos=int(os.environ.get("PORSIACASO_MINUTOS", "12")), objetivo=15)
        print(json.dumps(ej.informe, ensure_ascii=False, indent=1))
        print("Peticiones HTTP:", motor.descargador.peticiones)
        for h in Hallazgo.query.order_by(Hallazgo.id).all():
            print(f"- [{h.estado}] {h.tipo_detectado} · {(h.titulo or '')[:80]} · {(h.motivo or '')[:120]}")
        for a in Articulo.query.all():
            print(f"* FICHA [{a.estado}] {a.tipo}: {a.titulo} | límite {a.fecha_limite} | botones {[e.tipo for e in a.enlaces]}")
        assert ej.estado == "completada"
        assert ej.contadores.get("fuentes_consultadas", 0) >= 1
        assert Hallazgo.query.count() >= 1
        # Toda ficha creada tiene evidencia y botones con URLs reales https
        for a in Articulo.query.all():
            h = Hallazgo.query.filter_by(articulo_id=a.id).one()
            assert Evidencia.query.filter_by(hallazgo_id=h.id).count() > 0
            assert all(e.url.startswith("https://") for e in a.enlaces)
            assert a.estado == "revision"     # modo A: nada se publica solo

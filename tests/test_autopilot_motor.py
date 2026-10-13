"""Motor de jornada: límite de tiempo, recuperación, doble ejecución, detener, idempotencia, informe."""
from datetime import timedelta

import pytest

from ap_web import WebSimulada
from extensions import db
from models import Articulo, ahora
from autopilot.modelos import Bloqueo, Ejecucion, Fuente, Hallazgo, Tarea
from autopilot.motor import Motor, YaEnCurso, adquirir_bloqueo, liberar_bloqueo
from test_autopilot import fuente_gobpe


class Reloj:
    """Reloj simulado: cada consulta avanza `paso` segundos."""
    def __init__(self, paso=1.0):
        self.t, self.paso = 0.0, paso

    def __call__(self):
        self.t += self.paso
        return self.t


def motor(web, **kw):
    return Motor(descargador=web.descargador(), reloj=kw.pop("reloj", Reloj()), dormir=lambda s: None,
                 registrar=lambda m: None, **kw)


def test_jornada_completa_y_informe(app):
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe()
        ej = motor(web).ejecutar(minutos=30)
        assert ej.estado == "completada"
        c = ej.contadores
        assert c["fuentes_consultadas"] == 1 and c["hallazgos_nuevos"] == 3
        assert c.get("revision") == 2 and c.get("rechazado") == 1
        assert ej.informe["fichas"] == 2 and ej.informe["pendientes"] == 0
        assert any("bandeja" in r for r in ej.informe["recomendaciones"])
        assert Bloqueo.query.count() == 0     # bloqueo liberado
        assert Articulo.query.filter_by(origen="autopilot").count() == 2


def test_repetir_jornada_es_idempotente(app):
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe()
        motor(web).ejecutar(minutos=30)
        f.ultima_consulta = ahora() - timedelta(days=2)   # toca consultar otra vez
        db.session.commit()
        ej2 = motor(web).ejecutar(minutos=30)
        assert ej2.contadores.get("hallazgos_nuevos", 0) == 0
        assert Articulo.query.filter_by(origen="autopilot").count() == 2
        assert Hallazgo.query.count() == 3


def test_cierre_por_limite_de_tiempo_guarda_pendientes(app):
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe()
        # Cada consulta al reloj avanza 40 s: con 5 minutos solo cabe la consulta de la fuente
        ej = motor(web, reloj=Reloj(40), margen_cierre=60).ejecutar(minutos=5)
        assert ej.estado == "completada"
        assert "límite de tiempo" in ej.informe["motivo_fin"]
        pendientes = Tarea.query.filter_by(estado="pendiente", tipo="procesar_hallazgo").count()
        hechas = Tarea.query.filter_by(estado="hecha", tipo="procesar_hallazgo").count()
        assert pendientes >= 1 and ej.informe["pendientes"] == pendientes and hechas + pendientes == 3
        assert Tarea.query.filter_by(estado="en_curso").count() == 0     # nada a medias
        assert Articulo.query.count() <= hechas
        # La siguiente jornada continúa donde quedó
        motor(web).ejecutar(minutos=30)
        assert Articulo.query.filter_by(origen="autopilot").count() == 2
        assert Tarea.query.filter_by(estado="pendiente").count() == 0


def test_duracion_maxima_120_minutos(app):
    web = WebSimulada()
    with app.app_context():
        ej = motor(web).ejecutar(minutos=600)
        assert ej.duracion_max == 120


def test_no_hay_doble_ejecucion(app):
    with app.app_context():
        adquirir_bloqueo("otro-proceso")
        with pytest.raises(YaEnCurso):
            motor(WebSimulada()).ejecutar(minutos=5)
        # Un bloqueo abandonado (latido viejo) se recupera
        b = db.session.get(Bloqueo, "jornada")
        b.latido = ahora() - timedelta(minutes=30)
        db.session.commit()
        ej = motor(WebSimulada()).ejecutar(minutos=5)
        assert ej.estado == "completada"
        liberar_bloqueo("otro-proceso")


def test_recuperacion_tras_interrupcion(app):
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe()
        # Simula una jornada que murió a mitad: tarea en curso y ejecución sin cerrar
        vieja = Ejecucion(estado="en_curso", iniciada=ahora() - timedelta(hours=3), latido=ahora() - timedelta(hours=2))
        db.session.add(vieja)
        from autopilot import flujo
        flujo.consultar_fuente(f, web.descargador())
        t = Tarea.query.filter_by(tipo="procesar_hallazgo").first()
        t.estado = "en_curso"
        db.session.commit()
        ej = motor(web).ejecutar(minutos=30)
        assert db.session.get(Ejecucion, vieja.id).estado == "interrumpida"
        assert ej.contadores.get("recuperadas") == 1
        assert Tarea.query.filter_by(estado="en_curso").count() == 0
        assert Articulo.query.count() == 2


def test_detener_de_forma_segura(app):
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe()
        ej = Ejecucion(estado="solicitada", solicitud="detener")
        db.session.add(ej)
        db.session.commit()
        m = motor(web)
        # La solicitud previa se limpia al iniciar; se vuelve a pedir tras la primera tarea
        original = m._ejecutar_tarea

        def tras_primera(t, cfg, ejec):
            r = original(t, cfg, ejec)
            ejec.solicitud = "detener"
            db.session.commit()
            return r
        m._ejecutar_tarea = tras_primera
        ej = m.ejecutar(ejecucion_id=ej.id, minutos=30)
        assert ej.estado == "detenida"
        assert Tarea.query.filter_by(estado="pendiente").count() == 3   # quedan para la próxima
        assert Tarea.query.filter_by(estado="en_curso").count() == 0


def test_pausa_y_continuar(app):
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe()
        ej = Ejecucion(estado="solicitada")
        db.session.add(ej)
        db.session.commit()
        m = motor(web)
        llamadas = {"n": 0}
        original_sol = m._solicitud

        def solicitud(e):
            llamadas["n"] += 1
            if llamadas["n"] == 2:
                e.solicitud = "pausar"
                db.session.commit()
            if llamadas["n"] == 4:
                e.solicitud = "continuar"
                db.session.commit()
            return original_sol(e)
        m._solicitud = solicitud
        ej = m.ejecutar(ejecucion_id=ej.id, minutos=30)
        assert ej.estado == "completada" and ej.contadores.get("revision") == 2


def test_errores_de_red_con_reintentos_limitados(app):
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe()
        web.agregar(f.url_listado, "text/html", "caido", estado=503)
        ej = motor(web).ejecutar(minutos=30)
        t = Tarea.query.filter_by(tipo="consultar_fuente").one()
        assert t.estado == "pendiente" and t.intentos == 1 and t.proximo_intento > ahora()
        assert db.session.get(Fuente, f.id).errores_consecutivos == 1
        assert ej.estado == "completada"


def test_meta_no_se_fuerza(app):
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe()
        ej = motor(web).ejecutar(minutos=30, objetivo=15)
        assert ej.informe["fichas"] == 2
        assert any("no hubo más oportunidades útiles" in r for r in ej.informe["recomendaciones"])


def test_meta_alcanzada_deja_el_resto_pendiente(app):
    web = WebSimulada()
    with app.app_context():
        fuente_gobpe()
        ej = motor(web).ejecutar(minutos=30, objetivo=1)
        assert ej.informe["fichas"] == 1
        assert Tarea.query.filter_by(estado="pendiente", tipo="procesar_hallazgo").count() >= 1

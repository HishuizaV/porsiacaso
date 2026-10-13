"""Motor de jornada del Autopilot (proceso independiente del servidor web).

- Bloqueo único con latido: nunca corren dos jornadas a la vez.
- Cola persistente (tabla `tarea`) con claves idempotentes: repetir no duplica trabajo.
- Presupuesto de tiempo: no inicia una tarea si no alcanza a terminarla antes del cierre.
- Pausa / continuar / detener desde el panel (se leen de la base entre tareas).
- Cada tarea se guarda en su propia transacción; si el proceso muere, la siguiente jornada
  recupera lo que quedó a medias.
"""
import json
import os
import subprocess
import sys
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ahora
from autopilot import calidad, flujo
from autopilot.modelos import Bloqueo, Ejecucion, Fuente, Hallazgo, Tarea
from autopilot.red import Bloqueado, Descargador, ErrorRed

NOMBRE_BLOQUEO = "jornada"
LATIDO_VIEJO = timedelta(minutes=5)
COSTO = {"consultar_fuente": 60, "procesar_hallazgo": 150, "revisar_hallazgo": 120}   # segundos, peor caso
ORDEN_TIPOS = {"consultar_fuente": 0, "procesar_hallazgo": 1, "revisar_hallazgo": 2}
FICHAS = ("revision", "autopublicado", "programado")


class YaEnCurso(Exception):
    pass


# ---------- Bloqueo ----------
def adquirir_bloqueo(propietario):
    b = db.session.get(Bloqueo, NOMBRE_BLOQUEO)
    if b is not None:
        if b.latido and ahora() - b.latido < LATIDO_VIEJO:
            raise YaEnCurso("Ya hay una jornada en curso.")
        db.session.delete(b)   # latido viejo: el proceso anterior murió
        db.session.flush()
    db.session.add(Bloqueo(nombre=NOMBRE_BLOQUEO, propietario=propietario, adquirido=ahora(), latido=ahora()))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise YaEnCurso("Otra jornada tomó el control al mismo tiempo.")


def liberar_bloqueo(propietario):
    b = db.session.get(Bloqueo, NOMBRE_BLOQUEO)
    if b is not None and b.propietario == propietario:
        db.session.delete(b)
        db.session.commit()


def jornada_activa():
    b = db.session.get(Bloqueo, NOMBRE_BLOQUEO)
    return b is not None and b.latido is not None and ahora() - b.latido < LATIDO_VIEJO


# ---------- Motor ----------
class Motor:
    def __init__(self, descargador=None, ia=None, reloj=time.monotonic, dormir=time.sleep, margen_cierre=120,
                 pausa_sondeo=5, registrar=print):
        self.descargador = descargador
        self.ia = ia
        self.reloj, self.dormir = reloj, dormir
        self.margen, self.pausa_sondeo = margen_cierre, pausa_sondeo
        self.registrar = registrar
        self.propietario = uuid.uuid4().hex
        self.contadores = {}

    def _sumar(self, clave, n=1):
        self.contadores[clave] = self.contadores.get(clave, 0) + n

    def _log(self, texto):
        try:
            self.registrar(f"[{ahora():%H:%M:%S}] {texto}")
        except Exception:
            pass

    # ----- preparación -----
    def _recuperar(self, ej):
        reiniciadas = Tarea.query.filter_by(estado="en_curso").update(
            {"estado": "pendiente", "ultimo_error": "Interrumpida en una jornada anterior"})
        for otra in Ejecucion.query.filter(Ejecucion.id != ej.id, Ejecucion.estado.in_(("en_curso", "pausada"))).all():
            otra.estado, otra.finalizada = "interrumpida", otra.latido or ahora()
        for h in Hallazgo.query.filter_by(estado="nuevo").all():   # hallazgos sin tarea (caída a mitad)
            flujo.encolar("procesar_hallazgo", h.id, f"procesar:{h.id}", 2, ej.id)
        db.session.commit()
        if reiniciadas:
            self._log(f"Recuperadas {reiniciadas} tareas interrumpidas.")
            self._sumar("recuperadas", reiniciadas)

    def _planificar(self, ej, cfg):
        tipos = ej.tipos or cfg["tipos"]
        regiones = ej.regiones or cfg["regiones"]
        planificadas = 0
        for f in Fuente.query.order_by(Fuente.prioridad, Fuente.id).all():
            if not f.consultable or not f.toca_consultar:
                continue
            if tipos and f.tipo_contenido not in tipos:
                continue
            if regiones and f.ubicacion is not None and f.ubicacion.region.slug not in regiones:
                continue
            ventana = int(time.time() // (max(1, f.frecuencia_horas) * 3600))
            if flujo.encolar("consultar_fuente", f.id, f"fuente:{f.id}:{ventana}", f.prioridad, ej.id):
                planificadas += 1
        db.session.commit()
        return planificadas

    # ----- control -----
    def _latido(self, ej, etapa=None):
        ahora_ = ahora()
        ej.latido = ahora_
        if etapa:
            ej.etapa = etapa
        ej.contadores_json = json.dumps(self.contadores)
        b = db.session.get(Bloqueo, NOMBRE_BLOQUEO)
        if b is not None and b.propietario == self.propietario:
            b.latido = ahora_
        db.session.commit()

    def _solicitud(self, ej):
        db.session.refresh(ej)
        return ej.solicitud

    def _esperar_pausa(self, ej, fin):
        ej.estado, ej.solicitud = "pausada", None
        self._latido(ej, "pausada")
        self._log("Jornada en pausa.")
        while self.reloj() < fin - self.margen:
            self.dormir(self.pausa_sondeo)
            s = self._solicitud(ej)
            self._latido(ej)
            if s in ("continuar", "detener"):
                ej.solicitud = None if s == "continuar" else s
                ej.estado = "en_curso"
                db.session.commit()
                self._log("Jornada reanudada." if s == "continuar" else "Detención solicitada durante la pausa.")
                return s
        ej.estado = "en_curso"
        return "tiempo"

    def _siguiente(self, objetivo_alcanzado):
        q = Tarea.query.filter(Tarea.estado == "pendiente",
                               (Tarea.proximo_intento.is_(None)) | (Tarea.proximo_intento <= ahora()))
        if objetivo_alcanzado:
            q = q.filter(Tarea.tipo != "procesar_hallazgo")
        tareas = q.order_by(Tarea.prioridad, Tarea.id).limit(50).all()
        if not tareas:
            return None
        return min(tareas, key=lambda t: (ORDEN_TIPOS.get(t.tipo, 9), t.prioridad, t.id))

    def _precargar(self, cfg):
        """Descargas simultáneas moderadas de las próximas páginas (solo red, sin base de datos)."""
        if cfg["concurrencia"] <= 1 or not hasattr(self.descargador, "precargar"):
            return
        ids = [t.objetivo_id for t in Tarea.query.filter_by(estado="pendiente", tipo="procesar_hallazgo")
               .order_by(Tarea.prioridad, Tarea.id).limit(cfg["concurrencia"] * 2).all()]
        urls = [h.url for h in Hallazgo.query.filter(Hallazgo.id.in_(ids)).all()] if ids else []
        self.descargador.precargar(urls, cfg["concurrencia"])

    # ----- ejecución de una tarea -----
    def _ejecutar_tarea(self, t, cfg, ej):
        t.estado, t.actualizada, t.ejecucion_id = "en_curso", ahora(), ej.id
        t.intentos += 1
        db.session.commit()
        try:
            resultado = self._despachar(t, cfg, ej)
            t.estado, t.ultimo_error = "hecha", None
            db.session.commit()
            return resultado
        except Bloqueado as e:      # no tiene sentido reintentar
            db.session.rollback()
            self._fallo(t, f"Bloqueado: {e}", definitivo=True)
        except (ErrorRed, Exception) as e:   # noqa: B014
            db.session.rollback()
            detalle = f"{e.__class__.__name__}: {e}"
            if not isinstance(e, ErrorRed):
                detalle += "\n" + traceback.format_exc(limit=3)
            self._fallo(t, detalle, definitivo=False)
        return "error"

    def _fallo(self, t, detalle, definitivo):
        t = db.session.get(Tarea, t.id)
        t.ultimo_error, t.actualizada = detalle[:2000], ahora()
        if definitivo or t.intentos >= t.max_intentos:
            t.estado = "fallida"
        else:
            t.estado, t.proximo_intento = "pendiente", ahora() + timedelta(minutes=2 ** t.intentos)
        if t.tipo == "consultar_fuente":
            f = db.session.get(Fuente, t.objetivo_id)
            if f is not None:
                f.errores_consecutivos += 1
                f.ultimo_error = detalle[:1000]
                if f.errores_consecutivos >= 3:
                    f.estado = "error"
        elif t.tipo == "procesar_hallazgo" and t.estado == "fallida":
            h = db.session.get(Hallazgo, t.objetivo_id)
            if h is not None:
                h.estado, h.motivo = "error", detalle[:1000]
        self._sumar("errores")
        db.session.commit()
        self._log(f"Error en {t.tipo} #{t.objetivo_id}: {detalle.splitlines()[0][:150]}")

    def _despachar(self, t, cfg, ej):
        if t.tipo == "consultar_fuente":
            f = db.session.get(Fuente, t.objetivo_id)
            if f is None or not f.consultable:
                return "omitida"
            nuevos, vistos = flujo.consultar_fuente(f, self.descargador, ej.id)
            self._sumar("fuentes_consultadas")
            self._sumar("hallazgos_nuevos", nuevos)
            self._sumar("elementos_vistos", vistos)
            self._log(f"Fuente «{f.nombre}»: {vistos} elementos, {nuevos} nuevos.")
            return "ok"
        h = db.session.get(Hallazgo, t.objetivo_id)
        if h is None:
            return "omitida"
        if t.tipo == "procesar_hallazgo":
            if h.estado not in ("nuevo", "error"):
                return "omitida"   # idempotencia: ya procesado
            r = flujo.procesar_hallazgo(h, self.descargador, cfg, self.ia)
            self._sumar(r)
            self._log(f"Hallazgo #{h.id} «{(h.titulo or '')[:60]}»: {r}")
            return r
        if t.tipo == "revisar_hallazgo":
            r = flujo.revisar_hallazgo(h, self.descargador, cfg)
            self._sumar("revisados")
            if r == "actualizacion":
                self._sumar("actualizacion")
            return r
        raise ValueError(f"Tipo de tarea desconocido: {t.tipo}")

    # ----- jornada -----
    def ejecutar(self, ejecucion_id=None, minutos=None, objetivo=None, origen="manual", usuario_id=None):
        cfg = calidad.configuracion()
        adquirir_bloqueo(self.propietario)
        ej = db.session.get(Ejecucion, ejecucion_id) if ejecucion_id else None
        if ej is None:
            ej = Ejecucion(origen=origen, usuario_id=usuario_id)
            db.session.add(ej)
        ej.duracion_max = min(120, max(1, int(minutos or ej.duracion_max or cfg["duracion"])))
        ej.objetivo = int(objetivo or ej.objetivo or cfg["objetivo"])
        ej.estado, ej.iniciada, ej.pid, ej.solicitud = "en_curso", ahora(), os.getpid(), None
        db.session.commit()
        inicio = self.reloj()
        fin = inicio + ej.duracion_max * 60
        motivo_fin = "sin tareas pendientes"
        propio_descargador = self.descargador is None
        if propio_descargador:
            self.descargador = Descargador()
        try:
            self._log(f"Jornada #{ej.id}: máximo {ej.duracion_max} min, meta {ej.objetivo} fichas.")
            self._recuperar(ej)
            self._latido(ej, "planificando")
            self._sumar("fuentes_planificadas", self._planificar(ej, cfg))
            mantenimiento_hecho = False
            while True:
                s = self._solicitud(ej)
                if s == "detener":
                    motivo_fin, ej.estado = "detenida por el usuario", "detenida"
                    break
                if s == "pausar":
                    if self._esperar_pausa(ej, fin) == "detener":
                        motivo_fin, ej.estado = "detenida por el usuario", "detenida"
                        break
                fichas = sum(self.contadores.get(k, 0) for k in FICHAS)
                t = self._siguiente(objetivo_alcanzado=fichas >= ej.objetivo)
                restante = fin - self.reloj()
                if t is None:
                    if not mantenimiento_hecho and restante > self.margen + 180:
                        self._latido(ej, "mantenimiento")
                        cerradas, rotos = flujo.revisar_vigencias(self.descargador)
                        db.session.commit()
                        self._sumar("vencidas_cerradas", cerradas)
                        self._sumar("enlaces_rotos", rotos)
                        mantenimiento_hecho = True
                        continue
                    motivo_fin = "meta alcanzada" if fichas >= ej.objetivo else "sin tareas pendientes"
                    break
                if restante < self.margen + COSTO.get(t.tipo, 120):
                    motivo_fin = "límite de tiempo (lo pendiente queda para la próxima jornada)"
                    break
                self._latido(ej, {"consultar_fuente": "investigando", "procesar_hallazgo": "procesando",
                                  "revisar_hallazgo": "reverificando"}.get(t.tipo))
                if t.tipo == "procesar_hallazgo":
                    self._precargar(cfg)
                self._ejecutar_tarea(t, cfg, ej)
            if ej.estado not in ("detenida",):
                ej.estado = "completada"
        except KeyboardInterrupt:
            db.session.rollback()
            ej = db.session.get(Ejecucion, ej.id)
            ej.estado, motivo_fin = "detenida", "interrumpida con Ctrl+C"
            Tarea.query.filter_by(estado="en_curso").update({"estado": "pendiente"})
        except Exception as e:
            db.session.rollback()
            ej = db.session.get(Ejecucion, ej.id)
            ej.estado, ej.error = "fallida", f"{e.__class__.__name__}: {e}\n{traceback.format_exc(limit=5)}"[:4000]
            motivo_fin = "error inesperado"
            Tarea.query.filter_by(estado="en_curso").update({"estado": "pendiente"})
        finally:
            ej.finalizada = ahora()
            ej.etapa = "cerrada"
            ej.contadores_json = json.dumps(self.contadores)
            ej.informe_json = json.dumps(self._informe(ej, motivo_fin, self.reloj() - inicio), ensure_ascii=False)
            db.session.commit()
            liberar_bloqueo(self.propietario)
            if propio_descargador:
                self.descargador.cerrar()
            self._log(f"Jornada #{ej.id} {ej.estado}: {motivo_fin}.")
        return ej

    def _informe(self, ej, motivo_fin, segundos):
        c = self.contadores
        fichas = sum(c.get(k, 0) for k in FICHAS)
        pendientes = Tarea.query.filter_by(estado="pendiente").count()
        fuentes_error = [f.nombre for f in Fuente.query.filter_by(estado="error").all()]
        rec = []
        if pendientes:
            rec.append(f"Quedaron {pendientes} tareas para la próxima jornada.")
        if fuentes_error:
            rec.append("Revisa las fuentes con errores: " + ", ".join(fuentes_error) + ".")
        if fichas < ej.objetivo and not pendientes:
            rec.append(f"Se prepararon {fichas} de {ej.objetivo} fichas: no hubo más oportunidades útiles en las "
                       "fuentes activas. La meta no se fuerza; puedes agregar fuentes autorizadas.")
        if c.get("rechazado", 0) > fichas and c.get("rechazado", 0) >= 3:
            rec.append("Muchos elementos descartados: revisa los filtros (palabras clave) de las fuentes.")
        if c.get("revision", 0):
            rec.append(f"Hay {c['revision']} fichas nuevas esperando revisión en la bandeja.")
        return {"motivo_fin": motivo_fin, "minutos": round(segundos / 60, 1), "fichas": fichas,
                "pendientes": pendientes, "fuentes_con_error": fuentes_error, "contadores": c,
                "recomendaciones": rec}


# ---------- Lanzamiento desde el panel ----------
def lanzar_en_segundo_plano(ejecucion_id, raiz):
    """Inicia `flask autopilot jornada` como proceso aparte (no bloquea al servidor web)."""
    os.makedirs(os.path.join(raiz, "logs"), exist_ok=True)
    log = open(os.path.join(raiz, "logs", f"autopilot_{ejecucion_id}.log"), "a", encoding="utf-8")
    opciones = {}
    if os.name == "nt":
        opciones["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        opciones["start_new_session"] = True
    entorno = dict(os.environ, FLASK_APP="app.py", PYTHONIOENCODING="utf-8")
    return subprocess.Popen([sys.executable, "-m", "flask", "autopilot", "jornada", "--ejecucion", str(ejecucion_id),
                             "--origen", "panel"], cwd=raiz, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=entorno, **opciones)

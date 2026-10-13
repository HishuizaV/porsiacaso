"""CSRF por sesión para todos los formularios y límite simple de peticiones."""
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import session, request, abort

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def exento_csrf(vista):
    """Para APIs JSON que validan el origen por su cuenta."""
    vista._csrf_exento = True
    return vista


def verificar_csrf(app):
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    vista = app.view_functions.get(request.endpoint)
    if vista is not None and getattr(vista, "_csrf_exento", False):
        return
    token = session.get("_csrf")
    enviado = request.form.get("_csrf", "") or request.headers.get("X-CSRF-Token", "")
    if not token or not secrets.compare_digest(token, enviado):
        abort(400)


class Limitador:
    """Ventana deslizante en memoria (válido para un proceso; en varios procesos, por proceso)."""

    def __init__(self, maximo, segundos):
        self.maximo, self.segundos = maximo, segundos
        self.registros = defaultdict(deque)
        self.lock = threading.Lock()

    def permitir(self, clave):
        ahora = time.monotonic()
        with self.lock:
            cola = self.registros[clave]
            while cola and cola[0] <= ahora - self.segundos:
                cola.popleft()
            if len(cola) >= self.maximo:
                return False
            cola.append(ahora)
            if len(self.registros) > 10_000:   # evita crecer sin límite
                for k in [k for k, v in self.registros.items() if not v][:5000]:
                    del self.registros[k]
            return True

    def limpiar(self):
        with self.lock:
            self.registros.clear()


def ip_cliente():
    return request.remote_addr or "?"


# ---------- Límites persistentes (en la base de datos) ----------
# Ventana fija: válidos entre varios procesos o servidores y tras reinicios. Se usan para el
# buscador, el login y el asistente.
def _contador(nombre, clave, segundos, sumar):
    import random
    from sqlalchemy import text
    from extensions import db
    ventana = int(time.time() // segundos)
    k = f"{nombre}:{clave}"[:150]
    if sumar:
        r = db.session.execute(text(
            "UPDATE limite_contador SET cuenta = CASE WHEN ventana = :v THEN cuenta + 1 ELSE 1 END, ventana = :v "
            "WHERE clave = :k"), {"v": ventana, "k": k})
        if r.rowcount == 0:
            db.session.execute(text("INSERT INTO limite_contador (clave, ventana, cuenta) VALUES (:k, :v, 1)"),
                               {"k": k, "v": ventana})
        if random.random() < 0.01:   # limpieza ocasional de ventanas viejas
            db.session.execute(text("DELETE FROM limite_contador WHERE ventana < :v"), {"v": ventana - 100})
        db.session.commit()
    fila = db.session.execute(text("SELECT ventana, cuenta FROM limite_contador WHERE clave = :k"), {"k": k}).first()
    return fila[1] if fila and fila[0] == ventana else 0


def permitir_persistente(nombre, clave, maximo, segundos=60):
    """True si la petición entra en el límite (y la cuenta)."""
    from sqlalchemy.exc import SQLAlchemyError
    from extensions import db
    try:
        return _contador(nombre, clave, segundos, sumar=True) <= maximo
    except SQLAlchemyError:
        db.session.rollback()
        return True   # si la base falla, no se bloquea a los visitantes


def fallos(nombre, clave, segundos):
    return _contador(nombre, clave, segundos, sumar=False)


def registrar_fallo(nombre, clave, segundos):
    return _contador(nombre, clave, segundos, sumar=True)


def borrar_contador(nombre, clave):
    from sqlalchemy import text
    from extensions import db
    db.session.execute(text("DELETE FROM limite_contador WHERE clave = :k"), {"k": f"{nombre}:{clave}"[:150]})
    db.session.commit()

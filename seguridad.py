"""CSRF por sesión para todos los formularios y límite simple de peticiones."""
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import session, request, abort

EXENTOS = set()   # endpoints sin CSRF (APIs JSON que validan el origen por su cuenta)


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


def exento_csrf(vista):
    EXENTOS.add(vista.__module__ + "." + vista.__name__)
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

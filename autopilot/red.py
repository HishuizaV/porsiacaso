"""Descargas seguras para el Autopilot.

Todo contenido externo es un DATO no confiable. Este módulo impide que una fuente haga que el
servidor consulte direcciones internas (SSRF), respeta robots.txt, limita tamaño y tiempo y
espera entre peticiones al mismo dominio.
"""
import ipaddress
import os
import re
import socket
import threading
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

VERSION = "1.0"
# Identificación honesta del cliente. Con dominio propio, defínelo en AUTOPILOT_USER_AGENT con una URL de contacto.
USER_AGENT = os.environ.get(
    "AUTOPILOT_USER_AGENT",
    f"PorSiAcasoBot/{VERSION} (portal informativo peruano; lectura de convocatorias publicas)")
TIPOS_TEXTO = ("text/html", "application/xhtml+xml", "application/rss+xml", "application/atom+xml",
               "application/xml", "text/xml", "application/json", "text/plain")
TIPOS_PDF = ("application/pdf",)
PUERTOS = (None, 80, 443)


class ErrorRed(Exception):
    """Fallo de red recuperable (se puede reintentar)."""


class Bloqueado(Exception):
    """Petición prohibida: dirección interna, esquema no permitido o robots.txt."""


def ip_publica(ip):
    ip = ipaddress.ip_address(ip)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not (ip.is_private or ip.is_loopback or ip.is_link_local or
                                 ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def validar_url(url, resolver=socket.getaddrinfo):
    """Lanza Bloqueado si la URL no es http(s) pública. Devuelve el host."""
    try:
        partes = urlsplit(url)
    except ValueError:
        raise Bloqueado("URL mal formada")
    if partes.scheme not in ("http", "https"):
        raise Bloqueado(f"Esquema no permitido: {partes.scheme or 'ninguno'}")
    if partes.username or partes.password:
        raise Bloqueado("URL con credenciales")
    host = (partes.hostname or "").rstrip(".").lower()
    if not host or "." not in host:
        raise Bloqueado("Host no válido")
    try:
        puerto = partes.port
    except ValueError:
        raise Bloqueado("Puerto no válido")
    if puerto not in PUERTOS:
        raise Bloqueado(f"Puerto no permitido: {puerto}")
    try:   # IP literal
        if not ip_publica(host):
            raise Bloqueado("Dirección IP interna o reservada")
        return host
    except ValueError:
        pass
    try:
        infos = resolver(host, None)
    except (socket.gaierror, UnicodeError, OSError):
        raise ErrorRed(f"No se pudo resolver {host}")
    ips = {i[4][0] for i in infos}
    if not ips or any(not ip_publica(ip) for ip in ips):
        raise Bloqueado(f"{host} apunta a una dirección interna")
    return host


@dataclass
class Respuesta:
    url: str          # URL final (tras redirecciones validadas)
    estado: int
    tipo: str         # content-type sin parámetros
    contenido: bytes
    codificacion: str = None

    @property
    def texto(self):
        try:
            return self.contenido.decode(self.codificacion or "utf-8")
        except (LookupError, UnicodeDecodeError):
            return self.contenido.decode("utf-8", errors="replace")


class Descargador:
    def __init__(self, transporte=None, resolver=socket.getaddrinfo, respetar_robots=True,
                 pausa_dominio=2.0, timeout=20.0, max_bytes=15 * 1024 * 1024,
                 max_redirecciones=5, reintentos=2, dormir=time.sleep, reloj=time.monotonic):
        self.resolver, self.respetar_robots = resolver, respetar_robots
        self.pausa, self.max_bytes = pausa_dominio, max_bytes
        self.max_redir, self.reintentos = max_redirecciones, reintentos
        self.dormir, self.reloj = dormir, reloj
        self.cliente = httpx.Client(transport=transporte, timeout=timeout, follow_redirects=False,
                                    headers={"User-Agent": USER_AGENT,
                                             "Accept-Language": "es-PE,es;q=0.9"})
        self._ultimo, self._robots = {}, {}
        self._locks, self._lock = {}, threading.Lock()
        self.peticiones = 0
        self._cache = {}

    def cerrar(self):
        self.cliente.close()

    # ----- cortesía por dominio -----
    def _esperar_turno(self, host):
        with self._lock:
            lock = self._locks.setdefault(host, threading.Lock())
        with lock:
            espera = self._ultimo.get(host, -1e9) + self.pausa - self.reloj()
            if espera > 0:
                self.dormir(espera)
            self._ultimo[host] = self.reloj()

    # ----- robots.txt -----
    def robots_permite(self, url):
        if not self.respetar_robots:
            return True
        p = urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._pedir(base + "/robots.txt", TIPOS_TEXTO + ("text/html",), 512 * 1024,
                                revisar_robots=False, reintentos=0, aceptar_error=True)
                if r.estado in (401, 403):
                    rp.disallow_all = True
                elif r.estado >= 500:
                    raise ErrorRed("robots.txt no disponible")
                elif r.estado >= 400:
                    rp.allow_all = True
                else:
                    rp.parse(r.texto.splitlines())
            except Bloqueado:
                raise
            except ErrorRed:
                # Ante la duda (servidor caído) no se consulta el sitio en esta jornada
                rp.disallow_all = True
            self._robots[base] = rp
        return self._robots[base].can_fetch(USER_AGENT, url)

    # ----- descarga -----
    def obtener(self, url, tipos=TIPOS_TEXTO, max_bytes=None):
        with self._lock:
            previo = self._cache.pop(url, None)
        if previo is not None:
            if isinstance(previo, Exception):
                raise previo
            return previo
        return self._pedir(url, tipos, max_bytes or self.max_bytes)

    def precargar(self, urls, hilos=2):
        """Descarga en paralelo (moderado) páginas que se procesarán enseguida.
        La pausa por dominio se sigue respetando; los errores se entregan al pedir la URL."""
        from concurrent.futures import ThreadPoolExecutor
        pendientes = [u for u in dict.fromkeys(urls) if u not in self._cache and not re.search(r"\.pdf(\?|$)", u, re.I)]
        if not pendientes:
            return

        def uno(u):
            try:
                r = self._pedir(u, TIPOS_TEXTO, self.max_bytes)
            except (ErrorRed, Bloqueado) as e:
                r = e
            with self._lock:
                self._cache[u] = r
        with ThreadPoolExecutor(max_workers=max(1, min(4, hilos))) as ex:
            list(ex.map(uno, pendientes))

    def obtener_pdf(self, url, max_bytes=None):
        return self._pedir(url, TIPOS_PDF + ("application/octet-stream",), max_bytes or self.max_bytes)

    def _pedir(self, url, tipos, max_bytes, revisar_robots=True, reintentos=None, aceptar_error=False,
               metodo="GET", leer=True):
        reintentos = self.reintentos if reintentos is None else reintentos
        intento = 0
        while True:
            try:
                return self._una_vez(url, tipos, max_bytes, revisar_robots, aceptar_error, metodo, leer)
            except ErrorRed:
                if intento >= reintentos:
                    raise
                self.dormir(2 ** intento * 2)   # 2 s, 4 s, 8 s…
                intento += 1

    def _una_vez(self, url, tipos, max_bytes, revisar_robots, aceptar_error, metodo, leer=True):
        actual = url
        for _ in range(self.max_redir + 1):
            host = validar_url(actual, self.resolver)
            if revisar_robots and not self.robots_permite(actual):
                raise Bloqueado(f"robots.txt no permite {actual}")
            self._esperar_turno(host)
            self.peticiones += 1
            try:
                with self.cliente.stream(metodo, actual) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        destino = r.headers.get("location")
                        if not destino:
                            raise ErrorRed("Redirección sin destino")
                        actual = urljoin(actual, destino)
                        continue
                    if r.status_code == 429 or r.status_code >= 500:
                        raise ErrorRed(f"HTTP {r.status_code}")
                    if r.status_code >= 400 and not aceptar_error:
                        raise Bloqueado(f"HTTP {r.status_code}")   # 4xx no se reintenta
                    tipo = r.headers.get("content-type", "").split(";")[0].strip().lower()
                    if r.status_code < 400 and metodo == "GET" and tipos and tipo and tipo not in tipos:
                        raise Bloqueado(f"Tipo de contenido no permitido: {tipo}")
                    largo = int(r.headers.get("content-length") or 0)
                    if largo > max_bytes and leer:
                        raise Bloqueado(f"Archivo demasiado grande ({largo} bytes)")
                    datos = bytearray()
                    if metodo == "GET" and leer:
                        for trozo in r.iter_bytes():
                            datos.extend(trozo)
                            if len(datos) > max_bytes:
                                raise Bloqueado("Archivo demasiado grande")
                    return Respuesta(str(actual), r.status_code, tipo, bytes(datos), r.encoding)
            except httpx.TimeoutException:
                raise ErrorRed("Tiempo de espera agotado")
            except httpx.TransportError as e:
                raise ErrorRed(f"Error de conexión: {e.__class__.__name__}")
        raise Bloqueado("Demasiadas redirecciones")

    def comprobar_enlace(self, url):
        """(ok, estado, detalle). No descarga el cuerpo completo: HEAD y, si no se admite, GET corto."""
        try:
            r = self._pedir(url, None, 0, aceptar_error=True, metodo="HEAD", reintentos=1, leer=False)
            if r.estado in (403, 405, 501):
                r = self._pedir(url, None, 0, aceptar_error=True, reintentos=1, leer=False)
            return r.estado < 400, r.estado, r.url
        except Bloqueado as e:
            return False, 0, str(e)
        except ErrorRed as e:
            return False, 0, str(e)

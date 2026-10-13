"""Comandos: flask autopilot jornada | estado | pausar | continuar | detener | cargar-fuentes |
probar-fuente | medir-ia | sincronizar."""
import json

import click

from extensions import db
from models import Institucion, Ubicacion


def registrar(app):
    @app.cli.group("autopilot")
    def grupo():
        """PorSiAcaso Autopilot (investigación y preparación editorial por lotes)."""

    @grupo.command("jornada")
    @click.option("--minutos", type=int, help="Duración máxima (máx. 120).")
    @click.option("--objetivo", type=int, help="Fichas útiles buscadas (no obligatorio alcanzarlas).")
    @click.option("--ejecucion", type=int, help="ID de una jornada solicitada desde el panel.")
    @click.option("--origen", default="manual", type=click.Choice(["manual", "programador", "panel"]))
    def jornada(minutos, objetivo, ejecucion, origen):
        """Ejecuta una jornada completa y termina (pensado para el Programador de tareas)."""
        from autopilot.calidad import configuracion
        from autopilot.motor import Motor, YaEnCurso
        from autopilot.modelos import Ejecucion
        cfg = configuracion()
        ia = None
        if cfg["ia"]:
            from autopilot.ia import ClienteIA
            ia = ClienteIA(cfg["ia_modelo"])
            if not ia.disponible():
                click.echo("Ollama no está disponible: se continúa solo con reglas.")
                ia = None
        try:
            ej = Motor(ia=ia, registrar=click.echo).ejecutar(ejecucion, minutos, objetivo, origen)
        except YaEnCurso as e:
            if ejecucion:
                ej = db.session.get(Ejecucion, ejecucion)
                if ej is not None and ej.estado == "solicitada":
                    ej.estado, ej.error = "fallida", str(e)
                    db.session.commit()
            raise click.ClickException(str(e))
        click.echo(json.dumps(ej.informe, ensure_ascii=False, indent=2))

    @grupo.command("estado")
    def estado():
        """Muestra la última jornada."""
        from autopilot.modelos import Ejecucion, Tarea
        ej = Ejecucion.query.order_by(Ejecucion.id.desc()).first()
        if ej is None:
            click.echo("Aún no hay jornadas.")
            return
        click.echo(f"Jornada #{ej.id}: {ej.estado} · etapa {ej.etapa} · {ej.minutos_transcurridos} min")
        click.echo(json.dumps(ej.contadores, ensure_ascii=False))
        click.echo(f"Tareas pendientes: {Tarea.query.filter_by(estado='pendiente').count()}")

    def _solicitar(valor):
        from autopilot.modelos import Ejecucion
        ej = Ejecucion.query.filter(Ejecucion.estado.in_(("en_curso", "pausada"))).order_by(Ejecucion.id.desc()).first()
        if ej is None:
            raise click.ClickException("No hay una jornada en curso.")
        ej.solicitud = valor
        db.session.commit()
        click.echo(f"Solicitud «{valor}» enviada a la jornada #{ej.id}.")

    @grupo.command("pausar")
    def pausar():
        _solicitar("pausar")

    @grupo.command("continuar")
    def continuar():
        _solicitar("continuar")

    @grupo.command("detener")
    def detener():
        """Detención segura: termina la tarea actual, guarda y cierra."""
        _solicitar("detener")

    @grupo.command("cargar-fuentes")
    def cargar_fuentes():
        """Registra las fuentes iniciales investigadas (PAUSADAS, sin permisos). No duplica."""
        from autopilot.fuentes_iniciales import FUENTES, INSTITUCIONES
        from autopilot.modelos import Fuente
        from admin import slug_unico_modelo
        creadas = 0
        insts = {}
        for clave, (nombre, siglas, sector, web) in INSTITUCIONES.items():
            i = Institucion.query.filter_by(nombre=nombre).first()
            if i is None:
                i = Institucion(slug=slug_unico_modelo(Institucion, nombre), nombre=nombre, siglas=siglas,
                                sector=sector, web=web, verificada=False)
                db.session.add(i)
                db.session.flush()
            insts[clave] = i
        for f in FUENTES:
            if Fuente.query.filter_by(url_listado=f["url_listado"], url_principal=f["url_principal"]).first():
                continue
            zona = Ubicacion.query.filter_by(slug=f["zona"]).first() if f["zona"] else None
            db.session.add(Fuente(
                nombre=f["nombre"], institucion=insts[f["inst"]], url_principal=f["url_principal"],
                url_listado=f["url_listado"], tipo_contenido=f["tipo"], ubicacion=zona, formato=f["formato"],
                frecuencia_horas=f["frecuencia"], prioridad=f["prioridad"], confianza="alta",
                estado=f.get("estado", "pausada"), permite_extraccion=False, permite_autopublicacion=False,
                condiciones_acceso=f["condiciones"], observaciones=f["observaciones"],
                config_json=json.dumps(f["config"], ensure_ascii=False)))
            creadas += 1
        db.session.commit()
        click.echo(f"{creadas} fuente(s) registradas en pausa. Actívalas en el panel: Autopilot > Fuentes.")

    @grupo.command("probar-fuente")
    @click.argument("fuente_id", type=int)
    def probar_fuente(fuente_id):
        """Lee el listado de una fuente SIN guardar nada (para revisar la configuración)."""
        from autopilot import adaptadores
        from autopilot.modelos import Fuente
        from autopilot.red import Descargador
        f = db.session.get(Fuente, fuente_id)
        if f is None:
            raise click.ClickException("No existe esa fuente.")
        d = Descargador()
        try:
            items = adaptadores.listar(f, d)
        finally:
            d.cerrar()
        for it in items:
            click.echo(f"- {it.titulo[:90]}\n  {it.url}")
        click.echo(f"{len(items)} elemento(s).")

    @grupo.command("medir-ia")
    @click.option("--modelo", default=None)
    def medir_ia(modelo):
        """Compara reglas vs. IA local en los hallazgos ya guardados (no modifica nada)."""
        from autopilot.calidad import configuracion
        from autopilot.ia import ClienteIA
        from autopilot.medicion import medir
        ia = ClienteIA(modelo or configuracion()["ia_modelo"])
        if not ia.disponible():
            raise click.ClickException("Ollama no responde o el modelo no está instalado.")
        click.echo(json.dumps(medir(ia), ensure_ascii=False, indent=2))

    @grupo.command("sincronizar")
    @click.option("--destino", required=True, help="URL del sitio público, p. ej. https://porsiacaso.pe")
    def sincronizar(destino):
        """Envía al servidor público las fichas preparadas (requiere AUTOPILOT_TOKEN en ambos lados)."""
        from autopilot.sincronizar import enviar_pendientes
        r = enviar_pendientes(destino)
        click.echo(json.dumps(r, ensure_ascii=False, indent=2))

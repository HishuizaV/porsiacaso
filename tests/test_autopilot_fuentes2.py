"""Adaptadores especiales (procesos, tabla, JSON con plantillas, página única) y reglas corregidas
tras la jornada real con las 10 fuentes pedidas (13/10/2026). Estructuras copiadas de las páginas reales."""
import json
from datetime import date

from ap_web import WebSimulada, pdf_con_texto, fecha_es
from extensions import db
from models import Articulo, Institucion, Usuario
from autopilot import adaptadores, calidad, dedup, extraccion, flujo, verificador
from autopilot.modelos import Fuente, Hallazgo, DecisionEditorial
from test_autopilot import procesar_todo

AGRO = """<html><body><main><div class="page__box-text">
<h2>Proceso de Selección N° 001-2026-MIDAGRI-AGRO RURAL-UGRH</h2>
<p>Proceso de contratación de personal CAS D.L. 1057 Contratación de un Apoyo Administrativo para la Unidad de RR.HH.</p>
<ul><li><a href="https://www.gob.pe/i/1-bases">Bases</a></li><li><a href="https://www.gob.pe/i/1-res">Resultados de evaluación</a></li></ul>
</div><div class="page__box-text">
<h2>Proceso de Selección N° 023-2026-MIDAGRI-AGRO RURAL-UGRH</h2>
<p>Proceso de contratación de personal CAS D.L. 1057 - Contratación de un Capitán para la Sub Unidad de Extracción</p>
<ul><li><a href="https://www.gob.pe/i/23-bases">Bases</a></li><li><a href="https://www.gob.pe/i/23-crono">Cronograma</a></li>
<li><a href="https://www.gob.pe/i/anexo-05">Anexo 05</a></li></ul>
</div></main></body></html>"""

TABLA = """<table id="tabla-cas"><tr><td>005-2026</td><td>RESPONSABLE DE ASESORIA LEGAL</td>
<td><a href="admin008/cas/pdf/2026/005-PERFIL.pdf">ver</a></td></tr>
<tr><td>002-2026</td><td>ANALISTA</td><td><a href="admin008/cas/pdf/2026/002-PERFIL.pdf">ver</a>
<a href="admin008/cas/pdf/2026/002-EVALCURRICULAR.pdf">eval</a></td></tr></table>"""


def test_modo_procesos_omite_cerrados_y_saca_el_puesto():
    items = adaptadores.listar_procesos(AGRO, "https://www.gob.pe/", {})
    assert len(items) == 1
    it = items[0]
    assert it.titulo.endswith("– Capitán") and it.id_externo.startswith("023-2026")
    assert it.url == "https://www.gob.pe/i/23-bases"
    assert ("Cronograma", "https://www.gob.pe/i/23-crono") in it.extra["enlaces"]


def test_modo_tabla_omite_filas_en_evaluacion_y_usa_base():
    items = adaptadores.listar_tabla(TABLA, "https://x.gob.pe/controladores/",
                                     {"base_enlaces": "https://x.gob.pe/", "enlace_extra": "https://p.gob.pe/login"})
    assert [i.id_externo for i in items] == ["005-2026"]
    assert items[0].url == "https://x.gob.pe/admin008/cas/pdf/2026/005-PERFIL.pdf"
    assert ("Postulación", "https://p.gob.pe/login") in items[0].extra["enlaces"]


def test_json_con_plantillas_y_exclusion():
    datos = json.dumps([{"SPROCESO": "181-2026", "SSERVICIO": "ANALISTA III ", "BASES": "2026/a.pdf",
                         "RUTA_CARPETA": "https://p.gob.pe/Doc/", "SEDE": "LIMA", "NPLAZAS": 1},
                        {"SPROCESO": "182-2026", "SSERVICIO": "ESPECIALISTA (CANCELADO)", "BASES": "2026/b.pdf",
                         "RUTA_CARPETA": "https://p.gob.pe/Doc/"}])
    cfg = {"plantilla_url": "{RUTA_CARPETA}{BASES}", "plantilla_titulo": "CAS N° {SPROCESO} – {SSERVICIO}",
           "campos": {"id": "SPROCESO"}, "excluir": ["cancelado"]}
    items = adaptadores._filtrar(adaptadores.listar_json(datos, "https://p.gob.pe/", cfg), cfg)
    assert [(i.id_externo, i.url, i.titulo) for i in items] == [("181-2026", "https://p.gob.pe/Doc/2026/a.pdf",
                                                                  "CAS N° 181-2026 – ANALISTA III")]
    assert adaptadores.listar_json("[]", "https://p.gob.pe/", cfg) == []


def test_etapa_concluida_y_cancelacion():
    assert verificador.etapa_concluida([("Descargar", "https://cdn/9-comunicado-n-006-2026-resultados-finales.pdf")])
    assert "cancelada" in verificador.etapa_concluida(
        [("Comunicado", "https://www.gob.pe/i/7770919-comunicado-cancelacion-de-procesos-cas-008-2026")])
    assert verificador.etapa_concluida([("Relación de becarios", "https://cdn/x.pdf")])
    assert verificador.etapa_concluida([("Bases", "https://cdn/bases.pdf"), ("Cronograma", "https://cdn/c.pdf")]) is None


def test_resultados_no_son_boton_de_postular():
    enlaces = [("Resultados de postulantes seleccionados", "https://cdn/x-seleccionados-no-seleccionados.pdf"),
               ("Postula aquí", "https://www.pronabec.gob.pe/beca/")]
    tipos = [(t, u) for t, _e, u in extraccion.clasificar_enlaces(enlaces, "https://www.gob.pe/campana")]
    assert ("postular", "https://www.pronabec.gob.pe/beca/") in tipos
    assert all("seleccionados" not in u for _t, u in tipos)


def test_convocatoria_de_anio_anterior_se_descarta():
    hoy = date(2026, 10, 13)
    p = verificador.verificar_fechas({}, hoy, "beca", None, "Beca Perú 2023")
    assert any(g == "bloqueo" and "2023" in m for g, m in p)
    assert not verificador.verificar_fechas({}, hoy, "beca", None, "Beca 18 convocatoria 2026")


def test_pdf_compartido_no_vuelve_duplicadas_becas_distintas():
    class H:   # objetos mínimos
        def __init__(self, id_, titulo):
            self.id, self.titulo, self.url_normalizada, self.id_externo = id_, titulo, f"u{id_}", None
            self.fuente_id, self.huella_documento, self.codigo_convocatoria, self.huella = 1, "mismo", None, f"h{id_}"
            self.fuente, self.texto, self.tipo_detectado = None, None, "beca"
    a, b, c = H(1, "Beca Inclusión Técnico Productiva 2024"), H(2, "Beca Inclusión Carreras Profesionales 2024"), \
        H(3, "Beca Inclusión Técnico Productiva 2024 – ampliación")
    assert dedup.buscar_duplicado(b, [a]) == (None, None)
    assert dedup.buscar_duplicado(c, [a])[0] is a


def test_fecha_limite_dudosa_no_se_publica(app):
    web = WebSimulada()
    url = "https://www.gob.pe/institucion/muniprueba/informes-publicaciones/9444-beca-larga"
    web.agregar(url, "text/html", f"""<html><head><title>Beca Larga 2026 - X</title></head><body><main><h1>Beca Larga 2026</h1>
<p>El programa otorga la beca a estudiantes destacados de todo el país para estudios universitarios completos.</p>
<p>Dirigido a: Estudiantes de secundaria</p><p>Requisitos:</p><ul><li>Ser peruano</li>
<li>Haber concluido la educación secundaria en un colegio público</li><li>Acreditar alto rendimiento académico</li></ul>
<p>Cobertura:</p><ul><li>Matrícula y pensiones de estudios</li><li>Alimentación, movilidad local y materiales de estudio</li>
<li>Laptop o equivalente y tutoría permanente</li></ul>
<p>Los becarios estudian hasta el 31 de diciembre de 2029.</p>
<p><a href="https://www.gob.pe/postular-beca">Postula aquí</a></p></main></body></html>""")
    web.agregar("https://www.gob.pe/postular-beca", "text/html", "<html>ok</html>")
    with app.app_context():
        inst = Institucion(slug="prog", nombre="Programa", sector="publico")
        f = Fuente(nombre="F", institucion=inst, url_principal=url, url_listado=url, tipo_contenido="beca",
                   formato="html", estado="activa", permite_extraccion=True, config_json='{"modo": "pagina_unica"}')
        db.session.add(f)
        db.session.commit()
        flujo.consultar_fuente(f, web.descargador())
        procesar_todo(web.descargador())
        a = Articulo.query.one()
        assert a.fecha_limite is None and a.estado == "revision"


def test_reevaluar_retira_solo_borradores_intactos(app):
    """Una regla nueva retira fichas del Autopilot que nadie tocó; las revisadas por personas se respetan."""
    from test_autopilot import fuente_gobpe
    web = WebSimulada()
    with app.app_context():
        f = fuente_gobpe()
        desc = web.descargador()
        flujo.consultar_fuente(f, desc)
        procesar_todo(desc)
        emp = Articulo.query.filter_by(tipo="empleo").one()
        conv = Articulo.query.filter_by(tipo="convocatoria").one()
        # Una persona corrigió la convocatoria: el Autopilot ya no debe tocarla
        conv.editado_por_id = Usuario.query.filter_by(email="admin@prueba.test").one().id
        db.session.commit()
        conv_id, emp_titulo = conv.id, emp.titulo
        # La fuente publica resultados del empleo: con las reglas actuales ya no es postulable
        url = Hallazgo.query.filter_by(articulo_id=emp.id).one().url
        e, t, cuerpo, c = web.paginas[url]
        web.agregar(url, t, cuerpo.decode().replace("</main>",
                    '<p><a href="https://cdn.www.gob.pe/x/resultados-finales.pdf">Resultados finales</a></p></main>'))
        r = flujo.reevaluar_borradores(web.descargador(), calidad.configuracion())
        assert [x[0] for x in r["retiradas"]] == [emp_titulo] and r["omitidas"] == 1
        assert Articulo.query.filter_by(tipo="empleo").count() == 0
        assert db.session.get(Articulo, conv_id) is not None
        assert DecisionEditorial.query.filter(DecisionEditorial.articulo_id.is_(None)).count() >= 1


def test_montos_con_formatos_mixtos():
    assert extraccion.leer_monto("13.864.19") == 13864.19
    assert extraccion.leer_monto("2,800.50") == 2800.5
    assert extraccion.leer_monto("2.500") == 2500 and extraccion.leer_monto("2,500") == 2500
    assert extraccion.leer_monto("abc") is None


def test_boton_principal_segun_tipo():
    from tipos import TIPOS
    enlaces = extraccion.clasificar_enlaces([("Inscríbete aquí", "https://facilita.gob.pe/t/1")], "https://www.gob.pe/c", "convocatoria")
    assert ("postular", None, "https://facilita.gob.pe/t/1") in enlaces
    assert TIPOS["curso"]["cta"] == "inscripcion" and TIPOS["bono"]["cta"] == "consulta"


def test_misma_plantilla_distinto_proceso_no_es_duplicado():
    texto = "Perfil del puesto. Requisitos: experiencia en el sector público, formación universitaria. " * 6

    class H:
        def __init__(self, id_, ext):
            self.id, self.fuente_id, self.id_externo, self.titulo = id_, 16, ext, f"CAS N° {ext}"
            self.url_normalizada, self.huella_documento, self.codigo_convocatoria = f"u{id_}", None, None
            self.huella, self.fuente, self.texto, self.tipo_detectado = f"h{id_}", None, texto + ext, "empleo"
    assert dedup.buscar_duplicado(H(2, "006-2026"), [H(1, "005-2026")]) == (None, None)


def test_puesto_desde_el_titulo():
    d = extraccion._cargo("Convocatoria CAS N° 005-2026 – RESPONSABLE DE ASESORIA LEGAL", "texto sin etiquetas", "u", "empleo")
    assert d.valor == "RESPONSABLE DE ASESORIA LEGAL"


def test_duracion_del_contrato_no_es_fecha_limite():
    t = ("Duración del contrato: Hasta el 31 de diciembre de 2026 o hasta el retorno del titular del puesto, "
         "con posibilidad de prórroga. Remuneración mensual S/ 4,064.19")
    assert extraccion.fecha_limite(t, "u", date(2026, 10, 13)).estado == "no_encontrado"
    assert extraccion.fecha_limite("Inscripciones hasta el 20 de octubre de 2026.", "u",
                                   date(2026, 10, 13)).valor == date(2026, 10, 20)


def test_head_404_se_confirma_con_get():
    web = WebSimulada()
    import httpx

    def manejador(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(404 if req.method == "HEAD" else 200, text="ok")
    from autopilot.red import Descargador
    from ap_web import resolver_publico
    d = Descargador(transporte=httpx.MockTransport(manejador), resolver=resolver_publico, pausa_dominio=0,
                    dormir=lambda s: None)
    assert d.comprobar_enlace("https://plataforma.gob.pe/Login")[0] is True

"""La migración del CMS conserva los datos existentes (se prueba sobre una base temporal)."""
import os
import sqlite3

from flask_migrate import upgrade, downgrade

from app import crear_app

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_migracion_conserva_datos_y_urls(tmp_path):
    ruta = tmp_path / "migra.db"
    app = crear_app({"SQLALCHEMY_DATABASE_URI": f"sqlite:///{ruta}", "TESTING": True,
                     "UPLOAD_FOLDER": str(tmp_path / "up")})
    carpeta = os.path.join(RAIZ, "migrations")
    with app.app_context():
        upgrade(directory=carpeta, revision="f176f384db00")   # esquema anterior

    con = sqlite3.connect(ruta)
    con.execute("insert into usuario (id, nombre, email, password_hash, rol, activo) "
                "values (1, 'Ana', 'ana@x.pe', 'h', 'admin', 1)")
    con.execute("insert into categoria (id, slug, corto, nombre, orden, visible) values (1, 'empleo', 'Empleo', 'Empleo', 0, 1)")
    con.execute("insert into ubicacion (id, slug, nombre, tipo) values (1, 'lambayeque', 'Lambayeque', 'region')")
    con.execute("insert into pagina (id, slug, titulo, contenido) values (1, 'contacto', 'Contacto', '<p>x</p>')")
    con.execute("insert into articulo (id, slug, titulo, resumen, contenido, estado, destacado, visitas, lectura, "
                "fecha_publicacion, creado, actualizado, categoria_id, autor_id, ubicacion_id, datos_texto, fuente_url) "
                "values (7, 'nota-antigua', 'Nota antigua', 'Resumen', '<p>Hola</p>', 'publicado', 0, 42, 1, "
                "'2026-09-30 10:00:00', '2026-09-30 10:00:00', '2026-09-30 10:00:00', 1, 1, 1, 'Sueldo: S/ 1500', "
                "'https://www.gob.pe')")
    con.commit()
    con.close()

    with app.app_context():
        upgrade(directory=carpeta)   # a la última versión

    con = sqlite3.connect(ruta)
    fila = con.execute("select id, slug, titulo, tipo, visitas, datos_texto, fuente_url, ubicacion_id "
                       "from articulo").fetchone()
    assert fila == (7, "nota-antigua", "Nota antigua", "noticia", 42, "Sueldo: S/ 1500", "https://www.gob.pe", 1)
    assert con.execute("select visible from pagina").fetchone() == (1,)
    assert con.execute("select count(*) from usuario").fetchone() == (1,)
    assert con.execute("pragma integrity_check").fetchone() == ("ok",)
    con.close()

    # La URL antigua sigue funcionando con la app nueva
    r = app.test_client().get("/articulo/nota-antigua")
    assert r.status_code == 200 and "Nota antigua" in r.get_data(as_text=True)

    # La migración es reversible sin perder el artículo
    with app.app_context():
        downgrade(directory=carpeta, revision="f176f384db00")
        upgrade(directory=carpeta)
    con = sqlite3.connect(ruta)
    assert con.execute("select slug from articulo").fetchone() == ("nota-antigua",)
    con.close()

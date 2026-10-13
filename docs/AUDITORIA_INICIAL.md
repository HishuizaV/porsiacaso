# Auditoría inicial — PorSiAcaso

Fecha: 13 de octubre de 2026 · Rama `main` · último commit `c7898c9 Zonas y categorias editables`.

Este informe describe el estado **real** del repositorio antes de cualquier cambio.

## 1. Dependencias y entorno

| Elemento | Estado |
|---|---|
| Python (venv) | 3.13.14 (`venv/`, no versionado) |
| Flask / Werkzeug / Jinja2 | 3.1.3 / 3.1.9 / 3.1.6 |
| SQLAlchemy / Flask-SQLAlchemy | 2.1.1 / 3.1.1 |
| Flask-Login / Flask-Migrate / Alembic | 0.6.3 / 4.1.0 / 1.20.0 |
| bleach / Pillow | 6.4.0 / 12.3.0 |
| psycopg2-binary | 2.9.13 (no se usa en local) |
| SQLite | 3.50.4, **FTS5 disponible** |
| Pruebas | **No existían** (pytest no instalado) |

- `requirements.txt` estaba guardado en **UTF‑16** (generado con `pip freeze >` en PowerShell). pip lo tolera, pero otras herramientas no; se convierte a UTF‑8.
- Existe un directorio vacío `app/` (no versionado). No interfiere porque `app.py` tiene precedencia, pero conviene eliminarlo manualmente.

## 2. Estructura y modelos

Proyecto plano: `app.py` (app global + rutas públicas + comandos CLI), `admin.py` (blueprint `/admin`), `models.py`, `extensions.py`, `utils.py`, `datos_iniciales.py`.

Modelos: `Usuario` (rol admin/editor, activo), `Categoria` (slug, corto, icono, orden, visible), `Ubicacion` (región/ciudad con `padre_id`), `Articulo` (contenido HTML + `datos_texto` "Clave: valor" + `fuente_url`, estado borrador/publicado, destacado, visitas), `Pagina` (páginas fijas).

## 3. Base de datos real (`porsiacaso.db`)

| Tabla | Filas |
|---|---|
| usuario | 1 (administrador) |
| categoria | 7 |
| pagina | 5 (sobre-nosotros, politica-editorial, contacto, privacidad, terminos) |
| ubicacion | 26 (25 regiones + Chiclayo) |
| articulo | **0** |
| alembic_version | `f176f384db00` (al día con las migraciones) |

`porsiacaso.respaldo.db` es un respaldo anterior en la revisión `178622a5e0e6` (sin zonas). **No se toca.**

Respaldo nuevo creado antes de cualquier migración: `respaldos/porsiacaso_20261013_024155_antes_fase1.db` (integridad `ok`, mismos conteos, SHA‑256 `ac63cb64…a7a1a7`). `*.db` ya está en `.gitignore`.

## 4. Rutas

Públicas: `/`, `/categoria/<slug>`, `/zona/<slug>`, `/articulo/<slug>`, `/buscar`, `/sitemap.xml`, `/robots.txt`, `/<slug>` (páginas fijas, comodín).
Admin: login/logout, listado de artículos, formulario único de artículo, vista previa, publicar/despublicar, eliminar, categorías, zonas, páginas (solo editar), usuarios (crear/activar), cuenta.

## 5. Hallazgos

### Funcionales
1. **Todo es "artículo".** Un empleo, una beca o un trámite se publican como texto libre + "datos clave" en formato `Clave: valor`. No hay campos estructurados, ni fechas límite, ni vigencia, ni botones de postulación (solo un único "Ir a la fuente oficial").
2. Estados limitados a borrador/publicado: no hay archivado, revisión, programación ni duplicado.
3. Búsqueda `ILIKE` solo sobre título y resumen, **sensible a tildes** ("tramite" no encuentra "trámite"), sin paginación ni filtros.
4. Listados de categoría y zona sin paginación (`.all()`).
5. Contador de visitas hace un `commit` en cada lectura pública (bloqueos de escritura en SQLite bajo carga).
6. No hay instituciones/empresas como entidad.
7. Las páginas fijas no se pueden crear desde el panel (solo editar) y no existen: descargo de responsabilidad, publicidad, correcciones.

### SEO
8. `favicon.png` se referencia pero **no existe** (404 en cada página).
9. Imágenes estáticas de ~2 MB (PNG) usadas como `hero` y `og:image`: perjudica LCP y peso en móvil.
10. JSON-LD `Organization` en todas las páginas por defecto; `Article/NewsArticle` y `BreadcrumbList` correctos en artículos. No hay `WebSite`.
11. El canonical por defecto usa `request.path` (correcto), pero los resultados de búsqueda dependen de `cat=None` → título "Resultados de búsqueda" sin `noindex` explícito para la URL con `q` vacía (sí aplica noindex por la condición). Correcto en lo esencial.
12. Sitemap incluye categorías/zonas con contenido y páginas fijas: correcto; `robots.txt` correcto.
13. Enlaces de redes sociales en la barra superior apuntan a `#` (enlaces falsos).

### Publicidad / AdSense
14. `ANUNCIOS` vale `maqueta` **por defecto** y los recuadros "Publicidad" se muestran a **todos los visitantes**. Con `adsense` no se inserta ningún código: el modo real no estaba implementado.
15. No existe `ads.txt` ni configuración del ID de editor.
16. La página Contacto y la Política de privacidad contienen el correo de ejemplo `contacto@tudominio.com`.

### Seguridad
17. `SECRET_KEY` tiene un valor por defecto conocido; nada impide arrancar en producción con él.
18. CSRF propio implementado solo en el blueprint admin (correcto para lo existente; no cubre futuros formularios públicos).
19. Límite de intentos de login en memoria (válido para un solo proceso).
20. Sanitización con bleach en servidor: correcta. Los enlaces del contenido no reciben `rel` seguro.
21. Imágenes validadas con Pillow y reescritas como JPG (bien); no se limita el número de píxeles (riesgo de "decompression bomb") ni se guardan dimensiones (CLS).
22. Quill 1.3.7 desde CDN. Tiene un XSS conocido del lado cliente; mitigado porque el servidor sanitiza.

### Windows
23. Funciona en Windows (venv con `Scripts/`). Las rutas usan `os.path`. `requirements.txt` UTF‑16 es el único problema detectado.

## 6. Qué se reutiliza

- Modelo `Articulo` como entidad editorial general (IDs, slugs y URLs se conservan).
- `Categoria`, `Ubicacion`, `Pagina`, `Usuario`, roles y login con bloqueo.
- Sanitización bleach, procesamiento de imágenes, `slugify`, CSRF por sesión.
- Quill como editor de texto enriquecido (se conserva la versión, el servidor sanitiza).
- Sitemap, robots y JSON-LD de artículos como base.

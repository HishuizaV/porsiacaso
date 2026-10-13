# Estado del proyecto

Última actualización: 13/10/2026.

## Terminado y probado

| Área | Detalle |
|---|---|
| Protección de datos | Respaldos verificados en `respaldos/` (antes y después de la auditoría). Migración aditiva aplicada a `porsiacaso.db`: 1 usuario, 7 categorías, 26 zonas y 5 páginas intactos. `flask respaldo` creado |
| CMS por tipos | 10 tipos (`tipos.py`), tablas de detalle 1 a 1, enlaces/botones tipados con URL o PDF, instituciones creadas en línea, FAQ, aviso destacado, notas internas |
| Estados | borrador, revisión, publicado, programado (fecha futura, sin tareas cron), archivado; vigencia abierta / por confirmar / cerrada; vencida automática |
| Panel | Resumen con cifras reales, alertas editoriales, por vencer, listado con búsqueda/filtros/orden/paginación, duplicar, archivar, despublicar, eliminar con confirmación, vista previa fiel, checklist antes de publicar, bitácora, roles, instituciones, páginas (crear/ocultar), configuración |
| Público | Inicio según contenido real, secciones por tipo con filtros y paginación, páginas regionales (`/empleos/region/lambayeque`), fichas especializadas, búsqueda sin tildes con relevancia, 301 desde `/articulo/<slug>` |
| SEO | Titles, descriptions, canonicals (también paginados), noindex en filtros/búsqueda/vacíos/archivados, sitemap por tipo, robots, OG, favicon, WebSite/Organization (inicio), BreadcrumbList, Article/NewsArticle, JobPosting estricto, imágenes optimizadas (hero 2 MB → 107 KB) |
| Publicidad | off / maqueta (solo admins) / AdSense con ID validado; `ads.txt`; meta de verificación |
| Asistente | Reglas + sinónimos + detección de región, solo enlaces internos publicados y vigentes, pregunta la región, rechaza datos sensibles, 20 msg/min por IP, verificación de origen, desactivable, sin almacenamiento |
| Seguridad | CSRF global, `SECRET_KEY` obligatoria en producción, cabeceras (nosniff, SAMEORIGIN, HSTS en prod, no-store en admin), sanitización bleach con `rel` seguro, validación de URL, imágenes (Pillow + límite de píxeles), PDFs por firma, borrado de archivos sin rutas arbitrarias, panel completo tras login |
| Pruebas | 85 pruebas pytest en verde (`python -m pytest -q`, ~85 s) |
| Visual | Revisado con Edge headless a 375 px y 1366 px: sin desborde horizontal |

## Archivos

Nuevos: `tipos.py`, `web.py`, `admin_contenido.py`, `admin_sitio.py`, `consultas.py`, `seo.py`, `asistente.py`, `ajustes.py`, `seguridad.py`, `templates/{seccion,listado,buscar,publicacion,error,_asistente}.html`, `templates/fichas/*`, `templates/admin/{publicaciones,nueva,publicacion_form,_enlace_fila,_faq_fila,instituciones,institucion_form,configuracion,registros}.html`, `static/img/*`, `tests/*`, `docs/*`, `README.md`, `.env.example`, `requirements-dev.txt`.
Modificados: `app.py` (factory), `models.py`, `admin.py`, `utils.py`, `datos_iniciales.py`, plantillas base, CSS, JS, `requirements.txt` (UTF-16 → UTF-8).
Eliminados (reemplazados): `templates/{articulo,categoria,zona,_sidebar}.html`, `templates/admin/articulo_form.html`.

## Migraciones

`b7e4a2c91d05_cms_por_tipos` (aditiva, reversible; probada sobre copia real y en `tests/test_migraciones.py`).

## Decisiones

- `Articulo` sigue siendo la entidad general (conserva IDs/URLs); detalles por dominio en tablas 1 a 1 (ver `PLAN_IMPLEMENTACION.md`).
- "Vencida" se calcula, no se guarda: no depende de tareas programadas.
- Convocatorias con varias plazas y becas/cursos **no** llevan JobPosting ni otros tipos que Google no admite para este caso. FAQPage no se usa (Google lo limita a sitios gubernamentales y de salud).
- Búsqueda con columna normalizada + LIKE (portable a PostgreSQL); FTS5 está disponible pero no es necesario con el volumen actual.
- Las páginas institucionales nuevas se crearon **ocultas** con `[PENDIENTE]`: no se publica contenido sin revisión.
- Los editores pueden publicar sus propias publicaciones (comportamiento previo conservado); no pueden eliminar una publicada ni destacar.
- Quill 1.3.7 se conserva (no soporta tablas); para tablas se usan «Datos clave».

## Pendiente / conocido

- Contenido real: la base no tiene publicaciones. Hay que cargarlas a mano con fuentes verificadas.
- Datos institucionales: correo de contacto real, revisar privacidad/términos y completar páginas ocultas.
- Contacto y Privacidad existentes aún contienen `contacto@tudominio.com` (el panel lo alerta).
- Límite de login y del asistente en memoria: válido por proceso; con varios procesos cada uno tiene su contador.
- Quill se carga desde jsDelivr (solo en el panel).
- `migrations/env.py` genera un aviso de deprecación de Flask-SQLAlchemy (inofensivo).
- No medido aún: PageSpeed en servidor real, validación con la Prueba de resultados enriquecidos (requiere URL pública).
- Mejoras posibles: modelo de "Fuentes", redirecciones al cambiar slug, Ollama opcional para el asistente, FTS5.
- Directorio vacío `app/` fuera de Git: puede borrarse a mano.

## Continuar tras una interrupción

1. `.\venv\Scripts\Activate.ps1` y `python -m pytest -q`.
2. `git log --oneline` para ver los bloques hechos.
3. Revisar esta lista "Pendiente".

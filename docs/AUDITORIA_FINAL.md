# Auditoría final — PorSiAcaso

Fecha: 13/10/2026 · Rama `main` · commits `df9f36d` y `b6dbc0e` (locales, **no** enviados a GitHub, nada desplegado).

Criterio: solo se marca como **comprobado** lo verificado con una prueba automática, una ejecución real o una inspección del código hecha durante esta auditoría. Lo que no se pudo comprobar se indica explícitamente.

Evidencia recogida en esta auditoría:
- `python -m pytest -q` → **85 passed, 0 failed** (8 avisos de deprecación, ver §9).
- `flask db current` → `b7e4a2c91d05 (head)`; `flask db check` → «No new upgrade operations detected».
- Asistente probado en un navegador real (Edge headless, base de demostración temporal): abre el panel, envía «Busco trabajo en Chiclayo», muestra 1 resultado con enlace interno real; el enlace «Ver todo» devuelve ese mismo resultado.
- 50 búsquedas seguidas en `/buscar`: las 50 respondidas (confirma que el buscador **no** tiene límite de peticiones).
- Peso medido en local: HTML de inicio 13 KB, ficha de empleo 15 KB, CSS 26 KB, JS 6,5 KB, imagen de portada 42 KB (móvil) / 107 KB (escritorio).

---

## 1. Funcionalidades completamente implementadas (comprobadas)

| Funcionalidad | Cómo se comprobó |
|---|---|
| Conservación de datos: migración aditiva, IDs/slugs/URLs intactos, `/articulo/<slug>` sigue funcionando y redirige 301 para tipos nuevos | `test_migraciones.py` (base con datos antiguos → upgrade → downgrade → upgrade); conteos en la base real antes/después |
| CMS por tipos (10 tipos) con formularios especializados | `test_formularios_especializados`, `test_selector_de_tipos` |
| Publicar un empleo sin HTML, con institución creada sola y botones automáticos | `test_editor_publica_empleo_sin_html` (envío del formulario real → ficha pública con los enlaces ingresados) |
| Borradores incompletos permitidos; publicación bloqueada sin datos obligatorios ni fuente | `test_borrador_incompleto_se_guarda_pero_no_se_publica`, `test_curso_gratuito_exige_fuente` |
| Programar, archivar, despublicar, duplicar, eliminar, vista previa | `test_programar_publicacion`, `test_acciones_…`, `test_vista_previa_borrador` |
| Vencimiento automático (aviso, sin botón de postular, fuera de vigentes) | `test_vencida_muestra_aviso_y_oculta_postular` |
| Secciones con filtros, paginación real y páginas regionales | `test_filtros_de_empleo`, `test_paginacion_real`, `test_pagina_regional` |
| Fichas de beca, curso, bono (con «pendiente de verificación») y trámite (pasos) | `test_curso_beca_bono_fichas_especializadas`, `test_sin_enlaces_no_hay_botones_vacios` |
| Buscador sin tildes con relevancia | `test_buscador_sin_tildes_y_relevancia` |
| Panel con cifras reales, filtros, roles, bitácora, páginas ocultas, configuración validada | `test_panel_resumen_con_cifras_reales`, `test_listado_admin_filtra`, `test_paginas_institucionales_editables`, `test_configuracion_valida_ids`, `test_cambio_de_rol_y_desactivar` |
| Permisos editor/admin | `test_editor_sin_acceso_a_zonas_de_admin`, `test_editor_no_edita_publicaciones_ajenas`, `test_editor_no_elimina_publicada_ni_destaca` |
| SEO técnico y JSON-LD (ver §7) | `test_seo.py` (10 pruebas) |
| Publicidad en 3 modos + `ads.txt` (ver §7) | `test_seguridad.py` (5 pruebas de publicidad) |
| Asistente (ver §8) | `test_asistente.py` (12) + prueba en navegador |
| CSRF, sanitización, validación de URL/imagen/PDF, cabeceras, `SECRET_KEY` en producción | `test_seguridad.py` |
| Diseño adaptable sin desborde horizontal a 375 px | Medición `scrollWidth` en Edge headless (inicio, `/empleos`, ficha de empleo) + capturas revisadas a 375 y 1366 px |
| Respaldo verificable | `flask respaldo` ejecutado sobre la base real (integridad `ok`, SHA-256) |

## 2. Pendientes o incompletas

**Pedidas en el encargo y no implementadas:**
- Límite de peticiones / antiabuso en el **buscador** (`/buscar`). Solo el asistente y el login tienen límite. *Confirmado en esta auditoría.*
- Menús editables e «Identidad visual» configurables desde el panel.
- Módulo independiente de **Fuentes** (hoy: nombre + URL por publicación).
- Componentes dentro del editor (botones, recuadros, tablas, imágenes en el cuerpo). Se resolvió con campos estructurados (botones, aviso, datos clave, FAQ); Quill 1.3.7 sigue sin tablas ni imágenes en el texto.
- Caché de páginas y medición de rendimiento con Lighthouse/PageSpeed (solo hay pesos medidos en local, §intro).
- Auditoría de accesibilidad automatizada (axe/Lighthouse). Hay HTML semántico, etiquetas y contraste pensado, pero **no medido**.
- Redirecciones 301 si en el futuro se cambia un slug (hoy el slug no se puede cambiar, por diseño).
- Páginas de autor; imagen social específica por tipo (se usa la de la publicación o una genérica).
- Pruebas visuales automatizadas (las capturas fueron manuales).

**Parciales:**
- Roles: solo administrador y editor (sin rol «revisor»). Los editores **pueden publicar directamente** sus publicaciones (comportamiento heredado, conservado).
- Estados de carga: solo en el asistente («Buscando…»); los formularios no muestran indicador al enviar.
- Páginas institucionales nuevas (descargo, publicidad, correcciones) creadas **ocultas** con `[PENDIENTE]`; Contacto y Privacidad existentes conservan `contacto@tudominio.com`.
- Contenido: la base real tiene **0 publicaciones**. El portal está vacío hasta que se cargue información verificada.

## 3. Archivos y modelos modificados

**Modelos** (`models.py`):
- `Articulo`: nuevas columnas `tipo`, `imagen_ancho`, `imagen_alto`, `fuente_nombre`, `fecha_limite`, `vigencia`, `verificado_en`, `aviso`, `faq_json`, `notas_internas`, `busqueda`, `busqueda_titulo`, `institucion_id` + índices. Columnas anteriores intactas.
- `Pagina`: nueva columna `visible`.
- Nuevas tablas: `institucion`, `detalle_empleo`, `detalle_beca`, `detalle_curso`, `detalle_beneficio`, `detalle_tramite`, `enlace`, `ajuste`, `registro`.
- Sin cambios: `Usuario`, `Categoria`, `Ubicacion`.

**Archivos** (diferencia contra `c7898c9`: 78 archivos, +6597 / −1546 líneas):
- Nuevos: `tipos.py`, `web.py`, `admin_contenido.py`, `admin_sitio.py`, `consultas.py`, `seo.py`, `asistente.py`, `ajustes.py`, `seguridad.py`, migración `b7e4a2c91d05`, 22 plantillas, `static/img/*` (derivados optimizados; originales intactos), `tests/*` (7 archivos), `docs/*`, `README.md`, `.env.example`, `requirements-dev.txt`.
- Modificados: `app.py` (patrón factory), `admin.py`, `models.py`, `utils.py`, `datos_iniciales.py`, `requirements.txt` (UTF‑16 → UTF‑8, mismo contenido), `.gitignore`, CSS, JS, plantillas base y de panel.
- Eliminados (reemplazados): `templates/articulo.html`, `categoria.html`, `zona.html`, `_sidebar.html`, `admin/articulo_form.html`.
- No tocados: `porsiacaso.respaldo.db`, `static/images/*`, migraciones anteriores.

## 4. Migraciones

| Revisión | Estado |
|---|---|
| `178622a5e0e6`, `f176f384db00` | Ya existían y estaban aplicadas |
| `b7e4a2c91d05_cms_por_tipos` (nueva) | **Aplicada** a `porsiacaso.db` el 13/10/2026 |

Antes de aplicarla: respaldo `respaldos/porsiacaso_20261013_024155_antes_fase1.db` (integridad ok) y una prueba sobre una copia. Después: 1 usuario, 7 categorías, 26 zonas y 5 páginas iguales que antes, más 3 páginas nuevas ocultas (`flask completar-paginas`). Hay un segundo respaldo: `porsiacaso_20261013_032001.db`. Reversibilidad comprobada solo en base temporal (`test_migraciones.py`), **no** sobre la base real.

## 5. Pruebas

Ejecutadas en esta auditoría: **85 pasaron, 0 fallaron** (`test_admin` 26, `test_seguridad` 21, `test_publico` 15, `test_asistente` 12, `test_seo` 10, `test_migraciones` 1).

Historial honesto: en la primera ejecución fallaron 3 pruebas por un error del **propio dispositivo de pruebas** (generaba slugs distintos a los de la app); se corrigió el dispositivo, no el código evaluado.

**Sin prueba automática:**
- Comandos CLI `iniciar`, `completar-paginas`, `respaldo`, `crear-admin` (ejecutados a mano una vez).
- JavaScript del panel: agregar/quitar botones y preguntas, vista previa de imagen, checklist, editor Quill. Solo se comprobó que renderizan, no su interacción.
- Funcionamiento con PostgreSQL (`psycopg2` está instalado, pero nunca se ejecutó contra PostgreSQL).
- Validación de JSON-LD con la herramienta oficial de Google (requiere una URL pública).

## 6. ¿El panel publica empleos, becas y otros con campos y botones automáticos?

**Sí, comprobado** para empleo con el formulario real (prueba de extremo a extremo). Becas, cursos, bonos, trámites, guías y noticias tienen formularios propios, comprobados porque renderizan y se validan (guía y noticia también se publicaron vía formulario en las pruebas). Becas, cursos, bonos y trámites se publicaron en pruebas creándolos directamente en la base, no a través del formulario.

Los botones salen de los enlaces ingresados: el formulario trae precargadas las filas típicas de cada tipo (p. ej. «Postular en sitio oficial», «Ver convocatoria», «Ver bases» en empleo), o se suben PDFs. Sin enlace no se dibuja botón; los enlaces externos llevan `target="_blank" rel="noopener noreferrer nofollow"`. Las URL `javascript:` y similares se rechazan.

## 7. SEO y preparación para AdSense

**SEO — implementado y probado:** titles y descriptions por página, canonical (también en páginas 2+), `noindex` en búsquedas, filtros, secciones vacías, archivadas y vistas previas, sitemap con solo contenido publicado y secciones con contenido, robots que bloquea `/admin/` y `/api/`, 404 reales, Open Graph, favicon, breadcrumbs, `WebSite`/`Organization` (solo en el inicio), `Article`/`NewsArticle`. `JobPosting` solo cuando se cumplen todas estas condiciones: tipo empleo publicado y vigente, verificado, con institución, cargo, ubicación (o remoto), descripción ≥150 caracteres y enlace o fuente. No se marcan las convocatorias con varias plazas, las becas, los cursos ni los listados.
**No comprobado:** validación en Rich Results Test y en Search Console (requiere un sitio público).

**AdSense — preparación técnica implementada y probada:** publicidad desactivada por defecto; la maqueta solo la ven los administradores y no carga código de Google; AdSense solo se activa con un ID `ca-pub-` de 16 dígitos válido y bloques numéricos; etiqueta `google-adsense-account`; `/ads.txt` editable (404 si está vacío); anuncios rotulados y lejos de los botones de postulación.
**Falta (manual):** dominio propio con HTTPS, contenido real suficiente, completar las páginas legales con datos reales, solicitar la revisión. **No hay garantía de aprobación.**

## 8. ¿El chatbot funciona?

**Sí, funciona** (no es una maqueta). Comprobado por API (12 pruebas) y en navegador real. Por reglas, sin IA de pago: detecta la intención (empleo, beca, curso, bono, trámite, guía, noticia), la región/ciudad y palabras clave; pregunta la región si falta; devuelve solo publicaciones publicadas y vigentes con URL interna; si no hay resultados lo dice sin inventar. Rechaza números tipo DNI, tarjetas y contraseñas. Límite de 20 mensajes/min por IP y 600/min global, rechaza origen cruzado, no guarda conversaciones, se puede desactivar.

**Limitaciones reales:** entiende solo el vocabulario de su lista (sin errores ortográficos ni frases complejas); conversación de un solo nivel (recuerda tipo y región, nada más); el límite está en memoria (se reinicia con el proceso). Detalle menor: el texto dice «1 resultado vigente(s)».

## 9. Problemas de seguridad y compatibilidad que siguen existiendo

| # | Problema | Riesgo | Sugerencia |
|---|---|---|---|
| 1 | `/buscar` sin límite de peticiones (confirmado) | Medio: consultas LIKE sin índice → abuso de CPU | Aplicar el `Limitador` existente |
| 2 | Cualquier editor puede editar cualquier institución (web, logo) y reemplazar su logo desde el formulario de publicación | Medio: afecta publicaciones de otros | Restringir a administradores o al primer creador |
| 3 | Editores publican sin revisión | Editorial | Rol revisor / publicar solo admin (decisión tuya) |
| 4 | Quill desde jsDelivr sin `integrity` (SRI); Quill 1.3.7 tiene un XSS conocido del lado del cliente | Bajo: solo en el panel y el servidor sanitiza | Agregar SRI o servir Quill localmente |
| 5 | Límites de login y del asistente en memoria | Bajo con 1 proceso; con varios procesos, cada uno cuenta por separado | Contador en la base de datos si se escala |
| 6 | La sesión no se regenera al iniciar sesión (cookie firmada de Flask; `session_protection="strong"` activo) | Bajo | `session.clear()` antes de `login_user` |
| 7 | El contador de visitas escribe en la base en cada visita anónima | Rendimiento en SQLite con mucho tráfico | Agregar en lote o quitarlo |
| 8 | Sin Content-Security-Policy | Bajo | Definirla cuando AdSense esté activo (requiere permitir sus dominios) |
| 9 | Búsqueda del panel con `ilike` sin escapar `%` y `_` | Muy bajo (solo usuarios con sesión; actúan como comodines) | Escapar |
| 10 | La consola de Windows (cp1252) no imprime algunos caracteres en la CLI; se corrigió el único caso detectado (`→`) | Bajo | Mantener los mensajes CLI en caracteres latinos |
| 11 | Avisos de deprecación de `get_engine` en `migrations/env.py` (plantilla de Flask-Migrate) | Ninguno hoy; romperá en Flask-SQLAlchemy 3.2 | Actualizar `env.py` antes de subir de versión |
| 12 | Solo probado en Python 3.13 + SQLite en Windows | Compatibilidad | Probar PostgreSQL antes de usarlo |
| 13 | Directorio vacío `app/` fuera de Git | Ninguno | Borrarlo a mano |

## 10. Arquitectura recomendada para investigación y publicación automatizada

Principio: **la automatización investiga y redacta borradores; una persona verifica y publica**. Publicar en masa sin revisión contradice la política editorial, el riesgo de datos falsos y las políticas de AdSense sobre contenido automático de poco valor.

```
Fuentes oficiales ──► Recolectores ──► Hallazgos (crudos) ──► Extracción ──► Candidatos
 (RSS, portales,      (1 adaptador     + deduplicación por     (reglas;     (borrador tipado
  APIs públicas)       por fuente)      URL y huella)           LLM local    + procedencia)
                                                                opcional)          │
                                                     Revisión humana en el panel ◄─┘
                                                     (verificar → publicar con el
                                                      mismo validar_publicacion)
                                                                   │
                         Vigilancia: enlaces rotos, cambios de fecha, cierre → alertas
```

Componentes propuestos (sin implementar):
1. **Paquete `investigacion/`** con un adaptador por fuente (`fuentes/servir.py`, etc.) y una interfaz común `recolectar() -> list[Hallazgo]`. Respetar `robots.txt`, los términos de uso, un User-Agent identificado y pausas entre peticiones; preferir RSS/API oficiales.
2. **Modelos nuevos:** `FuenteMonitoreada` (URL, tipo por defecto, frecuencia, activa, último error), `Hallazgo` (URL, huella SHA‑256 del contenido, texto crudo, fecha, estado `nuevo|descartado|duplicado|convertido`, `articulo_id`). Así no se mezclan los datos crudos con las publicaciones.
3. **Extracción** a los campos de `tipos.py` (cargo, fechas, sueldo, enlaces) con reglas y expresiones regulares; opcionalmente **Ollama local** detrás de una interfaz intercambiable, siempre con la salida marcada «pendiente de verificación» y con el texto de origen al lado para comparar.
4. **Conversión a borrador:** reutilizar `buscar_o_crear_institucion`, `Enlace` y los modelos de detalle; estado `revision`, nunca `publicado`. La publicación pasa por `validar_publicacion` y la revisión humana (nuevo rol «revisor»).
5. **Ejecución gratuita:** comando `flask investigar` lanzado por el Programador de tareas de Windows o cron. No requiere servicios de pago ni colas externas al principio.
6. **Vigilancia de lo publicado:** comando que revisa enlaces (HEAD/GET), detecta cambios en la página de origen y genera alertas en el panel (ya existe el bloque de alertas).
7. **Trazabilidad:** cada publicación automatizada guarda su hallazgo de origen y quién la verificó (bitácora `Registro` ya disponible).
8. **Pruebas:** adaptadores probados con HTML guardado en `tests/fixtures/` (sin red), deduplicación y garantía de que nada se publica sin intervención humana.

Orden sugerido: modelos + 1 adaptador + bandeja de candidatos en el panel → deduplicación y vigilancia de enlaces → extracción asistida (reglas) → LLM local opcional.

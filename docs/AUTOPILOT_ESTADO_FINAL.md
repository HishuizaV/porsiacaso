# PorSiAcaso Autopilot — Estado final

Fecha: 13/10/2026. Commits locales sobre `09ac4fd`; **nada se envió a GitHub ni se desplegó**.

## Criterios de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| Se integra con el CMS real | ✅ | Las fichas son `Articulo` con sus tablas de detalle; mismas validaciones (`validar_publicacion`) |
| No destruye datos existentes | ✅ | Migración aditiva aplicada con respaldo `respaldos/porsiacaso_20261013_045008.db`; conteos iguales |
| Fuente configurable desde el panel | ✅ | Formulario con validación y «Probar lectura» |
| Detecta oportunidades reales de una fuente permitida | ✅ | Prueba real: 6 fichas vigentes de gob.pe (ENAP, PRONABEC) |
| Evita duplicaciones | ✅ | 6 capas + claves únicas; repetir jornada no crea nada |
| Extrae información estructurada | ✅ con límites | Ver «Limitaciones»: PDF escaneados no se leen |
| Crea un borrador de empleo realista sin código | ✅ | `test_flujo_fuente_a_borradores`; captura de la vista previa |
| Botones con URLs verificadas | ✅ | Cada enlace se comprueba; los rotos no se muestran |
| Muestra la evidencia | ✅ | Bandeja y página de hallazgo, dato por dato |
| Bloquea información insuficiente | ✅ | Lista de calidad; vencidas, antiguas y notas se descartan |
| Respeta permisos | ✅ | Editor / revisor / admin / servicio probados |
| Revisar, aprobar y programar | ✅ | Bandeja |
| Lotes con límite de tiempo, guarda progreso, se recupera | ✅ | Pruebas del motor |
| Corre desde Windows sin Claude Code | ✅ | `autopilot_jornada.bat` probado; `autopilot_programar.ps1` listo (no ejecutado) |
| Sin APIs de pago | ✅ | Solo bibliotecas libres; Ollama local opcional |
| No compromete el SEO existente | ✅ | 157 pruebas en verde, incluidas las de SEO; programadas fuera del sitemap |
| Controles editoriales compatibles con Google | ✅ (no garantiza aprobación) | Sin contenido inventado, sin páginas casi idénticas, revisión humana por defecto |
| Pruebas automatizadas | ✅ | 157 pasan |
| Manual para no programadores | ✅ | `AUTOPILOT_MANUAL.md` |

## Qué se construyó

- `autopilot/` (13 módulos): red segura, adaptadores, extracción con evidencia, clasificador, deduplicación,
  verificador, redactor/SEO, editor de calidad y política A/B/C, publicador con versiones, IA opcional,
  motor de jornada, sincronización firmada, medición de IA, CLI y fuentes iniciales.
- Panel: Autopilot, Bandeja, Fuentes, Hallazgos, Actualizaciones, Historial.
- Permisos: rol revisor, cuenta de servicio, instituciones solo para administradores, editores a revisión.
- Seguridad de la auditoría: límites persistentes (buscador, login, asistente), Quill local con SRI.
- Migración `732c8c030a5e` (aditiva). Aplicada a la base real. 7 fuentes registradas **en pausa**.

## Producción por jornada: lo que se puede afirmar

La meta de 10–15 fichas **depende de las fuentes autorizadas**, no del software. Con las fuentes verificadas
hoy, una jornada produjo **6 fichas vigentes en 3,5 minutos**; el resto eran documentos vencidos o
administrativos y se descartaron (correcto). Llegar a 10–15 diarias requiere **más fuentes autorizadas con
convocatorias vigentes** (por ejemplo, la colección CAS 2026 de cada municipalidad cuando exista) y
procesar manualmente SERVIR/Talento Perú, que no se automatiza.

## Limitaciones verificadas

1. **PDF escaneados**: las bases de la Municipalidad de Chiclayo son imágenes; sin OCR no se lee la fecha
   límite y la ficha va a revisión con aviso.
2. **SERVIR/Talento Perú** tiene protección antibots: consulta manual.
3. Extracción por reglas en español: pueden leerse mal fechas (caso real: «31/12/2027», marcada como dudosa).
4. Publicar con la laptop apagada exige un **servidor** con `AUTOPILOT_TOKEN`; no hay despliegue, así que
   **no está verificado en producción**.
5. La IA local medida en 6 casos (muestra pequeña); permanece desactivada por defecto.
6. DNS rebinding mitigado pero no eliminado; límites con ventana fija.

## Mejoras futuras priorizadas

1. OCR libre (Tesseract) para bases escaneadas, solo como dato «derivado» con revisión.
2. Alojar el sitio y probar la sincronización real; luego programar la jornada diaria.
3. Agregar fuentes de municipalidades y universidades de Lambayeque con convocatorias vigentes.
4. Detección de la colección anual nueva (CAS 2026) en gob.pe.
5. Content-Security-Policy y fijar la IP resuelta al conectar (contra DNS rebinding).
6. Ampliar la medición de IA a 50+ casos reales antes de considerar usarla por defecto.

## Cómo continuar tras una interrupción

1. `.\venv\Scripts\Activate.ps1` y `python -m pytest -q` (debe dar 157 pasadas).
2. `git log --oneline` para ver las etapas.
3. `flask autopilot estado` muestra la última jornada; la cola pendiente se retoma sola en la siguiente.

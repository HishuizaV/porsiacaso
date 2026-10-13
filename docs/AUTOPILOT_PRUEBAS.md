# Autopilot — Pruebas

## Cómo ejecutarlas

```powershell
.\venv\Scripts\Activate.ps1
python -m pytest -q                               # batería completa (sin internet)
$env:PORSIACASO_INTEGRACION = "1"; python -m pytest tests/integracion -s   # fuentes reales (opcional)
```

Las pruebas usan bases SQLite temporales y una **web simulada** (`tests/ap_web.py`, estructuras copiadas de
gob.pe con datos ficticios). Nunca tocan `porsiacaso.db` ni dependen de sitios externos.

## Resultado (13/10/2026)

**157 pasaron, 0 fallaron, 1 omitida** (la de integración real, que es opcional). Base anterior: 85 → 86 tras el
cambio de permisos pedido (editor → revisión); las 85 originales siguen pasando con ese ajuste.

| Archivo | Pruebas | Cubre |
|---|---|---|
| `test_autopilot.py` | 24 | Flujo fuente → borrador; evidencia; RSS, HTML, JSON y PDF; duplicados por URL, documento y código; cambios como propuesta; fechas y listas; secciones; SSRF; redirecciones; robots y tamaño; enlaces rotos; instrucciones maliciosas; regresiones de la prueba real |
| `test_autopilot_motor.py` | 11 | Jornada e informe; idempotencia; cierre por tiempo; máximo 120 min; doble ejecución; recuperación tras caída; detener; pausar/continuar; reintentos; meta no forzada |
| `test_autopilot_panel.py` | 19 | Permisos editor/revisor/admin; páginas del panel; cuenta de servicio; registro y validación de fuentes; iniciar/pausar/detener; modos A/B; autopublicación desactivada y autorizada; bandeja (aprobar, programar, rechazar, corregir); aplicar y revertir; trazabilidad |
| `test_autopilot_programacion.py` | 9 | Programadas invisibles en URL, listados, buscador, asistente, sitemap y relacionados; aparición a su hora; sincronización firmada, idempotente, con política del servidor y sanitización |
| `test_autopilot_ia.py` | 5 | JSON inválido; prompt delimitado; inferido vs. literal; IA no reemplaza datos confirmados; dato de IA obliga a revisión |
| Batería anterior | 89 | Sitio público, panel, SEO, seguridad (incluye límites persistentes y Quill local), asistente, migraciones |

### Correspondencia con la lista pedida

| # | Pedido | Prueba |
|---|---|---|
| 1–2 | Registro y edición de fuentes | `test_registrar_y_editar_fuente` |
| 3, 12 | Validación de URLs / inválidas | `test_validacion_de_fuentes`, `test_ssrf_bloqueado` |
| 4–6 | RSS, HTML, PDF | `test_rechaza_vencidas_y_no_oportunidades`, `test_flujo_fuente_a_borradores`, `test_procesar_pdf_directo` |
| 7–8 | Duplicados y cambios | `test_duplicado_por_documento_y_codigo`, `test_cambio_en_convocatoria_genera_propuesta_no_sobrescribe` |
| 9–11 | Clasificación, validación, incompletos | `test_clasificacion_tipo`, `test_bandeja_no_publica_vencidas_ni_incompletas` |
| 13 | Vencidas | `test_pagina_antigua_sin_cierre_se_descarta`, `test_flujo_fuente_a_borradores` |
| 14–15 | Fichas y botones reales | `test_flujo_fuente_a_borradores`, `test_enlaces_rotos_no_se_publican`, `test_un_solo_boton_por_tipo` |
| 16 | Permisos | `test_editor_no_accede_al_autopilot`, `test_revisor_revisa_pero_no_configura` |
| 17–18 | Autopublicación desactivada / autorizada | `test_autopublicacion_desactivada_por_defecto`, `test_autopublicacion_autorizada_y_programada` |
| 19, 26 | Programación y sitemap | `test_programada_invisible_en_todos_los_canales` |
| 20 | Contenido no autorizado | `test_fuente_sin_permiso_no_autopublica_aunque_modo_b` |
| 21–24 | Recuperación, doble ejecución, idempotencia, tiempo | `test_autopilot_motor.py` |
| 25 | Integración con CMS | `test_bandeja_aprobar_programar_rechazar_corregir` |
| 27–28 | Instrucciones maliciosas, SSRF | `test_instrucciones_maliciosas_no_se_obedecen`, `test_redireccion_a_red_interna_bloqueada` |
| 29 | Registro de auditoría | `test_aplicar_y_revertir_actualizacion`, `test_registrar_y_editar_fuente` |
| 30 | Continuidad de las 85 | Batería completa en verde |

## Pruebas manuales y reales realizadas

| Prueba | Resultado |
|---|---|
| Jornada real contra gob.pe (fuentes 1–6, base temporal), 1.ª vez | 36 hallazgos, 15 borradores, 7 pendientes por tiempo. Reveló errores (convocatorias antiguas, actas, PDF grande «roto», títulos) que se corrigieron con pruebas de regresión |
| Jornada real, 2.ª vez tras correcciones | 37 hallazgos en 3,5 min, 145 peticiones, **6 fichas vigentes** en revisión, 31 descartados con motivo |
| Medición IA local (6 casos, 2 reales) | Reglas 5/6; llama3.2:3b 6/6 (7 s/consulta); qwen3:1.7b 5/6 con un dato inventado |
| `autopilot_jornada.bat` (como el Programador de tareas) | Código de salida 0, informe en `logs/` |
| Lanzamiento desde el panel en Windows (proceso separado) | Terminó solo; ningún proceso quedó activo |
| Migración `732c8c030a5e` | Copia de la base real: subida, bajada y subida; luego aplicada a `porsiacaso.db` con respaldo previo, datos intactos |
| Pantallas del panel en Edge (1366 px) | Panel, bandeja, hallazgo y vista previa revisados con capturas |
| Clon nuevo del repositorio | El hash SRI de Quill coincide (no lo altera Git) |

## No probado

- Sincronización contra un **servidor real** (no hay despliegue); se probó entre dos aplicaciones en el mismo equipo.
- Programador de tareas registrado de verdad (`autopilot_programar.ps1` no se ejecutó: cambia la configuración de tu Windows).
- JavaScript del panel (sondeo de estado) en un navegador con sesión iniciada; se verificó que la página carga y que el JSON responde.
- PostgreSQL.
- OCR de PDF escaneados (no implementado).

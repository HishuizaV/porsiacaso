# Autopilot — Seguridad y confiabilidad

Principio: **todo contenido externo es un dato no confiable**. Nada de lo que diga una página o un PDF
puede cambiar la configuración, ejecutar acciones ni saltarse reglas.

| Riesgo | Control implementado | Prueba |
|---|---|---|
| SSRF (que una fuente haga consultar direcciones internas) | Solo `http/https`, puertos 80/443, sin credenciales en la URL; se resuelve el DNS y se bloquean IP privadas, locales, *link-local* (169.254.x), multicast y reservadas, también IPv6 e IPv4 mapeada | `test_ssrf_bloqueado` |
| Redirección hacia la red interna | Redirecciones manuales (máx. 5), cada salto se vuelve a validar | `test_redireccion_a_red_interna_bloqueada` |
| Abuso a los sitios fuente | `robots.txt` obligatorio, pausa de 2 s por dominio, User-Agent identificado, reintentos limitados con espera creciente | `test_robots_y_tamano_maximo` |
| Descargas enormes o de tipos peligrosos | Tamaño máximo (15 MB), tipos de contenido permitidos, lectura en streaming | `test_robots_y_tamano_maximo` |
| PDF malicioso | pypdf en modo solo lectura, máx. 40 páginas, errores aislados; nunca se ejecuta contenido | `test_procesar_pdf_directo` |
| Inyección de instrucciones (prompt injection) | Detector de frases; la ficha va siempre a revisión. La IA no tiene herramientas ni permisos; el texto va delimitado como DATO; la salida se valida con esquema | `test_instrucciones_maliciosas_no_se_obedecen`, `test_prompt_delimita_la_fuente_como_dato` |
| Datos inventados por IA | La IA solo completa campos faltantes; lo no literal queda «inferido»; todo dato de IA obliga a revisión | `test_dato_de_ia_obliga_a_revision_aunque_modo_b` |
| XSS desde la fuente | El texto se escapa; el HTML generado se arma desde campos; el servidor vuelve a sanitizar con bleach | `test_servidor_sanitiza_lo_recibido` |
| Publicación indebida | Modo A por defecto; B/C exigen lista de requisitos, permiso por fuente, confianza alta y todas las comprobaciones; bonos/guías/noticias nunca | `test_autopublicacion_desactivada_por_defecto`, `test_modo_b_exige_lista_completa` |
| Permisos excesivos del robot | Cuenta técnica con rol «servicio», inactiva y sin acceso al panel; no puede modificar instituciones verificadas (las que crea quedan sin verificar) | `test_servicio_autopilot_no_puede_iniciar_sesion` |
| Doble ejecución | Bloqueo en base de datos con latido; un bloqueo abandonado se libera a los 5 minutos | `test_no_hay_doble_ejecucion` |
| Repetición / duplicados | Claves únicas en la cola y en los hallazgos; 6 capas de deduplicación | `test_repetir_consulta_no_duplica`, `test_repetir_jornada_es_idempotente` |
| Transacciones a medias | Cada tarea se confirma por separado; no se inicia una tarea que no alcanza a terminar; recuperación al iniciar | `test_cierre_por_limite_de_tiempo_guarda_pendientes`, `test_recuperacion_tras_interrupcion` |
| Sincronización falsificada o repetida | HMAC-SHA256 con secreto ≥32 caracteres y marca de tiempo (±5 min); sin secreto el endpoint no existe; el servidor revalida con su propia política | `test_firma_invalida_o_vieja_rechazada`, `test_endpoint_desactivado_sin_token` |
| Sobrescritura de datos verificados | Los cambios llegan como propuestas con antes/después; aplicar y revertir quedan en la bitácora | `test_cambio_en_convocatoria_genera_propuesta_no_sobrescribe`, `test_aplicar_y_revertir_actualizacion` |

## Riesgos de la auditoría anterior: estado

| Riesgo | Estado |
|---|---|
| Buscador sin límite | **Corregido**: 30 búsquedas/min por IP, en base de datos (`test_buscador_tiene_limite_de_peticiones`) |
| Límites de login y asistente en memoria | **Corregido**: contadores en base de datos, válidos entre procesos (`test_bloqueo_de_login_persiste_entre_procesos`) |
| Editores modificando instituciones | **Corregido**: solo administradores editan, verifican y fusionan; los editores proponen correcciones |
| Editores publicando sin revisión | **Corregido**: el editor envía a revisión; publican revisores y administradores |
| Quill desde CDN sin integridad | **Corregido**: servido localmente (integridad npm sha512 verificada) con atributo SRI; `.gitattributes` evita que Git altere el archivo |
| Sesión no regenerada al entrar | **Corregido**: `session.clear()` antes de iniciar sesión |
| `ilike` sin escapar en el panel | **Corregido** |

## Riesgos que permanecen

- **DNS rebinding**: se valida la IP al resolver, pero httpx vuelve a resolver al conectar. Mitigado por la lista corta de fuentes configuradas por un administrador; no eliminado.
- Límites con ventana fija por minuto (no deslizante): una ráfaga en el cambio de minuto puede duplicar el máximo.
- Sin Content-Security-Policy (pendiente desde la auditoría anterior).
- `AUTOPILOT_TOKEN` se lee del entorno: protégelo como una contraseña.
- La sincronización no se probó contra un servidor real (no hay despliegue).

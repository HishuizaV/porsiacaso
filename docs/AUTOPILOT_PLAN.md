# PorSiAcaso Autopilot — Plan por etapas

Línea base (13/10/2026): árbol limpio en `09ac4fd`, **85/85 pruebas** en verde.

| Etapa | Entregable verificable | Prueba |
|---|---|---|
| A | Auditoría, fuentes reales investigadas, arquitectura y plan | Este documento + `AUTOPILOT_FUENTES.md` |
| B | Modelos y migración aditiva; roles (revisor, servicio); permisos de instituciones; registro de autoría | Migración sobre copia de la base real; pruebas de permisos |
| C | Flujo fuente → hallazgo → extracción → verificación → borrador especializado | Prueba de extremo a extremo con fixtures locales |
| D | Bandeja de revisión integrada al CMS; aprobar, rechazar, corregir, programar | Pruebas de panel |
| E | Jornada por lotes: bloqueo, cola persistente, presupuesto, pausa/detener, recuperación, informe | Pruebas de motor (tiempo simulado, interrupción, doble ejecución) |
| F | Visibilidad de programadas en todos los canales + sincronización con servidor | Pruebas de sitemap, buscador, asistente, URL directa; sincronización entre dos apps de prueba |
| G | Ollama opcional con medición de valor | Medición real con los modelos instalados |
| H | Modos A/B/C de autopublicación (A por defecto) | Pruebas de política |
| I | Riesgos de la auditoría: límite en buscador, límites persistentes, Quill local, permisos | Pruebas de seguridad; regresión completa; navegador |

Prioridad cuando falte tiempo: B → C → E → D → H → F → I → G.

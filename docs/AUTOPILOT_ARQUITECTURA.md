# PorSiAcaso Autopilot — Arquitectura

## Principio

El trabajo diario lo hace un **proceso Python independiente del servidor web** (`flask autopilot jornada`), que se ejecuta por lotes con un límite de tiempo. Lo puede iniciar el Programador de tareas de Windows o el botón del panel. No necesita Claude Code ni servicios de pago. El servidor web solo lee y escribe en la base de datos y muestra el estado.

```
             Programador de tareas de Windows / botón del panel
                                   │
                          flask autopilot jornada   (proceso propio, máx. 120 min)
                                   │
 ┌────────── Motor (autopilot/motor.py): bloqueo único, cola persistente, presupuesto ──────────┐
 │  1 Investigador   → adaptadores RSS / HTML / JSON / PDF por fuente (red.py segura)          │
 │  2 Clasificador   → tipo, región, institución, relevancia, prioridad, inyección             │
 │  3 Extractor      → campos por tipo + evidencia (fragmento, origen, estado del dato)         │
 │  4 Verificador    → enlaces, fechas, contradicciones; la IA nunca cuenta como prueba        │
 │  5 Redactor       → plantillas por tipo, solo con datos respaldados                          │
 │  6 SEO            → título, descripción, slug, enlaces internos sugeridos                   │
 │  7 Editor calidad → lista de comprobación; decide rechazo / revisión / autopublicable       │
 │  8 Publicador     → CMS existente (mismas validaciones); revisión, programado o publicado   │
 └──────────────────────────────────────────────────────────────────────────────────────────────┘
                                   │  SQLite (modo WAL) o PostgreSQL
                     Panel /admin/autopilot (Flask): control, bandeja, informes
```

## Por qué este diseño y no otros

| Alternativa | Motivo para no usarla como base |
|---|---|
| APScheduler dentro de Flask | Exige un proceso encendido todo el día y mezcla tareas pesadas con las visitas. El Programador de tareas de Windows lanza la jornada y el proceso termina solo |
| n8n | Licencia «Sustainable Use» (no es de código abierto OSI); añade Node y otro servidor |
| CrewAI / LangChain | Ocho «agentes LLM» serían lentos e imprecisos en una laptop; aquí los agentes son funciones deterministas y la IA es opcional |
| Playwright | Ninguna fuente autorizada probada requiere JavaScript; añade navegadores pesados. Las fuentes que exigen navegador o tienen protección antibots (SERVIR/Talento Perú, Incapsula) se marcan como manuales y **no se eluden** |
| changedetection.io (Apache‑2.0) | Es una aplicación completa; se reutiliza la idea (huella de contenido + diferencias), no el código |
| trafilatura (Apache‑2.0) | Útil, pero arrastra lxml y otras dependencias; las páginas objetivo (gob.pe) tienen `<main>` claro y basta BeautifulSoup. Puede añadirse después |
| PyMuPDF | Licencia AGPL‑3.0. Se usa **pypdf** (BSD) |

Licencias verificadas en GitHub el 13/10/2026: changedetection.io Apache‑2.0, ollama MIT, apscheduler MIT, playwright‑python Apache‑2.0, trafilatura Apache‑2.0, httpx BSD‑3, PyMuPDF AGPL‑3.0, n8n no OSI. pypdf (BSD‑3) y feedparser (BSD‑2) verificadas en su archivo LICENSE.

## Componentes

| Archivo | Responsabilidad |
|---|---|
| `autopilot/modelos.py` | Fuente, Hallazgo, Evidencia, Ejecucion, Tarea, Bloqueo, DecisionEditorial, VersionArticulo, Verificacion, PropuestaInstitucion, LimiteContador |
| `autopilot/red.py` | Descarga segura: solo http/https, bloqueo de IP privadas/locales (SSRF), redirecciones validadas, robots.txt, pausa por dominio, tamaño máximo, reintentos con espera creciente |
| `autopilot/adaptadores.py` | RSS/Atom (feedparser), HTML con selector o patrón configurable, JSON, PDF directo |
| `autopilot/extraccion.py` | Texto de HTML (`<main>`) y PDF (pypdf); extractores por tipo con evidencia |
| `autopilot/clasificador.py` | Tipo, región, relevancia, detección de instrucciones maliciosas |
| `autopilot/dedup.py` | URL normalizada, ID externo, código de convocatoria, huella de texto y de documento, similitud por *shingles* |
| `autopilot/verificador.py` | Verificación de enlaces y fechas, contradicciones |
| `autopilot/redactor.py` | Plantillas por tipo y metadatos SEO |
| `autopilot/calidad.py` | Lista editorial y política de autopublicación (modos A/B/C) |
| `autopilot/publicador.py` | Creación de borradores, propuestas de actualización, versiones y reversión |
| `autopilot/ia.py` | Cliente Ollama opcional, con JSON obligatorio y validación; sin Ollama se usan reglas |
| `autopilot/motor.py` | Jornada: bloqueo, cola, presupuesto por etapa, pausa/detener, recuperación, informe |
| `autopilot/sincronizar.py` | Envío firmado (HMAC) de publicaciones preparadas al servidor público |
| `admin_autopilot.py` + `templates/admin/autopilot/*` | Panel, fuentes, bandeja, hallazgos, historial, informes |

## Datos y trazabilidad

Cada dato extraído guarda: valor, **estado** (`confirmado`, `derivado`, `inferido`, `no_encontrado`, `contradictorio`), fragmento de origen, URL o página del PDF y método. Solo `confirmado` y `derivado` cuentan para publicar; `inferido` (IA) siempre obliga a revisión humana.

## Fechas

El sistema existente guarda la **hora de Lima sin zona** (UTC‑5 fijo; Perú no usa horario de verano desde 1994). Convertir todo a UTC obligaría a reescribir todas las fechas existentes sin beneficio funcional: con un desfase fijo la conversión es exacta y no hay horas ambiguas. Decisión: se mantiene la hora de Lima en la base y todo intercambio externo (sincronización, JSON-LD) usa ISO 8601 con desfase explícito `-05:00`. `models.ahora()` es la única fuente de hora.

## Publicación programada con la laptop apagada

La visibilidad se decide **en cada consulta** (`fecha_publicacion <= ahora()`), no con un proceso que «active» publicaciones. Por eso el servidor muestra lo programado a su hora sin depender de la laptop ni de la IA. La jornada local prepara las publicaciones y las envía al servidor (`flask autopilot sincronizar`). Mientras el sitio no esté alojado, esto solo funciona en local (ver `AUTOPILOT_ESTADO_FINAL.md`).

## Concurrencia

SQLite en modo WAL con `busy_timeout`: el servidor web lee mientras el ejecutor escribe. El ejecutor guarda cada tarea en su propia transacción. Un registro de `Bloqueo` con latido impide dos jornadas a la vez.

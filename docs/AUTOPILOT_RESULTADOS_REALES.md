# Autopilot — Resultados reales (13/10/2026)

Primera operación con información **real** sobre la base real (`porsiacaso.db`), modo A (sin autopublicación),
IA desactivada. Respaldos verificados antes de cada cambio en `respaldos/`.

## Acceso y condiciones de cada fuente

Todas respondieron HTTP 200 al descargador del Autopilot y su `robots.txt` permite la lectura automatizada.
No se eludió ninguna protección ni se usó sesión alguna.

| # | Fuente pedida | Cómo se lee | Estado |
|---|---|---|---|
| 4 | ENAP – campañas | Listado HTML de gob.pe (fuente ya existente; no se duplicó) | Activa |
| 8 | PRONABEC – campañas | Listado HTML de gob.pe | Activa |
| 9 | Ministerio de Cultura – CAS vigente | La página es una aplicación JavaScript; se lee el **listado JSON público** que esa misma página consulta (`plataformamincu…/LISTADO_PUBLICACION?NTC=1&NOPT=1`). Adaptador JSON con plantillas (nuevo) | Activa — **0 vigentes hoy** (22 en evaluación, 1733 finalizadas) |
| 10 | AGRO RURAL – CAS 2026 | Página con un bloque por proceso: **adaptador «procesos» (nuevo)**; omite procesos con resultados y sigue un salto a «Bases» y «Cronograma» para leer sus PDF | Activa |
| 11 | GRTPE Lambayeque – campañas | Listado HTML con palabras clave y exclusiones | Activa |
| 12 | GRE Lambayeque – Convocatoria CAS | **Página única (nuevo)** | Activa |
| 13 | GERESA Lambayeque – CAS 001-2026 | **Página única (nuevo)** | Activa |
| 14 | MTPE – Eventos Empleos Perú | La página describe el servicio; los eventos están en una aplicación JavaScript sin fuente de datos pública identificable | **Manual** |
| 15 | ProInnóvate – campañas | Listado HTML (concursos de financiamiento → tipo «beneficio», siempre revisión) | Activa |
| 16 | Proyectos Cultura (UE 008) – CAS | La tabla se carga desde `controladores/cas.controlador.php` de la misma web: **adaptador «tabla» (nuevo)**; omite filas con evaluaciones | Activa |

## Resultado por fuente (después de las correcciones)

| # | Fuente | Elementos leídos | Fichas en revisión | Descartados | Por qué se descartaron (principal) |
|---|---|---|---|---|---|
| 4 | ENAP | 12 | 4 | 8 | Cursos con fecha vencida (p. ej. «hasta el 12 de julio»), páginas de RESULTADOS, fechas contradictorias, catálogo sin datos |
| 8 | PRONABEC | 28 | 1 | 27 | Convocatorias 2023–2025 cerradas, con listas de seleccionados/aptos publicadas |
| 9 | Ministerio de Cultura | 0 | 0 | 0 | Sin CAS vigentes en su listado |
| 10 | AGRO RURAL | 4 abiertos (de 23) | 2 | 2 | CAS 008: **comunicado de cancelación**; CAS 014: publicado en marzo, sin cierre visible |
| 11 | GRTPE | 1 | 0 | 1 | La página solo tiene el título (sin evidencia) |
| 12 | GRE | 1 | 0 | 1 | Ya publicó «cuadro preliminar» y resultados finales |
| 13 | GERESA | 1 | 0 | 1 | Ya publicó resultados preliminares y finales |
| 15 | ProInnóvate | 11 | 2 | 9 | Concursos vencidos (enero–abril 2026), resultados publicados, páginas sin fecha ni datos |
| 16 | Proyectos Cultura | 2 abiertos (de 6) | 2 | 0 | — |
| | **Total** | **60** | **11** | **49** | |

Cuatro jornadas reales: 6,7 + 2,4 + 2,1 + 0,1 minutos. Sin errores de red al final. Sin duplicados.

## Las 11 fichas en la bandeja

**Con fecha de cierre confirmada y botones oficiales (6):**

| Ficha | Cierre | Evidencia |
|---|---|---|
| AGRO RURAL – Capitán (CAS 023-2026) | 21/10/2026 | Cronograma y bases PDF |
| AGRO RURAL – Especialista Administrativo II, Apurímac (CAS 024-2026) | 21/10/2026 | Cronograma y bases PDF |
| ENAP – Taller remoto IA para la Dirección Pública (G11), gratuito | 19/10/2026 | Página oficial + inscripción facilita.gob.pe |
| ENAP – Taller Reglamento de la Ley de Transparencia (G5), gratuito | 31/10/2026 | Página oficial + inscripción |
| ENAP – Curso MOOC Gestión pública para la inclusión, gratuito | 01/11/2026 | Página oficial |
| ENAP – Taller remoto IA Aplicaciones básicas (G10), gratuito | **13/10/2026 (cierra hoy)** | Página oficial + inscripción |

**Reales pero requieren tu confirmación (5):**

| Ficha | Qué falta confirmar |
|---|---|
| Proyectos Cultura – Responsable de Asesoría Legal (S/ 13,864.19) | El perfil no muestra fecha de cierre; la tabla oficial la muestra sin evaluaciones |
| Proyectos Cultura – Asistente Técnico (S/ 4,064.19) | Igual que la anterior |
| PRONABEC – Beca Generación del Bicentenario 2026 | La fecha encontrada (31/12/2027) se descartó por dudosa; confirmar cierre y público objetivo |
| ProInnóvate – Concurso Implementa tu iniciativa circular | Sin fecha de cierre ni público en la página; revisar las bases |
| ProInnóvate – Evaluadores para concursos | Es una convocatoria de evaluadores (no un beneficio): decidir si corresponde publicarla |

**Meta 10–15:** se generaron 11 fichas reales; solo 6 tienen todo verificado. No se completó la meta con
contenido dudoso: las fuentes pedidas tienen hoy pocas convocatorias realmente abiertas.

## Errores encontrados en la operación real y corregidos (con pruebas)

1. Enlaces «postular» que apuntaban a listas de resultados → los documentos de resultados nunca son botones.
2. Convocatorias de años anteriores sin línea de fecha → regla por año en el título.
3. Resultados, seleccionados, aptos, becarios, cancelación, suspensión → la postulación terminó.
4. PDF compartido entre becas distintas tomado como duplicado → exige título equivalente.
5. Dos procesos con la misma plantilla tomados como duplicados → procesos distintos de una fuente nunca se fusionan.
6. «Hasta el 31 de diciembre… o hasta el retorno del titular» tomado como cierre → se ignora la duración del contrato.
7. Fecha a más de un año → no se usa como cierre.
8. Región adivinada en páginas nacionales → si se mencionan varias regiones, no se asigna.
9. Servidor que responde 404 a HEAD y 200 a GET → se confirma con GET.
10. Montos «13.864.19» → lector de montos con separadores mixtos.
11. Botón principal de cursos («inscripción») y beneficios («consulta») → ahora se asigna.
12. Página oficial de beneficios rechazada por su tipo de botón → corregido.
13. Oportunidad sin fecha y con información mínima → se descarta por falta de evidencia.

Nueva herramienta: `flask autopilot reevaluar` rehace con las reglas actuales las fichas del Autopilot que
ninguna persona tocó, y retira las que ya no pasan (retiró 13 en total: 9 becas antiguas y 4 páginas sin evidencia).

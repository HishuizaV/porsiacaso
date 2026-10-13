# Plan de implementación — PorSiAcaso

Cada bloque termina con pruebas automáticas y un commit local. El estado real de cada bloque se registra en `docs/ESTADO_PROYECTO.md`.

## Decisión de arquitectura de contenido

**`Articulo` se mantiene como entidad editorial general** (título, slug, resumen, contenido, imagen, categoría, zona, autor, estado, fechas, fuente) y se añade:

- `Articulo.tipo`: `noticia`, `guia`, `empleo`, `convocatoria`, `beca`, `educativa`, `curso`, `bono`, `tramite`, `otro`.
- Pocos campos comunes a casi todas las oportunidades: institución, fecha límite, vigencia, fecha de verificación, nombre de la fuente, aviso destacado, notas internas.
- **Tablas de detalle 1 a 1** por dominio: `DetalleEmpleo` (empleo y convocatoria), `DetalleBeca` (beca y convocatoria educativa), `DetalleCurso`, `DetalleBeneficio` (bonos), `DetalleTramite`.
- `Enlace`: botones tipados (postular, convocatoria, bases, anexo, inscripción, consulta, oficial, otro) con URL externa o PDF subido.
- `Institucion`: empresas y entidades reutilizables (sector, web, logo).
- `Ajuste`: configuración clave‑valor editable (publicidad, chatbot, datos de contacto, verificación).

Motivo: conserva IDs, slugs y relaciones; evita una tabla universal con decenas de columnas vacías; cada tipo nuevo se agrega con una tabla de detalle y una entrada en el registro `tipos.py`.

Estados editoriales: `borrador`, `revision` (pendiente de verificar), `publicado`, `archivado`. Vigencia de oportunidades (independiente): `abierta`, `cerrada`, `por_confirmar`; "vencida" se calcula a partir de la fecha límite (nunca se guarda a mano). La **programación** se implementa guardando `fecha_publicacion` futura: las consultas públicas filtran `fecha_publicacion <= ahora`, por lo que no depende de tareas programadas.

URLs: cada tipo tiene su sección (`/empleos`, `/becas`, `/cursos`, `/bonos`, `/tramites`, `/guias`, `/convocatorias`, `/educacion-convocatorias`, `/noticias`) y su ficha `/<sección>/<slug>`. `/articulo/<slug>` sigue funcionando para noticias y redirige con **301** al resto.

## P0 — Imprescindible
| # | Entregable | Verificación |
|---|---|---|
| 0.1 | Respaldo verificable + auditoría | `respaldos/…db` con integridad ok |
| 0.2 | App factory, configuración segura, CSRF global, requirements UTF‑8 | pytest: arranque, CSRF |
| 0.3 | Modelos y migración **aditiva** (sin borrar columnas ni filas) | migración sobre copia de la BD real conserva conteos |
| 0.4 | CMS por tipos: selector "+ Nueva publicación", formularios especializados, enlaces/botones, institución en línea, PDFs | pytest: crear/editar empleo sin HTML |
| 0.5 | Ficha pública de empleo + JobPosting estricto + vencidas | pytest: JSON‑LD presente/ausente según reglas |
| 0.6 | `/empleos` con filtros, orden y paginación | pytest filtros |
| 0.7 | Sanitización, validación de URL, subidas, permisos | pytest seguridad |

## P1 — Alta prioridad
| # | Entregable |
|---|---|
| 1.1 | Fichas especializadas de beca, curso, bono, trámite (pasos visuales), guía |
| 1.2 | Rediseño visual público (mobile-first, identidad propia, accesible) |
| 1.3 | Panel: resumen con conteos reales, por vencer, alertas, filtros, duplicar, archivar |
| 1.4 | Páginas institucionales nuevas (creadas **ocultas** para revisión), creación de páginas desde el panel |
| 1.5 | Publicidad: off / maqueta (solo admins) / AdSense; `ads.txt` configurable |
| 1.6 | SEO: sitemap por tipo, WebSite/Organization, breadcrumbs, favicon, imágenes optimizadas |

## P2 — Mejoras
| # | Entregable |
|---|---|
| 2.1 | Asistente PorSiAcaso por reglas (sin IA de pago), con límite de consultas |
| 2.2 | Búsqueda sin tildes con relevancia |
| 2.3 | Checklist editorial antes de publicar (advertencias) |
| 2.4 | Documentación: README, `.env.example`, CHECKLIST_ADSENSE, despliegue |

## Fuera de alcance (documentado)
- Modelo independiente de "Fuentes" (se usa nombre + URL de fuente por publicación).
- Tablas dentro del editor Quill 1.x (no las soporta); se usan "Datos clave" estructurados.
- Integración Ollama (opcional futura).

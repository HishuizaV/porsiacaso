# Autopilot — Fuentes investigadas

Investigadas el **13/10/2026** consultando cada sitio y su `robots.txt`. Se registran en la base con
`flask autopilot cargar-fuentes` **en pausa y sin permiso de extracción**: tú decides activarlas en
*Panel → Autopilot → Fuentes* después de leer los términos de uso de cada sitio.

> Que una página sea pública no autoriza a copiarla. El Autopilot no copia textos: extrae datos
> (fechas, plazas, requisitos, enlaces) y redacta una ficha propia que enlaza a la fuente.

## Fuentes registradas

| # | Fuente | Método real de acceso | robots.txt | Resultado en la prueba real | Estado inicial |
|---|---|---|---|---|---|
| 1 | Municipalidad Provincial de Chiclayo — Convocatorias CAS 2025 (gob.pe) | HTML: colección de gob.pe con enlaces `informes-publicaciones/<id>` | Permite (solo bloquea `/admin/` y `?sheet=`) | 2 convocatorias de 2025, ya vencidas → descartadas por antigüedad. Sus bases son PDF **escaneados** (sin texto) | Pausada |
| 2 | MPCH — Convocatorias D. Leg. 728 (gob.pe) | HTML (gob.pe) | Permite | 4 convocatorias de 2023–2025 → descartadas por antigüedad | Pausada |
| 3 | Gobierno Regional de Lambayeque — publicaciones (gob.pe) | HTML (gob.pe) con filtro «convocatoria» | Permite | La lista mezcla actas, circulares y convenios de Obras por Impuestos: todos descartados correctamente | Pausada |
| 4 | ENAP (SERVIR) — cursos y convocatorias (gob.pe) | HTML (campañas de gob.pe) | Permite | 5 cursos/talleres gratuitos vigentes → fichas en revisión; resultados y cursos cerrados descartados | Pausada |
| 5 | PRONABEC — noticias (gob.pe) | HTML (gob.pe) con filtro de palabras clave | Permite | 1 convocatoria 2026 → ficha en revisión (fecha de cierre dudosa, marcada); notas institucionales descartadas | Pausada |
| 6 | PRONABEC — RSS de pronabec.gob.pe | RSS real (WordPress `/feed/`) | Permite (bloquea `/wp-admin/`, `/inicio/*`) | Desactualizado: último elemento de marzo de 2025, solo testimonios | Pausada (prioridad baja) |
| 7 | SERVIR — Talento Perú | **Manual**: protegido por un sistema antibots (Incapsula) | Sin robots.txt | **No se automatiza ni se elude la protección** | Manual |

## Fuentes evaluadas y no automatizadas

| Sitio | Motivo |
|---|---|
| Universidad Nacional Pedro Ruiz Gallo (unprg.edu.pe) | Responde **403** a clientes automatizados |
| datosabiertos.gob.pe | No se encontró una API CKAN en la ruta estándar (`/api/3/action/...` devuelve 404). No se afirma que tenga API |
| gob.pe `…/noticias.rss` | Devuelve 400: gob.pe **no** ofrece RSS por institución en esa ruta |

Ninguna fuente de esta lista ofrece una **API documentada** comprobada; el adaptador JSON existe y está probado,
listo para cuando haya una.

## Cómo agregar una fuente (sin programar)

1. *Panel → Autopilot → Fuentes → + Nueva fuente*.
2. Pega la URL del listado (página, RSS o API) y elige tipo, región e institución.
3. Escribe palabras clave (p. ej. `convocatoria, cas`) y, si hace falta, el patrón de enlace.
4. Pulsa **Probar lectura**: verás qué elementos encontraría, sin guardar nada.
5. Lee las condiciones del sitio. Solo entonces marca «permite extracción» y ponla **Activa**.
6. La autopublicación de una fuente es otro permiso aparte y solo funciona en modo B o C.

## Frecuencia y cortesía

Cada fuente tiene su frecuencia (24–72 h). El robot se identifica como `PorSiAcasoBot/1.0`, espera 2 segundos
entre peticiones al mismo sitio, respeta `robots.txt`, limita el tamaño de las descargas y reintenta como
máximo 2 veces con espera creciente. En la prueba real, 37 elementos necesitaron unas 145 peticiones en 3,5 minutos.

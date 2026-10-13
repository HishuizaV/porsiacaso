# PorSiAcaso — Guía general (lo esencial)

Portal peruano de oportunidades e información útil: empleos, convocatorias, becas, cursos, bonos, trámites,
guías y noticias, siempre con enlace a la fuente oficial. Incluye un panel para publicar sin saber programar
y el **Autopilot**, que investiga fuentes oficiales y prepara borradores para revisión.

Estado: funciona en **local** (http://127.0.0.1:5000). No está alojado en internet todavía.

---

## 1. Cómo arrancarlo (Windows)

```powershell
cd C:\Users\Holcen\Documents\Proyectos\PorSiAcaso
.\venv\Scripts\Activate.ps1
$env:FLASK_APP = "app.py"
flask run
```
- Sitio: http://127.0.0.1:5000 · Panel: http://127.0.0.1:5000/admin
- Pruebas: `python -m pytest -q` (172 pasan)

## 2. Qué hay en el sitio público

| Sección | Qué muestra |
|---|---|
| Inicio | Destacados, «cierran esta semana», oportunidades recientes, regiones, guías, noticias (solo si hay contenido) |
| `/empleos`, `/becas`, `/cursos`, `/bonos`, `/tramites`, `/guias`, `/noticias`… | Listados con filtros (región, institución, sector, modalidad, nivel, vigencia) y paginación |
| `/empleos/region/lambayeque` | Páginas por región |
| Ficha | Datos clave, requisitos, botones oficiales, fuente y fecha de verificación |
| Asistente (botón «¿Te ayudo a buscar?») | Busca en lo publicado, sin IA de pago, sin guardar conversaciones |

Las convocatorias **vencen solas**: al pasar la fecha límite se muestran como vencidas, sin botón de postular.

## 3. Roles

| Rol | Puede |
|---|---|
| Editor | Preparar publicaciones y enviarlas a revisión |
| Revisor | Revisar, corregir, aprobar y publicar |
| Administrador | Todo: fuentes, Autopilot, instituciones, usuarios, configuración |
| Servicio Autopilot | Cuenta técnica; no entra al panel |

## 4. Publicar a mano (noticias, guías y cualquier tipo)

Panel → **+ Nueva publicación** → elige el tipo → llena el formulario → Publicar (o Enviar a revisión si eres editor).
Los botones se crean pegando el enlace oficial; también puedes subir PDF. No se escribe HTML.

## 5. Autopilot (borradores automáticos)

1. **Iniciar jornada** (Panel → Autopilot) o automático cada día con `autopilot_programar.ps1`.
2. Lee las fuentes activas, descarta vencidas, cerradas, canceladas, duplicadas y sin evidencia.
3. Deja las fichas en **Autopilot → Bandeja de revisión** con la evidencia de cada dato.
4. Tú revisas: Vista previa → **Aprobar y publicar**, **Programar** o **Rechazar**.

- Jornada máxima: 120 min; se cierra sola. La meta (12–15) es una meta, no una garantía.
- Lo ya revisado no vuelve a aparecer. Cambios en la fuente llegan a **Actualizaciones** (aplicar / revertir).
- **Modo A** (actual): nada se publica solo. Bonos, guías y noticias nunca se publican solos.
- Noticias: el Autopilot no las redacta; se publican a mano.

Comandos útiles:
```powershell
flask autopilot jornada --minutos 60     # una jornada
flask autopilot estado                   # ver la última jornada
flask autopilot reevaluar                # rehacer borradores intactos con reglas nuevas
flask autopilot cargar-fuentes           # registrar el catálogo de fuentes (en pausa)
```

## 6. Fuentes

Activas: ENAP, PRONABEC (campañas), Ministerio de Cultura (CAS vigentes), AGRO RURAL, GRTPE, GRE y GERESA
Lambayeque, ProInnóvate, Ministerio de Cultura UE 008. Manuales: SERVIR/Talento Perú (protección antibots)
y MTPE Eventos Empleos Perú. Se agregan desde **Autopilot → Fuentes** (usa «Probar lectura» antes de activar).
Detalle y resultados: `AUTOPILOT_FUENTES.md` y `AUTOPILOT_RESULTADOS_REALES.md`.

## 7. Instituciones y empresas

Lista compartida de entidades (nombre, siglas, sector, web oficial, logo). Solo el administrador las edita,
verifica y une duplicadas; los editores proponen correcciones. «Sin verificar» es una marca interna: revisa y
pulsa **Verificar**.

## 8. Configuración del sitio (Panel → Configuración)

Correo de contacto, redes, código de Google Search Console, publicidad (desactivada / maqueta solo para
admins / AdSense con ID real), `ads.txt` y asistente. Páginas institucionales en **Páginas** (completa los
`[PENDIENTE]` antes de hacerlas visibles).

## 9. Respaldo y restauración

- Respaldar: `flask respaldo` → `respaldos\porsiacaso_FECHA.db` (verificado). Copia también `static\uploads\`.
- Restaurar: detener el sitio, copiar el respaldo sobre `porsiacaso.db`.
- Bases de datos, respaldos y registros **no** se suben a Git.

## 10. Seguridad (resumen)

CSRF en todos los formularios, contraseñas cifradas, bloqueo por intentos de login, límites de consultas
(buscador, asistente, login) guardados en la base, HTML saneado, validación de URLs, imágenes y PDF,
Autopilot con protección anti-SSRF y respeto de `robots.txt`, editor Quill servido localmente con integridad.

## 11. Estructura del código

| Archivo / carpeta | Función |
|---|---|
| `app.py` | Arranque, errores, comandos |
| `models.py`, `tipos.py` | Datos y tipos de publicación |
| `web.py` | Sitio público, sitemap, robots |
| `admin*.py` | Panel (contenido, sitio, Autopilot) |
| `autopilot/` | Motor: red segura, lectura de fuentes, extracción, verificación, redacción, calidad, publicación |
| `templates/`, `static/` | Diseño |
| `migrations/` | Cambios de base de datos (`flask db upgrade`) |
| `tests/` | Pruebas automáticas |

## 12. Pendiente / limitaciones

- No está en internet: falta hosting y dominio (necesarios para AdSense y para publicar con la laptop apagada).
- Bases en PDF escaneado: el Autopilot no lee su fecha (no hay OCR) → revisión manual.
- Si una entidad **cancela** algo ya publicado, hoy hay que retirarlo a mano.
- AdSense: el sitio está preparado, pero la aprobación depende de Google y de tener contenido real suficiente.

## 13. Más documentación

`AUTOPILOT_MANUAL.md` (uso diario) · `DESPLIEGUE.md` · `CHECKLIST_ADSENSE.md` · `AUTOPILOT_SEGURIDAD.md` ·
`AUTOPILOT_PRUEBAS.md` · `AUTOPILOT_ESTADO_FINAL.md` · `AUDITORIA_FINAL.md`

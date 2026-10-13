# Por Si Acaso

Portal peruano de oportunidades e información útil: empleos, convocatorias, becas, cursos, bonos, trámites, guías y noticias, siempre con su fuente oficial.

Hecho con Flask + SQLAlchemy + Jinja2. Funciona en local sin servicios de pago.

## Qué incluye

- **Panel para editores sin conocimientos técnicos**: botón «+ Nueva publicación», formularios por tipo (empleo, beca, curso, bono, trámite, guía, noticia…), botones oficiales automáticos, PDFs, preguntas frecuentes, vista previa, borradores, revisión, programación, duplicar y archivar.
- **Secciones públicas** con filtros (región, institución, sector, modalidad, nivel, vigencia), paginación y páginas por región.
- **Vencimiento automático**: al pasar la fecha límite la oportunidad se marca como vencida y se retira de los listados de vigentes.
- **SEO**: canonicals, sitemap, robots, Open Graph, breadcrumbs y datos estructurados solo cuando corresponden (JobPosting únicamente en vacantes reales, verificadas y vigentes).
- **Asistente PorSiAcaso**: ayuda a encontrar publicaciones por reglas, sin IA de pago y sin guardar conversaciones.
- **Publicidad preparada** (desactivada / maqueta solo para admins / AdSense) y `ads.txt` configurable.

## Instalación en Windows (PowerShell)

```powershell
cd C:\ruta\PorSiAcaso
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:FLASK_APP = "app.py"
flask db upgrade            # crea o actualiza las tablas (no borra datos)
flask iniciar               # categorías, regiones y páginas base (solo si están vacías)
flask completar-paginas     # agrega páginas institucionales nuevas como OCULTAS
flask crear-admin           # pide nombre, correo y contraseña
flask run                   # http://127.0.0.1:5000  ·  panel: /admin
```

Si PowerShell bloquea `Activate.ps1`: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

Variables de entorno: ver `.env.example`. En PowerShell se definen con `$env:NOMBRE = "valor"` (duran mientras la ventana esté abierta).

## Pruebas

```powershell
python -m pytest -q
```

Las pruebas crean bases de datos temporales: **nunca tocan `porsiacaso.db` ni `static/uploads`**.

## Respaldo y restauración

```powershell
flask respaldo        # copia verificada en respaldos\porsiacaso_AAAAMMDD_HHMMSS.db (nunca sobrescribe)
```

Restaurar (con la aplicación detenida):

```powershell
Copy-Item porsiacaso.db porsiacaso.antes_de_restaurar.db
Copy-Item respaldos\porsiacaso_AAAAMMDD_HHMMSS.db porsiacaso.db
```

Respalda también la carpeta `static\uploads\` (imágenes, logos y PDFs). Ni la base ni los respaldos se suben a Git (`.gitignore`).

## Migraciones

Después de cambiar `models.py`: `flask db migrate -m "descripcion"`, revisar el archivo generado y luego `flask db upgrade`. Haz siempre `flask respaldo` antes. `flask db check` confirma que modelos y migraciones coinciden.

## Estructura

| Archivo | Función |
|---|---|
| `app.py` | Creación de la app, errores, comandos CLI |
| `tipos.py` | Registro de tipos de publicación y sus campos (agregar un tipo = editar aquí) |
| `models.py` | Modelos y tablas de detalle |
| `web.py` | Rutas públicas, sitemap, robots, ads.txt |
| `admin.py`, `admin_contenido.py`, `admin_sitio.py` | Panel |
| `consultas.py` | Filtros y búsqueda sin tildes |
| `seo.py` | JSON-LD |
| `asistente.py` | Asistente por reglas |
| `ajustes.py` | Configuración editable desde el panel |
| `seguridad.py` | CSRF y límites de peticiones |

Más documentación en `docs/`: auditoría, plan, estado del proyecto, despliegue y checklist de AdSense.

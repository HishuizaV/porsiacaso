# Despliegue y puesta en marcha

> El sitio **solo funciona en local** hasta que alguien lo publique en un servidor. Nada aquí se ha desplegado.

## 1. Elegir alojamiento (decisión manual)

Condiciones consultadas el 13/10/2026; **verifícalas antes de decidir**, cambian a menudo.

| Opción | Lo bueno | Limitación importante |
|---|---|---|
| PythonAnywhere (gratis) | Flask nativo, SQLite persistente, sin tarjeta | Sin dominio propio en el plan gratuito (solo `usuario.pythonanywhere.com`), CPU diaria limitada. Dominio propio requiere plan de pago |
| Render (gratis) | Despliegue desde GitHub | Se apaga tras 15 min sin visitas; disco **efímero** (se pierden SQLite y subidas); Postgres gratis expira a los 30 días y luego se borra |
| VPS propio / plan de pago | Control total, dominio propio | Tiene costo |

Recomendación técnica: para probar públicamente sin costo, PythonAnywhere gratis (SQLite y `static/uploads` persisten). Para AdSense necesitarás **dominio propio** (Google no acepta subdominios gratuitos de hosting como sitio principal), lo que implica comprar un dominio y, en PythonAnywhere, un plan de pago. Esa decisión es tuya.

## 2. Variables obligatorias en producción

`SECRET_KEY` (aleatoria), `PRODUCCION=1`, `SITE_URL=https://tudominio.pe`. Opcionales: `DATABASE_URL`, `CONFIAR_PROXY=1` (si hay proxy delante). La app **se niega a arrancar** en producción sin `SECRET_KEY`.

WSGI: el objeto es `app` en `app.py` (`from app import app as application`).

## 3. Checklist previo a producción

- [ ] `python -m pytest -q` en verde.
- [ ] `flask respaldo` y copia de `static/uploads`.
- [ ] `flask db upgrade` en el servidor.
- [ ] `SECRET_KEY` propia, `PRODUCCION=1`, `SITE_URL` con https.
- [ ] HTTPS activo (PythonAnywhere y Render lo dan gratis; en VPS usa Let's Encrypt).
- [ ] Contraseña fuerte del administrador; borrar usuarios de prueba.
- [ ] Panel → Configuración: correo de contacto real.
- [ ] Panel → Páginas: completar los `[PENDIENTE]`, revisar privacidad y términos, hacer visibles descargo, publicidad y correcciones.
- [ ] Publicidad en **Desactivada** hasta que AdSense apruebe.
- [ ] Revisar que `/robots.txt` y `/sitemap.xml` muestren el dominio correcto.
- [ ] `FLASK_DEBUG` desactivado.

## 4. Dominio (manual)

Comprar el dominio (.pe en punto.pe o un registrador), apuntar el DNS (CNAME/A) según el proveedor y activar HTTPS. Actualizar `SITE_URL`.

## 5. Google Search Console (manual)

1. https://search.google.com/search-console → Agregar propiedad → «Prefijo de URL».
2. Método «Etiqueta HTML»: copiar solo el valor de `content` y pegarlo en Panel → Configuración → Search Console.
3. Verificar, luego enviar `https://tudominio.pe/sitemap.xml`.
4. Probar fichas de empleo en https://search.google.com/test/rich-results (JobPosting).

## 6. AdSense

Ver `docs/CHECKLIST_ADSENSE.md`.

## Qué se automatizó y qué es manual

| Automatizado | Manual |
|---|---|
| Migraciones, respaldos, sitemap, robots, canonicals, JSON-LD, vencimiento de convocatorias, ads.txt y etiquetas de verificación (desde el panel) | Contratar hosting y dominio, DNS, HTTPS en VPS, verificación en Search Console, solicitud y aprobación de AdSense, redactar contenido real y datos legales |

# Checklist para solicitar Google AdSense

Preparación ≠ aprobación. Google decide; esta lista reduce motivos comunes de rechazo. Políticas vigentes: https://support.google.com/adsense/answer/48182 (revísalas antes de solicitar).

## Técnico (ya implementado — verificar en el servidor)

- [x] Publicidad desactivada por defecto; modo maqueta visible solo para administradores (no carga código de Google ni genera impresiones).
- [x] AdSense solo se activa con un ID `ca-pub-` de 16 dígitos válido.
- [x] Etiqueta `google-adsense-account` automática al guardar el ID (sirve para verificar el sitio).
- [x] `/ads.txt` configurable desde el panel; vacío = no existe (no se inventan líneas).
- [x] Anuncios rotulados «Publicidad», separados de los botones de postulación (los botones están en el panel lateral; los anuncios, después del contenido).
- [x] Sin pop-ups, sin anuncios que tapen contenido, el asistente no se abre solo.
- [x] Sitemap, robots, canonicals, 404 reales, HTTPS (en el servidor), diseño adaptable a móvil.
- [ ] Comprobar en el servidor: `/ads.txt`, `/sitemap.xml`, velocidad móvil con PageSpeed Insights (medir, no estimar).

## Editorial (manual)

- [ ] Dominio propio con HTTPS.
- [ ] Contenido original y útil suficiente en varias secciones (no hay una cifra oficial; evita secciones con 1–2 publicaciones).
- [ ] Cada oportunidad con fuente oficial y fecha de verificación.
- [ ] Sin contenido copiado ni generado masivamente.
- [ ] Imágenes propias, con licencia o de uso libre, con crédito.
- [ ] Páginas visibles y completas: Sobre nosotros, Contacto (correo real), Privacidad, Términos, Política editorial, Descargo, Publicidad, Correcciones. Ninguna con `[PENDIENTE]` ni `tudominio`.
- [ ] Política de privacidad acorde a lo que realmente se usa (cookies de AdSense solo cuando esté activo) y a la Ley N.° 29733 de Protección de Datos Personales.
- [ ] Navegación funcional, sin enlaces rotos.

## Pasos de solicitud (manual)

1. Crear cuenta en https://adsense.google.com con datos reales del titular.
2. Añadir el sitio; copiar el ID `ca-pub-…`.
3. Panel → Configuración: pegar el ID (deja el modo en **Desactivada**: la etiqueta meta ya permite verificar) y pegar la línea de `ads.txt` que muestre AdSense.
4. Solicitar revisión y esperar el resultado de Google.
5. Solo tras la aprobación: crear bloques de anuncio, pegar sus ID en Configuración y cambiar el modo a **AdSense real**.
6. Nunca hacer clic en tus propios anuncios ni pedir clics.

## Fuera de alcance

Si en el futuro el sitio recibe tráfico del Espacio Económico Europeo o el Reino Unido, Google exige una plataforma de gestión de consentimiento (CMP) certificada; no está implementada porque el público objetivo es Perú.

# Manual del Autopilot (para personas sin conocimientos de programación)

## Qué hace

Cada jornada (máximo 2 horas) el Autopilot:

1. Revisa las fuentes oficiales que autorizaste.
2. Encuentra convocatorias, cursos y becas nuevas y descarta las repetidas.
3. Lee la página y las bases en PDF y saca los datos: puesto, plazas, requisitos, fecha límite, enlaces.
4. Comprueba que los enlaces funcionen y que la convocatoria no esté vencida.
5. Prepara una ficha con botones oficiales y te la deja en la **Bandeja de revisión**.
6. Al final escribe un informe y se cierra solo.

No inventa datos: si algo no está en la fuente, lo marca como faltante. La meta diaria (por ejemplo 12
fichas) es una meta, no una obligación: si solo hay 6 oportunidades reales, prepara 6.

## Primera vez (una sola vez)

1. Abre una ventana de PowerShell en la carpeta del proyecto y ejecuta:
   ```
   .\venv\Scripts\Activate.ps1
   $env:FLASK_APP = "app.py"
   flask db upgrade
   flask autopilot cargar-fuentes
   ```
2. Entra al panel (`/admin`) → **Autopilot → Fuentes**. Abre cada fuente, lee sus condiciones, pulsa
   **Probar lectura** y, si estás de acuerdo, marca «permite extracción» y ponla en **Activa**.

## Uso diario

### Opción 1: con un botón
*Panel → Autopilot → ▶ Iniciar jornada*. Elige duración (máx. 120 min) y meta. Puedes cerrar el navegador:
la jornada sigue en tu laptop y se apaga sola al terminar. Los botones **Pausar**, **Continuar** y
**Detener de forma segura** funcionan al terminar la tarea en curso (nunca dejan nada a medias).

### Opción 2: automática cada mañana
En PowerShell, una sola vez:
```
powershell -ExecutionPolicy Bypass -File .\autopilot_programar.ps1 -Hora 06:30
```
Windows ejecutará la jornada cada día a esa hora. Si la laptop estaba apagada, correrá al encenderla.
El registro queda en `logs\autopilot_programador.log`. Para quitarla:
`Unregister-ScheduledTask -TaskName "PorSiAcaso Autopilot" -Confirm:$false`

## Revisar y publicar (Bandeja de revisión)

Cada ficha muestra:
- **Evidencia**: cada dato con su estado: *confirmado* (está en la fuente), *derivado* (regla comprobable),
  *inferido* (lo propuso la IA, revísalo), *contradictorio* (la fuente dice cosas distintas).
- **Faltan datos** y **Por qué necesita revisión**.
- **Botones que verá el visitante**, con su dirección real.
- **Lista de calidad**: lo que se cumplió (✓) y lo que no.

Acciones: **Vista previa** (exactamente como la verá el público), **Corrección rápida** (título, resumen,
fecha límite), **Editar todo**, **✔ Aprobar y publicar**, **Programar** (elige fecha y hora) o **✖ Rechazar**.
Antes de aprobar, abre la fuente original y confirma la fecha límite: si las bases son un PDF escaneado,
el sistema te lo avisa porque no pudo leerlas.

## Cambios en convocatorias ya publicadas

Si la entidad modifica algo (fecha, sueldo, enlaces), el Autopilot **no** cambia tu ficha: lo deja en
*Autopilot → Actualizaciones* con el antes y el después. Pulsa **Aplicar cambio** o **Descartar**. Todo
cambio aplicado se puede **Revertir**. Las convocatorias vencidas se marcan como cerradas solas.

## Publicación automática (opcional)

| Modo | Qué hace |
|---|---|
| **A** (inicial) | Todo queda para tu revisión |
| **B** | Empleos, convocatorias y cursos que cumplan TODAS las reglas se publican solos (repartidos en el día, de 7:00 a 21:00) |
| **C** | Además, los tipos que autorices |

Para activar B o C debes marcar la lista de requisitos (pruebas, muestras revisadas, fuentes autorizadas,
botones y duplicados comprobados, política aceptada) y dar permiso de autopublicación a cada fuente.
Bonos, guías y noticias **nunca** se publican solos. Si un dato vino de la IA, o la fuente tiene texto
sospechoso, la ficha va a revisión aunque el modo lo permita.

## Publicar con la laptop apagada

Las fichas programadas aparecen solas a su hora **en el servidor donde está el sitio**. La jornada corre en
tu laptop; para que el servidor reciba lo preparado:

1. Define el mismo secreto en la laptop y en el servidor: `AUTOPILOT_TOKEN` (32 caracteres o más).
2. En la laptop define `AUTOPILOT_DESTINO=https://tu-sitio`.
3. `autopilot_jornada.bat` envía lo preparado al terminar. También: `flask autopilot sincronizar --destino https://tu-sitio`.

El servidor vuelve a validar todo: si su propio modo es A, lo recibido queda en su bandeja de revisión.
**Mientras el sitio no esté alojado en un servidor, esto solo funciona en tu laptop.**

## IA local (opcional)

Si tienes Ollama, puedes activarla en la configuración. Se usa solo para completar datos que las reglas no
encontraron, y lo que propone siempre pasa por tu revisión. En nuestras pruebas `llama3.2:3b` fue más preciso
y rápido (7 s por consulta) que `qwen3:1.7b`, que llegó a inventar un dato.

## Copias de seguridad

- Antes de actualizar: `flask respaldo` (crea `respaldos\porsiacaso_FECHA.db` verificado).
- Restaurar: detén el sitio y la jornada, copia el respaldo sobre `porsiacaso.db`.
- Copia también la carpeta `static\uploads\`.

## Problemas frecuentes

| Ves | Qué hacer |
|---|---|
| «Ya hay una jornada en curso» | Espera a que termine o pulsa Detener. Si la laptop se apagó, el bloqueo se libera solo a los 5 minutos |
| Fuente «Con errores» | Abre la fuente, pulsa Probar lectura. Puede haber cambiado su página |
| 0 fichas | Revisa que haya fuentes **activas** con permiso de extracción |
| Ficha sin fecha límite | Las bases pueden ser un PDF escaneado: complétala tú desde la fuente |

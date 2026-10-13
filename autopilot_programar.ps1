# Registra la jornada diaria del Autopilot en el Programador de tareas de Windows.
# Ejecutar UNA vez en PowerShell (sin permisos de administrador):
#   powershell -ExecutionPolicy Bypass -File .\autopilot_programar.ps1 -Hora 06:30
# Para quitarla:  Unregister-ScheduledTask -TaskName "PorSiAcaso Autopilot" -Confirm:$false
param(
    [string]$Hora = "06:30"
)
$carpeta = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat = Join-Path $carpeta "autopilot_jornada.bat"
if (-not (Test-Path $bat)) { throw "No se encontró $bat" }

$accion = New-ScheduledTaskAction -Execute $bat -WorkingDirectory $carpeta
$disparador = New-ScheduledTaskTrigger -Daily -At $Hora
# - StartWhenAvailable: si la laptop estaba apagada a esa hora, corre al encenderla.
# - WakeToRun: intenta despertar la laptop si está suspendida (no si está apagada).
# - ExecutionTimeLimit 2 h 15 min: red de seguridad; la jornada se cierra sola a los 120 min.
$opciones = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2 -Minutes 15) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "PorSiAcaso Autopilot" -Action $accion -Trigger $disparador -Settings $opciones `
    -Description "Jornada diaria del Autopilot de PorSiAcaso (máximo 120 minutos)" -Force | Out-Null
Write-Host "Tarea registrada: todos los días a las $Hora. Registro en $carpeta\logs\autopilot_programador.log"

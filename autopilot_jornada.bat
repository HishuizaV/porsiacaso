@echo off
REM PorSiAcaso Autopilot - una jornada (maximo 120 minutos) y se cierra sola.
REM Lo usa el Programador de tareas de Windows; tambien puede ejecutarse con doble clic.
cd /d "%~dp0"
if not exist logs mkdir logs
set FLASK_APP=app.py
set PYTHONIOENCODING=utf-8
echo ==== %DATE% %TIME% ==== >> logs\autopilot_programador.log
"%~dp0venv\Scripts\python.exe" -m flask autopilot jornada --origen programador >> logs\autopilot_programador.log 2>&1
REM Si hay un servidor publico configurado, envia lo preparado (requiere AUTOPILOT_TOKEN y AUTOPILOT_DESTINO)
if not "%AUTOPILOT_DESTINO%"=="" "%~dp0venv\Scripts\python.exe" -m flask autopilot sincronizar --destino %AUTOPILOT_DESTINO% >> logs\autopilot_programador.log 2>&1
exit /b 0

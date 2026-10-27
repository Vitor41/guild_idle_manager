@echo off
setlocal
cd /d "%~dp0"
set "APP_MODE=desktop"
set "GIM_PYTHONW=%~dp0.venv-desktop\Scripts\pythonw.exe"
if not exist "%GIM_PYTHONW%" (
  echo O ambiente desktop nao foi encontrado.
  echo Crie .venv-desktop e instale requirements-desktop-dev.txt conforme docs\DEV_DESKTOP.md.
  pause
  exit /b 1
)
start "Guild Idle Manager" "%GIM_PYTHONW%" -m app.desktop
endlocal

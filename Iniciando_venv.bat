@echo off
setlocal

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Criando ambiente virtual em %VENV_DIR%...
    py -3 -m venv "%VENV_DIR%"
    if errorlevel 1 (
        python -m venv "%VENV_DIR%"
    )
)

if not exist "%PYTHON_EXE%" (
    echo Nao foi possivel encontrar ou criar o Python do ambiente virtual.
    pause
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"

echo Instalando/validando dependencias...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo Aplicando migrations do banco...
python -m alembic upgrade head
if errorlevel 1 (
    echo Falha ao aplicar migrations. Verifique o PostgreSQL e o arquivo .env.
    pause
    exit /b 1
)

echo Iniciando Guild Idle Manager em http://127.0.0.1:8000
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause

@echo off
REM Construye el ejecutable de Windows (.exe) para TGI Report Generator.
REM Requiere: Python 3.11+ instalado. Ejecutar EN Windows.
setlocal
cd /d "%~dp0"

echo ==^> Creando entorno virtual (.venv_build)
python -m venv .venv_build
call .venv_build\Scripts\activate.bat

echo ==^> Instalando dependencias
python -m pip install --upgrade pip
pip install -r requirements-desktop.txt pyinstaller

echo ==^> Construyendo con PyInstaller
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --clean TGI_Report_Generator.spec

echo.
echo ==^> Listo. El ejecutable esta en:  dist\TGI_Report_Generator\TGI_Report_Generator.exe
endlocal

#!/usr/bin/env bash
# Construye el ejecutable de macOS (.app) para TGI Report Generator.
# Requiere: Python 3.11+ instalado. Ejecutar EN un Mac.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Creando entorno virtual (.venv_build)"
python3 -m venv .venv_build
source .venv_build/bin/activate

echo "==> Instalando dependencias"
pip install --upgrade pip
pip install -r requirements-desktop.txt pyinstaller

echo "==> Construyendo con PyInstaller"
rm -rf build dist
pyinstaller --noconfirm --clean TGI_Report_Generator.spec

echo ""
echo "==> Listo. La app está en:  dist/TGI_Report_Generator.app"
echo "    Ábrela con doble clic o:  open dist/TGI_Report_Generator.app"

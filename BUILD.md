# Construir TGI Report Generator (Mac y Windows)

La aplicación es Python + PyQt6 y funciona en **macOS** y **Windows**. El código es
el mismo para ambos; lo único distinto es el paso de empaquetado.

> **Importante:** PyInstaller **no** compila para otro sistema. El ejecutable de
> cada plataforma se construye **en esa misma plataforma**:
> - El `.exe` de Windows se arma en una máquina Windows.
> - El `.app` de macOS se arma en un Mac.

## Requisitos

- Python 3.11 o superior instalado.
- Conexión a internet la primera vez (para descargar dependencias).

## macOS

```bash
cd TGI_V1_Codigo_Fuente
./build_mac.sh
```

Resultado: `dist/TGI_Report_Generator.app`
Ábrela con doble clic o con `open dist/TGI_Report_Generator.app`.

> La primera vez, macOS puede advertir que la app es de un desarrollador no
> identificado. Para abrirla: clic derecho sobre la app → **Abrir** → **Abrir**.
> (O en Ajustes del Sistema → Privacidad y Seguridad → "Abrir de todos modos".)

## Windows

```bat
cd TGI_V1_Codigo_Fuente
build_windows.bat
```

Resultado: `dist\TGI_Report_Generator\TGI_Report_Generator.exe`
Se distribuye la carpeta `dist\TGI_Report_Generator\` completa (el `.exe` necesita
la subcarpeta `_internal` que va al lado).

## Ejecutar sin empaquetar (desarrollo, cualquier SO)

```bash
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Si el build se cuelga o es lentísimo (Mac)

Si la carpeta del proyecto está en el **Escritorio** o en **Documentos** y tienes
activada la sincronización con iCloud, las lecturas de los 1.500+ shapefiles
pueden colgarse (error `TimeoutError: Operation timed out`). Solución: copia la
carpeta a una ruta local no sincronizada (por ejemplo `/tmp/tgi_build`) y
construye desde ahí:

```bash
cp -R TGI_V1_Codigo_Fuente /tmp/tgi_build
cd /tmp/tgi_build
./build_mac.sh
```

El build empaqueta los shapefiles como un único `shapefiles.zip` (se genera solo
la primera vez; bórralo si cambias los shapefiles). La app los extrae sola en
tiempo de ejecución.

## Notas

- El empaquetado incluye automáticamente los datos que la app necesita
  (plantillas `.xlsx`, KMZ, y la carpeta `shapefiles/`), configurados en
  `TGI_Report_Generator.spec`.
- `requirements.txt` lista las dependencias exactas. Si agregas una librería nueva
  al código, añádela ahí antes de reconstruir.
- El `.spec` excluye librerías pesadas no usadas (torch, matplotlib, etc.) para que
  el ejecutable no crezca de más.

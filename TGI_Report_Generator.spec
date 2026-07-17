# -*- mode: python ; coding: utf-8 -*-
# Spec multiplataforma: produce un .app en macOS y un .exe (carpeta) en Windows.
# PyInstaller NO compila cruzado: ejecuta este spec en cada SO por separado.
import sys
import os
import zipfile

# Empaquetar los 1500+ shapefiles como UN solo .zip acelera enormemente el
# build (sobre todo el paso BUNDLE de macOS, que procesa archivo por archivo)
# y descarta los .gpkg que el código no usa. cips_infra los extrae en runtime.
# Si shapefiles.zip ya existe se reutiliza (bórralo para regenerarlo).
if not os.path.exists('shapefiles.zip') and os.path.isdir('shapefiles'):
    with zipfile.ZipFile('shapefiles.zip', 'w', zipfile.ZIP_DEFLATED) as _z:
        for _f in sorted(os.listdir('shapefiles')):
            if _f.endswith(('.shp', '.shx', '.dbf', '.prj', '.cpg')):
                _z.write(os.path.join('shapefiles', _f), _f)

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('EN BLANCO.xlsx', '.'), ('CIPS EN BLANCO.xlsx', '.'), ('Infra_General_TGI_V11_29032023.kmz', '.'), ('Infraestrutura TGI.xlsx', '.'), ('Listado equipos TGI.xlsx', '.'), ('consolidado OT.xlsx', '.'), ('PPM.XLSX', '.'), ('Listado de Infraestructura para Cod Informes.xlsx', '.'), ('shapefiles.zip', '.')],
    hiddenimports=['sklearn.utils._typedefs', 'sklearn.neighbors._partition_nodes', 'shapely', 'pyproj', 'shapefile'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchvision', 'torchgen', 'functorch', 'numba', 'llvmlite', 'onnxruntime', 'matplotlib', 'IPython', 'notebook', 'tornado'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TGI_Report_Generator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='TGI_Report_Generator',
)

# En macOS, empaquetar como .app de doble clic.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='TGI_Report_Generator.app',
        icon=None,
        bundle_identifier='com.pcc.tgi.reportgenerator',
        info_plist={
            'CFBundleName': 'TGI Report Generator',
            'CFBundleDisplayName': 'TGI Report Generator',
            'NSHighResolutionCapable': True,
        },
    )

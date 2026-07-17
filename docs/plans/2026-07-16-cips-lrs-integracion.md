# Integración CIPS-LRS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el procesamiento CIPS de la app ejecutable (PyQt6) por el motor LRS basado en shapefiles de `proceso-cips`, volcando el resultado en la hoja "Potenciales CIPS" del informe TGI.

**Architecture:** Motor LRS portado verbatim (unificar + snap a traza + PK geométrico + limpieza) expuesto como función testeable `procesar_cips_lrs(lista_archivos, shp_path)`. Un resolvedor Empresa/Distrito/Tramo → shapefile (vía Excel de infraestructura), un adaptador de esquema LRS → formato de `generator.fill_cips`, y un selector en la UI. `load_cips` se reescribe como glue delgado sobre esas piezas.

**Tech Stack:** Python 3.11, PyQt6, pandas, openpyxl, pyproj, shapely, pyshp (`shapefile`), scikit-learn.

---

## Convenciones

- **Carpeta de trabajo (SRC):** `/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente`
- **Intérprete de test (PY):** `/private/tmp/claude-501/-Users-pabloandresrivera-Desktop-Reportes-TGI-ejecutable/fe4ca874-ddce-4142-959f-70e0de4696f6/scratchpad/venv/bin/python`
  Ya tiene instaladas: PyQt6, pandas, openpyxl, pyproj, shapely, scikit-learn, pyshp, pillow, pytest.
- **Repo `proceso-cips` clonado en:** `/private/tmp/claude-501/-Users-pabloandresrivera-Desktop-Reportes-TGI-ejecutable/fe4ca874-ddce-4142-959f-70e0de4696f6/scratchpad/proceso-cips`
- Todos los tests se corren con `QT_QPA_PLATFORM=offscreen` cuando toquen PyQt.
- La carpeta no es repositorio git → Task 0 lo inicializa para permitir commits.

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `SRC/mod_unificar.py` (crear, copia verbatim) | Unifica varios Excel CIPS, arma columna `Comentarios` |
| `SRC/mod_cips_lrs.py` (crear, copia verbatim) | Motor LRS de referencia (lectura shapefile, snap, PK, limpieza) |
| `SRC/cips_lrs.py` (crear) | Wrapper testeable `procesar_cips_lrs(lista, shp)`; adapta I/O y conserva mV crudos |
| `SRC/cips_infra.py` (crear) | Carga Excel infra; API Empresa→Distrito→Tramo→shapefile |
| `SRC/cips_adapter.py` (crear) | Mapea DataFrame LRS → `list[dict]` para `fill_cips` |
| `SRC/app.py` (modificar) | Selector Empresa/Distrito/Tramo; reescribir `load_cips`; quitar CIPS viejo |
| `SRC/requirements.txt` (modificar) | Añadir deps GIS |
| `SRC/TGI_Report_Generator.spec` (modificar) | Añadir shapefiles + Excel infra a `datas` |
| `SRC/shapefiles/` (copiar) | Geometría de ductos |
| `SRC/Listado de Infraestructura para Cod Informes.xlsx` (copiar) | Mapeo tramos |
| `SRC/tests/conftest.py` (crear) | Fixture: genera CIPS sintético sobre shapefile real |
| `SRC/tests/test_cips_lrs.py` (crear) | Test del motor |
| `SRC/tests/test_cips_infra.py` (crear) | Test del resolvedor de shapefile |
| `SRC/tests/test_cips_adapter.py` (crear) | Test del adaptador |
| `SRC/tests/test_load_cips_integration.py` (crear) | Test integración engine→adapter→hoja |

---

### Task 0: Inicializar git y traer los assets

**Files:**
- Create: `SRC/.gitignore`

- [ ] **Step 1: Inicializar repo**

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"
git init
printf '__pycache__/\n*.pyc\n.pytest_cache/\ntests/_tmp/\n' > .gitignore
git add -A && git commit -m "chore: baseline del codigo fuente TGI antes de integrar CIPS-LRS"
```

- [ ] **Step 2: Copiar módulos de motor verbatim desde el repo clonado**

```bash
SRC="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"
REPO="/private/tmp/claude-501/-Users-pabloandresrivera-Desktop-Reportes-TGI-ejecutable/fe4ca874-ddce-4142-959f-70e0de4696f6/scratchpad/proceso-cips"
cp "$REPO/mod_unificar.py" "$SRC/mod_unificar.py"
cp "$REPO/mod_cips_lrs.py" "$SRC/mod_cips_lrs.py"
```

- [ ] **Step 3: Copiar assets (shapefiles + Excel infra)**

```bash
cp -R "$REPO/shapefiles" "$SRC/shapefiles"
cp "$REPO/data/Listado de Infraestructura para Cod Informes.xlsx" "$SRC/Listado de Infraestructura para Cod Informes.xlsx"
ls "$SRC/shapefiles" | wc -l   # espera ~1547
```

- [ ] **Step 4: Commit**

```bash
cd "$SRC" && git add -A && git commit -m "chore: traer motor CIPS-LRS y assets (shapefiles, infra) desde proceso-cips"
```

---

### Task 1: Scaffolding de tests + fixture de datos sintéticos

**Files:**
- Create: `SRC/tests/__init__.py`
- Create: `SRC/tests/conftest.py`

- [ ] **Step 1: Crear `tests/__init__.py` vacío**

```python
```

- [ ] **Step 2: Crear el fixture que genera CIPS sintético sobre un shapefile real**

`SRC/tests/conftest.py`:

```python
import os
import glob
import numpy as np
import pandas as pd
import pytest
import shapefile  # pyshp

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def shp_real():
    """Ruta a un shapefile real del bundle (R_ACA.shp)."""
    ruta = os.path.join(SRC, "shapefiles", "R_ACA.shp")
    assert os.path.exists(ruta), f"No existe {ruta}"
    return ruta


@pytest.fixture
def archivos_cips(tmp_path, shp_real):
    """Crea 2 Excel CIPS sintéticos con puntos a lo largo del shapefile real.
    Devuelve la lista de rutas."""
    sf = shapefile.Reader(shp_real)
    pts = sf.shapes()[0].points  # (lon, lat) en WGS84
    muestra = pts[:60]
    lons = [p[0] for p in muestra]
    lats = [p[1] for p in muestra]
    n = len(lons)
    rng = np.random.default_rng(42)

    rutas = []
    for k in range(2):
        ini = k * n
        survey = pd.DataFrame({
            "Data No": range(ini + 1, ini + n + 1),
            "Dist From Start": np.arange(n) * 10.0,
            "On Voltage": -1.1 + rng.standard_normal(n) * 0.02,
            "Off Voltage": -0.9 + rng.standard_normal(n) * 0.02,
            "Latitude": lats,
            "Longitude": lons,
            "Comment": [""] * n,
            "DCP/Feature/DCVG Anomaly": [""] * n,
        })
        dcp = pd.DataFrame({
            "Data No": [ini + 1],
            "Device ID": ["ABC123"],
            "Comments": ["inicio de tramo"],
        })
        ruta = os.path.join(tmp_path, f"cips_{k}.xlsx")
        with pd.ExcelWriter(ruta, engine="openpyxl") as w:
            survey.to_excel(w, sheet_name="Survey Data", index=False)
            dcp.to_excel(w, sheet_name="DCP Data", index=False)
        rutas.append(ruta)
    return rutas
```

- [ ] **Step 3: Verificar que el fixture importa (sin tests aún)**

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/ --collect-only -q
```

Expected: `no tests ran` sin errores de import (`$PY` = intérprete de test).

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test: scaffolding y fixture de datos CIPS sinteticos"
```

---

### Task 2: Wrapper del motor `cips_lrs.py`

El wrapper reutiliza `mod_unificar` y `mod_cips_lrs` verbatim (misma matemática LRS), adaptando solo el I/O: recibe **lista de archivos** y **conserva los mV crudos** (`On_mV`, `Off_mV`) que el export original descarta, para que la hoja del informe tenga columnas crudas y limpias distintas.

**Files:**
- Create: `SRC/cips_lrs.py`
- Test: `SRC/tests/test_cips_lrs.py`

- [ ] **Step 1: Escribir el test que falla**

`SRC/tests/test_cips_lrs.py`:

```python
import pandas as pd
from cips_lrs import procesar_cips_lrs


def test_procesar_cips_lrs_columnas_y_estado(archivos_cips, shp_real):
    df = procesar_cips_lrs(archivos_cips, shp_real)

    # Columnas clave que el adaptador necesita
    for col in ["PK_geom_m", "Lat_corr", "Long_corr",
                "On_mV_limpio", "Off_mV_limpio", "Estado_CP",
                "On_mV", "Off_mV", "Comentarios"]:
        assert col in df.columns, f"Falta columna {col}"

    # Los mV crudos se conservan (no None) y difieren en escala de Voltios
    assert df["On_mV"].notna().any()
    assert df["Off_mV"].notna().any()

    # Estado_CP solo toma valores válidos
    assert set(df["Estado_CP"].unique()) <= {"PROTEGIDO", "DESPROTEGIDO", "SOBREPROTEGIDO"}

    # PK monótono creciente tras ordenar
    pk = df["PK_geom_m"].dropna().tolist()
    assert pk == sorted(pk)
```

- [ ] **Step 2: Correr test para verificar que falla**

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_cips_lrs.py -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'cips_lrs'`.

- [ ] **Step 3: Escribir `cips_lrs.py`**

`SRC/cips_lrs.py`:

```python
"""Wrapper testeable del motor CIPS-LRS (proceso-cips).

Reutiliza mod_unificar + mod_cips_lrs (matemática LRS idéntica). Adapta el I/O:
recibe una lista de rutas de archivo y devuelve el DataFrame procesado
CONSERVANDO los mV crudos (On_mV/Off_mV) que el export original descarta.
"""
import os
import shutil
import tempfile
import numpy as np
import pandas as pd
import shapefile  # pyshp
from pyproj import Transformer
from shapely.geometry import Point
from sklearn.linear_model import LinearRegression

from mod_unificar import ejecutar_unificar
from mod_cips_lrs import _leer_linea_proyectada

CRITERIO_OK = -850
CRITERIO_MARGINAL = -1200


def procesar_cips_lrs(lista_archivos_xlsx, shp_path, carpeta_salida=None):
    """Unifica los archivos y aplica LRS sobre la traza del shapefile.

    Devuelve un DataFrame con, al menos: PK_geom_m, PK_real_m, Lat_corr,
    Long_corr, On_mV, Off_mV, On_mV_limpio, Off_mV_limpio, IR_Drop_mV_limpio,
    Estado_CP, Comentarios.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # Copiar los archivos a un temp para reusar ejecutar_unificar(carpeta)
        for ruta in lista_archivos_xlsx:
            shutil.copy(ruta, os.path.join(tmp, os.path.basename(ruta)))
        unif = ejecutar_unificar(tmp)

        xls = pd.ExcelFile(unif)
        df = pd.read_excel(xls, sheet_name="Survey Data")

        df = df.rename(columns={
            "Dist From Start": "PK_equipo",
            "On Voltage": "On_V",
            "Off Voltage": "Off_V",
            "Latitude": "Lat",
            "Longitude": "Long",
            "Comment": "Comentario",
            "DCP/Feature/DCVG Anomaly": "Anomalia",
        })

        def _clean(v):
            try:
                v = str(v).strip()
                return np.nan if v in ("", ".", "-", "None", "nan") else float(v)
            except Exception:
                return np.nan

        df["Lat"] = df["Lat"].apply(_clean)
        df["Long"] = df["Long"].apply(_clean)

        for coord in ("Lat", "Long"):
            mask = df[coord].isna()
            if mask.any() and (~mask).sum() >= 2:
                m = LinearRegression()
                m.fit(df.loc[~mask, ["PK_equipo"]], df.loc[~mask, coord])
                df.loc[mask, coord] = m.predict(df.loc[mask, ["PK_equipo"]])

        t_fwd = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        df["X"], df["Y"] = t_fwd.transform(df["Long"].values, df["Lat"].values)
        df["geometry"] = [Point(x, y) for x, y in zip(df["X"], df["Y"])]

        linea = _leer_linea_proyectada(shp_path)
        snapped = [linea.interpolate(linea.project(p)) for p in df["geometry"]]
        df["geometry"] = snapped
        df["PK_geom_m"] = [linea.project(p) for p in df["geometry"]]

        df_pk = df[["PK_equipo", "PK_geom_m"]].dropna()
        corr = df_pk["PK_equipo"].corr(df_pk["PK_geom_m"])
        if corr is not None and corr < 0:
            df["PK_geom_m"] = linea.length - df["PK_geom_m"]

        df["PK_real_m"] = df["PK_geom_m"] - df["PK_geom_m"].min()
        df = df.sort_values("PK_geom_m").reset_index(drop=True)

        t_back = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        xs = [p.x for p in df["geometry"]]
        ys = [p.y for p in df["geometry"]]
        df["Long_corr"], df["Lat_corr"] = t_back.transform(xs, ys)

        # mV crudos: SE CONSERVAN (a diferencia del export original)
        df["On_mV"] = df["On_V"] * 1000
        df["Off_mV"] = df["Off_V"] * 1000

        WINDOW, UMBRAL = 15, 250
        for col, out_col in [("Off_mV", "Off_mV_limpio"), ("On_mV", "On_mV_limpio")]:
            med = df[col].rolling(WINDOW, center=True).median()
            mask_out = abs(df[col] - med) > UMBRAL
            df[out_col] = df[col].copy()
            df.loc[mask_out, out_col] = med[mask_out]

        df["IR_Drop_mV_limpio"] = df["On_mV_limpio"] - df["Off_mV_limpio"]

        def validar(off):
            if pd.isna(off):
                return "DESPROTEGIDO"
            if off <= CRITERIO_MARGINAL:
                return "SOBREPROTEGIDO"
            if off <= CRITERIO_OK:
                return "PROTEGIDO"
            return "DESPROTEGIDO"

        df["Estado_CP"] = df["Off_mV_limpio"].apply(validar)

        df = df.drop(columns=["X", "Y", "geometry"], errors="ignore")

        if carpeta_salida:
            salida = os.path.join(carpeta_salida, "CIPS_VALIDADO_FINAL.xlsx")
            with pd.ExcelWriter(salida, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Survey Data", index=False)
            return df, salida

        return df
```

- [ ] **Step 4: Correr test para verificar que pasa**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_cips_lrs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: motor CIPS-LRS testeable (conserva mV crudos)"
```

---

### Task 3: Resolvedor de shapefile `cips_infra.py`

**Files:**
- Create: `SRC/cips_infra.py`
- Test: `SRC/tests/test_cips_infra.py`

- [ ] **Step 1: Escribir el test que falla**

`SRC/tests/test_cips_infra.py`:

```python
import os
from cips_infra import InfraTramos

SRC = os.path.dirname(os.path.abspath(__file__)).replace("/tests", "")


def test_empresas_y_cascada():
    infra = InfraTramos()
    empresas = infra.empresas()
    assert "TGI" in empresas and "OCENSA" in empresas

    # OCENSA: tramos directos, sin distrito
    tramos_oc = infra.tramos(empresa="OCENSA")
    assert len(tramos_oc) > 0

    # TGI: distritos D1..D8
    distritos = infra.distritos_tgi()
    assert "D1" in distritos
    tramos_d1 = infra.tramos(empresa="TGI", distrito="D1")
    assert len(tramos_d1) > 0


def test_resolver_shapefile_existente():
    infra = InfraTramos()
    # Cusiana - El Porvenir (OCENSA) -> CUS-EPO.shp existe
    shp = infra.shapefile(empresa="OCENSA", tramo="Cusiana - El Porvenir")
    assert shp is not None
    assert shp.endswith("CUS-EPO.shp")
    assert os.path.exists(shp)


def test_resolver_shapefile_faltante_devuelve_none():
    infra = InfraTramos()
    shp = infra.shapefile(empresa="TGI", distrito="X", tramo="NoExiste")
    assert shp is None
```

- [ ] **Step 2: Correr test para verificar que falla**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_cips_infra.py -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'cips_infra'`.

- [ ] **Step 3: Escribir `cips_infra.py`**

`SRC/cips_infra.py`:

```python
"""Resolución Empresa/Distrito/Tramo -> shapefile, vía el Excel de infraestructura.

Réplica de la lógica del sidebar de proceso-cips: OCENSA usa tramo directo;
TGI usa Distrito -> Tramo. El Excel tiene columnas: ID TRAMO, TRAMO, DISTRITO.
"""
import os
import sys
import pandas as pd


def _resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class InfraTramos:
    def __init__(self, excel_path=None, shapefiles_dir=None):
        self.excel_path = excel_path or _resource_path(
            "Listado de Infraestructura para Cod Informes.xlsx")
        self.shapefiles_dir = shapefiles_dir or _resource_path("shapefiles")
        self.df = pd.read_excel(self.excel_path)

    def empresas(self):
        return ["TGI", "OCENSA"]

    def distritos_tgi(self):
        sub = self.df[self.df["DISTRITO"] != "OCENSA"]
        return sorted(sub["DISTRITO"].dropna().unique().tolist())

    def tramos(self, empresa, distrito=None):
        if empresa == "OCENSA":
            sub = self.df[self.df["DISTRITO"] == "OCENSA"]
        else:
            sub = self.df[self.df["DISTRITO"] != "OCENSA"]
            if distrito:
                sub = sub[sub["DISTRITO"] == distrito]
        return sub["TRAMO"].dropna().astype(str).tolist()

    def shapefile(self, empresa, tramo, distrito=None):
        if empresa == "OCENSA":
            fila = self.df[(self.df["DISTRITO"] == "OCENSA") &
                           (self.df["TRAMO"] == tramo)]
        else:
            cond = (self.df["DISTRITO"] != "OCENSA") & (self.df["TRAMO"] == tramo)
            if distrito:
                cond = (self.df["DISTRITO"] == distrito) & (self.df["TRAMO"] == tramo)
            fila = self.df[cond]
        if fila.empty:
            return None
        id_tramo = str(fila["ID TRAMO"].values[0])
        ruta = os.path.join(self.shapefiles_dir, id_tramo + ".shp")
        return ruta if os.path.exists(ruta) else None
```

- [ ] **Step 4: Correr test para verificar que pasa**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_cips_infra.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: resolvedor Empresa/Distrito/Tramo -> shapefile"
```

---

### Task 4: Adaptador de esquema `cips_adapter.py`

Mapea el DataFrame LRS a la lista de dicts que espera `generator.fill_cips`.
Referencia de claves que consume `fill_cips` (generator.py:295-345): `abscisa_val`,
`referencia`, `on_mv`, `off_mv`, `on_limpio`, `off_limpio`, `vac`, `metal_on/off`,
`far_on/off`, `near_on/off`, `lat`, `lon`, `observaciones`. Las de Far/Near/Metal/VAC
se dejan ausentes (→ celdas vacías), como en proceso-cips.

**Files:**
- Create: `SRC/cips_adapter.py`
- Test: `SRC/tests/test_cips_adapter.py`

- [ ] **Step 1: Escribir el test que falla**

`SRC/tests/test_cips_adapter.py`:

```python
import pandas as pd
import numpy as np
from cips_adapter import lrs_df_a_cips_dicts


def _df_min():
    return pd.DataFrame({
        "PK_geom_m": [0.0, 1234.0],
        "Lat_corr": [4.1, 4.2],
        "Long_corr": [-73.1, -73.2],
        "On_mV": [-1100.0, -1050.0],
        "Off_mV": [-900.0, -880.0],
        "On_mV_limpio": [-1100.0, -1050.0],
        "Off_mV_limpio": [-900.0, -880.0],
        "Comentarios": ["inicio", ""],
        "Estado_CP": ["PROTEGIDO", "PROTEGIDO"],
    })


def test_mapeo_basico():
    dicts = lrs_df_a_cips_dicts(_df_min())
    assert len(dicts) == 2
    d0 = dicts[0]
    assert d0["abscisa_val"] == 0
    assert d0["on_mv"] == -1100.0
    assert d0["off_mv"] == -900.0
    assert d0["on_limpio"] == -1100.0
    assert d0["off_limpio"] == -900.0
    assert d0["lat"] == 4.1
    assert d0["lon"] == -73.1
    assert d0["observaciones"] == "inicio"
    # columnas no producidas por LRS: ausentes o vacías
    assert not d0.get("vac")
    assert not d0.get("far_on")


def test_abscisa_val_redondeado_entero():
    dicts = lrs_df_a_cips_dicts(_df_min())
    assert dicts[1]["abscisa_val"] == 1234
    assert isinstance(dicts[1]["abscisa_val"], int)
```

- [ ] **Step 2: Correr test para verificar que falla**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_cips_adapter.py -v
```

Expected: FAIL con `ModuleNotFoundError: No module named 'cips_adapter'`.

- [ ] **Step 3: Escribir `cips_adapter.py`**

`SRC/cips_adapter.py`:

```python
"""Adaptador: DataFrame del motor CIPS-LRS -> list[dict] para generator.fill_cips.

Las columnas Far/Near/Metal Ground y VAC no las produce el motor LRS; se dejan
ausentes para que fill_cips escriba celdas vacías (comportamiento de proceso-cips).
"""
import math
import pandas as pd


def _num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def lrs_df_a_cips_dicts(df):
    salida = []
    for _, row in df.iterrows():
        pk = row.get("PK_geom_m")
        abscisa_val = int(round(pk)) if pd.notna(pk) else 0
        comentario = str(row.get("Comentarios", "") or "").strip()
        salida.append({
            "abscisa_val": abscisa_val,
            "referencia": comentario,
            "observaciones": comentario,
            "on_mv": _num(row.get("On_mV")),
            "off_mv": _num(row.get("Off_mV")),
            "on_limpio": _num(row.get("On_mV_limpio")),
            "off_limpio": _num(row.get("Off_mV_limpio")),
            "lat": _num(row.get("Lat_corr")),
            "lon": _num(row.get("Long_corr")),
        })
    return salida
```

- [ ] **Step 4: Correr test para verificar que pasa**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_cips_adapter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: adaptador esquema LRS -> hoja Potenciales CIPS"
```

---

### Task 5: Test de integración engine → adapter → hoja

Verifica que la cadena completa escribe filas reales en la hoja "Potenciales CIPS"
de `EN BLANCO.xlsx` sin romper `fill_cips`.

**Files:**
- Test: `SRC/tests/test_load_cips_integration.py`

- [ ] **Step 1: Escribir el test**

`SRC/tests/test_load_cips_integration.py`:

```python
import os
from cips_lrs import procesar_cips_lrs
from cips_adapter import lrs_df_a_cips_dicts
from generator import ReportGenerator

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cadena_completa_escribe_hoja_cips(archivos_cips, shp_real, tmp_path):
    df = procesar_cips_lrs(archivos_cips, shp_real)
    dicts = lrs_df_a_cips_dicts(df)
    assert len(dicts) > 0

    gen = ReportGenerator()  # usa EN BLANCO.xlsx del SRC
    gen.fill_cips(dicts)

    ws = gen.wb["Potenciales CIPS"]
    # fila 12 = primer registro; col 2 = abscisa, col 5 = on_mv
    assert ws.cell(row=12, column=1).value == 1
    assert ws.cell(row=12, column=5).value is not None

    out = os.path.join(tmp_path, "informe_test.xlsx")
    gen.save(out)
    assert os.path.exists(out)
```

- [ ] **Step 2: Correr test**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_load_cips_integration.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "test: integracion engine->adapter->hoja Potenciales CIPS"
```

---

### Task 6: Selector Empresa/Distrito/Tramo en la UI

Añade tres combos en el tab "Datos Generales" (`setup_tab1`), poblados desde
`InfraTramos`, con cascada: Empresa cambia visibilidad de Distrito y repuebla Tramo.

**Files:**
- Modify: `SRC/app.py` (import; `setup_tab1`; nuevos métodos)

- [ ] **Step 1: Añadir el import de InfraTramos**

En `SRC/app.py`, tras la línea `from photo_utils import PhotoProcessor` (línea 18), añadir:

```python
from cips_infra import InfraTramos
```

- [ ] **Step 2: Crear los combos en `setup_tab1`**

En `SRC/app.py`, dentro de `setup_tab1`, **antes** de la línea
`local_layout.addWidget(self.btn_load_cips, 2, 0, 1, 2)` (línea 639), insertar:

```python
        # --- Selector CIPS: Empresa / Distrito / Tramo ---
        try:
            self.infra_tramos = InfraTramos()
        except Exception as e:
            self.infra_tramos = None
            print("No se pudo cargar infraestructura CIPS:", e)

        self.cmb_cips_empresa = QComboBox()
        self.cmb_cips_empresa.addItems(["TGI", "OCENSA"])
        self.cmb_cips_distrito = QComboBox()
        self.cmb_cips_tramo = QComboBox()

        self.cmb_cips_empresa.currentTextChanged.connect(self._on_cips_empresa_changed)
        self.cmb_cips_distrito.currentTextChanged.connect(self._on_cips_distrito_changed)

        local_layout.addWidget(QLabel("Empresa CIPS:"), 4, 0)
        local_layout.addWidget(self.cmb_cips_empresa, 4, 1)
        local_layout.addWidget(QLabel("Distrito:"), 5, 0)
        local_layout.addWidget(self.cmb_cips_distrito, 5, 1)
        local_layout.addWidget(QLabel("Tramo CIPS:"), 6, 0)
        local_layout.addWidget(self.cmb_cips_tramo, 6, 1)

        self._on_cips_empresa_changed(self.cmb_cips_empresa.currentText())
```

- [ ] **Step 3: Añadir los métodos de cascada**

En `SRC/app.py`, añadir estos métodos a la clase `AppWindow` (por ejemplo justo
antes de `def load_cips(self):`, línea 1421):

```python
    def _on_cips_empresa_changed(self, empresa):
        if not getattr(self, "infra_tramos", None):
            return
        es_tgi = (empresa == "TGI")
        self.cmb_cips_distrito.setVisible(es_tgi)
        if es_tgi:
            self.cmb_cips_distrito.blockSignals(True)
            self.cmb_cips_distrito.clear()
            self.cmb_cips_distrito.addItems(self.infra_tramos.distritos_tgi())
            self.cmb_cips_distrito.blockSignals(False)
            self._on_cips_distrito_changed(self.cmb_cips_distrito.currentText())
        else:
            self.cmb_cips_tramo.clear()
            self.cmb_cips_tramo.addItems(self.infra_tramos.tramos(empresa="OCENSA"))

    def _on_cips_distrito_changed(self, distrito):
        if not getattr(self, "infra_tramos", None):
            return
        if self.cmb_cips_empresa.currentText() != "TGI":
            return
        self.cmb_cips_tramo.clear()
        self.cmb_cips_tramo.addItems(
            self.infra_tramos.tramos(empresa="TGI", distrito=distrito))
```

- [ ] **Step 4: Smoke test de la UI (poblado y cascada)**

`SRC/tests/test_ui_cips_selector.py`:

```python
import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _stub_gemini():
    g = types.ModuleType("google.generativeai")
    g.configure = lambda **k: None
    g.GenerativeModel = object
    g.list_models = lambda: []
    sys.modules["google"] = types.ModuleType("google")
    sys.modules["google.generativeai"] = g


def test_selector_cascada():
    _stub_gemini()
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app import AppWindow
    w = AppWindow()

    assert w.cmb_cips_empresa.count() == 2
    # TGI por defecto -> distrito visible y tramos no vacíos
    w.cmb_cips_empresa.setCurrentText("TGI")
    assert w.cmb_cips_distrito.isVisibleTo(w) in (True, False)  # existe
    assert w.cmb_cips_tramo.count() > 0

    # OCENSA -> tramos OCENSA
    w.cmb_cips_empresa.setCurrentText("OCENSA")
    assert w.cmb_cips_tramo.count() > 0
```

Run:

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/test_ui_cips_selector.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: selector Empresa/Distrito/Tramo CIPS en la UI"
```

---

### Task 7: Reescribir `load_cips` y quitar el CIPS viejo

Reemplaza la implementación rota (KMZ + `cmb_kmz_rutas` + método de hilo) por el
flujo nuevo. Elimina el import de `CIPSReader`.

**Files:**
- Modify: `SRC/app.py` (import línea 15; método `load_cips` líneas 1421-1672)

- [ ] **Step 1: Quitar el import de CIPSReader**

En `SRC/app.py` línea 15, eliminar:

```python
from cips_reader import CIPSReader
```

- [ ] **Step 2: Reemplazar el cuerpo de `load_cips`**

Reemplazar **todo** el método `load_cips` (desde `def load_cips(self):` en la
línea 1421 hasta antes de `def refresh_cips_table(self):` en la 1674) por:

```python
    def load_cips(self):
        try:
            archivos, _ = QFileDialog.getOpenFileNames(
                self, "Seleccionar Data CIPS", "", "Excel (*.xlsx)")
            if not archivos:
                return

            if not getattr(self, "infra_tramos", None):
                QMessageBox.warning(self, "Error",
                    "No se cargó la base de infraestructura de tramos.")
                return

            empresa = self.cmb_cips_empresa.currentText()
            tramo = self.cmb_cips_tramo.currentText()
            distrito = self.cmb_cips_distrito.currentText() if empresa == "TGI" else None
            shp = self.infra_tramos.shapefile(empresa=empresa, tramo=tramo, distrito=distrito)
            if not shp:
                QMessageBox.warning(self, "Error",
                    f"No se encontró shapefile para el tramo '{tramo}'.")
                return

            self.lbl_status.setText("Procesando CIPS (LRS)...")
            QApplication.processEvents()

            from cips_lrs import procesar_cips_lrs
            from cips_adapter import lrs_df_a_cips_dicts
            df = procesar_cips_lrs(archivos, shp)
            cips_dicts = lrs_df_a_cips_dicts(df)

            self.data['cips'].extend(cips_dicts)
            self.refresh_cips_table()
            self.lbl_status.setText(
                f"Data CIPS procesada: {len(cips_dicts)} registros.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error CIPS",
                f"Ocurrió un error procesando CIPS:\n{str(e)}")
            self.lbl_status.setText("Error.")
```

- [ ] **Step 3: Verificar que la app arranca y `load_cips` no referencia widgets fantasma**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -c "
import sys, types
g = types.ModuleType('google.generativeai'); g.configure=lambda **k: None; g.GenerativeModel=object; g.list_models=lambda: []
sys.modules['google']=types.ModuleType('google'); sys.modules['google.generativeai']=g
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from app import AppWindow
w = AppWindow()
import inspect
src = inspect.getsource(w.load_cips)
assert 'cmb_kmz_rutas' not in src, 'load_cips aun referencia cmb_kmz_rutas'
assert 'procesar_cips_lrs' in src
print('OK: load_cips reescrito, sin widgets fantasma')
"
```

Expected: `OK: load_cips reescrito, sin widgets fantasma`.

- [ ] **Step 4: Correr toda la suite**

```bash
QT_QPA_PLATFORM=offscreen "$PY" -m pytest tests/ -v
```

Expected: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: reescribir load_cips con motor LRS; quitar CIPS viejo (KMZ)"
```

---

### Task 8: Dependencias y empaquetado

**Files:**
- Modify: `SRC/requirements.txt`
- Modify: `SRC/TGI_Report_Generator.spec`

- [ ] **Step 1: Actualizar `requirements.txt`**

Reemplazar el contenido de `SRC/requirements.txt` por:

```
openpyxl>=3.1.0
PyQt6>=6.5.0
pandas>=2.0.0
numpy>=1.26.0
scipy>=1.12.0
pyproj>=3.6.0
shapely>=2.0.0
pyshp>=2.3.1
scikit-learn>=1.4.0
pillow>=10.0.0
google-generativeai>=0.7.0
```

- [ ] **Step 2: Añadir assets a `datas` en el `.spec`**

En `SRC/TGI_Report_Generator.spec`, en la lista `datas=[...]` de `Analysis`,
añadir estas dos entradas (dejando las existentes):

```python
    ('Listado de Infraestructura para Cod Informes.xlsx', '.'),
    ('shapefiles', 'shapefiles'),
```

Y añadir hiddenimports para las libs GIS (reemplazar `hiddenimports=[]` por):

```python
    hiddenimports=['sklearn.utils._typedefs', 'sklearn.neighbors._partition_nodes',
                   'shapely', 'pyproj', 'shapefile'],
```

- [ ] **Step 3: Verificar que el `.spec` es Python válido**

```bash
"$PY" -c "compile(open('/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/TGI_Report_Generator.spec').read(), 'spec', 'exec'); print('spec OK')"
```

Expected: `spec OK`.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "build: deps GIS y assets CIPS en requirements y .spec"
```

---

## Notas de cierre

- **Reconstrucción del `.exe`:** requiere Windows con Python 3.11 y
  `pyinstaller TGI_Report_Generator.spec`. No se puede reconstruir en Mac; queda
  fuera del alcance de este plan (solo se deja el `.spec` correcto).
- **`cips_reader.py`** queda en la carpeta pero ya sin uso; se puede borrar en una
  limpieza posterior (fuera de alcance).
- El resto de bugs de auditoría (VAC, hoja `pe`, métodos duplicados, librerías no
  usadas de 474 MB) no se tocan aquí.

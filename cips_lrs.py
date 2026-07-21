"""Wrapper testeable del motor CIPS-LRS (proceso-cips).

Reutiliza mod_unificar + mod_cips_lrs (matemática LRS idéntica). Adapta el I/O:
recibe una lista de rutas de archivo y devuelve el DataFrame procesado
CONSERVANDO los mV crudos (On_mV/Off_mV) que el export original descarta.
"""
import os
import re
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

# Etiqueta de abscisa que el técnico escribe en la hoja DCP Data, p.ej.
# "pk 00+000: Pipe To Soil", "km 5+120 junta 3", "PK2+000". El número antes del
# '+' son kilómetros y el de después metros dentro del km.
_RE_ABSCISA = re.compile(r'(?:pk|km)\s*(\d+)\s*\+\s*(\d+)', re.IGNORECASE)


def _parse_abscisa_label(texto):
    """Devuelve la abscisa en metros de una etiqueta de campo, o None."""
    if texto is None or (isinstance(texto, float) and np.isnan(texto)):
        return None
    m = _RE_ABSCISA.search(str(texto))
    if not m:
        return None
    return int(m.group(1)) * 1000 + int(m.group(2))


def _abscisa_desde_dcp(unif, df):
    """Añade a df la columna 'Abscisa_label_m' con la abscisa rotulada por el
    técnico en la hoja DCP Data, mapeada por 'Data No' y rellenada hacia
    adelante (las sub-lecturas de un mismo poste heredan su abscisa). df debe
    venir en orden de adquisición (antes de ordenar por PK geométrico)."""
    df["Abscisa_label_m"] = np.nan
    try:
        dcp = pd.read_excel(unif, sheet_name="DCP Data")
    except Exception:
        return df
    col_feat = next((c for c in dcp.columns
                     if 'Feature' in str(c) or 'Anomaly' in str(c)), None)
    if col_feat is None or "Data No" not in dcp.columns or "Data No" not in df.columns:
        return df
    dcp["_absc"] = dcp[col_feat].apply(_parse_abscisa_label)
    etiquetas = dcp.dropna(subset=["_absc"]).groupby("Data No")["_absc"].first()
    if etiquetas.empty:
        return df
    df["Abscisa_label_m"] = df["Data No"].map(etiquetas).ffill()
    return df


def procesar_cips_lrs(lista_archivos_xlsx, shp_path, carpeta_salida=None):
    """Unifica los archivos y aplica LRS sobre la traza del shapefile.

    Devuelve un DataFrame con, al menos: PK_geom_m, PK_real_m, Lat_corr,
    Long_corr, On_mV, Off_mV, On_mV_limpio, Off_mV_limpio, IR_Drop_mV_limpio,
    Estado_CP, Comentarios.
    """
    with tempfile.TemporaryDirectory() as tmp:
        for ruta in lista_archivos_xlsx:
            shutil.copy(ruta, os.path.join(tmp, os.path.basename(ruta)))
        unif = ejecutar_unificar(tmp)

        xls = pd.ExcelFile(unif)
        df = pd.read_excel(xls, sheet_name="Survey Data")

        # Exportes acumulativos del logger repiten registros completos entre
        # archivos; una fila 100% idéntica es el mismo registro medido una vez.
        df = df.drop_duplicates().reset_index(drop=True)

        # Abscisa rotulada por el técnico (hoja DCP Data). En levantamientos por
        # postes el GPS se repite entre postes distintos, así que la proyección
        # geométrica los colapsa; la etiqueta es la fuente fiable. Se calcula
        # AQUÍ, en orden de adquisición, antes de reordenar por PK geométrico.
        df = _abscisa_desde_dcp(unif, df)

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

        # Abscisa final: la etiqueta del técnico manda; el PK geométrico (GPS)
        # es solo respaldo cuando la lectura no trae etiqueta. El informe se
        # ordena por esta abscisa real, no por la proyección GPS.
        df["Abscisa_final_m"] = df["Abscisa_label_m"]
        faltan = df["Abscisa_final_m"].isna()
        df.loc[faltan, "Abscisa_final_m"] = df.loc[faltan, "PK_geom_m"]
        df = df.sort_values("Abscisa_final_m", kind="stable").reset_index(drop=True)

        t_back = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        xs = [p.x for p in df["geometry"]]
        ys = [p.y for p in df["geometry"]]
        df["Long_corr"], df["Lat_corr"] = t_back.transform(xs, ys)

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

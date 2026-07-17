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
        for ruta in lista_archivos_xlsx:
            shutil.copy(ruta, os.path.join(tmp, os.path.basename(ruta)))
        unif = ejecutar_unificar(tmp)

        xls = pd.ExcelFile(unif)
        df = pd.read_excel(xls, sheet_name="Survey Data")

        # Exportes acumulativos del logger repiten registros completos entre
        # archivos; una fila 100% idéntica es el mismo registro medido una vez.
        df = df.drop_duplicates().reset_index(drop=True)

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

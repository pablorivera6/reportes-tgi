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

# Si la mediana de la distancia punto→traza supera esto, el tramo elegido no
# corresponde a los datos (GPS ruidoso ronda decenas de metros; un tramo
# equivocado queda a kilómetros).
UMBRAL_TRAMO_M = 300.0


def _lecturas_dcp(unif, df):
    """Extrae de la hoja DCP Data las lecturas de Metal IR / Far Ground /
    Near Ground y las asigna al punto del survey con el mismo Data No, en mV
    (Value1=ON, Value2=OFF; el equipo las registra en V)."""
    TIPOS = (("metal", "metal ir"), ("far", "far ground"), ("near", "near ground"))
    for pref, _ in TIPOS:
        df[f"{pref}_on_mv"] = np.nan
        df[f"{pref}_off_mv"] = np.nan
    try:
        dcp = pd.read_excel(unif, sheet_name="DCP Data")
    except Exception:
        return df
    col_feat = next((c for c in dcp.columns
                     if 'Feature' in str(c) or 'Anomaly' in str(c)), None)
    if col_feat is None or "Data No" not in dcp.columns or "Data No" not in df.columns:
        return df
    for _, fila in dcp.iterrows():
        feat = str(fila.get(col_feat, "") or "").lower()
        for pref, marca in TIPOS:
            if marca in feat:
                idx = df.index[df["Data No"] == fila["Data No"]]
                if len(idx) and pd.isna(df.loc[idx[0], f"{pref}_on_mv"]):
                    v1, v2 = fila.get("Value1"), fila.get("Value2")
                    if pd.notna(v1):
                        df.loc[idx[0], f"{pref}_on_mv"] = float(v1) * 1000
                    if pd.notna(v2):
                        df.loc[idx[0], f"{pref}_off_mv"] = float(v2) * 1000
                break
    return df


class TramoIncorrectoError(ValueError):
    """Los datos del archivo no corresponden al tramo/shapefile elegido."""

    def __init__(self, dist_m, lat=None, lon=None):
        self.dist_m = dist_m
        self.lat = lat
        self.lon = lon
        super().__init__(
            f"Los puntos del archivo quedan a ~{dist_m / 1000:.1f} km de la "
            f"traza del tramo seleccionado: el tramo NO corresponde a los "
            f"datos. Verifica Empresa/Distrito/Tramo.")


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

        # Lecturas Metal IR / Far / Near de la hoja DCP Data, por Data No.
        df = _lecturas_dcp(unif, df)

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

        # Guardia: si los puntos quedan lejos de la traza, el usuario eligió un
        # tramo que no es (p.ej. dejó el tramo por defecto del selector). Sin
        # esto, todo se proyecta al extremo de la traza y la abscisa sale 0.
        dist_traza = pd.Series(
            [p.distance(s) for p, s in zip(df["geometry"], snapped)])
        med = float(dist_traza.median()) if len(dist_traza) else 0.0
        if med > UMBRAL_TRAMO_M:
            raise TramoIncorrectoError(
                med, lat=float(df["Lat"].median()), lon=float(df["Long"].median()))

        df["geometry"] = snapped
        df["PK_geom_m"] = [linea.project(p) for p in df["geometry"]]

        df_pk = df[["PK_equipo", "PK_geom_m"]].dropna()
        corr = df_pk["PK_equipo"].corr(df_pk["PK_geom_m"])
        if corr is not None and corr < 0:
            df["PK_geom_m"] = linea.length - df["PK_geom_m"]

        # ── Respaldo por GPS congelado ───────────────────────────────────────
        # Si el equipo no actualizó el GPS (todas las lecturas con la misma
        # coordenada, típico dentro de estaciones de válvulas), la proyección
        # colapsa a un solo PK y la abscisa saldría constante (p.ej. todo 0).
        # Solo en ese caso la abscisa se toma del odómetro del equipo
        # ('Dist From Start' → PK_equipo), anclada a la etiqueta 'pk X+YYY' si
        # aparece en los comentarios. Con GPS normal el cálculo es IDÉNTICO al
        # de la app original proceso-cips.
        fuente_abscisa = "GPS"
        span_geom = float(df["PK_geom_m"].max() - df["PK_geom_m"].min()) if len(df) else 0.0
        pk_eq = pd.to_numeric(df["PK_equipo"], errors="coerce")
        span_eq = float(pk_eq.max() - pk_eq.min()) if pk_eq.notna().any() else 0.0
        if len(df) >= 3 and span_eq > 0 and span_geom < max(5.0, 0.01 * span_eq):
            import re as _re
            pat = _re.compile(r'(?:pk|km)\s*(\d+)\s*[+]\s*(\d+)', _re.IGNORECASE)
            ancla = 0.0
            encontrada = False
            for col in ("Comentarios", "Anomalia", "Comentario"):
                if col not in df.columns or encontrada:
                    continue
                for idx, txt in df[col].items():
                    if pd.isna(txt):
                        continue
                    m = pat.search(str(txt))
                    if m and pd.notna(pk_eq.loc[idx]):
                        etiqueta_m = int(m.group(1)) * 1000 + int(m.group(2))
                        ancla = etiqueta_m - float(pk_eq.loc[idx])
                        encontrada = True
                        break
            df["PK_geom_m"] = pk_eq.fillna(0) + ancla
            fuente_abscisa = "EQUIPO"

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

        df.attrs["fuente_abscisa"] = fuente_abscisa

        if carpeta_salida:
            salida = os.path.join(carpeta_salida, "CIPS_VALIDADO_FINAL.xlsx")
            with pd.ExcelWriter(salida, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Survey Data", index=False)
            return df, salida

        return df

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
        # Abscisa: la rotulada por el técnico (Abscisa_final_m) tiene prioridad;
        # si el motor no la trae (versión previa), se cae al PK geométrico.
        pk = row.get("Abscisa_final_m")
        if pk is None or (isinstance(pk, float) and math.isnan(pk)):
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

import pandas as pd
from cips_lrs import procesar_cips_lrs


def test_procesar_cips_lrs_columnas_y_estado(archivos_cips, shp_real):
    df = procesar_cips_lrs(archivos_cips, shp_real)

    for col in ["PK_geom_m", "Lat_corr", "Long_corr",
                "On_mV_limpio", "Off_mV_limpio", "Estado_CP",
                "On_mV", "Off_mV", "Comentarios"]:
        assert col in df.columns, f"Falta columna {col}"

    assert df["On_mV"].notna().any()
    assert df["Off_mV"].notna().any()

    assert set(df["Estado_CP"].unique()) <= {"PROTEGIDO", "DESPROTEGIDO", "SOBREPROTEGIDO"}

    pk = df["PK_geom_m"].dropna().tolist()
    assert pk == sorted(pk)

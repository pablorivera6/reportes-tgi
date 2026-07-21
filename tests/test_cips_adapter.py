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
    assert d0["observaciones"] == "Inicio"
    assert not d0.get("vac")
    assert not d0.get("far_on")


def test_abscisa_val_redondeado_entero():
    dicts = lrs_df_a_cips_dicts(_df_min())
    assert dicts[1]["abscisa_val"] == 1234
    assert isinstance(dicts[1]["abscisa_val"], int)

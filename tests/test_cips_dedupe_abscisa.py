"""Un solo punto por abscisa: el GPS quieto hace que varias lecturas caigan
en el mismo metro de la traza y el informe salía con 2-3 filas repetidas por
abscisa. Se deja un punto por abscisa SIN perder información: comentarios y
lecturas DCP de los duplicados se conservan en el punto que queda."""
import pandas as pd

from cips_adapter import lrs_df_a_cips_dicts


def _df(filas):
    return pd.DataFrame(filas)


def test_un_punto_por_abscisa_conservando_datos():
    df = _df([
        # tres lecturas en la misma abscisa 19: la 2a trae Metal IR, la 3a comenta
        {'PK_geom_m': 19.2, 'On_mV': -1641.5, 'Off_mV': -1072.5,
         'On_mV_limpio': -1641.5, 'Off_mV_limpio': -1072.5,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
        {'PK_geom_m': 19.3, 'On_mV': -1649.7, 'Off_mV': -1074.3,
         'On_mV_limpio': -1649.7, 'Off_mV_limpio': -1074.3,
         'Comentarios': '', 'metal_on_mv': -75.7, 'metal_off_mv': -13.9,
         'Lat_corr': 4.6, 'Long_corr': -75.7},
        {'PK_geom_m': 19.4, 'On_mV': -1650.0, 'Off_mV': -1075.0,
         'On_mV_limpio': -1650.0, 'Off_mV_limpio': -1075.0,
         'Comentarios': 'salida valvula', 'Lat_corr': 4.6, 'Long_corr': -75.7},
        # abscisa distinta: se conserva aparte
        {'PK_geom_m': 25.0, 'On_mV': -1700.0, 'Off_mV': -1100.0,
         'On_mV_limpio': -1700.0, 'Off_mV_limpio': -1100.0,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
    ])
    dicts = lrs_df_a_cips_dicts(df)
    assert [d['abscisa_val'] for d in dicts] == [19, 25], (
        f"abscisas: {[d['abscisa_val'] for d in dicts]}")
    d19 = dicts[0]
    assert d19['on_mv'] == -1641.5                     # se queda la primera lectura
    assert d19['metal_on'] == -75.7                    # lectura DCP del duplicado
    assert 'válvula' in d19['observaciones'].lower()   # comentario del duplicado


def test_sin_duplicados_no_cambia_nada():
    df = _df([
        {'PK_geom_m': 10.0, 'On_mV': -1600.0, 'Off_mV': -1000.0,
         'On_mV_limpio': -1600.0, 'Off_mV_limpio': -1000.0,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
        {'PK_geom_m': 20.0, 'On_mV': -1610.0, 'Off_mV': -1010.0,
         'On_mV_limpio': -1610.0, 'Off_mV_limpio': -1010.0,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
    ])
    assert len(lrs_df_a_cips_dicts(df)) == 2

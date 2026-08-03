"""El dedup CIPS debe eliminar SOLO repetidos exactos (misma abscisa y mismos
valores), no colapsar todas las lecturas de un mismo metro — se perdía calidad
de data de la inspección."""
import pandas as pd

from cips_adapter import lrs_df_a_cips_dicts


def _df(filas):
    return pd.DataFrame(filas)


def test_conserva_lecturas_distintas_misma_abscisa():
    # dos lecturas DISTINTAS que redondean al mismo metro (19) -> se conservan
    df = _df([
        {'PK_geom_m': 19.2, 'On_mV': -1641.5, 'Off_mV': -1072.5,
         'On_mV_limpio': -1641.5, 'Off_mV_limpio': -1072.5,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
        {'PK_geom_m': 19.4, 'On_mV': -1650.0, 'Off_mV': -1075.0,
         'On_mV_limpio': -1650.0, 'Off_mV_limpio': -1075.0,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
        {'PK_geom_m': 25.0, 'On_mV': -1700.0, 'Off_mV': -1100.0,
         'On_mV_limpio': -1700.0, 'Off_mV_limpio': -1100.0,
         'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7},
    ])
    dicts = lrs_df_a_cips_dicts(df)
    # 3 lecturas distintas (2 en abscisa 19 + 1 en 25) -> NO se colapsan a 1/metro
    assert len(dicts) == 3
    assert [d['abscisa_val'] for d in dicts] == [19, 19, 25]


def test_elimina_repetido_exacto():
    # misma abscisa Y mismos valores (exporte solapado) -> se deja una sola
    fila = {'PK_geom_m': 19.2, 'On_mV': -1641.5, 'Off_mV': -1072.5,
            'On_mV_limpio': -1641.5, 'Off_mV_limpio': -1072.5,
            'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7}
    df = _df([fila, dict(fila), {'PK_geom_m': 25.0, 'On_mV': -1700.0,
             'Off_mV': -1100.0, 'On_mV_limpio': -1700.0, 'Off_mV_limpio': -1100.0,
             'Comentarios': '', 'Lat_corr': 4.6, 'Long_corr': -75.7}])
    dicts = lrs_df_a_cips_dicts(df)
    assert len(dicts) == 2   # el repetido exacto se elimina


def test_repetido_conserva_comentario_y_dcp():
    base = {'PK_geom_m': 19.2, 'On_mV': -1641.5, 'Off_mV': -1072.5,
            'On_mV_limpio': -1641.5, 'Off_mV_limpio': -1072.5,
            'Lat_corr': 4.6, 'Long_corr': -75.7}
    a = dict(base, Comentarios='', metal_on_mv=-75.7, metal_off_mv=-13.9)
    b = dict(base, Comentarios='cruce caño')   # mismo valor, con comentario
    dicts = lrs_df_a_cips_dicts(_df([a, b]))
    assert len(dicts) == 1
    assert 'caño' in dicts[0]['observaciones'].lower()   # comentario conservado
    assert dicts[0]['metal_on'] == -75.7                 # lectura DCP conservada

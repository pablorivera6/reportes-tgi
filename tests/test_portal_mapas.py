"""DataFrames del portal cuando el tramo no tiene puntos que mapear.

Caso real (Palestina, 2026-09): su única inspección publicada es un DCVG que
**no encontró defectos**, y no hay CIPS ni PAP. La lista de filas del mapa
quedaba vacía, `pd.DataFrame([])` sale SIN columnas y el
`dropna(subset=["lat","lon"])` reventaba con KeyError — tumbando toda la página
"Vista por tramo", no solo el mapa. Y como esas inspecciones están aprobadas,
el error lo veía el cliente TGI.

Por eso las columnas se declaran explícitas: el DataFrame existe aunque no haya
una sola fila.
"""
import pandas as pd
import pytest

import dashboard


def test_df_puntos_vacio_conserva_las_columnas():
    df = dashboard.df_puntos([])
    assert df.empty
    for c in ("abscisa", "on", "off", "vac", "lat", "lon", "estado", "color"):
        assert c in df.columns


def test_df_puntos_vacio_admite_dropna_sin_reventar():
    """Es la llamada exacta que fallaba."""
    assert dashboard.df_puntos([]).dropna(subset=["lat", "lon"]).empty


def test_df_puntos_prefiere_el_potencial_limpio():
    df = dashboard.df_puntos([{"abscisa": 10, "on_mv": -1500, "off_mv": -900,
                               "on_limpio": -1480, "off_limpio": -880,
                               "lat": 5.0, "lon": -75.0}])
    assert df.loc[0, "on"] == -1480 and df.loc[0, "off"] == -880
    assert df.loc[0, "estado"] == "Protegido"
    assert df.loc[0, "color"] == dashboard.COLOR_ESTADO["Protegido"]


def test_df_puntos_cae_al_crudo_si_no_hay_limpio():
    df = dashboard.df_puntos([{"abscisa": 0, "on_mv": -1200, "off_mv": -700}])
    assert df.loc[0, "off"] == -700
    assert df.loc[0, "estado"] == "Desprotegido"


def test_df_mapa_vacio_conserva_las_columnas():
    df = dashboard.df_mapa([])
    assert df.empty
    assert list(df.columns) == ["lat", "lon", "color"]
    assert df.dropna(subset=["lat", "lon"]).empty


def test_df_mapa_descarta_las_filas_sin_coordenadas():
    df = dashboard.df_mapa([{"lat": 5.0, "lon": -75.0, "color": "#000"},
                            {"lat": None, "lon": None, "color": "#111"}])
    assert len(df.dropna(subset=["lat", "lon"])) == 1


def test_caso_palestina_dcvg_sin_defectos_y_sin_cips_ni_pap():
    """Un tramo cuyo único aporte al mapa sería una lista de defectos vacía."""
    det = {"DCVG": {"defectos": [], "postes": [], "resistividades": [],
                    "hallazgos": []}}
    filas = [{"lat": d.get("lat"), "lon": d.get("lon"), "color": "#000"}
             for d in det["DCVG"]["defectos"]]
    df = dashboard.df_mapa(filas).dropna(subset=["lat", "lon"])
    assert df.empty          # sin mapa, pero la página no se cae

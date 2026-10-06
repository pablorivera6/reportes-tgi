import os
import zipfile
from cips_infra import InfraTramos

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_empresas_y_cascada():
    infra = InfraTramos()
    empresas = infra.empresas()
    assert "TGI" in empresas and "OCENSA" in empresas

    tramos_oc = infra.tramos(empresa="OCENSA")
    assert len(tramos_oc) > 0

    distritos = infra.distritos_tgi()
    assert "D1" in distritos
    tramos_d1 = infra.tramos(empresa="TGI", distrito="D1")
    assert len(tramos_d1) > 0


def test_resolver_shapefile_existente():
    infra = InfraTramos()
    shp = infra.shapefile(empresa="OCENSA", tramo="Cusiana - El Porvenir")
    assert shp is not None
    assert shp.endswith("CUS-EPO.shp")
    assert os.path.exists(shp)


def test_resolver_shapefile_faltante_devuelve_none():
    infra = InfraTramos()
    shp = infra.shapefile(empresa="TGI", distrito="X", tramo="NoExiste")
    assert shp is None


def test_resolver_shapefile_desde_zip(tmp_path):
    # Empaqueta un tramo real (CUS-EPO) en un zip y resuelve SIN la carpeta.
    src_dir = os.path.join(SRC, "shapefiles")
    zpath = os.path.join(tmp_path, "shapefiles.zip")
    with zipfile.ZipFile(zpath, "w") as z:
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            z.write(os.path.join(src_dir, "CUS-EPO" + ext), "CUS-EPO" + ext)

    infra = InfraTramos(shapefiles_dir=os.path.join(tmp_path, "noexiste"),
                        shapefiles_zip=zpath)
    shp = infra.shapefile(empresa="OCENSA", tramo="Cusiana - El Porvenir")
    assert shp is not None
    assert shp.endswith("CUS-EPO.shp")
    assert os.path.exists(shp)
    # los archivos acompañantes también se extrajeron
    assert os.path.exists(shp.replace(".shp", ".dbf"))


def test_troncal_villavicencio_usme_tiene_shapefile():
    # El listado decía 'T_VIL_US' pero el archivo es T_VIL_USM.shp.
    infra = InfraTramos()
    shp = infra.shapefile(empresa="TGI", tramo="Troncal Villavicencio - Usme",
                          distrito="D4")
    assert shp is not None and shp.endswith("T_VIL_USM.shp")


import pytest


@pytest.mark.parametrize("tramo,distrito,archivo", [
    # ID equivocado en el listado (decía 'R_MNT')
    ("Troncal Montañuelo-Gualanday", "D2", "T_MON_GUA.shp"),
    # El archivo se llama con la sigla corta, no con el ID del listado
    ("Troncal Letras - Marsella", "D7", "T_LEMA.shp"),
    ("Troncal Mariquita - Letras", "D7", "T_MALE.shp"),
    ("Troncal Obando - Tuluá", "D8", "T_OBTU.shp"),
    ("Troncal Tulúa - Cali", "D8", "T_TUCA.shp"),
])
def test_tramos_con_id_distinto_al_archivo(tramo, distrito, archivo):
    infra = InfraTramos()
    shp = infra.shapefile(empresa="TGI", tramo=tramo, distrito=distrito)
    assert shp is not None and shp.endswith(archivo) and os.path.exists(shp)


def test_alias_tambien_desde_el_zip(tmp_path):
    # La app empaquetada lee de shapefiles.zip: el alias debe valer ahí.
    z = os.path.join(tmp_path, "s.zip")
    with zipfile.ZipFile(z, "w") as zf:
        for ext in (".shp", ".shx", ".dbf", ".prj"):
            zf.write(os.path.join(SRC, "shapefiles", "T_TUCA" + ext),
                     "T_TUCA" + ext)
    infra = InfraTramos(shapefiles_dir=os.path.join(tmp_path, "no_existe"),
                        shapefiles_zip=z)
    shp = infra.shapefile(empresa="TGI", tramo="Troncal Tulúa - Cali",
                          distrito="D8")
    assert shp is not None and shp.endswith("T_TUCA.shp")


def test_sugerir_incluye_tramo_con_alias():
    # Punto sobre la Troncal Tuluá - Cali (cerca de Buga)
    infra = InfraTramos()
    ids = [i for _, _, i in infra.sugerir_tramos(3.9, -76.3, max_seg=120)]
    assert "T_TUL_CAL" in ids


def test_la_victoria_d2_usa_la_traza_r_vict():
    # R_VICT.shp es la traza de La Victoria de Centro-Oriente (D2, sale de
    # Puerto Salgar - Mariquita): el CIPS 2023 del D2 cae a 0 m de ella.
    # El listado la tenía amarrada a la La Victoria del Valle (D8).
    infra = InfraTramos()
    shp = infra.shapefile(empresa="TGI", tramo="Ramal La Victoria", distrito="D2")
    assert shp is not None and shp.endswith("R_VICT.shp")


def test_la_victoria_d8_no_hereda_la_traza_del_d2():
    # La del Valle (Mariquita-Cali) queda a ~154 km de R_VICT: sin traza
    # propia es mejor "no tiene shapefile" que calcular abscisas sobre otra.
    infra = InfraTramos()
    d8 = [t for t in infra.tramos(empresa="TGI", distrito="D8") if "Victoria" in t]
    assert d8
    assert infra.shapefile(empresa="TGI", tramo=d8[0], distrito="D8") is None


def test_sugerencia_en_la_victoria_d2():
    infra = InfraTramos()
    sug = infra.sugerir_tramos(5.3145, -74.8544)
    victorias = [(t, d) for t, d, _ in sug if "Victoria" in t]
    assert victorias == [("Ramal La Victoria", "D2")]

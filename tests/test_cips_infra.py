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

"""Los HALLAZGOS del informe DCVG salen de la data cruda del logger (hoja DCP
Data: filas con comentario de campo), con abscisa=Station No y GPS de la hoja
Survey Data. Los defectos/postes siguen viniendo del FastField."""
import os

import openpyxl
import pytest

from dcvg_reader import leer_hallazgos_logger

_REF = "/private/tmp/dcvg_ref"


def _logger_sintetico(tmp_path):
    wb = openpyxl.Workbook()
    sd = wb.active; sd.title = "Survey Data"
    sd.append(["Data No", "Dist From Start", "Station No", "DCVG Voltage",
               "Comment", "DCP/Feature/DCVG Anomaly", "Latitude", "Longitude"])
    sd.append([1, 0, 500, 0.01, None, "Flag", 4.49, -75.73])
    sd.append([2, 0, 5740, 0.02, None, "Highway", 4.52, -75.74])
    dcp = wb.create_sheet("DCP Data")
    dcp.append(["Data No", "Station No", "DCP/Feature/Anomaly", "Value1",
                "Value2", "Comments", "Latitude", "Longitude"])
    dcp.append([1, 5740, "Highway", 0, 0, "cruse caño", None, None])
    dcp.append([2, 5735, "Highway", 0, 0, "toma resistividad", None, None])   # ruido
    dcp.append([3, 500, "Highway", 0, 0, "llegada valvula derivacion", None, None])
    dcp.append([4, 5785, "DCVG Anomaly", 0.05, 0.09, "Cathodic/Cathodic", None, None])  # carácter, no hallazgo
    ruta = os.path.join(tmp_path, "logger.xlsx")
    wb.save(ruta)
    return ruta


def test_hallazgos_logger_sintetico(tmp_path):
    h = leer_hallazgos_logger(_logger_sintetico(tmp_path))
    absc = sorted(x["abscisa_val"] for x in h)
    # cruce caño (5740) y llegada válvula (500); NO "toma resistividad" ni carácter
    assert 5740 in absc and 500 in absc
    assert 5735 not in absc, "no incluir puntos de solo 'toma resistividad'"
    # GPS traído de Survey Data por Station
    hv = next(x for x in h if x["abscisa_val"] == 5740)
    assert round(hv["lat"], 2) == 4.52


@pytest.mark.skipif(not os.path.isdir(_REF), reason="logger real no disponible")
def test_hallazgos_logger_montenegro():
    h = leer_hallazgos_logger(os.path.join(_REF, "DCVG MONTENEGRO 28 07 2026.xlsx"))
    assert len(h) >= 15, "debe extraer los hallazgos de campo"
    # todos con abscisa y la mayoría con GPS
    assert all(x["abscisa_val"] is not None for x in h)
    assert any("caño" in x["observaciones"].lower() or "cruce" in x["observaciones"].lower()
               for x in h)

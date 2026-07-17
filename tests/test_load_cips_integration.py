import os
from cips_lrs import procesar_cips_lrs
from cips_adapter import lrs_df_a_cips_dicts
from generator import ReportGenerator

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_cadena_completa_escribe_hoja_cips(archivos_cips, shp_real, tmp_path):
    df = procesar_cips_lrs(archivos_cips, shp_real)
    dicts = lrs_df_a_cips_dicts(df)
    assert len(dicts) > 0

    gen = ReportGenerator()  # usa EN BLANCO.xlsx del SRC
    gen.fill_cips(dicts)

    ws = gen.wb["Potenciales CIPS"]
    assert ws.cell(row=12, column=1).value == 1
    assert ws.cell(row=12, column=5).value is not None

    out = os.path.join(tmp_path, "informe_test.xlsx")
    gen.save(out)
    assert os.path.exists(out)

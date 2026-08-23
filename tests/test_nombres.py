"""Codificación del nombre de los archivos de informe y PPM.

Formato pedido por TGI:
  tipo_REP|PPM_R|T_sigla_mes_año_OT_contrato_PCC_Rev.A
Ejemplo real: DCVG_REP_R_ARM_03_25_1300013506_551007370_PCC_Rev.A
"""
import datetime

import pytest

from nombres import nombre_archivo, faltantes, sigla_tramo


def _info(**kw):
    base = {'tipo_inspeccion': 'DCVG', 'tramo': 'Armenia', 'fecha': '12/03/2025',
            'ot': '1300013506', 'contrato': '551007370'}
    base.update(kw)
    return base


def test_ejemplo_de_tgi():
    assert nombre_archivo(_info()) == \
        "DCVG_REP_R_ARM_03_25_1300013506_551007370_PCC_Rev.A.xlsx"


def test_ppm_cambia_rep_por_ppm():
    assert nombre_archivo(_info(), doc="PPM") == \
        "DCVG_PPM_R_ARM_03_25_1300013506_551007370_PCC_Rev.A.xlsx"


def test_troncal_lleva_t():
    # 'Norean - San Alberto' es Troncal, sigla NRSA (Infraestrutura TGI.xlsx)
    n = nombre_archivo(_info(tipo_inspeccion='CIPS', tramo='Norean - San Alberto'))
    assert n.startswith("CIPS_REP_T_NRSA_03_25_")


def test_cada_tipo_de_inspeccion_va_al_frente():
    for t in ("PAP", "CIPS", "DCVG"):
        assert nombre_archivo(_info(tipo_inspeccion=t)).startswith(f"{t}_REP_")


@pytest.mark.parametrize("fecha", [
    "12/03/2025", "2025-03-12", "12-03-2025", "12/03/25", "2025/03/12",
    "2025-03-12 00:00:00", datetime.date(2025, 3, 12),
    datetime.datetime(2025, 3, 12, 8, 30),
])
def test_mes_y_anio_en_cualquier_formato_de_fecha(fecha):
    assert "_03_25_" in nombre_archivo(_info(fecha=fecha))


def test_sigla_desde_el_archivo_de_infraestructura():
    assert sigla_tramo("Armenia")[:2] == ("ARM", "R")
    assert sigla_tramo("Norean - San Alberto")[:2] == ("NRSA", "T")
    # tolera acentos y el 'PK ...' que a veces trae el nombre del tramo
    assert sigla_tramo("Curumaní")[0] == "CUR"
    assert sigla_tramo("Armenia   PK 46+265")[:2] == ("ARM", "R")


def test_tramo_desconocido_no_rompe_el_nombre():
    sigla, letra, hallado = sigla_tramo("Ramal Que No Existe")
    assert hallado is False
    n = nombre_archivo(_info(tramo="Ramal Que No Existe"))
    # sin sigla oficial usa el nombre del tramo, pero el resto queda igual
    assert n.startswith("DCVG_REP_") and n.endswith("_PCC_Rev.A.xlsx")
    assert "03_25_1300013506_551007370" in n


def test_campos_vacios_no_dejan_dobles_guiones():
    n = nombre_archivo(_info(ot='', contrato=''))
    assert "__" not in n
    assert n == "DCVG_REP_R_ARM_03_25_PCC_Rev.A.xlsx"


def test_faltantes_avisa_que_no_se_pudo_codificar():
    assert faltantes(_info()) == []
    f = faltantes(_info(ot='', fecha='', tramo='Ramal Que No Existe'))
    assert 'OT' in f and 'Fecha' in f and any('sigla' in x.lower() for x in f)


def test_acentos_y_espacios_fuera_del_nombre():
    n = nombre_archivo(_info(tramo="Curumaní", contrato="551 007/370"))
    assert " " not in n and "/" not in n and "í" not in n


def test_sin_extension_si_se_pide():
    assert nombre_archivo(_info(), ext="") == \
        "DCVG_REP_R_ARM_03_25_1300013506_551007370_PCC_Rev.A"


def test_loop_y_aislado_tienen_su_letra():
    assert sigla_tramo("LOOP Cusiana - Miraflores")[1] == "L"
    assert sigla_tramo("Cantagallo - San Pablo")[1] == "A"


def test_tramo_duplicado_prefiere_la_linea_principal():
    # 'La Belleza - Vasconia' está dos veces: LOOP (BEVV) y Troncal (VRMB)
    assert sigla_tramo("La Belleza - Vasconia")[:2] == ("VRMB", "T")

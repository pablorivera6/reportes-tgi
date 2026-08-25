"""KMZ y paquete de entrega: el ZIP NO puede depender del KMZ.

En la app, el botón del paquete estaba anidado dentro del bloque del KMZ, y el
KMZ se construía dentro de un `except Exception: return None`. Resultado: si el
KMZ no se podía armar —por ejemplo, un DCVG sin defectos, o los defectos sin
coordenadas— desaparecían en silencio el KMZ **y** el paquete de entrega.
"""
import zipfile

import pytest

import entrega

BASE = {'cips': [], 'potenciales': [], 'hallazgos': [], 'dcvg_postes': [],
        'dcvg_defectos': [], 'dcvg_hallazgos': [], 'info': {}}


def _dcvg(**kw):
    d = dict(BASE, info={'tipo_inspeccion': 'DCVG', 'tramo': 'Ramal Armenia'})
    d.update(kw)
    return d


def test_dcvg_con_defectos(tmp_path):
    data = _dcvg(
        dcvg_postes=[{'pk_m': 0, 'on': -1600, 'off': -1100, 'lat': 4.5, 'lon': -75.7},
                     {'pk_m': 4000, 'on': -1600, 'off': -1100, 'lat': 4.55, 'lon': -75.75}],
        dcvg_defectos=[{'pk_m': 1500, 'ol_re': 50.0, 'caracter': 'AA',
                        'lat': 4.52, 'lon': -75.72}])
    kmz, motivo = entrega.kmz_de_inspeccion(data)
    assert kmz, motivo
    assert zipfile.ZipFile(__import__("io").BytesIO(kmz)).namelist()


def test_dcvg_sin_defectos_igual_arma_el_kmz():
    """Una inspección limpia (sin defectos) también tiene traza y hallazgos."""
    data = _dcvg(
        dcvg_postes=[{'pk_m': i * 1000, 'on': -1600, 'off': -1100,
                      'lat': 4.5 + i / 1000, 'lon': -75.7} for i in range(5)],
        dcvg_hallazgos=[{'abscisa_val': 2200, 'observaciones': 'cruce de caño',
                         'referencia': 'cruce', 'lat': 4.53, 'lon': -75.73}])
    kmz, motivo = entrega.kmz_de_inspeccion(data)
    assert kmz, f"un DCVG sin defectos se quedó sin KMZ: {motivo}"


def test_dcvg_con_defectos_sin_coordenadas():
    """FastField a veces no trae 'Ubicación': los postes sostienen el KMZ."""
    data = _dcvg(
        dcvg_postes=[{'pk_m': i * 1000, 'on': -1600, 'off': -1100,
                      'lat': 4.5 + i / 1000, 'lon': -75.7} for i in range(3)],
        dcvg_defectos=[{'pk_m': 1500, 'ol_re': 50.0, 'caracter': 'AA',
                        'lat': None, 'lon': None}])
    kmz, _m = entrega.kmz_de_inspeccion(data)
    assert kmz


def test_cips():
    data = dict(BASE, info={'tipo_inspeccion': 'CIPS', 'tramo': 'La Dorada'},
                cips=[{'abscisa_val': i * 10, 'lat': 5.44 + i / 10000, 'lon': -74.68,
                       'on_mv': -1500, 'off_mv': -1100, 'observaciones': ''}
                      for i in range(20)])
    kmz, motivo = entrega.kmz_de_inspeccion(data)
    assert kmz, motivo


def test_sin_datos_explica_el_motivo():
    kmz, motivo = entrega.kmz_de_inspeccion(dict(BASE, info={'tipo_inspeccion': 'DCVG'}))
    assert kmz is None
    assert motivo and "coordenada" in motivo.lower()


def test_un_error_no_se_traga_en_silencio():
    """Antes cualquier excepción devolvía None sin explicación."""
    kmz, motivo = entrega.kmz_de_inspeccion({'info': {}})     # dict incompleto
    assert kmz is None
    assert motivo            # siempre dice por qué


def test_el_paquete_se_arma_aunque_no_haya_kmz():
    """El entregable del contrato no puede depender del KMZ."""
    zip_bytes, resumen = entrega.construir_paquete(
        "DCVG_REP_R_ARM_03_25", "DCVG",
        informe=("informe.xlsx", b"contenido del informe"), kmz=None)
    import io
    nombres = zipfile.ZipFile(io.BytesIO(zip_bytes)).namelist()
    assert any("informe.xlsx" in n for n in nombres)
    assert resumen is not None

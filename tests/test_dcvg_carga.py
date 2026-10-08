"""La carga DCVG de la app no puede perder el tramo ni el recubrimiento porque
falle un paso secundario (logger, equipos, resistividades)."""
import pytest

from dcvg_carga import procesar_dcvg
from tests.test_dcvg_fastfield_campo import _dcvg, _resist


def _equipos(nombre):
    return ("S-123", "01/01/2026", ["Voltímetro"]) if nombre == "Juan Perez" else ("", "", [])


def test_el_fastfield_autollena_tramo_y_recubrimiento(tmp_path):
    r = procesar_dcvg([_dcvg(tmp_path / "d.xlsx")], [_resist(tmp_path / "r.xlsx")],
                      equipos_fn=_equipos)
    assert r['errores'] == []
    assert [p['pk_m'] for p in r['postes']] == [3000, 7000]
    assert len(r['resist']) == 1
    a = r['auto']
    assert a['tramo'] == 'Ramal Marsella'
    assert a['tipo_recubrimiento'] == 'FBE'          # del CSV de recubrimientos
    assert a['gasoducto'] == 'Mariquita-Cali' and a['contrato'] == '551007370'
    assert a['fecha'] == '07-05-2026' and a['contratista'] == 'PCC'


def test_un_logger_roto_no_tumba_el_autollenado(tmp_path):
    malo = tmp_path / "logger_roto.xlsx"
    malo.write_bytes(b"esto no es un xlsx")
    r = procesar_dcvg([_dcvg(tmp_path / "d.xlsx")], rutas_logger=[str(malo)])
    assert r['auto']['tramo'] == 'Ramal Marsella'
    assert r['auto']['tipo_recubrimiento'] == 'FBE'
    assert r['hallazgos'] == []
    assert any('logger' in e for e in r['errores']), r['errores']


def test_resistividad_rota_no_tumba_el_autollenado(tmp_path):
    malo = tmp_path / "resist_rota.xlsx"
    malo.write_bytes(b"nada")
    r = procesar_dcvg([_dcvg(tmp_path / "d.xlsx")], rutas_resist=[str(malo)])
    assert r['auto']['tramo'] == 'Ramal Marsella' and r['resist'] == []
    assert any('resistividades' in e for e in r['errores'])


def test_inspector_con_nombre_trae_sus_equipos(tmp_path):
    r = procesar_dcvg([_dcvg(tmp_path / "d.xlsx", tecnico="Juan Perez")], equipos_fn=_equipos)
    assert r['tecnico'] == "Juan Perez"
    assert r['auto']['serial_equipo'] == "S-123" and r['equipos'] == ["Voltímetro"]


def test_equipos_rotos_no_tumban_el_autollenado(tmp_path):
    def rompe(n):
        raise RuntimeError("listado dañado")
    r = procesar_dcvg([_dcvg(tmp_path / "d.xlsx", tecnico="Juan Perez")], equipos_fn=rompe)
    assert r['auto']['tramo'] == 'Ramal Marsella' and r['auto']['tipo_recubrimiento'] == 'FBE'
    assert any('equipos' in e for e in r['errores'])


def test_sin_fastfield_si_falla():
    with pytest.raises(Exception):
        procesar_dcvg(["/no/existe.xlsx"])

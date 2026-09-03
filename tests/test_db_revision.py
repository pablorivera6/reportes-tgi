"""La fila de inspección recuerda de dónde salió y en qué revisión va."""
import pytest

import db


def test_fila_inspeccion_guarda_origen_y_revision():
    fila = db._fila_inspeccion(
        {"tramo": "Ansermanuevo", "ot": "OT-1"}, "CIPS", 0, 1000, {}, "PCC",
        carga_id="carga-123", contexto={"info": {"tramo": "Ansermanuevo"}},
        revision="B")
    assert fila["carga_id"] == "carga-123"
    assert fila["contexto"]["info"]["tramo"] == "Ansermanuevo"
    assert fila["revision"] == "B"


def test_fila_inspeccion_sin_origen_no_mete_claves_vacias():
    fila = db._fila_inspeccion({"tramo": "X"}, "CIPS", 0, 1, {}, "PCC")
    assert "carga_id" not in fila and "contexto" not in fila
    assert fila["revision"] == "A"


def test_reemplazar_devuelve_estado_a_revision_y_limpia_el_rechazo():
    fila = db._fila_inspeccion({"tramo": "X"}, "CIPS", 0, 1, {}, "PCC",
                               revision="B", reemplaza=True)
    assert fila["estado"] == "en_revision"
    assert fila["nota_revision"] is None
    assert fila["revisado_por"] is None and fila["revisado_en"] is None


def test_guardar_con_reemplaza_id_sin_config_lanza_error(monkeypatch):
    monkeypatch.setattr(db, "_secrets", lambda: {})
    with pytest.raises(RuntimeError):
        db.guardar_inspeccion_cips({}, [], [], reemplaza_id="insp-1")

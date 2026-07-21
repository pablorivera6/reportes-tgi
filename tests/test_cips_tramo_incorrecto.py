"""Guardia de tramo equivocado: si los datos quedan lejos de la traza del
tramo seleccionado (p.ej. el usuario dejó el tramo por defecto del selector),
el motor debe negarse con TramoIncorrectoError en vez de proyectar todo al
extremo de la traza (abscisa 0 en todo). Caso real: archivos de Salento
procesados contra 'Aislado Brisas de Bolívar' (default del combo)."""
import os

import pytest

from cips_lrs import procesar_cips_lrs, TramoIncorrectoError
from cips_infra import InfraTramos

_SHP_LOCAL = "/private/tmp/tgi_push/shapefiles"


def test_tramo_equivocado_lanza_error(archivos_cips, tmp_path):
    otro = os.path.join(_SHP_LOCAL, "R_SAL.shp")
    if not os.path.exists(otro):
        pytest.skip("shapefiles locales no disponibles")
    # puntos de R_ACA (Acacías) contra la traza de Salento -> a cientos de km
    with pytest.raises(TramoIncorrectoError) as exc:
        procesar_cips_lrs(archivos_cips, otro)
    assert exc.value.dist_m > 1000
    assert exc.value.lat is not None


def test_sugerir_tramos_encuentra_salento():
    if not os.path.isdir(_SHP_LOCAL):
        pytest.skip("shapefiles locales no disponibles")
    infra = InfraTramos(shapefiles_dir=_SHP_LOCAL)
    # coordenada real de los archivos CIPS de Salento
    sugs = infra.sugerir_tramos(4.62688, -75.68613)
    ids = [i for _, _, i in sugs]
    assert "R_SAL" in ids, f"sugerencias: {sugs}"

"""La web de carga no deja enviar una carga sin evidencia.

Regresión: al sacar del catálogo los archivos que el técnico llena dentro de
FastField, PAP se quedó SIN ninguna casilla `req`. `faltantes()` devolvía lista
vacía, así que el botón Enviar aparecía habilitado con cero archivos y el envío
moría en un alert. Ahora la validación exige además al menos un adjunto.

El test corre el `web_carga/app.js` REAL sobre un DOM mínimo en Node
(`tests/web_carga_harness.js`) con el `data.js` REAL, así que si el catálogo
cambia el test sigue midiendo lo que de verdad ve el técnico.
"""
import json
import os
import shutil
import subprocess

import pytest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(SRC, "tests", "web_carga_harness.js")

SIN_EVIDENCIA = "Adjunta al menos un archivo de evidencia."


@pytest.fixture(scope="module")
def r():
    node = shutil.which("node")
    if not node:
        pytest.skip("node no está instalado en este entorno")
    out = subprocess.run([node, HARNESS], capture_output=True, text=True,
                         cwd=SRC, timeout=120)
    assert out.returncode == 0, f"el arnés falló:\n{out.stderr}"
    return json.loads(out.stdout)


def test_pap_no_tiene_casillas_obligatorias(r):
    # Si algún día PAP vuelve a tener una casilla `req`, este test avisa: la
    # regla de "al menos un archivo" se escribió justamente porque no la tiene.
    assert r["catalogo"]["PAP"] == []


def test_pap_sin_archivos_deja_el_boton_deshabilitado(r):
    assert r["pap_sin_archivos"]["disabled"] is True
    assert r["pap_sin_archivos"]["hint"] == SIN_EVIDENCIA


@pytest.mark.parametrize("caso", ["pap_con_equipos", "pap_con_foto"])
def test_pap_con_cualquier_archivo_habilita(r, caso):
    assert r[caso]["disabled"] is False
    assert r[caso]["hint"] == "Listo para enviar."


def test_cips_y_dcvg_conservan_sus_obligatorios(r):
    # La regla nueva no puede tapar la de casillas obligatorias: con un archivo
    # adjunto pero sin el obligatorio, CIPS sigue bloqueado y lo dice.
    assert r["cips_sin_archivos"]["disabled"] is True
    assert r["cips_solo_opcional"]["disabled"] is True
    assert "Archivo CIPS" in r["cips_solo_opcional"]["hint"]
    assert r["cips_completo"]["disabled"] is False
    assert r["dcvg_sin_archivos"]["disabled"] is True
    assert "Resistividades" in r["dcvg_sin_archivos"]["hint"]


def test_los_pk_siguen_mandando(r):
    # Con archivo adjunto pero sin PK final, el botón sigue deshabilitado.
    assert r["pap_con_archivo_sin_pk"]["disabled"] is True
    assert r["pap_con_archivo_sin_pk"]["hint"] == (
        "Completa tramo, fecha, nombre y PK inicial/final.")

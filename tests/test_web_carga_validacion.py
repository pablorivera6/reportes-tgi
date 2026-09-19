"""La web de carga: selector de tramo y validación del formulario.

Dos regresiones cubiertas aquí:

1. Al sacar del catálogo los archivos que el técnico llena dentro de FastField,
   PAP se quedó SIN ninguna casilla `req`: el botón Enviar aparecía habilitado
   con cero archivos y el envío moría en un alert. Ahora se exige al menos un
   adjunto.
2. El `<datalist>` nativo del campo Tramo no desplegaba de forma fiable en
   celular. Se reemplazó por un panel propio, y solo vale un tramo que exista
   en `window.TRAMOS` (texto libre ⇒ botón bloqueado).

El test corre el `web_carga/app.js` REAL sobre un DOM mínimo en Node
(`tests/web_carga_harness.js`) con el `data.js` REAL, así que si el catálogo o
la lista de tramos cambian el test sigue midiendo lo que ve el técnico.
"""
import json
import os
import shutil
import subprocess

import pytest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(SRC, "tests", "web_carga_harness.js")

SIN_EVIDENCIA = "Adjunta al menos un archivo de evidencia."
TRAMO_INVALIDO = "Selecciona un tramo válido de la lista."
FALTA_META = "Completa tramo, fecha, nombre y PK inicial/final."


@pytest.fixture(scope="module")
def r():
    node = shutil.which("node")
    if not node:
        pytest.skip("node no está instalado en este entorno")
    out = subprocess.run([node, HARNESS], capture_output=True, text=True,
                         cwd=SRC, timeout=120)
    assert out.returncode == 0, f"el arnés falló:\n{out.stderr}"
    return json.loads(out.stdout)


# ── Selector de tramo ────────────────────────────────────────────────────────

def test_al_tocar_el_campo_se_abre_la_lista_completa(r):
    # Lo que fallaba en celular: tocar el campo y no ver ningún tramo.
    assert r["panel_inicial_cerrado"] is True
    assert r["al_enfocar"]["abierto"] is True
    assert r["al_enfocar"]["n"] == r["total_tramos"] == 280


def test_filtra_al_escribir_ignorando_mayusculas_y_tildes(r):
    assert r["filtro_texto"]["abierto"] is True
    assert r["filtro_texto"]["opciones"] == ["Ramal Salento"]   # 'salento'
    assert r["filtro_sin_tilde"] == ["Ramal Chinchiná"]         # 'chinchina'
    assert r["filtro_sin_resultados"]["opciones"] == []


def test_al_tocar_un_tramo_lo_deja_en_el_campo_y_cierra(r):
    assert r["al_elegir"]["valor"] == "Ramal Salento"
    assert r["al_elegir"]["cerrado"] is True


def test_un_tramo_inventado_bloquea_el_envio(r):
    for caso in ("tramo_inventado", "filtro_sin_resultados"):
        est = r[caso] if "disabled" in r[caso] else r[caso]["estado"]
        assert est["disabled"] is True
        assert est["hint"] == TRAMO_INVALIDO


def test_tocar_fuera_cierra_el_panel(r):
    assert r["click_fuera_cierra"] is True


# ── Formateo del PK ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("escrito,visible", [
    ("125000", "125+000"),
    ("126500", "126+500"),
    ("9500", "9+500"),
    ("850", "0+850"),        # menos de 1 km
    ("125+000", "125+000"),  # ya formateado (pegado)
    ("", ""),                # vacío se queda vacío
])
def test_el_campo_muestra_el_pk_formateado(r, escrito, visible):
    # En iPhone el teclado numérico no trae el '+': el técnico escribe solo
    # dígitos y el campo los muestra como 'K+mmm'.
    assert r["pk_formato"][escrito or "(vacio)"] == visible


def test_se_formatea_mientras_teclea(r):
    assert r["tecleando"]["125000"] == "125+000"
    assert r["tecleando"]["850"] == "0+850"
    assert r["tecleando"]["pegado 125+000"] == "125+000"


def test_borrar_el_campo_lo_deja_vacio(r):
    assert r["al_borrar"]["valor"] == ""
    assert r["al_borrar"]["metros"] is None


def test_lo_que_se_ve_formateado_se_guarda_en_metros(r):
    # El campo muestra '125+000' y a Supabase (pk_inicial/pk_final) va el entero.
    assert r["a_la_bd"] == {"visible_inicial": "125+000", "metros_inicial": 125000,
                            "visible_final": "129+450", "metros_final": 129450}


# ── Validación del formulario ────────────────────────────────────────────────

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


def test_tecnico_y_pk_siguen_mandando(r):
    # Con tramo válido pero sin técnico elegido en el desplegable, bloqueado.
    assert r["sin_tecnico"]["disabled"] is True
    assert r["sin_tecnico"]["hint"] == FALTA_META
    # Con archivo adjunto pero sin PK final, también.
    assert r["pap_con_archivo_sin_pk"]["disabled"] is True
    assert r["pap_con_archivo_sin_pk"]["hint"] == FALTA_META

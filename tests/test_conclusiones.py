"""Las conclusiones base salen del generador SEGÚN EL TIPO de inspección.

Antes `ConclusionGenerator` solo sabía de PAP: un DCVG salía con "técnica de
Inspección PAP", estaciones de prueba y pintura de postes, y si en la sesión
quedaban potenciales de un PAP anterior se mezclaban con el CIPS o el DCVG.
"""
import pytest

from conclusions import ConclusionGenerator

INFO = {'tramo': 'Ramal Salento', 'tipo_ducto': 'Ramal', 'longitud_km': 15.8}
ACTIVAS = {'marco_h': False, 'ce': False, 'anodos': False,
           'cupones_ir': False, 'cupones_grav': False, 'pe': False}


def _pap():
    return [{'abscisa': i * 1000, 'abscisa_str': f'00{i}+000',
             'ref_geografica': 'Poste de Potencial', 'on_mv': -1100,
             'off_mv': -900 if i < 8 else -700, 'vac': 1.0} for i in range(10)]


def _cips():
    pts = []
    for i in range(100):
        a = i * 100
        off = -700 if 2000 <= a <= 2500 else -950          # 6 puntos desprotegidos
        crudo = -200 if a == 5000 else off                 # pico aislado (artefacto)
        pts.append({'abscisa_val': a, 'on_mv': crudo - 300, 'off_mv': crudo,
                    'on_limpio': off - 300, 'off_limpio': off})
    return pts


def _dcvg():
    postes = [{'tipo': 'Poste de Potencial', 'pk_m': 0, 'on': -1200, 'off': -1000},
              {'tipo': 'Poste de Potencial', 'pk_m': 5000, 'on': -1100, 'off': -900},
              {'tipo': 'Poste abscisado', 'pk_m': 7500, 'on': None, 'off': None},
              {'tipo': 'Poste de Potencial', 'pk_m': 10000, 'on': -1000, 'off': -800}]
    # pulso = 200 en todos los postes con lectura → P/RE = 200
    defectos = [{'pk_m': 1000, 'ol_re': 20, 'caracter': 'CC'},     # 10 %  Muy Pequeño
                {'pk_m': 2500, 'ol_re': 100, 'caracter': 'CA'},    # 50 %  Mediano
                {'pk_m': 7000, 'ol_re': 150, 'caracter': 'AA'}]    # 75 %  Grande
    resist = [{'pk_m': 1000, 'r1': 0.5, 'r2': 0.4, 'r3': 0.3},     # ρ1 = 314 → Muy Corrosivo
              {'pk_m': 6000, 'r1': 5.0, 'r2': 4.0, 'r3': 3.0}]     # ρ1 = 3142 → Medianamente
    hallazgos = [{'tipo': 'Cruce de vía', 'abscisa_val': 1200},
                 {'tipo': 'Válvula', 'abscisa_val': 4000}]
    return {'postes': postes, 'defectos': defectos, 'resist': resist,
            'hallazgos': hallazgos}


def _texto(lista):
    return "\n".join(lista)


# ── PAP: el comportamiento de siempre ────────────────────────────────────────

def test_pap_sigue_igual():
    cg = ConclusionGenerator(_pap(), [], [], [], ACTIVAS, dict(INFO, tipo_inspeccion='PAP'))
    c = cg.generar_conclusiones()
    assert 'Inspección PAP' in c[0] and '80%' in c[0]
    assert any('estaciones de prueba' in x for x in c)


def test_sin_tipo_asume_pap():
    cg = ConclusionGenerator(_pap(), [], [], [], ACTIVAS, dict(INFO))
    assert 'Inspección PAP' in cg.generar_conclusiones()[0]


# ── DCVG ─────────────────────────────────────────────────────────────────────

def test_dcvg_no_habla_de_pap_aunque_queden_potenciales_en_la_sesion():
    d = _dcvg()
    cg = ConclusionGenerator(_pap(), d['hallazgos'], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='DCVG'), dcvg=d)
    conc = _texto(cg.generar_conclusiones())
    reco = _texto(cg.generar_recomendaciones())
    for prohibido in ('PAP', 'estaciones de prueba', 'pintura', 'mantenimiento tipo'):
        assert prohibido not in conc and prohibido not in reco, prohibido
    assert 'DCVG' in conc


def test_dcvg_cuenta_y_clasifica_los_defectos():
    d = _dcvg()
    cg = ConclusionGenerator([], d['hallazgos'], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='DCVG'), dcvg=d)
    conc = _texto(cg.generar_conclusiones())
    assert '3 indicaciones' in conc or '3 defectos' in conc
    assert 'Grande' in conc and 'K 007+000' in conc
    assert 'Mediano' in conc and 'K 002+500' in conc
    assert 'Muy Pequeño' in conc or 'menor o igual a 15%' in conc
    assert 'indicaciones/km' in conc                 # densidad, como los históricos
    # carácter de las indicaciones con la notación de los históricos
    assert 'A-A' in conc and 'C-A' in conc and 'C-C' in conc


def test_dcvg_potenciales_de_postes_y_resistividad():
    d = _dcvg()
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='DCVG'), dcvg=d)
    conc = _texto(cg.generar_conclusiones())
    # 2 de 3 postes con lectura cumplen -850 → 67 %
    assert '67%' in conc
    assert 'Muy Corrosivo' in conc and 'Medianamente Corrosivo' in conc
    assert '1, 2 y 3 m' in conc


def test_dcvg_recomienda_atender_los_defectos_grandes_y_medianos():
    d = _dcvg()
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='DCVG'), dcvg=d)
    reco = _texto(cg.generar_recomendaciones())
    assert 'K 007+000' in reco and 'K 002+500' in reco
    assert 'K 001+000' not in reco          # el Muy Pequeño no se excava


def test_dcvg_sin_defectos_no_falla():
    d = _dcvg()
    d['defectos'] = []
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='DCVG'), dcvg=d)
    conc = _texto(cg.generar_conclusiones())
    assert 'no se identificaron indicaciones' in conc.lower() or 'sin indicaciones' in conc.lower()


# ── CIPS ─────────────────────────────────────────────────────────────────────

def test_cips_usa_el_potencial_suavizado_y_no_habla_de_pap():
    cg = ConclusionGenerator(_pap(), [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    conc = _texto(cg.generar_conclusiones())
    assert 'CIPS' in conc
    assert 'Inspección PAP' not in conc          # los postes cargados aportan, pero no es un PAP
    assert 'técnica de Inspección CIPS' in cg.generar_conclusiones()[0]
    assert 'longitud de 9.9 km' in conc and 'ISO 15589-1' in conc
    # 94 de 100 puntos cumplen (con el crudo, por el pico, serían 93)
    assert '94%' in conc and '93%' not in conc


def test_cips_senala_la_zona_desprotegida():
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    conc = _texto(cg.generar_conclusiones())
    assert 'K 002+000' in conc and 'K 002+500' in conc


def test_cips_con_urpc():
    cg = ConclusionGenerator([], [], [{'nombre': 'URPC Palmira'}], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    assert 'URPC Palmira' in _texto(cg.generar_conclusiones())


def test_cips_sin_datos_no_falla():
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=[])
    assert cg.generar_conclusiones() and cg.generar_recomendaciones()


# ── CIPS + postes de la misma campaña (así vienen los informes históricos) ───
# El informe histórico CIPS (plantilla, Ramal Pradera) trae además de las del
# perfil: VAC, estaciones de prueba, pintura y mantenimiento por tipo. Entran
# SOLO si en el trabajo se cargaron los postes.

def test_cips_con_postes_cargados_incluye_estaciones_y_mantenimiento():
    pots = _pap()
    pots[1]['pintura'] = 'Regular'
    pots[1]['tipo_mant'] = 'I'
    cg = ConclusionGenerator(pots, [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    conc = _texto(cg.generar_conclusiones())
    reco = _texto(cg.generar_recomendaciones())
    assert 'CIPS' in conc and '94%' in conc                 # el perfil manda primero
    assert 'estaciones de prueba' in conc and 'pintura' in conc
    assert 'mantenimiento tipo I' in reco
    assert 'Inspección PAP' not in conc                      # pero no se vende como PAP


def test_cips_sin_postes_no_habla_de_estaciones():
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    assert 'estaciones de prueba' not in _texto(cg.generar_conclusiones())


def test_cips_lista_los_picos_puntuales_corregidos():
    """El pico aislado del crudo (K 005+000) se reporta como caída puntual a
    contrastar con el DCVG, como hacen los históricos."""
    cg = ConclusionGenerator([], [], [], [], ACTIVAS,
                             dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    conc = _texto(cg.generar_conclusiones())
    assert 'K 005+000' in conc and 'picos puntuales' in conc


def test_pap_cita_iso_15589_y_el_rango():
    cg = ConclusionGenerator(_pap(), [], [], [], ACTIVAS, dict(INFO, tipo_inspeccion='PAP'))
    conc = _texto(cg.generar_conclusiones())
    assert 'ISO 15589-1' in conc and 'entre el K 000+000 y el K 009+000' in conc


def test_aislamientos_entran_en_pap_y_cips():
    aisl = [{'abscisado': 'K 001+000', 'diagnostico': 'Aislado'},
            {'abscisado': 'K 005+000', 'diagnostico': 'No aislado'}]
    cg = ConclusionGenerator(_pap(), [], [], aisl, ACTIVAS, dict(INFO, tipo_inspeccion='PAP'))
    conc = _texto(cg.generar_conclusiones())
    assert '2 junta(s)/brida(s) de aislamiento' in conc and 'K 005+000' in conc
    cg = ConclusionGenerator([], [], [], aisl, ACTIVAS, dict(INFO, tipo_inspeccion='CIPS'), cips=_cips())
    assert 'aislamiento' in _texto(cg.generar_conclusiones())

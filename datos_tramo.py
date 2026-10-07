"""Datos de Datos Generales que se derivan del nombre del tramo.

Un mismo tramo se escribe distinto en cada fuente:

  FastField              'Ramal Ansermanuevo'
  Infraestrutura TGI     'Ansermanuevo'
  consolidado OT         'Salento  PK 15+921'   (a veces con distrito: 'D07')

Por eso la comparación pasa siempre por `nombres.mismo_tramo`, que ignora el
'Ramal'/'Troncal' del principio y el 'PK …'/distrito del final, y compara por
palabras completas (para no confundir *Buga* con *Bugalagrande*).

Dos fuentes de OT:
  · `consolidado OT.xlsx` — una OT por subsistema, la del plan de medición de
    potenciales (INT-CE M.POT). Trae además distrito y longitud.
  · `ot_por_tipo.csv` — las OT de los demás planes (p. ej. TINT-DCVG). Manda
    sobre la anterior cuando el tipo de inspección coincide, porque para un
    DCVG la OT de potenciales es la equivocada.
"""
import csv
import os

from generator import resource_path
from nombres import mismo_tramo

ARCHIVO_INFRA = 'Infraestrutura TGI.xlsx'
ARCHIVO_OT = 'consolidado OT.xlsx'
ARCHIVO_OT_TIPO = 'ot_por_tipo.csv'
ARCHIVO_RECUBRIMIENTO = 'recubrimiento_por_tramo.csv'

#: Valores de la columna Recubrimiento de `Infraestrutura TGI.xlsx` que NO son
#: un recubrimiento: los 39 ramales de Mariquita-Cali (los que inspecciona PCC)
#: traen 'En validación' y salía tal cual en el informe.
_SIN_RECUBRIMIENTO = ('', 'nan', 'none', 'recubrimiento', 'en validacion', 'n/a', 'na', '-')

#: Número del contrato PCC Integrity ↔ TGI. Va en la carátula del informe y en
#: el nombre del archivo/ZIP. El FastField trae 'Cliente' (= 'TGI'), que NO es
#: el contrato: por eso se autollena desde aquí para todo tramo de TGI.
CONTRATO_TGI = '551007370'

#: Qué fila del consolidado corresponde a cada tipo de inspección. La columna
#: 'Texto breve operación' (o la 'Descripción posición de mantenimiento') dice
#: de qué plan es la OT; el consolidado trae hasta tres por tramo.
_PLAN_POR_TIPO = {
    'PAP': ('URPC-PAP', 'INT-CE PAP'),
    'CIPS': ('CIPS',),
    'DCVG': ('DCVG', 'INT-CE REV'),
}
#: Filas del consolidado que no son inspecciones de potenciales/recubrimiento.
_PLANES_AJENOS = ('CUPON', 'ANODOS', 'ÁNODOS', 'CALIBRACION', 'CALIBRACIÓN', 'CAJAS')

_cache = {}


def _texto(v):
    import pandas as pd
    return '' if v is None or pd.isna(v) else str(v).strip()


def _tabla(archivo, **kw):
    """Lee un Excel de datos una sola vez por ejecución."""
    if archivo not in _cache:
        import pandas as pd
        ruta = resource_path(archivo)
        try:
            _cache[archivo] = pd.read_excel(ruta, **kw) if os.path.exists(ruta) else None
        except Exception:
            _cache[archivo] = None
    return _cache[archivo]


def info_de_infraestructura(tramo):
    """{gasoducto, diametro, tipo_recubrimiento, tipo_ducto} del tramo."""
    df = _tabla(ARCHIVO_INFRA, header=1)
    if df is None or 'TRAMOS' not in getattr(df, 'columns', []):
        return {}
    import pandas as pd
    df = df.copy()
    if 'GASODUCTO.1' in df.columns:
        df['GASODUCTO.1'] = df['GASODUCTO.1'].ffill()
    df = df.dropna(subset=['TRAMOS'])
    filas = [r for _i, r in df.iterrows() if mismo_tramo(tramo, r['TRAMOS'])]
    if not filas:
        return {}
    # ante varias: primero la línea principal (un LOOP es otra línea) y, a
    # igualdad, la de nombre más parecido
    def _prioridad(r):
        es_loop = 'loop' in _texto(r.get('Tipo')).lower()
        return (es_loop, abs(len(str(r['TRAMOS'])) - len(str(tramo))))
    fila = min(filas, key=_prioridad)
    out = {}
    gas = _texto(fila.get('GASODUCTO.1')) or _texto(fila.get('GASODUCTO'))
    if gas:
        out['gasoducto'] = gas
    if 'Tipo' in fila and _texto(fila['Tipo']):
        out['tipo_ducto'] = _texto(fila['Tipo'])
    rec = recubrimiento_de(tramo, fila.get('Recubrimiento') if 'Recubrimiento' in fila else None)
    if rec:
        out['tipo_recubrimiento'] = rec
    diam = next((c for c in df.columns
                 if 'pulg' in str(c).lower() or ('Di' in str(c) and 'metro' in str(c))), None)
    if diam and _texto(fila[diam]):
        out['diametro'] = _texto(fila[diam])
    return out


def _norm(v):
    """Texto comparable: sin tildes, minúsculas, sin espacios de más."""
    import unicodedata
    t = ''.join(c for c in unicodedata.normalize('NFD', _texto(v)) if unicodedata.category(c) != 'Mn')
    return ' '.join(t.lower().split())


def _recubrimiento_por_tramo():
    """Filas de `recubrimiento_por_tramo.csv`: el recubrimiento real de los
    tramos que la tabla de infraestructura tiene 'En validación'. Las filas con
    recubrimiento vacío son solo la lista de pendientes y no cuentan."""
    if 'recubrimiento' not in _cache:
        filas = {}
        ruta = resource_path(ARCHIVO_RECUBRIMIENTO)
        try:
            with open(ruta, encoding='utf-8') as f:
                lineas = [ln for ln in f if not ln.lstrip().startswith('#')]
            for r in csv.DictReader(lineas):
                tramo = (r.get('tramo') or '').strip()
                rec = (r.get('recubrimiento') or '').strip()
                if tramo and rec and _norm(rec) not in _SIN_RECUBRIMIENTO:
                    filas[tramo] = rec
        except Exception:
            filas = {}
        _cache['recubrimiento'] = filas
    return _cache['recubrimiento']


def recubrimiento_de(tramo, valor_tabla=None):
    """Recubrimiento del tramo: primero el CSV de correcciones; si no, el de
    la tabla de infraestructura salvo que sea un marcador ('En validación')."""
    for t, rec in _recubrimiento_por_tramo().items():
        if mismo_tramo(tramo, t):
            return rec
    if _norm(valor_tabla) in _SIN_RECUBRIMIENTO:
        return None
    return _texto(valor_tabla)


def _ot_por_tipo():
    """Filas de `ot_por_tipo.csv` (las OT de los planes que no están en el
    consolidado)."""
    if 'ot_tipo' not in _cache:
        filas = []
        ruta = resource_path(ARCHIVO_OT_TIPO)
        try:
            with open(ruta, encoding='utf-8') as f:
                lineas = [ln for ln in f if not ln.lstrip().startswith('#')]
            for r in csv.DictReader(lineas):
                if (r.get('tramo') or '').strip() and (r.get('ot') or '').strip():
                    filas.append({k: (v or '').strip() for k, v in r.items()})
        except Exception:
            filas = []
        _cache['ot_tipo'] = filas
    return _cache['ot_tipo']


def _plan_de(fila):
    """Texto que identifica el plan de una fila del consolidado."""
    return (_texto(fila.get('Texto breve operación')) + ' '
            + _texto(fila.get('Descripción posición de mantenimiento'))).upper()


def _rango_fila(fila, tipo):
    """Qué tan apropiada es una fila del consolidado para el tipo de inspección
    (menor = mejor). 0: es la fila del plan del tipo · 1: fila sin descripción
    de plan (el bloque de inspecciones sin texto) · 2: otro plan de inspección
    · 3: cupones/ánodos/calibración (nunca una inspección)."""
    plan = _plan_de(fila)
    if any(p in plan for p in _PLANES_AJENOS):
        return 3
    if not plan.strip():
        return 1
    if tipo and any(p in plan for p in _PLAN_POR_TIPO.get(tipo, ())):
        return 0
    return 2


def info_de_ot(tramo, tipo=None):
    """{ot, distrito, longitud_km} del tramo, según el TIPO de inspección.

    El consolidado trae hasta tres filas por tramo (plan PAP, plan CIPS, plan
    DCVG) más cupones/ánodos/calibración: se toma la fila del plan del tipo
    pedido; sin ella, la fila sin descripción; nunca la de cupones si hay otra.
    """
    out = {}
    t = (tipo or '').strip().upper()
    df = _tabla(ARCHIVO_OT)
    if df is not None and 'SUBSISTEMA' in getattr(df, 'columns', []):
        filas = [r for _i, r in df.dropna(subset=['SUBSISTEMA']).iterrows()
                 if mismo_tramo(tramo, r['SUBSISTEMA'])]
        if filas:
            fila = min(filas, key=lambda r: _rango_fila(r, t))
            if 'Orden' in fila and _texto(fila['Orden']):
                try:
                    out['ot'] = str(int(float(fila['Orden'])))
                except (TypeError, ValueError):
                    out['ot'] = _texto(fila['Orden'])
            if 'Distrito' in fila and _texto(fila['Distrito']):
                out['distrito'] = _texto(fila['Distrito'])
            if 'Unidad [Km]' in fila and _texto(fila['Unidad [Km]']):
                try:
                    out['longitud_km'] = float(fila['Unidad [Km]'])
                except (TypeError, ValueError):
                    pass

    # la OT del plan propio del tipo de inspección manda sobre la del consolidado
    candidatas = [f for f in _ot_por_tipo() if mismo_tramo(tramo, f['tramo'])]
    propia = next((f for f in candidatas if f.get('tipo', '').upper() == t and t), None)
    if propia is None and not out.get('ot'):
        # sin OT del consolidado, sirve cualquier fila del tramo
        propia = next((f for f in candidatas if not f.get('tipo')), None) \
            or (candidatas[0] if candidatas else None)
    if propia:
        out['ot'] = propia['ot']
        if propia.get('distrito'):
            out['distrito'] = propia['distrito']
    return out


def autollenar(tramo, tipo=None):
    """Todo lo derivable del tramo, en un solo dict."""
    d = info_de_infraestructura(tramo)
    d.update(info_de_ot(tramo, tipo))
    if d:
        # el tramo está en las tablas de TGI → el contrato es el de TGI
        d['contrato'] = CONTRATO_TGI
    return d


def filtrar_autollenado(cambios, manuales, forzar=False):
    """Qué parte de un autollenado se puede aplicar sin pisar lo que el usuario
    escribió a mano en Datos Generales (p. ej. una OT corregida).

    `manuales` es el conjunto de campos editados a mano. Devuelve
    (cambios_aplicables, manuales_actualizados). Con `forzar` (el botón
    "Autollenar desde el tramo", reabrir un rechazo) los campos del autollenado
    vuelven a ser automáticos y se aplican todos.
    """
    manuales = set(manuales or ())
    cambios = dict(cambios or {})
    if forzar:
        manuales -= set(cambios)
    return {k: v for k, v in cambios.items() if k not in manuales}, manuales

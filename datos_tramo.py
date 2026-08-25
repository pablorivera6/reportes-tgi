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
    for col, clave in (('Tipo', 'tipo_ducto'), ('Recubrimiento', 'tipo_recubrimiento')):
        if col in fila and _texto(fila[col]):
            out[clave] = _texto(fila[col])
    diam = next((c for c in df.columns
                 if 'pulg' in str(c).lower() or ('Di' in str(c) and 'metro' in str(c))), None)
    if diam and _texto(fila[diam]):
        out['diametro'] = _texto(fila[diam])
    return out


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


def info_de_ot(tramo, tipo=None):
    """{ot, distrito, longitud_km} del tramo, según el TIPO de inspección."""
    out = {}
    df = _tabla(ARCHIVO_OT)
    if df is not None and 'SUBSISTEMA' in getattr(df, 'columns', []):
        filas = [r for _i, r in df.dropna(subset=['SUBSISTEMA']).iterrows()
                 if mismo_tramo(tramo, r['SUBSISTEMA'])]
        if filas:
            fila = filas[0]
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
    t = (tipo or '').strip().upper()
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
    return d

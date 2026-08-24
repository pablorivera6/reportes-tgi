"""Lectura de informes históricos para la comparativa del portal.

Un "histórico" es un informe de una inspección anterior del mismo tramo (de
PCC o de otro contratista). Como todos vienen en la plantilla del contrato, se
leen por encabezado y no por posición fija:

  - cabecera (col A = etiqueta, col C = valor): Fecha, Gasoducto, Tramo, Inspector
  - tabla de potenciales: ABSCISADO, ON [mV], OFF [mV], latitud/longitud

El resultado se guarda como **CSV liviano** (unas decenas de KB por tramo, en
vez de los ~2 MB del .xlsx) y se publica en Supabase, que es de donde el
dashboard y su PDF leen la comparación. Los CSV son la copia auditable local:
NO se suben al repo (es público).

Uso desde el cargador: `cargar_historico.py <informe.xlsx>`.
"""
import csv
import datetime
import os
import re
import unicodedata

import openpyxl

MESES = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep',
         'Oct', 'Nov', 'Dic']

# Hoja de datos según el tipo de inspección
HOJAS = (('Potenciales CIPS', 'CIPS'), ('Potenciales PAP', 'PAP'))

CAMPOS_CSV = ('abscisa', 'on', 'off', 'lat', 'lon', 'fecha')


def _txt(v):
    t = ''.join(c for c in unicodedata.normalize('NFD', str(v or ''))
                if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', t).strip().lower()


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def periodo_legible(fecha):
    """'30/11/2023 AL 01/12/2023' -> 'Nov 2023'. '' si no se entiende."""
    if isinstance(fecha, (datetime.datetime, datetime.date)):
        return f"{MESES[fecha.month]} {fecha.year}"
    txt = str(fecha or '').strip()
    if not txt:
        return ''
    # OJO: primero el formato ISO; si no, '2024-03-12' entra por la regla
    # dd/mm/aaaa leyendo '24-03-12' y devuelve el año equivocado.
    m = re.search(r'\b(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})\b', txt)
    if m:                                   # aaaa-mm-dd
        a, mes = int(m.group(1)), int(m.group(2))
        if 1 <= mes <= 12:
            return f"{MESES[mes]} {a}"
    m = re.search(r'\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b', txt)
    if m:                                   # dd/mm/aaaa
        mes, a = int(m.group(2)), int(m.group(3))
        a = a + 2000 if a < 100 else a
        if 1 <= mes <= 12:
            return f"{MESES[mes]} {a}"
    return ''


def datos_del_nombre(nombre):
    """Lo que se puede deducir del nombre codificado del archivo:
    CIPS_REP_R_DOR_11_23_1300006811_551003090_TEL_Rev0.xlsx"""
    partes = os.path.splitext(os.path.basename(nombre))[0].split('_')
    out = {}
    if partes:
        out['tipo'] = partes[0].upper()
    m = re.match(r'^[A-Z]+_(?:REP|PPM)_([RTLA])_([A-Z0-9]+)_(\d{2})_(\d{2})_'
                 r'(\d+)_(\d+)_', os.path.basename(nombre).upper())
    if m:
        out['letra'], out['sigla'] = m.group(1), m.group(2)
        mes, anio = int(m.group(3)), int(m.group(4))
        if 1 <= mes <= 12:
            out['periodo'] = f"{MESES[mes]} {2000 + anio}"
        out['ot'], out['contrato'] = m.group(5), m.group(6)
    return out


def _cabecera(ws):
    """{etiqueta_normalizada: valor} de las filas 5-9 (col A = etiqueta,
    col C = valor; col K/S = etiquetas de las otras dos columnas)."""
    out = {}
    for r in range(4, 10):
        for c_et, c_val in ((1, 3), (11, 13), (19, 21)):
            et = _txt(ws.cell(row=r, column=c_et).value)
            val = ws.cell(row=r, column=c_val).value
            if et and val not in (None, ''):
                out[et] = val
    return out


def _fila_encabezado_tabla(ws, hasta=20):
    """Fila donde está 'ABSCISADO' (los datos empiezan 2 filas después)."""
    for r in range(1, hasta + 1):
        for c in range(1, 6):
            if _txt(ws.cell(row=r, column=c).value).startswith('abscisado'):
                return r
    return 10


def _cols_potencial(ws, fila_enc):
    """Columnas de ON y OFF del bloque 'POTENCIAL NEGATIVO 1' (el medido),
    leídas de la fila de subencabezados."""
    ini = None
    for c in range(1, 40):
        if 'potencial negativo 1' in _txt(ws.cell(row=fila_enc, column=c).value):
            ini = c
            break
    if ini is None:
        return (5, 6)                      # respaldo: E/F
    on = off = None
    for c in range(ini, min(ini + 6, 40)):
        sub = _txt(ws.cell(row=fila_enc + 1, column=c).value)
        if sub.startswith('on') and on is None:
            on = c
        elif sub.startswith('off') and off is None:
            off = c
    return (on or ini, off or (ini + 1))


def leer_historico(ruta):
    """Lee un informe de inspección anterior. Devuelve
    {tramo, tipo, periodo, fecha, gasoducto, contratista, inspector, fuente,
     puntos: [{abscisa, on, off, lat, lon, fecha}], resumen}"""
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    hoja = tipo = None
    for nombre, t in HOJAS:
        if nombre in wb.sheetnames:
            hoja, tipo = nombre, t
            break
    if hoja is None:
        wb.close()
        raise ValueError(f"{os.path.basename(ruta)}: no tiene hoja de potenciales "
                         f"(se esperaba 'Potenciales CIPS' o 'Potenciales PAP')")
    ws = wb[hoja]
    cab = _cabecera(ws)

    def g(*etiquetas):
        for e in etiquetas:
            for k, v in cab.items():
                if k.startswith(_txt(e)):
                    return v
        return ''

    fila_enc = _fila_encabezado_tabla(ws)
    c_on, c_off = _cols_potencial(ws, fila_enc)
    puntos = []
    for fila in ws.iter_rows(min_row=fila_enc + 2, values_only=True):
        def v(col):
            return fila[col - 1] if col - 1 < len(fila) else None
        # el bloque de firmas cierra la tabla
        if any(_txt(x).startswith(('elaboro', 'reviso', 'aprobo')) for x in fila
               if isinstance(x, str)):
            break
        absc, on, off = _num(v(2)), _num(v(c_on)), _num(v(c_off))
        if absc is None or off is None:
            continue
        fecha_pt = v(3)
        puntos.append({
            'abscisa': absc, 'on': on, 'off': off,
            'lat': _num(v(19)), 'lon': _num(v(20)),
            'fecha': fecha_pt.strftime('%Y-%m-%d')
                     if isinstance(fecha_pt, (datetime.datetime, datetime.date))
                     else (str(fecha_pt).split()[0] if fecha_pt else '')})
    wb.close()

    fecha = g('fecha')
    del_nombre = datos_del_nombre(ruta)
    hist = {
        'tramo': str(g('tramo') or '').strip(),
        'tipo': tipo,
        'periodo': periodo_legible(fecha) or del_nombre.get('periodo', ''),
        'fecha': str(fecha or '').strip(),
        'gasoducto': str(g('gasoducto') or '').strip(),
        'contratista': str(g('contratista') or '').strip(),
        'inspector': str(g('inspector') or '').strip(),
        'fuente': os.path.basename(ruta),
        'puntos': puntos,
    }
    hist['resumen'] = resumen(puntos)
    return hist


def resumen(puntos):
    """Indicadores del histórico (mismo criterio que el portal: OFF ≤ -850 mV)."""
    offs = [p['off'] for p in puntos if isinstance(p.get('off'), (int, float))]
    if not offs:
        return {'n': 0, 'fuera': None, 'pct_prot': None, 'prom_off': None,
                'min_off': None, 'max_off': None}
    fuera = sum(1 for o in offs if o > -850)
    return {'n': len(offs), 'fuera': fuera,
            'pct_prot': round(100 * (len(offs) - fuera) / len(offs), 2),
            'prom_off': round(sum(offs) / len(offs), 1),
            'min_off': round(min(offs), 1), 'max_off': round(max(offs), 1)}


# ── CSV liviano ──────────────────────────────────────────────────────────────

def a_csv(hist, ruta):
    """Guarda el histórico como CSV: una cabecera comentada con los metadatos
    y una fila por punto."""
    with open(ruta, 'w', newline='', encoding='utf-8') as f:
        for k in ('tramo', 'tipo', 'periodo', 'fecha', 'gasoducto',
                  'contratista', 'fuente'):
            f.write(f"# {k}: {hist.get(k, '')}\n")
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV, extrasaction='ignore')
        w.writeheader()
        w.writerows(hist['puntos'])
    return ruta


def desde_csv(ruta):
    """Reconstruye el histórico desde el CSV generado por `a_csv`."""
    meta, filas = {}, []
    with open(ruta, encoding='utf-8') as f:
        lineas = f.readlines()
    datos = []
    for ln in lineas:
        if ln.startswith('#'):
            k, _, v = ln[1:].partition(':')
            meta[k.strip()] = v.strip()
        else:
            datos.append(ln)
    for fila in csv.DictReader(datos):
        filas.append({'abscisa': _num(fila.get('abscisa')),
                      'on': _num(fila.get('on')), 'off': _num(fila.get('off')),
                      'lat': _num(fila.get('lat')), 'lon': _num(fila.get('lon')),
                      'fecha': fila.get('fecha', '')})
    meta['puntos'] = filas
    meta['resumen'] = resumen(filas)
    return meta

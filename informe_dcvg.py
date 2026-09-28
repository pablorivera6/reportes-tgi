"""Lee un informe DCVG **ya generado** (.xlsx) y lo devuelve en la forma que
produce el generador, para poder publicarlo al portal.

Un informe hecho antes del portal —o fuera de la app— solo existe como Excel.
Este lector lo traduce a los mismos dicts que salen de `dcvg_reader`
(`pk_m`, `on`, `ol_re`, `forma_n`…), que son los que espera
`db.guardar_inspeccion_dcvg`. Así publicarlo recorre exactamente el mismo
camino que una inspección recién procesada: en particular, la severidad la
vuelve a calcular `db._severidad_dcvg` a partir de OL/RE y de los pulsos de los
postes, en vez de copiar el número del Excel.

Las hojas se leen **por etiqueta de encabezado**, nunca por posición fija: la
plantilla de PCC parte el %IR en tres columnas (AA/CA/CC) y la del contratista
lo pone en una sola, y las filas de datos empiezan en distinta altura según la
hoja. Se reutiliza el mapeo de `historicos`, que ya resuelve ambas plantillas.

**Sí lee la severidad del Excel** (P/RE, %IR y clasificación). En una
inspección recién procesada esos tres son derivados y los calcula
`db._severidad_dcvg`; pero un informe ya entregado al cliente es el documento
oficial, y sus fórmulas anclan la interpolación de P/RE en los postes que se
eligieron al generarlo — no siempre los más cercanos. Recalcularlos haría que
el portal mostrara números distintos a los del PDF que TGI ya tiene. Quien
publique decide cuál usar con `db.guardar_inspeccion_dcvg(..., severidades=)`.
"""
import os

import openpyxl

from historicos import (_fila_encabezado_dcvg, _mapa_columnas_dcvg,
                        _meta_informe, _num, _txt)

HOJA_DCVG = 'Inspección DCVG'
HOJA_RESIST = 'Resistividad'
HOJA_HALLAZGOS = 'Hallazgos'

# Forma [mV]: las cuatro lecturas van por hora del reloj (N=12, E=3, S=6, O=9)
# y en la plantilla ocupan cuatro columnas seguidas bajo 'FORMA'.
_FORMA = ('forma_n', 'forma_e', 'forma_s', 'forma_o')


def _info(wb):
    """Datos generales, de la hoja 'Informe'."""
    meta = _meta_informe(wb)

    def g(*etiquetas):
        for e in etiquetas:                       # exacta primero
            if _txt(e) in meta:
                return meta[_txt(e)]
        for e in etiquetas:                       # si no, por prefijo
            for k, v in meta.items():
                if k.startswith(_txt(e)):
                    return v
        return ''

    def s(*etiquetas):
        v = g(*etiquetas)
        return str(v).strip() if v not in (None, '') else ''

    return {
        'tramo': s('tramo'), 'gasoducto': s('gasoducto'),
        'fecha': s('fecha'), 'inspector': s('inspector'),
        'ot': s('ot', 'no de ot'), 'contrato': s('no de contrato', 'contrato'),
        'contratista': s('contratista'),
        'serial_equipo': s('serial equipo'),
        'fecha_calibracion': s('fecha calibracion eqp', 'fecha calibracion'),
        'tipo_recubrimiento': s('tipo de recubrimiento'),
        'diametro': s('diametro'), 'ciclo': s('ciclo'),
        'tipo_inspeccion': 'DCVG',
    }


def _postes_y_defectos(wb):
    """De la hoja 'Inspección DCVG'.

    La hoja lleva postes, defectos y hallazgos **intercalados por abscisa** (es
    la secuencia del recorrido). Los hallazgos tienen su propia hoja, así que
    aquí se descartan: se queda con las filas que son defecto (referencia
    'Defecto') o poste (las que traen ON/OFF).
    """
    ws = wb[HOJA_DCVG]
    fila_enc = _fila_encabezado_dcvg(ws)
    mapa = _mapa_columnas_dcvg(ws, fila_enc)

    def celda(fila, campo, numerico=False):
        rango = mapa.get(campo)
        if not rango:
            return None
        for c in range(rango[0], rango[1] + 1):
            v = fila[c - 1] if c - 1 < len(fila) else None
            if v in (None, ''):
                continue
            return _num(v) if numerico else v
        return None

    postes, defectos = [], []
    ini_forma = (mapa.get('forma') or (0, -1))[0]
    for fila in ws.iter_rows(min_row=fila_enc + 2, values_only=True):
        if any(_txt(x).startswith(('elaboro', 'reviso', 'aprobo')) for x in fila
               if isinstance(x, str)):
            break
        absc = celda(fila, 'abscisa', True)
        if absc is None:
            continue
        referencia = str(celda(fila, 'referencia') or '').strip()
        on, off = celda(fila, 'on', True), celda(fila, 'off', True)
        comun = {'pk_m': absc, 'lat': celda(fila, 'lat', True),
                 'lon': celda(fila, 'lon', True)}
        if 'defecto' in _txt(referencia):
            # El %IR del informe viene en FRACCIÓN (0,1245) y el portal usa
            # porcentaje (12,45). Mismo criterio que en `historicos`.
            sev = celda(fila, 'severidad', True)
            pct = round(sev * 100, 2) if sev is not None and sev <= 1.5 else sev
            d = dict(comun,
                     caracter=str(celda(fila, 'caracter') or '').strip().upper(),
                     ol_re=celda(fila, 'ol_re', True),
                     profundidad=celda(fila, 'profundidad', True),
                     p_re=celda(fila, 'p_re', True),
                     severidad_pct=pct,
                     clasificacion=str(celda(fila, 'clasificacion') or '').strip(),
                     comentarios=str(celda(fila, 'observaciones') or '').strip())
            for i, k in enumerate(_FORMA):
                v = fila[ini_forma - 1 + i] if ini_forma else None
                d[k] = _num(v)
            defectos.append(d)
        elif on is not None or off is not None:
            postes.append(dict(comun, tipo=referencia, on=on, off=off,
                               vac=celda(fila, 'vac', True)))
    return postes, defectos


def _fila_con(ws, etiqueta, col=1, hasta=20):
    """Fila cuyo texto en `col` empieza por `etiqueta` (encabezado de tabla)."""
    for r in range(1, hasta + 1):
        if _txt(ws.cell(row=r, column=col).value).startswith(_txt(etiqueta)):
            return r
    return None


def _resistividades(wb):
    """Hoja 'Resistividad': A abscisa · B sector · C/D coords · E profundidad ·
    F/H/J resistencia a 1/2/3 m (G/I/K son las etiquetas '1 m', '2 m', '3 m')."""
    if HOJA_RESIST not in wb.sheetnames:
        return []
    ws = wb[HOJA_RESIST]
    enc = _fila_con(ws, 'abscisado')
    if enc is None:
        return []
    out = []
    for fila in ws.iter_rows(min_row=enc + 2, values_only=True):
        if any(_txt(x).startswith(('elaboro', 'reviso', 'aprobo')) for x in fila
               if isinstance(x, str)):
            break
        absc = _num(fila[0] if fila else None)
        if absc is None:
            continue
        def v(i):
            return _num(fila[i]) if i < len(fila) else None
        out.append({'pk_m': absc,
                    'sector': str(fila[1] or '').strip() if len(fila) > 1 else '',
                    'lat': v(2), 'lon': v(3), 'profundidad': v(4),
                    'r1': v(5), 'r2': v(7), 'r3': v(9)})
    return out


def _hallazgos(wb):
    """Hoja 'Hallazgos': encabezado en la fila del 'ÍTEM', datos justo debajo."""
    if HOJA_HALLAZGOS not in wb.sheetnames:
        return []
    ws = wb[HOJA_HALLAZGOS]
    enc = _fila_con(ws, 'item', hasta=25)
    if enc is None:
        return []
    out = []
    for fila in ws.iter_rows(min_row=enc + 1, values_only=True):
        if any(_txt(x).startswith(('elaboro', 'reviso', 'aprobo')) for x in fila
               if isinstance(x, str)):
            break
        def v(i):
            return fila[i] if i < len(fila) else None
        ini = _num(v(1))
        tipo = str(v(11) or '').strip()
        if ini is None and not tipo:
            continue
        out.append({'abscisa_inicio': ini, 'abscisa_fin': _num(v(2)),
                    'longitud': _num(v(3)),
                    'lat_inicio': _num(v(6)), 'lon_inicio': _num(v(7)),
                    'lat_fin': _num(v(8)), 'lon_fin': _num(v(9)),
                    'fecha': v(10), 'tipo': tipo,
                    'descripcion': str(v(12) or '').strip()})
    return out


def leer_informe_dcvg(ruta):
    """{info, postes, defectos, resistividades, hallazgos, fuente}."""
    wb = openpyxl.load_workbook(ruta, data_only=True)
    if HOJA_DCVG not in wb.sheetnames:
        wb.close()
        raise ValueError(f"{os.path.basename(ruta)}: no tiene la hoja "
                         f"'{HOJA_DCVG}' (¿es un informe DCVG?)")
    postes, defectos = _postes_y_defectos(wb)
    out = {'info': _info(wb), 'postes': postes, 'defectos': defectos,
           'resistividades': _resistividades(wb), 'hallazgos': _hallazgos(wb),
           'fuente': os.path.basename(ruta)}
    wb.close()
    return out


def severidades_del_informe(defectos):
    """Las severidades tal como las trae el informe, en la forma que devuelve
    `db._severidad_dcvg`, para pasarlas a `guardar_inspeccion_dcvg`."""
    return [{'p_re': d.get('p_re'), 'severidad_pct': d.get('severidad_pct'),
             'clasificacion': d.get('clasificacion') or None}
            for d in defectos]

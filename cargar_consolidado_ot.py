"""Convierte el control de OT de TGI (CONTROL_2026_TGI_Consolidado_OT_...xlsx,
hoja 'Consolidado OT') en `consolidado_ot_2026.csv`, la fuente principal de
OT del generador.

Uso:  python3 cargar_consolidado_ot.py <CONTROL_2026_...xlsx>

Solo se exportan las columnas que necesita el informe (tramo, tipo, OT,
distrito, trimestre, estado, mes): el archivo de TGI trae valores y
facturación, y el repositorio es público. Si TGI manda una versión nueva,
basta con volver a correr este script y publicar el CSV."""
import csv
import sys

import openpyxl

HOJA = 'Consolidado OT'
SALIDA = 'consolidado_ot_2026.csv'

#: Nombres de TGI que se escriben distinto en el FastField / Infraestrutura
#: (la comparación es exacta tras normalizar, así que se traducen aquí).
ALIAS = {
    'TEBAIDA': 'La Tebaida',
    'BUGA LA GRANDE': 'Bugalagrande',
    'ARMENIA LOOP': 'Loop - Ramal Armenia',
    'LOOP ARMENIA': 'Loop - Ramal Armenia',
    'PTE GUILLERMO-SUCRE ORIENTAL': 'Puente Guillermo - Sucre Oriental',
    'PTO SALGAR-MARIQUITA': 'Puerto Salgar - Mariquita',
    'TELLO-PINOS NEIVA': 'Tello - Los Pinos',
    'PK 65+900 - APIAY': 'PK 65 - Apiay',
    'APIAY VILLAVICENCIO': 'Apiay - Villavicencio',
    'VILLAVICENCIO USME': 'Villavicencio - Usme',
}


def tipo_de(actividad, grupo):
    a, g = (actividad or '').upper(), (grupo or '').upper()
    if 'CIPS' in a or 'CIPS' in g:
        return 'CIPS'
    if 'DCVG' in a or 'REV' in g:
        return 'DCVG'
    if 'PAP' in a or 'PAP' in g:
        return 'PAP'
    return ''            # calibración de ánodos, etc.: no es una inspección


def _canonico(nombre):
    from nombres import limpiar_tramo
    base = ' '.join(str(nombre or '').split())
    clave = limpiar_tramo(base).upper()
    for k, v in ALIAS.items():
        if limpiar_tramo(k).upper() == clave or base.upper() == k:
            return v
    return base


def filas_de(ruta):
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    ws = wb[HOJA] if HOJA in wb.sheetnames else wb[wb.sheetnames[0]]
    idx = None
    out = []
    for r in ws.iter_rows(values_only=True):
        if idx is None:
            cab = [str(c or '').strip() for c in r]
            if 'OT' in cab and any(c.lower().startswith('nombre') for c in cab):
                idx = {c: i for i, c in enumerate(cab)}
            continue
        def g(*nombres):
            for n in nombres:
                i = next((i for c, i in idx.items() if c.lower().startswith(n.lower())), None)
                if i is not None and i < len(r) and r[i] is not None:
                    return str(r[i]).strip()
            return ''
        ot, nombre = g('OT'), g('Nombre')
        if not ot or not nombre or not ot.replace('.', '').isdigit():
            continue
        tipo = tipo_de(g('Actividad'), g('Grupo'))
        if not tipo:
            continue
        out.append({'tramo': _canonico(nombre), 'tramo_tgi': nombre, 'tipo': tipo,
                    'ot': str(int(float(ot))), 'distrito': g('Distrito'),
                    'trimestre': g('Trimestre'), 'estado': g('Estado'),
                    'mes': g('Mes')})
    return out


def main(ruta, salida=SALIDA):
    filas = filas_de(ruta)
    with open(salida, 'w', newline='', encoding='utf-8') as f:
        f.write("# OT 2026 por tramo y tipo de inspección, generado por\n"
                "# cargar_consolidado_ot.py desde el control de OT de TGI (hoja\n"
                "# 'Consolidado OT'). NO editar a mano: correr el script con el archivo\n"
                "# nuevo. Las OT que haya que forzar van en ot_por_tipo.csv.\n")
        w = csv.DictWriter(f, fieldnames=['tramo', 'tramo_tgi', 'tipo', 'ot', 'distrito',
                                          'trimestre', 'estado', 'mes'])
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} OT escritas en {salida}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], *sys.argv[2:3])

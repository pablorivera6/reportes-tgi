"""Carga de un DCVG en la app: lee los archivos y arma el autollenado de Datos
Generales SIN que un paso secundario tumbe a los demás.

Antes todo iba en un solo try: si fallaba la data cruda del logger, los
equipos del inspector o las resistividades, el error cancelaba también el
tramo, la fecha y el recubrimiento (el ingeniero tenía que escribir el tramo
a mano y le quedaban campos en blanco, Marsella 2026-10). Ahora cada paso se
guarda por separado y lo que falle se reporta en `errores`."""
from dcvg_reader import (leer_dcvg_fastfield_varios, leer_resistividades_fastfield_varios,
                         leer_hallazgos_logger_varios, info_desde_meta)


def procesar_dcvg(rutas_dcvg, rutas_resist=None, rutas_logger=None, tipo='DCVG',
                  equipos_fn=None):
    """Devuelve {'postes','defectos','resist','hallazgos','auto','tecnico',
    'equipos','errores'}. `auto` son los campos de Datos Generales derivados del
    FastField (tramo, fecha, contratista, inspector) más lo que el tramo
    autollena (gasoducto, recubrimiento, OT, contrato…). `equipos_fn(inspector)`
    -> (serial, fecha_calibracion, equipos) es el buscador del listado de
    equipos (vive en la app; aquí es opcional)."""
    import datos_tramo

    out = {'postes': [], 'defectos': [], 'resist': [], 'hallazgos': [], 'auto': {},
           'tecnico': '', 'equipos': [], 'errores': []}
    d = leer_dcvg_fastfield_varios(list(rutas_dcvg))      # si esto falla, falla todo
    out['postes'], out['defectos'] = d['postes'], d['defectos']
    # Lo que trae la cabecera del FastField se aplica SIEMPRE.
    out['auto'] = info_desde_meta(d['meta'], [])

    rutas_resist = list(rutas_resist or [])
    rutas_logger = list(rutas_logger or [])
    if rutas_resist:
        try:
            out['resist'] = leer_resistividades_fastfield_varios(rutas_resist)
        except Exception as e:
            out['errores'].append(f"resistividades: {type(e).__name__}: {e}")
    if rutas_logger:
        try:
            out['hallazgos'] = leer_hallazgos_logger_varios(rutas_logger)
        except Exception as e:
            out['errores'].append(f"data cruda del logger (hallazgos): {type(e).__name__}: {e}")
        try:
            # el inspector del logger es el que casa con el listado de equipos
            con_logger = info_desde_meta(d['meta'], rutas_logger)
            if con_logger.get('inspector'):
                out['auto']['inspector'] = con_logger['inspector']
        except Exception as e:
            out['errores'].append(f"técnico del logger: {type(e).__name__}: {e}")

    tecnico = out['auto'].get('inspector', '')
    out['tecnico'] = tecnico
    if tecnico and equipos_fn is not None:
        try:
            serial, fc, eqs = equipos_fn(tecnico)
            if serial:
                out['auto']['serial_equipo'] = serial
            if fc:
                out['auto']['fecha_calibracion'] = fc
            out['equipos'] = eqs or []
        except Exception as e:
            out['errores'].append(f"equipos del inspector: {type(e).__name__}: {e}")

    tramo = out['auto'].get('tramo', '')
    if tramo:
        try:
            out['auto'].update(datos_tramo.autollenar(tramo, tipo))
        except Exception as e:
            out['errores'].append(f"autollenado del tramo '{tramo}': {type(e).__name__}: {e}")
    return out

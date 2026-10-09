"""Conclusiones y recomendaciones BASE del informe, según el TIPO de inspección.

El ingeniero las corrige a mano antes de entregar, pero la base tiene que salir
del generador y hablar de la técnica que se hizo:

  PAP   → potenciales por poste (-850 / -1200), VAC, estaciones de prueba,
          pintura, mantenimiento por tipo, inspecciones especiales.
  CIPS  → perfil continuo (potencial SUAVIZADO `off_limpio`, el oficial),
          % protegido / sobreprotegido, zonas desprotegidas por abscisa.
  DCVG  → indicaciones (defectos) por severidad %IR y carácter, potenciales de
          los postes, resistividad del suelo, hallazgos del recorrido.

Cada rama usa SOLO la data de su técnica: si en la sesión quedaron potenciales
de un PAP anterior, un DCVG no los menciona.
"""


def _k(metros):
    """'K 002+500' a partir de metros."""
    try:
        m = int(round(float(metros)))
    except (TypeError, ValueError):
        return ''
    return f"K {m // 1000:03d}+{m % 1000:03d}"


def _lista(items, sep=" y "):
    items = [str(i) for i in items if str(i)]
    if not items:
        return ''
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + sep + items[-1]


def _urpcs(rectificadores):
    """Nombres de las URPC, todos con el prefijo 'URPC ' (sin duplicarlo)."""
    out = []
    for r in (rectificadores or []):
        n = str(r.get('nombre') or '').strip()
        if n:
            out.append(n if n.upper().startswith('URPC') else f'URPC {n}')
    return out


def _linea(tipo_ducto, tramo):
    """'Ramal Salento' aunque el tramo ya traiga el 'Ramal' (no 'Ramal Ramal Salento')."""
    tipo_ducto = str(tipo_ducto or '').strip()
    tramo = str(tramo or '').strip()
    if not tipo_ducto:
        return tramo
    if not tramo or tramo.lower().startswith(tipo_ducto.lower()):
        return tramo or tipo_ducto
    return f'{tipo_ducto} {tramo}'


def _n(cant, singular, plural=None):
    """'1 indicación tiene' / '3 indicaciones tienen'."""
    plural = plural if plural is not None else singular + 's'
    return f'{cant} {singular if cant == 1 else plural}'


class ConclusionGenerator:
    def __init__(self, potenciales: list[dict], hallazgos: list[dict],
                 rectificadores: list[dict], aislamientos: list[dict],
                 inspecciones_activas: dict, info_general: dict,
                 cips: list[dict] = None, dcvg: dict = None):
        """`cips` = data['cips'] (puntos del survey) para un informe CIPS.
        `dcvg` = {'postes','defectos','resist','hallazgos'} para un DCVG.
        El tipo sale de info_general['tipo_inspeccion'] (sin él, PAP)."""
        self.potenciales = potenciales or []
        self.hallazgos = hallazgos or []
        self.rectificadores = rectificadores or []
        self.aislamientos = aislamientos or []
        self.inspecciones_activas = inspecciones_activas or {}
        self.info_general = info_general or {}
        self.cips = cips or []
        self.dcvg = dcvg or {}
        self.tipo = str(self.info_general.get('tipo_inspeccion') or 'PAP').strip().upper()

    # ── despacho por tipo ──────────────────────────────────────────────────
    def generar_conclusiones(self) -> list[str]:
        if self.tipo == 'DCVG':
            return self._conclusiones_dcvg()
        if self.tipo == 'CIPS':
            return self._conclusiones_cips()
        return self._conclusiones_pap()

    def generar_recomendaciones(self) -> list[str]:
        if self.tipo == 'DCVG':
            return self._recomendaciones_dcvg()
        if self.tipo == 'CIPS':
            return self._recomendaciones_cips()
        return self._recomendaciones_pap()

    @staticmethod
    def _c_sobreproteccion(pct, tecnica, tipo_ducto, tramo):
        """Conclusión de -1200 mV con la referencia ISO 15589-1:2018 de los históricos."""
        linea = _linea(tipo_ducto, tramo)
        if pct > 0:
            return (f'Los potenciales de protección catódica (Instant Off), registrados mediante la técnica '
                    f'de {tecnica} realizada a la línea {linea}, registraron que el {pct:.0f}% de '
                    f'la longitud inspeccionada presenta un potencial estructura electrolito más electronegativo '
                    f'de -1200 mV [CSE], límite recomendado según la norma ISO 15589-1:2018, presentando '
                    f'posibilidad de desprendimiento catódico (disbonding) del recubrimiento.')
        return (f'Los potenciales de protección catódica (Instant Off), registrados mediante la técnica de '
                f'{tecnica} realizada a la línea {linea}, no presentan potenciales estructura '
                f'electrolito más electronegativos de -1200 mV [CSE], límite recomendado según la norma '
                f'ISO 15589-1:2018.')

    def _c_aislamientos(self):
        """Juntas/bridas de aislamiento inspeccionadas y cuántas aíslan."""
        if not self.aislamientos:
            return None
        n = len(self.aislamientos)
        diag = [str(a.get('diagnostico') or '').strip().lower() for a in self.aislamientos]
        aisladas = sum(1 for d in diag if d and 'no' not in d.split() and 'aisl' in d)
        pasan = [a for a, d in zip(self.aislamientos, diag) if d and ('no' in d.split() or 'paso' in d)]
        txt = f'Se inspeccionaron {n} junta(s)/brida(s) de aislamiento'
        if aisladas:
            txt += f', de las cuales {aisladas} ({100.0 * aisladas / n:.0f}%) se encuentran aislando correctamente'
        if pasan:
            txt += (f'; presentan paso de corriente las ubicadas en '
                    f'{_lista([a.get("abscisado") or a.get("tag") or "" for a in pasan])}')
        return txt + '.'

    def _rango_pap(self):
        absc = [p.get('abscisa') for p in self.potenciales if p.get('abscisa') is not None]
        if len(absc) < 2 or min(absc) == max(absc):
            return ''
        return (f' entre el {_k(min(absc))} y el {_k(max(absc))}, en una longitud de '
                f'{(max(absc) - min(absc)) / 1000.0:.1f} km')

    def _c_urpc(self, tipo_ducto):
        nombres = _urpcs(self.rectificadores)
        if not nombres:
            return None
        return (f'Las unidades de protección catódica que influyen en el {tipo_ducto} '
                f'corresponden a la(s) {_lista(nombres)}, propiedad de TGI, las cuales '
                f'se encuentran operando de manera normal.')

    def calcular_estadisticas(self) -> dict:
        stats = {
            'total_puntos': 0,
            'protegidos_850': 0,
            'pct_protegido': 0.0,
            'sobreprotegidos_1200': 0,
            'pct_sobreprotegido': 0.0,
            'cumple_vac': True,
            'max_vac': 0.0,
            'total_estaciones': 0,
            'n_postes_potencial': 0,
            'n_postes_abscisado': 0,
            'n_valvulas': 0,
            'abscisas_abscisados': [],
            'postes_pintura_regular': [],
            'postes_pintura_malo': [],
            'mantenimiento_por_tipo': {},
            'total_requiere_mant': 0,
            'abscisas_por_tipo_mant': {},
            'n_valvulas_inspeccionadas': 0,
            'abscisas_valvulas': [],
            'inspecciones_no_realizadas': []
        }

        offs = [p['off_mv'] for p in self.potenciales if p.get('off_mv') is not None]
        stats['total_puntos'] = len(offs)
        if offs:
            stats['protegidos_850'] = sum(1 for v in offs if v <= -850)
            stats['pct_protegido'] = (stats['protegidos_850'] / len(offs)) * 100
            stats['sobreprotegidos_1200'] = sum(1 for v in offs if v <= -1200)
            stats['pct_sobreprotegido'] = (stats['sobreprotegidos_1200'] / len(offs)) * 100

        vacs = [p['vac'] for p in self.potenciales if p.get('vac') is not None]
        if vacs:
            stats['max_vac'] = max(vacs)
            stats['cumple_vac'] = all(v <= 15 for v in vacs)

        for p in self.potenciales:
            ref = str(p.get('ref_geografica', '')).lower()
            abscisa = p.get('abscisa_str', f"K 000+{p.get('abscisa',0):03d}")
            if 'potencial' in ref:
                stats['n_postes_potencial'] += 1
            elif 'abscisado' in ref:
                stats['n_postes_abscisado'] += 1
                stats['abscisas_abscisados'].append(f"K {abscisa}")
            elif 'valvula' in ref or 'válvula' in ref:
                stats['n_valvulas'] += 1
                stats['abscisas_valvulas'].append(f"K {abscisa}")

            pintura = str(p.get('pintura', '')).lower()
            if 'regular' in pintura:
                stats['postes_pintura_regular'].append(f"K {abscisa}")
            elif 'malo' in pintura:
                stats['postes_pintura_malo'].append(f"K {abscisa}")

            mant = p.get('tipo_mant')
            if mant and mant != 'NO APLICA':
                stats['mantenimiento_por_tipo'][mant] = stats['mantenimiento_por_tipo'].get(mant, 0) + 1
                stats['total_requiere_mant'] += 1
                if mant not in stats['abscisas_por_tipo_mant']:
                    stats['abscisas_por_tipo_mant'][mant] = []
                stats['abscisas_por_tipo_mant'][mant].append(f"K {abscisa}")

        stats['total_estaciones'] = stats['n_postes_potencial'] + stats['n_postes_abscisado'] + stats['n_valvulas']

        names = {
            'marco_h': 'marcos H',
            'ce': 'cruces encamisados',
            'anodos': 'ánodos',
            'cupones_ir': 'cupones IR',
            'cupones_grav': 'cupones gravimétricos',
            'pe': 'puentes eléctricos'
        }
        for k, v in self.inspecciones_activas.items():
            if not v and k in names:
                stats['inspecciones_no_realizadas'].append(names[k])

        return stats

    # ── PAP ───────────────────────────────────────────────────────────────
    def _conclusiones_pap(self) -> list[str]:
        stats = self.calcular_estadisticas()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        linea = _linea(tipo_ducto, tramo)
        long_km = info.get('longitud_km', 0)

        conclusiones = []

        # C1
        rango = self._rango_pap()
        c1 = (f'Los potenciales de protección catódica (Instant Off), registrados mediante la técnica de '
              f'Inspección PAP realizada a la línea {linea}{rango}, cumplen en un '
              f'{stats["pct_protegido"]:.0f}% de la longitud inspeccionada el criterio establecido en el '
              f'numeral 6.2.1.3 de la norma NACE SP0169 (AMPP) "un potencial estructura electrolito de '
              f'-850 mV o más negativo, medido respecto a un electrodo de referencia de cobre sulfato de '
              f'cobre [CSE]".')
        conclusiones.append(c1)

        # C2
        c2 = self._c_sobreproteccion(stats["pct_sobreprotegido"], 'Inspección PAP', tipo_ducto, tramo)
        conclusiones.append(c2)

        # C3
        urpc = self._c_urpc(tipo_ducto)
        if urpc:
            conclusiones.append(urpc)

        conclusiones += self._conclusiones_postes(stats, tipo_ducto, tramo, long_km)
        return conclusiones


    def _conclusiones_postes(self, stats, tipo_ducto, tramo, long_km) -> list[str]:
        """Conclusiones que salen de los POSTES inspeccionados (VAC, estaciones
        de prueba, pintura, mantenimiento, válvulas, inspecciones especiales).
        Las usa el PAP y también el CIPS cuando en la misma campaña se
        inspeccionaron los postes (así vienen los informes históricos)."""
        conclusiones = []
        linea = _linea(tipo_ducto, tramo)
        # C4
        sup_txt = 'no superan' if stats['cumple_vac'] else 'superan'
        c4 = f'Los potenciales AC registrados en {linea} {sup_txt} el limite establecido en la norma NACE SP0177-19 numeral 5.2.1.1 "Los límites de seguridad los determinará un personal calificado y estos no deben superar los 15VAC con respecto a una tierra local, en este caso al electrodo de Cu/CUSO4" en los {long_km:03.0f} Km inspeccionados.'
        conclusiones.append(c4)

        # C5
        if stats['n_postes_abscisado'] > 0:
            lista_abs = ", ".join(stats['abscisas_abscisados'])
            c5 = f'Se inspeccionaron {stats["total_estaciones"]} estaciones de prueba, de las cuales {stats["n_postes_abscisado"]} corresponde(n) a poste(s) de abscisado ({lista_abs}).'
        else:
            c5 = f'Se inspeccionaron {stats["total_estaciones"]} estaciones de prueba.'
        conclusiones.append(c5)

        # C6
        if stats['postes_pintura_regular']:
            l_reg = ", ".join(stats['postes_pintura_regular'])
            conclusiones.append(f'Las estaciones de prueba ubicadas en los {l_reg} presentan pintura en estado regular.')
        if stats['postes_pintura_malo']:
            l_mal = ", ".join(stats['postes_pintura_malo'])
            conclusiones.append(f'Las estaciones de prueba ubicadas en los {l_mal} presentan pintura en estado malo.')

        # C7
        if stats['total_requiere_mant'] > 0:
            desglose = []
            for k, v in stats['mantenimiento_por_tipo'].items():
                desglose.append(f'{v} de tipo {k}')
            desglose_str = ", ".join(desglose)
            c7 = f'Del total de postes inspeccionados, {stats["total_requiere_mant"]} requieren mantenimiento, distribuidos en {desglose_str}.'
            conclusiones.append(c7)

        # C8
        if stats['n_valvulas'] > 0:
            v_list = stats['abscisas_valvulas']
            if len(v_list) > 1:
                v_str = ", ".join(v_list[:-1]) + " y " + v_list[-1]
            else:
                v_str = v_list[0]
            c8 = f'Se inspeccionan {stats["n_valvulas"]} válvulas a lo largo del recorrido del {linea}, ubicadas en los {v_str}.'
            conclusiones.append(c8)

        aisl = self._c_aislamientos()
        if aisl:
            conclusiones.append(aisl)

        # C9
        if stats['inspecciones_no_realizadas']:
            no_ins = stats['inspecciones_no_realizadas']
            if len(no_ins) > 1:
                no_str = ", ".join(no_ins[:-1]) + " ni " + no_ins[-1]
            else:
                no_str = no_ins[0]
            c9 = f'Durante la inspección no se evidenciaron {no_str} ni otros hallazgos relevantes.'
            conclusiones.append(c9)

        return conclusiones

    def _recomendaciones_mantenimiento(self, stats) -> list[str]:
        out = []
        for tipo, abscisas in stats['abscisas_por_tipo_mant'].items():
            out.append(f'Se recomienda realizar mantenimiento tipo {tipo} a las estaciones de prueba '
                       f'{_lista(abscisas)}.')
        return out

    def _recomendaciones_pap(self) -> list[str]:
        stats = self.calcular_estadisticas()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        linea = _linea(tipo_ducto, tramo)

        recomendaciones = []
        r1 = f'Se recomienda continuar con las inspecciones periódicas del {linea}, en conjunto con las de las URPC\'s, con el fin de asegurar el correcto funcionamiento del sistema de protección catódica.'
        recomendaciones.append(r1)

        recomendaciones += self._recomendaciones_mantenimiento(stats)
        return recomendaciones

    # ── CIPS ──────────────────────────────────────────────────────────────
    @staticmethod
    def _off_cips(p):
        v = p.get('off_limpio')
        return v if v is not None else p.get('off_mv')

    #: umbral del filtro de picos de cips_lrs._suavizar_outliers (mV)
    _UMBRAL_PICO = 250

    def estadisticas_cips(self) -> dict:
        pts = sorted((p for p in self.cips if p.get('abscisa_val') is not None),
                     key=lambda p: p['abscisa_val'])
        offs = [(p['abscisa_val'], self._off_cips(p)) for p in pts
                if self._off_cips(p) is not None]
        n = len(offs)
        st = {'n': n, 'pct_protegido': 0.0, 'pct_sobreprotegido': 0.0,
              'zonas_desprotegidas': [], 'picos': [], 'ini': None, 'fin': None,
              'long_km': 0.0, 'min_off': None, 'max_off': None}
        if not offs:
            return st
        st['ini'], st['fin'] = offs[0][0], offs[-1][0]
        st['long_km'] = (st['fin'] - st['ini']) / 1000.0
        vals = [v for _a, v in offs]
        st['pct_protegido'] = 100.0 * sum(1 for v in vals if v <= -850) / n
        st['pct_sobreprotegido'] = 100.0 * sum(1 for v in vals if v <= -1200) / n
        st['min_off'], st['max_off'] = min(vals), max(vals)
        # sectores contiguos más positivos que -850 (no cumplen)
        zona = None
        for a, v in offs:
            if v > -850:
                if zona is None:
                    zona = [a, a]
                else:
                    zona[1] = a
            elif zona is not None:
                st['zonas_desprotegidas'].append(tuple(zona))
                zona = None
        if zona is not None:
            st['zonas_desprotegidas'].append(tuple(zona))
        # caídas o picos puntuales: lecturas crudas que el filtro corrigió
        for p in pts:
            crudo, limpio = p.get('off_mv'), p.get('off_limpio')
            if crudo is not None and limpio is not None and abs(crudo - limpio) > self._UMBRAL_PICO:
                st['picos'].append(p['abscisa_val'])
        return st

    def _conclusiones_cips(self) -> list[str]:
        st = self.estadisticas_cips()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        linea = _linea(tipo_ducto, tramo)
        long_km = float(info.get('longitud_km') or st['long_km'] or 0)
        c = []
        # 1. fuente de protección (si se conocen las URPC)
        urpcs = _urpcs(self.rectificadores)
        if urpcs:
            c.append(f'La línea {linea} se encuentra protegida por corriente impresa a través de '
                     f'la(s) {_lista(urpcs)}, propiedad de TGI, las cuales se ciclaron durante el '
                     f'registro para obtener el potencial Instant Off.')
        if st['n']:
            # 2. cumplimiento -850 mV (numeral 6.2.1.3 NACE SP0169)
            c.append(f'El registro de potenciales de protección catódica (Instant Off) mediante la técnica de '
                     f'Inspección CIPS realizada a la línea {linea} entre el {_k(st["ini"])} y el '
                     f'{_k(st["fin"])}, en una longitud de {st["long_km"]:.1f} km, cumple en un '
                     f'{st["pct_protegido"]:.0f}% de la longitud inspeccionada el criterio establecido en el '
                     f'numeral 6.2.1.3 de la norma NACE SP0169 (AMPP) "un potencial estructura electrolito de '
                     f'-850 mV o más negativo, medido respecto a un electrodo de referencia de cobre sulfato de '
                     f'cobre [CSE]".')
            # 3. sobreprotección -1200 mV (ISO 15589-1)
            c.append(self._c_sobreproteccion(st['pct_sobreprotegido'], 'Inspección CIPS', tipo_ducto, tramo))
        else:
            c.append(f'Se realizó la Inspección CIPS (Close Interval Potential Survey) a la línea '
                     f'{linea}; el archivo del logger no trae lecturas Instant Off válidas.')
        # 5. VAC, 9. estaciones, 10. marcos H/ánodos/cruces: salen de los postes
        #    cuando se inspeccionaron en la misma campaña (como en los históricos).
        if self.potenciales:
            c += self._conclusiones_postes(self.calcular_estadisticas(), tipo_ducto, tramo, long_km)
        # 6. sectores más positivos que -850 mV y causa probable
        if st['n']:
            if st['zonas_desprotegidas']:
                zonas = [f'entre el {_k(a)} y el {_k(b)}' if a != b else f'en el {_k(a)}'
                         for a, b in st['zonas_desprotegidas']]
                c.append(f'Los potenciales más positivos que el criterio de -850 mV [CSE] se concentran '
                         f'{_lista(zonas)}, sector(es) atribuible(s) a [CAUSA PROBABLE POR VERIFICAR: baja '
                         f'influencia de la URPC del sector, corriente de salida insuficiente o terreno seco].')
            else:
                c.append(f'No se identificaron sectores con potencial Instant Off más positivo que -850 mV '
                         f'[CSE] a lo largo de la longitud inspeccionada.')
            # 7. caídas o picos puntuales
            if st['picos']:
                picos = st['picos'][:12]
                extra = f' y {len(st["picos"]) - 12} más' if len(st['picos']) > 12 else ''
                c.append(f'Se identificaron caídas o picos puntuales de potencial en los {_lista([_k(a) for a in picos])}'
                         f'{extra}, lecturas aisladas corregidas en el perfil, que conviene contrastar con las '
                         f'indicaciones del DCVG del tramo.')
        # 11. juntas / bridas de aislamiento
        aisl = self._c_aislamientos()
        if aisl:
            c.append(aisl)
        # hallazgos del recorrido
        if self.hallazgos:
            tipos = {}
            for h in self.hallazgos:
                t = str(h.get('tipo') or 'Otro').strip() or 'Otro'
                tipos[t] = tipos.get(t, 0) + 1
            desglose = _lista([f'{v} {k.lower()}' for k, v in sorted(tipos.items(), key=lambda kv: -kv[1])])
            c.append(f'Durante el recorrido se registraron {len(self.hallazgos)} hallazgos ({desglose}), '
                     f'relacionados en la hoja Hallazgos.')
        return c

    def _recomendaciones_cips(self) -> list[str]:
        st = self.estadisticas_cips()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        linea = _linea(tipo_ducto, tramo)
        r = []
        if st['zonas_desprotegidas']:
            zonas = _lista([f'{_k(a)} - {_k(b)}' if a != b else _k(a) for a, b in st['zonas_desprotegidas']])
            r.append(f'Se recomienda reforzar el nivel de protección catódica en {zonas}: verificar la corriente '
                     f'de salida de las URPC de influencia y, de ser necesario, evaluar una nueva fuente de '
                     f'corriente o un CIPS ciclando una sola URPC para identificar su alcance.')
        if st['pct_sobreprotegido'] > 0:
            r.append('Se recomienda ajustar la salida de las URPC en las zonas con potenciales más '
                     'electronegativos de -1200 mV [CSE] para evitar el desprendimiento catódico del recubrimiento.')
        if st['picos']:
            r.append(f'Se recomienda la inspección directa del recubrimiento en los puntos con caídas de potencial '
                     f'({_lista([_k(a) for a in st["picos"][:8]])}) y su contraste con el DCVG del tramo.')
        if self.potenciales:
            r += self._recomendaciones_mantenimiento(self.calcular_estadisticas())
        r.append(f'Se recomienda continuar con el plan de mantenimiento y monitoreo de TGI, con las inspecciones '
                 f'periódicas del {linea} en conjunto con las de las URPC\'s, con el fin de asegurar '
                 f'el correcto funcionamiento del sistema de protección catódica.')
        return r

    # ── DCVG ──────────────────────────────────────────────────────────────
    _RHO_CLASES = ((500, 'Muy Corrosivo'), (1000, 'Corrosivo'), (2000, 'Moderadamente Corrosivo'),
                   (10000, 'Medianamente Corrosivo'))

    @classmethod
    def _clase_rho(cls, rho):
        for lim, nombre in cls._RHO_CLASES:
            if rho <= lim:
                return nombre
        return 'Despreciable'

    #: rangos de %IR como los redactan los históricos (misma clasificación de la plantilla)
    _RANGOS_IR = (('Muy Pequeño', 'menor o igual a 15%'), ('Pequeño', 'entre 16% y 35%'),
                  ('Mediano', 'entre 36% y 60%'), ('Grande', 'mayor a 60%'))
    _CARACTER = {'AA': 'A-A (anódico/anódico)', 'CA': 'C-A (catódico/anódico)',
                 'CC': 'C-C (catódico/catódico)'}

    def estadisticas_dcvg(self) -> dict:
        from db import _severidad_dcvg
        postes = self.dcvg.get('postes') or []
        defectos = self.dcvg.get('defectos') or []
        resist = self.dcvg.get('resist') or []
        sev = _severidad_dcvg(postes, defectos)
        st = {'n_defectos': len(defectos), 'por_clase': {}, 'detalle_por_clase': {},
              'por_caracter': {}, 'max_pct': None, 'densidad_km': None,
              'n_postes': 0, 'pct_postes_ok': 0.0, 'postes_fuera': [],
              'rho_clases': {}, 'n_rho': 0, 'prof_min': None, 'prof_max': None,
              'ini': None, 'fin': None, 'long_km': 0.0}
        for d, s_ in zip(defectos, sev):
            clase = s_.get('clasificacion') or 'Sin P/RE'
            st['por_clase'][clase] = st['por_clase'].get(clase, 0) + 1
            car = str(d.get('caracter') or '').strip().upper() or 'N/D'
            st['por_caracter'][car] = st['por_caracter'].get(car, 0) + 1
            pct = s_.get('severidad_pct')
            st['detalle_por_clase'].setdefault(clase, []).append(
                _k(d.get('pk_m')) + (f' ({pct:.0f}% IR, {car})' if pct is not None else f' ({car})'))
            if pct is not None:
                st['max_pct'] = max(st['max_pct'] or 0, pct)
            prof = d.get('profundidad')
            if prof is not None:
                try:
                    prof = float(prof)
                    st['prof_min'] = prof if st['prof_min'] is None else min(st['prof_min'], prof)
                    st['prof_max'] = prof if st['prof_max'] is None else max(st['prof_max'], prof)
                except (TypeError, ValueError):
                    pass
        con_lectura = [p for p in postes if p.get('off') is not None]
        st['n_postes'] = len(con_lectura)
        if con_lectura:
            ok = [p for p in con_lectura if p['off'] <= -850]
            st['pct_postes_ok'] = 100.0 * len(ok) / len(con_lectura)
            st['postes_fuera'] = [_k(p.get('pk_m')) for p in con_lectura if p['off'] > -850]
        pks = [p.get('pk_m') for p in postes + defectos if p.get('pk_m') is not None]
        if pks:
            st['ini'], st['fin'] = min(pks), max(pks)
            st['long_km'] = (st['fin'] - st['ini']) / 1000.0
        long_km = float(self.info_general.get('longitud_km') or st['long_km'] or 0)
        if long_km > 0 and defectos:
            st['densidad_km'] = len(defectos) / long_km
        # resistividad Wenner a 1, 2 y 3 m (ρ = 2·π·a·R, a en cm), como la plantilla
        for r in resist:
            for clave, a_cm in (('r1', 100), ('r2', 200), ('r3', 300)):
                if r.get(clave) is None:
                    continue
                try:
                    rho = 2 * 3.141592653589793 * float(r[clave]) * a_cm
                except (TypeError, ValueError):
                    continue
                clase = self._clase_rho(rho)
                st['rho_clases'][clase] = st['rho_clases'].get(clase, 0) + 1
                st['n_rho'] += 1
        return st

    def _conclusiones_dcvg(self) -> list[str]:
        st = self.estadisticas_dcvg()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        linea = _linea(tipo_ducto, tramo)
        long_km = float(info.get('longitud_km') or st['long_km'] or 0)
        c = []
        rango = (f' entre el {_k(st["ini"])} y el {_k(st["fin"])}'
                 if st['ini'] is not None and st['fin'] is not None and st['ini'] != st['fin'] else '')
        if st['n_defectos']:
            # 1. número de indicaciones, densidad y distribución por %IR
            desglose = _lista([f'{st["por_clase"][k]} {"tiene" if st["por_clase"][k] == 1 else "tienen"} '
                               f'un índice de severidad IR {txt}'
                               for k, txt in self._RANGOS_IR if k in st['por_clase']], sep=' y ')
            dens = (f', con una densidad de defectos de {st["densidad_km"]:.2f} indicaciones/km'
                    if st['densidad_km'] is not None else '')
            c.append(f'Mediante la técnica DCVG (Direct Current Voltage Gradient) realizada a la línea '
                     f'{linea}{rango}, en una longitud de {long_km:.1f} km, se identificaron '
                     f'{_n(st["n_defectos"], "indicación", "indicaciones")} (defectos de recubrimiento){dens}. En donde {desglose}.')
            # 2. carácter
            car = _lista([f'{v} {self._CARACTER.get(k, k)}'
                          for k, v in sorted(st['por_caracter'].items(), key=lambda kv: -kv[1])])
            c.append(f'Según el carácter de la indicación (ON/OFF), las {st["n_defectos"]} indicaciones se '
                     f'distribuyen en: {car}.')
            # 3. detalle de las más severas
            graves = [k for k in ('Grande', 'Mediano') if st['detalle_por_clase'].get(k)]
            if graves:
                partes = [f'severidad {k}: {_lista(st["detalle_por_clase"][k])}' for k in graves]
                c.append(f'Las indicaciones más severas corresponden a {"; ".join(partes)}'
                         + (f' (%IR máximo {st["max_pct"]:.0f}%).' if st['max_pct'] is not None else '.'))
            else:
                c.append('Ninguna indicación alcanza severidad Mediana o Grande: todas presentan un índice de '
                         'severidad IR igual o menor a 35% (Pequeño o Muy Pequeño).')
        else:
            c.append(f'Mediante la técnica DCVG (Direct Current Voltage Gradient) realizada a la línea '
                     f'{linea}{rango}, en una longitud de {long_km:.1f} km, no se identificaron '
                     f'indicaciones (defectos de recubrimiento).')
        # 4. resistividad (1, 2 y 3 m)
        if st['n_rho']:
            desglose = _lista([f'el {100.0 * v / st["n_rho"]:.0f}% de los registros corresponde a una zona '
                               f'de corrosividad {k}'
                               for k, v in sorted(st['rho_clases'].items(), key=lambda kv: -kv[1])])
            c.append(f'Basado en la totalidad de las mediciones de resistividad del suelo (método Wenner a 1, 2 y '
                     f'3 m de profundidad, {st["n_rho"]} registros), {desglose}.')
        # 5. profundidad de la tubería
        if st['prof_min'] is not None:
            if st['prof_min'] == st['prof_max']:
                c.append(f'La profundidad de la tubería en las indicaciones es de {st["prof_min"] / 100:.1f} m.')
            else:
                c.append(f'La profundidad de la tubería en las indicaciones varía entre {st["prof_min"] / 100:.1f} m '
                         f'y {st["prof_max"] / 100:.1f} m.')
        # potenciales de los postes
        if st['n_postes']:
            txt = (f'Los potenciales de protección catódica (Instant Off) medidos en los {st["n_postes"]} '
                   f'postes de potencial del recorrido cumplen en un {st["pct_postes_ok"]:.0f}% el criterio de '
                   f'-850 mV [CSE] del numeral 6.2.1.3 de la norma NACE SP0169 (AMPP)')
            txt += f'; no lo cumplen los postes {_lista(st["postes_fuera"])}.' if st['postes_fuera'] else '.'
            c.append(txt)
        # 6. sistema de protección catódica
        urpc = self._c_urpc(tipo_ducto)
        if urpc:
            c.append(urpc)
        # hallazgos del recorrido
        hall = self.dcvg.get('hallazgos') if self.dcvg.get('hallazgos') is not None else self.hallazgos
        if hall:
            tipos = {}
            for h in hall:
                t = str(h.get('tipo') or 'Otro').strip() or 'Otro'
                tipos[t] = tipos.get(t, 0) + 1
            desglose = _lista([f'{v} {k.lower()}' for k, v in sorted(tipos.items(), key=lambda kv: -kv[1])])
            c.append(f'Durante el recorrido se registraron {len(hall)} hallazgos ({desglose}), '
                     f'relacionados en la hoja Hallazgos.')
        return c

    def _recomendaciones_dcvg(self) -> list[str]:
        st = self.estadisticas_dcvg()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        linea = _linea(tipo_ducto, tramo)
        r = []
        graves = {k: st['detalle_por_clase'][k] for k in ('Grande', 'Mediano')
                  if st['detalle_por_clase'].get(k)}
        if graves:
            partes = [f'{k} ({_lista(v)})' for k, v in graves.items()]
            r.append(f'Se recomienda la inspección directa (excavación y verificación del recubrimiento) y la '
                     f'reparación según la matriz de acción requerida en las indicaciones de severidad '
                     f'{_lista(partes)}, priorizando las de carácter A-A y C-A.')
        menores = [k for k in ('Pequeño', 'Muy Pequeño') if st['por_clase'].get(k)]
        if menores:
            r.append(f'Las indicaciones de severidad {_lista(menores)} se recomienda mantenerlas en seguimiento '
                     f'en la próxima campaña, sin intervención inmediata.')
        if st['postes_fuera']:
            r.append(f'Se recomienda revisar el nivel de protección catódica en los postes '
                     f'{_lista(st["postes_fuera"])}, que no cumplen el criterio de -850 mV [CSE].')
        r.append(f'Se recomienda continuar con el plan de mantenimiento y monitoreo de TGI, con las inspecciones '
                 f'periódicas del {linea} en conjunto con las de las URPC\'s, con el fin de asegurar '
                 f'el correcto funcionamiento del sistema de protección catódica.')
        return r

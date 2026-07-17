class ConclusionGenerator:
    def __init__(self, potenciales: list[dict], hallazgos: list[dict], 
                 rectificadores: list[dict], aislamientos: list[dict],
                 inspecciones_activas: dict, info_general: dict):
        self.potenciales = potenciales
        self.hallazgos = hallazgos
        self.rectificadores = rectificadores
        self.aislamientos = aislamientos
        self.inspecciones_activas = inspecciones_activas
        self.info_general = info_general

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

    def generar_conclusiones(self) -> list[str]:
        stats = self.calcular_estadisticas()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')
        long_km = info.get('longitud_km', 0)

        conclusiones = []

        # C1
        c1 = f'Los potenciales de protección catódica (Instant Off), registrados mediante la técnica de Inspección PAP realizada a la línea {tipo_ducto} {tramo}, cumple en un {stats["pct_protegido"]:.0f}% de la longitud inspeccionada el criterio establecido en el numeral 6.2.1.3 de la norma NACE SP0169 "un potencial estructura electrolito de -850 mV o mas negativo, medido respecto a un electrodo de referencia de cobre sulfato de cobre [CSE]"'
        conclusiones.append(c1)

        # C2
        c2 = f'Los potenciales de protección catódica (Instant Off), registrados mediante la técnica de Inspección PAP realizada a la línea {tipo_ducto} {tramo}, registró que el {stats["pct_sobreprotegido"]:03.0f}% de la longitud inspeccionada presenta un potencial estructura electrolito mas electronegativo de -1200 mV[CSE].'
        conclusiones.append(c2)

        # C3
        if self.rectificadores:
            nombres = [r.get('nombre', '') for r in self.rectificadores if r.get('nombre')]
            if nombres:
                if len(nombres) > 1:
                    lista_urpcs = ", ".join(nombres[:-1]) + " y " + nombres[-1]
                else:
                    lista_urpcs = nombres[0]
                c3 = f'Las unidades de protección catódica que influyen en el {tipo_ducto} corresponden a las URPC {lista_urpcs}, propiedad de TGI, las cuales se encuentran operando de manera normal.'
                conclusiones.append(c3)

        # C4
        sup_txt = 'no superan' if stats['cumple_vac'] else 'superan'
        c4 = f'Los potenciales AC registrados en {tipo_ducto} {tramo} {sup_txt} el limite establecido en la norma NACE SP0177-19 numeral 5.2.1.1 "Los límites de seguridad los determinará un personal calificado y estos no deben superar los 15VAC con respecto a una tierra local, en este caso al electrodo de Cu/CUSO4" en los {long_km:03.0f} Km inspeccionados.'
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
            c8 = f'Se inspeccionan {stats["n_valvulas"]} válvulas a lo largo del recorrido del {tipo_ducto} {tramo}, ubicadas en los {v_str}.'
            conclusiones.append(c8)

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

    def generar_recomendaciones(self) -> list[str]:
        stats = self.calcular_estadisticas()
        info = self.info_general
        tipo_ducto = info.get('tipo_ducto', 'Línea')
        tramo = info.get('tramo', '')

        recomendaciones = []
        r1 = f'Se recomienda continuar con las inspecciones periódicas del {tipo_ducto} {tramo}, en conjunto con las de las URPC\'s, con el fin de asegurar el correcto funcionamiento del sistema de protección catódica.'
        recomendaciones.append(r1)

        for tipo, abscisas in stats['abscisas_por_tipo_mant'].items():
            if len(abscisas) > 1:
                abs_str = ", ".join(abscisas[:-1]) + " y " + abscisas[-1]
            else:
                abs_str = abscisas[0]
            r2 = f'Se recomienda realizar mantenimiento tipo {tipo} a las estaciones de prueba {abs_str}.'
            recomendaciones.append(r2)

        return recomendaciones

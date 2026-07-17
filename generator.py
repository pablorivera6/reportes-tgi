"""
TGI Report Generator - Motor de generación de informes Excel
Llena la plantilla EN BLANCO.xlsx con los datos procesados
"""
import openpyxl
import pandas as pd
from openpyxl.utils import get_column_letter
from copy import copy
from datetime import datetime
from typing import Optional
import os
import sys
import math


def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


class ReportGenerator:
    """Generates inspection reports by filling the EN BLANCO.xlsx template"""

    def __init__(self, template_path: Optional[str] = None):
        """Initializes the generator with a template"""
        if template_path is None:
            # Revert to standard EN BLANCO.xlsx which now contains the Potenciales CIPS sheet manually
            template_path = resource_path("EN BLANCO.xlsx")
        self.wb = openpyxl.load_workbook(template_path)
        self.ws_informe = self.wb['Informe']
        self.ws_potenciales = self.wb['Potenciales PAP']
        self.ws_hallazgos = self.wb['Hallazgos']
        # Gráficas - handle encoding variations
        self._init_sheet_refs()

    def _init_sheet_refs(self):
        """Initialize sheet references handling encoding"""
        sheet_map = {}
        for name in self.wb.sheetnames:
            sheet_map[name.lower()] = name
        
        def find_sheet(keywords):
            for name, original in [(n.lower(), n) for n in self.wb.sheetnames]:
                if all(k.lower() in name for k in keywords):
                    return self.wb[original]
            return None

        self.ws_grafica_vdc = find_sheet(['fica', 'vdc']) or find_sheet(['fica', 'VDC'])
        self.ws_grafica_interf = find_sheet(['fica', 'nterferencia'])
        self.ws_grafica_vac = find_sheet(['fica', 'vac']) or find_sheet(['fica', 'VAC'])
        self.ws_marco_h = find_sheet(['marco', 'h'])
        self.ws_ce = find_sheet(['ce'])
        self.ws_anodos = find_sheet(['nodos'])
        self.ws_aislamientos = find_sheet(['aislamiento'])
        self.ws_cupones_ir = find_sheet(['cupones', 'ir', 'free'])
        self.ws_cupones_grav = find_sheet(['cupones', 'gravim'])
        self.ws_pe = find_sheet(['pe'])
        self.ws_tramos_aereos = find_sheet(['tramos', 'reos'])
        self.ws_tramos_no_insp = find_sheet(['tramos', 'no'])

    def _safe_write(self, ws, row: int, col: int, value):
        """Write value to cell, preserving formatting of merged cells"""
        try:
            cell = ws.cell(row=row, column=col)
            cell.value = value
        except (AttributeError, ValueError):
            pass

    def _copy_row_style(self, ws, source_row: int, target_row: int, min_col: int, max_col: int):
        """Copy cell styles from source row to target row to preserve template formatting"""
        for col in range(min_col, max_col + 1):
            source_cell = ws.cell(row=source_row, column=col)
            target_cell = ws.cell(row=target_row, column=col)
            if source_cell.has_style:
                target_cell.font = copy(source_cell.font)
                target_cell.border = copy(source_cell.border)
                target_cell.fill = copy(source_cell.fill)
                target_cell.number_format = copy(source_cell.number_format)
                target_cell.alignment = copy(source_cell.alignment)

    def fill_general_info(self, data: dict):
        """Fill Informe sheet rows 6-9 with general information
        
        data keys: fecha, gasoducto, tramo, inspector, serial_equipo, 
                   fecha_calibracion, tipo_recubrimiento, diametro,
                   contrato, ot, contratista, ciclo
        """
        ws = self.ws_informe
        # Row 6
        self._safe_write(ws, 6, 7, data.get('fecha', ''))           # G6 - Fecha
        self._safe_write(ws, 6, 22, data.get('serial_equipo', ''))   # V6 - Serial
        self._safe_write(ws, 6, 32, data.get('contrato', ''))        # AF6 - Contrato
        # Row 7
        self._safe_write(ws, 7, 7, data.get('gasoducto', ''))        # G7 - Gasoducto
        self._safe_write(ws, 7, 22, data.get('fecha_calibracion', ''))# V7 - Fecha cal.
        self._safe_write(ws, 7, 32, data.get('ot', ''))              # AF7 - OT
        # Row 8
        self._safe_write(ws, 8, 7, data.get('tramo', ''))            # G8 - Tramo
        self._safe_write(ws, 8, 22, data.get('tipo_recubrimiento', ''))# V8 - Recubrim.
        self._safe_write(ws, 8, 32, data.get('contratista', ''))     # AF8 - Contratista
        # Row 9
        self._safe_write(ws, 9, 7, data.get('inspector', ''))        # G9 - Inspector
        self._safe_write(ws, 9, 22, data.get('diametro', ''))        # V9 - Diámetro
        self._safe_write(ws, 9, 32, data.get('ciclo', ''))           # AF9 - Ciclo
        
        # Row 20 (Documentos de Referencia)
        tipo_inspeccion = data.get('tipo_inspeccion', 'CIPS')
        self._safe_write(ws, 20, 1, f"PR-I-06 PROCEDIMIENTO PARA ENCENDIDO, CALIBRACIÓN E INSPECCIÓN {tipo_inspeccion} DE SPC")

    def fill_equipos_utilizados(self, equipos_list: list):
        """Fill the EQUIPOS UTILIZADOS section (rows 24-28)
        equipos_list is a list of strings
        """
        ws = self.ws_informe
        if not equipos_list:
            return
            
        # Clear existing first
        for r in range(24, 29):
            self._safe_write(ws, r, 1, "")
            self._safe_write(ws, r, 19, "")
            
        # Write new
        for i, eq in enumerate(equipos_list):
            if i < 5:
                self._safe_write(ws, 24 + i, 1, eq)
            elif i < 10:
                self._safe_write(ws, 24 + (i - 5), 19, eq)

    def fill_sistema_inspeccionado(self, data: dict, potenciales: list):
        """Fill system inspection section (rows 38-46)
        
        data keys: tipo_inspeccion, detalle, justificacion, uso_tierra,
                   amenaza, tipo_ducto, tipo_spc, topografia,
                   altura_inicio, altura_fin, resumen_justificacion
        """
        ws = self.ws_informe
        
        # Calculate start/end points from potenciales
        if potenciales:
            sorted_pot = sorted(potenciales, key=lambda p: p.get('abscisa', 0))
            first = sorted_pot[0]
            last = sorted_pot[-1]
            
            # Row 39 - Punto Inicial
            self._safe_write(ws, 39, 7, first.get('abscisa', 0))           # G39
            self._safe_write(ws, 39, 15, first.get('lat'))                  # O39
            self._safe_write(ws, 39, 23, first.get('lon'))                  # W39
            self._safe_write(ws, 39, 29, data.get('altura_inicio', ''))     # AC39
            
            # Row 40 - Punto Final
            self._safe_write(ws, 40, 7, last.get('abscisa', 0))            # G40
            self._safe_write(ws, 40, 15, last.get('lat'))                   # O40
            self._safe_write(ws, 40, 23, last.get('lon'))                   # W40
            self._safe_write(ws, 40, 29, data.get('altura_fin', ''))        # AC40

        # Row 41
        self._safe_write(ws, 41, 7, data.get('tipo_inspeccion', 'Inspección PAP'))
        self._safe_write(ws, 41, 15, data.get('detalle', 'Normal'))
        self._safe_write(ws, 41, 23, data.get('justificacion', 'Monitoreo'))
        self._safe_write(ws, 41, 29, data.get('uso_tierra', ''))
        
        # Row 42
        self._safe_write(ws, 42, 7, data.get('amenaza', 'CORROSIÓN EXTERNA'))
        self._safe_write(ws, 42, 15, data.get('tipo_ducto', ''))
        self._safe_write(ws, 42, 23, data.get('tipo_spc', ''))
        self._safe_write(ws, 42, 29, data.get('topografia', ''))

        # Calculate lengths (rows 43-45)
        if potenciales:
            sorted_pot = sorted(potenciales, key=lambda p: p.get('abscisa', 0))
            total_length_km = (sorted_pot[-1].get('abscisa', 0) - sorted_pot[0].get('abscisa', 0)) / 1000.0
            
            # Count protected/unprotected/overprotected
            offs = [p['off_mv'] for p in potenciales if p.get('off_mv') is not None]
            n_total = len(offs) if offs else 1
            n_protected = sum(1 for v in offs if v <= -850)
            n_unprotected = sum(1 for v in offs if v > -850)
            n_overprotected = sum(1 for v in offs if v <= -1200)
            
            pct_protected = n_protected / n_total if n_total > 0 else 0
            pct_unprotected = n_unprotected / n_total if n_total > 0 else 0
            pct_overprotected = n_overprotected / n_total if n_total > 0 else 0
            
            len_protected = total_length_km * pct_protected
            len_unprotected = total_length_km * pct_unprotected
            len_overprotected = total_length_km * pct_overprotected
            
            # Row 43 - Aerial (default 0 for PAP)
            self._safe_write(ws, 43, 7, 0)     # G43 - Long total aérea
            self._safe_write(ws, 43, 15, 0)    # O43 - Long aérea inspeccionada
            self._safe_write(ws, 43, 23, 0)    # W43 - Aérea no insp
            self._safe_write(ws, 43, 29, 0)    # AC43 - Enterrada no insp
            
            # Row 44 - Buried
            self._safe_write(ws, 44, 7, total_length_km)     # G44
            self._safe_write(ws, 44, 15, total_length_km)    # O44
            self._safe_write(ws, 44, 23, len_protected)      # W44
            self._safe_write(ws, 44, 29, len_unprotected)    # AC44
            
            # Row 45 - Percentages
            self._safe_write(ws, 45, 7, len_overprotected)   # G45
            self._safe_write(ws, 45, 15, pct_protected)      # O45
            self._safe_write(ws, 45, 23, pct_unprotected)    # W45
            self._safe_write(ws, 45, 29, pct_overprotected)  # AC45
            
            # Row 31 - Descripción de la Línea
            tipo_tramo = data.get('tipo_tramo', 'Tramo')
            tramo = data.get('tramo', '')
            gasoducto = data.get('gasoducto', '')
            recubrimiento = data.get('tipo_recubrimiento', '')
            diametro = data.get('diametro', '')
            rectificadores_tgi = data.get('rectificadores_tgi', '[ESCRIBIR RECTIFICADORES TGI]')
            
            descripcion = (f"El {tipo_tramo} {tramo} perteneciente al Gasoducto {gasoducto}, "
                           f"cuenta con una longitud de {total_length_km:.1f} Km aproximadamente. "
                           f"La Tubería cuenta con un recubrimiento {recubrimiento} y un Diámetro de {diametro} in, "
                           f"tiene como mecanismo contra la corrosión externa un sistema de corriente impresa "
                           f"por las URPC de {rectificadores_tgi} propiedad de TGI. Adicional, las URPC's "
                           f"[ESCRIBIR RECTIFICADORES CENIT] propiedad de CENIT, tienen influencia sobre el Ramal.")
            self._safe_write(ws, 30, 1, descripcion)
        
        # Row 46 - Resumen justificación
        self._safe_write(ws, 46, 7, data.get('resumen_justificacion', ''))

    def fill_monitoreo(self, data: dict):
        """Fill monitoring section (rows 48-51)
        
        data keys: criterio, descripcion_criterio, ciclo_on, ciclo_off,
                   datos_por_km, pct_rechazados, clima
        """
        ws = self.ws_informe
        # Row 50
        self._safe_write(ws, 50, 7, data.get('criterio', '6.2.1.3 (-850mVCSE)'))
        self._safe_write(ws, 50, 15, data.get('descripcion_criterio', 
            'Potencial polarizado más electronegativo que -850mVCSE'))
        self._safe_write(ws, 50, 23, data.get('ciclo_on', 1.6))
        self._safe_write(ws, 50, 29, data.get('ciclo_off', 0.4))
        # Row 51
        self._safe_write(ws, 51, 7, data.get('datos_por_km', 0))
        self._safe_write(ws, 51, 15, data.get('pct_rechazados', 0))
        self._safe_write(ws, 51, 23, data.get('clima', ''))

    def fill_potenciales_pap(self, potenciales: list, fecha: str = ''):
        """Fill Potenciales PAP data table starting at row 12
        
        Each potencial dict has: abscisa, fecha, ref_geografica, on_mv, off_mv,
        on_mv_corregido, off_mv_corregido, on_mv_neg2, off_mv_neg2,
        on_mv_foraneo1, off_mv_foraneo1, on_mv_foraneo2, off_mv_foraneo2,
        potencial_natural, polarizacion, vac, resistencia, ir_on_off,
        lat, lon, alt, pintura, conexiones, verticalidad, tipo_mant, observaciones
        """
        ws = self.ws_potenciales
        sorted_pot = sorted(potenciales, key=lambda p: p.get('abscisa', 0))
        
        if len(sorted_pot) > 1:
            ws.insert_rows(13, amount=len(sorted_pot)-1)
            # Copiar estilo (solo si no son demasiados, o hacerlo rapido)
            if len(sorted_pot) < 1000:
                for i in range(1, len(sorted_pot)):
                    self._copy_row_style(ws, 12, 12 + i, 1, 27)

        for i, p in enumerate(sorted_pot):
            row = 12 + i
                
            self._safe_write(ws, row, 1, i + 1)                              # A - ITEM
            self._safe_write(ws, row, 2, p.get('abscisa', ''))                # B - ABSCISADO
            self._safe_write(ws, row, 3, p.get('fecha', fecha))               # C - FECHA
            self._safe_write(ws, row, 4, p.get('ref_geografica', ''))          # D - REF GEOG
            self._safe_write(ws, row, 5, p.get('on_mv'))                      # E - ON NEG1
            self._safe_write(ws, row, 6, p.get('off_mv'))                     # F - OFF NEG1
            self._safe_write(ws, row, 7, p.get('on_mv_corregido'))            # G - ON CORR
            self._safe_write(ws, row, 8, p.get('off_mv_corregido'))           # H - OFF CORR
            self._safe_write(ws, row, 9, p.get('on_mv_neg2'))                 # I - ON NEG2
            self._safe_write(ws, row, 10, p.get('off_mv_neg2'))               # J - OFF NEG2
            self._safe_write(ws, row, 11, p.get('on_mv_foraneo1'))            # K
            self._safe_write(ws, row, 12, p.get('off_mv_foraneo1'))           # L
            self._safe_write(ws, row, 13, p.get('on_mv_foraneo2'))            # M
            self._safe_write(ws, row, 14, p.get('off_mv_foraneo2'))           # N
            self._safe_write(ws, row, 15, p.get('potencial_natural'))         # O
            self._safe_write(ws, row, 16, p.get('polarizacion'))              # P
            self._safe_write(ws, row, 17, p.get('vac'))                       # Q - VAC
            self._safe_write(ws, row, 18, p.get('resistencia'))               # R - Resistencia
            self._safe_write(ws, row, 19, p.get('ir_on_off'))                 # S - IR ON-OFF
            self._safe_write(ws, row, 20, p.get('lat'))                       # T - LAT
            self._safe_write(ws, row, 21, p.get('lon'))                       # U - LON
            self._safe_write(ws, row, 22, p.get('alt'))                       # V - Altura
            self._safe_write(ws, row, 23, p.get('pintura'))                   # W - Pintura
            self._safe_write(ws, row, 24, p.get('conexiones'))                # X - Conexiones
            self._safe_write(ws, row, 25, p.get('verticalidad'))              # Y - Verticalidad
            self._safe_write(ws, row, 26, p.get('tipo_mant'))                 # Z - Tipo mant
            self._safe_write(ws, row, 27, p.get('observaciones'))             # AA - Obs

    def fill_cips(self, cips_data: list):
        if not cips_data:
            return
            
        ws_cips = self.wb['Potenciales CIPS']
        
        # Start inserting at row 12
        for i, data in enumerate(cips_data):
            row_idx = i + 12
            
            # Formatear abscisa
            abscisa = data.get('abscisa', '')
            if not abscisa and data.get('abscisa_val'):
                val = data['abscisa_val']
                km = int(val / 1000)
                m = int(val % 1000)
                abscisa = f"K {km:03d}+{m:03d}"

            ws_cips.cell(row=row_idx, column=1, value=i + 1)
            ws_cips.cell(row=row_idx, column=2, value=abscisa)
            # Fecha (maybe we don't have it here, leave empty or you could pass it)
            ws_cips.cell(row=row_idx, column=4, value=data.get('referencia', ''))
            
            ws_cips.cell(row=row_idx, column=5, value=data.get('on_mv', ''))
            ws_cips.cell(row=row_idx, column=6, value=data.get('off_mv', ''))
            
            ws_cips.cell(row=row_idx, column=7, value=data.get('on_limpio', ''))
            ws_cips.cell(row=row_idx, column=8, value=data.get('off_limpio', ''))
            
            # POTENCIAL NATURAL, POLARIZACIÓN (leave empty for now unless calculated)
            
            ws_cips.cell(row=row_idx, column=11, value=data.get('vac', ''))
            
            ws_cips.cell(row=row_idx, column=12, value=data.get('metal_on', ''))
            ws_cips.cell(row=row_idx, column=13, value=data.get('metal_off', ''))
            
            ws_cips.cell(row=row_idx, column=14, value=data.get('far_on', ''))
            ws_cips.cell(row=row_idx, column=15, value=data.get('far_off', ''))
            
            ws_cips.cell(row=row_idx, column=16, value=data.get('near_on', ''))
            ws_cips.cell(row=row_idx, column=17, value=data.get('near_off', ''))
            
            # IR ON-OFF
            on_limp = data.get('on_limpio')
            off_limp = data.get('off_limpio')
            if pd.notna(on_limp) and pd.notna(off_limp):
                ws_cips.cell(row=row_idx, column=18, value=on_limp - off_limp)
                
            ws_cips.cell(row=row_idx, column=19, value=data.get('lat', ''))
            ws_cips.cell(row=row_idx, column=20, value=data.get('lon', ''))
            ws_cips.cell(row=row_idx, column=21, value=data.get('observaciones', ''))

    def fill_graficas(self, potenciales: list, info: dict):
        """Fill chart data for VDC, Interferencia, and VAC graphs"""
        sorted_pot = sorted(potenciales, key=lambda p: p.get('abscisa', 0))
        if not sorted_pot:
            return
            
        max_abscisa = sorted_pot[-1].get('abscisa', 0)
        fecha = info.get('fecha', '')
        gasoducto = info.get('gasoducto', '')
        tramo = info.get('tramo', '')
        tipo_ducto = info.get('tipo_ducto', '')
        longitud = info.get('longitud_km', 0)
        diametro = info.get('diametro', '')
        recubrimiento = info.get('tipo_recubrimiento', '')

        # --- Gráfica VDC ---
        if self.ws_grafica_vdc:
            ws = self.ws_grafica_vdc
            # Info box (rows 31-36)
            self._safe_write(ws, 31, 4, fecha)
            self._safe_write(ws, 32, 4, gasoducto)
            self._safe_write(ws, 33, 4, f'{tipo_ducto} {tramo}')
            self._safe_write(ws, 34, 4, longitud)
            self._safe_write(ws, 35, 4, diametro)
            self._safe_write(ws, 36, 4, recubrimiento)
            
            # Criteria lines (rows 41-43)
            self._safe_write(ws, 42, 5, 0)
            self._safe_write(ws, 43, 5, max_abscisa)
            self._safe_write(ws, 42, 6, -850)
            self._safe_write(ws, 43, 6, -850)
            self._safe_write(ws, 42, 7, -1200)
            self._safe_write(ws, 43, 7, -1200)
            self._safe_write(ws, 42, 8, 100)
            self._safe_write(ws, 43, 8, 100)
            
            # Comments for chart annotations (rows 47+)
            self._safe_write(ws, 47, 5, 'Comentarios gráfica')
            self._safe_write(ws, 48, 5, 'Abscisa')
            self._safe_write(ws, 48, 6, 'Posición Y coment.')
            self._safe_write(ws, 48, 7, 'Comentario')
            for i, p in enumerate(sorted_pot):
                row = 49 + i
                self._safe_write(ws, row, 5, p.get('abscisa', 0))
                self._safe_write(ws, row, 6, -2100)  # Y position for annotation
                obs = p.get('observaciones', '')
                self._safe_write(ws, row, 7, obs if obs else p.get('ref_geografica', ''))
            
            # Observations text
            offs = [p['off_mv'] for p in potenciales if p.get('off_mv') is not None]
            n_total = len(offs) if offs else 1
            n_protected = sum(1 for v in offs if v <= -850)
            pct = round(n_protected / n_total * 100) if n_total > 0 else 0
            n_over = sum(1 for v in offs if v <= -1200)
            pct_over = round(n_over / n_total * 100) if n_total > 0 else 0
            
            obs_vdc = (f'Los potenciales de protección catódica (Instant Off), registrados mediante '
                      f'la técnica de Inspección PAP realizada a la línea {tipo_ducto} {tramo}, '
                      f'cumple en un {pct}% de la longitud inspeccionada el criterio establecido '
                      f'en el numeral 6.2.1.3 de la norma NACE SP0169 "un potencial estructura '
                      f'electrolito de -850 mV o mas negativo, medido respecto a un electrodo '
                      f'de referencia de cobre sulfato de cobre [CSE]"')
            self._safe_write(ws, 32, 6, obs_vdc)
            
            obs_1200 = (f'Los potenciales de protección catódica (Instant Off), registrados mediante '
                       f'la técnica de Inspección PAP realizada a la línea {tipo_ducto} {tramo}, '
                       f'registró que el {pct_over:03d}% de la longitud inspeccionada presenta un '
                       f'potencial estructura electrolito mas electronegativo de -1200 mV[CSE].')
            self._safe_write(ws, 35, 6, obs_1200)

        # --- Gráfica Interferencia ---
        if self.ws_grafica_interf:
            ws = self.ws_grafica_interf
            self._safe_write(ws, 31, 4, fecha)
            self._safe_write(ws, 32, 4, gasoducto)
            self._safe_write(ws, 33, 4, f'{tipo_ducto} {tramo}')
            self._safe_write(ws, 34, 4, longitud)
            self._safe_write(ws, 35, 4, diametro)
            self._safe_write(ws, 36, 4, recubrimiento)
            # Criteria 50mV line
            self._safe_write(ws, 41, 5, 0)
            self._safe_write(ws, 42, 5, max_abscisa)
            self._safe_write(ws, 41, 6, 50)
            self._safe_write(ws, 42, 6, 50)
            # Observation
            obs_interf = (f'A lo largo de la totalidad del tramo inspeccionado del '
                         f'{tipo_ducto} {tramo} no se evidencian inversiones de potencial.')
            self._safe_write(ws, 32, 6, obs_interf)

        # --- Gráfica VAC ---
        if self.ws_grafica_vac:
            ws = self.ws_grafica_vac
            self._safe_write(ws, 31, 4, fecha)
            self._safe_write(ws, 32, 4, gasoducto)
            self._safe_write(ws, 33, 4, f'{tipo_ducto} {tramo}')
            self._safe_write(ws, 34, 4, longitud)
            self._safe_write(ws, 35, 4, diametro)
            self._safe_write(ws, 36, 4, recubrimiento)
            # Criteria 15 VAC
            self._safe_write(ws, 42, 5, 0)
            self._safe_write(ws, 43, 5, max_abscisa)
            self._safe_write(ws, 42, 6, 15)
            self._safe_write(ws, 43, 6, 15)
            # Observation
            vacs = [p.get('vac', 0) for p in potenciales if p.get('vac') is not None]
            cumple = all(v <= 15 for v in vacs) if vacs else True
            supera_text = 'no superan' if cumple else 'superan'
            obs_vac = (f'Los potenciales AC registrados en {tipo_ducto} {tramo} {supera_text} '
                      f'el limite establecido en la norma NACE SP0177-19 numeral 5.2.1.1 '
                      f'"Los límites de seguridad los determinará un personal calificado y '
                      f'estos no deben superar los 15VAC con respecto a una tierra local, '
                      f'en este caso al electrodo de Cu/CUSO4" en los '
                      f'{longitud:03.0f} Km inspeccionados.')
            self._safe_write(ws, 32, 6, obs_vac)

        self.ajustar_graficas(potenciales)

    def fill_hallazgos(self, hallazgos: list, info: dict):
        """Fill Hallazgos sheet
        
        info keys: fecha, gasoducto, tramo, tipo_inspeccion, contrato, contratista, ot, inspector
        Each hallazgo: abscisa_inicio, abscisa_fin, longitud, gasoducto, tramo,
                       lat_inicio, lon_inicio, lat_fin, lon_fin, fecha, tipo, descripcion
        """
        ws = self.ws_hallazgos
        # Header info (rows 6-9)
        self._safe_write(ws, 6, 3, info.get('fecha', ''))
        self._safe_write(ws, 6, 12, info.get('tipo_inspeccion', 'Inspección PAP'))
        self._safe_write(ws, 7, 3, info.get('gasoducto', ''))
        self._safe_write(ws, 7, 12, info.get('contrato', ''))
        self._safe_write(ws, 8, 3, info.get('tramo', ''))
        self._safe_write(ws, 8, 12, info.get('contratista', ''))
        self._safe_write(ws, 9, 3, info.get('inspector', ''))
        self._safe_write(ws, 9, 12, info.get('ot', ''))

        if not hallazgos:
            return

        n_prefilled = 6
        start_row = 18
        
        # Clear default text in prefilled rows
        for r in range(start_row, start_row + n_prefilled):
            self._safe_write(ws, r, 1, '')

        # Insert rows if we have more than prefilled
        if len(hallazgos) > n_prefilled:
            ws.insert_rows(start_row + n_prefilled, len(hallazgos) - n_prefilled)
            for r in range(start_row + n_prefilled, start_row + len(hallazgos)):
                self._copy_row_style(ws, start_row, r, 1, 13)

        for i, h in enumerate(hallazgos):
            row = start_row + i
            
            # Prefer abscisa_val for numeric formatting if available
            abs_ini = h.get('abscisa_val', h.get('abscisa_inicio', h.get('abscisa', '')))
            abs_fin = h.get('abscisa_fin', '')
            
            self._safe_write(ws, row, 1, i + 1)                               # A - ITEM
            self._safe_write(ws, row, 2, abs_ini)                              # B
            self._safe_write(ws, row, 3, abs_fin)                              # C
            self._safe_write(ws, row, 4, h.get('longitud', ''))                # D
            self._safe_write(ws, row, 5, h.get('gasoducto', info.get('gasoducto', '')))  # E
            self._safe_write(ws, row, 6, h.get('tramo', info.get('tramo', '')))           # F
            self._safe_write(ws, row, 7, h.get('lat_inicio', h.get('lat', '')))  # G
            self._safe_write(ws, row, 8, h.get('lon_inicio', h.get('lon', '')))  # H
            self._safe_write(ws, row, 9, h.get('lat_fin', ''))                   # I
            self._safe_write(ws, row, 10, h.get('lon_fin', ''))                  # J
            self._safe_write(ws, row, 11, h.get('fecha', info.get('fecha', '')))  # K
            self._safe_write(ws, row, 12, h.get('tipo', ''))                   # L
            self._safe_write(ws, row, 13, h.get('descripcion', ''))            # M
            
        # Clear unused prefilled rows
        if len(hallazgos) < n_prefilled:
            for r in range(start_row + len(hallazgos), start_row + n_prefilled):
                for c in range(1, 14):
                    self._safe_write(ws, r, c, '')

    def fill_rectificadores(self, rectificadores: list):
        """Fill rectifier parameters in Informe sheet (rows 80+)
        
        Each rect: nombre, voltaje_nominal, corriente_nominal,
                   vdc_salida, idc_salida, disponibilidad_v, disponibilidad_i,
                   taps, pot_on_off_text, corriente_neg
        """
        ws = self.ws_informe
        for i, r in enumerate(rectificadores):
            row = 80 + i
            if i > 0:
                self._copy_row_style(ws, 80, row, 2, 34)
                
            self._safe_write(ws, row, 2, r.get('nombre', ''))                # B - URPC
            self._safe_write(ws, row, 5, r.get('voltaje_nominal'))            # E - V nominal
            self._safe_write(ws, row, 8, r.get('corriente_nominal'))          # H - I nominal
            # Datos de última inspección
            ultima = r.get('ultima_inspeccion', {})
            self._safe_write(ws, row, 11, ultima.get('vdc_salida'))           # K - V operac.
            self._safe_write(ws, row, 14, ultima.get('idc_salida'))           # N - I operac.
            self._safe_write(ws, row, 17, ultima.get('disponibilidad_v'))     # Q - Disp V%
            self._safe_write(ws, row, 20, ultima.get('disponibilidad_i'))     # T - Disp I%
            self._safe_write(ws, row, 21, ultima.get('taps', ''))             # U - TAPS
            
            # Datos de conexión a estructura
            conexion = r.get('conexion_estructura', {})
            pot_on = conexion.get('pot_on', '')
            pot_off = conexion.get('pot_off', '')
            
            # Potencial ON-OFF formatted text
            if pot_on and pot_off:
                pot_text = f'ON: {pot_on}\nOFF: {pot_off}'
            else:
                pot_text = '-'
            self._safe_write(ws, row, 23, pot_text)                           # W - NEG 1
            self._safe_write(ws, row, 24, '-')                                # X - NEG 2
            self._safe_write(ws, row, 27, '-')                                # AA - NEG 3
            self._safe_write(ws, row, 29, conexion.get('corriente', ''))      # AC - NEG 1 A
            self._safe_write(ws, row, 32, '-')                                # AF - NEG 2 A
            self._safe_write(ws, row, 34, '-')                                # AH - NEG 3 A

    def fill_aislamientos(self, aislamientos: list):
        """Fill Aislamientos sheet data starting at row 13
        
        Each aislamiento: abscisado, tag, clase, diametro, presion, temperatura,
                          tipo_brida, num_pernos, diam_pernos, tipo_aislamiento,
                          pct_aislamiento, pot_on_arriba, pot_off_arriba,
                          pot_on_abajo, pot_off_abajo, dif_on, dif_off,
                          diagnostico, lat, lon, observaciones
        """
        if not self.ws_aislamientos or not aislamientos:
            return
        ws = self.ws_aislamientos
        
        n_prefilled = 6
        start_row = 13
        
        if len(aislamientos) > n_prefilled:
            ws.insert_rows(start_row + n_prefilled, len(aislamientos) - n_prefilled)
            for r in range(start_row + n_prefilled, start_row + len(aislamientos)):
                self._copy_row_style(ws, start_row, r, 1, 22)
        
        for i, a in enumerate(aislamientos):
            row = start_row + i
                
            self._safe_write(ws, row, 1, i + 1)
            self._safe_write(ws, row, 2, a.get('abscisa_val', a.get('abscisado', '')))
            self._safe_write(ws, row, 3, a.get('tag', '-'))
            self._safe_write(ws, row, 4, a.get('clase', ''))
            self._safe_write(ws, row, 5, a.get('diametro', ''))
            self._safe_write(ws, row, 6, a.get('presion', '-'))
            self._safe_write(ws, row, 7, a.get('temperatura', '-'))
            self._safe_write(ws, row, 8, a.get('tipo_brida', ''))
            self._safe_write(ws, row, 9, a.get('num_pernos', ''))
            self._safe_write(ws, row, 10, a.get('diam_pernos', ''))
            self._safe_write(ws, row, 11, a.get('tipo_aislamiento', ''))
            self._safe_write(ws, row, 12, a.get('pct_aislamiento', ''))
            self._safe_write(ws, row, 13, a.get('pot_on_arriba'))
            self._safe_write(ws, row, 14, a.get('pot_off_arriba'))
            self._safe_write(ws, row, 15, a.get('pot_on_abajo'))
            self._safe_write(ws, row, 16, a.get('pot_off_abajo'))
            self._safe_write(ws, row, 17, a.get('dif_on'))
            self._safe_write(ws, row, 18, a.get('dif_off'))
            self._safe_write(ws, row, 19, a.get('diagnostico', ''))
            self._safe_write(ws, row, 20, a.get('lat'))
            self._safe_write(ws, row, 21, a.get('lon'))
            self._safe_write(ws, row, 22, a.get('observaciones', ''))
            
        # Clear unused prefilled rows
        if len(aislamientos) < n_prefilled:
            for r in range(start_row + len(aislamientos), start_row + n_prefilled):
                for c in range(1, 23):
                    self._safe_write(ws, r, c, '')

    def fill_inspecciones(self, marco_h: list = None, ce: list = None,
                          anodos: list = None, cupones_ir: list = None,
                          cupones_grav: list = None, pe: list = None,
                          tramos_aereos: list = None, tramos_no_insp: list = None):
        """Fill special inspection sheets with data or leave defaults"""
        
        # Marco H
        if marco_h and self.ws_marco_h:
            ws = self.ws_marco_h
            # Clear default text
            self._safe_write(ws, 12, 16, '')
            self._safe_write(ws, 13, 16, '')
            
            for i, m in enumerate(marco_h):
                row = 12 + i
                self._safe_write(ws, row, 1, i + 1)
                self._safe_write(ws, row, 2, m.get('abscisado', ''))
                self._safe_write(ws, row, 3, m.get('fecha', ''))
                self._safe_write(ws, row, 4, m.get('pot_on_gasoducto', ''))
                self._safe_write(ws, row, 5, m.get('pot_off_gasoducto', ''))
                self._safe_write(ws, row, 6, m.get('pot_on_marco', ''))
                self._safe_write(ws, row, 7, m.get('pot_off_marco', ''))
                self._safe_write(ws, row, 8, m.get('aislado', ''))
                self._safe_write(ws, row, 9, m.get('dif_on', ''))
                self._safe_write(ws, row, 10, m.get('dif_off', ''))
                self._safe_write(ws, row, 11, 'Aislado' if m.get('aislado') else 'Corto')
                self._safe_write(ws, row, 12, m.get('estado_aislante', 'Buen Estado'))
                self._safe_write(ws, row, 13, m.get('lat', ''))
                self._safe_write(ws, row, 14, m.get('lon', ''))
                self._safe_write(ws, row, 15, m.get('estado_pintura', 'Bueno'))
                self._safe_write(ws, row, 16, m.get('observaciones', ''))

        # Inventario Tramos Aéreos
        if tramos_aereos and self.ws_tramos_aereos:
            ws = self.ws_tramos_aereos
            self._safe_write(ws, 12, 1, '')  # Clear default
            for i, t in enumerate(tramos_aereos):
                row = 12 + i
                self._safe_write(ws, row, 1, i + 1)
                self._safe_write(ws, row, 2, t.get('inicio_abscisa', ''))
                self._safe_write(ws, row, 3, t.get('fin_abscisa', ''))
                self._safe_write(ws, row, 4, t.get('longitud', ''))
                self._safe_write(ws, row, 5, t.get('gasoducto', ''))
                self._safe_write(ws, row, 6, t.get('tramo', ''))
                self._safe_write(ws, row, 7, t.get('lat_inicio'))
                self._safe_write(ws, row, 8, t.get('lon_inicio'))
                self._safe_write(ws, row, 9, t.get('lat_fin'))
                self._safe_write(ws, row, 10, t.get('lon_fin'))
                self._safe_write(ws, row, 11, t.get('fecha', ''))
                self._safe_write(ws, row, 12, t.get('observaciones', ''))

        # Tramos no inspeccionados
        if tramos_no_insp and self.ws_tramos_no_insp:
            ws = self.ws_tramos_no_insp
            for i, t in enumerate(tramos_no_insp):
                row = 12 + i
                self._safe_write(ws, row, 1, i + 1)
                self._safe_write(ws, row, 2, t.get('abscisa_inicio', ''))
                self._safe_write(ws, row, 3, t.get('abscisa_fin', ''))
                self._safe_write(ws, row, 4, t.get('longitud', ''))
                self._safe_write(ws, row, 5, t.get('gasoducto', ''))
                self._safe_write(ws, row, 6, t.get('tramo', ''))
                self._safe_write(ws, row, 7, t.get('lat_inicio'))
                self._safe_write(ws, row, 8, t.get('lon_inicio'))
                self._safe_write(ws, row, 9, t.get('lat_fin'))
                self._safe_write(ws, row, 10, t.get('lon_fin'))
                self._safe_write(ws, row, 11, t.get('fecha', ''))
                self._safe_write(ws, row, 12, t.get('justificacion', ''))

    def fill_conclusiones(self, conclusiones: list):
        """Fill Conclusions section"""
        ws = self.ws_informe
        
        # Conclusiones
        start_row = 88
        for r in range(70, 100):
            val = ws.cell(row=r, column=1).value
            if val and isinstance(val, str) and 'CONCLUSIONES' in val.upper():
                start_row = r + 1
                break
                
        for i, conc in enumerate(conclusiones[:6]):
            self._safe_write(ws, start_row + i, 1, f"• {conc}")
            
    def fill_recomendaciones(self, recomendaciones: list):
        """Fill Recommendations section"""
        ws = self.ws_informe
        # Recomendaciones
        start_row = 95
        for r in range(80, 110):
            val = ws.cell(row=r, column=1).value
            if val and isinstance(val, str) and 'RECOMENDACIONES' in val.upper():
                start_row = r + 1
                break
                
        for i, rec in enumerate(recomendaciones[:5]):
            self._safe_write(ws, start_row + i, 1, f"• {rec}")

    def fill_firmas(self, elaboro: dict, reviso: dict, aprobo: dict):
        """Fill signatures in ALL sheets
        
        Each dict has: nombre, cargo, empresa
        """
        # Informe sheet
        ws = self.ws_informe
        self._safe_write(ws, 104, 4, elaboro.get('nombre', ''))
        self._safe_write(ws, 105, 4, elaboro.get('cargo', ''))
        self._safe_write(ws, 106, 4, elaboro.get('empresa', ''))
        self._safe_write(ws, 104, 15, reviso.get('nombre', ''))
        self._safe_write(ws, 105, 15, reviso.get('cargo', ''))
        self._safe_write(ws, 106, 15, reviso.get('empresa', ''))
        self._safe_write(ws, 104, 24, aprobo.get('nombre', ''))
        self._safe_write(ws, 105, 24, aprobo.get('cargo', ''))
        self._safe_write(ws, 106, 24, aprobo.get('empresa', ''))

        # Potenciales PAP
        ws = self.ws_potenciales
        start_row = 77
        for r in range(12, 500):
            val = ws.cell(row=r, column=4).value
            if val and isinstance(val, str) and 'ELABORÓ' in val.upper():
                start_row = r + 1
                break
        self._safe_write(ws, start_row, 4, elaboro.get('nombre', ''))
        self._safe_write(ws, start_row + 1, 4, elaboro.get('cargo', ''))
        self._safe_write(ws, start_row + 2, 4, elaboro.get('empresa', ''))
        self._safe_write(ws, start_row, 15, reviso.get('nombre', ''))
        self._safe_write(ws, start_row + 1, 15, reviso.get('cargo', ''))
        self._safe_write(ws, start_row + 2, 15, reviso.get('empresa', ''))
        self._safe_write(ws, start_row, 24, aprobo.get('nombre', ''))
        self._safe_write(ws, start_row + 1, 24, aprobo.get('cargo', ''))
        self._safe_write(ws, start_row + 2, 24, aprobo.get('empresa', ''))

        # Hallazgos
        if self.ws_hallazgos:
            ws = self.ws_hallazgos
            start_row = 26
            for r in range(18, 500):
                val = ws.cell(row=r, column=3).value
                if val and isinstance(val, str) and 'ELABORÓ' in val.upper():
                    start_row = r + 1
                    break
            self._safe_write(ws, start_row, 3, elaboro.get('nombre', ''))
            self._safe_write(ws, start_row + 1, 3, elaboro.get('cargo', ''))
            self._safe_write(ws, start_row + 2, 3, elaboro.get('empresa', ''))
            self._safe_write(ws, start_row, 7, reviso.get('nombre', ''))
            self._safe_write(ws, start_row + 1, 7, reviso.get('cargo', ''))
            self._safe_write(ws, start_row + 2, 7, reviso.get('empresa', ''))
            self._safe_write(ws, start_row, 12, aprobo.get('nombre', ''))
            self._safe_write(ws, start_row + 1, 12, aprobo.get('cargo', ''))
            self._safe_write(ws, start_row + 2, 12, aprobo.get('empresa', ''))

        # Aislamientos
        if self.ws_aislamientos:
            ws = self.ws_aislamientos
            start_row = 19
            for r in range(15, 200):
                val = ws.cell(row=r, column=1).value
                if val and isinstance(val, str) and 'NOMBRE' in val.upper():
                    start_row = r
                    break
                    
            self._safe_write(ws, start_row, 3, elaboro.get('nombre', ''))
            self._safe_write(ws, start_row + 1, 3, elaboro.get('cargo', ''))
            self._safe_write(ws, start_row + 2, 3, elaboro.get('empresa', ''))
            self._safe_write(ws, start_row, 8, reviso.get('nombre', ''))
            self._safe_write(ws, start_row + 1, 8, reviso.get('cargo', ''))
            self._safe_write(ws, start_row + 2, 8, reviso.get('empresa', ''))
            self._safe_write(ws, start_row, 18, aprobo.get('nombre', ''))
            self._safe_write(ws, start_row + 1, 18, aprobo.get('cargo', ''))
            self._safe_write(ws, start_row + 2, 18, aprobo.get('empresa', ''))


    def fill_aislamientos(self, aislamientos: list):
        """Fill Aislamientos data table starting at row 13"""
        ws = self.ws_aislamientos
        if not ws or not aislamientos:
            return
            
        for i, a in enumerate(aislamientos):
            row = 13 + i
            if i > 0:
                ws.insert_rows(row)
                self._copy_row_style(ws, 13, row, 1, 22)
                
            self._safe_write(ws, row, 1, i + 1)                              # A - ÍTEM
            self._safe_write(ws, row, 2, a.get('abscisado', ''))              # B - ABSCISADO
            self._safe_write(ws, row, 3, a.get('tag', ''))                    # C - TAG
            self._safe_write(ws, row, 4, a.get('clase', ''))                  # D - CLASS
            self._safe_write(ws, row, 5, a.get('diametro', ''))               # E - DIÁMETRO NOMINAL
            self._safe_write(ws, row, 6, a.get('presion', ''))                # F - PRESIÓN
            self._safe_write(ws, row, 7, a.get('temperatura', ''))            # G - TEMPERATURA
            self._safe_write(ws, row, 8, a.get('tipo_brida', ''))             # H - TIPO DE BRIDA
            self._safe_write(ws, row, 9, a.get('numero_pernos', ''))          # I - NÚMERO DE PERNOS
            self._safe_write(ws, row, 10, a.get('diametro_pernos', ''))       # J - DIÁMETRO DE PERNOS
            self._safe_write(ws, row, 11, a.get('tipo_aislamiento', ''))      # K - TIPO DE AISLAMIENTO
            self._safe_write(ws, row, 12, a.get('porcentaje_aislamiento', '')) # L - % AISLAMIENTO
            self._safe_write(ws, row, 13, a.get('pot_on_arriba', ''))         # M - AGUAS ARRIBA POT ON
            self._safe_write(ws, row, 14, a.get('pot_off_arriba', ''))        # N - AGUAS ARRIBA POT OFF
            self._safe_write(ws, row, 15, a.get('pot_on_abajo', ''))          # O - AGUAS ABAJO POT ON
            self._safe_write(ws, row, 16, a.get('pot_off_abajo', ''))         # P - AGUAS ABAJO POT OFF
            self._safe_write(ws, row, 17, a.get('diferencia', ''))            # Q - DIFERENCIA
            self._safe_write(ws, row, 18, "")                                 # R - DIFERENCIA INSTANT OFF
            self._safe_write(ws, row, 19, a.get('diagnostico', ''))           # S - DIAGNÓSTICO
            self._safe_write(ws, row, 20, a.get('latitud', ''))               # T - LATITUD
            self._safe_write(ws, row, 21, a.get('longitud', ''))              # U - LONGITUD
            self._safe_write(ws, row, 22, a.get('observaciones', ''))         # V - OBSERVACIONES


    def fill_comentario_huella(self, comentario: str):
        """Fill oscilloscopic footprint comment in Informe row 74"""
        self._safe_write(self.ws_informe, 74, 6, comentario)

    @staticmethod
    def _nice_floor(v, step):
        return math.floor(v / step) * step

    @staticmethod
    def _nice_ceil(v, step):
        return math.ceil(v / step) * step

    def ajustar_graficas(self, potenciales):
        """Ajusta rango de series y ejes de las 3 graficas a los datos reales.

        - Series 'Potenciales PAP' de fila 12 (primer poste) a 11+N.
        - Eje X: 0 hasta la abscisa maxima (redondeada a 100 m).
        - Eje Y: min/max de los datos + 10% margen, manteniendo visibles las
          lineas de criterio. Elimina las series #REF! rotas del template.
        """
        import re
        if not potenciales:
            return
        n = len(potenciales)
        last = 11 + n
        max_absc = max((p.get('abscisa') or 0) for p in potenciales)
        x_max = self._nice_ceil(max_absc, 100) if max_absc > 0 else 100

        cfgs = [
            (self.ws_grafica_vdc,    ['on_mv', 'off_mv'], [-850, -1200], 100),
            (self.ws_grafica_interf, ['ir_on_off'],       [50],          10),
            (self.ws_grafica_vac,    ['vac'],             [15],          2),
        ]

        def _ref_ok(s):
            for part in (s.xVal, s.yVal):
                f = part.numRef.f if (part and part.numRef) else None
                if f is None or '#REF!' in f:
                    return False
            return True

        for ws, keys, criterios, step in cfgs:
            if ws is None or not getattr(ws, '_charts', None):
                continue
            chart = ws._charts[0]

            series_validas = [s for s in chart.series if _ref_ok(s)]
            for s in series_validas:
                fx = s.xVal.numRef.f
                if 'Potenciales PAP' in fx:
                    s.xVal.numRef.f = re.sub(r'\$B\$\d+:\$B\$\d+',
                                             f'$B$12:$B${last}', fx)
                    col = re.search(r'\$([A-Z]+)\$\d+:', s.yVal.numRef.f).group(1)
                    s.yVal.numRef.f = f"'Potenciales PAP'!${col}$12:${col}${last}"
                    if s.xVal.numRef.numCache:
                        s.xVal.numRef.numCache = None
                    if s.yVal.numRef.numCache:
                        s.yVal.numRef.numCache = None
            chart.series = series_validas

            chart.x_axis.scaling.min = 0
            chart.x_axis.scaling.max = x_max

            vals = [p.get(k) for k in keys for p in potenciales if p.get(k) is not None]
            if vals:
                lo = min(vals + criterios)
                hi = max(vals + criterios)
                span = (hi - lo) or 1
                margin = span * 0.1
                chart.y_axis.scaling.min = self._nice_floor(lo - margin, step)
                chart.y_axis.scaling.max = self._nice_ceil(hi + margin, step)

    def save(self, output_path: str):
        """Save the completed report"""
        self.wb.save(output_path)
        return output_path

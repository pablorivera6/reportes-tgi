import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
import os
from generator import resource_path
from ortografia import corregir_campo

class PPMGenerator:
    def __init__(self, template_path: str = None):
        if template_path is None:
            template_path = resource_path("PPM.XLSX")
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"No se encontró la plantilla PPM en: {template_path}")
        self.template_path = template_path
        self.wb = openpyxl.load_workbook(template_path)
        self.ws = self.wb['CIPS - PAP'] if 'CIPS - PAP' in self.wb.sheetnames else self.wb.active

    def _safe_write(self, row, col, value):
        try:
            cell = self.ws.cell(row=row, column=col)
            cell.value = value
            # Optionally set a basic style here if needed
        except Exception as e:
            pass

    def _limpiar_filas_datos(self):
        """Borra cualquier dato remanente del template (filas 2+): si el
        archivo base se guardó con datos de una inspección anterior, no deben
        arrastrarse al PPM generado."""
        for row in self.ws.iter_rows(min_row=2, max_row=self.ws.max_row,
                                     min_col=1, max_col=18):
            for cell in row:
                if cell.value is not None:
                    cell.value = None

    def generate(self, info: dict, potenciales: list, aislamientos: list,
                 output_path: str, cips: list = None):
        # The template has headers in row 1, data starts at row 2
        self._limpiar_filas_datos()

        # We need to map everything into rows
        current_row = 2

        # 1. Add potential points
        for pot in potenciales:
            self._write_row(current_row, info, pot)
            current_row += 1

        # 1b. Add CIPS points (mismo contenido que la hoja CIPS del informe)
        for c in (cips or []):
            on = c.get('on_mv')
            off = c.get('off_mv')
            ir = None
            if c.get('on_limpio') is not None and c.get('off_limpio') is not None:
                ir = c['on_limpio'] - c['off_limpio']
            elif on is not None and off is not None:
                ir = on - off
            self._write_row(current_row, info, {
                'abscisa': c.get('abscisa_val'),
                'lat': c.get('lat', ''),
                'lon': c.get('lon', ''),
                'alt': '',
                'on_mv': on,
                'off_mv': off,
                'potencial_natural': None,
                'polarizacion': None,
                'observaciones': c.get('observaciones', ''),
                'ir_on_off': ir,
                'fecha': c.get('fecha'),
            })
            current_row += 1

        # 2. Add isolation points
        for ais in aislamientos:
            pot_pseudo = {
                'abscisa': ais.get('abscisado', 0),
                'lat': ais.get('latitud', ''),
                'lon': ais.get('longitud', ''),
                'alt': '',
                'on_mv': ais.get('pot_on_arriba'),
                'off_mv': ais.get('pot_off_arriba'),
                'potencial_natural': None,
                'polarizacion': None,
                'observaciones': ais.get('observaciones', ''),
                'ir_on_off': None
            }
            # Compute IR drop if both exist
            if pot_pseudo['on_mv'] is not None and pot_pseudo['off_mv'] is not None:
                try:
                    pot_pseudo['ir_on_off'] = float(pot_pseudo['on_mv']) - float(pot_pseudo['off_mv'])
                except:
                    pass
                    
            self._write_row(current_row, info, pot_pseudo)
            current_row += 1
            
        self.wb.save(output_path)

    def _write_row(self, row, info, data):
        # ['ENGROUTEID', 'No Contrato', 'Distrito', 'Tipo de Tramo', 'Tramo', 
        #  'Fecha de Inspección', 'ABCISA', 'Center line', 'Latitud', 'Longitud', 
        #  'Altitud', 'P On mV', 'P Off mV', 'P Natural mV', 'Polarizacion mV', 
        #  'Dirección de la inspección', 'Comentario', 'IR On-Off mV']
        
        self._safe_write(row, 1, info.get('route_id', ''))
        self._safe_write(row, 2, info.get('contrato', ''))
        self._safe_write(row, 3, info.get('distrito', ''))
        self._safe_write(row, 4, info.get('tipo_ducto', ''))
        self._safe_write(row, 5, info.get('tramo', ''))
        # Fecha del día en que se tomó el punto (si viene por dato); si no, la
        # fecha general del informe.
        self._safe_write(row, 6, data.get('fecha') or info.get('fecha', ''))
        
        # ABCISA is usually an integer in meters? We'll write exactly what's there (should be integer normally)
        abscisa = data.get('abscisa', '')
        if isinstance(abscisa, str):
            # If abscisa is "km+m", let's extract the integer meter value if possible, or leave as is
            pass
        self._safe_write(row, 7, abscisa)
        
        self._safe_write(row, 8, None) # Center line
        self._safe_write(row, 9, data.get('lat', ''))
        self._safe_write(row, 10, data.get('lon', ''))
        self._safe_write(row, 11, data.get('alt', ''))
        self._safe_write(row, 12, data.get('on_mv'))
        self._safe_write(row, 13, data.get('off_mv'))
        self._safe_write(row, 14, data.get('potencial_natural'))
        self._safe_write(row, 15, data.get('polarizacion'))
        
        # Default Ascendente for now?
        self._safe_write(row, 16, 'Ascendente')
        
        self._safe_write(row, 17, corregir_campo(data.get('observaciones', '')))
        self._safe_write(row, 18, data.get('ir_on_off'))

import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import google.generativeai as genai

class PhotoProcessor:
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)
            # Try multiple models if one is not found
            self.model_name = 'gemini-1.5-flash'
        else:
            self.model = None

    def get_exif_data(self, image_path: str) -> dict:
        """Extract EXIF data including GPS and Datetime from a photo"""
        try:
            img = Image.open(image_path)
            exif_raw = img._getexif()
            if not exif_raw:
                return {}
            
            exif = {}
            for tag_id, value in exif_raw.items():
                tag = TAGS.get(tag_id, tag_id)
                exif[tag] = value
                
            return exif
        except Exception as e:
            print(f"Error reading EXIF from {image_path}: {e}")
            return {}

    def get_gps_coordinates(self, exif_data: dict) -> tuple:
        """Returns (lat, lon) in decimal degrees or (None, None)"""
        if 'GPSInfo' not in exif_data:
            return None, None
            
        gps_info = {}
        for key in exif_data['GPSInfo'].keys():
            decode = GPSTAGS.get(key, key)
            gps_info[decode] = exif_data['GPSInfo'][key]
            
        def _convert_to_degrees(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)

        lat = None
        lon = None
        
        if 'GPSLatitude' in gps_info and 'GPSLongitude' in gps_info:
            lat = _convert_to_degrees(gps_info['GPSLatitude'])
            if gps_info.get('GPSLatitudeRef') != 'N':
                lat = -lat
                
            lon = _convert_to_degrees(gps_info['GPSLongitude'])
            if gps_info.get('GPSLongitudeRef') != 'E':
                lon = -lon
                
        return lat, lon

    def get_datetime(self, exif_data: dict) -> str:
        """Returns formatted datetime string if available"""
        if 'DateTimeOriginal' in exif_data:
            # Format is usually 'YYYY:MM:DD HH:MM:SS'
            dt = str(exif_data['DateTimeOriginal'])
            return dt.replace(':', '-', 2)
        return ""

    def classify_image_with_ai(self, image_path: str) -> tuple:
        """Use Gemini Vision to classify the pipeline finding. Returns (Tipo, Descripción)"""
        if not self.api_key:
            return "Hallazgo Fotográfico a Revisar", "Foto sin descripción. (Falta API Key de Gemini)"
            
        try:
            img = Image.open(image_path)
            prompt = (
                "Eres un inspector experto de gasoductos en Colombia. Lee atentamente la marca de agua (texto escrito sobre la imagen) y mira la infraestructura. "
                "Tu objetivo es clasificar la foto ÚNICAMENTE si menciona o muestra claramente una de estas opciones permitidas:\n"
                "1. Cruce de vía\n"
                "2. Cruce de caño\n"
                "3. Línea de media, alta o baja tensión\n"
                "4. Tramo enmontado\n"
                "5. Propiedad privada\n"
                "6. Cultivo\n"
                "Si el texto en la imagen o el contenido NO corresponde a NINGUNA de estas 6 opciones específicas, debes descartarla respondiendo 'Descartar'. "
                "Responde en EXACTAMENTE dos líneas.\n"
                "Línea 1: El Tipo (escribe exactamente una de las 6 opciones anteriores, o la palabra 'Descartar').\n"
                "Línea 2: Una descripción muy corta de lo que leíste en la marca de agua o lo que se ve."
            )
            
            # Buscar dinámicamente qué modelos soporta su API Key
            models_to_try = []
            try:
                available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                # Priorizar 1.5 flash, luego 1.5 pro, luego 1.0 pro
                for pref in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-1.0-pro', 'models/gemini-pro']:
                    if pref in available or pref.replace('models/', '') in available:
                        models_to_try.append(pref)
                if not models_to_try and available:
                    models_to_try.append(available[0]) # usar cualquiera que soporte generateContent
            except Exception as e:
                pass # Si falla list_models, usar fallback manual
                
            if not models_to_try:
                models_to_try = [
                    'gemini-1.5-flash',
                    'models/gemini-1.5-flash',
                    'gemini-1.5-pro'
                ]
            
            response = None
            errors = []
            for m_name in models_to_try:
                try:
                    model = genai.GenerativeModel(m_name)
                    response = model.generate_content([prompt, img])
                    break
                except Exception as e:
                    errors.append(f"{m_name}: {str(e)}")
                    continue
                    
            if not response:
                error_msg = " | ".join(errors)
                raise Exception(error_msg)
                
            lines = response.text.strip().split('\n')
            
            tipo = lines[0].replace('Tipo:', '').replace('Línea 1:', '').strip()
            desc = lines[1].replace('Descripción:', '').replace('Línea 2:', '').strip() if len(lines) > 1 else ""
            
            # Limpiar markdown u asteriscos si la IA los puso
            tipo = tipo.replace('*', '').strip()
            desc = desc.replace('*', '').strip()
            
            return tipo, desc
        except Exception as e:
            print(f"Error AI Vision for {image_path}: {e}")
            return "Hallazgo Fotográfico (Error IA)", str(e)

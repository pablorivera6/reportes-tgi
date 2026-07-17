import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
import math
from typing import Optional, List, Dict, Tuple
import re

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS points in meters."""
    R = 6371000  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.current_text = ''
        self.current_row = []
        self.rows = []
        
    def handle_starttag(self, tag, attrs):
        if tag == 'td':
            self.in_td = True
            self.current_text = ''
    
    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_td = False
            self.current_row.append(self.current_text.strip())
        elif tag == 'tr':
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = []
    
    def handle_data(self, data):
        if self.in_td:
            self.current_text += data

class KMZPipelineLoader:
    def __init__(self, kmz_path: str):
        self.pipelines: Dict[str, List[Tuple[float, float]]] = {}
        self.pks: Dict[str, List[Dict]] = {}
        self.urpcs: List[Dict] = []
        self._parse(kmz_path)
        
        # Sort PKs by meter value
        for route_id in self.pks:
            self.pks[route_id].sort(key=lambda x: x['pk_meters'])

    def _parse_abscisa_to_meters(self, text: str) -> int:
        match = re.search(r'(\d+)\+(\d+)', text)
        if match:
            return int(match.group(1)) * 1000 + int(match.group(2))
        return 0

    def _parse(self, kmz_path: str):
        with zipfile.ZipFile(kmz_path) as kmz:
            kml_data = kmz.read('doc.kml').decode('utf-8', errors='replace')
            kml_data = kml_data.replace(
                'xsi:schemaLocation',
                'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation',
                1
            )
            
            root = ET.fromstring(kml_data)
            ns = {'kml': 'http://www.opengis.net/kml/2.2', 'gx': 'http://www.google.com/kml/ext/2.2'}
            
            for folder in root.iter('{http://www.opengis.net/kml/2.2}Folder'):
                name_el = folder.find('kml:name', ns)
                if name_el is None:
                    continue
                folder_name = name_el.text
                
                # 1. Pipelines
                if 'RED_TGI' in folder_name:
                    for pm in folder.findall('kml:Placemark', ns):
                        pm_name_el = pm.find('kml:name', ns)
                        pm_name = pm_name_el.text if pm_name_el is not None else 'NA'
                        
                        route_id = 'NA'
                        desc_el = pm.find('kml:description', ns)
                        if desc_el is not None and desc_el.text:
                            parser = TableParser()
                            parser.feed(desc_el.text)
                            for row in parser.rows:
                                if len(row) == 2 and 'Route' in row[0]:
                                    route_id = row[1]
                        
                        if route_id == 'NA' or route_id == '<Null>':
                            route_id = pm_name

                        ls = pm.find('.//kml:LineString', ns)
                        if ls is not None:
                            coords_el = ls.find('kml:coordinates', ns)
                            if coords_el is not None and coords_el.text:
                                points = coords_el.text.strip().split()
                                coords = []
                                for pt in points:
                                    parts = pt.split(',')
                                    if len(parts) >= 2:
                                        # KML is lon, lat
                                        coords.append((float(parts[1]), float(parts[0])))
                                if coords:
                                    self.pipelines[route_id] = coords
                
                # 2. PKs
                elif 'PK_WGS84' in folder_name:
                    for pm in folder.findall('kml:Placemark', ns):
                        desc_el = pm.find('kml:description', ns)
                        if desc_el is not None and desc_el.text:
                            parser = TableParser()
                            parser.feed(desc_el.text)
                            data = {}
                            for row in parser.rows:
                                if len(row) == 2:
                                    data[row[0]] = row[1]
                            
                            route_id = data.get('Route_ID', 'NA')
                            pk_str = data.get('PK', '0+000')
                            pk_meters = self._parse_abscisa_to_meters(pk_str)
                            
                            pt = pm.find('.//kml:Point', ns)
                            if pt is not None:
                                coords_el = pt.find('kml:coordinates', ns)
                                if coords_el is not None and coords_el.text:
                                    parts = coords_el.text.strip().split(',')
                                    if len(parts) >= 2:
                                        lat, lon = float(parts[1]), float(parts[0])
                                        if route_id not in self.pks:
                                            self.pks[route_id] = []
                                        self.pks[route_id].append({
                                            'name': pk_str,
                                            'pk_meters': pk_meters,
                                            'lat': lat,
                                            'lon': lon
                                        })

    def get_pipeline_coords(self, route_id: str) -> List[Tuple[float, float]]:
        return self.pipelines.get(route_id, [])

    def get_pks_for_route(self, route_id: str) -> List[Dict]:
        return self.pks.get(route_id, [])

    def get_all_route_ids(self) -> List[str]:
        return list(self.pipelines.keys())

    def find_route_by_name(self, name: str) -> Optional[str]:
        name_lower = name.lower()
        # Direct match
        for rid in self.pipelines.keys():
            if name_lower in rid.lower() or rid.lower() in name_lower:
                return rid
                
        # Acronym match: "troncal mariquita letras" -> "t_mar_let"
        parts = [p for p in name_lower.replace('-', ' ').replace('_', ' ').split() if p]
        if len(parts) >= 2:
            # Try to build something like "t_mar_let" or "r_cai"
            prefix = parts[0][0] # 't' or 'r'
            abbr = prefix + '_' + '_'.join(p[:3] for p in parts[1:])
            for rid in self.pipelines.keys():
                if abbr in rid.lower() or rid.lower() in abbr:
                    return rid
                    
            # Try just taking the first 3 letters of each word
            abbr2 = '_'.join(p[:3] for p in parts)
            for rid in self.pipelines.keys():
                if abbr2 in rid.lower() or rid.lower() in abbr2:
                    return rid
                    
        return None

    def find_closest_route(self, lat: float, lon: float) -> str:
        best_route = None
        min_dist = float('inf')
        
        for rid, coords in self.pipelines.items():
            if not coords: continue
            # Check distance to a few sample points (start, middle, end) to be fast
            samples = [coords[0], coords[len(coords)//2], coords[-1]]
            for p_lat, p_lon in samples:
                d = haversine_distance(lat, lon, p_lat, p_lon)
                if d < min_dist:
                    min_dist = d
                    best_route = rid
        return best_route

class AbscisaCalculator:
    def __init__(self, pipeline_coords: List[Tuple[float, float]], known_pks: List[Dict]):
        self.line = pipeline_coords
        self.pks = known_pks
        self.cumulative_distances = [0.0]
        
        # Pre-compute distances along polyline
        if len(self.line) > 1:
            for i in range(1, len(self.line)):
                lat1, lon1 = self.line[i-1]
                lat2, lon2 = self.line[i]
                dist = haversine_distance(lat1, lon1, lat2, lon2)
                self.cumulative_distances.append(self.cumulative_distances[-1] + dist)

    def _project_point(self, lat: float, lon: float) -> float:
        """Project GPS point onto polyline and return raw cumulative distance"""
        if not self.line:
            return 0.0
        
        min_dist = float('inf')
        closest_cum_dist = 0.0
        
        for i in range(len(self.line) - 1):
            lat1, lon1 = self.line[i]
            lat2, lon2 = self.line[i+1]
            
            # Simple planar projection to local Cartesian
            dy = lat2 - lat1
            dx = (lon2 - lon1) * math.cos(math.radians(lat1))
            l2 = dx*dx + dy*dy
            
            py = lat - lat1
            px = (lon - lon1) * math.cos(math.radians(lat1))
            
            if l2 == 0:
                t = 0.0
            else:
                t = max(0, min(1, (px * dx + py * dy) / l2))
                
            proj_lat = lat1 + t * dy
            proj_lon = lon1 + t * (lon2 - lon1) # un-correct dx for lon
            
            dist = haversine_distance(lat, lon, proj_lat, proj_lon)
            if dist < min_dist:
                min_dist = dist
                seg_len = self.cumulative_distances[i+1] - self.cumulative_distances[i]
                closest_cum_dist = self.cumulative_distances[i] + t * seg_len
        return closest_cum_dist

    def project_coordinates(self, lat: float, lon: float) -> Tuple[float, float]:
        """Project GPS point onto polyline and return the snapped (lat, lon)"""
        if not self.line:
            return lat, lon
        
        min_dist = float('inf')
        best_proj_lat, best_proj_lon = lat, lon
        
        for i in range(len(self.line) - 1):
            lat1, lon1 = self.line[i]
            lat2, lon2 = self.line[i+1]
            
            dy = lat2 - lat1
            dx = (lon2 - lon1) * math.cos(math.radians(lat1))
            l2 = dx*dx + dy*dy
            
            py = lat - lat1
            px = (lon - lon1) * math.cos(math.radians(lat1))
            
            if l2 == 0:
                t = 0.0
            else:
                t = max(0, min(1, (px * dx + py * dy) / l2))
                
            proj_lat = lat1 + t * dy
            proj_lon = lon1 + t * (lon2 - lon1)
            
            dist = haversine_distance(lat, lon, proj_lat, proj_lon)
            if dist < min_dist:
                min_dist = dist
                best_proj_lat = proj_lat
                best_proj_lon = proj_lon
                
        return best_proj_lat, best_proj_lon

    def _calibrate_with_pks(self, raw_distance: float, lat: float, lon: float) -> int:
        if not self.pks:
            return int(raw_distance)
            
        # Find closest PK geometrically
        closest_pk = None
        min_pk_dist = float('inf')
        for pk in self.pks:
            d = haversine_distance(lat, lon, pk['lat'], pk['lon'])
            if d < min_pk_dist:
                min_pk_dist = d
                closest_pk = pk
                
        if closest_pk and min_pk_dist < 5000: # within 5km of a PK
            # Return raw distance offset by the closest PK's true distance
            # This applies a smooth calibration offset without snapping to the PK
            return int(closest_pk['pk_meters'] + (raw_distance - self._project_point(closest_pk['lat'], closest_pk['lon'])))
            
        return int(raw_distance)

    def calculate(self, lat: float, lon: float) -> int:
        if not self.line:
            return 0
        raw_dist = self._project_point(lat, lon)
        return self._calibrate_with_pks(raw_dist, lat, lon)

    def format_abscisa(self, meters: int) -> str:
        km = meters // 1000
        m = meters % 1000
        return f"{km:03d}+{m:03d}"

    @staticmethod
    def parse_abscisa(text: str) -> int:
        if not text:
            return 0
        match = re.search(r'(\d+)\+(\d+)', str(text))
        if match:
            return int(match.group(1)) * 1000 + int(match.group(2))
        try:
            return int(text)
        except ValueError:
            return 0

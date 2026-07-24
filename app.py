import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTabWidget, QLabel, QPushButton, 
                             QTableWidget, QTableWidgetItem, QFileDialog, 
                             QLineEdit, QHeaderView, QTextEdit, QCheckBox, 
                             QScrollArea, QProgressBar, QMessageBox, QComboBox,
                             QFrame, QGridLayout, QGroupBox, QDialog, 
                             QListWidget, QDialogButtonBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QLinearGradient, QBrush

from geo_utils import KMZPipelineLoader, AbscisaCalculator
from readers import FastFieldReader, EquipoReader, RectificadorReader
from generator import ReportGenerator
from conclusions import ConclusionGenerator
from photo_utils import PhotoProcessor
from cips_infra import InfraTramos

# --- Estilos Corporativos (Modern Tech Theme) ---
DARK_STYLE = """
* {
    font-family: 'Segoe UI', '-apple-system', 'Helvetica Neue', 'Inter', sans-serif;
}
QMainWindow {
    background-color: #09090b;
}
QWidget#sidebar {
    background-color: #111115;
    border-right: 1px solid rgba(255, 255, 255, 0.05);
}
QPushButton.nav-button {
    background-color: transparent;
    color: #a1a1aa;
    text-align: left;
    padding: 12px 20px;
    border: none;
    font-size: 14px;
    font-weight: 600;
    border-radius: 8px;
    margin: 4px 12px;
}
QPushButton.nav-button:hover {
    background-color: rgba(225, 29, 72, 0.1);
    color: #f43f5e;
}
QPushButton.nav-button:checked {
    background-color: #e11d48;
    color: #ffffff;
    font-weight: 700;
    border-radius: 8px;
}
QStackedWidget {
    background-color: #09090b;
}
QPushButton {
    background-color: #18181b;
    border: 1px solid rgba(225, 29, 72, 0.4);
    color: #f43f5e;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton:hover {
    background-color: rgba(225, 29, 72, 0.15);
    border: 1px solid #f43f5e;
    color: #ffffff;
}
QPushButton#actionBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #be123c);
    color: #ffffff;
    border: none;
    font-size: 15px;
    font-weight: bold;
    border-radius: 8px;
    padding: 12px 20px;
}
QPushButton#actionBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f43f5e, stop:1 #e11d48);
}
QTableWidget {
    background-color: #111115;
    color: #f4f4f5;
    gridline-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    outline: none;
}
QHeaderView::section {
    background-color: #18181b;
    color: #f43f5e;
    padding: 10px;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    border-right: 1px solid rgba(255, 255, 255, 0.05);
    font-weight: bold;
    font-size: 13px;
}
QTableWidget::item:selected {
    background-color: rgba(225, 29, 72, 0.2);
    color: #ffffff;
}
QLineEdit, QTextEdit, QComboBox {
    background-color: #18181b;
    color: #f4f4f5;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 500;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #e11d48;
    background-color: #27272a;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #a1a1aa;
    margin-right: 10px;
}
QComboBox::down-arrow:on {
    border-top: 5px solid #e11d48;
}
QComboBox QAbstractItemView {
    background-color: #18181b;
    color: #f4f4f5;
    selection-background-color: #e11d48;
    selection-color: white;
    border: 1px solid #27272a;
    border-radius: 8px;
    outline: none;
}
QLabel {
    color: #a1a1aa;
    font-size: 13px;
    font-weight: 600;
}
QProgressBar {
    border: 1px solid #27272a;
    border-radius: 8px;
    text-align: center;
    color: white;
    background-color: #111115;
    font-weight: bold;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e11d48, stop:1 #f43f5e);
    border-radius: 7px;
}
QCheckBox {
    color: #a1a1aa;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #27272a;
    background-color: #18181b;
}
QCheckBox::indicator:checked {
    background-color: #e11d48;
    border: 1px solid #f43f5e;
}
"""

class WorkerThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, app_data, output_path):
        super().__init__()
        self.app_data = app_data
        self.output_path = output_path
        
        # Build PPM path
        import os
        base_dir = os.path.dirname(self.output_path)
        base_name = os.path.basename(self.output_path)
        
        # Derive PPM name from the chosen output path name
        if "REP" in base_name:
            ppm_name = base_name.replace("REP", "PPM")
        else:
            ppm_name = "PPM_" + base_name
            
        self.ppm_path = os.path.join(base_dir, ppm_name)

    def run(self):
        try:
            self.status.emit("Iniciando generador de informe...")
            self.progress.emit(10)
            tipo_inspeccion = self.app_data.get('info', {}).get('tipo_inspeccion', 'ESTANDAR')
            if tipo_inspeccion == 'CIPS':
                import os, sys
                if hasattr(sys, '_MEIPASS'):
                    base_path = sys._MEIPASS
                else:
                    base_path = os.path.dirname(os.path.abspath(__file__))
                cips_template = os.path.join(base_path, "CIPS EN BLANCO.xlsx")
                gen = ReportGenerator(cips_template)
            else:
                gen = ReportGenerator()
                
            self.progress.emit(20)
            
            # Llenar datos
            self.status.emit("Llenando información general...")
            gen.fill_general_info(self.app_data['info'])
            if 'equipos_inspector' in self.app_data:
                gen.fill_equipos_utilizados(self.app_data['equipos_inspector'])
            self.progress.emit(30)
            
            self.status.emit("Llenando sistema inspeccionado...")
            gen.fill_sistema_inspeccionado(self.app_data['info'], self.app_data['potenciales'])
            self.progress.emit(40)
            
            self.status.emit("Llenando monitoreo y potenciales...")
            gen.fill_monitoreo(self.app_data['info'])
            gen.fill_potenciales_pap(self.app_data['potenciales'], self.app_data['info'].get('fecha',''))
            self.progress.emit(50)
            
            if 'cips' in self.app_data and self.app_data['cips']:
                self.status.emit("Integrando datos de campo CIPS...")
                cips = self.app_data['cips']
                potenciales = self.app_data.get('potenciales', [])
                
                if potenciales:
                    try:
                        import numpy as np
                        from scipy.spatial import cKDTree
                        
                        # Extract valid coordinates
                        valid_cips = []
                        cips_coords = []
                        for i, p in enumerate(cips):
                            if p.get('lat') and p.get('lon'):
                                valid_cips.append(i)
                                cips_coords.append([p['lat'], p['lon']])
                        
                        valid_pots = []
                        pot_coords = []
                        for i, p in enumerate(potenciales):
                            if p.get('lat') and p.get('lon'):
                                valid_pots.append(i)
                                pot_coords.append([p['lat'], p['lon']])
                                
                        if cips_coords and pot_coords:
                            # 20m tolerance in degrees (approx)
                            TOLERANCE = 0.00018
                            
                            tree = cKDTree(np.array(cips_coords))
                            dist, idx = tree.query(np.array(pot_coords), k=1)
                            
                            for i, d, cips_idx in zip(valid_pots, dist, idx):
                                if d <= TOLERANCE:
                                    c_dict = cips[valid_cips[cips_idx]]
                                    p_dict = potenciales[i]
                                    
                                    # Merge VAC and Resistencia
                                    c_dict['vac'] = p_dict.get('vac')
                                    
                                    obs = str(c_dict.get('observaciones', ''))
                                    new_obs = str(p_dict.get('observaciones', ''))
                                    
                                    if new_obs and new_obs != 'nan':
                                        c_dict['observaciones'] = obs + " | " + new_obs if obs else new_obs
                                        
                    except Exception as e:
                        print("Error en spatial match CIPS:", e)
                
                self.status.emit("Llenando potenciales CIPS...")
                gen.fill_cips(cips)
            
            self.status.emit("Generando gráficas...")
            gen.fill_graficas(self.app_data['potenciales'], self.app_data['info'])
            if tipo_inspeccion == 'CIPS' and self.app_data.get('cips'):
                gen.fill_graficas_cips(self.app_data['cips'], self.app_data['info'])
            self.progress.emit(60)
            
            self.status.emit("Llenando hallazgos y rectificadores...")
            hallazgos_rep = list(self.app_data['hallazgos'])
            if tipo_inspeccion == 'CIPS' and self.app_data.get('cips'):
                from cips_adapter import cips_a_hallazgos
                hallazgos_rep += cips_a_hallazgos(self.app_data['cips'])
            gen.fill_hallazgos(hallazgos_rep, self.app_data['info'])
            gen.fill_rectificadores(self.app_data['rectificadores'])
            self.progress.emit(70)
            
            self.status.emit("Llenando aislamientos e inspecciones...")
            gen.fill_aislamientos(self.app_data['aislamientos'])
            # Inspecciones
            gen.fill_inspecciones(
                marco_h=self.app_data['inspecciones'].get('marco_h', []),
                ce=self.app_data['inspecciones'].get('ce', []),
                anodos=self.app_data['inspecciones'].get('anodos', []),
                cupones_ir=self.app_data['inspecciones'].get('cupones_ir', []),
                cupones_grav=self.app_data['inspecciones'].get('cupones_grav', []),
                pe=self.app_data['inspecciones'].get('pe', []),
                tramos_aereos=self.app_data['inspecciones'].get('tramos_aereos', []),
                tramos_no_insp=self.app_data['inspecciones'].get('tramos_no_insp', [])
            )
            self.progress.emit(80)
            
            self.status.emit("Llenando conclusiones y firmas...")
            gen.fill_conclusiones(self.app_data['conclusiones'])
            gen.fill_recomendaciones(self.app_data['recomendaciones'])
            gen.fill_firmas(self.app_data['firmas']['elaboro'], 
                           self.app_data['firmas']['reviso'], 
                           self.app_data['firmas']['aprobo'])
            self.progress.emit(90)
            
            self.status.emit("Guardando archivo PAP...")
            gen.save(self.output_path)
            self.progress.emit(95)
            
            self.status.emit("Generando y guardando archivo PPM...")
            from ppm_generator import PPMGenerator
            ppm_gen = PPMGenerator()
            ppm_gen.generate(
                self.app_data['info'],
                self.app_data['potenciales'],
                self.app_data['aislamientos'],
                self.ppm_path,
                cips=self.app_data.get('cips') or []
            )
            self.progress.emit(100)
            self.status.emit("¡Informes generados con éxito!")
            self.finished.emit(f"PAP: {self.output_path}\nPPM: {self.ppm_path}")
            

        except Exception as e:
            self.error.emit(str(e))

class TramoSelectorDialog(QDialog):
    def __init__(self, tramos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Tramo(s)")
        self.setMinimumWidth(300)
        self.selected_tramos = []
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("El archivo contiene múltiples tramos.\nSeleccione el/los tramos que desea importar:"))
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for t in tramos:
            self.list_widget.addItem(t)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
        layout.addWidget(self.list_widget)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
    def accept(self):
        self.selected_tramos = [item.text() for item in self.list_widget.selectedItems()]
        super().accept()
class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PROTECCIÓN CATÓDICA DE COLOMBIA - Reportes TGI")
        self.setMinimumSize(1000, 750)
        
        # Aplicar el estilo globalmente para asegurar que los elementos anidados lo hereden
        QApplication.instance().setStyleSheet(DARK_STYLE)
        
        # Datos en memoria
        self.data = {
            'info': {},
            'potenciales': [],
            'cips': [],
            'hallazgos': [],
            'rectificadores': [],
            'aislamientos': [],
            'inspecciones': {},
            'conclusiones': [],
            'recomendaciones': [],
            'firmas': {'elaboro': {}, 'reviso': {}, 'aprobo': {}}
        }
        
        self.kmz_loader = None
        self.abscisa_calculator = None
        self.active_inspections = {
            'marco_h': False, 'ce': False, 'anodos': False, 'cupones_ir': False,
            'cupones_grav': False, 'pe': False
        }
        
        self.setup_ui()
        self.try_load_default_kmz()

    def try_load_default_kmz(self):
        default_kmz_name = "Infra_General_TGI_V11_29032023.kmz"
        
        # Determine base paths to search
        search_paths = []
        if getattr(sys, 'frozen', False):
            # Running as compiled PyInstaller executable
            if hasattr(sys, '_MEIPASS'):
                search_paths.append(sys._MEIPASS) # If bundled
            search_paths.append(os.path.dirname(sys.executable)) # Next to the .exe
            search_paths.append(os.path.join(os.path.dirname(sys.executable), '..', '..')) # Root folder
        else:
            # Running as normal Python script
            search_paths.append(os.path.dirname(os.path.abspath(__file__)))
            search_paths.append(os.getcwd())
            
        found_kmz = None
        for path in search_paths:
            candidate = os.path.join(path, default_kmz_name)
            if os.path.exists(candidate):
                found_kmz = candidate
                break
                
        if found_kmz:
            try:
                from geo_utils import KMZPipelineLoader, AbscisaCalculator
                self.kmz_loader = KMZPipelineLoader(found_kmz)
                print(f"KMZ Cargado (Automático): {default_kmz_name}")
                
                # Auto-initialize AbscisaCalculator with the first available route
                route_names = self.kmz_loader.get_all_route_ids()
                if route_names:
                    route_id = route_names[0]
                    pipeline_coords = self.kmz_loader.get_pipeline_coords(route_id)
                    pks = self.kmz_loader.get_pks_for_route(route_id)
                    self.abscisa_calculator = AbscisaCalculator(pipeline_coords, pks)
            except Exception as e:
                print(f"Error cargando KMZ: {str(e)}")
        else:
            print("KMZ No encontrado. Por favor cárgalo manualmente si es requerido.")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- Sidebar ---
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(5)
        
        # Título en Sidebar
        title_label = QLabel("PROTECCIÓN\nCATÓDICA\nDE COLOMBIA")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #d32f2f; letter-spacing: 1px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(title_label)
        
        subtitle = QLabel("Generador TGI")
        subtitle.setStyleSheet("font-size: 12px; color: #757575; margin-bottom: 20px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(subtitle)
        
        # Botones de navegación
        btn_datos = QPushButton("📝 Datos Generales")
        btn_datos.setObjectName("nav_datos")
        btn_datos.setProperty("class", "nav-button")
        btn_datos.setCheckable(True)
        btn_datos.setChecked(True)
        
        btn_pap = QPushButton("📊 Potenciales PAP")
        btn_pap.setObjectName("nav_pap")
        btn_pap.setProperty("class", "nav-button")
        btn_pap.setCheckable(True)
        
        btn_hallazgos = QPushButton("⚠️ Hallazgos")
        btn_hallazgos.setObjectName("nav_hallazgos")
        btn_hallazgos.setProperty("class", "nav-button")
        btn_hallazgos.setCheckable(True)
        
        btn_rectificadores = QPushButton("🔌 Rectificadores")
        btn_rectificadores.setObjectName("nav_rect")
        btn_rectificadores.setProperty("class", "nav-button")
        btn_rectificadores.setCheckable(True)

        btn_insp_especiales = QPushButton("🛠️ Insp. Especiales")
        btn_insp_especiales.setObjectName("nav_insp")
        btn_insp_especiales.setProperty("class", "nav-button")
        btn_insp_especiales.setCheckable(True)
        
        btn_aislamientos = QPushButton("🔗 Aislamientos")
        btn_aislamientos.setObjectName("nav_aisl")
        btn_aislamientos.setProperty("class", "nav-button")
        btn_aislamientos.setCheckable(True)
        
        btn_conclusiones = QPushButton("📋 Conclusiones")
        btn_conclusiones.setObjectName("nav_conc")
        btn_conclusiones.setProperty("class", "nav-button")
        btn_conclusiones.setCheckable(True)

        btn_firmas = QPushButton("✍️ Firmas")
        btn_firmas.setObjectName("nav_firmas")
        btn_firmas.setProperty("class", "nav-button")
        btn_firmas.setCheckable(True)
        
        self.nav_buttons = [btn_datos, btn_pap, btn_hallazgos, btn_rectificadores, btn_insp_especiales, btn_aislamientos, btn_conclusiones, btn_firmas]
        
        from PyQt6.QtWidgets import QStackedWidget, QButtonGroup
        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        
        for i, btn in enumerate(self.nav_buttons):
            self.btn_group.addButton(btn, i)
            sidebar_layout.addWidget(btn)
            
        self.btn_group.idClicked.connect(self.switch_tab)
        sidebar_layout.addStretch()
        
        # --- Right Panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Content Area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        self.tabs = QStackedWidget()
        content_layout.addWidget(self.tabs)
        right_layout.addWidget(content_area)
        
        # Barra inferior
        bottom_bar = QVBoxLayout()
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(20, 0, 20, 20)
        self.btn_generar = QPushButton("🚀 GENERAR INFORME EXCEL")
        self.btn_generar.setObjectName("actionBtn")
        self.btn_generar.setMinimumHeight(40)
        self.btn_generar.clicked.connect(self.generar_informe)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        
        self.lbl_status = QLabel("Listo.")
        
        bottom_layout.addWidget(self.btn_generar)
        bottom_layout.addWidget(self.progress_bar)
        bottom_layout.addWidget(self.lbl_status)
        bottom_bar.addLayout(bottom_layout)
        right_layout.addLayout(bottom_bar)
        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(right_panel)
        
        # Inicializar páginas
        self.tab1 = QWidget()
        self.tab_cips = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        self.tab4 = QWidget()
        self.tab5 = QWidget()
        self.tab6 = QWidget()
        self.tab7 = QWidget()
        self.tab8 = QWidget()
        
        self.tabs.addWidget(self.tab1)
        self.tabs.addWidget(self.tab2)
        self.tabs.addWidget(self.tab3)
        self.tabs.addWidget(self.tab4)
        self.tabs.addWidget(self.tab5)
        self.tabs.addWidget(self.tab6)
        self.tabs.addWidget(self.tab7)
        self.tabs.addWidget(self.tab8)
        
        self.setup_tab1()
        self.setup_tab2()
        self.setup_tab3()
        self.setup_tab4()
        self.setup_tab5()
        self.setup_tab6()
        self.setup_tab7()
        self.setup_tab8()
        
        # Seleccionar primera tab
        self.nav_buttons[0].setChecked(True)
        self.switch_tab(0)

    def switch_tab(self, index):
        self.tabs.setCurrentIndex(index)

    def setup_tab1(self):
        main_layout = QVBoxLayout(self.tab1)
        
        # --- Top Section: Actions ---
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(20)
        
        # Group 2: Archivos de Campo
        group_local = QGroupBox("Archivos Locales de Campo")
        group_local.setStyleSheet("""
            QGroupBox {
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 8px;
                margin-top: 1ex;
                font-weight: bold;
                color: #f4f4f5;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        local_layout = QGridLayout()
        local_layout.setContentsMargins(10, 15, 10, 10)
        local_layout.setSpacing(10)
        
        self.cmb_metodo_abscisa = QComboBox()
        self.cmb_metodo_abscisa.addItems(["Georeferencia Ajustada (Recomendado)", "Georeferencia Pura KMZ", "Distancia de Hilo + PKs"])
        
        self.btn_load_fastfield = QPushButton("📄 Agregar FASTFIELD (.xlsx)")
        self.btn_load_fastfield.clicked.connect(self.load_fastfield)
        self.btn_load_equipos = QPushButton("🧰 Agregar EQUIPOS (.xlsx)")
        self.btn_load_equipos.clicked.connect(self.load_equipo)
        self.btn_load_cips = QPushButton("📉 Cargar Data CIPS")
        self.btn_load_cips.clicked.connect(self.load_cips)
        self.btn_load_rectificador = QPushButton("⚡ Agregar Rectificador")
        self.btn_load_rectificador.clicked.connect(self.load_rectificador)
        self.btn_load_fotos = QPushButton("🖼️ Cargar Carpeta Fotos (IA)")
        self.btn_load_fotos.clicked.connect(self.load_fotos)
        
        local_layout.addWidget(QLabel("Método Cálculo CIPS:"), 0, 0)
        local_layout.addWidget(self.cmb_metodo_abscisa, 0, 1)
        local_layout.addWidget(self.btn_load_fastfield, 1, 0)
        local_layout.addWidget(self.btn_load_equipos, 1, 1)
        # --- Selector CIPS: Empresa / Distrito / Tramo ---
        try:
            self.infra_tramos = InfraTramos()
        except Exception as e:
            self.infra_tramos = None
            print("No se pudo cargar infraestructura CIPS:", e)

        self.cmb_cips_empresa = QComboBox()
        self.cmb_cips_empresa.addItems(["TGI", "OCENSA"])
        self.cmb_cips_distrito = QComboBox()
        self.cmb_cips_tramo = QComboBox()

        self.cmb_cips_empresa.currentTextChanged.connect(self._on_cips_empresa_changed)
        self.cmb_cips_distrito.currentTextChanged.connect(self._on_cips_distrito_changed)

        local_layout.addWidget(QLabel("Empresa CIPS:"), 4, 0)
        local_layout.addWidget(self.cmb_cips_empresa, 4, 1)
        local_layout.addWidget(QLabel("Distrito:"), 5, 0)
        local_layout.addWidget(self.cmb_cips_distrito, 5, 1)
        local_layout.addWidget(QLabel("Tramo CIPS:"), 6, 0)
        local_layout.addWidget(self.cmb_cips_tramo, 6, 1)

        self._on_cips_empresa_changed(self.cmb_cips_empresa.currentText())

        local_layout.addWidget(self.btn_load_cips, 2, 0, 1, 2)
        local_layout.addWidget(self.btn_load_rectificador, 3, 0)
        local_layout.addWidget(self.btn_load_fotos, 3, 1)
        
        group_local.setLayout(local_layout)
        actions_layout.addWidget(group_local, stretch=1)
        
        main_layout.addLayout(actions_layout)
        
        # API Key Input
        api_layout = QHBoxLayout()
        api_layout.setContentsMargins(0, 15, 0, 15)
        lbl_api = QLabel("🔑 Gemini API Key (IA):")
        self.ai_key_input = QLineEdit()
        self.ai_key_input.setPlaceholderText("Opcional: Pega tu llave API de Gemini Vision aquí...")
        self.ai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addWidget(lbl_api)
        api_layout.addWidget(self.ai_key_input, stretch=1)
        main_layout.addLayout(api_layout)
        
        # --- Contenedor de Formulario Principal ---
        form_card = QFrame()
        form_card.setObjectName("form_card")
        form_card.setStyleSheet("""
            QFrame#form_card {
                background-color: #111115;
                border: 1px solid #27272a;
                border-radius: 12px;
                margin-top: 10px;
            }
        """)
        card_layout = QVBoxLayout(form_card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        # Configurar campos en la pestaña de Datos Generales
        grid = QGridLayout()
        grid.setSpacing(15)
        
        self.fields = {}
        labels = ['Gasoducto', 'Tramo', 'Tipo Ducto', 'Contrato', 'OT', 'Contratista', 
                  'Fecha', 'Inspector', 'Serial Equipo', 'Fecha Calibración', 
                  'Diámetro', 'Tipo Recubrimiento', 'Ciclo']
        
        for i, name in enumerate(labels):
            l = QLabel(name)
            le = QLineEdit()
            self.fields[name.lower().replace(' ', '_').replace('á', 'a').replace('ó', 'o')] = le
            v = QVBoxLayout()
            v.addWidget(l)
            v.addWidget(le)
            grid.addLayout(v, i // 3, i % 3)
            
        # Combo para Tipo de Inspección
        l = QLabel("Tipo Inspección")
        self.cmb_tipo_inspeccion = QComboBox()
        self.cmb_tipo_inspeccion.addItems(["PAP", "CIPS", "DCVG"])
        self.fields['tipo_inspeccion'] = self.cmb_tipo_inspeccion
        v = QVBoxLayout()
        v.addWidget(l)
        v.addWidget(self.cmb_tipo_inspeccion)
        grid.addLayout(v, len(labels) // 3, len(labels) % 3)
            
        # Conectar el cambio manual del tramo para auto-llenar
        if 'tramo' in self.fields:
            self.fields['tramo'].editingFinished.connect(
                lambda: [
                    self.autofill_from_infrastructure(self.fields['tramo'].text()),
                    self.autofill_ot_km(self.fields['tramo'].text())
                ]
            )
            
        card_layout.addLayout(grid)
        main_layout.addWidget(form_card)
        main_layout.addStretch()

    def setup_tab_cips(self):
        layout = QVBoxLayout(self.tab_cips)
        self.table_cips = QTableWidget(0, 7)
        self.table_cips.setHorizontalHeaderLabels(["Abscisa", "Ref", "On [mV]", "Off [mV]", "Lat", "Lon", "Observaciones"])
        layout.addWidget(self.table_cips)


    def setup_tab2(self):
        layout = QVBoxLayout(self.tab2)
        self.table_pot = QTableWidget(0, 14)
        self.table_pot.setHorizontalHeaderLabels([
            "Abscisa", "Fecha", "Ref Geográfica", "ON (mV)", "OFF (mV)", 
            "VAC", "Resistencia", "IR ON-OFF", "Lat", "Lon", 
            "Pintura", "Conexiones", "Mantenimiento", "Observaciones"
        ])
        self.table_pot.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table_pot)

    def setup_tab3(self):
        layout = QVBoxLayout(self.tab3)
        self.table_hal = QTableWidget(0, 8)
        self.table_hal.setHorizontalHeaderLabels([
            "Abscisa Ini", "Abscisa Fin", "Longitud", "Tipo Hallazgo", 
            "Descripción", "Lat", "Lon", "Fecha"
        ])
        self.table_hal.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_hal)

    def setup_tab4(self):
        layout = QVBoxLayout(self.tab4)
        self.table_rect = QTableWidget(0, 8)
        self.table_rect.setHorizontalHeaderLabels([
            "Nombre", "Gasoducto", "V Nominal", "I Nominal", 
            "V Operativo", "I Operativo", "TAPS", "Disponibilidad"
        ])
        self.table_rect.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table_rect)

    def setup_tab5(self):
        layout = QVBoxLayout(self.tab5)
        # Checkboxes
        self.checks = {}
        for name, key in [("Marco H", "marco_h"), ("Cruces Encamisados", "ce"), 
                          ("Ánodos", "anodos"), ("Cupones IR FREE", "cupones_ir"),
                          ("Cupones Gravimétricos", "cupones_grav"), ("Puentes Eléctricos", "pe")]:
            cb = QCheckBox(name)
            cb.stateChanged.connect(lambda state, k=key: self.active_inspections.update({k: state == Qt.CheckState.Checked.value}))
            self.checks[key] = cb
            layout.addWidget(cb)
        layout.addStretch()

    def setup_tab6(self):
        layout = QVBoxLayout(self.tab6)
        
        # Opciones de carga
        top_layout = QHBoxLayout()
        btn_load_ais = QPushButton("📂 Cargar Archivos Aislamientos")
        btn_load_ais.setObjectName("actionBtn")
        btn_load_ais.clicked.connect(self.load_aislamientos_folder)
        
        self.lbl_aislamientos_info = QLabel("0 aislamientos cargados")
        
        top_layout.addWidget(btn_load_ais)
        top_layout.addWidget(self.lbl_aislamientos_info)
        top_layout.addStretch()
        
        layout.addLayout(top_layout)
        
        self.table_ais = QTableWidget(0, 8)
        self.table_ais.setHorizontalHeaderLabels([
            "Abscisa", "TAG", "Clase", "Diámetro", 
            "Tipo Brida", "ON Arriba", "OFF Arriba", "Diagnóstico"
        ])
        self.table_ais.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        btn_add = QPushButton("Agregar Aislamiento Manual")
        btn_add.clicked.connect(lambda: self.table_ais.insertRow(self.table_ais.rowCount()))
        layout.addWidget(btn_add)
        layout.addWidget(self.table_ais)

    def setup_tab7(self):
        layout = QVBoxLayout(self.tab7)
        btn_gen = QPushButton("🔄 Auto-Generar Conclusiones y Recomendaciones")
        btn_gen.setObjectName("actionBtn")
        btn_gen.clicked.connect(self.auto_generate_conclusions)
        layout.addWidget(btn_gen)
        
        layout.addWidget(QLabel("Conclusiones:"))
        self.txt_conclusiones = QTextEdit()
        layout.addWidget(self.txt_conclusiones)
        
        layout.addWidget(QLabel("Recomendaciones:"))
        self.txt_recomendaciones = QTextEdit()
        layout.addWidget(self.txt_recomendaciones)

    def setup_tab8(self):
        layout = QVBoxLayout(self.tab8)
        
        def add_firma(title, prefix):
            group = QVBoxLayout()
            group.addWidget(QLabel(f"--- {title} ---"))
            
            n = QLineEdit()
            c = QLineEdit()
            e = QLineEdit()
            n.setPlaceholderText("Nombre")
            c.setPlaceholderText("Cargo")
            e.setPlaceholderText("Empresa")
            
            self.fields[f'{prefix}_nombre'] = n
            self.fields[f'{prefix}_cargo'] = c
            self.fields[f'{prefix}_empresa'] = e
            
            group.addWidget(n)
            group.addWidget(c)
            group.addWidget(e)
            layout.addLayout(group)
            
        add_firma("Elaboró", "elab")
        add_firma("Revisó", "rev")
        add_firma("Aprobó", "aprob")
        layout.addStretch()

    # --- Actions ---
    def autofill_from_infrastructure(self, tramo_name):
        import pandas as pd
        import sys
        
        # Determinar la ruta base (si es un ejecutable o script)
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        infra_file = os.path.join(base_path, 'Infraestrutura TGI.xlsx')
        # También buscar en el directorio de ejecución actual por si acaso
        if not os.path.exists(infra_file):
            infra_file = 'Infraestrutura TGI.xlsx'
            
        if not os.path.exists(infra_file):
            print(f"No se encontro archivo infraestructura en {base_path}")
            return
        
        try:
            df = pd.read_excel(infra_file, header=1)
            if 'GASODUCTO.1' in df.columns:
                df['GASODUCTO.1'] = df['GASODUCTO.1'].ffill()
                
            if 'TRAMOS' not in df.columns:
                return
                
            df = df.dropna(subset=['TRAMOS'])
            matches = df[df['TRAMOS'].astype(str).str.contains(tramo_name, case=False, na=False)]
            
            if not matches.empty:
                row = matches.iloc[0]
                
                # Verificar coincidencia exacta si es posible
                exact_matches = df[df['TRAMOS'].astype(str).str.lower() == tramo_name.lower()]
                if not exact_matches.empty:
                    row = exact_matches.iloc[0]
                
                # Obtener GASODUCTO
                gasoducto_val = None
                if 'GASODUCTO.1' in row and pd.notna(row['GASODUCTO.1']):
                    gasoducto_val = row['GASODUCTO.1']
                elif 'GASODUCTO' in row and pd.notna(row['GASODUCTO']):
                    gasoducto_val = row['GASODUCTO']
                    
                if gasoducto_val:
                    self.fields['gasoducto'].setText(str(gasoducto_val))
                
                # Obtener Diámetro
                diam_cols = [c for c in df.columns if 'Di' in str(c) and 'metro' in str(c)]
                if not diam_cols: diam_cols = [c for c in df.columns if 'pulg' in str(c).lower()]
                if diam_cols and pd.notna(row[diam_cols[0]]):
                    self.fields['diametro'].setText(str(row[diam_cols[0]]))
                
                # Obtener Recubrimiento
                if 'Recubrimiento' in row and pd.notna(row['Recubrimiento']):
                    self.fields['tipo_recubrimiento'].setText(str(row['Recubrimiento']))
                    
                # Obtener Tipo Ducto
                if 'Tipo' in row and pd.notna(row['Tipo']):
                    if not self.fields['tipo_ducto'].text():
                        self.fields['tipo_ducto'].setText(str(row['Tipo']))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error cargando base de datos: {str(e)}")

    def load_aislamientos_folder(self):
        filepaths, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Archivos de Aislamientos FastField", "", "Excel (*.xlsx)")
        if filepaths:
            try:
                from readers import AislamientoReader
                reader = AislamientoReader()
                aislamientos = reader.read_files(filepaths)
                
                self.data['aislamientos'] = aislamientos
                self.lbl_aislamientos_info.setText(f"{len(aislamientos)} aislamientos cargados")
                
                # Actualizar tabla visualmente
                self.table_ais.setRowCount(0)
                for item in aislamientos:
                    row_idx = self.table_ais.rowCount()
                    self.table_ais.insertRow(row_idx)
                    self.table_ais.setItem(row_idx, 0, QTableWidgetItem(str(item.get('abscisado', ''))))
                    self.table_ais.setItem(row_idx, 1, QTableWidgetItem(str(item.get('tag', ''))))
                    self.table_ais.setItem(row_idx, 2, QTableWidgetItem(str(item.get('clase', ''))))
                    self.table_ais.setItem(row_idx, 3, QTableWidgetItem(str(item.get('diametro', ''))))
                    self.table_ais.setItem(row_idx, 4, QTableWidgetItem(str(item.get('tipo_brida', ''))))
                    self.table_ais.setItem(row_idx, 5, QTableWidgetItem(str(item.get('pot_on_arriba', ''))))
                    self.table_ais.setItem(row_idx, 6, QTableWidgetItem(str(item.get('pot_off_arriba', ''))))
                    self.table_ais.setItem(row_idx, 7, QTableWidgetItem(str(item.get('diagnostico', ''))))
                    
                QMessageBox.information(self, "Éxito", f"Se han cargado {len(aislamientos)} reportes de aislamiento.")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.warning(self, "Error", f"Error cargando aislamientos: {str(e)}")

    def load_fastfield(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar FASTFIELD", "", "Excel (*.xlsx)")
            if not files:
                return
            reader = FastFieldReader()
            for f in files:
                data = reader.read(f)
                
                unique_tramos = list(set(p['tramo'] for p in data['potenciales'] if p.get('tramo')))
                unique_tramos.sort()
                
                pots_to_add = data['potenciales']
                
                if len(unique_tramos) > 1:
                    dialog = TramoSelectorDialog(unique_tramos, self)
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        selected = dialog.selected_tramos
                        if not selected:
                            continue
                        pots_to_add = [p for p in pots_to_add if p.get('tramo') in selected]
                        data['tramo'] = selected[0]
                    else:
                        continue
                        
                self.data['potenciales'].extend(pots_to_add)
                
                # Update info
                if data['tramo']: 
                    self.fields['tramo'].setText(data['tramo'])
                    self.autofill_from_infrastructure(data['tramo'])
                    self.autofill_ot_km(data['tramo'])
                if data['contrato']: self.fields['contrato'].setText(data['contrato'])
                if data['tecnico']: 
                    self.fields['inspector'].setText(data['tecnico'])
                    self.autofill_equipos(data['tecnico'])
                if data['fecha']: self.fields['fecha'].setText(data['fecha'])
                if data['tipo_tramo']: self.fields['tipo_ducto'].setText(data['tipo_tramo'])
                
                # Save route_id for abscisa calculation
                if pots_to_add:
                    self.current_route_id = pots_to_add[0].get('route_id')
                
            # Post-process potenciales after all files loaded
            if self.data['potenciales']:
                # Initialize dictionaries
                if 'marco_h' not in self.data['inspecciones']: self.data['inspecciones']['marco_h'] = []
                
                sorted_pots = sorted(self.data['potenciales'], key=lambda x: x.get('abscisa_val', 0))
                tramos_aereos = []
                current_tramo = None
                
                for p in sorted_pots:
                    obs = str(p.get('observaciones', '')).lower()
                    ref = str(p.get('ref_geografica', '')).lower()
                    
                    if 'marco h' in obs or 'marco h' in ref:
                        mh = {
                            'route_id': p.get('route_id'),
                            'abscisado': p.get('abscisa_str'),
                            'fecha': p.get('fecha'),
                            'pot_on_gasoducto': None,
                            'pot_off_gasoducto': None,
                            'pot_on_marco': p.get('on_mv'),
                            'pot_off_marco': p.get('off_mv'),
                            'aislado': 1 if ('aislado' in obs or 'buen' in str(p.get('conexiones', '')).lower()) else 0,
                            'estado_marco': 'Marco H en buen estado' if 'buen' in str(p.get('pintura', '')).lower() else 'Malo',
                            'estado_aislante': 'Buen Estado',
                            'lat': p.get('lat'),
                            'lon': p.get('lon'),
                            'estado_pintura': p.get('pintura', 'Bueno'),
                            'observaciones': p.get('observaciones', '')
                        }
                        self.data['inspecciones']['marco_h'].append(mh)
                        
                    # Interface Tierra-Aire (Start of aerial)
                    if 'tierra aire' in obs or 'tierra aire' in ref or 'enterrada-aérea' in ref or 'enterrada-aerea' in ref:
                        current_tramo = {
                            'route_id': p.get('route_id'),
                            'inicio_abscisa_val': p.get('abscisa_val', 0),
                            'inicio_abscisa': p.get('abscisa_str', ''),
                            'lat_inicio': p.get('lat'),
                            'lon_inicio': p.get('lon'),
                            'fecha': p.get('fecha')
                        }
                    # Interface Aire-Tierra (End of aerial)
                    elif 'aire tierra' in obs or 'aire tierra' in ref or 'aéreo-enterrada' in ref or 'aereo-enterrada' in ref:
                        if current_tramo:
                            current_tramo['fin_abscisa_val'] = p.get('abscisa_val', 0)
                            current_tramo['fin_abscisa'] = p.get('abscisa_str', '')
                            current_tramo['lat_fin'] = p.get('lat')
                            current_tramo['lon_fin'] = p.get('lon')
                            current_tramo['longitud'] = current_tramo['fin_abscisa_val'] - current_tramo['inicio_abscisa_val']
                            current_tramo['gasoducto'] = data.get('tramo', '')
                            current_tramo['tramo'] = data.get('tipo_tramo', '')
                            tramos_aereos.append(current_tramo)
                            current_tramo = None
                            
                self.data['inspecciones']['tramos_aereos'] = tramos_aereos
                self.data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
                
            self.update_ruta_filter()
            self.refresh_potenciales_table()
            self.refresh_hallazgos_table()
        except Exception as e:
            import traceback
            err_msg = traceback.format_exc()
            print(err_msg)
            QMessageBox.critical(self, "Error Fatal", f"Ocurrió un error al cargar Fastfield:\n{str(e)}\n\n{err_msg}")


    def load_equipo(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar EQUIPO", "", "Excel (*.xlsx)")
        reader = EquipoReader()
        for f in files:
            data = reader.read(f)
            # Combine hallazgos
            self.data['hallazgos'].extend(data['hallazgos'])
            
            # Setup AbscisaCalculator if we have KMZ and Route ID
            if self.kmz_loader and hasattr(self, 'current_route_id') and self.current_route_id:
                calc_route_id = self.current_route_id
                pipeline_coords = self.kmz_loader.get_pipeline_coords(calc_route_id)
                if not pipeline_coords:
                    resolved = self.kmz_loader.find_route_by_name(calc_route_id)
                    if resolved:
                        calc_route_id = resolved
                        pipeline_coords = self.kmz_loader.get_pipeline_coords(calc_route_id)
                
                pks = self.kmz_loader.get_pks_for_route(calc_route_id)
                if pipeline_coords:
                    self.abscisa_calculator = AbscisaCalculator(pipeline_coords, pks)
                    
            # Calculate missing abscisas for hallazgos
            for h in self.data['hallazgos']:
                meters = 0
                if h.get('abscisa') is None and h.get('lat') and h.get('lon') and self.abscisa_calculator:
                    meters = self.abscisa_calculator.calculate(h['lat'], h['lon'])
                    h['abscisa'] = self.abscisa_calculator.format_abscisa(meters)
                else:
                    meters = AbscisaCalculator.parse_abscisa(str(h.get('abscisa', '0+000')))
                    if self.abscisa_calculator:
                        h['abscisa'] = self.abscisa_calculator.format_abscisa(meters)
                    else:
                        km = meters // 1000
                        m = meters % 1000
                        h['abscisa'] = f"{km:03d}+{m:03d}"
                h['abscisa_val'] = meters
                
            # Update info
            info = data['survey_info']
            
            # Identify route for this equipo file
            route_id = None
            if self.kmz_loader and info['pipeline']:
                route_id = self.kmz_loader.find_route_by_name(info['pipeline'])
            for h in data['hallazgos']:
                if not h.get('route_id'):
                    h['route_id'] = route_id
            
            # Sort hallazgos by abscisa
            self.data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
            
            # Process DCP points for Marco H
            for dcp in data.get('dcp_points', []):
                comment = str(dcp.get('comment', '')).lower()
                if 'marco h' in comment:
                    lat = dcp.get('lat')
                    lon = dcp.get('lon')
                    meters = 0
                    abscisa_str = ''
                    if self.abscisa_calculator and lat and lon:
                        meters = self.abscisa_calculator.calculate(lat, lon)
                        abscisa_str = self.abscisa_calculator.format_abscisa(meters)
                        
                    mh = {
                        'route_id': route_id,
                        'abscisado': abscisa_str,
                        'fecha': info.get('date', ''),
                        'pot_on_gasoducto': None,
                        'pot_off_gasoducto': None,
                        'pot_on_marco': None,
                        'pot_off_marco': None,
                        'aislado': 1 if 'aislado' in comment else 0,
                        'estado_marco': '',
                        'estado_aislante': '',
                        'lat': lat,
                        'lon': lon,
                        'estado_pintura': '',
                        'observaciones': str(dcp.get('comment', ''))
                    }
                    if 'marco_h' not in self.data['inspecciones']:
                        self.data['inspecciones']['marco_h'] = []
                    self.data['inspecciones']['marco_h'].append(mh)

            # Update info
            info = data['survey_info']
            if info['pipeline'] and not self.fields['gasoducto'].text(): 
                self.fields['gasoducto'].setText(info['pipeline'])
            if info['cycle_on_ms'] and not self.fields['ciclo'].text(): 
                self.fields['ciclo'].setText(f"{info['cycle_on_ms']}/{info['cycle_off_ms']} ms")
            
        self.update_ruta_filter()
        self.refresh_hallazgos_table()

    def get_equipos_for_inspector(self, inspector_name):
        import pandas as pd
        import os
        try:
            from generator import resource_path
            filepath = resource_path("Listado equipos TGI.xlsx")
            if not os.path.exists(filepath): return None, None, []
            df = pd.read_excel(filepath, header=2)
            
            inspector_name = inspector_name.strip().upper()
            
            # Map "Luis Benitez" to "Evelio Alvarez" for equipment
            if "LUIS BENITEZ" in inspector_name:
                inspector_name = "EVELIO ALVAREZ"
            
            datalogger_serial = ""
            datalogger_fecha_cal = ""
            equipos_list = []
            
            for index, row in df.iterrows():
                if pd.isna(row.iloc[1]):
                    continue
                insp = str(row.iloc[1]).strip().upper()
                
                # Coincidencia flexible (Ej. "Luis Ortiz" coincidirá con "Luis Humberto Ortiz")
                insp_words = set(insp.split())
                search_words = set(inspector_name.split())
                
                if insp == inspector_name or len(insp_words.intersection(search_words)) >= 2:
                    equipo = str(row.iloc[2]).strip()
                    marca = str(row.iloc[3]).strip()
                    serial = str(row.iloc[4]).strip()
                    fecha_cal = row.iloc[5]
                    
                    if "DATALOG" in equipo.upper():
                        datalogger_serial = serial
                        if pd.notna(fecha_cal):
                            if isinstance(fecha_cal, pd.Timestamp):
                                datalogger_fecha_cal = fecha_cal.strftime('%d/%m/%Y')
                            else:
                                datalogger_fecha_cal = str(fecha_cal).split()[0]
                        
                    equipos_list.append(f"{equipo}: {marca} - {serial}")
            
            return datalogger_serial, datalogger_fecha_cal, equipos_list
        except Exception as e:
            print("Error loading equipos:", e)
            return None, None, []

    def autofill_ot_km(self, tramo_name):
        import pandas as pd
        import os
        try:
            from generator import resource_path
            filepath = resource_path("consolidado OT.xlsx")
            if not os.path.exists(filepath): return
            df = pd.read_excel(filepath)
            
            if 'SUBSISTEMA' not in df.columns: return
            
            matches = df[df['SUBSISTEMA'].astype(str).str.contains(tramo_name, case=False, na=False)]
            if not matches.empty:
                row = matches.iloc[0]
                
                # OT
                if 'Orden' in df.columns and pd.notna(row['Orden']):
                    try:
                        ot_val = int(float(row['Orden']))
                        self.fields['ot'].setText(str(ot_val))
                    except:
                        self.fields['ot'].setText(str(row['Orden']).strip())
                        
                # Distrito
                if 'Distrito' in df.columns and pd.notna(row['Distrito']):
                    self.data['info']['distrito'] = str(row['Distrito'])
                        
                # KM (Unidad [Km])
                if 'Unidad [Km]' in df.columns and pd.notna(row['Unidad [Km]']):
                    try:
                        self.data['info']['longitud_km'] = float(row['Unidad [Km]'])
                    except:
                        pass
        except Exception as e:
            print("Error cargando consolidado OT:", e)
            return None, None, []

    def autofill_equipos(self, inspector_name):
        datalogger, fecha_cal, eq_list = self.get_equipos_for_inspector(inspector_name)
        if datalogger:
            self.fields['serial_equipo'].setText(datalogger)
        if fecha_cal:
            self.fields['fecha_calibracion'].setText(fecha_cal)
        
        self.fields['contratista'].setText("PCC")
        
        if eq_list:
            self.data['equipos_inspector'] = eq_list

    def load_rectificador(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Rectificador", "", "Excel (*.xlsx)")
        reader = RectificadorReader()
        for f in files:
            data = reader.read(f)
            if data:
                self.data['rectificadores'].append(data)
        self.refresh_rectificadores_table()

    def load_fotos(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Fotos")
        if not folder:
            return
            
        api_key = self.ai_key_input.text().strip()
        processor = PhotoProcessor(api_key=api_key if api_key else None)
        
        # Necesitamos el abscisa_calculator inicializado
        if not hasattr(self, 'abscisa_calculator') or not self.abscisa_calculator:
            QMessageBox.warning(self, "Atención", "Debe cargar primero el KMZ y un archivo EQUIPO o FASTFIELD para calcular las abscisas.")
            return

        import os
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            return
            
        progress = QProgressDialog("Analizando fotos y calculando abscisas...", "Cancelar", 0, len(image_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        nuevos_hallazgos = 0

        for i, filename in enumerate(image_files):
            if progress.wasCanceled():
                break
                
            progress.setValue(i)
            file_path = os.path.join(folder, filename)
            
            # Extraer EXIF
            exif = processor.get_exif_data(file_path)
            lat, lon = processor.get_gps_coordinates(exif)
            fecha_foto = processor.get_datetime(exif)
            
            if lat and lon:
                meters = self.abscisa_calculator.calculate(lat, lon)
                
                # Verificar si ya existe un hallazgo cercano (±20 metros)
                existe = False
                for h in self.data['hallazgos']:
                    if abs(h.get('abscisa_val', -9999) - meters) <= 20:
                        existe = True
                        break
                        
                # Verificar si existe un poste/potencial cercano (±20 metros)
                existe_potencial = False
                for p in self.data['potenciales']:
                    if abs(p.get('abscisa', -9999) - meters) <= 20:
                        existe_potencial = True
                        break
                        
                name_lower = filename.lower()
                # Palabras clave explícitas de hallazgos
                keywords = [
                    'via', 'vía', 
                    'caño', 
                    'tension', 'tensión', 'at', 'mt', 'bt', 
                    'enmontado', 'monte',
                    'privada', 'predio',
                    'cultivo'
                ]
                es_hallazgo_explicito = any(k in name_lower for k in keywords)

                if not existe:
                    # Si hay un poste cerca y el nombre de la foto no menciona un hallazgo explícito,
                    # asumimos que es una foto del poste y no la agregamos como hallazgo.
                    if existe_potencial and not es_hallazgo_explicito:
                        continue
                        
                    tipo = ""
                    if 'via' in name_lower or 'vía' in name_lower: tipo = "Cruce de Vía"
                    elif 'caño' in name_lower: tipo = "Cruce de Caño"
                    elif 'tension' in name_lower or 'tensión' in name_lower or ' at ' in name_lower or ' mt ' in name_lower or ' bt ' in name_lower: tipo = "Línea de media, alta o baja tensión"
                    elif 'enmontado' in name_lower or 'monte' in name_lower: tipo = "Tramo enmontado"
                    elif 'privada' in name_lower or 'predio' in name_lower: tipo = "Propiedad privada"
                    elif 'cultivo' in name_lower: tipo = "Cultivo"
                    
                    desc = f"Hallazgo generado automáticamente desde foto ({filename})"
                    
                    # Si no hay tipo claro y tenemos API KEY, usamos IA
                    if not tipo and api_key:
                        progress.setLabelText(f"Clasificando con IA: {filename}")
                        tipo_ia, desc_ia = processor.classify_image_with_ai(file_path)
                        if 'descartar' in tipo_ia.lower():
                            continue # El usuario pidió ignorar el resto
                        tipo = tipo_ia
                        desc = f"{desc_ia} (Autogenerado desde foto: {filename})"
                    elif not tipo:
                        # Si no hay IA y tampoco coincide la palabra clave, se descarta (a petición del usuario)
                        continue
                        
                    nuevo_h = {
                        'tipo': tipo,
                        'descripcion': desc,
                        'lat': lat,
                        'lon': lon,
                        'alt': None,
                        'abscisa_val': meters,
                        'abscisa': self.abscisa_calculator.format_abscisa(meters),
                        'fecha': fecha_foto.split(' ')[0] if fecha_foto else ''
                    }
                    self.data['hallazgos'].append(nuevo_h)
                    nuevos_hallazgos += 1
                    
        progress.setValue(len(image_files))
        
        # Sort hallazgos by abscisa
        self.data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
        self.refresh_hallazgos_table()
        
        QMessageBox.information(self, "Proceso Completado", f"Se han procesado {len(image_files)} fotos.\nSe agregaron {nuevos_hallazgos} nuevos hallazgos basados en el GPS.")

    def load_kmz(self):
        f, _ = QFileDialog.getOpenFileName(self, "Seleccionar KMZ", "", "KMZ (*.kmz)")
        if f:
            try:
                self.kmz_loader = KMZPipelineLoader(f)
                self.lbl_kmz_status.setText(f"KMZ Cargado: {os.path.basename(f)}")
                self.lbl_kmz_status.setStyleSheet("color: #69f0ae;")
            except Exception as e:
                self.lbl_kmz_status.setText(f"Error cargando KMZ: {str(e)}")
                self.lbl_kmz_status.setStyleSheet("color: #ff5252;")

    def update_ruta_filter(self):
        if not hasattr(self, "cmb_filtro_ruta"): return
        rutas = set()
        for p in self.data['potenciales']:
            if p.get('route_id'):
                rutas.add(p['route_id'])
        for h in self.data['hallazgos']:
            if h.get('route_id'):
                rutas.add(h['route_id'])
        
        current = self.cmb_filtro_ruta.currentText()
        self.cmb_filtro_ruta.blockSignals(True)
        self.cmb_filtro_ruta.clear()
        self.cmb_filtro_ruta.addItem("Todas las Rutas")
        for r in sorted(list(rutas)):
            self.cmb_filtro_ruta.addItem(r)
            
        if current in rutas:
            self.cmb_filtro_ruta.setCurrentText(current)
        self.cmb_filtro_ruta.blockSignals(False)

    def apply_filter(self, text):
        self.refresh_potenciales_table()
        self.refresh_hallazgos_table()

    def get_filtered_data(self):
        if not hasattr(self, "cmb_filtro_ruta"): return self.data
        selected = self.cmb_filtro_ruta.currentText()
        if selected == "Todas las Rutas":
            return self.data
            
        filtered = {
            'info': self.data['info'], 
            'potenciales': [p for p in self.data['potenciales'] if p.get('route_id') == selected],
            'hallazgos': [h for h in self.data['hallazgos'] if h.get('route_id') == selected or not h.get('route_id')],
            'rectificadores': self.data['rectificadores'], 
            'aislamientos': self.data['aislamientos'],
            'inspecciones': {
                'marco_h': [m for m in self.data['inspecciones'].get('marco_h', []) if m.get('route_id') == selected or not m.get('route_id')],
                'tramos_aereos': [t for t in self.data['inspecciones'].get('tramos_aereos', []) if t.get('route_id') == selected or not t.get('route_id')]
            },
            'conclusiones': self.data['conclusiones'],
            'recomendaciones': self.data['recomendaciones'],
            'firmas': self.data['firmas'],
            'equipos_inspector': self.data.get('equipos_inspector', [])
        }
        return filtered

    def _on_cips_empresa_changed(self, empresa):
        if not getattr(self, "infra_tramos", None):
            return
        es_tgi = (empresa == "TGI")
        self.cmb_cips_distrito.setVisible(es_tgi)
        if es_tgi:
            self.cmb_cips_distrito.blockSignals(True)
            self.cmb_cips_distrito.clear()
            self.cmb_cips_distrito.addItems(self.infra_tramos.distritos_tgi())
            self.cmb_cips_distrito.blockSignals(False)
            self._on_cips_distrito_changed(self.cmb_cips_distrito.currentText())
        else:
            self.cmb_cips_tramo.clear()
            self.cmb_cips_tramo.addItems(self.infra_tramos.tramos(empresa="OCENSA"))

    def _on_cips_distrito_changed(self, distrito):
        if not getattr(self, "infra_tramos", None):
            return
        if self.cmb_cips_empresa.currentText() != "TGI":
            return
        self.cmb_cips_tramo.clear()
        self.cmb_cips_tramo.addItems(
            self.infra_tramos.tramos(empresa="TGI", distrito=distrito))

    def load_cips(self):
        try:
            archivos, _ = QFileDialog.getOpenFileNames(
                self, "Seleccionar Data CIPS", "", "Excel (*.xlsx)")
            if not archivos:
                return

            if not getattr(self, "infra_tramos", None):
                QMessageBox.warning(self, "Error",
                    "No se cargó la base de infraestructura de tramos.")
                return

            empresa = self.cmb_cips_empresa.currentText()
            tramo = self.cmb_cips_tramo.currentText()
            distrito = self.cmb_cips_distrito.currentText() if empresa == "TGI" else None
            shp = self.infra_tramos.shapefile(empresa=empresa, tramo=tramo, distrito=distrito)
            if not shp:
                msg = f"El tramo '{tramo}' no tiene shapefile en el paquete."
                try:
                    from cips_lrs import coords_muestra
                    latlon = coords_muestra(archivos)
                    if latlon:
                        sugs = self.infra_tramos.sugerir_tramos(*latlon)
                        if sugs:
                            lista = "\n".join(f"  • {t} (Distrito {d}, {i})"
                                              for t, d, i in sugs[:5])
                            msg += ("\n\nSegún las coordenadas de los archivos, "
                                    "los datos corresponden a:\n" + lista)
                except Exception:
                    pass
                QMessageBox.warning(self, "Error", msg)
                return

            self.lbl_status.setText("Procesando CIPS (LRS)...")
            QApplication.processEvents()

            from cips_lrs import procesar_cips_lrs
            from cips_adapter import lrs_df_a_cips_dicts

            # Acumular ARCHIVOS y reprocesar el conjunto completo: así las
            # abscisas se ordenan globalmente y reprocesar nunca duplica datos.
            previos = getattr(self, "cips_archivos", [])
            self.cips_archivos = previos + [a for a in archivos if a not in previos]
            df = procesar_cips_lrs(self.cips_archivos, shp)
            cips_dicts = lrs_df_a_cips_dicts(df)

            self.data['cips'] = cips_dicts
            self.refresh_cips_table()
            self.lbl_status.setText(
                f"Data CIPS procesada: {len(cips_dicts)} registros "
                f"de {len(self.cips_archivos)} archivo(s).")
        except Exception as e:
            import traceback
            traceback.print_exc()
            msg = f"Ocurrió un error procesando CIPS:\n{str(e)}"
            try:
                from cips_lrs import TramoIncorrectoError
                if isinstance(e, TramoIncorrectoError) and e.lat:
                    sugs = self.infra_tramos.sugerir_tramos(e.lat, e.lon)
                    if sugs:
                        lista = "\n".join(f"  • {t} (Distrito {d}, {i})"
                                          for t, d, i in sugs[:5])
                        msg += ("\n\nSegún las coordenadas del archivo, los "
                                "datos parecen corresponder a:\n" + lista)
            except Exception:
                pass
            QMessageBox.critical(self, "Error CIPS", msg)
            self.lbl_status.setText("Error.")
    def refresh_cips_table(self):
        self.table_cips.setRowCount(0)
        self.data['cips'].sort(key=lambda x: x.get('abscisa_val', 0))
        for p in self.data['cips']:
            r = self.table_cips.rowCount()
            self.table_cips.insertRow(r)
            items = [
                str(p.get('abscisa') or ''),
                str(p.get('referencia') or ''),
                str(p.get('on_mv') or ''),
                str(p.get('off_mv') or ''),
                str(p.get('lat') or ''),
                str(p.get('lon') or ''),
                str(p.get('observaciones') or '')
            ]
            for c, txt in enumerate(items):
                self.table_cips.setItem(r, c, QTableWidgetItem(str(txt)))

    def load_rectificador(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Rectificador", "", "Excel (*.xlsx)")
        reader = RectificadorReader()
        for f in files:
            data = reader.read(f)
            if data:
                self.data['rectificadores'].append(data)
        self.refresh_rectificadores_table()

    def load_fotos(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Fotos")
        if not folder:
            return
            
        api_key = self.ai_key_input.text().strip()
        processor = PhotoProcessor(api_key=api_key if api_key else None)
        
        # Necesitamos el abscisa_calculator inicializado
        if not hasattr(self, 'abscisa_calculator') or not self.abscisa_calculator:
            QMessageBox.warning(self, "Atención", "Debe cargar primero el KMZ y un archivo EQUIPO o FASTFIELD para calcular las abscisas.")
            return

        import os
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            return
            
        progress = QProgressDialog("Analizando fotos y calculando abscisas...", "Cancelar", 0, len(image_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        nuevos_hallazgos = 0

        for i, filename in enumerate(image_files):
            if progress.wasCanceled():
                break
                
            progress.setValue(i)
            file_path = os.path.join(folder, filename)
            
            # Extraer EXIF
            exif = processor.get_exif_data(file_path)
            lat, lon = processor.get_gps_coordinates(exif)
            fecha_foto = processor.get_datetime(exif)
            
            if lat and lon:
                meters = self.abscisa_calculator.calculate(lat, lon)
                
                # Verificar si ya existe un hallazgo cercano (±20 metros)
                existe = False
                for h in self.data['hallazgos']:
                    if abs(h.get('abscisa_val', -9999) - meters) <= 20:
                        existe = True
                        break
                        
                # Verificar si existe un poste/potencial cercano (±20 metros)
                existe_potencial = False
                for p in self.data['potenciales']:
                    if abs(p.get('abscisa', -9999) - meters) <= 20:
                        existe_potencial = True
                        break
                        
                name_lower = filename.lower()
                # Palabras clave explícitas de hallazgos
                keywords = [
                    'via', 'vía', 
                    'caño', 
                    'tension', 'tensión', 'at', 'mt', 'bt', 
                    'enmontado', 'monte',
                    'privada', 'predio',
                    'cultivo'
                ]
                es_hallazgo_explicito = any(k in name_lower for k in keywords)

                if not existe:
                    # Si hay un poste cerca y el nombre de la foto no menciona un hallazgo explícito,
                    # asumimos que es una foto del poste y no la agregamos como hallazgo.
                    if existe_potencial and not es_hallazgo_explicito:
                        continue
                        
                    tipo = ""
                    if 'via' in name_lower or 'vía' in name_lower: tipo = "Cruce de Vía"
                    elif 'caño' in name_lower: tipo = "Cruce de Caño"
                    elif 'tension' in name_lower or 'tensión' in name_lower or ' at ' in name_lower or ' mt ' in name_lower or ' bt ' in name_lower: tipo = "Línea de media, alta o baja tensión"
                    elif 'enmontado' in name_lower or 'monte' in name_lower: tipo = "Tramo enmontado"
                    elif 'privada' in name_lower or 'predio' in name_lower: tipo = "Propiedad privada"
                    elif 'cultivo' in name_lower: tipo = "Cultivo"
                    
                    desc = f"Hallazgo generado automáticamente desde foto ({filename})"
                    
                    # Si no hay tipo claro y tenemos API KEY, usamos IA
                    if not tipo and api_key:
                        progress.setLabelText(f"Clasificando con IA: {filename}")
                        tipo_ia, desc_ia = processor.classify_image_with_ai(file_path)
                        if 'descartar' in tipo_ia.lower():
                            continue # El usuario pidió ignorar el resto
                        tipo = tipo_ia
                        desc = f"{desc_ia} (Autogenerado desde foto: {filename})"
                    elif not tipo:
                        # Si no hay IA y tampoco coincide la palabra clave, se descarta (a petición del usuario)
                        continue
                        
                    nuevo_h = {
                        'tipo': tipo,
                        'descripcion': desc,
                        'lat': lat,
                        'lon': lon,
                        'alt': None,
                        'abscisa_val': meters,
                        'abscisa': self.abscisa_calculator.format_abscisa(meters),
                        'fecha': fecha_foto.split(' ')[0] if fecha_foto else ''
                    }
                    self.data['hallazgos'].append(nuevo_h)
                    nuevos_hallazgos += 1
                    
        progress.setValue(len(image_files))
        
        # Sort hallazgos by abscisa
        self.data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
        self.refresh_hallazgos_table()
        
        QMessageBox.information(self, "Proceso Completado", f"Se han procesado {len(image_files)} fotos.\nSe agregaron {nuevos_hallazgos} nuevos hallazgos basados en el GPS.")

    def load_kmz(self):
        f, _ = QFileDialog.getOpenFileName(self, "Seleccionar KMZ", "", "KMZ (*.kmz)")
        if f:
            try:
                self.kmz_loader = KMZPipelineLoader(f)
                self.lbl_kmz_status.setText(f"KMZ Cargado: {os.path.basename(f)}")
                self.lbl_kmz_status.setStyleSheet("color: #69f0ae;")
                if hasattr(self, 'cmb_kmz_rutas'):
                    self.cmb_kmz_rutas.clear()
                    rutas = sorted(self.kmz_loader.get_all_route_ids())
                    self.cmb_kmz_rutas.addItems(["--- Auto-Detectar ---"] + rutas)
            except Exception as e:
                self.lbl_kmz_status.setText(f"Error cargando KMZ: {str(e)}")
                self.lbl_kmz_status.setStyleSheet("color: #ff5252;")

    def update_ruta_filter(self):
        if not hasattr(self, "cmb_filtro_ruta"): return
        rutas = set()
        for p in self.data['potenciales']:
            if p.get('route_id'):
                rutas.add(p['route_id'])
        for h in self.data['hallazgos']:
            if h.get('route_id'):
                rutas.add(h['route_id'])
        
        current = self.cmb_filtro_ruta.currentText()
        self.cmb_filtro_ruta.blockSignals(True)
        self.cmb_filtro_ruta.clear()
        self.cmb_filtro_ruta.addItem("Todas las Rutas")
        for r in sorted(list(rutas)):
            self.cmb_filtro_ruta.addItem(r)
            
        if current in rutas:
            self.cmb_filtro_ruta.setCurrentText(current)
        self.cmb_filtro_ruta.blockSignals(False)

    def apply_filter(self, text):
        self.refresh_potenciales_table()
        self.refresh_hallazgos_table()

    def get_filtered_data(self):
        if not hasattr(self, "cmb_filtro_ruta"): return self.data
        selected = self.cmb_filtro_ruta.currentText()
        if selected == "Todas las Rutas":
            return self.data
            
        filtered = {
            'info': self.data['info'], 
            'potenciales': [p for p in self.data['potenciales'] if p.get('route_id') == selected],
            'hallazgos': [h for h in self.data['hallazgos'] if h.get('route_id') == selected or not h.get('route_id')],
            'rectificadores': self.data['rectificadores'], 
            'aislamientos': self.data['aislamientos'],
            'inspecciones': {
                'marco_h': [m for m in self.data['inspecciones'].get('marco_h', []) if m.get('route_id') == selected or not m.get('route_id')],
                'tramos_aereos': [t for t in self.data['inspecciones'].get('tramos_aereos', []) if t.get('route_id') == selected or not t.get('route_id')]
            },
            'conclusiones': self.data['conclusiones'],
            'recomendaciones': self.data['recomendaciones'],
            'firmas': self.data['firmas'],
            'equipos_inspector': self.data.get('equipos_inspector', [])
        }
        return filtered


    def refresh_potenciales_table(self):
        self.table_pot.setRowCount(0)
        filtered_pots = self.get_filtered_data()['potenciales']
        for p in filtered_pots:
            r = self.table_pot.rowCount()
            self.table_pot.insertRow(r)
            items = [
                p.get('abscisa_str', ''), p.get('fecha', ''), p.get('ref_geografica', ''),
                str(p.get('on_mv') or ''), str(p.get('off_mv') or ''), str(p.get('vac') or ''),
                str(p.get('resistencia') or ''), str(p.get('ir_on_off') or ''),
                str(p.get('lat') or ''), str(p.get('lon') or ''),
                p.get('pintura', ''), p.get('conexiones', ''), p.get('tipo_mant', ''),
                p.get('observaciones', '')
            ]
            for c, txt in enumerate(items):
                item = QTableWidgetItem(txt)
                # Highlight bad values
                if c == 4: # OFF
                    v = p.get('off_mv')
                    if v is not None:
                        if v > -850: item.setForeground(QColor("#ff5252")) # Red
                        elif v <= -1200: item.setForeground(QColor("#ffd740")) # Yellow
                        else: item.setForeground(QColor("#69f0ae")) # Green
                self.table_pot.setItem(r, c, item)

    def refresh_hallazgos_table(self):
        self.table_hal.setRowCount(0)
        filtered_hals = self.get_filtered_data()['hallazgos']
        for h in filtered_hals:
            r = self.table_hal.rowCount()
            self.table_hal.insertRow(r)
            items = [
                str(h.get('abscisa') or ''), '', '', h.get('tipo', ''), h.get('descripcion', ''),
                str(h.get('lat') or ''), str(h.get('lon') or ''), h.get('fecha', '')
            ]
            for c, txt in enumerate(items):
                self.table_hal.setItem(r, c, QTableWidgetItem(str(txt or '')))

    def refresh_rectificadores_table(self):
        self.table_rect.setRowCount(0)
        for r_data in self.data['rectificadores']:
            r = self.table_rect.rowCount()
            self.table_rect.insertRow(r)
            ui = r_data.get('ultima_inspeccion', {})
            items = [
                r_data.get('nombre', ''), r_data.get('gasoducto', ''),
                str(r_data.get('voltaje_nominal') or ''), str(r_data.get('corriente_nominal') or ''),
                str(ui.get('vdc_salida') or ''), str(ui.get('idc_salida') or ''),
                str(ui.get('taps') or ''), str(ui.get('disponibilidad_v') or '')
            ]
            for c, txt in enumerate(items):
                self.table_rect.setItem(r, c, QTableWidgetItem(txt))

    def collect_info(self):
        import re
        # Gather data from UI
        from PyQt6.QtWidgets import QComboBox
        for k, widget in self.fields.items():
            if not k.startswith('elab') and not k.startswith('rev') and not k.startswith('aprob'):
                if isinstance(widget, QComboBox):
                    val = widget.currentText()
                else:
                    val = widget.text()
                
                # Clean Tramo name (strip " PK..." or " (PK...")
                if k == 'tramo' and val:
                    val = re.sub(r'\s*\(?PK.*', '', val).strip()
                    
                self.data['info'][k] = val
                
        # Set route_id
        selected = self.cmb_filtro_ruta.currentText() if hasattr(self, 'cmb_filtro_ruta') else ""
        if selected and selected != "Todas las Rutas":
            self.data['info']['route_id'] = selected
        else:
            self.data['info']['route_id'] = getattr(self, 'current_route_id', '') or ''
                
        # Calculamos longitud solo si no fue autocompletada desde OT
        filtered_data = self.get_filtered_data()
        if 'longitud_km' not in self.data['info']:
            if filtered_data['potenciales']:
                p_sort = sorted(filtered_data['potenciales'], key=lambda x: x.get('abscisa',0))
                self.data['info']['longitud_km'] = (p_sort[-1].get('abscisa',0) - p_sort[0].get('abscisa',0)) / 1000.0
            
        # self.data['inspecciones'] = self.active_inspections # BUGFIX: Don't overwrite the actual arrays
        
        # Firmas
        self.data['firmas']['elaboro'] = {
            'nombre': self.fields['elab_nombre'].text(),
            'cargo': self.fields['elab_cargo'].text(),
            'empresa': self.fields['elab_empresa'].text()
        }
        self.data['firmas']['reviso'] = {
            'nombre': self.fields['rev_nombre'].text(),
            'cargo': self.fields['rev_cargo'].text(),
            'empresa': self.fields['rev_empresa'].text()
        }
        self.data['firmas']['aprobo'] = {
            'nombre': self.fields['aprob_nombre'].text(),
            'cargo': self.fields['aprob_cargo'].text(),
            'empresa': self.fields['aprob_empresa'].text()
        }

    def auto_generate_conclusions(self):
        self.collect_info()
        filtered_data = self.get_filtered_data()
        cg = ConclusionGenerator(
            filtered_data['potenciales'], filtered_data['hallazgos'],
            filtered_data['rectificadores'], filtered_data['aislamientos'],
            self.active_inspections, filtered_data['info']
        )
        
        conclusiones = cg.generar_conclusiones()
        recomendaciones = cg.generar_recomendaciones()
        
        self.txt_conclusiones.setText("\n\n".join(conclusiones))
        self.txt_recomendaciones.setText("\n\n".join(recomendaciones))

    def refresh_cips_table(self):
        self.table_cips.setRowCount(0)
        self.data['cips'].sort(key=lambda x: x.get('abscisa_val', 0))
        for p in self.data['cips']:
            r = self.table_cips.rowCount()
            self.table_cips.insertRow(r)
            items = [
                str(p.get('abscisa') or ''),
                str(p.get('referencia') or ''),
                str(p.get('on_mv') or ''),
                str(p.get('off_mv') or ''),
                str(p.get('lat') or ''),
                str(p.get('lon') or ''),
                str(p.get('observaciones') or '')
            ]
            for c, txt in enumerate(items):
                self.table_cips.setItem(r, c, QTableWidgetItem(str(txt)))

    def load_rectificador(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Seleccionar Rectificador", "", "Excel (*.xlsx)")
        reader = RectificadorReader()
        for f in files:
            data = reader.read(f)
            if data:
                self.data['rectificadores'].append(data)
        self.refresh_rectificadores_table()

    def load_fotos(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Fotos")
        if not folder:
            return
            
        api_key = self.ai_key_input.text().strip()
        processor = PhotoProcessor(api_key=api_key if api_key else None)
        
        # Necesitamos el abscisa_calculator inicializado
        if not hasattr(self, 'abscisa_calculator') or not self.abscisa_calculator:
            QMessageBox.warning(self, "Atención", "Debe cargar primero el KMZ y un archivo EQUIPO o FASTFIELD para calcular las abscisas.")
            return

        import os
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        
        image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if not image_files:
            return
            
        progress = QProgressDialog("Analizando fotos y calculando abscisas...", "Cancelar", 0, len(image_files), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        nuevos_hallazgos = 0

        for i, filename in enumerate(image_files):
            if progress.wasCanceled():
                break
                
            progress.setValue(i)
            file_path = os.path.join(folder, filename)
            
            # Extraer EXIF
            exif = processor.get_exif_data(file_path)
            lat, lon = processor.get_gps_coordinates(exif)
            fecha_foto = processor.get_datetime(exif)
            
            if lat and lon:
                meters = self.abscisa_calculator.calculate(lat, lon)
                
                # Verificar si ya existe un hallazgo cercano (±20 metros)
                existe = False
                for h in self.data['hallazgos']:
                    if abs(h.get('abscisa_val', -9999) - meters) <= 20:
                        existe = True
                        break
                        
                # Verificar si existe un poste/potencial cercano (±20 metros)
                existe_potencial = False
                for p in self.data['potenciales']:
                    if abs(p.get('abscisa', -9999) - meters) <= 20:
                        existe_potencial = True
                        break
                        
                name_lower = filename.lower()
                # Palabras clave explícitas de hallazgos
                keywords = [
                    'via', 'vía', 
                    'caño', 
                    'tension', 'tensión', 'at', 'mt', 'bt', 
                    'enmontado', 'monte',
                    'privada', 'predio',
                    'cultivo'
                ]
                es_hallazgo_explicito = any(k in name_lower for k in keywords)

                if not existe:
                    # Si hay un poste cerca y el nombre de la foto no menciona un hallazgo explícito,
                    # asumimos que es una foto del poste y no la agregamos como hallazgo.
                    if existe_potencial and not es_hallazgo_explicito:
                        continue
                        
                    tipo = ""
                    if 'via' in name_lower or 'vía' in name_lower: tipo = "Cruce de Vía"
                    elif 'caño' in name_lower: tipo = "Cruce de Caño"
                    elif 'tension' in name_lower or 'tensión' in name_lower or ' at ' in name_lower or ' mt ' in name_lower or ' bt ' in name_lower: tipo = "Línea de media, alta o baja tensión"
                    elif 'enmontado' in name_lower or 'monte' in name_lower: tipo = "Tramo enmontado"
                    elif 'privada' in name_lower or 'predio' in name_lower: tipo = "Propiedad privada"
                    elif 'cultivo' in name_lower: tipo = "Cultivo"
                    
                    desc = f"Hallazgo generado automáticamente desde foto ({filename})"
                    
                    # Si no hay tipo claro y tenemos API KEY, usamos IA
                    if not tipo and api_key:
                        progress.setLabelText(f"Clasificando con IA: {filename}")
                        tipo_ia, desc_ia = processor.classify_image_with_ai(file_path)
                        if 'descartar' in tipo_ia.lower():
                            continue # El usuario pidió ignorar el resto
                        tipo = tipo_ia
                        desc = f"{desc_ia} (Autogenerado desde foto: {filename})"
                    elif not tipo:
                        # Si no hay IA y tampoco coincide la palabra clave, se descarta (a petición del usuario)
                        continue
                        
                    nuevo_h = {
                        'tipo': tipo,
                        'descripcion': desc,
                        'lat': lat,
                        'lon': lon,
                        'alt': None,
                        'abscisa_val': meters,
                        'abscisa': self.abscisa_calculator.format_abscisa(meters),
                        'fecha': fecha_foto.split(' ')[0] if fecha_foto else ''
                    }
                    self.data['hallazgos'].append(nuevo_h)
                    nuevos_hallazgos += 1
                    
        progress.setValue(len(image_files))
        
        # Sort hallazgos by abscisa
        self.data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
        self.refresh_hallazgos_table()
        
        QMessageBox.information(self, "Proceso Completado", f"Se han procesado {len(image_files)} fotos.\nSe agregaron {nuevos_hallazgos} nuevos hallazgos basados en el GPS.")

    def load_kmz(self):
        f, _ = QFileDialog.getOpenFileName(self, "Seleccionar KMZ", "", "KMZ (*.kmz)")
        if f:
            try:
                self.kmz_loader = KMZPipelineLoader(f)
                self.lbl_kmz_status.setText(f"KMZ Cargado: {os.path.basename(f)}")
                self.lbl_kmz_status.setStyleSheet("color: #69f0ae;")
                if hasattr(self, 'cmb_kmz_rutas'):
                    self.cmb_kmz_rutas.clear()
                    rutas = sorted(self.kmz_loader.get_all_route_ids())
                    self.cmb_kmz_rutas.addItems(["--- Auto-Detectar ---"] + rutas)
            except Exception as e:
                self.lbl_kmz_status.setText(f"Error cargando KMZ: {str(e)}")
                self.lbl_kmz_status.setStyleSheet("color: #ff5252;")

    def update_ruta_filter(self):
        if not hasattr(self, "cmb_filtro_ruta"): return
        rutas = set()
        for p in self.data['potenciales']:
            if p.get('route_id'):
                rutas.add(p['route_id'])
        for h in self.data['hallazgos']:
            if h.get('route_id'):
                rutas.add(h['route_id'])
        
        current = self.cmb_filtro_ruta.currentText()
        self.cmb_filtro_ruta.blockSignals(True)
        self.cmb_filtro_ruta.clear()
        self.cmb_filtro_ruta.addItem("Todas las Rutas")
        for r in sorted(list(rutas)):
            self.cmb_filtro_ruta.addItem(r)
            
        if current in rutas:
            self.cmb_filtro_ruta.setCurrentText(current)
        self.cmb_filtro_ruta.blockSignals(False)

    def apply_filter(self, text):
        self.refresh_potenciales_table()
        self.refresh_hallazgos_table()

    def get_filtered_data(self):
        if not hasattr(self, "cmb_filtro_ruta"): return self.data
        selected = self.cmb_filtro_ruta.currentText()
        if selected == "Todas las Rutas":
            return self.data
            
        filtered = {
            'info': self.data['info'], 
            'potenciales': [p for p in self.data['potenciales'] if p.get('route_id') == selected],
            'hallazgos': [h for h in self.data['hallazgos'] if h.get('route_id') == selected or not h.get('route_id')],
            'rectificadores': self.data['rectificadores'], 
            'aislamientos': self.data['aislamientos'],
            'inspecciones': {
                'marco_h': [m for m in self.data['inspecciones'].get('marco_h', []) if m.get('route_id') == selected or not m.get('route_id')],
                'tramos_aereos': [t for t in self.data['inspecciones'].get('tramos_aereos', []) if t.get('route_id') == selected or not t.get('route_id')]
            },
            'conclusiones': self.data['conclusiones'],
            'recomendaciones': self.data['recomendaciones'],
            'firmas': self.data['firmas'],
            'equipos_inspector': self.data.get('equipos_inspector', [])
        }
        return filtered

    def refresh_potenciales_table(self):
        self.table_pot.setRowCount(0)
        filtered_pots = self.get_filtered_data()['potenciales']
        for p in filtered_pots:
            r = self.table_pot.rowCount()
            self.table_pot.insertRow(r)
            items = [
                p.get('abscisa_str', ''), p.get('fecha', ''), p.get('ref_geografica', ''),
                str(p.get('on_mv') or ''), str(p.get('off_mv') or ''), str(p.get('vac') or ''),
                str(p.get('resistencia') or ''), str(p.get('ir_on_off') or ''),
                str(p.get('lat') or ''), str(p.get('lon') or ''),
                p.get('pintura', ''), p.get('conexiones', ''), p.get('tipo_mant', ''),
                p.get('observaciones', '')
            ]
            for c, txt in enumerate(items):
                item = QTableWidgetItem(txt)
                # Highlight bad values
                if c == 4: # OFF
                    v = p.get('off_mv')
                    if v is not None:
                        if v > -850: item.setForeground(QColor("#ff5252")) # Red
                        elif v <= -1200: item.setForeground(QColor("#ffd740")) # Yellow
                        else: item.setForeground(QColor("#69f0ae")) # Green
                self.table_pot.setItem(r, c, item)

    def refresh_hallazgos_table(self):
        self.table_hal.setRowCount(0)
        filtered_hals = self.get_filtered_data()['hallazgos']
        for h in filtered_hals:
            r = self.table_hal.rowCount()
            self.table_hal.insertRow(r)
            items = [
                str(h.get('abscisa') or ''), '', '', h.get('tipo', ''), h.get('descripcion', ''),
                str(h.get('lat') or ''), str(h.get('lon') or ''), h.get('fecha', '')
            ]
            for c, txt in enumerate(items):
                self.table_hal.setItem(r, c, QTableWidgetItem(str(txt or '')))

    def refresh_rectificadores_table(self):
        self.table_rect.setRowCount(0)
        for r_data in self.data['rectificadores']:
            r = self.table_rect.rowCount()
            self.table_rect.insertRow(r)
            ui = r_data.get('ultima_inspeccion', {})
            items = [
                r_data.get('nombre', ''), r_data.get('gasoducto', ''),
                str(r_data.get('voltaje_nominal') or ''), str(r_data.get('corriente_nominal') or ''),
                str(ui.get('vdc_salida') or ''), str(ui.get('idc_salida') or ''),
                str(ui.get('taps') or ''), str(ui.get('disponibilidad_v') or '')
            ]
            for c, txt in enumerate(items):
                self.table_rect.setItem(r, c, QTableWidgetItem(txt))

    def collect_info(self):
        import re
        # Gather data from UI
        from PyQt6.QtWidgets import QComboBox
        for k, widget in self.fields.items():
            if not k.startswith('elab') and not k.startswith('rev') and not k.startswith('aprob'):
                if isinstance(widget, QComboBox):
                    val = widget.currentText()
                else:
                    val = widget.text()
                
                # Clean Tramo name (strip " PK..." or " (PK...")
                if k == 'tramo' and val:
                    val = re.sub(r'\s*\(?PK.*', '', val).strip()
                    
                self.data['info'][k] = val
                
        # Set route_id
        selected = self.cmb_filtro_ruta.currentText() if hasattr(self, 'cmb_filtro_ruta') else ""
        if selected and selected != "Todas las Rutas":
            self.data['info']['route_id'] = selected
        else:
            self.data['info']['route_id'] = getattr(self, 'current_route_id', '') or ''
                
        # Calculamos longitud solo si no fue autocompletada desde OT
        filtered_data = self.get_filtered_data()
        if 'longitud_km' not in self.data['info']:
            if filtered_data['potenciales']:
                p_sort = sorted(filtered_data['potenciales'], key=lambda x: x.get('abscisa',0))
                self.data['info']['longitud_km'] = (p_sort[-1].get('abscisa',0) - p_sort[0].get('abscisa',0)) / 1000.0
            
        # self.data['inspecciones'] = self.active_inspections # BUGFIX: Don't overwrite the actual arrays
        
        # Firmas
        self.data['firmas']['elaboro'] = {
            'nombre': self.fields['elab_nombre'].text(),
            'cargo': self.fields['elab_cargo'].text(),
            'empresa': self.fields['elab_empresa'].text()
        }
        self.data['firmas']['reviso'] = {
            'nombre': self.fields['rev_nombre'].text(),
            'cargo': self.fields['rev_cargo'].text(),
            'empresa': self.fields['rev_empresa'].text()
        }
        self.data['firmas']['aprobo'] = {
            'nombre': self.fields['aprob_nombre'].text(),
            'cargo': self.fields['aprob_cargo'].text(),
            'empresa': self.fields['aprob_empresa'].text()
        }

    def auto_generate_conclusions(self):
        self.collect_info()
        filtered_data = self.get_filtered_data()
        cg = ConclusionGenerator(
            filtered_data['potenciales'], filtered_data['hallazgos'],
            filtered_data['rectificadores'], filtered_data['aislamientos'],
            self.active_inspections, filtered_data['info']
        )
        
        conclusiones = cg.generar_conclusiones()
        recomendaciones = cg.generar_recomendaciones()
        
        self.txt_conclusiones.setText("\n\n".join(conclusiones))
        self.txt_recomendaciones.setText("\n\n".join(recomendaciones))


    def generar_informe(self):
        self.collect_info()
        self.data['conclusiones'] = [p.strip() for p in self.txt_conclusiones.toPlainText().split('\n\n') if p.strip()]
        self.data['recomendaciones'] = [p.strip() for p in self.txt_recomendaciones.toPlainText().split('\n\n') if p.strip()]
        
        filtered_data = self.get_filtered_data()
        # Ensure we pass the updated conclusions/firmas
        filtered_data['conclusiones'] = self.data['conclusiones']
        filtered_data['recomendaciones'] = self.data['recomendaciones']
        filtered_data['firmas'] = self.data['firmas']
        
        # Prepare rectificadores string for general info description
        nombres_rect = [r.get('nombre') for r in filtered_data.get('rectificadores', []) if r.get('nombre')]
        if nombres_rect:
            filtered_data['info']['rectificadores_tgi'] = ", ".join(nombres_rect)
        else:
            filtered_data['info']['rectificadores_tgi'] = "[ESCRIBIR RECTIFICADORES TGI]"
            
        info_d = filtered_data.get('info', {})
        default_name = f"PAP_REP_{info_d.get('tipo_tramo','')}_{info_d.get('tramo','')}_{info_d.get('route_id','')}_{info_d.get('contrato','')}_PCC_RevA.xlsx"
        
        out_path, _ = QFileDialog.getSaveFileName(self, "Guardar Informe", default_name, "Excel (*.xlsx)")
        if not out_path:
            return
            
        self.btn_generar.setEnabled(False)
        self.worker = WorkerThread(filtered_data, out_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self.lbl_status.setText)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.start()

    def on_generation_finished(self, path):
        self.btn_generar.setEnabled(True)
        QMessageBox.information(self, "Éxito", f"Informe generado exitosamente en:\n{path}")
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Listo.")

    def on_generation_error(self, err):
        self.btn_generar.setEnabled(True)
        QMessageBox.critical(self, "Error", f"Ocurrió un error al generar el informe:\n{err}")
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Error.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = AppWindow()
    window.show()
    sys.exit(app.exec())

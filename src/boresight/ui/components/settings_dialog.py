from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QLineEdit, QFormLayout, QGroupBox, QTabWidget, QWidget, QScrollArea)
from PySide6.QtCore import QSettings, Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Configuration Settings")
        self.resize(550, 800)
        self.settings = QSettings("Shotover", "BoresightTool")
        
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # ---------------------------------------------------------
        # TAB 1: SYSTEM PROFILES
        # ---------------------------------------------------------
        self.tab_profiles_scroll = QScrollArea()
        self.tab_profiles_scroll.setWidgetResizable(True)
        self.tab_profiles = QWidget()
        profile_layout = QVBoxLayout(self.tab_profiles)
        
        self.profile_inputs = {}
        
        def add_profile_group(title, prefix, default_range):
            group = QGroupBox(title)
            form = QFormLayout(group)
            
            inputs = {
                'range': QLineEdit(str(self.settings.value(f"{prefix}/range", default_range))),
                'canvas': QLineEdit(str(self.settings.value(f"{prefix}/canvas", 3840.0))),
                'eon_focal': QLineEdit(str(self.settings.value(f"{prefix}/eon_focal", 504.0))),
                'eon_pitch': QLineEdit(str(self.settings.value(f"{prefix}/eon_pitch", 0.00274))),
                'eon_w': QLineEdit(str(self.settings.value(f"{prefix}/eon_w", 5328.0))),
                'mwir_focal': QLineEdit(str(self.settings.value(f"{prefix}/focal", 420.0))),
                'mwir_pitch': QLineEdit(str(self.settings.value(f"{prefix}/pitch", 0.010))),
                'mwir_w': QLineEdit(str(self.settings.value(f"{prefix}/mwir_w", 1280.0)))
            }
            
            form.addRow("Target Range (m):", inputs['range'])
            form.addRow("Canvas Width (px):", inputs['canvas'])
            form.addRow("EON Focal Length (mm):", inputs['eon_focal'])
            form.addRow("EON Native Pitch (mm):", inputs['eon_pitch'])
            form.addRow("EON Native Width (px):", inputs['eon_w'])
            form.addRow("MWIR Focal Length (mm):", inputs['mwir_focal'])
            form.addRow("MWIR Native Pitch (mm):", inputs['mwir_pitch'])
            form.addRow("MWIR Native Width (px):", inputs['mwir_w'])
            
            profile_layout.addWidget(group)
            self.profile_inputs[prefix] = inputs

        add_profile_group("Shotover-NZ Defaults", "nz", 3880.75)
        add_profile_group("Shotover-Boulder Defaults", "boulder", 4500.0)
        add_profile_group("User Defined Defaults", "user", 3880.75)
        
        self.btn_reset_profiles = QPushButton("Restore Factory Profile Defaults")
        self.btn_reset_profiles.setAutoDefault(False)
        self.btn_reset_profiles.clicked.connect(self.reset_profile_defaults)
        profile_layout.addWidget(self.btn_reset_profiles)
        
        self.tab_profiles_scroll.setWidget(self.tab_profiles)
        self.tabs.addTab(self.tab_profiles_scroll, "System Profiles")

        # ---------------------------------------------------------
        # TAB 2: ROI & MASKING CONFIG
        # ---------------------------------------------------------
        self.tab_roi = QWidget()
        roi_layout = QVBoxLayout(self.tab_roi)
        self.roi_form = QFormLayout()
        
        self.roi_inputs = {}
        defaults = {
            'roi_x_min': 940, 'roi_x_max': 980, 'roi_y_min': 420, 'roi_y_max': 560,
            'search_y_min_eon': 460, 'search_y_max_eon': 510, 'search_y_min_mwir': 460, 'search_y_max_mwir': 510,
            'horizon_x_min': 800, 'horizon_x_max': 1120, 'horizon_y_min': 520, 'horizon_y_max': 570,
            'stroke_dilation': 7, 'line_dilation': 3, 'min_mast_prominence': 0.0, 'min_horizon_gradient': 0.0
        }
        for key, def_val in defaults.items():
            current_val = self.settings.value(f"roi/{key}", def_val)
            le = QLineEdit(str(current_val))
            self.roi_inputs[key] = le
            self.roi_form.addRow(key + ":", le)
            
        roi_group = QGroupBox("ROI & Masking Variables")
        roi_group.setLayout(self.roi_form)
        roi_layout.addWidget(roi_group)
        
        self.btn_reset_roi = QPushButton("Restore Factory ROI Defaults")
        self.btn_reset_roi.setAutoDefault(False)
        self.btn_reset_roi.clicked.connect(self.reset_roi_defaults)
        roi_layout.addWidget(self.btn_reset_roi)
        self.tabs.addTab(self.tab_roi, "ROI & Masking")

        # ---------------------------------------------------------
        # TAB 3: IMAGE OUTPUT DIMENSIONS
        # ---------------------------------------------------------
        self.tab_dims = QWidget()
        dims_layout = QVBoxLayout(self.tab_dims)
        
        self.dims_group = QGroupBox("Camera Image Output Dimensions (Pixels)")
        dims_form = QFormLayout(self.dims_group)
        self.inp_eon_w = QLineEdit(str(self.settings.value("dims/eon_w", 3840.0)))
        self.inp_eon_h = QLineEdit(str(self.settings.value("dims/eon_h", 2160.0)))
        self.inp_mwir_w = QLineEdit(str(self.settings.value("dims/mwir_w", 1280.0)))
        self.inp_mwir_h = QLineEdit(str(self.settings.value("dims/mwir_h", 720.0)))
        
        dims_form.addRow("EON Output Image Width:", self.inp_eon_w)
        dims_form.addRow("EON Output Image Height:", self.inp_eon_h)
        dims_form.addRow("MWIR Output Image Width:", self.inp_mwir_w)
        dims_form.addRow("MWIR Output Image Height:", self.inp_mwir_h)
        dims_layout.addWidget(self.dims_group)
        
        self.btn_reset_dims = QPushButton("Restore Dimensions")
        self.btn_reset_dims.setAutoDefault(False)
        self.btn_reset_dims.clicked.connect(self.reset_dims_defaults)
        dims_layout.addWidget(self.btn_reset_dims)
        dims_layout.addStretch()
        
        self.tabs.addTab(self.tab_dims, "Image Dimensions")

        main_layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setAutoDefault(False)
        self.btn_save.clicked.connect(self.save_settings)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setAutoDefault(False)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            return 
        super().keyPressEvent(event)

    def reset_profile_defaults(self):
        defaults = {
            'range': {'nz': '3880.75', 'boulder': '4500.0', 'user': '3880.75'},
            'canvas': '3840.0',
            'eon_focal': '504.0',
            'eon_pitch': '0.00274',
            'eon_w': '5328.0',
            'mwir_focal': '420.0',
            'mwir_pitch': '0.010',
            'mwir_w': '1280.0'
        }
        for prefix, inputs in self.profile_inputs.items():
            inputs['range'].setText(defaults['range'][prefix])
            inputs['canvas'].setText(defaults['canvas'])
            inputs['eon_focal'].setText(defaults['eon_focal'])
            inputs['eon_pitch'].setText(defaults['eon_pitch'])
            inputs['eon_w'].setText(defaults['eon_w'])
            inputs['mwir_focal'].setText(defaults['mwir_focal'])
            inputs['mwir_pitch'].setText(defaults['mwir_pitch'])
            inputs['mwir_w'].setText(defaults['mwir_w'])

    def reset_roi_defaults(self):
        defaults = {
            'roi_x_min': 940, 'roi_x_max': 980, 'roi_y_min': 420, 'roi_y_max': 560,
            'search_y_min_eon': 460, 'search_y_max_eon': 510, 'search_y_min_mwir': 460, 'search_y_max_mwir': 510,
            'horizon_x_min': 800, 'horizon_x_max': 1120, 'horizon_y_min': 520, 'horizon_y_max': 570,
            'stroke_dilation': 7, 'line_dilation': 3, 'min_mast_prominence': 0.0, 'min_horizon_gradient': 0.0
        }
        for key, def_val in defaults.items(): self.roi_inputs[key].setText(str(def_val))

    def reset_dims_defaults(self):
        self.inp_eon_w.setText("3840.0")
        self.inp_eon_h.setText("2160.0")
        self.inp_mwir_w.setText("1280.0")
        self.inp_mwir_h.setText("720.0")

    def save_settings(self):
        for prefix, inputs in self.profile_inputs.items():
            self.settings.setValue(f"{prefix}/range", inputs['range'].text())
            self.settings.setValue(f"{prefix}/canvas", inputs['canvas'].text())
            self.settings.setValue(f"{prefix}/eon_focal", inputs['eon_focal'].text())
            self.settings.setValue(f"{prefix}/eon_pitch", inputs['eon_pitch'].text())
            self.settings.setValue(f"{prefix}/eon_w", inputs['eon_w'].text())
            self.settings.setValue(f"{prefix}/focal", inputs['mwir_focal'].text())
            self.settings.setValue(f"{prefix}/pitch", inputs['mwir_pitch'].text())
            self.settings.setValue(f"{prefix}/mwir_w", inputs['mwir_w'].text())
        
        for key, le in self.roi_inputs.items():
            if 'prominence' in key or 'gradient' in key: self.settings.setValue(f"roi/{key}", float(le.text()))
            else: self.settings.setValue(f"roi/{key}", int(float(le.text())))

        self.settings.setValue("dims/eon_w", self.inp_eon_w.text())
        self.settings.setValue("dims/eon_h", self.inp_eon_h.text())
        self.settings.setValue("dims/mwir_w", self.inp_mwir_w.text())
        self.settings.setValue("dims/mwir_h", self.inp_mwir_h.text())
        
        self.accept()
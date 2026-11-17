from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QLineEdit, QFormLayout, QGroupBox, QTabWidget, QWidget)
from PySide6.QtCore import QSettings, Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Global Configuration Settings")
        self.resize(500, 750)
        self.settings = QSettings("Shotover", "BoresightTool")
        
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # ---------------------------------------------------------
        # TAB 1: SYSTEM PROFILES
        # ---------------------------------------------------------
        self.tab_profiles = QWidget()
        profile_layout = QVBoxLayout(self.tab_profiles)
        
        self.nz_group = QGroupBox("Shotover-NZ Defaults")
        nz_form = QFormLayout(self.nz_group)
        self.nz_range = QLineEdit(str(self.settings.value("nz/range", 3880.75)))
        self.nz_focal = QLineEdit(str(self.settings.value("nz/focal", 420.0)))
        self.nz_pitch = QLineEdit(str(self.settings.value("nz/pitch", 0.010)))
        self.nz_mwir_w = QLineEdit(str(self.settings.value("nz/mwir_w", 1280.0)))
        self.nz_canvas = QLineEdit(str(self.settings.value("nz/canvas", 3840.0)))
        nz_form.addRow("Range (m):", self.nz_range)
        nz_form.addRow("MWIR Focal Length (mm):", self.nz_focal)
        nz_form.addRow("MWIR Native Pitch (mm):", self.nz_pitch)
        nz_form.addRow("MWIR Native Width (px):", self.nz_mwir_w)
        nz_form.addRow("Canvas Width (px):", self.nz_canvas)
        profile_layout.addWidget(self.nz_group)
        
        self.boulder_group = QGroupBox("Shotover-Boulder Defaults")
        boulder_form = QFormLayout(self.boulder_group)
        self.boulder_range = QLineEdit(str(self.settings.value("boulder/range", 4500.0)))
        self.boulder_focal = QLineEdit(str(self.settings.value("boulder/focal", 420.0)))
        self.boulder_pitch = QLineEdit(str(self.settings.value("boulder/pitch", 0.010)))
        self.boulder_mwir_w = QLineEdit(str(self.settings.value("boulder/mwir_w", 1280.0)))
        self.boulder_canvas = QLineEdit(str(self.settings.value("boulder/canvas", 3840.0)))
        boulder_form.addRow("Range (m):", self.boulder_range)
        boulder_form.addRow("MWIR Focal Length (mm):", self.boulder_focal)
        boulder_form.addRow("MWIR Native Pitch (mm):", self.boulder_pitch)
        boulder_form.addRow("MWIR Native Width (px):", self.boulder_mwir_w)
        boulder_form.addRow("Canvas Width (px):", self.boulder_canvas)
        profile_layout.addWidget(self.boulder_group)
        
        self.user_group = QGroupBox("User Defined Defaults")
        user_form = QFormLayout(self.user_group)
        self.user_range = QLineEdit(str(self.settings.value("user/range", 3880.75)))
        self.user_focal = QLineEdit(str(self.settings.value("user/focal", 420.0)))
        self.user_pitch = QLineEdit(str(self.settings.value("user/pitch", 0.010)))
        self.user_mwir_w = QLineEdit(str(self.settings.value("user/mwir_w", 1280.0)))
        self.user_canvas = QLineEdit(str(self.settings.value("user/canvas", 3840.0)))
        user_form.addRow("Range (m):", self.user_range)
        user_form.addRow("MWIR Focal Length (mm):", self.user_focal)
        user_form.addRow("MWIR Native Pitch (mm):", self.user_pitch)
        user_form.addRow("MWIR Native Width (px):", self.user_mwir_w)
        user_form.addRow("Canvas Width (px):", self.user_canvas)
        profile_layout.addWidget(self.user_group)
        
        self.btn_reset_profiles = QPushButton("Restore Factory Profile Defaults")
        self.btn_reset_profiles.setAutoDefault(False)
        self.btn_reset_profiles.clicked.connect(self.reset_profile_defaults)
        profile_layout.addWidget(self.btn_reset_profiles)
        
        self.tabs.addTab(self.tab_profiles, "System Profiles")

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
        """Intercept Enter key so it doesn't accidentally trigger dialog accept or random buttons"""
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            return 
        super().keyPressEvent(event)

    def reset_profile_defaults(self):
        self.nz_range.setText("3880.75")
        self.nz_focal.setText("420.0")
        self.nz_pitch.setText("0.010")
        self.nz_mwir_w.setText("1280.0")
        self.nz_canvas.setText("3840.0")
        
        self.boulder_range.setText("4500.0")
        self.boulder_focal.setText("420.0")
        self.boulder_pitch.setText("0.010")
        self.boulder_mwir_w.setText("1280.0")
        self.boulder_canvas.setText("3840.0")
        
        self.user_range.setText("3880.75")
        self.user_focal.setText("420.0")
        self.user_pitch.setText("0.010")
        self.user_mwir_w.setText("1280.0")
        self.user_canvas.setText("3840.0")

    def reset_roi_defaults(self):
        defaults = {
            'roi_x_min': 940, 'roi_x_max': 980, 'roi_y_min': 420, 'roi_y_max': 560,
            'search_y_min_eon': 460, 'search_y_max_eon': 510, 'search_y_min_mwir': 460, 'search_y_max_mwir': 510,
            'horizon_x_min': 800, 'horizon_x_max': 1120, 'horizon_y_min': 520, 'horizon_y_max': 570,
            'stroke_dilation': 7, 'line_dilation': 3, 'min_mast_prominence': 0.0, 'min_horizon_gradient': 0.0
        }
        for key, def_val in defaults.items(): self.roi_inputs[key].setText(str(def_val))

    def save_settings(self):
        self.settings.setValue("nz/range", self.nz_range.text())
        self.settings.setValue("nz/focal", self.nz_focal.text())
        self.settings.setValue("nz/pitch", self.nz_pitch.text())
        self.settings.setValue("nz/mwir_w", self.nz_mwir_w.text())
        self.settings.setValue("nz/canvas", self.nz_canvas.text())
        
        self.settings.setValue("boulder/range", self.boulder_range.text())
        self.settings.setValue("boulder/focal", self.boulder_focal.text())
        self.settings.setValue("boulder/pitch", self.boulder_pitch.text())
        self.settings.setValue("boulder/mwir_w", self.boulder_mwir_w.text())
        self.settings.setValue("boulder/canvas", self.boulder_canvas.text())
        
        self.settings.setValue("user/range", self.user_range.text())
        self.settings.setValue("user/focal", self.user_focal.text())
        self.settings.setValue("user/pitch", self.user_pitch.text())
        self.settings.setValue("user/mwir_w", self.user_mwir_w.text())
        self.settings.setValue("user/canvas", self.user_canvas.text())
        
        for key, le in self.roi_inputs.items():
            if 'prominence' in key or 'gradient' in key: self.settings.setValue(f"roi/{key}", float(le.text()))
            else: self.settings.setValue(f"roi/{key}", int(float(le.text())))
        self.accept()
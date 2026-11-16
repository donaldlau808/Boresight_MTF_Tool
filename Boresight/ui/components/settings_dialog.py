from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                               QLineEdit, QGroupBox, QPushButton)
from PySide6.QtCore import QSettings

class SettingsDialog(QDialog):
    """Dialog to configure and save System Constant Profiles."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure System Profiles")
        self.setMinimumWidth(400)
        self.settings = QSettings("Shotover", "BoresightTool")
        layout = QVBoxLayout(self)

        self.form_nz = QFormLayout()
        self.nz_range = QLineEdit(str(self.settings.value("nz/range", 3880.75)))
        self.nz_focal = QLineEdit(str(self.settings.value("nz/focal", 420.0)))
        self.nz_pitch = QLineEdit(str(self.settings.value("nz/pitch", 0.010)))
        self.nz_mwir_w = QLineEdit(str(self.settings.value("nz/mwir_w", 1280.0)))
        self.nz_canvas = QLineEdit(str(self.settings.value("nz/canvas", 3840.0)))
        
        gb_nz = QGroupBox("Shotover-NZ Defaults")
        self.form_nz.addRow("Target Range (m):", self.nz_range)
        self.form_nz.addRow("Focal Length (mm):", self.nz_focal)
        self.form_nz.addRow("Pixel Pitch (mm):", self.nz_pitch)
        self.form_nz.addRow("Native Width (px):", self.nz_mwir_w)
        self.form_nz.addRow("Canvas Width (px):", self.nz_canvas)
        gb_nz.setLayout(self.form_nz)

        self.form_b = QFormLayout()
        self.b_range = QLineEdit(str(self.settings.value("boulder/range", 4500.0)))
        self.b_focal = QLineEdit(str(self.settings.value("boulder/focal", 420.0)))
        self.b_pitch = QLineEdit(str(self.settings.value("boulder/pitch", 0.010)))
        self.b_mwir_w = QLineEdit(str(self.settings.value("boulder/mwir_w", 1280.0)))
        self.b_canvas = QLineEdit(str(self.settings.value("boulder/canvas", 3840.0)))
        
        gb_b = QGroupBox("Shotover-Boulder Defaults")
        self.form_b.addRow("Target Range (m):", self.b_range)
        self.form_b.addRow("Focal Length (mm):", self.b_focal)
        self.form_b.addRow("Pixel Pitch (mm):", self.b_pitch)
        self.form_b.addRow("Native Width (px):", self.b_mwir_w)
        self.form_b.addRow("Canvas Width (px):", self.b_canvas)
        gb_b.setLayout(self.form_b)

        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self.save_settings)
        
        layout.addWidget(gb_nz)
        layout.addWidget(gb_b)
        layout.addWidget(btn_save)

    def save_settings(self):
        self.settings.setValue("nz/range", self.nz_range.text())
        self.settings.setValue("nz/focal", self.nz_focal.text())
        self.settings.setValue("nz/pitch", self.nz_pitch.text())
        self.settings.setValue("nz/mwir_w", self.nz_mwir_w.text())
        self.settings.setValue("nz/canvas", self.nz_canvas.text())

        self.settings.setValue("boulder/range", self.b_range.text())
        self.settings.setValue("boulder/focal", self.b_focal.text())
        self.settings.setValue("boulder/pitch", self.b_pitch.text())
        self.settings.setValue("boulder/mwir_w", self.b_mwir_w.text())
        self.settings.setValue("boulder/canvas", self.b_canvas.text())
        self.accept()
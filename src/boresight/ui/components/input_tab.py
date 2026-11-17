from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                               QComboBox, QPushButton, QLabel, QFormLayout, QLineEdit, QSplitter)
from PySide6.QtCore import Qt
from boresight.ui.components.custom_labels import ClickableLabel

class InputTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        const_group = QGroupBox("System Constants")
        const_layout = QVBoxLayout(const_group)
        
        profile_layout = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItems(["Shotover-NZ", "Shotover-Boulder", "User Defined"])
        
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setMaximumWidth(100)
        
        profile_layout.addWidget(QLabel("Load Profile:"))
        profile_layout.addWidget(self.cmb_profile, stretch=1)
        profile_layout.addWidget(self.btn_settings)
        const_layout.addLayout(profile_layout)
        
        form_layout = QHBoxLayout()
        form1 = QFormLayout()
        self.inp_range = QLineEdit()
        self.inp_range.setReadOnly(True)
        self.inp_focal = QLineEdit()
        self.inp_focal.setReadOnly(True)
        form1.addRow("Target Range (m):", self.inp_range)
        form1.addRow("MWIR Focal Length (mm):", self.inp_focal)
        
        form2 = QFormLayout()
        self.inp_pitch = QLineEdit()
        self.inp_pitch.setReadOnly(True)
        self.inp_mwir_w = QLineEdit()
        self.inp_mwir_w.setReadOnly(True)
        self.inp_canvas_w = QLineEdit()
        self.inp_canvas_w.setReadOnly(True)
        form2.addRow("MWIR Native Pitch (mm):", self.inp_pitch)
        form2.addRow("MWIR Native Width (px):", self.inp_mwir_w)
        form2.addRow("Screenshot Canvas Width (px):", self.inp_canvas_w)
        
        form_layout.addLayout(form1)
        form_layout.addLayout(form2)
        const_layout.addLayout(form_layout)
        layout.addWidget(const_group)
        
        self.input_splitter = QSplitter(Qt.Horizontal)
        self.eon_label = ClickableLabel("EON")
        self.mwir_label = ClickableLabel("MWIR")
        self.input_splitter.addWidget(self.eon_label)
        self.input_splitter.addWidget(self.mwir_label)
        layout.addWidget(self.input_splitter, stretch=1)
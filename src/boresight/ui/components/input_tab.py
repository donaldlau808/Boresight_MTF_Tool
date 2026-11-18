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
        
        # Shared top constants
        form_top = QFormLayout()
        self.inp_range = QLineEdit()
        self.inp_range.setReadOnly(True)
        form_top.addRow("Target Range (m):", self.inp_range)
        const_layout.addLayout(form_top)
        
        # Side-by-side EON and MWIR metrics
        cameras_layout = QHBoxLayout()
        
        eon_group = QGroupBox("EON Optical Metrics")
        eon_form = QFormLayout(eon_group)
        self.inp_eon_focal = QLineEdit()
        self.inp_eon_focal.setReadOnly(True)
        self.inp_eon_pitch = QLineEdit()
        self.inp_eon_pitch.setReadOnly(True)
        eon_form.addRow("Focal Length (mm):", self.inp_eon_focal)
        eon_form.addRow("Native Pitch (mm):", self.inp_eon_pitch)
        cameras_layout.addWidget(eon_group)
        
        mwir_group = QGroupBox("MWIR Optical Metrics")
        mwir_form = QFormLayout(mwir_group)
        self.inp_focal = QLineEdit()
        self.inp_focal.setReadOnly(True)
        self.inp_pitch = QLineEdit()
        self.inp_pitch.setReadOnly(True)
        mwir_form.addRow("Focal Length (mm):", self.inp_focal)
        mwir_form.addRow("Native Pitch (mm):", self.inp_pitch)
        cameras_layout.addWidget(mwir_group)

        const_layout.addLayout(cameras_layout)
        layout.addWidget(const_group)
        
        self.input_splitter = QSplitter(Qt.Horizontal)
        self.eon_label = ClickableLabel("EON")
        self.mwir_label = ClickableLabel("MWIR")
        self.input_splitter.addWidget(self.eon_label)
        self.input_splitter.addWidget(self.mwir_label)
        layout.addWidget(self.input_splitter, stretch=1)
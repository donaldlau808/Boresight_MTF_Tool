from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QGroupBox,
                               QLineEdit, QPushButton, QLabel, QListWidget, QTextEdit)

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(350)
        sidebar_layout = QVBoxLayout(self)
        
        self.chk_advanced = QCheckBox("Auto Batch Processing (Experimental)")
        self.chk_advanced.setStyleSheet("font-weight: bold;")
        sidebar_layout.addWidget(self.chk_advanced)

        self.dir_group = QGroupBox("Directories")
        dir_layout = QVBoxLayout(self.dir_group)
        
        self.batch_input_container = QWidget()
        batch_input_layout = QVBoxLayout(self.batch_input_container)
        batch_input_layout.setContentsMargins(0, 0, 0, 0)
        
        self.dir_input_base = QLineEdit()
        self.dir_input_base.setPlaceholderText("Input Data Directory")
        self.dir_input_base.setReadOnly(True)
        self.btn_browse_input = QPushButton("Browse Input...")
        
        batch_input_layout.addWidget(QLabel("Input Data (EON/MWIR):"))
        batch_input_layout.addWidget(self.dir_input_base)
        batch_input_layout.addWidget(self.btn_browse_input)
        
        self.dir_output_base = QLineEdit()
        self.dir_output_base.setPlaceholderText("Output Results Directory (Assigned on Run)")
        self.dir_output_base.setReadOnly(True)
        
        dir_layout.addWidget(self.batch_input_container)
        dir_layout.addWidget(QLabel("Output Directory:"))
        dir_layout.addWidget(self.dir_output_base)
        sidebar_layout.addWidget(self.dir_group)

        list_group = QGroupBox("System Number")
        list_layout = QVBoxLayout(list_group)
        self.folder_list = QListWidget()
        self.btn_remove_system = QPushButton("Remove System from Queue")
        self.btn_remove_system.setStyleSheet("font-weight: bold;")
        list_layout.addWidget(self.folder_list)
        list_layout.addWidget(self.btn_remove_system)
        sidebar_layout.addWidget(list_group)
        
        manual_group = QGroupBox("Manual Coordinate Selection")
        manual_layout = QVBoxLayout(manual_group)
        self.lbl_manual_status = QLabel("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")
        manual_layout.addWidget(self.lbl_manual_status)
        
        manual_btn_layout = QVBoxLayout()
        self.btn_run_manual = QPushButton("Run Manual Processing")
        self.btn_run_manual.setStyleSheet("font-weight: bold;")
        
        btn_clear_layout = QHBoxLayout()
        self.btn_clear_manual = QPushButton("Clear Current Points")
        self.btn_clear_all_manual = QPushButton("Clear All Points")
        btn_clear_layout.addWidget(self.btn_clear_manual)
        btn_clear_layout.addWidget(self.btn_clear_all_manual)
        
        manual_btn_layout.addWidget(self.btn_run_manual)
        manual_btn_layout.addLayout(btn_clear_layout)
        manual_layout.addLayout(manual_btn_layout)
        sidebar_layout.addWidget(manual_group)

        self.color_group = QGroupBox("Crosshair Colors")
        color_layout = QVBoxLayout(self.color_group)
        self.chk_orange = QCheckBox("Orange Crosshair")
        self.chk_green = QCheckBox("Green Crosshair")
        self.chk_white = QCheckBox("White Crosshair")
        color_layout.addWidget(self.chk_orange)
        color_layout.addWidget(self.chk_green)
        color_layout.addWidget(self.chk_white)
        sidebar_layout.addWidget(self.color_group)
        
        log_group = QGroupBox("Application Terminal")
        log_layout = QVBoxLayout(log_group)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("background-color: #FFFFFF; color: #000000; font-family: Consolas; border: 1px solid #C0C0C0;")
        log_layout.addWidget(self.log_viewer)
        sidebar_layout.addWidget(log_group)

        self.btn_run_batch = QPushButton("Run Batch Processing")
        self.btn_run_batch.setMinimumHeight(40)
        self.btn_run_batch.setStyleSheet("font-weight: bold;")

        self.btn_cancel = QPushButton("Cancel Processing")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setStyleSheet("font-weight: bold;")
        self.btn_cancel.setEnabled(False)
        
        self.btn_gen_report = QPushButton("Generate Excel Report")
        self.btn_gen_report.setMinimumHeight(40)

        sidebar_layout.addWidget(self.btn_run_batch)
        sidebar_layout.addWidget(self.btn_cancel)
        sidebar_layout.addWidget(self.btn_gen_report)
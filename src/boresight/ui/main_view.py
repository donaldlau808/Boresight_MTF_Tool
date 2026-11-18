from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QProgressBar, QStatusBar, QTabWidget
from PySide6.QtCore import Qt, Signal

from boresight.ui.components.input_tab import InputTab
from boresight.ui.components.output_tab import OutputTab
from boresight.ui.components.report_tab import ReportTab
from boresight.ui.components.sidebar import Sidebar

class MainView(QMainWindow):
    view_closing = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Boresight MTF Evaluation Tool")
        self.resize(1400, 950)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.tabs = QTabWidget()
        self.c_input_tab = InputTab()
        self.c_output_tab = OutputTab()
        self.c_report_tab = ReportTab()
        self.tabs.addTab(self.c_input_tab, "1. Pre-Processing Inputs")
        self.tabs.addTab(self.c_output_tab, "2. Post-Processing Diagnostics")
        self.tabs.addTab(self.c_report_tab, "3. Data Report Viewer")
        
        self.c_sidebar = Sidebar()
        
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.c_sidebar)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Aliases for rapid element access
        self.inp_range = self.c_input_tab.inp_range
        
        self.inp_eon_focal = self.c_input_tab.inp_eon_focal
        self.inp_eon_pitch = self.c_input_tab.inp_eon_pitch
        
        self.inp_focal = self.c_input_tab.inp_focal
        self.inp_pitch = self.c_input_tab.inp_pitch
        
        self.cmb_profile = self.c_input_tab.cmb_profile
        self.eon_label = self.c_input_tab.eon_label
        self.mwir_label = self.c_input_tab.mwir_label
        
        self.diag_side_by_side = self.c_output_tab.diag_side_by_side
        self.diag_eon_mask = self.c_output_tab.diag_eon_mask
        self.diag_mwir_mask = self.c_output_tab.diag_mwir_mask
        
        self.report_table = self.c_report_tab.report_table
        
        self.chk_advanced = self.c_sidebar.chk_advanced
        self.dir_input_base = self.c_sidebar.dir_input_base
        self.btn_browse_input = self.c_sidebar.btn_browse_input
        self.dir_output_base = self.c_sidebar.dir_output_base
        self.folder_list = self.c_sidebar.folder_list
        self.btn_remove_system = self.c_sidebar.btn_remove_system
        self.lbl_manual_status = self.c_sidebar.lbl_manual_status
        self.btn_run_manual = self.c_sidebar.btn_run_manual
        self.btn_clear_manual = self.c_sidebar.btn_clear_manual
        self.btn_clear_all_manual = self.c_sidebar.btn_clear_all_manual
        self.chk_orange = self.c_sidebar.chk_orange
        self.chk_green = self.c_sidebar.chk_green
        self.chk_white = self.c_sidebar.chk_white
        self.log_viewer = self.c_sidebar.log_viewer
        self.btn_run_batch = self.c_sidebar.btn_run_batch
        self.btn_cancel = self.c_sidebar.btn_cancel
        self.btn_gen_report = self.c_sidebar.btn_gen_report

    def closeEvent(self, event):
        self.view_closing.emit()
        super().closeEvent(event)
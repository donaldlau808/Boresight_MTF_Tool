import os
import glob
import shutil
import pandas as pd
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                               QPushButton, QLabel, QLineEdit, QFileDialog, 
                               QListWidget, QCheckBox, QGroupBox, QSplitter, 
                               QProgressBar, QStatusBar, QMessageBox, QApplication,
                               QTabWidget, QFormLayout, QTableWidget, 
                               QTableWidgetItem, QTextEdit, QComboBox, QInputDialog)
from PySide6.QtCore import Qt, QSettings

from core import boresight_eval
from core.logger import setup_logger
from ui.components.custom_labels import ClickableLabel, ResizableImageLabel
from ui.components.settings_dialog import SettingsDialog  # <--- NEW IMPORT
from ui.threads import BatchProcessThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Boresight MTF Evaluation Tool")
        self.resize(1400, 950)
        self.settings = QSettings("Shotover", "BoresightTool")
        
        self.logger, self.log_emitter = setup_logger()
        self.log_emitter.log_signal.connect(self.append_log)
        
        # State tracking for multi-system manual coords
        self.system_manual_coords = {} 
        self.process_thread = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # ==========================================
        # LEFT SIDE: Tabs
        # ==========================================
        self.tabs = QTabWidget()
        
        # TAB 1: Pre-Processing
        self.tab_input = QWidget()
        input_layout = QVBoxLayout(self.tab_input)
        
        const_group = QGroupBox("System Constants")
        const_layout = QVBoxLayout(const_group)
        
        profile_layout = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItems(["Shotover-NZ", "Shotover-Boulder", "User Defined"])
        self.cmb_profile.currentIndexChanged.connect(self.load_profile)
        
        self.btn_settings = QPushButton("⚙ Settings")
        self.btn_settings.setMaximumWidth(100)
        self.btn_settings.clicked.connect(self.open_settings)
        
        profile_layout.addWidget(QLabel("Load Profile:"))
        profile_layout.addWidget(self.cmb_profile, stretch=1)
        profile_layout.addWidget(self.btn_settings)
        const_layout.addLayout(profile_layout)
        
        form_layout = QHBoxLayout()
        form1 = QFormLayout()
        self.inp_range = QLineEdit()
        self.inp_focal = QLineEdit()
        form1.addRow("Target Range (m):", self.inp_range)
        form1.addRow("MWIR Focal Length (mm):", self.inp_focal)
        
        form2 = QFormLayout()
        self.inp_pitch = QLineEdit()
        self.inp_mwir_w = QLineEdit()
        self.inp_canvas_w = QLineEdit()
        form2.addRow("MWIR Native Pitch (mm):", self.inp_pitch)
        form2.addRow("MWIR Native Width (px):", self.inp_mwir_w)
        form2.addRow("Screenshot Canvas Width (px):", self.inp_canvas_w)
        
        form_layout.addLayout(form1)
        form_layout.addLayout(form2)
        const_layout.addLayout(form_layout)
        input_layout.addWidget(const_group)
        
        self.input_splitter = QSplitter(Qt.Horizontal)
        self.eon_label = ClickableLabel("EON")
        self.eon_label.coordinate_clicked.connect(self.register_click)
        self.eon_label.image_dropped.connect(self.handle_image_drop) 
        
        self.mwir_label = ClickableLabel("MWIR")
        self.mwir_label.coordinate_clicked.connect(self.register_click)
        self.mwir_label.image_dropped.connect(self.handle_image_drop) 

        self.input_splitter.addWidget(self.eon_label)
        self.input_splitter.addWidget(self.mwir_label)
        input_layout.addWidget(self.input_splitter, stretch=1)

        # TAB 2: Post-Processing Diagnostics
        self.tab_output = QWidget()
        output_layout = QVBoxLayout(self.tab_output)
        self.diag_tabs = QTabWidget()
        
        self.diag_side_by_side = ResizableImageLabel()
        self.diag_eon_mask = ResizableImageLabel()
        self.diag_mwir_mask = ResizableImageLabel()

        self.diag_tabs.addTab(self.diag_side_by_side, "Side-by-Side Alignment")
        self.diag_tabs.addTab(self.diag_eon_mask, "EON Zoomed Mask")
        self.diag_tabs.addTab(self.diag_mwir_mask, "MWIR Zoomed Mask")
        output_layout.addWidget(self.diag_tabs)
        
        # TAB 3: Excel Report Viewer
        self.tab_report = QWidget()
        report_layout = QVBoxLayout(self.tab_report)
        self.report_table = QTableWidget()
        self.report_table.setEditTriggers(QTableWidget.NoEditTriggers)
        report_layout.addWidget(QLabel("Extracted Intersection Data Export:"))
        report_layout.addWidget(self.report_table)

        self.tabs.addTab(self.tab_input, "1. Pre-Processing Inputs")
        self.tabs.addTab(self.tab_output, "2. Post-Processing Diagnostics")
        self.tabs.addTab(self.tab_report, "3. Data Report Viewer")

        # ==========================================
        # RIGHT SIDE: Sidebar
        # ==========================================
        sidebar = QWidget()
        sidebar.setFixedWidth(350)
        sidebar_layout = QVBoxLayout(sidebar)

        dir_group = QGroupBox("Directories")
        dir_layout = QVBoxLayout(dir_group)
        
        self.dir_input_base = QLineEdit()
        self.dir_input_base.setPlaceholderText("Input Data Directory")
        self.dir_input_base.setReadOnly(True)
        self.btn_browse_input = QPushButton("Browse Input...")
        self.btn_browse_input.clicked.connect(self.browse_input_directory)
        
        self.dir_output_base = QLineEdit()
        self.dir_output_base.setPlaceholderText("Output Results Directory")
        self.dir_output_base.setReadOnly(True)
        self.btn_browse_output = QPushButton("Browse Output...")
        self.btn_browse_output.clicked.connect(self.browse_output_directory)
        
        dir_layout.addWidget(QLabel("Input Data (EON/MWIR):"))
        dir_layout.addWidget(self.dir_input_base)
        dir_layout.addWidget(self.btn_browse_input)
        dir_layout.addWidget(QLabel("Output Results (Reports):"))
        dir_layout.addWidget(self.dir_output_base)
        dir_layout.addWidget(self.btn_browse_output)
        sidebar_layout.addWidget(dir_group)

        list_group = QGroupBox("System Number")
        list_layout = QVBoxLayout(list_group)
        self.folder_list = QListWidget()
        self.folder_list.itemSelectionChanged.connect(self.load_selected_folder)
        list_layout.addWidget(self.folder_list)
        
        self.btn_remove_system = QPushButton("Remove System from Queue")
        self.btn_remove_system.setStyleSheet("background-color: #8b0000; color: white;")
        self.btn_remove_system.clicked.connect(self.remove_selected_system)
        list_layout.addWidget(self.btn_remove_system)
        
        sidebar_layout.addWidget(list_group)
        
        manual_group = QGroupBox("Manual Coordinate Override")
        manual_layout = QVBoxLayout(manual_group)
        self.lbl_manual_status = QLabel("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")
        manual_layout.addWidget(self.lbl_manual_status)
        
        manual_btn_layout = QHBoxLayout()
        self.btn_run_manual = QPushButton("Process Manual Queue")
        self.btn_run_manual.setStyleSheet("background-color: #D77800; color: white; font-weight: bold;")
        self.btn_run_manual.clicked.connect(self.run_manual_processing)
        
        self.btn_clear_manual = QPushButton("Clear Current Points")
        self.btn_clear_manual.clicked.connect(self.clear_manual_coords)
        
        manual_btn_layout.addWidget(self.btn_run_manual)
        manual_btn_layout.addWidget(self.btn_clear_manual)
        manual_layout.addLayout(manual_btn_layout)
        sidebar_layout.addWidget(manual_group)

        color_group = QGroupBox("Crosshair Colors")
        color_layout = QVBoxLayout(color_group)
        self.chk_orange = QCheckBox("Orange Crosshair")
        self.chk_green = QCheckBox("Green Crosshair")
        self.chk_white = QCheckBox("White Crosshair")
        color_layout.addWidget(self.chk_orange)
        color_layout.addWidget(self.chk_green)
        color_layout.addWidget(self.chk_white)
        sidebar_layout.addWidget(color_group)
        
        log_group = QGroupBox("Application Terminal")
        log_layout = QVBoxLayout(log_group)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("background-color: #0c0c0c; color: #d4d4d4; font-family: Consolas;")
        log_layout.addWidget(self.log_viewer)
        sidebar_layout.addWidget(log_group)

        self.btn_run_batch = QPushButton("Run Batch Processing (Auto)")
        self.btn_run_batch.setMinimumHeight(40)
        self.btn_run_batch.setStyleSheet("background-color: #0078D7; color: white; font-weight: bold;")
        self.btn_run_batch.clicked.connect(self.run_batch_processing)

        self.btn_cancel = QPushButton("Cancel Processing")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.cancel_processing)
        
        self.btn_gen_report = QPushButton("Generate Excel Report")
        self.btn_gen_report.setMinimumHeight(40)
        self.btn_gen_report.clicked.connect(self.generate_excel_report)

        sidebar_layout.addWidget(self.btn_run_batch)
        sidebar_layout.addWidget(self.btn_cancel)
        sidebar_layout.addWidget(self.btn_gen_report)

        main_layout.addWidget(self.tabs)
        main_layout.addWidget(sidebar)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(300)
        self.progress_bar.setValue(0)
        self.status_bar.addPermanentWidget(self.progress_bar)

        self.load_profile()
        self.logger.info("Ready. Select Input/Output directories or drop images to begin.")

    def handle_image_drop(self, channel, file_path):
        input_dir = self.dir_input_base.text()
        output_dir = self.dir_output_base.text()
        
        if not input_dir or not os.path.exists(input_dir):
            input_dir = os.path.join(os.getcwd(), "Boresight_Workspace")
            os.makedirs(input_dir, exist_ok=True)
            self.dir_input_base.setText(input_dir)
            self.logger.info(f"Auto-created input directory at {input_dir}")
            
        if not output_dir:
            self.dir_output_base.setText(input_dir)
            
        system_num, ok = QInputDialog.getText(
            self, 
            "System Number Request", 
            f"Enter the System Number for this {channel} image:"
        )
        
        if not ok or not system_num.strip():
            self.logger.info("File drop cancelled by user.")
            return
            
        system_num = system_num.strip().zfill(3)
        dest_dir = os.path.join(input_dir, channel, system_num)
        os.makedirs(dest_dir, exist_ok=True)
        
        for old_file in glob.glob(os.path.join(dest_dir, "*.*")):
            try: os.remove(old_file)
            except Exception as e: self.logger.warning(f"Could not remove old file {old_file}: {e}")
                
        dest_path = os.path.join(dest_dir, os.path.basename(file_path))
        try:
            shutil.copy2(file_path, dest_path)
            self.logger.info(f"Routed {os.path.basename(file_path)} to -> {channel}/{system_num}")
        except Exception as e:
            self.logger.error(f"Failed to copy dropped file: {e}")
            return
            
        self.populate_folder_list(input_dir)
        items = self.folder_list.findItems(system_num, Qt.MatchExactly)
        if items:
            self.folder_list.setCurrentItem(items[0])

    def remove_selected_system(self):
        """Safely removes the system from the active UI queue without deleting the source files."""
        if not self.folder_list.currentItem():
            QMessageBox.warning(self, "No Selection", "Please select a System Number to remove.")
            return
            
        system_num = self.folder_list.currentItem().text()
        
        # Pop it out of the UI List Tool Cache
        row = self.folder_list.currentRow()
        self.folder_list.takeItem(row)
        
        # Remove it from manual tracking if it exists
        if system_num in self.system_manual_coords:
            del self.system_manual_coords[system_num]
            
        self.logger.info(f"Removed System {system_num} from current processing queue.")
        
        # Force clear the viewers
        self.eon_label.clear_image()
        self.mwir_label.clear_image()
        self.diag_side_by_side.clear_image()
        self.diag_eon_mask.clear_image()
        self.diag_mwir_mask.clear_image()
        self.lbl_manual_status.setText("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")

    def append_log(self, level, msg):
        color = "#d4d4d4"
        if level in ["WARNING", "ERROR", "CRITICAL"]:
            color = "#ff5555"
            msg = f"⚠ {msg}"
        self.log_viewer.append(f"<span style='color:{color};'>{msg}</span>")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.load_profile()

    def load_profile(self):
        profile = self.cmb_profile.currentText()
        if profile == "Shotover-NZ":
            self.inp_range.setText(str(self.settings.value("nz/range", 3880.75)))
            self.inp_focal.setText(str(self.settings.value("nz/focal", 420.0)))
            self.inp_pitch.setText(str(self.settings.value("nz/pitch", 0.010)))
            self.inp_mwir_w.setText(str(self.settings.value("nz/mwir_w", 1280.0)))
            self.inp_canvas_w.setText(str(self.settings.value("nz/canvas", 3840.0)))
        elif profile == "Shotover-Boulder":
            self.inp_range.setText(str(self.settings.value("boulder/range", 4500.0)))
            self.inp_focal.setText(str(self.settings.value("boulder/focal", 420.0)))
            self.inp_pitch.setText(str(self.settings.value("boulder/pitch", 0.010)))
            self.inp_mwir_w.setText(str(self.settings.value("boulder/mwir_w", 1280.0)))
            self.inp_canvas_w.setText(str(self.settings.value("boulder/canvas", 3840.0)))
        else:
            self.inp_range.clear()
            self.inp_focal.clear()
            self.inp_pitch.clear()
            self.inp_mwir_w.clear()
            self.inp_canvas_w.clear()

    def get_system_constants(self):
        try:
            return {
                'target_range': float(self.inp_range.text()),
                'focal_length': float(self.inp_focal.text()),
                'pixel_pitch': float(self.inp_pitch.text()),
                'native_width': float(self.inp_mwir_w.text()),
                'canvas_width': float(self.inp_canvas_w.text())
            }
        except ValueError:
            self.logger.error("Invalid Constants: Please ensure all System Constants are valid numbers.")
            return None

    def browse_input_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Data Directory")
        if folder:
            self.dir_input_base.setText(folder)
            if not self.dir_output_base.text():
                self.dir_output_base.setText(folder)
            self.populate_folder_list(folder)
            
    def browse_output_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Results Directory")
        if folder:
            self.dir_output_base.setText(folder)

    def populate_folder_list(self, input_dir):
        self.folder_list.clear()
        eon_dir = os.path.join(input_dir, "EON")
        mwir_dir = os.path.join(input_dir, "MWIR")
        
        subfolders = set()
        if os.path.exists(eon_dir):
            try: subfolders.update([f.name for f in os.scandir(eon_dir) if f.is_dir()])
            except PermissionError: pass
                
        if os.path.exists(mwir_dir):
            try: subfolders.update([f.name for f in os.scandir(mwir_dir) if f.is_dir()])
            except PermissionError: pass
                
        if not subfolders:
            self.logger.warning(f"No system folders found in {input_dir}")
            return
            
        sorted_folders = sorted(list(subfolders))
        for folder in sorted_folders:
            self.folder_list.addItem(folder)
            
        self.logger.info(f"Loaded {len(sorted_folders)} system numbers.")

    def load_selected_folder(self):
        if not self.folder_list.currentItem(): return
        system_num = self.folder_list.currentItem().text()
        input_dir = self.dir_input_base.text()
        output_dir = self.dir_output_base.text()
        
        self.eon_label.clear_markup()
        self.mwir_label.clear_markup()
        
        if system_num not in self.system_manual_coords:
            self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        coords = self.system_manual_coords[system_num]
        
        valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        eon_images = [img for img in glob.glob(os.path.join(input_dir, "EON", system_num, "*.*")) if img.lower().endswith(valid_exts)]
        mwir_images = [img for img in glob.glob(os.path.join(input_dir, "MWIR", system_num, "*.*")) if img.lower().endswith(valid_exts)]
        
        if eon_images: 
            self.eon_label.set_image(eon_images[0])
            if coords['eon_x'] is not None:
                self.eon_label.draw_markup(coords['eon_x'], coords['eon_y'])
        else: 
            self.eon_label.clear_image()
            
        if mwir_images: 
            self.mwir_label.set_image(mwir_images[0])
            if coords['mwir_x'] is not None:
                self.mwir_label.draw_markup(coords['mwir_x'], coords['mwir_y'])
        else: 
            self.mwir_label.clear_image()

        self.update_manual_status_label()

        if output_dir:
            res_dir = os.path.join(output_dir, "Boresight_Outputs")
            path_sbs = os.path.join(res_dir, f"{system_num}_side_by_side_zoomed.png")
            path_eon = os.path.join(res_dir, f"{system_num}_eon_mask_diagnostic_zoomed.png")
            path_mwir = os.path.join(res_dir, f"{system_num}_mwir_mask_diagnostic_zoomed.png")
            
            self.diag_side_by_side.set_image(path_sbs) if os.path.exists(path_sbs) else self.diag_side_by_side.clear_image()
            self.diag_eon_mask.set_image(path_eon) if os.path.exists(path_eon) else self.diag_eon_mask.clear_image()
            self.diag_mwir_mask.set_image(path_mwir) if os.path.exists(path_mwir) else self.diag_mwir_mask.clear_image()

    def clear_manual_coords(self):
        if not self.folder_list.currentItem(): return
        system_num = self.folder_list.currentItem().text()
        self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        self.eon_label.clear_markup()
        self.mwir_label.clear_markup()
        self.update_manual_status_label()

    def register_click(self, channel, x, y):
        if not self.folder_list.currentItem(): return
        system_num = self.folder_list.currentItem().text()
        
        if channel == "EON":
            self.system_manual_coords[system_num]['eon_x'] = x
            self.system_manual_coords[system_num]['eon_y'] = y
        elif channel == "MWIR":
            self.system_manual_coords[system_num]['mwir_x'] = x
            self.system_manual_coords[system_num]['mwir_y'] = y
            
        self.update_manual_status_label()
        self.logger.info(f"Registered System {system_num} {channel} manual coordinate: ({x}, {y})")

    def update_manual_status_label(self):
        if not self.folder_list.currentItem():
            self.lbl_manual_status.setText("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")
            return
            
        system_num = self.folder_list.currentItem().text()
        coords = self.system_manual_coords.get(system_num, {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None})
        
        e_txt = f"({coords['eon_x']}, {coords['eon_y']})" if coords['eon_x'] is not None else "Not Selected"
        m_txt = f"({coords['mwir_x']}, {coords['mwir_y']})" if coords['mwir_x'] is not None else "Not Selected"
        self.lbl_manual_status.setText(f"System {system_num}\nEON Target: {e_txt}\nMWIR Target: {m_txt}")

    def clear_output_directory(self):
        output_dir = self.dir_output_base.text()
        if not output_dir: return
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        if os.path.exists(res_dir):
            try:
                shutil.rmtree(res_dir)
                os.makedirs(res_dir)
                self.logger.info("Cleared stale files from Boresight_Outputs.")
            except Exception as e:
                self.logger.error(f"Failed to clear output directory: {e}")

    def run_manual_processing(self):
        """Processes only systems that have manual override coordinates defined."""
        if not self.dir_output_base.text():
            QMessageBox.warning(self, "Output Required", "Please specify an Output Directory first.")
            return

        systems_to_process = []
        for sys_idx in range(self.folder_list.count()):
            sys_num = self.folder_list.item(sys_idx).text()
            if sys_num in self.system_manual_coords:
                coords = self.system_manual_coords[sys_num]
                # Only add if ALL 4 coordinates are defined
                if all(v is not None for v in coords.values()):
                    systems_to_process.append(sys_num)
                    
        if not systems_to_process:
            QMessageBox.warning(self, "Missing Points", "No systems in the queue have fully defined manual coordinates.")
            return

        self.clear_output_directory()
        self._process_folders(systems_to_process, manual_override=True)

    def run_batch_processing(self):
        """Processes all systems blindly using the auto computer vision core."""
        if not self.dir_input_base.text() or not self.dir_output_base.text():
            QMessageBox.warning(self, "Directories Required", "Please specify both Input and Output directories.")
            return
            
        self.clear_output_directory()
        folders = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        self._process_folders(folders, manual_override=False)

    def cancel_processing(self):
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.requestInterruption()
            self.logger.warning("Cancel requested... stopping after current folder.")
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

    def _process_folders(self, folder_list, manual_override=False):
        input_dir = self.dir_input_base.text()
        output_dir = self.dir_output_base.text()
        if not input_dir or not output_dir or not folder_list: return

        self.btn_cancel.setEnabled(True)
        self.btn_run_batch.setEnabled(False)
        self.btn_run_manual.setEnabled(False)

        colors = {'orange': self.chk_orange.isChecked(), 'green': self.chk_green.isChecked(), 'white': self.chk_white.isChecked()}
        self.progress_bar.setMaximum(len(folder_list))
        self.progress_bar.setValue(0)
        
        self.process_thread = BatchProcessThread(
            folder_list, input_dir, output_dir, colors, 
            manual_coords_dict=self.system_manual_coords, 
            manual_override=manual_override
        )
        self.process_thread.progress_update.connect(self.update_progress)
        self.process_thread.finished_data.connect(self.on_batch_finished)
        self.process_thread.start()

    def update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.logger.info(msg)

    def on_batch_finished(self, intersection_data, folder_list):
        output_dir = self.dir_output_base.text()
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        os.makedirs(res_dir, exist_ok=True)

        if intersection_data:
            try:
                df_new = pd.DataFrame(intersection_data)
                df_new["Subfolder ID"] = df_new["Subfolder ID"].astype(str).str.zfill(3)
                
                excel_path = os.path.join(res_dir, "All_Boresight_Intersections.xlsx")
                if os.path.exists(excel_path) and len(folder_list) == 1:
                    df_old = pd.read_excel(excel_path)
                    df_old["Subfolder ID"] = df_old["Subfolder ID"].astype(str).str.zfill(3)
                    
                    target_folder = str(folder_list[0]).zfill(3)
                    df_old = df_old[df_old["Subfolder ID"] != target_folder] 
                    df_final = pd.concat([df_old, df_new]).sort_values("Subfolder ID")
                else:
                    df_final = df_new
                    
                df_final.to_excel(excel_path, index=False, sheet_name="Intersections")
                self.logger.info("Processing complete. Saved raw intersections.")
                
                self.load_dataframe_to_table(df_final)
                
                if len(folder_list) == 1:
                    self.load_selected_folder()
                    self.tabs.setCurrentIndex(1) 
            except PermissionError:
                self.logger.error("Permission Denied: Excel file is open. Close it and try again.")
            except Exception as e:
                self.logger.error(f"Failed to save Excel data: {e}")

        self.btn_cancel.setEnabled(False)
        self.btn_run_batch.setEnabled(True)
        self.btn_run_manual.setEnabled(True)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

    def generate_excel_report(self):
        output_dir = self.dir_output_base.text()
        if not output_dir:
            QMessageBox.warning(self, "Output Required", "Please specify an Output Directory first.")
            return
            
        sys_constants = self.get_system_constants()
        if not sys_constants: return
            
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        excel_input = os.path.join(res_dir, "All_Boresight_Intersections.xlsx")
        excel_output = os.path.join(res_dir, "CoBoresight_Misalignment_Report.xlsx")
        plot_dir = os.path.join(res_dir, "CoBoresight_Plots")
        
        self.logger.info("Generating formatted Excel Report...")
        
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        QApplication.processEvents()
        
        try:
            result = boresight_eval.generate_report(excel_input, excel_output, plot_dir, sys_constants)
            success = result[0]
            msg = result[1]
            
            if success:
                df_display = result[2]
                self.logger.info(f"Report Generated: {excel_output}")
                self.load_dataframe_to_table(df_display)
                self.tabs.setCurrentIndex(2)
            else:
                self.logger.error(f"Report Generation Failed: {msg}")
                
        except PermissionError:
            self.logger.error("Permission Denied: The CoBoresight Report is likely open in Excel. Please close it.")
        except Exception as e:
            self.logger.error(f"Unexpected error formatting report: {e}")
        finally:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)

    def load_dataframe_to_table(self, df):
        try:
            df.fillna("", inplace=True)
            self.report_table.setRowCount(df.shape[0])
            self.report_table.setColumnCount(df.shape[1])
            self.report_table.setHorizontalHeaderLabels(df.columns.astype(str))
            
            for row in range(df.shape[0]):
                for col in range(df.shape[1]):
                    item = QTableWidgetItem(str(df.iat[row, col]))
                    self.report_table.setItem(row, col, item)
                    
            self.report_table.resizeColumnsToContents()
        except Exception as e:
            self.logger.error(f"Failed to populate table viewer: {str(e)}")
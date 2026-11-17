import os
import re
import glob
import shutil
import tempfile
import pandas as pd
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                               QPushButton, QLabel, QLineEdit, QFileDialog, 
                               QListWidget, QCheckBox, QGroupBox, QSplitter, 
                               QProgressBar, QStatusBar, QMessageBox, QApplication,
                               QTabWidget, QFormLayout, QTableWidget, 
                               QTableWidgetItem, QTextEdit, QComboBox, QInputDialog)
from PySide6.QtCore import Qt, QSettings

from boresight.core import boresight_eval
from boresight.core.logger import setup_logger
from boresight.ui.components.custom_labels import ClickableLabel, ResizableImageLabel
from boresight.ui.components.settings_dialog import SettingsDialog
from boresight.ui.threads import BatchProcessThread, ReportGeneratorThread


class MainWindow(QMainWindow):
    VALID_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Boresight MTF Evaluation Tool")
        self.resize(1400, 950)
        self.settings = QSettings("Shotover", "BoresightTool")
        
        self.logger, self.log_emitter = setup_logger()
        self.log_emitter.log_signal.connect(self.append_log)
        
        self.system_manual_coords = {}
        self.system_image_paths = {}
        self.fresh_systems = set()
        self.drop_cache_dir = os.path.join(tempfile.gettempdir(), "Boresight_Drop_Cache")
        shutil.rmtree(self.drop_cache_dir, ignore_errors=True)
        self.process_thread = None
        self.report_thread = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.tabs = QTabWidget()
        self.tab_input = QWidget()
        input_layout = QVBoxLayout(self.tab_input)
        
        const_group = QGroupBox("System Constants")
        const_layout = QVBoxLayout(const_group)
        
        profile_layout = QHBoxLayout()
        self.cmb_profile = QComboBox()
        self.cmb_profile.addItems(["Shotover-NZ", "Shotover-Boulder", "User Defined"])
        self.cmb_profile.currentIndexChanged.connect(self.load_profile)
        
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setMaximumWidth(100)
        self.btn_settings.clicked.connect(self.open_settings)
        
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
        
        self.chk_advanced = QCheckBox("Auto Batch Processing (Experimental)")
        self.chk_advanced.setStyleSheet("font-weight: bold;")
        self.chk_advanced.stateChanged.connect(self.toggle_advanced_mode)
        sidebar_layout.addWidget(self.chk_advanced)

        dir_group = QGroupBox("Directories")
        dir_layout = QVBoxLayout(dir_group)
        self.dir_input_base = QLineEdit()
        self.dir_input_base.setPlaceholderText("Input Data Directory")
        self.dir_input_base.setReadOnly(True)
        self.btn_browse_input = QPushButton("Browse Input...")
        self.btn_browse_input.clicked.connect(self.browse_input_directory)
        
        self.dir_output_base = QLineEdit()
        self.dir_output_base.setPlaceholderText("Output Results Directory (Assigned on Run)")
        self.dir_output_base.setReadOnly(True)
        
        dir_layout.addWidget(QLabel("Input Data (EON/MWIR):"))
        dir_layout.addWidget(self.dir_input_base)
        dir_layout.addWidget(self.btn_browse_input)
        dir_layout.addWidget(QLabel("Output Directory:"))
        dir_layout.addWidget(self.dir_output_base)
        sidebar_layout.addWidget(dir_group)

        list_group = QGroupBox("System Number")
        list_layout = QVBoxLayout(list_group)
        self.folder_list = QListWidget()
        self.folder_list.itemSelectionChanged.connect(self.load_selected_folder)
        list_layout.addWidget(self.folder_list)
        self.btn_remove_system = QPushButton("Remove System from Queue")
        self.btn_remove_system.setStyleSheet("font-weight: bold;")
        self.btn_remove_system.clicked.connect(self.remove_selected_system)
        list_layout.addWidget(self.btn_remove_system)
        sidebar_layout.addWidget(list_group)
        
        manual_group = QGroupBox("Manual Coordinate Selection")
        manual_layout = QVBoxLayout(manual_group)
        self.lbl_manual_status = QLabel("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")
        manual_layout.addWidget(self.lbl_manual_status)
        
        manual_btn_layout = QVBoxLayout()
        self.btn_run_manual = QPushButton("Run Manual Processing")
        self.btn_run_manual.setStyleSheet("font-weight: bold;")
        self.btn_run_manual.clicked.connect(self.run_manual_processing)
        
        btn_clear_layout = QHBoxLayout()
        self.btn_clear_manual = QPushButton("Clear Current Points")
        self.btn_clear_manual.clicked.connect(self.clear_manual_coords)
        self.btn_clear_all_manual = QPushButton("Clear All Points")
        self.btn_clear_all_manual.clicked.connect(self.clear_all_manual_coords)
        btn_clear_layout.addWidget(self.btn_clear_manual)
        btn_clear_layout.addWidget(self.btn_clear_all_manual)
        
        manual_btn_layout.addWidget(self.btn_run_manual)
        manual_btn_layout.addLayout(btn_clear_layout)
        manual_layout.addLayout(manual_btn_layout)
        sidebar_layout.addWidget(manual_group)

        self.color_group = QGroupBox("Crosshair Colors")
        color_layout = QVBoxLayout(self.color_group)
        self.chk_orange = QCheckBox("Orange Crosshair")
        self.chk_orange.stateChanged.connect(self.invalidate_report)
        self.chk_green = QCheckBox("Green Crosshair")
        self.chk_green.stateChanged.connect(self.invalidate_report)
        self.chk_white = QCheckBox("White Crosshair")
        self.chk_white.stateChanged.connect(self.invalidate_report)
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
        self.btn_run_batch.clicked.connect(self.run_batch_processing)

        self.btn_cancel = QPushButton("Cancel Processing")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setStyleSheet("font-weight: bold;")
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
        self.toggle_advanced_mode()
        self.logger.info("Ready. Select Input directory or drop images to begin.")

    def invalidate_report(self, *args, **kwargs):
        """Greys out the Excel Report button if the queue or parameters change."""
        self.btn_gen_report.setEnabled(False)

    def toggle_advanced_mode(self):
        adv_active = self.chk_advanced.isChecked()
        self.color_group.setVisible(adv_active)
        self.btn_run_batch.setVisible(adv_active)
            
    def _get_roi_config(self):
        defaults = {
            'roi_x_min': 940, 'roi_x_max': 980, 'roi_y_min': 420, 'roi_y_max': 560,
            'search_y_min_eon': 460, 'search_y_max_eon': 510, 'search_y_min_mwir': 460, 'search_y_max_mwir': 510,
            'horizon_x_min': 800, 'horizon_x_max': 1120, 'horizon_y_min': 520, 'horizon_y_max': 570,
            'stroke_dilation': 7, 'line_dilation': 3, 'min_mast_prominence': 0.0, 'min_horizon_gradient': 0.0
        }
        cfg = {}
        for k, d in defaults.items():
            val = self.settings.value(f"roi/{k}", d)
            if 'prominence' in k or 'gradient' in k: cfg[k] = float(val)
            else: cfg[k] = int(float(val))
        return cfg

    # ==========================================
    # FILESYSTEM & VALIDATION HELPERS
    # ==========================================
    def _is_dir_writable(self, target_dir):
        try:
            os.makedirs(target_dir, exist_ok=True)
            probe = os.path.join(target_dir, f".write_probe_{os.getpid()}")
            with open(probe, "w") as f: f.write("ok")
            os.remove(probe)
            return True
        except Exception:
            return False

    def _sanitize_system_id(self, raw_text):
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", raw_text.strip())
        if not cleaned: return ""
        return cleaned.zfill(3) if cleaned.isdigit() else cleaned

    def _find_channel_dir(self, base_dir, channel_name):
        if not os.path.isdir(base_dir): return None
        try:
            for entry in os.scandir(base_dir):
                if entry.is_dir() and entry.name.upper() == channel_name.upper(): return entry.path
        except PermissionError: pass
        return None

    def _get_valid_images(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path): return []
        valid = []
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file() and entry.name.lower().endswith(self.VALID_EXTS):
                    try:
                        if entry.stat().st_size > 0: valid.append(entry.path)
                    except OSError: pass
        except PermissionError: pass
        return sorted(valid)

    def _check_excel_unlocked(self, res_dir):
        if not os.path.isdir(res_dir): return True
        for xlsx_path in glob.glob(os.path.join(res_dir, "*.xlsx")):
            if os.path.basename(xlsx_path).startswith("~$"):
                self.logger.error(f"Excel lock file detected: {os.path.basename(xlsx_path)}. Close Excel first.")
                return False
            try:
                with open(xlsx_path, "a"): pass
            except PermissionError:
                self.logger.error(f"File is locked in Excel: {os.path.basename(xlsx_path)}. Close it and try again.")
                return False
        return True

    def _clear_all_viewports(self):
        self.eon_label.clear_image(); self.mwir_label.clear_image(); self.diag_side_by_side.clear_image()
        self.diag_eon_mask.clear_image(); self.diag_mwir_mask.clear_image()
        self.lbl_manual_status.setText("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")

    # ==========================================
    # DRAG & DROP + QUEUE MANAGEMENT
    # ==========================================
    def handle_image_drop(self, channel, file_path):
        file_path = os.path.normpath(file_path)
        if not os.path.isfile(file_path):
            self.logger.error(f"Dropped file not found on disk: {file_path}")
            return
        try:
            if os.path.getsize(file_path) == 0:
                self.logger.error(f"Dropped file is empty (0 bytes): {os.path.basename(file_path)}")
                return
        except OSError: return
            
        raw_num, ok = QInputDialog.getText(self, "System Number Request", f"Enter the System Number for this {channel} image:")
        if not ok or not raw_num.strip(): return
            
        system_num = self._sanitize_system_id(raw_num)
        if not system_num: return

        dest_dir = os.path.join(self.drop_cache_dir, channel, system_num)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            for old_file in glob.glob(os.path.join(dest_dir, "*.*")):
                try: os.remove(old_file)
                except Exception: pass
            dest_path = os.path.join(dest_dir, os.path.basename(file_path))
            shutil.copy2(file_path, dest_path)
            self.logger.info(f"Loaded {os.path.basename(file_path)} into System {system_num} ({channel})")
        except Exception: return

        if system_num not in self.system_image_paths:
            self.system_image_paths[system_num] = {'EON': None, 'MWIR': None}
            self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
            self.fresh_systems.add(system_num)

        self.system_image_paths[system_num][channel] = dest_path
        if channel == "EON":
            self.system_manual_coords[system_num]['eon_x'] = None
            self.system_manual_coords[system_num]['eon_y'] = None
        elif channel == "MWIR":
            self.system_manual_coords[system_num]['mwir_x'] = None
            self.system_manual_coords[system_num]['mwir_y'] = None

        existing_items = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        if system_num not in existing_items:
            existing_items.append(system_num)
            self.folder_list.clear()
            for item_text in sorted(existing_items): self.folder_list.addItem(item_text)

        items = self.folder_list.findItems(system_num, Qt.MatchExactly)
        if items:
            if self.folder_list.currentItem() == items[0]: self.load_selected_folder()
            else: self.folder_list.setCurrentItem(items[0])
            
        self.invalidate_report()

    def remove_selected_system(self):
        if not self.folder_list.currentItem():
            QMessageBox.warning(self, "No Selection", "Please select a System Number to remove.")
            return
        system_num = self.folder_list.currentItem().text()
        row = self.folder_list.currentRow()
        self.folder_list.takeItem(row)
        self.system_manual_coords.pop(system_num, None)
        self.system_image_paths.pop(system_num, None)
        self.fresh_systems.discard(system_num)
        for ch in ("EON", "MWIR"): shutil.rmtree(os.path.join(self.drop_cache_dir, ch, system_num), ignore_errors=True)
        self.logger.info(f"Removed System {system_num} from current processing queue.")
        if self.folder_list.count() == 0: self._clear_all_viewports()
        self.invalidate_report()

    def append_log(self, level, msg):
        color = "#000000"
        if level in ["WARNING", "ERROR", "CRITICAL"]: color = "#D32F2F"; msg = f"⚠ {msg}"
        self.log_viewer.append(f"<span style='color:{color};'>{msg}</span>")
        self.log_viewer.verticalScrollBar().setValue(self.log_viewer.verticalScrollBar().maximum())

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec(): self.load_profile()

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
        elif profile == "User Defined":
            self.inp_range.setText(str(self.settings.value("user/range", 3880.75)))
            self.inp_focal.setText(str(self.settings.value("user/focal", 420.0)))
            self.inp_pitch.setText(str(self.settings.value("user/pitch", 0.010)))
            self.inp_mwir_w.setText(str(self.settings.value("user/mwir_w", 1280.0)))
            self.inp_canvas_w.setText(str(self.settings.value("user/canvas", 3840.0)))
        else:
            self.inp_range.clear(); self.inp_focal.clear(); self.inp_pitch.clear(); self.inp_mwir_w.clear(); self.inp_canvas_w.clear()

    def get_system_constants(self):
        try:
            return {
                'target_range': float(self.inp_range.text()), 'focal_length': float(self.inp_focal.text()),
                'pixel_pitch': float(self.inp_pitch.text()), 'native_width': float(self.inp_mwir_w.text()), 'canvas_width': float(self.inp_canvas_w.text())
            }
        except ValueError:
            self.logger.error("Invalid Constants: Please ensure all System Constants are valid numbers.")
            return None

    def browse_input_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Input Data Directory")
        if not folder: return
        folder = os.path.normpath(folder)
        if os.path.basename(folder).upper() in ("EON", "MWIR"):
            parent = os.path.dirname(folder)
            if self._find_channel_dir(parent, "EON") and self._find_channel_dir(parent, "MWIR"):
                self.logger.info(f"Detected '{os.path.basename(folder)}' subfolder; using parent directory: {parent}")
                folder = parent
        self.dir_input_base.setText(folder)
        self.populate_folder_list(folder)

    def browse_output_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Destination Output Directory")
        if not folder: return False
        folder = os.path.normpath(folder)
        if not self._is_dir_writable(folder):
            QMessageBox.critical(self, "Read-Only Directory", f"The selected output directory is not writable:\n{folder}\n\nPlease choose a folder where you have write permissions.")
            return False
        if os.path.basename(folder).upper() in ("EON", "MWIR"):
            QMessageBox.warning(self, "Invalid Output Directory", "Please select a parent folder rather than an EON or MWIR image folder.")
            return False
        self.dir_output_base.setText(folder)
        self.logger.info(f"Output directory set to: {folder}")
        return True

    def populate_folder_list(self, input_dir):
        self.folder_list.clear(); self.system_image_paths.clear(); self.system_manual_coords.clear(); self.fresh_systems.clear(); self._clear_all_viewports()
        eon_dir = self._find_channel_dir(input_dir, "EON")
        mwir_dir = self._find_channel_dir(input_dir, "MWIR")
        if not eon_dir or not mwir_dir:
            self.logger.warning(f"Expected both 'EON' and 'MWIR' folders inside {input_dir}")
            return
        subfolders = set()
        for ch_dir in (eon_dir, mwir_dir):
            try: subfolders.update([f.name for f in os.scandir(ch_dir) if f.is_dir()])
            except PermissionError: pass
        sorted_folders = sorted(list(subfolders))
        loaded_count = 0
        for folder in sorted_folders:
            eon_imgs = self._get_valid_images(os.path.join(eon_dir, folder))
            mwir_imgs = self._get_valid_images(os.path.join(mwir_dir, folder))
            if not eon_imgs or not mwir_imgs: continue
            self.system_image_paths[folder] = {'EON': eon_imgs[0], 'MWIR': mwir_imgs[0]}
            self.folder_list.addItem(folder)
            loaded_count += 1
        if loaded_count == 0:
            self.logger.warning(f"No complete EON/MWIR system pairs found in {input_dir}")
            return
        self.logger.info(f"Loaded {loaded_count} complete system pairs.")
        self.folder_list.setCurrentRow(0)
        self.invalidate_report()

    def load_selected_folder(self):
        if not self.folder_list.currentItem(): return
        system_num = self.folder_list.currentItem().text()
        output_dir = self.dir_output_base.text()
        self.eon_label.clear_markup(); self.mwir_label.clear_markup()
        if system_num not in self.system_manual_coords:
            self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        coords = self.system_manual_coords[system_num]
        paths = self.system_image_paths.get(system_num, {'EON': None, 'MWIR': None})
        eon_path, mwir_path = paths.get('EON'), paths.get('MWIR')
        
        if eon_path and os.path.isfile(eon_path):
            self.eon_label.set_image(eon_path)
            if coords['eon_x'] is not None: self.eon_label.draw_markup(coords['eon_x'], coords['eon_y'])
        else: self.eon_label.clear_image()
            
        if mwir_path and os.path.isfile(mwir_path):
            self.mwir_label.set_image(mwir_path)
            if coords['mwir_x'] is not None: self.mwir_label.draw_markup(coords['mwir_x'], coords['mwir_y'])
        else: self.mwir_label.clear_image()
        self.update_manual_status_label()

        if output_dir and system_num not in self.fresh_systems:
            res_dir = os.path.join(output_dir, "Boresight_Outputs")
            path_sbs = os.path.join(res_dir, f"{system_num}_side_by_side_zoomed.png")
            path_eon = os.path.join(res_dir, f"{system_num}_eon_mask_diagnostic_zoomed.png")
            path_mwir = os.path.join(res_dir, f"{system_num}_mwir_mask_diagnostic_zoomed.png")
            self.diag_side_by_side.set_image(path_sbs) if os.path.isfile(path_sbs) else self.diag_side_by_side.clear_image()
            self.diag_eon_mask.set_image(path_eon) if os.path.isfile(path_eon) else self.diag_eon_mask.clear_image()
            self.diag_mwir_mask.set_image(path_mwir) if os.path.isfile(path_mwir) else self.diag_mwir_mask.clear_image()
        else:
            self.diag_side_by_side.clear_image(); self.diag_eon_mask.clear_image(); self.diag_mwir_mask.clear_image()

    def clear_manual_coords(self):
        if not self.folder_list.currentItem(): return
        system_num = self.folder_list.currentItem().text()
        self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        self.eon_label.clear_markup(); self.mwir_label.clear_markup(); self.update_manual_status_label()
        self.invalidate_report()

    def clear_all_manual_coords(self):
        for sys_num in self.system_manual_coords:
            self.system_manual_coords[sys_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        self.eon_label.clear_markup()
        self.mwir_label.clear_markup()
        self.update_manual_status_label()
        self.logger.info("Cleared manual coordinates for all queued systems.")
        self.invalidate_report()

    def register_click(self, channel, x, y):
        if not self.folder_list.currentItem(): return
        system_num = self.folder_list.currentItem().text()
        if channel == "EON":
            self.system_manual_coords[system_num]['eon_x'] = x; self.system_manual_coords[system_num]['eon_y'] = y
        elif channel == "MWIR":
            self.system_manual_coords[system_num]['mwir_x'] = x; self.system_manual_coords[system_num]['mwir_y'] = y
        self.update_manual_status_label()
        self.logger.info(f"Registered System {system_num} {channel} manual coordinate: ({x}, {y})")
        self.invalidate_report()

    def update_manual_status_label(self):
        if not self.folder_list.currentItem():
            self.lbl_manual_status.setText("System --\nEON Target: Not Selected\nMWIR Target: Not Selected")
            return
        system_num = self.folder_list.currentItem().text()
        coords = self.system_manual_coords.get(system_num, {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None})
        e_txt = f"({coords['eon_x']}, {coords['eon_y']})" if coords['eon_x'] is not None else "Not Selected"
        m_txt = f"({coords['mwir_x']}, {coords['mwir_y']})" if coords['mwir_x'] is not None else "Not Selected"
        self.lbl_manual_status.setText(f"System {system_num}\nEON Target: {e_txt}\nMWIR Target: {m_txt}")

    def _validate_queue_pairs(self, folder_list):
        incomplete = []
        for sys_num in folder_list:
            paths = self.system_image_paths.get(sys_num, {})
            eon_ok = bool(paths.get('EON') and os.path.isfile(paths['EON']))
            mwir_ok = bool(paths.get('MWIR') and os.path.isfile(paths['MWIR']))
            if not eon_ok or not mwir_ok:
                missing = []
                if not eon_ok: missing.append("EON")
                if not mwir_ok: missing.append("MWIR")
                incomplete.append(f"System {sys_num} (missing {' & '.join(missing)})")
        return incomplete

    def clear_output_directory(self):
        output_dir = self.dir_output_base.text()
        if not output_dir: return False
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        if not self._check_excel_unlocked(res_dir):
            QMessageBox.warning(self, "Excel File Open", "An output Excel report is currently open in Excel.\nPlease close Excel before running processing.")
            return False
        if os.path.exists(res_dir):
            try:
                shutil.rmtree(res_dir)
                os.makedirs(res_dir, exist_ok=True)
                self.logger.info("Cleared stale files from Boresight_Outputs.")
            except Exception as e:
                self.logger.error(f"Failed to clear output directory: {e}")
                return False
        return True

    def run_manual_processing(self):
        systems_to_process, partial_systems = [], []
        for sys_idx in range(self.folder_list.count()):
            sys_num = self.folder_list.item(sys_idx).text()
            if sys_num in self.system_manual_coords:
                coords = self.system_manual_coords[sys_num]
                defined_count = sum(1 for v in coords.values() if v is not None)
                if defined_count == 4: systems_to_process.append(sys_num)
                elif defined_count > 0: partial_systems.append(sys_num)
                    
        if not systems_to_process:
            msg = "No systems in the queue have fully defined manual coordinates (both EON and MWIR)."
            if partial_systems: msg += f"\n\nIncomplete points on: {', '.join(partial_systems)}"
            QMessageBox.warning(self, "Missing Points", msg)
            return

        incomplete_pairs = self._validate_queue_pairs(systems_to_process)
        if incomplete_pairs: 
            QMessageBox.warning(self, "Incomplete Image Pairs", "Every system in the queue must have both EON and MWIR images:\n\n" + "\n".join(incomplete_pairs))
            return
        
        QMessageBox.information(self, "Output Required", "Please browse and select a destination folder for this run's outputs.")
        if not self.browse_output_directory(): return

        res_dir = os.path.join(self.dir_output_base.text(), "Boresight_Outputs")
        if not self._check_excel_unlocked(res_dir): return
        self._process_folders(systems_to_process, manual_override=True)

    def run_batch_processing(self):
        if self.folder_list.count() == 0: return
        if not (self.chk_orange.isChecked() or self.chk_green.isChecked() or self.chk_white.isChecked()):
            QMessageBox.warning(self, "Crosshair Color Required", "Please select at least one Crosshair Color (Orange, Green, or White) for automatic detection.")
            return
        
        folders = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        incomplete_pairs = self._validate_queue_pairs(folders)
        if incomplete_pairs:
            QMessageBox.warning(self, "Incomplete Image Pairs", "Every system in the queue must have both EON and MWIR images:\n\n" + "\n".join(incomplete_pairs))
            return
            
        QMessageBox.information(self, "Output Required", "Please browse and select a destination folder for this run's outputs.")
        if not self.browse_output_directory(): return

        if not self.clear_output_directory(): return
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
        if not output_dir or not folder_list: return

        self.btn_cancel.setEnabled(True)
        self.btn_run_batch.setEnabled(False)
        self.btn_run_manual.setEnabled(False)
        self._is_manual_run = manual_override

        colors = {'orange': self.chk_orange.isChecked(), 'green': self.chk_green.isChecked(), 'white': self.chk_white.isChecked()}
        self.progress_bar.setMaximum(len(folder_list))
        self.progress_bar.setValue(0)
        
        self.process_thread = BatchProcessThread(
            folder_list, input_dir, output_dir, colors, 
            manual_coords_dict=self.system_manual_coords, 
            manual_override=manual_override,
            system_paths_dict=self.system_image_paths,
            roi_config=self._get_roi_config()
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
        self.fresh_systems.difference_update(folder_list)

        if intersection_data:
            try:
                df_final = pd.DataFrame(intersection_data)
                df_final["Subfolder ID"] = df_final["Subfolder ID"].astype(str).str.zfill(3)
                df_final = df_final.sort_values("Subfolder ID")
                
                excel_path = os.path.join(res_dir, "All_Boresight_Intersections.xlsx")
                df_final.to_excel(excel_path, index=False, sheet_name="Intersections")
                self.logger.info("Processing complete. Saved raw intersections.")
                self.load_dataframe_to_table(df_final)
                self.load_selected_folder()
                self.btn_gen_report.setEnabled(True)
                if len(folder_list) == 1: self.tabs.setCurrentIndex(1) 
            except PermissionError:
                self.logger.error("Permission Denied: Excel file is open. Close it and try again.")
            except Exception as e:
                self.logger.error(f"Failed to save Excel data: {e}")

        self.btn_cancel.setEnabled(False)
        self.btn_run_batch.setEnabled(self.chk_advanced.isChecked())
        self.btn_run_manual.setEnabled(True)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

    def generate_excel_report(self):
        output_dir = self.dir_output_base.text()
        if not output_dir: return
        sys_constants = self.get_system_constants()
        if not sys_constants: return
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        excel_input = os.path.join(res_dir, "All_Boresight_Intersections.xlsx")
        excel_output = os.path.join(res_dir, "CoBoresight_Misalignment_Report.xlsx")
        plot_dir = os.path.join(res_dir, "CoBoresight_Plots")

        active_systems = [self.folder_list.item(i).text() for i in range(self.folder_list.count())]
        if not active_systems:
            QMessageBox.warning(self, "No Systems Loaded", "The system queue is empty. There is no relevant data to generate a report.")
            return

        if not os.path.isfile(excel_input):
            QMessageBox.warning(self, "No Processed Data", "No intersection data found yet.\nPlease run Batch Processing or Manual Queue Processing first.")
            return

        try:
            df_check = pd.read_excel(excel_input)
            df_check["Subfolder ID"] = df_check["Subfolder ID"].astype(str).str.zfill(3)
            df_filtered = df_check[df_check["Subfolder ID"].isin(active_systems)]
            if df_filtered.empty:
                QMessageBox.warning(self, "No Relevant Data", "None of the systems currently in the queue have processed intersection data available.\nPlease process these systems first.")
                return
        except Exception:
            pass 

        if not self._check_excel_unlocked(res_dir): return
        
        self.logger.info("Generating formatted Excel Report in background... please wait.")
        self.progress_bar.setMaximum(0)
        self.progress_bar.setValue(0)
        
        self.btn_gen_report.setEnabled(False)
        self.btn_run_batch.setEnabled(False)
        self.btn_run_manual.setEnabled(False)
        
        self.report_thread = ReportGeneratorThread(excel_input, excel_output, plot_dir, sys_constants, active_systems)
        self.report_thread.finished_report.connect(self.on_report_finished)
        self.report_thread.start()

    def on_report_finished(self, success, msg, df_display):
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.btn_gen_report.setEnabled(True)
        self.btn_run_batch.setEnabled(self.chk_advanced.isChecked())
        self.btn_run_manual.setEnabled(True)
        
        if success:
            self.logger.info(msg)
            self.load_dataframe_to_table(df_display)
            self.tabs.setCurrentIndex(2)
        else:
            self.logger.error(f"Report Generation Failed: {msg}")
            QMessageBox.warning(self, "Report Generation Failed", str(msg))

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

    def closeEvent(self, event):
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.requestInterruption()
            self.process_thread.wait(3000)
        if self.report_thread and self.report_thread.isRunning():
            self.report_thread.wait(3000)
        shutil.rmtree(self.drop_cache_dir, ignore_errors=True)
        super().closeEvent(event)
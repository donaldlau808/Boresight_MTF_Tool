import os
import re
import glob
import shutil
import tempfile
import json
from PySide6.QtWidgets import QMessageBox, QFileDialog, QInputDialog, QTableWidgetItem
from PySide6.QtCore import QSettings, Qt, QObject

from boresight.core.logger import setup_logger
from boresight.ui.threads import BatchProcessThread, ReportGeneratorThread
from boresight.ui.components.settings_dialog import SettingsDialog
from boresight.ui.components.system_number_dialog import SystemNumberDialog

class MainController(QObject):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.settings = QSettings("Shotover", "BoresightTool")
        self.logger, self.log_emitter = setup_logger()
        
        # --- Aliases required to keep legacy Pytests passing without rewrites ---
        self.dir_input_base = self.view.dir_input_base
        self.dir_output_base = self.view.dir_output_base
        self.eon_label = self.view.eon_label
        self.mwir_label = self.view.mwir_label
        self.folder_list = self.view.folder_list
        self.chk_orange = self.view.chk_orange

        # --- Internal State ---
        self.system_manual_coords = {}
        self.system_image_paths = {}
        self.system_optical_centers = {}  # ADDED
        self.fresh_systems = set()
        self.drop_cache_dir = os.path.join(tempfile.gettempdir(), "Boresight_Drop_Cache")
        shutil.rmtree(self.drop_cache_dir, ignore_errors=True)
        self.process_thread = None
        self.report_thread = None
        self.df_intersections = None

        self._connect_signals()
        self.load_profile()
        self.toggle_advanced_mode()
        self.logger.info("Ready. Select Input directory or drop images to begin.")

    def _connect_signals(self):
        self.log_emitter.log_signal.connect(self.append_log)
        self.view.cmb_profile.currentIndexChanged.connect(self.load_profile)
        self.view.c_input_tab.btn_settings.clicked.connect(self.open_settings)
        
        self.view.eon_label.coordinate_clicked.connect(self.register_click)
        self.view.eon_label.image_dropped.connect(self.handle_image_drop)
        self.view.mwir_label.coordinate_clicked.connect(self.register_click)
        self.view.mwir_label.image_dropped.connect(self.handle_image_drop)
        
        self.view.chk_advanced.stateChanged.connect(self.toggle_advanced_mode)
        self.view.btn_browse_input.clicked.connect(self.browse_input_directory)
        self.view.folder_list.itemSelectionChanged.connect(self.load_selected_folder)
        self.view.btn_remove_system.clicked.connect(self.remove_selected_system)
        
        self.view.btn_run_manual.clicked.connect(self.run_manual_processing)
        self.view.btn_clear_manual.clicked.connect(self.clear_manual_coords)
        self.view.btn_clear_all_manual.clicked.connect(self.clear_all_manual_coords)
        
        self.view.chk_orange.stateChanged.connect(self.invalidate_report)
        self.view.chk_green.stateChanged.connect(self.invalidate_report)
        self.view.chk_white.stateChanged.connect(self.invalidate_report)
        
        self.view.btn_run_batch.clicked.connect(self.run_batch_processing)
        self.view.btn_cancel.clicked.connect(self.cancel_processing)
        self.view.btn_gen_report.clicked.connect(self.generate_excel_report)
        
        self.view.view_closing.connect(self.cleanup)

    def invalidate_report(self, *args, **kwargs):
        self.view.btn_gen_report.setEnabled(False)

    def toggle_advanced_mode(self):
        adv_active = self.view.chk_advanced.isChecked()
        self.view.c_sidebar.color_group.setVisible(adv_active)
        self.view.c_sidebar.batch_input_container.setVisible(adv_active)
        self.view.btn_run_batch.setVisible(adv_active)
        
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
        valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        valid = []
        try:
            for entry in os.scandir(folder_path):
                if entry.is_file() and entry.name.lower().endswith(valid_exts):
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
        self.view.eon_label.clear_image()
        self.view.mwir_label.clear_image()
        self.view.diag_side_by_side.clear_image()
        self.view.diag_eon_mask.clear_image()
        self.view.diag_mwir_mask.clear_image()
        self.view.lbl_manual_status.setText(
            "System --\n"
            "EON Target: Not Selected\n"
            "Optical Center X: Not Uploaded, Optical Center Y: Not Uploaded\n"
            "MWIR Target: Not Selected\n"
            "Optical Center X: Not Uploaded, Optical Center Y: Not Uploaded"
        )

    def handle_image_drop(self, channel, file_path):
        file_path = os.path.normpath(file_path)
        if not os.path.isfile(file_path):
            self.logger.error(f"Dropped file not found on disk: {file_path}")
            return
        try:
            if os.path.getsize(file_path) == 0:
                self.logger.error(f"Dropped file is empty: {os.path.basename(file_path)}")
                return
        except OSError: return
            
        self.view.activateWindow()
        self.view.raise_()
        
        dialog = SystemNumberDialog(channel, self.view)
        if not dialog.exec(): return
            
        raw_num, raw_comment = dialog.get_values()
        if not raw_num: return
            
        system_num = self._sanitize_system_id(raw_num)
        if not system_num: return
            
        if raw_comment:
            clean_comment = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', "_", raw_comment).strip('_')
            if clean_comment: system_num = f"{system_num}_{clean_comment}"

        # Ensure system entries exist
        if system_num not in self.system_image_paths:
            self.system_image_paths[system_num] = {'EON': None, 'MWIR': None}
            self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
            self.system_optical_centers[system_num] = {'EON': None, 'MWIR': None}
            self.fresh_systems.add(system_num)

        # Handle JS Calibration Drop
        if file_path.lower().endswith('.js'):
            try:
                with open(file_path, 'r') as f:
                    cal_data = json.load(f)
                    
                    # Recursive helper to search the JSON tree for a specific key
                    def find_key(obj, target_key):
                        if isinstance(obj, dict):
                            if target_key in obj:
                                return obj[target_key]
                            for val in obj.values():
                                res = find_key(val, target_key)
                                if res is not None:
                                    return res
                        elif isinstance(obj, list):
                            for item in obj:
                                res = find_key(item, target_key)
                                if res is not None:
                                    return res
                        return None

                    raw_cx = find_key(cal_data, 'center_x')
                    raw_cy = find_key(cal_data, 'center_y')
                    
                    # CHANGED: Explicitly check for missing data and alert the user
                    if raw_cx is None or raw_cy is None:
                        self.logger.warning(f"Optical center data not found in {os.path.basename(file_path)}.")
                        QMessageBox.warning(
                            self.view, 
                            "Missing Data", 
                            f"Could not find 'center_x' and/or 'center_y' variables in the uploaded file:\n{os.path.basename(file_path)}"
                        )
                        return
                    
                    cx = float(raw_cx)
                    cy = float(raw_cy)
                    
                    self.system_optical_centers[system_num][channel] = (cx, cy)
                
                self.logger.info(f"Loaded Optical Centers ({cx}, {cy}) for System {system_num} ({channel})")
                self.update_manual_status_label()
                self.invalidate_report()
            except Exception as e:
                self.logger.error(f"Failed to parse calibration file: {e}")
                QMessageBox.warning(self.view, "Parse Error", f"Invalid JS file:\n{e}")
            return

        # Handle Standard Image Drop
        dest_dir = os.path.join(self.drop_cache_dir, channel, system_num)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            for old_file in glob.glob(os.path.join(dest_dir, "*.*")):
                try: os.remove(old_file)
                except Exception: pass
            dest_path = os.path.join(dest_dir, os.path.basename(file_path))
            shutil.copy2(file_path, dest_path)
            self.logger.info(f"Loaded {os.path.basename(file_path)} into System {system_num} ({channel})")
        except Exception as e:
            self.logger.error(f"Failed to load dropped image: {e}")
            QMessageBox.warning(self.view, "Load Error", f"Could not copy image:\n{e}")
            return

        self.system_image_paths[system_num][channel] = dest_path
        if channel == "EON":
            self.system_manual_coords[system_num]['eon_x'] = None
            self.system_manual_coords[system_num]['eon_y'] = None
        elif channel == "MWIR":
            self.system_manual_coords[system_num]['mwir_x'] = None
            self.system_manual_coords[system_num]['mwir_y'] = None

        existing_items = [self.view.folder_list.item(i).text() for i in range(self.view.folder_list.count())]
        if system_num not in existing_items:
            existing_items.append(system_num)
            self.view.folder_list.clear()
            for item_text in sorted(existing_items): self.view.folder_list.addItem(item_text)

        items = self.view.folder_list.findItems(system_num, Qt.MatchExactly)
        if items:
            if self.view.folder_list.currentItem() == items[0]: self.load_selected_folder()
            else: self.view.folder_list.setCurrentItem(items[0])
            
        self.invalidate_report()

    def remove_selected_system(self):
        if not self.view.folder_list.currentItem():
            QMessageBox.warning(self.view, "No Selection", "Please select a System Number to remove.")
            return
        system_num = self.view.folder_list.currentItem().text()
        row = self.view.folder_list.currentRow()
        self.view.folder_list.takeItem(row)
        self.system_manual_coords.pop(system_num, None)
        self.system_image_paths.pop(system_num, None)
        self.system_optical_centers.pop(system_num, None) # ADDED
        self.fresh_systems.discard(system_num)
        for ch in ("EON", "MWIR"): shutil.rmtree(os.path.join(self.drop_cache_dir, ch, system_num), ignore_errors=True)
        self.logger.info(f"Removed System {system_num} from current processing queue.")
        if self.view.folder_list.count() == 0: self._clear_all_viewports()
        self.invalidate_report()

    def append_log(self, level, msg):
        color = "#000000"
        if level in ["WARNING", "ERROR", "CRITICAL"]: color = "#D32F2F"; msg = f"⚠ {msg}"
        self.view.log_viewer.append(f"<span style='color:{color};'>{msg}</span>")
        self.view.log_viewer.verticalScrollBar().setValue(self.view.log_viewer.verticalScrollBar().maximum())

    def open_settings(self):
        dialog = SettingsDialog(self.view)
        if dialog.exec(): self.load_profile()

    def load_profile(self):
        profile = self.view.cmb_profile.currentText()
        prefix = "nz" if profile == "Shotover-NZ" else "boulder" if profile == "Shotover-Boulder" else "user"
        default_range = 4500.0 if prefix == "boulder" else 3880.75
        
        self.view.inp_range.setText(str(self.settings.value(f"{prefix}/range", default_range)))
        
        self.view.inp_eon_focal.setText(str(self.settings.value(f"{prefix}/eon_focal", 504.0)))
        self.view.inp_eon_pitch.setText(str(self.settings.value(f"{prefix}/eon_pitch", 0.00274)))
        
        self.view.inp_focal.setText(str(self.settings.value(f"{prefix}/focal", 420.0)))
        self.view.inp_pitch.setText(str(self.settings.value(f"{prefix}/pitch", 0.010)))

    def get_system_constants(self):
        try:
            return {
                'target_range': float(self.view.inp_range.text()), 
                
                'eon_focal_length': float(self.view.inp_eon_focal.text()),
                'eon_pixel_pitch': float(self.view.inp_eon_pitch.text()),
                
                'focal_length': float(self.view.inp_focal.text()),
                'pixel_pitch': float(self.view.inp_pitch.text()), 
                
                'eon_img_w': float(self.settings.value("dims/eon_w", 3840.0)),
                'eon_img_h': float(self.settings.value("dims/eon_h", 2160.0)),
                'mwir_img_w': float(self.settings.value("dims/mwir_w", 1280.0)),
                'mwir_img_h': float(self.settings.value("dims/mwir_h", 720.0))
            }
        except ValueError:
            self.logger.error("Invalid Constants: Please ensure all System Constants are valid numbers.")
            QMessageBox.warning(self.view, "Invalid Input", "System Constants must be valid numbers.")
            return None

    def browse_input_directory(self):
        folder = QFileDialog.getExistingDirectory(self.view, "Select Input Data Directory")
        if not folder: return
        folder = os.path.normpath(folder)
        if os.path.basename(folder).upper() in ("EON", "MWIR"):
            parent = os.path.dirname(folder)
            if self._find_channel_dir(parent, "EON") and self._find_channel_dir(parent, "MWIR"):
                self.logger.info(f"Detected '{os.path.basename(folder)}' subfolder; using parent directory: {parent}")
                folder = parent
        self.view.dir_input_base.setText(folder)
        self.populate_folder_list(folder)

    def browse_output_directory(self):
        folder = QFileDialog.getExistingDirectory(self.view, "Select Destination Output Directory")
        if not folder: return False
        folder = os.path.normpath(folder)
        if not self._is_dir_writable(folder):
            QMessageBox.critical(self.view, "Read-Only Directory", f"The selected output directory is not writable:\n{folder}\n\nPlease choose a folder where you have write permissions.")
            return False
        if os.path.basename(folder).upper() in ("EON", "MWIR"):
            QMessageBox.warning(self.view, "Invalid Output Directory", "Please select a parent folder rather than an EON or MWIR image folder.")
            return False
            
        res_dir = os.path.join(folder, "Boresight_Outputs")
        if os.path.exists(res_dir):
            try:
                if any(os.scandir(res_dir)):
                    QMessageBox.warning(self.view, "Directory Already Used", 
                        "This folder already contains processed Boresight outputs.\n\n"
                        "To prevent overwriting data from previous or current sessions, "
                        "please select an empty or completely new folder.")
                    return False
            except PermissionError:
                pass

        self.view.dir_output_base.setText(folder)
        self.logger.info(f"Output directory set to: {folder}")
        return True

    def validate_output_is_empty(self):
        output_dir = self.view.dir_output_base.text()
        if not output_dir: return False
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        
        if os.path.exists(res_dir):
            try:
                if any(os.scandir(res_dir)):
                    QMessageBox.warning(self.view, "Directory Already Used", 
                        "The current output directory already contains processed data.\n\n"
                        "To prevent overwriting, please click 'Browse Input...' and select a new, empty folder.")
                    return False
            except PermissionError:
                pass
                
        os.makedirs(res_dir, exist_ok=True)
        return True

    def populate_folder_list(self, input_dir):
        self.view.folder_list.clear()
        self.system_image_paths.clear()
        self.system_manual_coords.clear()
        self.system_optical_centers.clear() # ADDED
        self.fresh_systems.clear()
        self._clear_all_viewports()
        self.df_intersections = None
        
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
            self.view.folder_list.addItem(folder)
            loaded_count += 1
        if loaded_count == 0:
            self.logger.warning(f"No complete EON/MWIR system pairs found in {input_dir}")
            return
        self.logger.info(f"Loaded {loaded_count} complete system pairs.")
        self.view.folder_list.setCurrentRow(0)
        self.invalidate_report()

    def load_selected_folder(self):
        if not self.view.folder_list.currentItem(): return
        system_num = self.view.folder_list.currentItem().text()
        output_dir = self.view.dir_output_base.text()
        self.view.eon_label.clear_markup()
        self.view.mwir_label.clear_markup()
        if system_num not in self.system_manual_coords:
            self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        coords = self.system_manual_coords[system_num]
        paths = self.system_image_paths.get(system_num, {'EON': None, 'MWIR': None})
        eon_path, mwir_path = paths.get('EON'), paths.get('MWIR')
        
        if eon_path and os.path.isfile(eon_path):
            self.view.eon_label.set_image(eon_path)
            if coords['eon_x'] is not None: self.view.eon_label.draw_markup(coords['eon_x'], coords['eon_y'])
        else: self.view.eon_label.clear_image()
            
        if mwir_path and os.path.isfile(mwir_path):
            self.view.mwir_label.set_image(mwir_path)
            if coords['mwir_x'] is not None: self.view.mwir_label.draw_markup(coords['mwir_x'], coords['mwir_y'])
        else: self.view.mwir_label.clear_image()
        self.update_manual_status_label()

        if output_dir and system_num not in self.fresh_systems:
            res_dir = os.path.join(output_dir, "Boresight_Outputs")
            path_sbs = os.path.join(res_dir, f"{system_num}_side_by_side_zoomed.png")
            path_eon = os.path.join(res_dir, f"{system_num}_eon_mask_diagnostic_zoomed.png")
            path_mwir = os.path.join(res_dir, f"{system_num}_mwir_mask_diagnostic_zoomed.png")
            self.view.diag_side_by_side.set_image(path_sbs) if os.path.isfile(path_sbs) else self.view.diag_side_by_side.clear_image()
            self.view.diag_eon_mask.set_image(path_eon) if os.path.isfile(path_eon) else self.view.diag_eon_mask.clear_image()
            self.view.diag_mwir_mask.set_image(path_mwir) if os.path.isfile(path_mwir) else self.view.diag_mwir_mask.clear_image()
        else:
            self.view.diag_side_by_side.clear_image()
            self.view.diag_eon_mask.clear_image()
            self.view.diag_mwir_mask.clear_image()

    def clear_manual_coords(self):
        if not self.view.folder_list.currentItem(): return
        system_num = self.view.folder_list.currentItem().text()
        self.system_manual_coords[system_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
        self.view.eon_label.clear_markup()
        self.view.mwir_label.clear_markup()
        self.update_manual_status_label()
        self.invalidate_report()

    def clear_all_manual_coords(self):
        for sys_num in self.system_manual_coords:
            self.system_manual_coords[sys_num] = {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None}
            self.system_optical_centers[sys_num] = {'EON': None, 'MWIR': None} 
        self.view.eon_label.clear_markup()
        self.view.mwir_label.clear_markup()
        self.update_manual_status_label()
        self.logger.info("Cleared manual coordinates for all queued systems.")
        self.invalidate_report()

    def register_click(self, channel, x, y):
        if not self.view.folder_list.currentItem(): return
        system_num = self.view.folder_list.currentItem().text()
        if channel == "EON":
            self.system_manual_coords[system_num]['eon_x'] = x
            self.system_manual_coords[system_num]['eon_y'] = y
        elif channel == "MWIR":
            self.system_manual_coords[system_num]['mwir_x'] = x
            self.system_manual_coords[system_num]['mwir_y'] = y
        self.update_manual_status_label()
        self.logger.info(f"Registered System {system_num} {channel} manual coordinate: ({x}, {y})")
        self.invalidate_report()

    def update_manual_status_label(self):
        if not self.view.folder_list.currentItem():
            self.view.lbl_manual_status.setText(
                "System --\n"
                "EON Target: Not Selected\n"
                "Optical Center X: Not Uploaded, Optical Center Y: Not Uploaded\n"
                "MWIR Target: Not Selected\n"
                "Optical Center X: Not Uploaded, Optical Center Y: Not Uploaded"
            )
            return
        
        system_num = self.view.folder_list.currentItem().text()
        coords = self.system_manual_coords.get(system_num, {'eon_x': None, 'eon_y': None, 'mwir_x': None, 'mwir_y': None})
        opts = self.system_optical_centers.get(system_num, {'EON': None, 'MWIR': None})
        
        e_txt = f"({coords['eon_x']}, {coords['eon_y']})" if coords['eon_x'] is not None else "Not Selected"
        m_txt = f"({coords['mwir_x']}, {coords['mwir_y']})" if coords['mwir_x'] is not None else "Not Selected"
        
        e_opt_str = f"Optical Center X: {opts['EON'][0]:.4f}, Optical Center Y: {opts['EON'][1]:.4f}" if opts['EON'] is not None else "Optical Center X: Not Uploaded, Optical Center Y: Not Uploaded"
        m_opt_str = f"Optical Center X: {opts['MWIR'][0]:.4f}, Optical Center Y: {opts['MWIR'][1]:.4f}" if opts['MWIR'] is not None else "Optical Center X: Not Uploaded, Optical Center Y: Not Uploaded"
        
        self.view.lbl_manual_status.setText(f"System {system_num}\nEON Target: {e_txt}\n{e_opt_str}\nMWIR Target: {m_txt}\n{m_opt_str}")

    def _validate_queue_pairs(self, folder_list):
        incomplete = []
        for sys_num in folder_list:
            paths = self.system_image_paths.get(sys_num, {})
            opts = self.system_optical_centers.get(sys_num, {})
            
            eon_ok = bool(paths.get('EON') and os.path.isfile(paths['EON']))
            mwir_ok = bool(paths.get('MWIR') and os.path.isfile(paths['MWIR']))
            eon_opt_ok = opts.get('EON') is not None
            mwir_opt_ok = opts.get('MWIR') is not None
            
            if not eon_ok or not mwir_ok or not eon_opt_ok or not mwir_opt_ok:
                missing = []
                if not eon_ok: missing.append("EON Image")
                if not mwir_ok: missing.append("MWIR Image")
                if not eon_opt_ok: missing.append("EON .js Cal")
                if not mwir_opt_ok: missing.append("MWIR .js Cal")
                incomplete.append(f"System {sys_num} (missing {' & '.join(missing)})")
        return incomplete

    def run_manual_processing(self):
        systems_to_process, partial_systems = [], []
        for sys_idx in range(self.view.folder_list.count()):
            sys_num = self.view.folder_list.item(sys_idx).text()
            if sys_num in self.system_manual_coords:
                coords = self.system_manual_coords[sys_num]
                defined_count = sum(1 for v in coords.values() if v is not None)
                if defined_count == 4: systems_to_process.append(sys_num)
                elif defined_count > 0: partial_systems.append(sys_num)
                    
        if not systems_to_process:
            msg = "No systems in the queue have fully defined manual coordinates (both EON and MWIR)."
            if partial_systems: msg += f"\n\nIncomplete points on: {', '.join(partial_systems)}"
            QMessageBox.warning(self.view, "Missing Points", msg)
            return

        incomplete_pairs = self._validate_queue_pairs(systems_to_process)
        if incomplete_pairs: 
            QMessageBox.warning(self.view, "Incomplete Image Pairs", "Every system in the queue must have both EON and MWIR images:\n\n" + "\n".join(incomplete_pairs))
            return
        
        QMessageBox.information(self.view, "Output Required", "Please browse and select a destination folder for this run's outputs.")
        if not self.browse_output_directory(): return
        if not self.validate_output_is_empty(): return
        
        self._process_folders(systems_to_process, manual_override=True)

    def run_batch_processing(self):
        if self.view.folder_list.count() == 0: return
        if not (self.view.chk_orange.isChecked() or self.view.chk_green.isChecked() or self.view.chk_white.isChecked()):
            QMessageBox.warning(self.view, "Crosshair Color Required", "Please select at least one Crosshair Color (Orange, Green, or White) for automatic detection.")
            return
        
        folders = [self.view.folder_list.item(i).text() for i in range(self.view.folder_list.count())]
        incomplete_pairs = self._validate_queue_pairs(folders)
        if incomplete_pairs:
            QMessageBox.warning(self.view, "Incomplete Image Pairs", "Every system in the queue must have both EON and MWIR images:\n\n" + "\n".join(incomplete_pairs))
            return
            
        QMessageBox.information(self.view, "Output Required", "Please browse and select a destination folder for this run's outputs.")
        if not self.browse_output_directory(): return
        if not self.validate_output_is_empty(): return
        
        self._process_folders(folders, manual_override=False)

    def cancel_processing(self):
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.requestInterruption()
            self.logger.warning("Cancel requested... stopping after current folder.")
        self.view.progress_bar.setMaximum(100)
        self.view.progress_bar.setValue(0)
        self.view.progress_bar.setFormat("Cancelled")

    def _process_folders(self, folder_list, manual_override=False):
        input_dir = self.view.dir_input_base.text()
        output_dir = self.view.dir_output_base.text()
        if not output_dir or not folder_list: return

        self.view.btn_cancel.setEnabled(True)
        self.view.btn_run_batch.setEnabled(False)
        self.view.btn_run_manual.setEnabled(False)

        colors = {'orange': self.view.chk_orange.isChecked(), 'green': self.view.chk_green.isChecked(), 'white': self.view.chk_white.isChecked()}
        
        self.view.progress_bar.setFormat("%p%")
        self.view.progress_bar.setMaximum(len(folder_list))
        self.view.progress_bar.setValue(0)
        
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
        self.view.progress_bar.setValue(val)
        self.logger.info(msg)

    def on_batch_finished(self, intersection_data, folder_list):
        output_dir = self.view.dir_output_base.text()
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        os.makedirs(res_dir, exist_ok=True)
        self.fresh_systems.difference_update(folder_list)

        if intersection_data:
            try:
                for row in intersection_data:
                    sys_id = row.get("Subfolder ID", "")
                    opts = self.system_optical_centers.get(sys_id, {'EON': None, 'MWIR': None})
                    row["EON Opt Center X"] = opts['EON'][0]
                    row["EON Opt Center Y"] = opts['EON'][1]
                    row["MWIR Opt Center X"] = opts['MWIR'][0]
                    row["MWIR Opt Center Y"] = opts['MWIR'][1]

                from boresight.core import data_handler
                self.df_intersections = data_handler.process_batch_results(intersection_data)
                
                self.logger.info("Processing complete. Extracted intersections kept in memory.")
                self.load_dataframe_to_table(self.df_intersections)
                self.load_selected_folder()
                self.view.btn_gen_report.setEnabled(True)
                if len(folder_list) == 1: self.view.tabs.setCurrentIndex(1) 
            except Exception as e:
                self.logger.error(f"Failed to process internal data: {e}")

        self.view.btn_cancel.setEnabled(False)
        self.view.btn_run_batch.setEnabled(self.view.chk_advanced.isChecked())
        self.view.btn_run_manual.setEnabled(True)
        
        self.view.progress_bar.setMaximum(100)
        self.view.progress_bar.setValue(100)
        self.view.progress_bar.setFormat("Done")

    def generate_excel_report(self):
        output_dir = self.view.dir_output_base.text()
        if not output_dir: return
        sys_constants = self.get_system_constants()
        if not sys_constants: return
        res_dir = os.path.join(output_dir, "Boresight_Outputs")
        excel_output = os.path.join(res_dir, "CoBoresight_Misalignment_Report.xlsx")

        active_systems = [self.view.folder_list.item(i).text() for i in range(self.view.folder_list.count())]
        if not active_systems:
            QMessageBox.warning(self.view, "No Systems Loaded", "The system queue is empty. There is no relevant data to generate a report.")
            return

        if self.df_intersections is None:
            QMessageBox.warning(self.view, "No Processed Data", "No intersection data found yet.\nPlease run Batch Processing or Manual Queue Processing first.")
            return

        try:
            from boresight.core import data_handler
            if not data_handler.has_active_data(self.df_intersections, active_systems):
                QMessageBox.warning(self.view, "No Relevant Data", "None of the systems currently in the queue have processed intersection data available.\nPlease process these systems first.")
                return
        except Exception:
            pass 

        if not self._check_excel_unlocked(res_dir): return
        
        self.logger.info("Generating formatted Excel Report in background... please wait.")
        
        self.view.progress_bar.setFormat("Generating...")
        self.view.progress_bar.setMaximum(0)
        self.view.progress_bar.setValue(0)
        
        self.view.btn_gen_report.setEnabled(False)
        self.view.btn_run_batch.setEnabled(False)
        self.view.btn_run_manual.setEnabled(False)
        
        self.report_thread = ReportGeneratorThread(self.df_intersections, excel_output, sys_constants, active_systems)
        self.report_thread.finished_report.connect(self.on_report_finished)
        self.report_thread.start()

    def on_report_finished(self, success, msg, df_display):
        self.view.btn_gen_report.setEnabled(True)
        self.view.btn_run_batch.setEnabled(self.view.chk_advanced.isChecked())
        self.view.btn_run_manual.setEnabled(True)
        
        if success:
            self.view.progress_bar.setMaximum(100)
            self.view.progress_bar.setValue(100)
            self.view.progress_bar.setFormat("Done")
            self.logger.info(msg)
            self.load_dataframe_to_table(df_display)
            self.view.tabs.setCurrentIndex(2)
        else:
            self.view.progress_bar.setMaximum(100)
            self.view.progress_bar.setValue(0)
            self.view.progress_bar.setFormat("Error")
            self.logger.error(f"Report Generation Failed: {msg}")
            QMessageBox.warning(self.view, "Report Generation Failed", str(msg))

    def load_dataframe_to_table(self, df):
        try:
            from boresight.core import data_handler
            headers, rows = data_handler.prepare_table_data(df)
            
            self.view.report_table.setRowCount(len(rows))
            self.view.report_table.setColumnCount(len(headers))
            self.view.report_table.setHorizontalHeaderLabels(headers)
            
            for row_idx, row_data in enumerate(rows):
                for col_idx, cell_value in enumerate(row_data):
                    item = QTableWidgetItem(cell_value)
                    self.view.report_table.setItem(row_idx, col_idx, item)
            self.view.report_table.resizeColumnsToContents()
        except Exception as e:
            self.logger.error(f"Failed to populate table viewer: {str(e)}")

    def cleanup(self):
        if self.process_thread and self.process_thread.isRunning():
            self.process_thread.requestInterruption()
            self.process_thread.wait(3000)
        if self.report_thread and self.report_thread.isRunning():
            self.report_thread.wait(3000)
        shutil.rmtree(self.drop_cache_dir, ignore_errors=True)

    def close(self):
        return self.view.close()
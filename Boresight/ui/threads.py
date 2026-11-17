import os
import glob
from PySide6.QtCore import QThread, Signal
from core import pixel_scraper
from core import boresight_eval

class BatchProcessThread(QThread):
    progress_update = Signal(int, str)
    finished_data = Signal(list, list)

    def __init__(self, folder_list, input_dir, output_dir, colors,
                 manual_coords_dict=None, manual_override=False, system_paths_dict=None, roi_config=None):
        super().__init__()
        self.folder_list = folder_list
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.colors = colors
        self.manual_coords_dict = manual_coords_dict or {}
        self.manual_override = manual_override
        self.system_paths_dict = system_paths_dict
        self.roi_config = roi_config

    def _resolve_pair_paths(self, subfolder):
        if self.system_paths_dict is not None:
            pair = self.system_paths_dict.get(subfolder, {})
            return pair.get('EON'), pair.get('MWIR')

        valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        eon_folder = os.path.join(self.input_dir, "EON", subfolder)
        mwir_folder = os.path.join(self.input_dir, "MWIR", subfolder)
        eon_images = [img for img in glob.glob(os.path.join(eon_folder, "*.*")) if img.lower().endswith(valid_exts)]
        mwir_images = [img for img in glob.glob(os.path.join(mwir_folder, "*.*")) if img.lower().endswith(valid_exts)]
        return (eon_images[0] if eon_images else None), (mwir_images[0] if mwir_images else None)

    def run(self):
        intersection_data = []
        output_results_dir = os.path.join(self.output_dir, "Boresight_Outputs")

        for i, subfolder in enumerate(self.folder_list):
            if self.isInterruptionRequested():
                self.progress_update.emit(i, f"Cancelled during folder [{subfolder}].")
                break

            eon_path, mwir_path = self._resolve_pair_paths(subfolder)
            if not eon_path or not os.path.exists(eon_path) or not mwir_path or not os.path.exists(mwir_path):
                self.progress_update.emit(i + 1, f"Skipped System [{subfolder}]: Missing EON or MWIR image.")
                continue

            self.progress_update.emit(i + 1, f"Processing System [{subfolder}]...")
            coords = self.manual_coords_dict.get(subfolder) if self.manual_override else None
            result_dict, success = pixel_scraper.process_pair(
                eon_path, mwir_path, subfolder, output_results_dir,
                self.colors, self.colors, manual_coords=coords, roi_config=self.roi_config
            )
            if result_dict:
                intersection_data.append(result_dict)

        self.finished_data.emit(intersection_data, self.folder_list)

class ReportGeneratorThread(QThread):
    finished_report = Signal(bool, str, object)
    
    def __init__(self, excel_input, excel_output, plot_dir, sys_constants, active_systems=None):
        super().__init__()
        self.excel_input = excel_input
        self.excel_output = excel_output
        self.plot_dir = plot_dir
        self.sys_constants = sys_constants
        self.active_systems = active_systems

    def run(self):
        try:
            result = boresight_eval.generate_report(self.excel_input, self.excel_output, self.plot_dir, self.sys_constants, self.active_systems)
            self.finished_report.emit(result[0], result[1], result[2])
        except Exception as e:
            self.finished_report.emit(False, str(e), None)
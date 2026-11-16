import os
import glob
from PySide6.QtCore import QThread, Signal
from core import pixel_scraper

class BatchProcessThread(QThread):
    progress_update = Signal(int, str)
    finished_data = Signal(list, list)

    def __init__(self, folder_list, input_dir, output_dir, colors, manual_coords_dict=None, manual_override=False):
        super().__init__()
        self.folder_list = folder_list
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.colors = colors
        self.manual_coords_dict = manual_coords_dict or {}
        self.manual_override = manual_override

    def run(self):
        intersection_data = []
        eon_dir = os.path.join(self.input_dir, "EON")
        mwir_dir = os.path.join(self.input_dir, "MWIR")
        output_results_dir = os.path.join(self.output_dir, "Boresight_Outputs")

        for i, subfolder in enumerate(self.folder_list):
            if self.isInterruptionRequested():
                self.progress_update.emit(i, f"Cancelled during folder [{subfolder}].")
                break

            self.progress_update.emit(i + 1, f"Processing Folder [{subfolder}]...")

            eon_folder = os.path.join(eon_dir, subfolder)
            mwir_folder = os.path.join(mwir_dir, subfolder)
            
            valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
            eon_images = [img for img in glob.glob(os.path.join(eon_folder, "*.*")) if img.lower().endswith(valid_exts)]
            mwir_images = [img for img in glob.glob(os.path.join(mwir_folder, "*.*")) if img.lower().endswith(valid_exts)]
            
            if eon_images and mwir_images:
                coords = self.manual_coords_dict.get(subfolder) if self.manual_override else None
                result_dict, success = pixel_scraper.process_pair(
                    eon_images[0], mwir_images[0], subfolder, output_results_dir, 
                    self.colors, self.colors, manual_coords=coords
                )
                if result_dict:
                    intersection_data.append(result_dict)

        self.finished_data.emit(intersection_data, self.folder_list)
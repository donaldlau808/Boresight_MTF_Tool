from pathlib import Path
from PySide6.QtCore import QThread, Signal

class BatchProcessThread(QThread):
    progress_update = Signal(int, str)
    finished_data = Signal(object, list, list, list)

    def __init__(self, folder_list, input_dir, output_dir, colors,
                 manual_coords_dict=None, manual_override=False,
                 system_paths_dict=None, roi_config=None, optical_centers_dict=None):
        super().__init__()
        self.folder_list = folder_list
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.colors = colors
        self.manual_coords_dict = manual_coords_dict or {}
        self.manual_override = manual_override
        self.system_paths_dict = system_paths_dict
        self.roi_config = roi_config
        self.optical_centers_dict = optical_centers_dict or {}

    def _resolve_pair_paths(self, subfolder: str):
        if self.system_paths_dict is not None:
            pair = self.system_paths_dict.get(subfolder, {})
            return pair.get('EON'), pair.get('MWIR')

        valid_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
        eon_dir = self.input_dir / "EON" / subfolder
        mwir_dir = self.input_dir / "MWIR" / subfolder

        eon_img = next((p for p in eon_dir.iterdir() if p.suffix.lower() in valid_exts), None) if eon_dir.exists() else None
        mwir_img = next((p for p in mwir_dir.iterdir() if p.suffix.lower() in valid_exts), None) if mwir_dir.exists() else None

        return str(eon_img) if eon_img else None, str(mwir_img) if mwir_img else None

    def run(self):
        from boresight.core import pixel_scraper, data_handler

        intersection_data = []
        output_results_dir = self.output_dir / "Boresight_Outputs"

        for i, subfolder in enumerate(self.folder_list):
            if self.isInterruptionRequested():
                self.progress_update.emit(i, f"Cancelled during folder [{subfolder}].")
                break

            eon_path, mwir_path = self._resolve_pair_paths(subfolder)
            if not eon_path or not Path(eon_path).exists() or not mwir_path or not Path(mwir_path).exists():
                self.progress_update.emit(i + 1, f"Skipped System [{subfolder}]: Missing EON or MWIR image.")
                continue

            # Emit current count (i) on start so the bar does not jump to 100% prematurely
            self.progress_update.emit(i, f"Processing System [{subfolder}]...")
            coords = self.manual_coords_dict.get(subfolder) if self.manual_override else None

            result_dict, _ = pixel_scraper.process_pair(
                eon_path, mwir_path, subfolder, str(output_results_dir),
                self.colors, self.colors, manual_coords=coords, roi_config=self.roi_config,
                save_masks=not self.manual_override
            )

            if result_dict:
                opts = self.optical_centers_dict.get(subfolder, {'EON': None, 'MWIR': None})
                result_dict["EON Opt Center X"] = opts['EON'][0] if opts.get('EON') else None
                result_dict["EON Opt Center Y"] = opts['EON'][1] if opts.get('EON') else None
                result_dict["MWIR Opt Center X"] = opts['MWIR'][0] if opts.get('MWIR') else None
                result_dict["MWIR Opt Center Y"] = opts['MWIR'][1] if opts.get('MWIR') else None
                intersection_data.append(result_dict)

            self.progress_update.emit(i + 1, f"Finished System [{subfolder}].")

        df_final = None
        headers, rows = [], []
        if intersection_data:
            df_final = data_handler.process_batch_results(intersection_data)
            headers, rows = data_handler.prepare_table_data(df_final)

        self.finished_data.emit(df_final, headers, rows, self.folder_list)


class ReportGeneratorThread(QThread):
    finished_report = Signal(bool, str, object, list, list)

    def __init__(self, df_input, excel_output, sys_constants, active_systems=None):
        super().__init__()
        self.df_input = df_input
        self.excel_output = excel_output
        self.sys_constants = sys_constants
        self.active_systems = active_systems

    def run(self):
        from boresight.core import boresight_eval, data_handler

        try:
            success, msg, df_out = boresight_eval.generate_report(
                self.df_input, self.excel_output, self.sys_constants, self.active_systems
            )
            headers, rows = data_handler.prepare_table_data(df_out) if success else ([], [])
            self.finished_report.emit(success, msg, df_out, headers, rows)
        except Exception as e:
            self.finished_report.emit(False, str(e), None, [], [])
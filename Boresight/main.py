import sys
import os
import traceback
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog
from ui.main_window import MainWindow
from core.logger import setup_logger


def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Catches fatal errors, prevents silent UI crashes, and prompts user to save the crash log."""
    logger, _ = setup_logger()
    logger.critical("Uncaught Exception:", exc_info=(exc_type, exc_value, exc_traceback))

    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("Fatal Application Error")
    msg_box.setText("An unexpected error occurred and the application must close.\n\nPlease save the crash report on the next screen to provide to the developer.")
    msg_box.setDetailedText(error_msg)
    msg_box.exec()
    
    file_path, _ = QFileDialog.getSaveFileName(
        None, 
        "Save Crash Report", 
        os.path.join(os.path.expanduser("~"), "Desktop", "boresight_crash_report.txt"), 
        "Text Files (*.txt)"
    )
    
    if file_path:
        try:
            with open(file_path, 'w') as f:
                f.write("--- BORESIGHT TOOL CRASH REPORT ---\n\n")
                f.write(error_msg)
        except Exception as e:
            logger.error(f"Failed to save crash log: {e}")
            
    sys.exit(1)


def run_startup_checks():
    """Lightweight diagnostics to verify core runtime libraries and DLL bindings."""
    logger, _ = setup_logger()
    try:
        import pandas as pd
        import openpyxl
        import cv2
        import matplotlib
        logger.info("Startup Diagnostics: All core dependencies validated.")
        return True, ""
    except ImportError as e:
        logger.critical(f"Startup Diagnostics Failed: Missing library or runtime DLL - {e}")
        return False, str(e)


if __name__ == "__main__":
    sys.excepthook = global_exception_handler
    
    app = QApplication(sys.argv)

    ok, err_detail = run_startup_checks()
    if not ok:
        QMessageBox.critical(
            None, 
            "Startup Failure", 
            f"A critical library or Windows C++ runtime component failed to load:\n\n{err_detail}"
        )
        sys.exit(1)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
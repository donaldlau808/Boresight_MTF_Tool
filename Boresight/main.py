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
    
    # Ensure a QApplication exists to render the dialogs
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Critical)
    msg_box.setWindowTitle("Fatal Application Error")
    msg_box.setText("An unexpected error occurred and the application must close.\n\nPlease save the crash report on the next screen to provide to the developer.")
    msg_box.setDetailedText(error_msg)
    msg_box.exec()
    
    # Prompt the user to save the crash log somewhere they can easily find it
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
    """Lightweight diagnostics to verify system readiness."""
    logger, _ = setup_logger()
    try:
        # Verify pandas/openpyxl engine bindings are available early
        import pandas as pd
        import openpyxl
        logger.info("Startup Diagnostics: Dependencies validated.")
        return True
    except ImportError as e:
        logger.critical(f"Startup Diagnostics Failed: Missing library - {e}")
        return False

if __name__ == "__main__":
    # 1. Mount the global failure mode handler
    sys.excepthook = global_exception_handler
    
    app = QApplication(sys.argv)

    # 2. Run Startup Self-Checks
    if not run_startup_checks():
        QMessageBox.critical(
            None, 
            "Startup Failure", 
            "A critical dependency is missing. The application cannot start."
        )
        sys.exit(1)

    # 3. Launch UI
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
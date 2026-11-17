import logging
import os
import tempfile
from PySide6.QtCore import QObject, Signal

class LogEmitter(QObject):
    """Bridge to send log strings to the Qt Main Thread."""
    log_signal = Signal(str, str) # level, message

class GuiLogHandler(logging.Handler):
    """Custom logging handler that emits signals to the GUI."""
    def __init__(self):
        super().__init__()
        self.emitter = LogEmitter()

    def emit(self, record):
        msg = self.format(record)
        self.emitter.log_signal.emit(record.levelname, msg)

def setup_logger():
    logger = logging.getLogger("BoresightApp")
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        # EXE SAFE: Write the background log to the user's hidden OS Temp folder
        log_file = os.path.join(tempfile.gettempdir(), "boresight_background.log")
        
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        gui_h = GuiLogHandler()
        gui_h.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        gui_h.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        logger.addHandler(gui_h)
        
    return logger, logger.handlers[-1].emitter

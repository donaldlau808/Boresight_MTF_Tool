from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from boresight.ui.components.custom_labels import ResizableImageLabel

class OutputTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.diag_tabs = QTabWidget()
        
        self.diag_side_by_side = ResizableImageLabel()
        self.diag_eon_mask = ResizableImageLabel()
        self.diag_mwir_mask = ResizableImageLabel()

        self.diag_tabs.addTab(self.diag_side_by_side, "Side-by-Side Alignment")
        self.diag_tabs.addTab(self.diag_eon_mask, "EON Zoomed Mask")
        self.diag_tabs.addTab(self.diag_mwir_mask, "MWIR Zoomed Mask")
        layout.addWidget(self.diag_tabs)
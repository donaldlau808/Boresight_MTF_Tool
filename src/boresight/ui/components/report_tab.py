from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget

class ReportTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.report_table = QTableWidget()
        self.report_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(QLabel("Extracted Intersection Data Export:"))
        layout.addWidget(self.report_table)
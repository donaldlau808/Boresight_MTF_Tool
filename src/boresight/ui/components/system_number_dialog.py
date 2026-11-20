from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDialogButtonBox, QLabel

class SystemNumberDialog(QDialog):
    def __init__(self, channel, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Number Request")
        self.resize(350, 150)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Enter details for this {channel} image:"))
        
        form = QFormLayout()
        self.inp_sys = QLineEdit()
        self.inp_sys.setPlaceholderText("e.g. 123")
        
        self.inp_comment = QLineEdit()
        self.inp_comment.setPlaceholderText("e.g. pre_vib (optional)")
        
        form.addRow("System Number:", self.inp_sys)
        form.addRow("Comment/Tag:", self.inp_comment)
        layout.addLayout(form)
        
        self.btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        layout.addWidget(self.btn_box)

    def get_values(self):
        return self.inp_sys.text().strip(), self.inp_comment.text().strip()

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        self.inp_sys.setFocus()
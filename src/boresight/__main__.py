import sys
from PySide6.QtWidgets import QApplication
from boresight.ui.main_view import MainView
from boresight.ui.main_controller import MainController

def main():
    app = QApplication(sys.argv)
    
    view = MainView()
    controller = MainController(view)
    
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
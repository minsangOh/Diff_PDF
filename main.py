import sys
import ctypes
from PyQt6.QtWidgets import QApplication
from ui.main_window import DiffApp

if __name__ == "__main__":
    try:
        # Windows Taskbar Icon Fix
        myappid = 'selim.pdfdiff.tool.1.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass

    app = QApplication(sys.argv)
    window = DiffApp()
    window.show()
    sys.exit(app.exec())
"""Diagnostic: test if PySide6 GUI can launch from this environment."""
import sys
import traceback
from pathlib import Path

log_file = Path(__file__).parent / "_gui_diagnostic.log"

try:
    sys.path.insert(0, str(Path(__file__).parent))
    
    with open(log_file, "w") as f:
        f.write(f"Python: {sys.executable}\n")
        f.write(f"Version: {sys.version}\n")
        f.write(f"Path: {sys.path}\n\n")
        
        f.write("Importing PySide6...\n")
        from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
        from PySide6.QtCore import QTimer
        f.write("PySide6 imported OK\n\n")
        
        f.write("Creating QApplication...\n")
        app = QApplication([])
        f.write("QApplication created OK\n\n")
        
        f.write("Creating window...\n")
        win = QMainWindow()
        win.setWindowTitle("Diagnostic Test")
        win.resize(400, 200)
        label = QLabel("If you see this, PySide6 works!")
        win.setCentralWidget(label)
        win.show()
        f.write("Window shown OK\n\n")
        
        # Auto-close after 5 seconds
        QTimer.singleShot(5000, app.quit)
        
        f.write("Starting event loop...\n")
        f.flush()
        
    app.exec()
    
    with open(log_file, "a") as f:
        f.write("Event loop finished OK\n")
        
except Exception as e:
    with open(log_file, "a") as f:
        f.write(f"\nERROR: {e}\n")
        f.write(traceback.format_exc())

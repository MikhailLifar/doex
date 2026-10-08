"""QApplication bootstrap."""

from __future__ import annotations

import sys


def run_app() -> int:
    from PyQt5.QtWidgets import QApplication

    # Fusion: calm flat look per TZ visual tone
    QApplication.setStyle("Fusion")
    app = QApplication(sys.argv)
    app.setApplicationName("doex")
    app.setOrganizationName("doex")

    from doex.gui.main_window import MainWindow

    win = MainWindow()
    win.show()
    return app.exec_()

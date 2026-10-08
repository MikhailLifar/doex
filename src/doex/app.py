"""QApplication bootstrap — placeholder until GUI panels land."""

from __future__ import annotations

import sys


def run_app() -> int:
    from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow

    from doex import __version__

    app = QApplication(sys.argv)
    win = QMainWindow()
    win.setWindowTitle(f"doex {__version__}")
    win.setCentralWidget(
        QLabel(
            "doex scaffold\n\n"
            "See TZ.md for the full spec.\n"
            "Campaign UI lands in the next milestones."
        )
    )
    win.resize(520, 240)
    win.show()
    return app.exec_()

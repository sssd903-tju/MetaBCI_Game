#!/usr/bin/env python3
"""MetaBCI Platform — Desktop Application Entry Point."""
import sys
import argparse

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MetaBCI Platform')
    parser.add_argument('--simulate', action='store_true')
    args = parser.parse_args()

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName('MetaBCI Platform')
    app.setOrganizationName('TBC-TJU')

    from metabci.brainviz.theme import apply_theme
    apply_theme(app)

    from metabci.brainviz.main_window import MainWindow
    window = MainWindow(simulate=args.simulate)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())

# -*- coding: utf-8 -*-
"""
brainviz — MetaBCI Visualization Platform

用法:
    from metabci.brainviz import launch
    launch()
"""


def launch(simulate: bool = False):
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName('MetaBCI Platform')
    app.setOrganizationName('TBC-TJU')

    from metabci.brainviz.theme import apply_theme
    apply_theme(app)

    from metabci.brainviz.main_window import MainWindow
    window = MainWindow(simulate=simulate)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())

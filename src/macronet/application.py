"""Punto de entrada de la interfaz educativa de MacroNet."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

from macronet.domain.four_step import FOUR_STEP_SEQUENCE


class MainWindow(QMainWindow):
    """Ventana inicial del recorrido educativo."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MacroNet Transport")
        self.resize(900, 600)

        container = QWidget()
        layout = QVBoxLayout(container)

        title = QLabel("MacroNet Transport")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel("Modelo educativo de transporte de cuatro etapas")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        for index, stage in enumerate(FOUR_STEP_SEQUENCE, start=1):
            label = QLabel(f"{index}. {stage.display_name}")
            label.setStyleSheet("font-size: 18px; padding: 10px;")
            layout.addWidget(label)

        layout.addStretch()
        self.setCentralWidget(container)


def main() -> int:
    """Inicia la aplicación de escritorio."""

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

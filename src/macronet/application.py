"""Punto de entrada de la interfaz educativa de MacroNet."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from macronet.domain.four_step import FOUR_STEP_SEQUENCE
from macronet.ui.distribution_widget import DistributionWidget
from macronet.ui.generation_widget import GenerationWidget


class MainWindow(QMainWindow):
    """Ventana inicial del recorrido educativo."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MacroNet Transport")
        self.resize(1100, 760)

        tabs = QTabWidget()
        tabs.addTab(self._build_overview(), "Inicio")
        generation_widget = GenerationWidget()
        distribution_widget = DistributionWidget()
        generation_widget.result_calculated.connect(distribution_widget.set_from_generation)
        tabs.addTab(generation_widget, "1. Generación y atracción")
        tabs.addTab(distribution_widget, "2. Distribución")

        if generation_widget.current_result is not None:
            distribution_widget.set_from_generation(generation_widget.current_result)

        for index, stage in enumerate(FOUR_STEP_SEQUENCE[2:], start=3):
            placeholder = QLabel(
                f"{stage.display_name}\n\nMódulo planificado para una versión posterior."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("font-size: 18px; color: #666;")
            tabs.addTab(placeholder, f"{index}. {stage.display_name}")
            tabs.setTabEnabled(tabs.count() - 1, False)

        self.setCentralWidget(tabs)

    @staticmethod
    def _build_overview() -> QWidget:
        """Construye la portada y el recorrido de aprendizaje."""

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
        return container


def main() -> int:
    """Inicia la aplicación de escritorio."""

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

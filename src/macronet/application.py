"""Punto de entrada de la interfaz educativa de MacroNet."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from macronet import __version__
from macronet.domain.four_step import FOUR_STEP_SEQUENCE
from macronet.ui.assignment_widget import AssignmentWidget
from macronet.ui.distribution_widget import DistributionWidget
from macronet.ui.generation_widget import GenerationWidget
from macronet.ui.mode_choice_widget import ModeChoiceWidget
from macronet.ui.summary_widget import SummaryWidget

OVERVIEW_STAGES = (
    (
        "Generación y atracción de viajes",
        "Estima cuántos viajes produce y atrae cada zona mediante regresiones lineales "
        "y balanceo proporcional.",
    ),
    (
        "Distribución de viajes",
        "Relaciona orígenes y destinos en una matriz OD mediante un modelo gravitacional "
        "doblemente restringido y el algoritmo de Furness.",
    ),
    (
        "Elección modal",
        "Reparte cada flujo OD entre los modos disponibles mediante funciones de utilidad "
        "y un modelo logit multinomial.",
    ),
    (
        "Asignación de viajes",
        "Carga la demanda modal en la red con asignación Todo-o-Nada y rutas mínimas "
        "calculadas con el algoritmo de Dijkstra.",
    ),
)


class MainWindow(QMainWindow):
    """Ventana inicial del recorrido educativo."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"MacroNet Transport {__version__}")
        self.resize(1100, 760)

        tabs = QTabWidget()
        tabs.addTab(self._build_overview(), "Inicio")
        generation_widget = GenerationWidget()
        distribution_widget = DistributionWidget()
        mode_choice_widget = ModeChoiceWidget()
        assignment_widget = AssignmentWidget()
        summary_widget = SummaryWidget()
        generation_widget.result_calculated.connect(distribution_widget.set_from_generation)
        generation_widget.result_calculated.connect(summary_widget.set_from_generation)
        distribution_widget.result_calculated.connect(mode_choice_widget.set_from_distribution)
        distribution_widget.result_calculated.connect(summary_widget.set_from_distribution)
        mode_choice_widget.result_calculated.connect(assignment_widget.set_from_mode_choice)
        mode_choice_widget.result_calculated.connect(summary_widget.set_from_mode_choice)
        assignment_widget.result_calculated.connect(
            lambda result: summary_widget.set_from_assignment(
                result,
                assignment_widget.assigned_mode_name,
            )
        )
        tabs.addTab(generation_widget, "1. Generación y atracción")
        tabs.addTab(distribution_widget, "2. Distribución")
        tabs.addTab(mode_choice_widget, "3. Elección modal")
        tabs.addTab(assignment_widget, "4. Asignación")
        tabs.addTab(summary_widget, "Resumen")

        if generation_widget.current_result is not None:
            summary_widget.set_from_generation(generation_widget.current_result)
            distribution_widget.set_from_generation(generation_widget.current_result)

        for index, stage in enumerate(FOUR_STEP_SEQUENCE[4:], start=5):
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

        subtitle = QLabel("Modelo educativo de transporte de cuatro etapas para macrosimulación")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        for index, (name, description) in enumerate(OVERVIEW_STAGES, start=1):
            label = QLabel(f"<b>{index}. {name}</b><br><small>{description}</small>")
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            label.setStyleSheet("font-size: 18px; padding: 10px;")
            layout.addWidget(label)

        layout.addStretch()

        credits = QLabel(
            "Software libre (GPL-3.0) · Desarrollador: Héctor Benítez García"
        )
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setStyleSheet("font-size: 12px; padding: 6px;")
        layout.addWidget(credits)
        return container


def main() -> int:
    """Inicia la aplicación de escritorio."""

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

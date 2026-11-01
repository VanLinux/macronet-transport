"""Punto de entrada de la interfaz educativa de MacroNet."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from macronet import __version__
from macronet.domain.four_step import FOUR_STEP_SEQUENCE
from macronet.project import ProjectError, load_project, save_project
from macronet.sumo.scenario import SumoError
from macronet.ui.appearance import Appearance, make_scrollable
from macronet.ui.assignment_widget import AssignmentWidget
from macronet.ui.distribution_widget import DistributionWidget
from macronet.ui.generation_widget import GenerationWidget
from macronet.ui.microsimulation_widget import MicrosimulationWidget
from macronet.ui.mode_choice_widget import ModeChoiceWidget
from macronet.ui.project_state import capture_document, capture_inputs, restore_document
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
        "Carga la demanda modal con Todo-o-Nada o equilibrio de Wardrop, "
        "con comparación de flujos y diagnóstico de convergencia.",
    ),
)


class MainWindow(QMainWindow):
    """Ventana inicial del recorrido educativo."""

    def __init__(self) -> None:
        super().__init__()
        self.appearance = Appearance(self)
        self.setWindowTitle(f"MacroNet Transport {__version__}")
        self.resize(1280, 900)
        self.project_path: Path | None = None
        self._dirty = False
        self._close_after_sumo = False
        self._install_tabs(ExerciseTabs())
        file_menu = self.menuBar().addMenu("Archivo")
        for title, shortcut, callback in (
            ("Abrir ejercicio (.mnet)…", QKeySequence.StandardKey.Open, self._open_project),
            ("Guardar ejercicio", QKeySequence.StandardKey.Save, self._save_project),
            ("Guardar ejercicio como…", QKeySequence.StandardKey.SaveAs, self._save_project_as),
        ):
            action = QAction(title, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            file_menu.addAction(action)
        view_menu = self.menuBar().addMenu("Apariencia")
        themes = QActionGroup(self)
        themes.setExclusive(True)
        for title, mode in (("Seguir al sistema", "auto"), ("Claro", "light"), ("Oscuro", "dark")):
            action = QAction(title, themes)
            action.setCheckable(True)
            action.setChecked(mode == "auto")
            action.triggered.connect(lambda _checked, value=mode: self.appearance.set_mode(value))
            view_menu.addAction(action)
        help_menu = self.menuBar().addMenu("Ayuda")
        about = help_menu.addAction("Acerca de…")
        about.triggered.connect(self._show_about)
        self._update_title()

    def _show_about(self):
        from macronet.ui.about_dialog import AboutDialog

        dialog = AboutDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _install_tabs(self, tabs) -> None:
        self.setCentralWidget(tabs)
        for table in tabs.findChildren(QTableWidget):
            table.itemChanged.connect(self._mark_dirty)
        for spin in (*tabs.findChildren(QDoubleSpinBox), *tabs.findChildren(QSpinBox)):
            spin.valueChanged.connect(self._mark_dirty)
        for selector in tabs.findChildren(QComboBox):
            selector.currentIndexChanged.connect(self._mark_dirty)
        for checkbox in tabs.findChildren(QCheckBox):
            checkbox.toggled.connect(self._mark_dirty)
        for widget in tabs.stages.values():
            if hasattr(widget, "calibration"):
                widget.calibration.changed.connect(self._mark_dirty)
        tabs.widget(5).analyst_changed.connect(self._mark_dirty)
        tabs.widget(3).fares_changed.connect(self._mark_dirty)
        tabs.microsimulation.changed.connect(self._mark_dirty)
        tabs.microsimulation.running_changed.connect(self._sumo_running_changed)

    def _sumo_running_changed(self, running):
        if not running and self._close_after_sumo:
            QTimer.singleShot(0, self.close)

    def _mark_dirty(self, *_args) -> None:
        self._dirty = True
        self._update_title()

    def _update_title(self) -> None:
        name = self.project_path.name if self.project_path else "Ejercicio nuevo"
        self.setWindowTitle(
            f"MacroNet Transport {__version__} — {name}{' *' if self._dirty else ''}"
        )
        self.statusBar().showMessage(
            "Cambios sin guardar · Archivo → Guardar ejercicio (.mnet)"
            if self._dirty
            else str(self.project_path)
            if self.project_path
            else "Archivo → Abrir o Guardar ejercicio (.mnet) para continuar después."
        )

    def _save_project_as(self) -> bool:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar ejercicio completo",
            str(self.project_path or "ejercicio.mnet"),
            "Ejercicio MacroNet (*.mnet)",
        )
        if not filename:
            return False
        path = Path(filename)
        if path.suffix.casefold() != ".mnet":
            path = path.with_suffix(".mnet")
        return self._write_project(path)

    def _save_project(self) -> bool:
        return (
            self._write_project(self.project_path) if self.project_path else self._save_project_as()
        )

    def _write_project(self, path: Path) -> bool:
        self._commit_pending_editor()
        try:
            save_project(path, capture_document(self.centralWidget()))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo guardar el ejercicio", str(error))
            return False
        self.project_path = path
        self._dirty = False
        self._update_title()
        return True

    def _confirm_unsaved(self) -> bool:
        self._commit_pending_editor()
        if not self._dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Cambios sin guardar",
            "¿Desea guardar el ejercicio antes de continuar?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self._save_project()
        return answer == QMessageBox.StandardButton.Discard

    def _commit_pending_editor(self) -> None:
        """Confirma la celda activa también al guardar mediante Ctrl+S o cerrar."""

        focused = QApplication.focusWidget()
        if focused is not None and self.isAncestorOf(focused):
            focused.clearFocus()

    def _open_project(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Abrir ejercicio", "", "Ejercicio MacroNet (*.mnet)"
        )
        if not filename:
            return
        self.open_project_path(Path(filename))

    def open_project_path(self, path: Path) -> bool:
        """Prepara una vista completa y solo la sustituye si el archivo es válido."""

        if self.centralWidget().microsimulation.is_running:
            QMessageBox.information(
                self,
                "Microsimulación en curso",
                "Cancele o espere la ejecución antes de abrir otro ejercicio.",
            )
            return False
        # Guardar antes de leer evita reabrir una copia antigua del mismo archivo.
        if not self._confirm_unsaved():
            return False
        candidate = None
        try:
            document = load_project(path)
            candidate = ExerciseTabs()
            restore_document(candidate, document)
        except (OSError, ProjectError, ValueError, AttributeError, OverflowError) as error:
            if candidate is not None:
                candidate.deleteLater()
            QMessageBox.critical(self, "No se pudo abrir el ejercicio", str(error))
            return False
        self._install_tabs(candidate)
        self.project_path = path
        self._dirty = False
        self._update_title()
        if document["draft"] != document["calculated"]:
            self.statusBar().showMessage(
                "Ejercicio abierto con cambios pendientes de calcular. "
                "Los resultados muestran el último cálculo válido."
            )
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        simulation = self.centralWidget().microsimulation
        if simulation.is_running:
            self._close_after_sumo = True
            simulation.cancel()
            event.ignore()
        else:
            self._close_after_sumo = False
            if self._confirm_unsaved():
                event.accept()
            else:
                event.ignore()


class ExerciseTabs(QTabWidget):
    """Ejercicio independiente que puede validarse antes de sustituir el abierto."""

    def __init__(self) -> None:
        super().__init__()

        tabs = self
        tabs.addTab(self._build_overview(), "Inicio")
        generation_widget = GenerationWidget()
        distribution_widget = DistributionWidget()
        mode_choice_widget = ModeChoiceWidget()
        assignment_widget = AssignmentWidget()
        summary_widget = SummaryWidget()
        self.microsimulation = MicrosimulationWidget(self._sumo_source)
        generation_widget.result_calculated.connect(distribution_widget.set_from_generation)
        generation_widget.result_calculated.connect(summary_widget.set_from_generation)
        distribution_widget.result_calculated.connect(mode_choice_widget.set_from_distribution)
        distribution_widget.result_calculated.connect(summary_widget.set_from_distribution)
        mode_choice_widget.result_calculated.connect(assignment_widget.set_from_mode_choice)
        mode_choice_widget.result_calculated.connect(summary_widget.set_from_mode_choice)
        assignment_widget.result_calculated.connect(self._update_assignment_summary)
        assignment_widget.result_calculated.connect(self.microsimulation.invalidate)
        tabs.addTab(generation_widget, "1. Generación y atracción")
        tabs.addTab(distribution_widget, "2. Distribución")
        tabs.addTab(mode_choice_widget, "3. Elección modal")
        tabs.addTab(assignment_widget, "4. Asignación")
        tabs.addTab(summary_widget, "Resumen")
        tabs.addTab(self.microsimulation, "Microsimulación SUMO")

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

        self.stages = dict(
            zip(
                ("generation", "distribution", "modal", "assignment"),
                (generation_widget, distribution_widget, mode_choice_widget, assignment_widget),
                strict=True,
            )
        )
        self.calculated_states = {
            stage: capture_inputs(stage, widget) for stage, widget in self.stages.items()
        }
        for widget in self.stages.values():
            widget.result_calculated.connect(self._capture_calculated_state)
        summary_widget.metadata_provider = self._report_metadata
        summary_widget.fare_scenarios_provider = lambda: mode_choice_widget.fare_scenarios
        summary_widget.microsimulation_provider = self.microsimulation.state
        self.microsimulation.changed.connect(summary_widget.refresh_sumo)
        self.microsimulation.sync_geometry()
        for widget in (*self.stages.values(), summary_widget, self.microsimulation):
            make_scrollable(widget)
        summary_widget.mode_table.setColumnWidth(0, 220)

    def _sumo_source(self):
        source = self.calculated_states["assignment"]
        if capture_inputs("assignment", self.stages["assignment"]) != source:
            raise SumoError(
                "Hay cambios de asignación pendientes. Pulse Asignar o Comparar "
                "antes de preparar la microsimulación."
            )
        return source

    def _report_metadata(self):
        return self.calculated_states

    def _capture_calculated_state(self, _result: object) -> None:
        sender = self.sender()
        for stage, widget in self.stages.items():
            if widget is sender:
                self.calculated_states[stage] = capture_inputs(stage, widget)
                break

    def _update_assignment_summary(self, result: object) -> None:
        assignment = self.widget(4)
        self.widget(5).set_from_assignment(
            result, assignment.assigned_mode_name, assignment.comparison
        )

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

        credits = QLabel("Software libre (GPL-3.0) · Desarrollador: Héctor Benítez García")
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

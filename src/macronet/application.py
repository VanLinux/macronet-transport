"""Punto de entrada de la interfaz educativa de MacroNet."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from macronet import __version__
from macronet.project import ProjectError, load_project, save_project
from macronet.sumo.scenario import SumoError
from macronet.ui.appearance import Appearance, install_scroll_guard, make_scrollable
from macronet.ui.assignment_widget import AssignmentWidget
from macronet.ui.distribution_widget import DistributionWidget
from macronet.ui.generation_widget import GenerationWidget
from macronet.ui.microsimulation_widget import MicrosimulationWidget
from macronet.ui.mode_choice_widget import ModeChoiceWidget
from macronet.ui.project_state import capture_document, capture_inputs, restore_document
from macronet.ui.summary_widget import SummaryWidget

REPOSITORY_URL = "https://github.com/VanLinux/macronet-transport"
MANUAL_URL = REPOSITORY_URL + "/blob/main/docs/manual.md"
OVERLEAF_URL = "https://www.overleaf.com/project"


class MainWindow(QMainWindow):
    """Ventana inicial del recorrido educativo."""

    def __init__(self) -> None:
        super().__init__()
        self.appearance = Appearance(self)
        install_scroll_guard(QApplication.instance())
        self.setWindowTitle(f"MacroNet Transport {__version__}")
        self.resize(1280, 900)
        self.project_path: Path | None = None
        self._dirty = False
        self._close_after_sumo = False
        self._install_tabs(ExerciseTabs())
        self._build_menus()
        self._update_title()

    def _build_menus(self):
        standard = QKeySequence.StandardKey
        icon = QStyle.StandardPixmap
        file_menu = self.menuBar().addMenu("Archivo")
        self._add_action(
            file_menu, "Nuevo", self._new_project, standard.New, icon.SP_FileIcon
        )
        self._add_action(
            file_menu, "Abrir…", self._open_project, standard.Open, icon.SP_DialogOpenButton
        )
        file_menu.addSeparator()
        self._add_action(
            file_menu, "Guardar", self._save_project, standard.Save, icon.SP_DialogSaveButton
        )
        self._add_action(file_menu, "Guardar como…", self._save_project_as, standard.SaveAs)
        export = file_menu.addMenu("Exportar")
        exports = (
            ("Informe técnico (.tex)…", 5, "_export_tex", "export_button"),
            ("Matriz OD (.csv)…", 2, "_export_od_csv", "export_button"),
            ("Matrices modales (.csv)…", 3, "_export_modal_csv", "export_button"),
            ("Flujos de asignación (.csv)…", 4, "_export_csv", "export_graph_button"),
            ("Red asignada (.graphml)…", 4, "_export_graphml", "export_graph_button"),
        )
        actions = []
        for label, index, method, button in exports:
            action = self._add_action(
                export, label,
                lambda i=index, fn=method: getattr(self.centralWidget().widget(i), fn)(),
            )
            actions.append((action, index, button))

        def update_exports():
            tabs = self.centralWidget()
            for action, index, button in actions:
                action.setEnabled(getattr(tabs.widget(index), button).isEnabled())

        export.aboutToShow.connect(update_exports)
        file_menu.addSeparator()
        self._add_action(file_menu, "Salir", self.close, standard.Quit)

        project = self.menuBar().addMenu("Proyecto")
        self._add_action(project, "Cargar caso demostrativo", self._load_demonstration)
        simulation = project.addMenu("Simular")
        self._add_action(simulation, "Calcular las cuatro etapas", self._calculate_project)
        self._add_action(simulation, "Microsimulación con SUMO…", self._open_sumo)

        view_menu = self.menuBar().addMenu("Vista")
        themes = QActionGroup(self)
        themes.setExclusive(True)
        for label, mode in (("Modo claro", "light"), ("Modo oscuro", "dark")):
            action = QAction(label, themes)
            action.setCheckable(True)
            action.setChecked(self.appearance.dark == (mode == "dark"))
            action.triggered.connect(lambda _checked, value=mode: self.appearance.set_mode(value))
            view_menu.addAction(action)

        help_menu = self.menuBar().addMenu("Ayuda")
        self._add_action(help_menu, "Acerca de…", self._show_about)
        self._add_action(
            help_menu, "Manual de usuario ↗", lambda: QDesktopServices.openUrl(QUrl(MANUAL_URL))
        )
        self._add_action(
            help_menu, "Compilar .tex en Overleaf ↗",
            lambda: QDesktopServices.openUrl(QUrl(OVERLEAF_URL)),
        )

    def _add_action(self, menu, label, callback, shortcut=None, icon=None):
        action = QAction(label, self)
        if icon is not None:
            action.setIcon(self.style().standardIcon(icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(lambda _checked=False: callback())
        menu.addAction(action)
        return action

    def _new_project(self):
        return self._replace_exercise(demonstration=False)

    def _load_demonstration(self):
        return self._replace_exercise(demonstration=True)

    def _replace_exercise(self, *, demonstration):
        if not self._can_replace_exercise():
            return False
        self._install_tabs(ExerciseTabs(demonstration=demonstration))
        self.project_path = None
        self._dirty = demonstration
        self._update_title()
        if demonstration:
            self.statusBar().showMessage(
                "Caso demostrativo cargado · 4 zonas · Datos ficticios para práctica."
            )
        return True

    def _calculate_project(self):
        tabs = self.centralWidget()
        if tabs.microsimulation.is_running:
            return
        self._commit_pending_editor()
        if tabs.calculate_all():
            tabs.setCurrentIndex(5)
            self.statusBar().showMessage("Cálculo de las cuatro etapas terminado.")

    def _open_sumo(self):
        tabs = self.centralWidget()
        tabs.setCurrentWidget(tabs.microsimulation)

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
        for key in ("generation", "assignment"):
            tabs.stages[key].inputs_changed.connect(self._mark_dirty)
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
            "Cambios sin guardar · Archivo → Guardar (.mnet)"
            if self._dirty
            else str(self.project_path)
            if self.project_path
            else "Proyecto → Cargar caso demostrativo, o capture sus datos en la etapa 1."
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

        if not self._can_replace_exercise():
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

    def _can_replace_exercise(self):
        if self.centralWidget().microsimulation.is_running:
            QMessageBox.information(
                self,
                "Microsimulación en curso",
                "Cancele o espere la ejecución antes de cambiar de ejercicio.",
            )
            return False
        return self._confirm_unsaved()

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

    def __init__(self, *, demonstration=False) -> None:
        super().__init__()
        self._batch = False
        self.addTab(self._build_overview(), "Inicio y alcance")
        self.stages = {
            "generation": GenerationWidget(),
            "distribution": DistributionWidget(),
            "modal": ModeChoiceWidget(),
            "assignment": AssignmentWidget(),
        }
        self.calculated_states = {}
        summary = SummaryWidget()
        self.microsimulation = MicrosimulationWidget(self._sumo_source)
        for widget, label in zip(
            self.stages.values(),
            ("1. Generación y atracción", "2. Distribución", "3. Elección modal", "4. Asignación"),
            strict=True,
        ):
            self.addTab(widget, label)
        self.addTab(summary, "Resumen")
        self.addTab(self.microsimulation, "Microsimulación SUMO")
        for stage, widget in self.stages.items():
            widget.result_calculated.connect(
                lambda result, key=stage: self._stage_calculated(key, result)
            )
        summary.metadata_provider = self._report_metadata
        summary.report_issue_provider = self._report_issue
        summary.fare_scenarios_provider = lambda: self.stages["modal"].fare_scenarios
        summary.microsimulation_provider = self.microsimulation.state
        self.microsimulation.changed.connect(summary.refresh_sumo)
        for widget in (self.widget(0), *self.stages.values(), summary, self.microsimulation):
            make_scrollable(widget)
        summary.mode_table.setColumnWidth(0, 220)
        if demonstration:
            self.stages["distribution"].load_example()
            self.stages["modal"].load_example()
            self.stages["assignment"].load_example()
            self.stages["generation"].load_example()
            self.microsimulation.sync_geometry()

    def calculate_all(self):
        """Calcula en secuencia y muestra la primera etapa que aún requiere datos."""
        self._batch = True
        try:
            for index, widget in enumerate(self.stages.values(), 1):
                try:
                    widget.calculate(raise_errors=True)
                except ValueError as error:
                    self.setCurrentIndex(index)
                    QMessageBox.warning(self, self.tabText(index), str(error))
                    return False
        finally:
            self._batch = False
        return True

    def _stage_calculated(self, stage, result):
        widget = self.stages[stage]
        self.calculated_states[stage] = capture_inputs(stage, widget)
        summary = self.widget(5)
        next_stage = None
        if stage == "generation":
            if result != summary.generation_result:
                next_stage = self.stages["distribution"]
                next_stage.set_from_generation(result)
            summary.set_from_generation(result)
        elif stage == "distribution":
            summary.set_from_distribution(result)
            next_stage = self.stages["modal"]
            next_stage.set_from_distribution(result)
        elif stage == "modal":
            summary.set_from_mode_choice(result)
            next_stage = self.stages["assignment"]
            next_stage.set_from_mode_choice(result)
        else:
            summary.set_from_assignment(result, widget.assigned_mode_name, widget.comparison)
            self.microsimulation.invalidate()
            summary.refresh_sumo()
        if next_stage is not None and not self._batch:
            try:
                next_stage.calculate(raise_errors=True)
            except ValueError:
                # Puede faltar una matriz de impedancias o una red aún en captura.
                # El botón de la etapa muestra el diagnóstico completo cuando se pulsa.
                pass

    def _sumo_source(self):
        source = self.calculated_states.get("assignment")
        if source is None:
            raise SumoError("Calcule la asignación antes de preparar la microsimulación.")
        if capture_inputs("assignment", self.stages["assignment"]) != source:
            raise SumoError(
                "Hay cambios de asignación pendientes. Pulse Asignar o Comparar "
                "antes de preparar la microsimulación."
            )
        return source

    def _report_metadata(self):
        return self.calculated_states

    def _report_issue(self):
        summary = self.widget(5)
        if not {"modal", "assignment"} <= self.calculated_states.keys():
            return ""
        modal = self.calculated_states["modal"]
        assignment = self.calculated_states["assignment"]
        distribution = summary.distribution_result
        mode = next(
            (mode for mode in summary.mode_choice_result.mode_summaries
             if mode.mode_name == assignment["mode_name"]),
            None,
        )
        if (
            tuple(zone.zone.name for zone in summary.generation_result.zones)
            != distribution.zone_names
            or tuple(modal["zone_names"]) != distribution.zone_names
            or modal["trip_matrix"] != [list(row) for row in distribution.trip_matrix]
            or modal["impedance_matrix"] != [list(row) for row in distribution.impedance_matrix]
            or tuple(assignment["zone_names"]) != summary.mode_choice_result.zone_names
            or mode is None
            or assignment["demand_matrix"] != [list(row) for row in mode.trip_matrix]
        ):
            return (
                "El resumen conserva resultados anteriores de alguna etapa. "
                "Actualice los cálculos antes de exportar el informe conjunto."
            )
        return ""

    @staticmethod
    def _build_overview() -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        card = QFrame()
        card.setObjectName("overviewCard")
        content = QVBoxLayout(card)
        content.setContentsMargins(18, 16, 18, 18)
        content.setSpacing(9)

        def add_label(text):
            label = QLabel(text)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            content.addWidget(label)
            return label

        add_label("<b>MacroNet Transport</b>").setStyleSheet("font-size: 28px;")
        add_label(
            "<b>Modelación macroscópica de la demanda de transporte</b><br>"
            "Herramienta libre para estudiar el modelo clásico de cuatro etapas."
        )
        metadata = QGridLayout()
        metadata.setHorizontalSpacing(18)
        metadata.setVerticalSpacing(6)
        metadata.setColumnStretch(2, 1)
        for row, (key, value) in enumerate((
            ("Versión", __version__),
            ("Desarrollador", "Héctor Alonso Benítez García"),
            ("Licencia", "GNU General Public License v3.0"),
            ("Plataforma actual", platform.system()),
            ("Repositorio", "github.com/VanLinux/macronet-transport"),
        )):
            metadata.addWidget(QLabel(f"<b>{key}</b>"), row, 0)
            if key == "Repositorio":
                link = QPushButton(value)
                link.setObjectName("overviewLink")
                link.setCursor(Qt.CursorShape.PointingHandCursor)
                link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPOSITORY_URL)))
                metadata.addWidget(link, row, 1, alignment=Qt.AlignmentFlag.AlignLeft)
            else:
                metadata.addWidget(QLabel(value), row, 1)
        content.addLayout(metadata)

        add_label(
            "<b>Alcance:</b> estima viajes por zona, distribuye la demanda en una matriz OD, "
            "reparte los viajes entre modos y asigna un modo a la red vial por Todo o Nada "
            "o por equilibrio de Wardrop. Incluye calibración, tarifas y "
            "microsimulación vehicular opcional con SUMO."
        )
        add_label(
            "<b>Límites:</b> no diseña intersecciones ni optimiza semáforos. "
            "No pronostica con datos reales sin calibración y validación, "
            "ni determina por sí solo el nivel de servicio HCM."
        )
        add_label(
            "<b>Flujo de trabajo</b>"
            "<ol><li>Capture las zonas o elija Proyecto → Cargar caso demostrativo.</li>"
            "<li>Calcule producciones y atracciones; capture las impedancias OD.</li>"
            "<li>Revise los parámetros de elección modal y las tarifas, si se usan.</li>"
            "<li>Defina centroides y arcos; elija el método de asignación.</li>"
            "<li>Revise el Resumen y exporte el informe técnico desde Archivo.</li></ol>"
        )
        add_label(
            "<b>Supuestos principales</b><ul>"
            "<li>Las unidades y el periodo de análisis deben ser coherentes entre etapas.</li>"
            "<li>Las impedancias, parámetros y capacidades representan el escenario analizado.</li>"
            "<li>SUMO requiere una red y una demanda vehicular coherentes; "
            "la geometría inicial debe verificarse antes de simular.</li></ul>"
        )
        layout.addWidget(card)
        layout.addStretch()
        return container


def main() -> int:
    """Inicia la aplicación de escritorio."""

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()

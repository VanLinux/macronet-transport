"""Resumen integrado y exportable del modelo de cuatro etapas."""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from macronet.domain.assignment import AssignmentResult
from macronet.domain.distribution import DistributionResult
from macronet.domain.generation import GenerationResult
from macronet.domain.mode_choice import ModeChoiceResult
from macronet.exporters import save_summary_tex


class SummaryWidget(QWidget):
    """Concentra los indicadores esenciales de las cuatro etapas."""

    def __init__(self) -> None:
        super().__init__()
        self.generation_result: GenerationResult | None = None
        self.distribution_result: DistributionResult | None = None
        self.mode_choice_result: ModeChoiceResult | None = None
        self.assignment_result: AssignmentResult | None = None
        self.assigned_mode = "Automóvil"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Resumen del análisis")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        explanation = QLabel(
            "Esta vista reúne los indicadores indispensables de las cuatro etapas y se "
            "actualiza automáticamente después de cada cálculo."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        generation_group = QGroupBox("1. Generación y atracción")
        generation_layout = QVBoxLayout(generation_group)
        self.generation_label = QLabel("Sin resultados.")
        self.generation_label.setWordWrap(True)
        generation_layout.addWidget(self.generation_label)
        layout.addWidget(generation_group)

        distribution_group = QGroupBox("2. Distribución")
        distribution_layout = QVBoxLayout(distribution_group)
        self.distribution_label = QLabel("Sin resultados.")
        self.distribution_label.setWordWrap(True)
        distribution_layout.addWidget(self.distribution_label)
        layout.addWidget(distribution_group)

        mode_group = QGroupBox("3. Elección modal")
        mode_layout = QVBoxLayout(mode_group)
        self.mode_table = QTableWidget(0, 3)
        self.mode_table.setHorizontalHeaderLabels(("Modo", "Viajes", "Participación"))
        self.mode_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mode_table.setMaximumHeight(150)
        mode_layout.addWidget(self.mode_table)
        layout.addWidget(mode_group)

        assignment_group = QGroupBox("4. Asignación")
        assignment_layout = QVBoxLayout(assignment_group)
        self.assignment_label = QLabel("Sin resultados.")
        self.assignment_label.setWordWrap(True)
        assignment_layout.addWidget(self.assignment_label)
        layout.addWidget(assignment_group)

        self.export_button = QPushButton("Descargar informe (.tex)")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_tex)
        layout.addWidget(self.export_button)
        layout.addStretch()

    def set_from_generation(self, result: GenerationResult) -> None:
        self.generation_result = result
        self.generation_label.setText(
            f"<b>Viajes producidos:</b> {result.total_productions:,.2f} &nbsp; · &nbsp; "
            f"<b>Atracciones iniciales:</b> {result.total_attractions_raw:,.2f} &nbsp; · "
            f"&nbsp; <b>Factor de balanceo:</b> {result.balance_factor:.4f} &nbsp; · &nbsp; "
            f"<b>Atracciones balanceadas:</b> {result.total_attractions_balanced:,.2f}"
        )
        self._update_export_state()

    def set_from_distribution(self, result: DistributionResult) -> None:
        self.distribution_result = result
        state = "Sí" if result.converged else "No"
        self.distribution_label.setText(
            f"<b>Viajes distribuidos:</b> {sum(result.row_totals):,.2f} &nbsp; · &nbsp; "
            f"<b>Convergió:</b> {state} &nbsp; · &nbsp; "
            f"<b>Iteraciones:</b> {result.iterations} &nbsp; · &nbsp; "
            f"<b>Error máximo:</b> {result.maximum_error:.3e} viajes"
        )
        self._update_export_state()

    def set_from_mode_choice(self, result: ModeChoiceResult) -> None:
        self.mode_choice_result = result
        self.mode_table.setRowCount(len(result.mode_summaries) + 1)
        for row, mode in enumerate(result.mode_summaries):
            self._set_table_row(
                row,
                (mode.mode_name, f"{mode.total_trips:,.2f}", f"{mode.share:.2%}"),
            )
        self._set_table_row(
            len(result.mode_summaries),
            ("Total", f"{result.total_trips:,.2f}", "100.00%"),
        )
        self._update_export_state()

    def set_from_assignment(self, result: AssignmentResult, mode_name: str) -> None:
        self.assignment_result = result
        self.assigned_mode = mode_name
        critical = max(result.link_results, key=lambda item: item.volume_capacity_ratio)
        overloaded = sum(item.volume_capacity_ratio > 1.0 for item in result.link_results)
        self.assignment_label.setText(
            f"<b>Modo asignado:</b> {escape(mode_name)} &nbsp; · &nbsp; "
            f"<b>Demanda interzonal:</b> {result.assigned_demand:,.2f} &nbsp; · &nbsp; "
            f"<b>Demanda intrazonal:</b> {result.intrazonal_demand:,.2f}<br>"
            f"<b>Arco crítico:</b> {escape(critical.link.link_id)} "
            f"({escape(critical.link.tail)} → {escape(critical.link.head)}) &nbsp; · &nbsp; "
            f"<b>Máximo v/c:</b> {critical.volume_capacity_ratio:.3f} &nbsp; · &nbsp; "
            f"<b>Arcos con v/c &gt; 1:</b> {overloaded}"
        )
        self._update_export_state()

    @staticmethod
    def _set_item(table: QTableWidget, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, column, item)

    def _set_table_row(self, row: int, values: tuple[str, str, str]) -> None:
        for column, value in enumerate(values):
            self._set_item(self.mode_table, row, column, value)

    def _update_export_state(self) -> None:
        self.export_button.setEnabled(
            all(
                result is not None
                for result in (
                    self.generation_result,
                    self.distribution_result,
                    self.mode_choice_result,
                    self.assignment_result,
                )
            )
        )

    def _export_tex(self) -> None:
        if not all(
            result is not None
            for result in (
                self.generation_result,
                self.distribution_result,
                self.mode_choice_result,
                self.assignment_result,
            )
        ):
            QMessageBox.information(
                self,
                "Análisis incompleto",
                "Deben existir resultados válidos de las cuatro etapas.",
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar informe LaTeX",
            "resumen_macronet.tex",
            "Documento LaTeX (*.tex)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.casefold() != ".tex":
            path = path.with_suffix(".tex")
        try:
            save_summary_tex(
                path,
                self.generation_result,
                self.distribution_result,
                self.mode_choice_result,
                self.assignment_result,
                self.assigned_mode,
            )
        except OSError as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))
            return
        QMessageBox.information(self, "Exportación terminada", f"Informe guardado en:\n{path}")

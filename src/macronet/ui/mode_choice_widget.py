"""Interfaz educativa del modelo logit multinomial."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from macronet.domain.mode_choice import (
    ModeChoiceError,
    ModeChoiceResult,
    ModeSpecification,
    choose_modes,
)

EXAMPLE_NAMES = ("Centro", "Norte", "Sur", "Oriente")
EXAMPLE_IMPEDANCES = (
    (3.0, 10.0, 15.0, 20.0),
    (10.0, 3.0, 12.0, 18.0),
    (15.0, 12.0, 3.0, 9.0),
    (20.0, 18.0, 9.0, 3.0),
)
EXAMPLE_TRIPS = (
    (168.4462148161, 50.4945794760, 24.1036672614, 16.9555387562),
    (112.1954983070, 136.3864451476, 43.6407073136, 27.7773494897),
    (65.9662329679, 53.7526239711, 104.0519702133, 66.2291727064),
    (53.3920539090, 39.3663514053, 76.2036552118, 161.0379390477),
)
DEFAULT_MODES = (
    ModeSpecification("Automóvil", 0.3, 1.0, 0.0, 5.0, 0.25),
    ModeSpecification("Transporte público", 0.6, 1.35, 5.0, 6.0, 0.0),
    ModeSpecification("Bicicleta", -0.8, 2.2, 0.0, 0.0, 0.0),
)


class ModeChoiceWidget(QWidget):
    """Expone utilidades, probabilidades y matrices modales."""

    result_calculated = Signal(object)

    MODE_HEADERS = (
        "Modo",
        "Constante ASC",
        "Multiplicador de tiempo",
        "Tiempo fijo",
        "Costo fijo",
        "Costo variable",
    )

    def __init__(self) -> None:
        super().__init__()
        self._zone_names = EXAMPLE_NAMES
        self._trip_matrix = EXAMPLE_TRIPS
        self._impedance_matrix = EXAMPLE_IMPEDANCES
        self.current_result: ModeChoiceResult | None = None
        self._modal_matrix_tables: list[QTableWidget] = []
        self._build_ui()
        self._restore_defaults()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Elección modal")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        explanation = QLabel(
            "Cada celda de la matriz OD se divide entre las alternativas mediante sus "
            "utilidades. Modifique los parámetros para observar cómo cambian las cuotas."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(self._build_equations_group())
        layout.addWidget(self._build_coefficients_group())

        self.modes_table = QTableWidget(0, len(self.MODE_HEADERS))
        self.modes_table.setHorizontalHeaderLabels(self.MODE_HEADERS)
        self._stretch_headers(self.modes_table)
        self.modes_table.setMaximumHeight(170)
        layout.addWidget(self.modes_table)

        selector_group = QGroupBox("Par origen-destino para inspección")
        selector_layout = QGridLayout(selector_group)
        self.od_selector = QComboBox()
        self.od_selector.currentIndexChanged.connect(self._display_selected_od)
        calculate_button = QPushButton("Calcular elección modal")
        calculate_button.setDefault(True)
        calculate_button.clicked.connect(self.calculate)
        restore_button = QPushButton("Restaurar parámetros")
        restore_button.clicked.connect(self._restore_defaults)
        selector_layout.addWidget(self.od_selector, 0, 0)
        selector_layout.addWidget(calculate_button, 0, 1)
        selector_layout.addWidget(restore_button, 0, 2)
        layout.addWidget(selector_group)

        results = QTabWidget()
        self.detail_table = QTableWidget(0, 6)
        self.detail_table.setHorizontalHeaderLabels(
            ("Modo", "Tiempo", "Costo", "Utilidad", "Probabilidad", "Viajes")
        )
        self.summary_table = QTableWidget(0, 3)
        self.summary_table.setHorizontalHeaderLabels(("Modo", "Viajes", "Participación"))
        self.modal_matrices_tabs = QTabWidget()
        self._stretch_headers(self.detail_table)
        self._stretch_headers(self.summary_table)
        results.addTab(self.detail_table, "Detalle O-D")
        results.addTab(self.summary_table, "Totales por modo")
        results.addTab(self.modal_matrices_tabs, "Matrices modales")
        layout.addWidget(results, stretch=1)

        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.summary)

    @staticmethod
    def _build_equations_group() -> QGroupBox:
        group = QGroupBox("Modelo aplicado")
        layout = QVBoxLayout(group)
        equations = QLabel(
            "<b>Atributos:</b> tₘᵢⱼ = tₘ⁰ + λₘcᵢⱼ; "
            "Cₘᵢⱼ = Cₘ⁰ + γₘcᵢⱼ<br>"
            "<b>Utilidad:</b> Uₘᵢⱼ = ASCₘ + β<sub>t</sub>tₘᵢⱼ + "
            "β<sub>c</sub>Cₘᵢⱼ<br>"
            "<b>Probabilidad:</b> Pₘᵢⱼ = exp(Uₘᵢⱼ) / Σₖexp(Uₖᵢⱼ); "
            "Tₘᵢⱼ = TᵢⱼPₘᵢⱼ"
        )
        equations.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(equations)
        return group

    def _build_coefficients_group(self) -> QGroupBox:
        group = QGroupBox("Coeficientes genéricos de utilidad")
        layout = QGridLayout(group)
        self.time_coefficient_input = self._coefficient_input(-0.08)
        self.cost_coefficient_input = self._coefficient_input(-0.18)
        layout.addWidget(QLabel("βt (tiempo)"), 0, 0)
        layout.addWidget(self.time_coefficient_input, 1, 0)
        layout.addWidget(QLabel("βc (costo)"), 0, 1)
        layout.addWidget(self.cost_coefficient_input, 1, 1)
        return group

    @staticmethod
    def _coefficient_input(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-100.0, 0.0)
        spin.setDecimals(4)
        spin.setSingleStep(0.01)
        spin.setValue(value)
        return spin

    def set_from_distribution(self, distribution_result: object) -> None:
        """Recibe la matriz OD y las impedancias calculadas en la etapa 2."""

        self._zone_names = distribution_result.zone_names
        self._trip_matrix = distribution_result.trip_matrix
        self._impedance_matrix = distribution_result.impedance_matrix
        self._populate_od_selector()
        self.calculate()

    def calculate(self) -> None:
        try:
            modes = self._read_modes()
            result = choose_modes(
                self._zone_names,
                self._trip_matrix,
                self._impedance_matrix,
                modes,
                self.time_coefficient_input.value(),
                self.cost_coefficient_input.value(),
            )
        except (ModeChoiceError, ValueError, AttributeError) as error:
            QMessageBox.warning(self, "Datos no válidos", str(error))
            return

        self.current_result = result
        self._fill_summary(result)
        self._fill_modal_matrices(result)
        self._display_selected_od()
        self.summary.setText(
            f"<b>Comprobación:</b> {result.total_trips:,.2f} viajes distribuidos; "
            f"Σ de participaciones = {sum(mode.share for mode in result.mode_summaries):.6f}."
        )
        self.result_calculated.emit(result)

    def _restore_defaults(self) -> None:
        self.time_coefficient_input.setValue(-0.08)
        self.cost_coefficient_input.setValue(-0.18)
        self.modes_table.setRowCount(len(DEFAULT_MODES))
        for row, mode in enumerate(DEFAULT_MODES):
            values = (
                mode.name,
                mode.alternative_constant,
                mode.time_multiplier,
                mode.time_constant,
                mode.fixed_cost,
                mode.variable_cost,
            )
            for column, value in enumerate(values):
                self.modes_table.setItem(row, column, QTableWidgetItem(str(value)))
        self._populate_od_selector()
        self.calculate()

    def _populate_od_selector(self) -> None:
        previous = self.od_selector.currentIndex()
        self.od_selector.blockSignals(True)
        self.od_selector.clear()
        for origin in self._zone_names:
            for destination in self._zone_names:
                self.od_selector.addItem(f"{origin} → {destination}")
        self.od_selector.setCurrentIndex(max(0, min(previous, self.od_selector.count() - 1)))
        self.od_selector.blockSignals(False)

    def _read_modes(self) -> tuple[ModeSpecification, ...]:
        modes: list[ModeSpecification] = []
        for row in range(self.modes_table.rowCount()):
            name_item = self.modes_table.item(row, 0)
            name = name_item.text().strip() if name_item else ""
            modes.append(
                ModeSpecification(
                    name=name,
                    alternative_constant=self._read_number(row, 1),
                    time_multiplier=self._read_number(row, 2),
                    time_constant=self._read_number(row, 3),
                    fixed_cost=self._read_number(row, 4),
                    variable_cost=self._read_number(row, 5),
                )
            )
        return tuple(modes)

    def _read_number(self, row: int, column: int) -> float:
        item = self.modes_table.item(row, column)
        if item is None or not item.text().strip():
            raise ValueError(f"Falta un valor en la fila {row + 1}, columna {column + 1}.")
        try:
            return float(item.text().strip().replace(",", "."))
        except ValueError as error:
            raise ValueError(
                f"El valor de la fila {row + 1}, columna {column + 1} no es numérico."
            ) from error

    def _display_selected_od(self) -> None:
        if self.current_result is None or self.od_selector.currentIndex() < 0:
            return
        size = len(self._zone_names)
        index = self.od_selector.currentIndex()
        origin, destination = divmod(index, size)
        od_result = self.current_result.od_results[origin][destination]
        self.detail_table.setRowCount(len(od_result.alternatives))
        for row, alternative in enumerate(od_result.alternatives):
            values = (
                alternative.mode_name,
                f"{alternative.travel_time:.2f}",
                f"{alternative.monetary_cost:.2f}",
                f"{alternative.utility:.4f}",
                f"{alternative.probability:.4f}",
                f"{alternative.trips:.2f}",
            )
            for column, value in enumerate(values):
                self._set_result_item(self.detail_table, row, column, value)

    def _fill_summary(self, result: ModeChoiceResult) -> None:
        self.summary_table.setRowCount(len(result.mode_summaries) + 1)
        for row, mode in enumerate(result.mode_summaries):
            values = (mode.mode_name, f"{mode.total_trips:.2f}", f"{mode.share:.2%}")
            for column, value in enumerate(values):
                self._set_result_item(self.summary_table, row, column, value)
        total_row = len(result.mode_summaries)
        for column, value in enumerate(("Total", f"{result.total_trips:.2f}", "100.00%")):
            self._set_result_item(self.summary_table, total_row, column, value)

    def _fill_modal_matrices(self, result: ModeChoiceResult) -> None:
        self.modal_matrices_tabs.clear()
        self._modal_matrix_tables.clear()
        for mode in result.mode_summaries:
            table = QTableWidget()
            self._fill_matrix(table, mode.trip_matrix, result.zone_names)
            self._modal_matrix_tables.append(table)
            self.modal_matrices_tabs.addTab(table, mode.mode_name)

    def _fill_matrix(
        self,
        table: QTableWidget,
        matrix: tuple[tuple[float, ...], ...],
        names: tuple[str, ...],
    ) -> None:
        size = len(matrix)
        table.setRowCount(size)
        table.setColumnCount(size)
        table.setHorizontalHeaderLabels(names)
        table.setVerticalHeaderLabels(names)
        self._stretch_headers(table)
        for row, values in enumerate(matrix):
            for column, value in enumerate(values):
                self._set_result_item(table, row, column, f"{value:.2f}")

    @staticmethod
    def _set_result_item(
        table: QTableWidget,
        row: int,
        column: int,
        text: str,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        item.setBackground(QColor("#e8f0fe"))
        table.setItem(row, column, item)

    @staticmethod
    def _stretch_headers(table: QTableWidget) -> None:
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

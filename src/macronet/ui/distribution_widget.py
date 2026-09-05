"""Interfaz educativa del modelo gravitacional de distribución."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from macronet.domain.distribution import DistributionError, distribute_trips

EXAMPLE_NAMES = ("Centro", "Norte", "Sur", "Oriente")
EXAMPLE_PRODUCTIONS = (260.0, 320.0, 290.0, 330.0)
EXAMPLE_ATTRACTIONS = (400.0, 280.0, 248.0, 272.0)
EXAMPLE_COSTS = (
    (3.0, 10.0, 15.0, 20.0),
    (10.0, 3.0, 12.0, 18.0),
    (15.0, 12.0, 3.0, 9.0),
    (20.0, 18.0, 9.0, 3.0),
)


class DistributionWidget(QWidget):
    """Muestra cada insumo y resultado del balanceo gravitacional."""

    result_calculated = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.current_result = None
        self._zone_names = EXAMPLE_NAMES
        self._build_ui()
        self._set_marginals(EXAMPLE_NAMES, EXAMPLE_PRODUCTIONS, EXAMPLE_ATTRACTIONS)
        self._restore_costs()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Distribución de viajes")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        explanation = QLabel(
            "Las producciones y atracciones provienen de la etapa anterior. Modifique las "
            "impedancias o β para observar cómo cambia la matriz origen-destino."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(self._build_equations_group())
        layout.addWidget(self._build_controls_group())

        self.marginals_table = QTableWidget(0, 3)
        self.marginals_table.setHorizontalHeaderLabels(
            ("Zona", "Producciones Oᵢ", "Atracciones Dⱼ")
        )
        self._stretch_headers(self.marginals_table)
        self.marginals_table.setMaximumHeight(170)
        layout.addWidget(self.marginals_table)

        matrices = QTabWidget()
        self.cost_table = QTableWidget()
        self.friction_table = QTableWidget()
        self.trip_table = QTableWidget()
        self.history_table = QTableWidget(0, 3)
        self.history_table.setHorizontalHeaderLabels(
            ("Iteración", "Error máximo en filas", "Error máximo en columnas")
        )
        for table in (
            self.cost_table,
            self.friction_table,
            self.trip_table,
            self.history_table,
        ):
            self._stretch_headers(table)
        matrices.addTab(self.cost_table, "Impedancias cᵢⱼ")
        matrices.addTab(self.friction_table, "Fricción f(cᵢⱼ)")
        matrices.addTab(self.trip_table, "Matriz OD Tᵢⱼ")
        matrices.addTab(self.history_table, "Convergencia")
        layout.addWidget(matrices, stretch=1)

        calculate_button = QPushButton("Distribuir viajes")
        calculate_button.setDefault(True)
        calculate_button.clicked.connect(self.calculate)
        layout.addWidget(calculate_button)

        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.summary)

    @staticmethod
    def _build_equations_group() -> QGroupBox:
        group = QGroupBox("Modelo aplicado")
        layout = QVBoxLayout(group)
        equations = QLabel(
            "<b>Fricción exponencial:</b> f(cᵢⱼ) = exp(−βcᵢⱼ)<br>"
            "<b>Modelo:</b> Tᵢⱼ = aᵢOᵢ bⱼDⱼ f(cᵢⱼ)<br>"
            "<b>Restricciones:</b> ΣⱼTᵢⱼ = Oᵢ &nbsp; y &nbsp; ΣᵢTᵢⱼ = Dⱼ"
        )
        equations.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(equations)
        return group

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Parámetros numéricos")
        layout = QGridLayout(group)

        self.beta_input = QDoubleSpinBox()
        self.beta_input.setRange(0.0, 100.0)
        self.beta_input.setDecimals(4)
        self.beta_input.setSingleStep(0.01)
        self.beta_input.setValue(0.1)

        self.tolerance_input = QDoubleSpinBox()
        self.tolerance_input.setRange(0.000001, 1.0)
        self.tolerance_input.setDecimals(6)
        self.tolerance_input.setValue(0.000001)

        self.iterations_input = QSpinBox()
        self.iterations_input.setRange(1, 10_000)
        self.iterations_input.setValue(500)

        restore_button = QPushButton("Restaurar impedancias")
        restore_button.clicked.connect(self._restore_costs)

        layout.addWidget(QLabel("β"), 0, 0)
        layout.addWidget(self.beta_input, 1, 0)
        layout.addWidget(QLabel("Tolerancia"), 0, 1)
        layout.addWidget(self.tolerance_input, 1, 1)
        layout.addWidget(QLabel("Máximo de iteraciones"), 0, 2)
        layout.addWidget(self.iterations_input, 1, 2)
        layout.addWidget(restore_button, 1, 3)
        return group

    def set_from_generation(self, generation_result: object) -> None:
        """Recibe automáticamente los marginales calculados en la etapa 1."""

        zones = generation_result.zones
        names = tuple(result.zone.name for result in zones)
        productions = tuple(result.production for result in zones)
        attractions = tuple(result.attraction_balanced for result in zones)
        self._set_marginals(names, productions, attractions)
        if self.cost_table.rowCount() != len(names):
            self._set_cost_matrix(self._default_costs(len(names)))
        self.calculate()

    def calculate(self) -> None:
        try:
            names, productions, attractions = self._read_marginals()
            costs = self._read_costs()
            result = distribute_trips(
                names,
                productions,
                attractions,
                costs,
                self.beta_input.value(),
                tolerance=self.tolerance_input.value(),
                max_iterations=self.iterations_input.value(),
            )
        except (DistributionError, ValueError, AttributeError) as error:
            QMessageBox.warning(self, "Datos no válidos", str(error))
            return

        self._fill_matrix(self.friction_table, result.friction_matrix, names)
        self._fill_trip_matrix(result.trip_matrix, result.row_totals, result.column_totals, names)
        self._fill_history(result.history)
        state = "convergió" if result.converged else "no convergió"
        self.summary.setText(
            f"<b>Resultado:</b> el modelo {state} en {result.iterations} iteraciones; "
            f"error máximo final = {result.maximum_error:.3e} viajes."
        )
        self.current_result = result
        self.result_calculated.emit(result)

    def _set_marginals(
        self,
        names: tuple[str, ...],
        productions: tuple[float, ...],
        attractions: tuple[float, ...],
    ) -> None:
        self._zone_names = names
        self.marginals_table.setRowCount(len(names))
        for row, values in enumerate(zip(names, productions, attractions, strict=True)):
            for column, value in enumerate(values):
                self.marginals_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _restore_costs(self) -> None:
        if len(self._zone_names) == len(EXAMPLE_COSTS):
            costs = EXAMPLE_COSTS
        else:
            costs = self._default_costs(len(self._zone_names))
        self._set_cost_matrix(costs)
        self.calculate()

    @staticmethod
    def _default_costs(size: int) -> tuple[tuple[float, ...], ...]:
        return tuple(
            tuple(3.0 if origin == destination else 8.0 + 3.0 * abs(origin - destination)
                  for destination in range(size))
            for origin in range(size)
        )

    def _set_cost_matrix(self, costs: tuple[tuple[float, ...], ...]) -> None:
        size = len(costs)
        self.cost_table.setRowCount(size)
        self.cost_table.setColumnCount(size)
        self.cost_table.setHorizontalHeaderLabels(self._zone_names)
        self.cost_table.setVerticalHeaderLabels(self._zone_names)
        for row, values in enumerate(costs):
            for column, value in enumerate(values):
                self.cost_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _read_marginals(
        self,
    ) -> tuple[tuple[str, ...], tuple[float, ...], tuple[float, ...]]:
        names: list[str] = []
        productions: list[float] = []
        attractions: list[float] = []
        for row in range(self.marginals_table.rowCount()):
            name_item = self.marginals_table.item(row, 0)
            names.append(name_item.text().strip() if name_item else "")
            productions.append(self._read_number(self.marginals_table, row, 1))
            attractions.append(self._read_number(self.marginals_table, row, 2))
        return tuple(names), tuple(productions), tuple(attractions)

    def _read_costs(self) -> tuple[tuple[float, ...], ...]:
        return tuple(
            tuple(
                self._read_number(self.cost_table, row, column)
                for column in range(self.cost_table.columnCount())
            )
            for row in range(self.cost_table.rowCount())
        )

    @staticmethod
    def _read_number(table: QTableWidget, row: int, column: int) -> float:
        item = table.item(row, column)
        if item is None or not item.text().strip():
            raise ValueError(f"Falta un valor en la fila {row + 1}, columna {column + 1}.")
        try:
            return float(item.text().strip().replace(",", "."))
        except ValueError as error:
            raise ValueError(
                f"El valor de la fila {row + 1}, columna {column + 1} no es numérico."
            ) from error

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
        for row, values in enumerate(matrix):
            for column, value in enumerate(values):
                self._set_result_item(table, row, column, f"{value:.6f}")

    def _fill_trip_matrix(
        self,
        matrix: tuple[tuple[float, ...], ...],
        row_totals: tuple[float, ...],
        column_totals: tuple[float, ...],
        names: tuple[str, ...],
    ) -> None:
        size = len(matrix)
        self.trip_table.setRowCount(size + 1)
        self.trip_table.setColumnCount(size + 1)
        self.trip_table.setHorizontalHeaderLabels((*names, "Σ fila"))
        self.trip_table.setVerticalHeaderLabels((*names, "Σ columna"))
        for row, values in enumerate(matrix):
            for column, value in enumerate(values):
                self._set_result_item(self.trip_table, row, column, f"{value:.2f}")
            self._set_result_item(self.trip_table, row, size, f"{row_totals[row]:.2f}")
        for column, total in enumerate(column_totals):
            self._set_result_item(self.trip_table, size, column, f"{total:.2f}")
        self._set_result_item(self.trip_table, size, size, f"{sum(row_totals):.2f}")

    def _fill_history(self, history: tuple[object, ...]) -> None:
        self.history_table.setRowCount(len(history))
        for row, iteration in enumerate(history):
            values = (
                str(iteration.number),
                f"{iteration.maximum_row_error:.6e}",
                f"{iteration.maximum_column_error:.6e}",
            )
            for column, value in enumerate(values):
                self._set_result_item(self.history_table, row, column, value)

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

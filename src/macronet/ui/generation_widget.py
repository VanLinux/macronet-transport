"""Interfaz interactiva del módulo de generación y atracción."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from macronet.domain.generation import (
    GenerationCoefficients,
    GenerationError,
    ZoneInput,
    calculate_generation,
)

EXAMPLE_ZONES = (
    ("Centro", 100, 60, 200, 100),
    ("Norte", 120, 80, 100, 150),
    ("Sur", 110, 70, 80, 150),
    ("Oriente", 120, 90, 120, 100),
)


class GenerationWidget(QWidget):
    """Permite modificar y observar el cálculo de la primera etapa."""

    result_calculated = Signal(object)

    INPUT_COLUMN_COUNT = 5
    HEADERS = (
        "Zona",
        "Hogares Hᵢ",
        "Vehículos Vᵢ",
        "Empleos Eᵢ",
        "Estudiantes Sᵢ",
        "Producción Pᵢ",
        "Atracción Aᵢ",
        "Atracción balanceada",
    )

    def __init__(self) -> None:
        super().__init__()
        self.current_result = None
        self._coefficient_inputs: dict[str, QDoubleSpinBox] = {}
        self._build_ui()
        self._load_example()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Generación y atracción de viajes")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        explanation = QLabel(
            "Esta etapa estima los viajes producidos y atraídos por cada zona mediante "
            "regresiones lineales. Modifique los datos o coeficientes y pulse Calcular; "
            "las atracciones se balancean para igualar el total de producciones. "
            "Cambie los nombres de zona aquí y pulse Calcular para actualizarlos en "
            "las demás pestañas."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        layout.addWidget(self._build_equations_group())
        layout.addWidget(self._build_coefficients_group())

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, stretch=1)

        buttons = QHBoxLayout()
        calculate_button = QPushButton("Calcular")
        calculate_button.setDefault(True)
        calculate_button.clicked.connect(self.calculate)
        buttons.addWidget(calculate_button)

        restore_button = QPushButton("Restaurar caso didáctico")
        restore_button.clicked.connect(self._load_example)
        buttons.addWidget(restore_button)

        buttons.addStretch()
        layout.addLayout(buttons)

        self.summary = QLabel()
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(self.summary)

    @staticmethod
    def _build_equations_group() -> QGroupBox:
        group = QGroupBox("Ecuaciones aplicadas")
        layout = QVBoxLayout(group)
        equations = QLabel(
            "<b>Producción:</b> Pᵢ = β₀ + β<sub>H</sub>Hᵢ + β<sub>V</sub>Vᵢ<br>"
            "<b>Atracción:</b> Aᵢ = α₀ + α<sub>E</sub>Eᵢ + α<sub>S</sub>Sᵢ<br>"
            "<b>Balanceo:</b> Aᵢ* = F·Aᵢ, &nbsp; F = ΣPᵢ / ΣAᵢ"
        )
        equations.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(equations)
        return group

    def _build_coefficients_group(self) -> QGroupBox:
        group = QGroupBox("Coeficientes editables")
        layout = QGridLayout(group)
        specifications = (
            ("production_intercept", "β₀", 0.0),
            ("production_households", "βH (hogares)", 2.0),
            ("production_vehicles", "βV (vehículos)", 1.0),
            ("attraction_intercept", "α₀", 0.0),
            ("attraction_jobs", "αE (empleos)", 2.0),
            ("attraction_students", "αS (estudiantes)", 1.0),
        )
        for index, (name, label, value) in enumerate(specifications):
            row, column = divmod(index, 3)
            spin = self._create_coefficient_input(value)
            self._coefficient_inputs[name] = spin
            layout.addWidget(QLabel(label), row * 2, column)
            layout.addWidget(spin, row * 2 + 1, column)
        return group

    @staticmethod
    def _create_coefficient_input(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1_000_000, 1_000_000)
        spin.setDecimals(4)
        spin.setValue(value)
        return spin

    def _load_example(self) -> None:
        defaults = GenerationCoefficients()
        for name, spin in self._coefficient_inputs.items():
            spin.setValue(getattr(defaults, name))

        self.table.setRowCount(len(EXAMPLE_ZONES))
        for row, values in enumerate(EXAMPLE_ZONES):
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
            for column in range(self.INPUT_COLUMN_COUNT, len(self.HEADERS)):
                self._set_result_item(row, column, "—")
        self.calculate()

    def calculate(self) -> None:
        try:
            zones = [self._read_zone(row) for row in range(self.table.rowCount())]
            coefficients = GenerationCoefficients(
                **{name: spin.value() for name, spin in self._coefficient_inputs.items()}
            )
            result = calculate_generation(zones, coefficients)
        except (GenerationError, ValueError) as error:
            QMessageBox.warning(self, "Datos no válidos", str(error))
            return

        for row, zone_result in enumerate(result.zones):
            self._set_result_item(row, 5, f"{zone_result.production:,.2f}")
            self._set_result_item(row, 6, f"{zone_result.attraction_raw:,.2f}")
            self._set_result_item(row, 7, f"{zone_result.attraction_balanced:,.2f}")

        self.summary.setText(
            f"<b>Comprobación:</b> ΣP = {result.total_productions:,.2f} viajes; "
            f"ΣA = {result.total_attractions_raw:,.2f} viajes; "
            f"F = {result.balance_factor:.4f}; "
            f"ΣA* = {result.total_attractions_balanced:,.2f} viajes."
        )
        self.current_result = result
        self.result_calculated.emit(result)

    def _read_zone(self, row: int) -> ZoneInput:
        name_item = self.table.item(row, 0)
        name = name_item.text().strip() if name_item else ""
        return ZoneInput(
            name=name,
            households=self._read_number(row, 1),
            vehicles=self._read_number(row, 2),
            jobs=self._read_number(row, 3),
            students=self._read_number(row, 4),
        )

    def _read_number(self, row: int, column: int) -> float:
        item = self.table.item(row, column)
        if item is None or not item.text().strip():
            raise ValueError(f"Falta un valor en la fila {row + 1}, columna {column + 1}.")
        try:
            return float(item.text().strip().replace(",", "."))
        except ValueError as error:
            raise ValueError(
                f"El valor de la fila {row + 1}, columna {column + 1} no es numérico."
            ) from error

    def _set_result_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, column, item)

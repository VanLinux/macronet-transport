"""Captura y restaura entradas de las cuatro etapas sin mezclar borradores y resultados."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from macronet.project import STAGES, project_document


def table_values(table: QTableWidget, columns: int | None = None) -> list[list[str]]:
    return [
        [
            table.item(row, column).text() if table.item(row, column) else ""
            for column in range(columns or table.columnCount())
        ]
        for row in range(table.rowCount())
    ]


def fill_table(table: QTableWidget, values: list[list[str]], readonly: tuple[int, ...] = ()):
    table.setRowCount(len(values))
    for row, cells in enumerate(values):
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            if column in readonly:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, column, item)


def _matrix(values):
    return [list(row) for row in values]


def capture_inputs(stage: str, widget) -> dict:
    if stage == "generation":
        return {
            "table": table_values(widget.table, 5),
            "coefficients": {
                name: spin.value() for name, spin in widget._coefficient_inputs.items()
            },
        }
    if stage == "distribution":
        return {
            "marginals": table_values(widget.marginals_table),
            "costs": table_values(widget.cost_table),
            "beta": widget.beta_input.value(),
            "tolerance": widget.tolerance_input.value(),
            "iterations": widget.iterations_input.value(),
        }
    if stage == "modal":
        return {
            "modes": table_values(widget.modes_table),
            "time_coefficient": widget.time_coefficient_input.value(),
            "cost_coefficient": widget.cost_coefficient_input.value(),
            "zone_names": list(widget._zone_names),
            "trip_matrix": _matrix(widget._trip_matrix),
            "impedance_matrix": _matrix(widget._impedance_matrix),
        }
    return {
        "centroids": table_values(widget.zone_nodes_table),
        "links": table_values(widget.links_table),
        "zone_names": list(widget._zone_names),
        "demand_matrix": _matrix(widget._demand_matrix),
        "mode_name": widget._mode_name,
        "mode_index": widget.mode_selector.currentIndex(),
    }


def restore_inputs(stage: str, widget, state: dict) -> None:
    if stage == "generation":
        fill_table(widget.table, state["table"])
        for name, value in state["coefficients"].items():
            widget._coefficient_inputs[name].setValue(value)
    elif stage == "distribution":
        widget._zone_names = tuple(row[0] for row in state["marginals"])
        fill_table(widget.marginals_table, state["marginals"], (0,))
        widget.cost_table.setColumnCount(len(state["costs"]))
        fill_table(widget.cost_table, state["costs"])
        widget.cost_table.setHorizontalHeaderLabels(widget._zone_names)
        widget.cost_table.setVerticalHeaderLabels(widget._zone_names)
        widget.beta_input.setValue(state["beta"])
        widget.tolerance_input.setValue(state["tolerance"])
        widget.iterations_input.setValue(state["iterations"])
    elif stage == "modal":
        fill_table(widget.modes_table, state["modes"])
        widget._zone_names = tuple(state["zone_names"])
        widget._trip_matrix = tuple(tuple(row) for row in state["trip_matrix"])
        widget._impedance_matrix = tuple(tuple(row) for row in state["impedance_matrix"])
        widget.time_coefficient_input.setValue(state["time_coefficient"])
        widget.cost_coefficient_input.setValue(state["cost_coefficient"])
        widget._populate_od_selector()
    else:
        fill_table(widget.zone_nodes_table, state["centroids"], (0,))
        fill_table(widget.links_table, state["links"])
        widget._zone_names = tuple(state["zone_names"])
        widget._demand_matrix = tuple(tuple(row) for row in state["demand_matrix"])
        widget._mode_name = state["mode_name"]
        widget.mode_selector.blockSignals(True)
        widget.mode_selector.setCurrentIndex(state["mode_index"])
        widget.mode_selector.blockSignals(False)


def capture_document(tabs) -> dict:
    return project_document(
        {stage: capture_inputs(stage, widget) for stage, widget in tabs.stages.items()},
        tabs.calculated_states,
        tabs.widget(5).analyst_name,
        tabs.currentIndex(),
        tabs.widget(3).od_selector.currentIndex(),
    )


def restore_document(tabs, document: dict) -> None:
    """Recalcula instantáneas válidas y conserva las celdas todavía en edición."""

    for stage in STAGES:
        widget = tabs.stages[stage]
        if stage == "assignment":
            widget._mode_choice_result = tabs.widget(3).current_result
            widget.mode_selector.blockSignals(True)
            widget.mode_selector.clear()
            widget.mode_selector.addItems(
                [mode.mode_name for mode in widget._mode_choice_result.mode_summaries]
            )
            widget.mode_selector.blockSignals(False)
        widget.blockSignals(True)
        try:
            restore_inputs(stage, widget, document["calculated"][stage])
            widget.calculate(raise_errors=True)
        finally:
            widget.blockSignals(False)
    summary = tabs.widget(5)
    summary.set_from_generation(tabs.widget(1).current_result)
    summary.set_from_distribution(tabs.widget(2).current_result)
    summary.set_from_mode_choice(tabs.widget(3).current_result)
    summary.set_from_assignment(tabs.widget(4).current_result, tabs.widget(4).assigned_mode_name)
    summary.analyst_name = document["analyst_name"]
    for stage, widget in tabs.stages.items():
        restore_inputs(stage, widget, document["draft"][stage])
    tabs.calculated_states = document["calculated"]
    tabs.widget(3).od_selector.setCurrentIndex(
        min(document["view"]["od"], tabs.widget(3).od_selector.count() - 1)
    )
    tabs.setCurrentIndex(document["view"]["tab"])

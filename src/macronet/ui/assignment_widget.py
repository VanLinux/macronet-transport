"""Interfaz educativa de asignación Todo-o-Nada."""

from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
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

from macronet.domain.assignment import (
    AssignmentError,
    AssignmentResult,
    Link,
    assign_all_or_nothing,
)
from macronet.exporters import save_assignment_graphml

EXAMPLE_NAMES = ("Centro", "Norte", "Sur", "Oriente")
EXAMPLE_AUTO_DEMAND = (
    (67.4361560353, 21.1501975770, 10.2298692064, 7.1938280208),
    (46.9936845089, 54.6009480904, 18.4082163313, 11.8041455673),
    (27.9951097421, 22.6724647044, 41.6555377182, 27.6174896070),
    (22.6509294563, 16.7276704810, 31.7759162685, 64.4682932079),
)


class NetworkCanvas(FigureCanvasQTAgg):
    """Representa la red y escala cada arco según su flujo."""

    def __init__(self, figsize: tuple[float, float] = (7, 5)) -> None:
        self.figure = Figure(figsize=figsize)
        super().__init__(self.figure)

    def update_network(self, result: AssignmentResult) -> None:
        self.figure.clear()
        axes = self.figure.subplots()
        nodes = sorted(
            {item.link.tail for item in result.link_results}
            | {item.link.head for item in result.link_results}
        )
        positions = {
            node: (
                cos(2 * pi * index / len(nodes)),
                sin(2 * pi * index / len(nodes)),
            )
            for index, node in enumerate(nodes)
        }
        maximum_volume = max((item.volume for item in result.link_results), default=1.0)
        if maximum_volume == 0:
            maximum_volume = 1.0

        for item in result.link_results:
            start = positions[item.link.tail]
            end = positions[item.link.head]
            curvature = 0.13 if item.link.tail < item.link.head else -0.13
            arrow = FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                connectionstyle=f"arc3,rad={curvature}",
                color=self._flow_color(item.volume_capacity_ratio),
                linewidth=0.8 + 4.0 * item.volume / maximum_volume,
                mutation_scale=12,
                shrinkA=18,
                shrinkB=18,
                alpha=0.8,
            )
            axes.add_patch(arrow)

        for node, (x_coordinate, y_coordinate) in positions.items():
            axes.scatter(x_coordinate, y_coordinate, s=850, color="#e8f0fe", edgecolor="#174ea6")
            axes.text(x_coordinate, y_coordinate, node, ha="center", va="center", fontsize=9)

        axes.set_title("Azul: v/c ≤ 0.8 · Naranja: 0.8 < v/c ≤ 1 · Rojo: v/c > 1")
        axes.set_aspect("equal")
        axes.axis("off")
        self.figure.tight_layout()
        self.draw_idle()

    @staticmethod
    def _flow_color(ratio: float) -> str:
        if ratio > 1.0:
            return "#c62828"
        if ratio > 0.8:
            return "#ef6c00"
        return "#1565c0"


class AssignmentWidget(QWidget):
    """Edita la red y muestra rutas, flujos y utilización."""

    result_calculated = Signal(object)

    LINK_HEADERS = ("Arco", "Desde", "Hasta", "Tiempo libre", "Capacidad")

    def __init__(self) -> None:
        super().__init__()
        self._zone_names = EXAMPLE_NAMES
        self._demand_matrix = EXAMPLE_AUTO_DEMAND
        self._mode_name = "Automóvil"
        self.current_result: AssignmentResult | None = None
        self._build_ui()
        self._set_zone_nodes(EXAMPLE_NAMES)
        self._restore_network()

    @property
    def assigned_mode_name(self) -> str:
        """Nombre del modo cuya matriz se carga en la red."""

        return self._mode_name

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Asignación Todo-o-Nada")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)

        self.explanation = QLabel(
            "Esta etapa carga la demanda modal en la red mediante asignación Todo-o-Nada "
            "y calcula las rutas mínimas con el algoritmo de Dijkstra."
        )
        self.explanation.setWordWrap(True)
        layout.addWidget(self.explanation)
        layout.addWidget(self._build_equations_group())

        self.zone_nodes_table = QTableWidget(0, 2)
        self.zone_nodes_table.setHorizontalHeaderLabels(("Zona", "Nodo centroide"))
        self._stretch_headers(self.zone_nodes_table)
        self.zone_nodes_table.setMaximumHeight(145)
        layout.addWidget(self.zone_nodes_table)

        self.links_table = QTableWidget(0, len(self.LINK_HEADERS))
        self.links_table.setHorizontalHeaderLabels(self.LINK_HEADERS)
        self._stretch_headers(self.links_table)
        self.links_table.setMaximumHeight(245)
        layout.addWidget(self.links_table)

        restore_button = QPushButton("Restaurar red didáctica")
        restore_button.clicked.connect(self._restore_network)
        assign_button = QPushButton("Asignar Todo-o-Nada")
        assign_button.setDefault(True)
        assign_button.clicked.connect(self.calculate)
        layout.addWidget(restore_button)
        layout.addWidget(assign_button)

        results = QTabWidget()
        self.paths_table = QTableWidget(0, 6)
        self.paths_table.setHorizontalHeaderLabels(
            ("Origen", "Destino", "Demanda", "Ruta de nodos", "Arcos", "Costo")
        )
        self.flows_table = QTableWidget(0, 7)
        self.flows_table.setHorizontalHeaderLabels(
            ("Arco", "Desde", "Hasta", "Tiempo", "Capacidad", "Flujo", "v/c")
        )
        network_panel = QWidget()
        network_layout = QVBoxLayout(network_panel)
        self.network_canvas = NetworkCanvas()
        network_layout.addWidget(self.network_canvas, stretch=1)
        network_actions = QHBoxLayout()
        self.enlarge_graph_button = QPushButton("Ver grafo en grande")
        self.enlarge_graph_button.setEnabled(False)
        self.enlarge_graph_button.clicked.connect(self._show_network_large)
        network_actions.addWidget(self.enlarge_graph_button)
        self.export_graph_button = QPushButton("Descargar grafo (.graphml)")
        self.export_graph_button.setEnabled(False)
        self.export_graph_button.clicked.connect(self._export_graphml)
        network_actions.addWidget(self.export_graph_button)
        network_actions.addStretch()
        network_layout.addLayout(network_actions)
        self._stretch_headers(self.paths_table)
        self._stretch_headers(self.flows_table)
        results.addTab(self.paths_table, "Rutas mínimas")
        results.addTab(self.flows_table, "Flujos por arco")
        results.addTab(network_panel, "Red y flujos")
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
            "<b>Ruta mínima:</b> r*ᵢⱼ = arg minᵣ Σₐ∈ᵣ tₐ⁰<br>"
            "<b>Flujo del arco:</b> xₐ = ΣᵢΣⱼ qᵢⱼδₐ,ᵣ*ᵢⱼ<br>"
            "<b>Diagnóstico:</b> utilización = xₐ / capacidadₐ"
        )
        equations.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(equations)
        return group

    def set_from_mode_choice(self, mode_choice_result: object) -> None:
        """Recibe la matriz de automóvil producida en la etapa 3."""

        summaries = mode_choice_result.mode_summaries
        selected = next(
            (mode for mode in summaries if "autom" in mode.mode_name.casefold()),
            summaries[0],
        )
        new_names = mode_choice_result.zone_names
        old_names = self._zone_names
        self._zone_names = new_names
        self._demand_matrix = selected.trip_matrix
        self._mode_name = selected.mode_name
        if len(new_names) != len(old_names):
            self._set_zone_nodes(new_names)
            self._set_links(self._default_links(new_names))
        else:
            # Renaming a zone must not restore the user's network or centroid mapping.
            renames = dict(zip(old_names, new_names, strict=True))
            for row, name in enumerate(new_names):
                self.zone_nodes_table.item(row, 0).setText(name)
                node_item = self.zone_nodes_table.item(row, 1)
                node_item.setText(renames.get(node_item.text(), node_item.text()))
            for row in range(self.links_table.rowCount()):
                for column in (1, 2):
                    item = self.links_table.item(row, column)
                    item.setText(renames.get(item.text(), item.text()))
        self.calculate()

    def calculate(self) -> None:
        try:
            zone_nodes = self._read_zone_nodes()
            links = self._read_links()
            result = assign_all_or_nothing(
                self._zone_names,
                zone_nodes,
                self._demand_matrix,
                links,
            )
        except (AssignmentError, ValueError, AttributeError) as error:
            QMessageBox.warning(self, "Datos no válidos", str(error))
            return

        self.explanation.setText(
            f"Se asigna la matriz modal de {self._mode_name} mediante Todo-o-Nada y rutas "
            "mínimas de Dijkstra. La capacidad no modifica las rutas; se utiliza únicamente "
            "para calcular v/c."
        )
        self._fill_paths(result)
        self._fill_flows(result)
        self.network_canvas.update_network(result)
        self.current_result = result
        self.enlarge_graph_button.setEnabled(True)
        self.export_graph_button.setEnabled(True)
        maximum_ratio = max(item.volume_capacity_ratio for item in result.link_results)
        self.summary.setText(
            f"<b>Comprobación:</b> demanda total = {result.total_demand:.2f}; "
            f"interzonal asignada = {result.assigned_demand:.2f}; "
            f"intrazonal = {result.intrazonal_demand:.2f}; "
            f"máximo v/c = {maximum_ratio:.3f}."
        )
        self.result_calculated.emit(result)

    def _show_network_large(self) -> None:
        if self.current_result is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Red y flujos — vista ampliada")
        dialog.resize(1100, 800)
        layout = QVBoxLayout(dialog)
        canvas = NetworkCanvas(figsize=(11, 8))
        canvas.update_network(self.current_result)
        layout.addWidget(canvas)
        dialog.exec()

    def _export_graphml(self) -> None:
        if self.current_result is None:
            QMessageBox.information(
                self,
                "Sin resultados",
                "Primero debe ejecutar la asignación.",
            )
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar red asignada",
            "red_asignada.graphml",
            "GraphML (*.graphml)",
        )
        if not filename:
            return
        path = Path(filename)
        if path.suffix.casefold() != ".graphml":
            path = path.with_suffix(".graphml")
        try:
            save_assignment_graphml(
                path,
                self.current_result,
                self._read_zone_nodes(),
                self._mode_name,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "No se pudo guardar", str(error))
            return
        QMessageBox.information(self, "Exportación terminada", f"Grafo guardado en:\n{path}")

    def _restore_network(self) -> None:
        self._set_links(self._default_links(self._zone_names))
        self.calculate()

    @staticmethod
    def _default_links(names: tuple[str, ...]) -> tuple[Link, ...]:
        if len(names) < 2:
            return ()
        if len(names) == 4:
            specifications = (
                (0, 1, 6.0, 50.0),
                (0, 2, 9.0, 40.0),
                (0, 3, 16.0, 30.0),
                (1, 2, 5.0, 40.0),
                (1, 3, 10.0, 30.0),
                (2, 3, 4.0, 45.0),
            )
        else:
            specifications = tuple(
                (index, (index + 1) % len(names), 6.0, 180.0)
                for index in range(len(names))
            )
        links: list[Link] = []
        for first, second, travel_time, capacity in specifications:
            links.append(
                Link(f"L{first}{second}", names[first], names[second], travel_time, capacity)
            )
            links.append(
                Link(f"L{second}{first}", names[second], names[first], travel_time, capacity)
            )
        return tuple(links)

    def _set_zone_nodes(self, names: tuple[str, ...]) -> None:
        self.zone_nodes_table.setRowCount(len(names))
        for row, name in enumerate(names):
            zone_item = QTableWidgetItem(name)
            zone_item.setFlags(zone_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.zone_nodes_table.setItem(row, 0, zone_item)
            self.zone_nodes_table.setItem(row, 1, QTableWidgetItem(name))

    def _set_links(self, links: tuple[Link, ...]) -> None:
        self.links_table.setRowCount(len(links))
        for row, link in enumerate(links):
            values = (
                link.link_id,
                link.tail,
                link.head,
                link.free_flow_time,
                link.capacity,
            )
            for column, value in enumerate(values):
                self.links_table.setItem(row, column, QTableWidgetItem(str(value)))

    def _read_zone_nodes(self) -> tuple[str, ...]:
        return tuple(
            self.zone_nodes_table.item(row, 1).text().strip()
            for row in range(self.zone_nodes_table.rowCount())
        )

    def _read_links(self) -> tuple[Link, ...]:
        links: list[Link] = []
        for row in range(self.links_table.rowCount()):
            links.append(
                Link(
                    link_id=self._read_text(row, 0),
                    tail=self._read_text(row, 1),
                    head=self._read_text(row, 2),
                    free_flow_time=self._read_number(row, 3),
                    capacity=self._read_number(row, 4),
                )
            )
        return tuple(links)

    def _read_text(self, row: int, column: int) -> str:
        item = self.links_table.item(row, column)
        if item is None or not item.text().strip():
            raise ValueError(f"Falta un texto en la fila {row + 1}, columna {column + 1}.")
        return item.text().strip()

    def _read_number(self, row: int, column: int) -> float:
        text = self._read_text(row, column)
        try:
            return float(text.replace(",", "."))
        except ValueError as error:
            raise ValueError(
                f"El valor de la fila {row + 1}, columna {column + 1} no es numérico."
            ) from error

    def _fill_paths(self, result: AssignmentResult) -> None:
        self.paths_table.setRowCount(len(result.paths))
        for row, path in enumerate(result.paths):
            values = (
                path.origin,
                path.destination,
                f"{path.demand:.2f}",
                " → ".join(path.nodes),
                ", ".join(path.link_ids) if path.link_ids else "Intrazonal",
                f"{path.cost:.2f}",
            )
            for column, value in enumerate(values):
                self._set_result_item(self.paths_table, row, column, value)

    def _fill_flows(self, result: AssignmentResult) -> None:
        self.flows_table.setRowCount(len(result.link_results))
        for row, item in enumerate(result.link_results):
            values = (
                item.link.link_id,
                item.link.tail,
                item.link.head,
                f"{item.link.free_flow_time:.2f}",
                f"{item.link.capacity:.2f}",
                f"{item.volume:.2f}",
                f"{item.volume_capacity_ratio:.3f}",
            )
            for column, value in enumerate(values):
                self._set_result_item(self.flows_table, row, column, value)

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
        table.setItem(row, column, item)

    @staticmethod
    def _stretch_headers(table: QTableWidget) -> None:
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

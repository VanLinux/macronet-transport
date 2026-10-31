"""Microsimulación posasignación: el motor siempre trabaja fuera del hilo gráfico."""

from __future__ import annotations

import copy
from dataclasses import asdict
from pathlib import Path
from threading import Event

from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from macronet.sumo.runner import detect_tools, run_scenario
from macronet.sumo.scenario import Node, Road, Settings, SumoCancelled, defaults
from macronet.ui.appearance import AdaptiveCanvas


class SumoTask(QThread):
    progress = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.cancel_event = Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            result = self.operation(self.cancel_event, self.progress.emit)
        except SumoCancelled as error:
            self.cancelled.emit(str(error))
        except Exception as error:
            self.failed.emit(str(error))
        else:
            self.succeeded.emit(result)


def _values(table):
    return [
        [table.item(i, j).text() if table.item(i, j) else "" for j in range(table.columnCount())]
        for i in range(table.rowCount())
    ]


def _fill(table, rows, readonly=()):
    table.blockSignals(True)
    try:
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                item = QTableWidgetItem(str(value))
                if j in readonly:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
    finally:
        table.blockSignals(False)


def _float(text):
    return float(text.strip().replace(",", "."))


class MicrosimulationWidget(QWidget):
    changed = Signal()
    running_changed = Signal(bool)

    def __init__(self, source_provider, parent=None):
        super().__init__(parent)
        self.source_provider = source_provider
        self.task = None
        self.last_run = None
        self.stale = False
        self._restoring = True
        self._build_ui()
        self._restoring = False

    @property
    def is_running(self):
        return self.task is not None

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Microsimulación y evaluación · SUMO")
        title.setStyleSheet("font-size: 24px; font-weight: 600;")
        layout.addWidget(title)
        explanation = QLabel(
            "Módulo opcional posterior a las cuatro etapas. Usa la OD del modo asignado y "
            "una geometría vial adicional. SUMO simula automóviles; no representa pasajeros "
            "de autobús ni peatones como vehículos. Las coordenadas iniciales son esquemáticas. "
            "Revise longitudes, velocidades y carriles con datos del escenario. Los cruces son "
            "prioritarios y sus conexiones se generan automáticamente, sin semáforos."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        motor = QGroupBox("Motor opcional")
        motor_layout = QHBoxLayout(motor)
        self.bin_directory = QLineEdit()
        self.bin_directory.setPlaceholderText("Carpeta bin de SUMO (vacío = detección automática)")
        self.bin_directory.setToolTip(
            "Detección automática: SUMO incluido, entorno Python, SUMO_HOME/bin y PATH."
        )
        motor_layout.addWidget(self.bin_directory, 1)
        self.choose_bin = QPushButton("Buscar carpeta…")
        self.choose_bin.clicked.connect(self._choose_bin)
        motor_layout.addWidget(self.choose_bin)
        self.check_button = QPushButton("Comprobar SUMO")
        self.check_button.clicked.connect(self.check_tools)
        motor_layout.addWidget(self.check_button)
        layout.addWidget(motor)
        form = QGroupBox("Demanda vehicular y periodo de análisis")
        grid = QGridLayout(form)
        self.period_s = QSpinBox()
        self.period_s.setRange(10, 86400)
        self.period_s.setValue(3600)
        self.clearance_s = QSpinBox()
        self.clearance_s.setRange(0, 86400)
        self.clearance_s.setValue(1800)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(42)
        self.timeout_s = QSpinBox()
        self.timeout_s.setRange(5, 3600)
        self.timeout_s.setValue(300)
        self.demand_unit = QComboBox()
        self.demand_unit.addItem("Viajes-persona por periodo", "persons")
        self.demand_unit.addItem("Vehículos por periodo", "vehicles")
        self.occupancy = QDoubleSpinBox()
        self.occupancy.setRange(1, 100)
        self.occupancy.setDecimals(3)
        self.occupancy.setValue(1.3)
        self.multiplier = QDoubleSpinBox()
        self.multiplier.setRange(0.001, 100)
        self.multiplier.setDecimals(3)
        self.multiplier.setValue(1)
        self.departures = QComboBox()
        self.departures.addItem("Uniformes globales · OD mezcladas", "uniform")
        self.departures.addItem("Aleatorias con semilla", "random")
        for i, (label, field) in enumerate(
            (
                ("Periodo de demanda y capacidad BPR (s)", self.period_s),
                ("Despeje posterior sin nueva demanda (s)", self.clearance_s),
                ("Semilla", self.seed),
                ("Límite de tiempo real (s)", self.timeout_s),
                ("Unidades de la OD del modo asignado", self.demand_unit),
                ("Ocupación (personas/vehículo)", self.occupancy),
                ("Multiplicador de demanda del escenario", self.multiplier),
                ("Distribución temporal de salidas", self.departures),
            )
        ):
            row, column = divmod(i, 2)
            grid.addWidget(QLabel(label), 2 * row, column)
            grid.addWidget(field, 2 * row + 1, column)
        layout.addWidget(form)
        self.source_label = QLabel("Actualice la geometría desde la asignación.")
        self.source_label.setWordWrap(True)
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.source_label)
        self.sync_button = QPushButton("Actualizar geometría desde la asignación")
        self.sync_button.clicked.connect(self.sync_geometry)
        layout.addWidget(self.sync_button)
        self.geometry = QTabWidget()
        self.nodes_table = QTableWidget(0, 3)
        self.nodes_table.setHorizontalHeaderLabels(("Nodo", "X (m)", "Y (m)"))
        self.roads_table = QTableWidget(0, 6)
        self.roads_table.setHorizontalHeaderLabels(
            ("Arco", "Desde", "Hasta", "Longitud (m)", "Velocidad (km/h)", "Carriles")
        )
        self.nodes_table.setMinimumHeight(180)
        self.roads_table.setMinimumHeight(220)
        self.geometry.addTab(self.nodes_table, "Nodos y coordenadas")
        self.geometry.addTab(self.roads_table, "Arcos y geometría")
        layout.addWidget(self.geometry)
        note = QLabel(
            "Conversión: vehículos = OD × multiplicador / ocupación (solo si son personas). "
            "Se excluyen viajes dentro del mismo centroide y se aplica resto mayor al resto. "
            "La referencia AON/UE se recalcula con la misma OD vehicular redondeada y "
            "t⁰ = longitud / velocidad. La capacidad BPR se conserva por periodo; "
            "no determina automáticamente la capacidad microscópica ni los carriles. "
            "Las rutas SUMO usan una pasada con esos costos estáticos; no es DUE ni "
            "reproduce la distribución de rutas del UE estático. Calentamiento: 0 s."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.confirmed = QCheckBox(
            "Confirmo que el modo es vial y que revisé unidades, periodo, capacidad y geometría"
        )
        layout.addWidget(self.confirmed)
        actions = QHBoxLayout()
        self.export_button = QPushButton("Exportar escenario sin ejecutar…")
        self.export_button.clicked.connect(lambda: self._choose_output(False))
        self.run_button = QPushButton("Ejecutar SUMO…")
        self.run_button.clicked.connect(lambda: self._choose_output(True))
        self.cancel_button = QPushButton("Cancelar ejecución")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        self.folder_button = QPushButton("Abrir carpeta de la última ejecución")
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self._open_folder)
        for button in (self.export_button, self.run_button, self.cancel_button, self.folder_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel(
            "Motor opcional: las cuatro etapas funcionan aunque SUMO no esté instalado."
        )
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.metrics = QLabel("Sin ejecuciones.")
        self.metrics.setTextFormat(Qt.TextFormat.PlainText)
        self.metrics.setWordWrap(True)
        layout.addWidget(self.metrics)
        results = QTabWidget()
        self.comparison = QTableWidget(0, 6)
        self.comparison.setHorizontalHeaderLabels(
            (
                "Arco",
                "Flujo estático (veh)",
                "Tiempo estático (min)",
                "Entradas SUMO (veh)",
                "Tiempo SUMO (min)",
                "Velocidad SUMO (km/h)",
            )
        )
        self.plot = AdaptiveCanvas(Figure(figsize=(7, 3)))
        results.addTab(self.comparison, "Contraste por arco")
        results.addTab(self.plot, "Evolución de vehículos")
        layout.addWidget(results)
        for spin in (
            self.period_s,
            self.clearance_s,
            self.seed,
            self.timeout_s,
            self.occupancy,
            self.multiplier,
        ):
            spin.valueChanged.connect(self._edited)
        for combo in (self.demand_unit, self.departures):
            combo.currentIndexChanged.connect(self._edited)
        self.demand_unit.currentIndexChanged.connect(self._update_occupancy)
        self.confirmed.toggled.connect(self._confirmation_changed)
        self.bin_directory.textChanged.connect(self._edited)
        for table in (self.nodes_table, self.roads_table):
            table.itemChanged.connect(self._edited)

    def _update_occupancy(self):
        self.occupancy.setEnabled(
            self.demand_unit.currentData() == "persons" and not self.is_running
        )

    def _edited(self, *_args):
        if self._restoring:
            return
        self.confirmed.setChecked(False)
        self.invalidate()
        self.changed.emit()

    def _confirmation_changed(self):
        if not self._restoring:
            self.changed.emit()

    def invalidate(self):
        if self.last_run:
            self.stale = True
            self.status.setText(
                "Se conservan resultados de una ejecución anterior; vuelva a ejecutar "
                "para evaluar los datos actuales."
            )

    def _is_stale(self):
        if self.stale or not self.last_run:
            return self.stale
        try:
            return self.last_run["inputs"]["source"] != self.source_provider()
        except ValueError:
            return True

    def _choose_bin(self):
        folder = QFileDialog.getExistingDirectory(self, "Carpeta bin de Eclipse SUMO")
        if folder:
            self.bin_directory.setText(folder)

    def sync_geometry(self):
        try:
            source = self.source_provider()
        except ValueError as error:
            QMessageBox.warning(self, "Asignación pendiente", str(error))
            return
        self.update_geometry(source)

    def update_geometry(self, source, *, preserve=True):
        nodes, roads = defaults(source)
        previous_nodes = {row[0]: row[1:] for row in _values(self.nodes_table)} if preserve else {}
        previous_roads = {row[0]: row[3:] for row in _values(self.roads_table)} if preserve else {}
        _fill(
            self.nodes_table,
            [[node.name, *previous_nodes.get(node.name, [node.x, node.y])] for node in nodes],
            (0,),
        )
        by_id = {road.link_id: road for road in roads}
        _fill(
            self.roads_table,
            [
                [
                    row[0],
                    row[1],
                    row[2],
                    *previous_roads.get(
                        row[0],
                        [by_id[row[0]].length_m, by_id[row[0]].speed_kmh, by_id[row[0]].lanes],
                    ),
                ]
                for row in source["links"]
            ],
            (0, 1, 2),
        )
        self.source_label.setText(
            f"Modo: {source['mode_name']} · "
            f"{len(source['zone_names'])} zonas · "
            f"Referencia: {source['method'].upper()} · "
            "Geometría de ejemplo editable, sin calibración local."
        )
        self._edited()

    def settings(self):
        return Settings(
            **{
                name: getattr(self, name).value()
                for name in (
                    "period_s",
                    "clearance_s",
                    "seed",
                    "timeout_s",
                    "occupancy",
                    "multiplier",
                )
            },
            demand_unit=self.demand_unit.currentData(),
            departures=self.departures.currentData(),
            confirmed=self.confirmed.isChecked(),
        )

    def state(self):
        return dict(
            settings=asdict(self.settings()),
            nodes=_values(self.nodes_table),
            roads=_values(self.roads_table),
            bin_directory=self.bin_directory.text(),
            last_run=copy.deepcopy(self.last_run),
            stale=self._is_stale(),
        )

    def restore_state(self, state):
        self._restoring = True
        try:
            for name, value in state.get("settings", {}).items():
                field = getattr(self, name)
                if isinstance(field, QComboBox):
                    field.setCurrentIndex(field.findData(value))
                elif isinstance(field, QCheckBox):
                    field.setChecked(value)
                else:
                    field.setValue(value)
            self.bin_directory.setText(state.get("bin_directory", ""))
            _fill(self.nodes_table, state.get("nodes", []), (0,))
            _fill(self.roads_table, state.get("roads", []), (0, 1, 2))
            self.last_run = copy.deepcopy(state.get("last_run"))
            self.stale = state.get("stale", False)
            self.source_label.setText(
                "Configuración SUMO recuperada del ejercicio. "
                "La ejecución usará la última asignación válida."
            )
            self._display_result()
        finally:
            self._restoring = False
        self._update_occupancy()

    def _choose_output(self, execute):
        folder = QFileDialog.getExistingDirectory(self, "Guardar escenario y salidas SUMO")
        if folder:
            self.start_run(folder, execute=execute)

    def start_run(self, folder, *, execute=True):
        if self.is_running:
            return
        try:
            source = copy.deepcopy(self.source_provider())
            settings = self.settings()
            settings.validate()
            nodes = [
                Node(row[0], _float(row[1]), _float(row[2])) for row in _values(self.nodes_table)
            ]
            roads = [
                Road(row[0], _float(row[3]), _float(row[4]), int(row[5]))
                for row in _values(self.roads_table)
            ]
            bin_directory = self.bin_directory.text().strip()
        except ValueError as error:
            QMessageBox.warning(self, "Datos de microsimulación", str(error))
            return
        self._launch(
            lambda cancel, progress: run_scenario(
                folder,
                source,
                nodes,
                roads,
                settings,
                bin_directory=bin_directory,
                execute=execute,
                cancel=cancel,
                progress=progress,
            )
        )

    def check_tools(self):
        if self.is_running:
            return
        directory = self.bin_directory.text().strip()

        def operation(cancel, _progress):
            paths, versions = detect_tools(directory, cancel=cancel)
            return {"tool_check": True, "paths": paths, "versions": versions}

        self._launch(operation)

    def _launch(self, operation):
        self.status.setText("Preparando ejecución…")
        self.task = SumoTask(operation, self)
        self.task.progress.connect(self.status.setText)
        self.task.succeeded.connect(self._succeeded)
        self.task.failed.connect(self._failed)
        self.task.cancelled.connect(self.status.setText)
        self.task.finished.connect(self._idle)
        self._set_busy(True)
        self.running_changed.emit(True)
        self.task.start()

    def _set_busy(self, busy):
        for field in (
            self.geometry,
            self.bin_directory,
            self.choose_bin,
            self.run_button,
            self.export_button,
            self.sync_button,
            self.check_button,
            self.confirmed,
            self.period_s,
            self.clearance_s,
            self.seed,
            self.timeout_s,
            self.demand_unit,
            self.occupancy,
            self.multiplier,
            self.departures,
        ):
            field.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if not busy:
            self._update_occupancy()

    def cancel(self):
        if self.task:
            self.status.setText("Cancelando y cerrando los procesos SUMO…")
            self.task.cancel()

    @Slot(object)
    def _succeeded(self, result):
        if result.get("tool_check"):
            self.status.setText("SUMO disponible: " + result["versions"]["sumo"])
            return
        self.last_run = result
        self.stale = False
        self.stale = self._is_stale()
        self._display_result()
        self.changed.emit()

    @Slot(str)
    def _failed(self, message):
        self.status.setText(message)
        QMessageBox.warning(self, "No se completó la microsimulación", message)

    @Slot()
    def _idle(self):
        task, self.task = self.task, None
        task.deleteLater()
        self._set_busy(False)
        self.running_changed.emit(False)

    def _display_result(self):
        result = self.last_run
        if not result:
            return
        self.folder_button.setEnabled(True)
        if result["status"] == "prepared":
            self.metrics.setText(
                f"Escenario preparado: {result['generated']} vehículos; sin simulación."
            )
            self.comparison.setRowCount(0)
            self.plot.figure.clear()
            self.plot.draw_idle()
            self.status.setText(
                "Escenario exportado sin ejecutar. Consulte README.txt en " + result["directory"]
            )
            return
        stats = result["statistics"]

        def display(key):
            return f"{stats[key]:.2f}" if stats[key] is not None else "Sin llegadas"

        self.metrics.setText(
            f"Generados: {stats['generated']} · Insertados: {stats['inserted']} · "
            f"Llegados: {stats['arrived']} · En red: {stats['running']} · "
            f"Pendientes de insertar: {stats['pending']} · "
            f"Retirados sin completar: {stats['removed']}\n"
            f"Recorridos completados: tiempo medio {display('mean_duration_s')} s · "
            f"espera {display('mean_waiting_s')} s · "
            f"pérdida de tiempo {display('mean_time_loss_s')} s · "
            f"retraso de inserción {display('mean_depart_delay_s')} s · "
            f"velocidad agregada {display('mean_speed_kmh')} km/h.\n"
            f"Intracentroide excluido: {result['excluded_intrazonal_vehicles']:.3f} "
            "veh equivalentes · "
            f"ajuste de redondeo: {result['rounding_error']:+.3f} veh. "
            "Los tiempos SUMO por arco se estiman con las muestras de todo el horizonte, incluido "
            "el despeje. No son una solución UE ni una certificación de calibración."
        )
        _fill(
            self.comparison,
            [
                [
                    row["link_id"],
                    f"{row['static_vehicles']:.2f}",
                    f"{row['static_time_min']:.3f}",
                    row["sumo_entered"],
                    f"{row['sumo_time_min']:.3f}"
                    if row["sumo_time_min"] is not None
                    else "Sin muestras",
                    f"{row['sumo_speed_kmh']:.2f}"
                    if row["sumo_speed_kmh"] is not None
                    else "Sin muestras",
                ]
                for row in result["edges"]
            ],
            tuple(range(6)),
        )
        self.plot.figure.clear()
        axes = self.plot.figure.subplots()
        series = result.get("series", [])
        if series:
            axes.plot([row[0] for row in series], [row[1] for row in series], label="En red")
            axes.plot(
                [row[0] for row in series],
                [row[2] for row in series],
                linestyle="--",
                label="Llegados acumulados",
            )
            axes.legend()
        axes.set_xlabel("Tiempo simulado (s)")
        axes.set_ylabel("Vehículos")
        self.plot.figure.tight_layout()
        self.plot.draw_idle()
        self.status.setText(
            "Ejecución anterior conservada; vuelva a ejecutar para los datos actuales."
            if self.stale
            else "Simulación terminada. Archivos: " + result["directory"]
        )

    def _open_folder(self):
        if self.last_run:
            path = Path(self.last_run["directory"])
            if path.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            else:
                QMessageBox.information(
                    self,
                    "Carpeta no disponible",
                    "El ejercicio conserva los indicadores. "
                    "La carpeta externa no está en este equipo.",
                )


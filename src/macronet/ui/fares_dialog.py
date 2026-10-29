"""Editor opcional de tarifas, matrices monetarias e instantáneas de escenarios."""

import copy
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from macronet.domain.fare_scenarios import compare_scenarios, evaluate_snapshot
from macronet.domain.fares import (
    DISTANCE_SOURCES,
    SCHEMES,
    default_profile,
    distance_csv,
    parse_distance_csv,
)


def values(table):
    return [
        [table.item(i, j).text() if table.item(i, j) else "" for j in range(table.columnCount())]
        for i in range(table.rowCount())
    ]


def fill(table, rows, *, readonly=False):
    table.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if readonly:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(i, j, item)


class FaresDialog(QDialog):
    def __init__(self, modal):
        super().__init__(modal)
        self.modal = modal
        self.names = list(modal._zone_names)
        self.profiles = copy.deepcopy(modal.fare_profiles) or [
            default_profile(self.names) for _ in range(3)
        ]
        self.scenarios = copy.deepcopy(modal.fare_scenarios)
        self._index = None
        self.setWindowTitle("Tarifas y costos de viaje")
        self.resize(940, 760)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Los esquemas tarifarios activos sustituyen el costo fijo + variable del modo. "
            "Importes en MXN por persona y viaje; distancias en km. La tarifa se aplica "
            "también a viajes intrazonales. Use βc compatible con MXN. "
            "Las comparaciones mantienen fija la OD total."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.mode = QComboBox()
        self.mode.addItems([m.name for m in modal._read_modes()])
        layout.addWidget(self.mode)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)
        content = QWidget()
        form_layout = QVBoxLayout(content)
        form = QFormLayout()
        self.scheme = QComboBox()
        for key, label in SCHEMES.items():
            self.scheme.addItem(label, key)
        self.fixed = QDoubleSpinBox()
        self.rate = QDoubleSpinBox()
        for spin in (self.fixed, self.rate):
            spin.setRange(0, 1e12)
            spin.setDecimals(6)
        form.addRow("Esquema del modo", self.scheme)
        form.addRow("Tarifa plana / base (MXN)", self.fixed)
        form.addRow("Cargo por km (MXN/km)", self.rate)
        self.source = QComboBox()
        for key, label in DISTANCE_SOURCES.items():
            self.source.addItem(label, key)
        self.provenance = QLineEdit()
        form.addRow("Origen de las distancias", self.source)
        form.addRow("Fuente, fecha o método de estimación", self.provenance)
        form_layout.addLayout(form)
        self.bands = QTableWidget(0, 2)
        self.bands.setHorizontalHeaderLabels(
            ("Hasta km (vacío = sin límite)", "Tarifa total (MXN)")
        )
        self.bands.horizontalHeader().setStretchLastSection(True)
        self.bands.setColumnWidth(0, 320)
        self.bands.setMinimumHeight(150)
        form_layout.addWidget(self.bands)
        band_actions = QHBoxLayout()
        self.add_band = QPushButton("Agregar intervalo")
        self.add_band.clicked.connect(lambda: self.bands.insertRow(self.bands.rowCount()))
        self.remove_band = QPushButton("Eliminar intervalo seleccionado")
        self.remove_band.clicked.connect(lambda: self.bands.removeRow(self.bands.currentRow()))
        band_actions.addWidget(self.add_band)
        band_actions.addWidget(self.remove_band)
        form_layout.addLayout(band_actions)
        boundary = QLabel(
            "Primer intervalo: 0 ≤ d ≤ límite. Siguientes: límite anterior < d ≤ límite. "
            "Use límites crecientes y deje vacío el último para cubrir toda distancia."
        )
        boundary.setWordWrap(True)
        form_layout.addWidget(boundary)
        self.distances = QTableWidget(len(self.names), len(self.names))
        self.distances.setHorizontalHeaderLabels(self.names)
        self.distances.setVerticalHeaderLabels(self.names)
        self.distances.setMinimumHeight(230)
        form_layout.addWidget(QLabel("Distancias del modo (km); incluya valores intrazonales"))
        form_layout.addWidget(self.distances)
        distance_actions = QHBoxLayout()
        for label, callback in (
            ("Plantilla de distancias (.csv)", self._template),
            ("Importar distancias (.csv)", self._import_distances),
            ("Exportar distancias (.csv)", self._export_distances),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            distance_actions.addWidget(button)
        form_layout.addLayout(distance_actions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        tabs.addTab(scroll, "Configuración por modo")
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        self.costs = QTableWidget(len(self.names), len(self.names))
        self.costs.setHorizontalHeaderLabels(self.names)
        self.costs.setVerticalHeaderLabels(self.names)
        preview_layout.addWidget(
            QLabel("Vista previa del modo seleccionado: costo monetario total (MXN).")
        )
        self.preview_button = QPushButton("Calcular vista previa")
        self.preview_button.clicked.connect(self.preview)
        preview_layout.addWidget(self.preview_button)
        preview_layout.addWidget(self.costs)
        export_costs = QPushButton("Exportar costos, distancias y elección modal (.csv)…")
        export_costs.clicked.connect(self._export_costs)
        preview_layout.addWidget(export_costs)
        tabs.addTab(preview, "Matriz de costos")
        scenarios = QWidget()
        scenario_layout = QVBoxLayout(scenarios)
        label = QLabel(
            "Guarde variantes con nombres únicos. Las instantáneas incluyen OD, tiempos, "
            "coeficientes, modos y tarifas. La comparación no cambia el ejercicio. "
            "Los cambios se conservan al pulsar Aplicar y calcular."
        )
        label.setWordWrap(True)
        scenario_layout.addWidget(label)
        self.scenario_list = QListWidget()
        self.scenario_list.addItems([s["name"] for s in self.scenarios])
        scenario_layout.addWidget(self.scenario_list)
        actions = QHBoxLayout()
        for label, callback in (
            ("Guardar escenario actual…", self._save_scenario),
            ("Eliminar seleccionado", self._delete_scenario),
            ("Comparar escenarios", self.compare),
            ("Exportar escenarios (.csv)…", self._export_scenarios),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        scenario_layout.addLayout(actions)
        self.comparison = QTableWidget(0, 6)
        self.comparison.setHorizontalHeaderLabels(
            (
                "Escenario",
                "Modo",
                "Viajes",
                "Participación (%)",
                "Δ viajes vs primero",
                "Δ participación (pp)",
            )
        )
        scenario_layout.addWidget(self.comparison)
        tabs.addTab(scenarios, "Escenarios tarifarios")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aplicar y calcular")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.mode.currentIndexChanged.connect(self._switch_mode)
        self.scheme.currentIndexChanged.connect(self._enable_fields)
        for spin in (self.fixed, self.rate):
            spin.valueChanged.connect(self.costs.clearContents)
        for selector in (self.scheme, self.source):
            selector.currentIndexChanged.connect(self.costs.clearContents)
        self.provenance.textChanged.connect(self.costs.clearContents)
        for table in (self.distances, self.bands):
            table.itemChanged.connect(self.costs.clearContents)
        self._switch_mode(0)

    def _store(self):
        if self._index is None:
            return
        self.profiles[self._index] = dict(
            scheme=self.scheme.currentData(),
            fixed=self.fixed.value(),
            rate=self.rate.value(),
            bands=values(self.bands),
            distance_source=self.source.currentData(),
            distance_note=self.provenance.text(),
            zone_names=self.names[:],
            distances=values(self.distances),
        )

    def _switch_mode(self, index):
        self._store()
        self._index = index
        profile = self.profiles[index]
        self.scheme.setCurrentIndex(self.scheme.findData(profile["scheme"]))
        self.fixed.setValue(profile["fixed"])
        self.rate.setValue(profile["rate"])
        self.source.setCurrentIndex(self.source.findData(profile["distance_source"]))
        self.provenance.setText(profile["distance_note"])
        fill(self.bands, profile["bands"])
        fill(self.distances, profile["distances"])
        self.costs.clearContents()
        self._enable_fields()

    def _enable_fields(self):
        scheme = self.scheme.currentData()
        self.fixed.setEnabled(scheme in ("flat", "mixed"))
        self.rate.setEnabled(scheme in ("per_km", "mixed"))
        for field in (self.bands, self.add_band, self.remove_band):
            field.setEnabled(scheme == "bands")
        for field in (self.distances, self.source, self.provenance):
            field.setEnabled(scheme in ("bands", "per_km", "mixed"))

    def snapshot(self):
        self._store()
        return self.modal.fare_snapshot(self.profiles)

    def preview(self):
        try:
            result = evaluate_snapshot(self.snapshot())
        except ValueError as error:
            QMessageBox.warning(self, "Revise tarifas y distancias", str(error))
            return None
        matrix = [
            [od.alternatives[self.mode.currentIndex()].monetary_cost for od in row]
            for row in result.od_results
        ]
        fill(self.costs, [[f"{v:.6g}" for v in row] for row in matrix], readonly=True)
        return result

    def accept(self):
        if self.preview() is not None:
            super().accept()

    def _save_scenario(self):
        if self.preview() is None:
            return
        if len(self.scenarios) >= 20:
            QMessageBox.warning(self, "Escenarios", "Se admiten hasta 20 escenarios por ejercicio.")
            return
        name, accepted = QInputDialog.getText(self, "Guardar escenario", "Nombre del escenario:")
        if not accepted:
            return
        name = name.strip()
        if (
            not name
            or len(name) > 100
            or name.casefold() in {s["name"].casefold() for s in self.scenarios}
        ):
            QMessageBox.warning(self, "Escenarios", "Use un nombre único de 1 a 100 caracteres.")
            return
        self.scenarios.append(dict(name=name, inputs=self.snapshot()))
        self.scenario_list.addItem(name)
        self.comparison.setRowCount(0)

    def _delete_scenario(self):
        index = self.scenario_list.currentRow()
        if index >= 0:
            self.scenarios.pop(index)
            self.scenario_list.takeItem(index)
            self.comparison.setRowCount(0)

    def compare(self):
        try:
            rows = compare_scenarios(self.scenarios)
        except ValueError as error:
            QMessageBox.warning(self, "Escenarios no comparables", str(error))
            return
        fill(
            self.comparison,
            [
                [
                    r["scenario"],
                    r["mode"],
                    f"{r['trips']:.6g}",
                    f"{100 * r['share']:.4f}",
                    f"{r['delta_trips']:+.6g}",
                    f"{r['delta_pp']:+.4f}",
                ]
                for r in rows
            ],
            readonly=True,
        )
        self.comparison.resizeColumnsToContents()

    def _save_csv(self, content, title, default):
        path, _ = QFileDialog.getSaveFileName(self, title, default, "CSV (*.csv)")
        if path:
            target = Path(path)
            if target.suffix.lower() != ".csv":
                target = target.with_suffix(".csv")
            try:
                target.write_text(content, encoding="utf-8-sig", newline="")
            except OSError as error:
                QMessageBox.warning(self, "No se pudo exportar", str(error))

    def _template(self):
        self._save_csv(distance_csv(self.names), "Plantilla de distancias", "distancias_km.csv")

    def _export_distances(self):
        self._save_csv(
            distance_csv(self.names, values(self.distances)),
            "Exportar distancias",
            "distancias_km.csv",
        )

    def _import_distances(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar distancias en km", "", "CSV (*.csv)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > 2 * 1024 * 1024:
                raise ValueError("El CSV de distancias supera 2 MB.")
            matrix = parse_distance_csv(Path(path).read_text(encoding="utf-8-sig"), self.names)
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.warning(self, "Distancias no importadas", str(error))
            return
        fill(self.distances, matrix)

    def _export_costs(self):
        if self.preview() is None:
            return
        from macronet.exporters import build_fare_csv

        self._save_csv(
            build_fare_csv([dict(name="Vista previa", inputs=self.snapshot())]),
            "Exportar costos de viaje",
            "costos_modales.csv",
        )

    def _export_scenarios(self):
        from macronet.exporters import build_fare_csv

        try:
            content = build_fare_csv(self.scenarios)
        except ValueError as error:
            QMessageBox.warning(self, "Escenarios", str(error))
            return
        self._save_csv(content, "Exportar escenarios tarifarios", "escenarios_tarifarios.csv")

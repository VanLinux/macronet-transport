"""Calibración guiada con importación, mapeo, diagnóstico y aplicación explícita."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from html import escape
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

from macronet.domain.calibration import (
    CalibrationError,
    fit_distribution,
    fit_generation,
    fit_modal,
)
from macronet.ui.appearance import AdaptiveCanvas


class FitWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, callback, parent):
        super().__init__(parent)
        self.callback = callback

    def run(self):
        try:
            self.succeeded.emit(self.callback().to_dict())
        except Exception as error:  # El hilo debe devolver cualquier error sin terminar Qt.
            self.failed.emit(str(error))


class CalibrationPanel(QGroupBox):
    changed = Signal()

    def __init__(self, kind, context, apply_parameters, parent=None):
        super().__init__("Origen de parámetros · independiente por etapa", parent)
        self.kind, self.context, self.apply_parameters = kind, context, apply_parameters
        self.state = {"mode": "manual", "records": {}, "applied": {}}
        layout = QHBoxLayout(self)
        self.selector = QComboBox()
        self.selector.addItem("Manual · coeficientes editables", "manual")
        self.selector.addItem("Estimados · calibración con datos observados", "estimated")
        self.open_button = QPushButton("Importar, estimar y revisar…")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_dialog)
        self.selector.currentIndexChanged.connect(self._mode_changed)
        layout.addWidget(self.selector)
        layout.addWidget(self.open_button)

    def _mode_changed(self):
        self.state["mode"] = self.selector.currentData()
        self.open_button.setEnabled(self.state["mode"] == "estimated")
        self.changed.emit()

    def manual_edit(self, key=None):
        """Conserva el diagnóstico, pero ya no atribuye un valor editado a la estimación."""
        if key is None:
            self.state["applied"] = {}
        else:
            self.state["applied"].pop(key, None)
        self.changed.emit()

    def restore_state(self, state):
        self.state = copy.deepcopy(state)
        self.selector.blockSignals(True)
        self.selector.setCurrentIndex(1 if state["mode"] == "estimated" else 0)
        self.selector.blockSignals(False)
        self.open_button.setEnabled(state["mode"] == "estimated")

    def open_dialog(self):
        try:
            context = self.context()
        except ValueError as error:
            QMessageBox.warning(self, "Revise las entradas de la etapa", str(error))
            return
        dialog = CalibrationDialog(self, context)
        dialog.exec()


class CalibrationDialog(QDialog):
    def __init__(self, panel, context):
        super().__init__(panel)
        self.panel, self.context = panel, context
        self.rows, self.headers, self.result = [], [], None
        self.worker = None
        self.setWindowTitle("Calibración · revisar antes de aplicar")
        self.resize(980, 750)
        layout = QVBoxLayout(self)
        self.help = QLabel()
        self.help.setWordWrap(True)
        layout.addWidget(self.help)
        controls = QHBoxLayout()
        self.target = QComboBox()
        if panel.kind == "generation":
            self.target.addItem("Producción · H y V", "production")
            self.target.addItem("Atracción · E y S", "attraction")
        else:
            self.target.addItem(
                "Distribución" if panel.kind == "distribution" else "Elección modal", panel.kind
            )
        self.model = QComboBox()
        if panel.kind == "generation":
            self.model.addItem("OLS · enlace identidad", "ols")
            self.model.addItem("Poisson · enlace log", "poisson")
            self.model.addItem("Binomial negativa NB2 · enlace log", "negative_binomial")
        elif panel.kind == "distribution":
            self.model.addItem(context["friction_function"], context["friction_function"])
        else:
            self.model.addItem("MNL · máxima verosimilitud", "mnl")
        self.advanced = QCheckBox("Habilitar modelos de conteo")
        self.advanced.setVisible(panel.kind == "generation")
        self.advanced.toggled.connect(self._enable_models)
        self._enable_models(False)
        controls.addWidget(self.target)
        controls.addWidget(self.model)
        controls.addWidget(self.advanced)
        layout.addLayout(controls)
        actions = QHBoxLayout()
        load = QPushButton("Importar observaciones CSV…")
        load.clicked.connect(self._import_csv)
        template = QPushButton("Descargar plantilla CSV…")
        template.clicked.connect(self._template)
        self.estimate_button = QPushButton("Estimar parámetros")
        self.estimate_button.clicked.connect(self.estimate)
        self.apply_button = QPushButton("Aplicar parámetros estimados")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply)
        for button in (load, template, self.estimate_button, self.apply_button):
            actions.addWidget(button)
        self.load_button = load
        layout.addLayout(actions)
        self.mapping_form = QFormLayout()
        layout.addLayout(self.mapping_form)
        self.mapping = {}
        tabs = QTabWidget()
        self.preview = QTableWidget()
        self.preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        tabs.addTab(self.preview, "Observaciones importadas")
        self.diagnostics = QTextBrowser()
        tabs.addTab(self.diagnostics, "Diagnósticos y parámetros")
        self.plot = AdaptiveCanvas(Figure(figsize=(8, 4)))
        tabs.addTab(self.plot, "Observados y predichos / residuales")
        self.tabs = tabs
        layout.addWidget(tabs, 1)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self._active_target = self.target.currentData()
        self.target.currentIndexChanged.connect(self._switch_target)
        self.model.currentIndexChanged.connect(self._invalidate)
        self._restore_record()

    def _switch_target(self):
        self._remember_record(self._active_target)
        self._active_target = self.target.currentData()
        self._restore_record()

    def _remember_record(self, key):
        if self.rows:
            self.panel.state["records"][key] = dict(
                rows=copy.deepcopy(self.rows),
                headers=self.headers,
                filename=self.filename,
                mapping={k: c.currentText() for k, c in self.mapping.items()},
                model=self.model.currentData(),
                advanced=self.advanced.isChecked(),
                result=self.result,
                context=json.loads(json.dumps(self.context)),
            )
            self.panel.changed.emit()

    def _enable_models(self, enabled):
        if self.panel.kind != "generation":
            return
        for index in (1, 2):
            self.model.model().item(index).setEnabled(enabled)
        if not enabled:
            self.model.setCurrentIndex(0)

    def _roles(self):
        if self.panel.kind == "generation":
            return [
                ("id", "Observación independiente (única)"),
                ("x1", "Hogares H" if self.target.currentData() == "production" else "Empleos E"),
                (
                    "x2",
                    "Vehículos V" if self.target.currentData() == "production" else "Estudiantes S",
                ),
                ("y", "Viajes observados"),
                ("sample", "Muestra (opcional: train / validation)"),
            ]
        if self.panel.kind == "distribution":
            return [
                ("origin", "Origen (nombre de zona)"),
                ("destination", "Destino (nombre de zona)"),
                ("trips", "Viajes OD observados"),
            ]
        return [
            ("id", "Observación/persona"),
            ("mode", "Modo estable (m1, m2, m3)"),
            ("chosen", "Elegido (0/1)"),
            ("time", "Tiempo (min)"),
            ("cost", "Costo (MXN)"),
            ("available", "Disponible (0/1)"),
        ]

    def _restore_record(self):
        saved = self.panel.state["records"].get(self.target.currentData(), {})
        self.rows = copy.deepcopy(saved.get("rows", []))
        self.headers = list(saved.get("headers", []))
        self.filename = saved.get("filename", "")
        self.advanced.setChecked(saved.get("advanced", False))
        index = self.model.findData(saved.get("model", self.model.itemData(0)))
        self.model.setCurrentIndex(max(0, index))
        if self.panel.kind == "generation":
            text = "OLS conserva las ecuaciones actuales. Poisson/NB2 usan exp(intercepto + βX); "
            text += "habilítelos solo para conteos y después de revisar supuestos. "
            text += (
                "Producción y atracción se estiman por separado. "
                "Requiere n > parámetros y rango completo."
            )
        elif self.panel.kind == "distribution":
            text = (
                "Importe todas las celdas OD observadas (incluidos ceros). "
                "Orden según nombres de zona. "
            )
            text += (
                "Se usan las impedancias y marginales actuales: "
                "deben corresponder a la misma muestra. "
            )
            text += (
                "Cada evaluación recalcula Furness. Función: " + self.context["friction_function"]
            )
        else:
            text = "Tres filas por observación, una por alternativa, incluso no disponibles. "
            text += "Un solo elegido disponible; al menos dos alternativas disponibles. "
            text += "ASC_m1 = 0. " + "; ".join(
                f"m{i + 1} = {name}" for i, name in enumerate(self.context["mode_names"])
            )
        self.help.setText(text)
        self._show_data(saved.get("mapping", {}))
        self.result = saved.get("result")
        if self.result:
            self._display_result(self.result)
        else:
            self.diagnostics.clear()
            self.plot.figure.clear()
            self.plot.draw_idle()
        self.apply_button.setEnabled(bool(self.result))

    def _show_data(self, mapping=None):
        while self.mapping_form.rowCount():
            self.mapping_form.removeRow(0)
        self.mapping = {}
        for key, label in self._roles():
            combo = QComboBox()
            combo.addItems(["—", *self.headers])
            default = (mapping or {}).get(key, key if key in self.headers else "—")
            combo.setCurrentText(default)
            combo.currentIndexChanged.connect(self._invalidate)
            self.mapping_form.addRow(label, combo)
            self.mapping[key] = combo
        self.preview.setColumnCount(len(self.headers))
        self.preview.setHorizontalHeaderLabels(self.headers)
        self.preview.setRowCount(min(len(self.rows), 200))
        for row, values in enumerate(self.rows[:200]):
            for column, value in enumerate(values):
                self.preview.setItem(row, column, QTableWidgetItem(value))
        self.preview.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def _invalidate(self, *_args):
        self.result = None
        self.apply_button.setEnabled(False)

    def _import_csv(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Datos observados", "", "CSV (*.csv)")
        if not filename:
            return
        try:
            path = Path(filename)
            if path.stat().st_size > 5 * 1024 * 1024:
                raise ValueError("Use un CSV menor de 5 MB.")
            text = path.read_text(encoding="utf-8-sig")
            try:
                dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            data = list(csv.reader(text.splitlines(), dialect))
            headers = [h.strip() for h in data[0]]
            rows = [row for row in data[1:] if any(cell.strip() for cell in row)]
            if (
                not headers
                or len(headers) > 50
                or len(set(headers)) != len(headers)
                or any(not h for h in headers)
                or not rows
                or len(rows) > 30000
                or any(len(row) != len(headers) for row in rows)
                or any(len(cell) > 10000 for row in [headers, *rows] for cell in row)
            ):
                raise ValueError(
                    "CSV vacío, encabezados duplicados o filas de dimensiones diferentes."
                )
        except (OSError, UnicodeError, ValueError, IndexError, csv.Error) as error:
            QMessageBox.warning(self, "CSV no válido", str(error))
            return
        self.headers, self.rows, self.filename = headers, rows, path.name
        self._show_data()
        self._invalidate()

    def _template(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Plantilla", "observaciones.csv", "CSV (*.csv)"
        )
        if filename:
            try:
                with (
                    Path(filename)
                    .with_suffix(".csv")
                    .open("w", encoding="utf-8-sig", newline="") as f
                ):
                    writer = csv.writer(f)
                    writer.writerow([key for key, _ in self._roles()])
            except OSError as error:
                QMessageBox.warning(self, "No se pudo guardar", str(error))

    def _mapped_rows(self):
        selected = {k: c.currentText() for k, c in self.mapping.items()}
        required = [k for k in selected if k != "sample"]
        if any(selected[k] not in self.headers for k in required):
            raise CalibrationError("Asigne una columna a cada dato requerido.")
        used = [v for v in selected.values() if v in self.headers]
        if len(set(used)) != len(used):
            raise CalibrationError("Cada dato debe usar una columna diferente.")
        return [
            {
                key: row[self.headers.index(header)].strip()
                for key, header in selected.items()
                if header in self.headers
            }
            for row in self.rows
        ]

    def _fit_callback(self):
        records = self._mapped_rows()
        if not records:
            raise CalibrationError("Importe observaciones antes de estimar.")
        model = self.model.currentData()
        context = copy.deepcopy(self.context)
        kind = self.panel.kind
        if kind == "generation":
            ids = [row["id"] for row in records]
            if any(not v for v in ids) or len(set(ids)) != len(ids):
                raise CalibrationError("Las observaciones independientes deben tener ID único.")
            if any(
                row.get("sample", "train") not in ("", "train", "validation") for row in records
            ):
                raise CalibrationError("Muestra solo admite train o validation.")
            train = [r for r in records if r.get("sample", "train") != "validation"]
            test = [r for r in records if r.get("sample") == "validation"]

            def features(rows):
                return [[float(r["x1"]), float(r["x2"])] for r in rows]

            def observed(rows):
                return [float(r["y"]) for r in rows]

            x, y = features(train), observed(train)
            validation = (features(test), observed(test)) if test else None
            return lambda: fit_generation(x, y, model=model, validation=validation)
        if kind == "distribution":
            names = context["names"]
            matrix = [[None] * len(names) for _ in names]
            for row in records:
                if row["origin"] not in names or row["destination"] not in names:
                    raise CalibrationError(
                        "Una zona observada no coincide con las zonas del ejercicio."
                    )
                i, j = names.index(row["origin"]), names.index(row["destination"])
                if matrix[i][j] is not None:
                    raise CalibrationError("Una celda OD observada está duplicada.")
                matrix[i][j] = float(row["trips"])
            if any(cell is None for row in matrix for cell in row):
                raise CalibrationError("Incluya todas las celdas OD, también los ceros.")
            return lambda: fit_distribution(
                names,
                context["productions"],
                context["attractions"],
                context["costs"],
                matrix,
                friction_function=model,
            )
        observations = {}
        for row in records:
            if not row["id"] or row["mode"] not in ("m1", "m2", "m3"):
                raise CalibrationError("Cada fila necesita ID y un modo m1, m2 o m3.")
            group = observations.setdefault(row["id"], {})
            if row["mode"] in group:
                raise CalibrationError("Alternativa repetida dentro de una observación.")
            group[row["mode"]] = row
        times, costs, choices, available = [], [], [], []
        for group in observations.values():
            if set(group) != {"m1", "m2", "m3"}:
                raise CalibrationError("Cada observación debe incluir los tres modos.")
            alternatives = [group[f"m{i}"] for i in (1, 2, 3)]
            chosen = [float(r["chosen"]) for r in alternatives]
            if any(v not in (0, 1) for v in chosen) or sum(chosen) != 1:
                raise CalibrationError("Indique exactamente un modo elegido (1) por observación.")
            choices.append(chosen.index(1))
            times.append([float(r["time"]) for r in alternatives])
            costs.append([float(r["cost"]) for r in alternatives])
            available.append([float(r["available"]) for r in alternatives])
        return lambda: fit_modal(times, costs, choices, available)

    def estimate(self):
        try:
            callback = self._fit_callback()
        except (ValueError, TypeError) as error:
            QMessageBox.warning(self, "Revise los datos", str(error))
            return
        self._invalidate()
        self.worker = FitWorker(callback, self)
        self._busy(True)
        self.diagnostics.setPlainText("Estimando con datos observados…")
        self.tabs.setCurrentWidget(self.diagnostics)
        self.worker.succeeded.connect(self._estimated)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(lambda: self._busy(False))
        self.worker.start()

    def _busy(self, busy):
        for widget in (
            self.target,
            self.model,
            self.advanced,
            self.load_button,
            self.estimate_button,
        ):
            widget.setEnabled(not busy)
        for combo in self.mapping.values():
            combo.setEnabled(not busy)

    def _estimated(self, result):
        self.result = result
        self.panel.state["records"][self.target.currentData()] = dict(
            rows=copy.deepcopy(self.rows),
            headers=self.headers,
            filename=self.filename,
            mapping={k: c.currentText() for k, c in self.mapping.items()},
            model=self.model.currentData(),
            advanced=self.advanced.isChecked(),
            result=result,
            context=json.loads(json.dumps(self.context)),
        )
        self.panel.changed.emit()
        self._display_result(result)
        self.apply_button.setEnabled(True)

    def _display_result(self, result):
        text = [
            f"<b>Modelo: {escape(result['model'])}</b>",
            "<table>",
            "<tr><th>Parámetro</th><th>Estimación</th><th>EE</th><th>IC 95%</th></tr>",
        ]
        for name, value in result["parameters"].items():
            se = result["standard_errors"].get(name)
            ci = result["confidence_intervals"].get(name)
            label = name
            if self.panel.kind == "generation":
                labels = (
                    {
                        "intercept": "β₀ · intercepto producción",
                        "x1": "βH · hogares",
                        "x2": "βV · vehículos",
                    }
                    if self.target.currentData() == "production"
                    else {
                        "intercept": "α₀ · intercepto atracción",
                        "x1": "αE · empleos",
                        "x2": "αS · estudiantes",
                    }
                )
                label = labels.get(name, name)
            se_text = f"{se:.6g}" if se is not None else "—"
            ci_text = f"[{ci[0]:.6g}, {ci[1]:.6g}]" if ci else "—"
            text.append(
                f"<tr><td>{escape(label)}</td><td>{value:.8g}</td>"
                f"<td>{se_text}</td><td>{ci_text}</td></tr>"
            )
        text.append("</table><br>")
        text.extend(f"{escape(k)}: {v:.6g}<br>" for k, v in result["metrics"].items())
        text.extend(f"<p>{escape(note)}</p>" for note in result["warnings"])
        text.append(
            "<p>Los coeficientes actuales cambian únicamente al pulsar Aplicar. "
            "Después, pulse Calcular en la etapa.</p>"
        )
        self.diagnostics.setHtml("".join(text))
        self.plot.figure.clear()
        observed, predicted = np.asarray(result["observed"]), np.asarray(result["predicted"])
        axes = self.plot.figure.subplots(1, 2)
        if self.panel.kind == "modal":
            indexes = np.arange(1, 4)
            metrics = result["metrics"]
            axes[0].bar(
                indexes - 0.18,
                [metrics[f"observed_share_m{i}"] for i in indexes],
                width=0.36,
                color="0.4",
                label="Observada",
            )
            axes[0].bar(
                indexes + 0.18,
                [metrics[f"predicted_share_m{i}"] for i in indexes],
                width=0.36,
                color="0.7",
                label="Predicha",
            )
            axes[0].legend()
            axes[0].set_xlabel("Modo m1 / m2 / m3")
            axes[1].hist(predicted, color="0.5")
            axes[1].set_xlabel("Probabilidad del modo elegido")
        else:
            axes[0].scatter(observed, predicted, color="0.4", s=12)
            low, high = min(observed.min(), predicted.min()), max(observed.max(), predicted.max())
            axes[0].plot([low, high], [low, high], color="0.6", linestyle="--")
            axes[0].set_xlabel("Viajes observados")
            axes[0].set_ylabel("Viajes predichos")
            axes[1].scatter(predicted, observed - predicted, color="0.4", s=12)
            axes[1].axhline(0, color="0.6")
            axes[1].set_xlabel("Predichos")
            axes[1].set_ylabel("Residuales")
        self.plot.figure.tight_layout()
        self.plot.draw_idle()

    def _failed(self, message):
        self.diagnostics.setPlainText(message)
        QMessageBox.warning(self, "No se pudo estimar", message)

    def apply(self):
        if self.result is None:
            return
        try:
            key = self.target.currentData()
            self.panel.apply_parameters(key, self.result)
        except ValueError as error:
            QMessageBox.warning(self, "No se pueden aplicar estos parámetros", str(error))
            return
        self.panel.state["applied"][key] = copy.deepcopy(self.result)
        self.panel.state["applied"][key]["source"] = {
            "filename": self.filename,
            "row_count": len(self.rows),
            "mapping": {k: c.currentText() for k, c in self.mapping.items()},
            "sha256": hashlib.sha256(
                json.dumps([self.headers, self.rows], ensure_ascii=False).encode()
            ).hexdigest(),
        }
        self.panel.changed.emit()
        self.diagnostics.append("<p><b>Parámetros aplicados. Pulse Calcular en la etapa.</b></p>")

    def done(self, result):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(
                self, "Estimación en curso", "Espere a que termine la estimación."
            )
            return
        self._remember_record(self.target.currentData())
        super().done(result)

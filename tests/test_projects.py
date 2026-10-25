"""Regresiones de guardado completo, reanudación, informes y cancelaciones."""

import copy
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox  # noqa: E402

from macronet.application import MainWindow  # noqa: E402
from macronet.project import ProjectError, load_project, save_project  # noqa: E402
from macronet.ui.project_state import capture_document  # noqa: E402


@pytest.fixture
def window(monkeypatch, qt_app):
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox, "information", lambda *a: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: pytest.fail(str(a)))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: pytest.fail(str(a)))
    window = MainWindow()
    yield window
    window._dirty = False
    window.close()
    window.deleteLater()
    qt_app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def customize(window):
    tabs = window.centralWidget()
    gen, dist, modal, assign, summary = (tabs.widget(i) for i in range(1, 6))
    gen.table.item(0, 0).setText("Zona México")
    gen.table.item(1, 1).setText("140")
    gen._coefficient_inputs["production_households"].setValue(2.5)
    gen.calculate()
    dist.cost_table.item(0, 1).setText("11,5")
    dist.beta_input.setValue(0.15)
    dist.tolerance_input.setValue(0.0001)
    dist.iterations_input.setValue(500)
    # Marginales independientes: no deben ser sustituidos al reabrir.
    dist.marginals_table.item(0, 1).setText("300")
    dist.marginals_table.item(1, 1).setText("400")
    dist.marginals_table.item(2, 1).setText("300")
    dist.marginals_table.item(3, 1).setText("400")
    for row in range(4):
        dist.marginals_table.item(row, 2).setText("350")
    dist.calculate()
    for row, name in enumerate(("Taxi, compartido", "Autobús & Metro", "A pie")):
        modal.modes_table.item(row, 0).setText(name)
    modal.modes_table.item(2, 2).setText("3.1")
    modal.time_coefficient_input.setValue(-0.12)
    modal.cost_coefficient_input.setValue(-0.15)
    modal.calculate()
    assign.mode_selector.setCurrentIndex(1)
    assign.zone_nodes_table.item(0, 1).setText("N001")
    for row in range(assign.links_table.rowCount()):
        for col in (1, 2):
            if assign.links_table.item(row, col).text() == "Zona México":
                assign.links_table.item(row, col).setText("N001")
    assign.links_table.item(0, 3).setText("7.5")
    assign.links_table.item(0, 4).setText("123")
    assign.calculate()
    summary.analyst_name = "María López & Grupo_3"
    modal.od_selector.setCurrentIndex(6)
    tabs.setCurrentIndex(4)


def test_complete_project_roundtrip_and_continuation(window, tmp_path):
    customize(window)
    tabs = window.centralWidget()
    expected = capture_document(tabs)
    results = [tabs.widget(i).current_result for i in range(1, 5)]
    path = tmp_path / "práctica.mnet"
    assert window._write_project(path)
    assert not window._dirty
    assert load_project(path) == expected
    assert window.open_project_path(path)
    restored = window.centralWidget()
    assert capture_document(restored) == expected
    assert [restored.widget(i).current_result for i in range(1, 5)] == results
    assert restored.widget(5).assignment_result == results[-1]
    assert restored.widget(5).assigned_mode == "Autobús & Metro"
    # La conexión entre las cuatro etapas sigue activa después de abrir.
    restored.widget(1).table.item(0, 1).setText("200")
    restored.widget(1).calculate()
    assert restored.widget(5).generation_result.total_productions > 1400
    assert window._dirty


def test_unfinished_cells_and_previous_results_are_preserved(window, tmp_path):
    tabs = window.centralWidget()
    result = tabs.widget(3).current_result
    tabs.widget(3).modes_table.item(0, 1).setText("")
    tabs.widget(1).table.item(0, 1).setText("pendiente")
    path = tmp_path / "incompleto.mnet"
    expected = capture_document(tabs)
    assert window._write_project(path)
    assert window.open_project_path(path)
    assert capture_document(window.centralWidget()) == expected
    assert window.centralWidget().widget(3).current_result == result
    assert "pendientes de calcular" in window.statusBar().currentMessage()


@pytest.mark.parametrize("content", ["no es JSON", "{}", '{"format":"Otro"}'])
def test_bad_files_leave_active_exercise_intact(window, tmp_path, monkeypatch, content):
    tabs = window.centralWidget()
    expected = capture_document(tabs)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: errors.append(a[2]))
    path = tmp_path / "roto.mnet"
    path.write_text(content)
    assert not window.open_project_path(path)
    assert errors
    assert window.centralWidget() is tabs
    assert capture_document(tabs) == expected


def test_invalid_calculated_state_leaves_active_exercise_intact(window, tmp_path, monkeypatch):
    tabs = window.centralWidget()
    document = capture_document(tabs)
    document["calculated"]["assignment"]["links"][0][4] = "-1"
    path = tmp_path / "capacidad_invalida.mnet"
    save_project(path, document)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: None)
    assert not window.open_project_path(path)
    assert window.centralWidget() is tabs


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(format_version=99),
        lambda d: d["draft"]["distribution"].update(beta=101),
        lambda d: d["draft"]["modal"].update(modes=[]),
        lambda d: d["draft"]["modal"]["trip_matrix"][0].append(1.0),
        lambda d: d["draft"]["assignment"].update(mode_index=-1),
        lambda d: d["draft"]["generation"]["coefficients"].update(
            production_intercept=float("nan")
        ),
    ],
)
def test_schema_rejects_incompatible_and_out_of_range_data(window, tmp_path, mutation):
    document = copy.deepcopy(capture_document(window.centralWidget()))
    mutation(document)
    path = tmp_path / "incompatible.mnet"
    path.write_text(json.dumps(document))
    with pytest.raises(ProjectError):
        load_project(path)


def test_failed_atomic_save_preserves_previous_file(window, tmp_path, monkeypatch):
    document = capture_document(window.centralWidget())
    path = tmp_path / "original.mnet"
    save_project(path, document)
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disco no disponible")

    monkeypatch.setattr("macronet.project.os.replace", fail)
    with pytest.raises(OSError):
        save_project(path, document)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_report_prompts_name_every_time_and_can_cancel(window, tmp_path, monkeypatch):
    summary = window.centralWidget().widget(5)
    path = tmp_path / "informe.tex"
    prompts = []

    def name_prompt(*args, **kwargs):
        prompts.append(kwargs["text"])
        return "María & López_1", True

    monkeypatch.setattr(QInputDialog, "getText", name_prompt)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(path), ""))
    summary._export_tex()
    summary._export_tex()
    assert prompts == ["", "María & López_1"]
    assert r"Usuario: María \& López\_1" in path.read_text(encoding="utf-8")
    assert window._dirty
    before = path.read_bytes()
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    summary._export_tex()
    assert path.read_bytes() == before


def test_save_as_suffix_and_cancel_close(window, tmp_path, monkeypatch):
    path = tmp_path / "ejercicio"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(path), ""))
    assert window._save_project_as()
    assert window.project_path == path.with_suffix(".mnet")
    window.centralWidget().widget(1).table.item(0, 1).setText("200")
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()


def test_mode_names_and_assignment_selection_survive_renaming(window):
    tabs = window.centralWidget()
    modal, assign = tabs.widget(3), tabs.widget(4)
    assign.mode_selector.setCurrentIndex(2)
    modal.modes_table.item(2, 0).setText("Motocicleta")
    modal.calculate()
    assert assign.assigned_mode_name == "Motocicleta"
    assert assign.current_result.total_demand == pytest.approx(
        modal.current_result.mode_summaries[2].total_trips
    )
    assert tabs.widget(5).assigned_mode == "Motocicleta"
    assert modal.modal_matrices_tabs.tabText(2) == "Motocicleta"


def test_active_cell_editor_is_committed_before_save_or_close(window, tmp_path, monkeypatch):
    window.show()
    tabs = window.centralWidget()
    tabs.setCurrentIndex(1)
    table = tabs.widget(1).table
    app = QApplication.instance()
    app.processEvents()
    table.setCurrentCell(0, 1)
    table.editItem(table.item(0, 1))
    app.processEvents()
    app.focusWidget().setText("999")
    path = tmp_path / "editor.mnet"
    assert window._write_project(path)
    assert load_project(path)["draft"]["generation"]["table"][0][1] == "999"
    table.editItem(table.item(0, 1))
    app.processEvents()
    app.focusWidget().setText("888")
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Cancel)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert window._dirty
    assert table.item(0, 1).text() == "888"


def test_reopening_current_file_reads_newly_saved_edits(window, tmp_path, monkeypatch):
    path = tmp_path / "mismo_ejercicio.mnet"
    assert window._write_project(path)
    window.centralWidget().widget(1).table.item(0, 1).setText("999")
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Save)
    assert window.open_project_path(path)
    assert window.centralWidget().widget(1).table.item(0, 1).text() == "999"


def test_wardrop_comparison_roundtrip_and_report(window, tmp_path, monkeypatch):
    tabs = window.centralWidget()
    assignment = tabs.widget(4)
    assignment.method_selector.setCurrentIndex(1)
    assignment.compare_methods(raise_errors=True)
    assert assignment.comparison is not None
    assert assignment.current_result.method == "ue"
    expected = capture_document(tabs)
    path = tmp_path / "wardrop.mnet"
    assert window._write_project(path)
    assert load_project(path) == expected
    assert expected["results"]["assignment"]["history"]
    assert window.open_project_path(path)
    assert capture_document(window.centralWidget()) == expected
    summary = window.centralWidget().widget(5)
    tex = tmp_path / "ue.tex"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Héctor", True))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(tex), ""))
    summary._export_tex()
    text = tex.read_text(encoding="utf-8")
    assert "Wardrop UE (Frank--Wolfe)" in text
    assert "Comparación sobre la misma OD" in text
    assert "brecha relativa final" in text
    assert "letterpaper" in text and "fontenc" not in text


def test_schema_one_opens_with_original_aon_and_ols_defaults(window, tmp_path):
    document = capture_document(window.centralWidget())
    original = window.centralWidget().widget(4).current_result
    document["format_version"] = 1
    document["app_version"] = "3.0.0"
    document.pop("results")
    for section in ("draft", "calculated"):
        for stage, state in document[section].items():
            if stage == "generation":
                allowed = {"table", "coefficients"}
            elif stage == "distribution":
                allowed = {"marginals", "costs", "beta", "tolerance", "iterations"}
            elif stage == "modal":
                allowed = {
                    "modes",
                    "time_coefficient",
                    "cost_coefficient",
                    "zone_names",
                    "trip_matrix",
                    "impedance_matrix",
                }
            else:
                allowed = {
                    "centroids",
                    "links",
                    "zone_names",
                    "demand_matrix",
                    "mode_name",
                    "mode_index",
                }
            for key in set(state) - allowed:
                state.pop(key)
    path = tmp_path / "version_3_0.mnet"
    path.write_text(json.dumps(document))
    assert load_project(path)["format_version"] == 3
    assert window.open_project_path(path)
    assignment = window.centralWidget().widget(4)
    assert assignment.method_selector.currentData() == "aon"
    assert assignment.current_result == original


def test_calibration_is_explicit_and_preserves_observations_on_reopen(window, tmp_path, qt_app):
    from macronet.ui.calibration_widget import CalibrationDialog

    tabs = window.centralWidget()
    gen = tabs.widget(1)
    original = gen.current_result
    gen.calibration.selector.setCurrentIndex(1)
    dialog = CalibrationDialog(gen.calibration, {})
    dialog.headers = ["id", "x1", "x2", "y"]
    dialog.rows = [
        [str(i), str(10 + i), str(i * i / 10), str(2 + 3.2 * (10 + i) + 1.1 * i * i / 10)]
        for i in range(20)
    ]
    dialog.filename = "observaciones.csv"
    dialog._show_data()
    dialog.estimate()
    assert dialog.worker.wait(15000)
    qt_app.processEvents()
    assert dialog.result is not None
    assert gen.current_result is original
    assert gen._coefficient_inputs["production_households"].value() == 2
    dialog.apply()
    assert gen.current_result is original
    assert gen._coefficient_inputs["production_households"].value() == pytest.approx(3.2)
    dialog.accept()
    expected = capture_document(tabs)
    path = tmp_path / "calibracion.mnet"
    assert window._write_project(path)
    assert load_project(path) == expected
    assert window.open_project_path(path)
    restored = window.centralWidget().widget(1)
    assert restored.current_result == original
    assert restored.calibration.state["records"]["production"]["filename"] == "observaciones.csv"
    assert restored.calibration.state["applied"]["production"]["model"] == "ols"
    restored.calculate(raise_errors=True)
    assert restored.current_result.total_productions > original.total_productions
    assert restored.calibration.state["applied"]["production"]["model"] == "ols"
    restored._coefficient_inputs["production_households"].setValue(4)
    assert "production" not in restored.calibration.state["applied"]


def test_advanced_distribution_and_modal_application_are_independent(window):
    tabs = window.centralWidget()
    gen, dist, modal, assignment = (tabs.widget(i) for i in range(1, 5))
    gen_coeff = gen._coefficient_inputs["production_households"].value()
    dist.advanced_functions.setChecked(True)
    dist.friction_selector.setCurrentIndex(1)
    dist.alpha_input.setValue(1.3)
    dist.calculate(raise_errors=True)
    assert dist.current_result.friction_function == "power"
    modal._apply_estimate(
        "modal",
        {
            "parameters": {
                "beta_time": -0.13,
                "beta_cost": -0.2,
                "ASC_m1": 0,
                "ASC_m2": 0.5,
                "ASC_m3": -0.3,
            }
        },
    )
    modal.calculate(raise_errors=True)
    assert modal.time_coefficient_input.value() == -0.13
    assert gen._coefficient_inputs["production_households"].value() == gen_coeff
    assert assignment.alpha_input.value() == 0.15
    assert assignment.beta_input.value() == 4


def test_light_dark_themes_keep_readable_palette_and_latex_font(window, qt_app):
    from PySide6.QtGui import QPalette

    for mode in ("dark", "light"):
        window.appearance.set_mode(mode)
        background = qt_app.palette().color(QPalette.ColorRole.Base).lightness()
        foreground = qt_app.palette().color(QPalette.ColorRole.Text).lightness()
        assert abs(background - foreground) > 150
        assert qt_app.font().family() == "Latin Modern Roman"
    window.appearance.set_mode("auto")

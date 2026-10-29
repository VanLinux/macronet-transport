"""Integración gráfica, guardado y compatibilidad del módulo opcional."""

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from macronet.application import MainWindow  # noqa: E402
from macronet.exporters import build_summary_tex  # noqa: E402
from macronet.project import ProjectError, load_project, save_project  # noqa: E402
from macronet.sumo.scenario import SumoCancelled, SumoError  # noqa: E402
from macronet.ui.project_state import capture_document  # noqa: E402

SUFFIX = ".exe" if os.name == "nt" else ""
HAS_SUMO = all(
    (Path(sys.executable).parent / (name + SUFFIX)).is_file() or shutil.which(name)
    for name in ("sumo", "netconvert", "duarouter")
)


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: pytest.fail(str(a[-1])))
    window = MainWindow()
    yield window
    panel = window.centralWidget().microsimulation
    if panel.is_running:
        panel.cancel()
        assert panel.task.wait(5000)
        app.processEvents()
    window._dirty = False
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def wait_idle(panel, timeout_ms=20000):
    if not panel.is_running:
        return
    loop = QEventLoop()
    watchdog = QTimer()
    watchdog.setSingleShot(True)
    watchdog.timeout.connect(loop.quit)

    def changed(running):
        if not running:
            loop.quit()

    panel.running_changed.connect(changed)
    watchdog.start(timeout_ms)
    try:
        loop.exec()
    finally:
        watchdog.stop()
        panel.running_changed.disconnect(changed)
    assert not panel.is_running, "El trabajador SUMO no terminó dentro del límite"


def test_worker_keeps_event_loop_responsive_and_cancels_on_close(window):
    panel = window.centralWidget().microsimulation
    heartbeats = []
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: heartbeats.append(1))
    heartbeat.start(10)

    def operation(cancel, _progress):
        cancel.wait(5)
        if cancel.is_set():
            raise SumoCancelled("Cancelado")
        return {"tool_check": True, "versions": {"sumo": "test"}}

    window.show()
    panel._launch(operation)
    QTimer.singleShot(200, window.close)
    wait_idle(panel)
    heartbeat.stop()
    assert len(heartbeats) >= 5
    assert not panel.is_running


def test_pending_assignment_edits_are_never_sent_to_sumo(window):
    tabs = window.centralWidget()
    tabs.widget(4).links_table.item(0, 3).setText("99")
    with pytest.raises(SumoError, match="pendientes"):
        tabs._sumo_source()


def test_prepared_scenario_and_draft_geometry_survive_mnet_without_engine(window, tmp_path):
    panel = window.centralWidget().microsimulation
    panel.confirmed.setChecked(True)
    panel.start_run(tmp_path, execute=False)
    wait_idle(panel)
    assert panel.last_run["status"] == "prepared"
    # También debe guardarse una celda incompleta sin ejecutarla al reabrir.
    panel.nodes_table.item(0, 1).setText("")
    window.centralWidget().setCurrentIndex(6)
    expected = capture_document(window.centralWidget())
    path = tmp_path / "with-sumo.mnet"
    assert window._write_project(path)
    assert window.open_project_path(path)
    assert capture_document(window.centralWidget()) == expected
    assert window.centralWidget().microsimulation.nodes_table.item(0, 1).text() == ""
    assert not window.centralWidget().microsimulation.is_running


def test_schema_two_opens_without_sumo_and_retains_analytic_results(window, tmp_path):
    document = capture_document(window.centralWidget())
    original = window.centralWidget().widget(4).current_result
    document["format_version"] = 2
    document.pop("microsimulation")
    path = tmp_path / "v3-1-1.mnet"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_project(path)["format_version"] == 4
    assert window.open_project_path(path)
    assert window.centralWidget().widget(4).current_result == original
    assert window.centralWidget().microsimulation.last_run is None


@pytest.mark.skipif(not HAS_SUMO, reason="Motor SUMO opcional no instalado")
def test_real_window_run_reopen_and_tex_preserve_static_results(window, tmp_path):
    tabs = window.centralWidget()
    assignment = tabs.widget(4)
    assignment.method_selector.setCurrentIndex(1)
    assignment.calculate(raise_errors=True)
    original = assignment.current_result
    panel = tabs.microsimulation
    panel.period_s.setValue(120)
    panel.clearance_s.setValue(1800)
    panel.multiplier.setValue(0.1)
    panel.confirmed.setChecked(True)
    window.show()
    tabs.setCurrentIndex(6)
    panel.start_run(tmp_path)
    wait_idle(panel)
    assert assignment.current_result is original
    run = panel.last_run
    assert run and run["status"] == "completed"
    assert run["statistics"]["inserted"] == run["generated"]
    expected = capture_document(tabs)
    path = tmp_path / "simulated.mnet"
    assert window._write_project(path)
    assert window.open_project_path(path)
    assert capture_document(window.centralWidget()) == expected
    summary = window.centralWidget().widget(5)
    tex = build_summary_tex(
        summary.generation_result,
        summary.distribution_result,
        summary.mode_choice_result,
        summary.assignment_result,
        summary.assigned_mode,
        "Héctor & Equipo",
        microsimulation=expected["microsimulation"],
    )
    assert "Microsimulación opcional con SUMO" in tex
    assert "letterpaper" in tex and "fontenc" not in tex
    assert run["fingerprint"] in tex
    (tmp_path / "sumo-report.tex").write_text(tex, encoding="utf-8")
    # Un archivo con indicadores incoherentes se rechaza antes de sustituir la ventana.
    invalid = copy.deepcopy(expected)
    invalid["microsimulation"]["last_run"]["statistics"]["inserted"] += 1
    with pytest.raises(ProjectError):
        save_project(tmp_path / "invalid.mnet", invalid)

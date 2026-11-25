"""Inicio, edición sin demostrativo y navegación con la rueda."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QScrollArea  # noqa: E402

from macronet.application import MainWindow  # noqa: E402
from macronet.ui.project_state import capture_document, fill_table  # noqa: E402


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: pytest.fail(str(a[-1])))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: pytest.fail(str(a[-1])))
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    window = MainWindow()
    yield window
    window._dirty = False
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_startup_is_empty_until_demo_is_selected(window, tmp_path):
    tabs = window.centralWidget()
    assert tabs.currentIndex() == 0
    assert tabs.tabText(0) == "Inicio y alcance"
    assert [action.text() for action in window.menuBar().actions()] == [
        "Archivo", "Proyecto", "Vista", "Ayuda",
    ]
    assert all(widget.current_result is None for widget in tabs.stages.values())
    assert tabs.widget(1).table.rowCount() == tabs.widget(4).links_table.rowCount() == 0
    assert not tabs.widget(5).export_button.isEnabled()
    blank = capture_document(tabs)
    path = tmp_path / "vacío.mnet"
    assert blank["format_version"] == 5 and blank["calculated"] == {}
    assert window._write_project(path)
    assert window.open_project_path(path)
    assert capture_document(window.centralWidget()) == blank
    window.menuBar().actions()[1].menu().actions()[0].trigger()
    tabs = window.centralWidget()
    assert tabs.widget(1).current_result.total_productions == 1200
    assert tabs.widget(5).export_button.isEnabled()
    assert window.project_path is None
    assert window._new_project()
    assert not window.centralWidget().calculated_states


def test_manual_case_saves_partial_inputs_and_calculates_without_an_example(window, tmp_path):
    tabs = window.centralWidget()
    generation, distribution, _, assignment = tabs.stages.values()
    fill_table(generation.table, [["A", "10", "0", "10", "0"], ["B", "20", "0", "20", "0"]])
    generation.calculate(raise_errors=True)
    assert list(tabs.calculated_states) == ["generation"]
    assert distribution.cost_table.item(0, 1).text() == ""
    assert assignment.links_table.rowCount() == 0
    path = tmp_path / "captura.mnet"
    assert window._write_project(path)
    expected = capture_document(tabs)
    assert window.open_project_path(path)
    tabs = window.centralWidget()
    assert capture_document(tabs) == expected
    assert tabs.widget(1).current_result.total_productions == 60
    distribution, assignment = tabs.widget(2), tabs.widget(4)
    fill_table(distribution.cost_table, [["1", "4"], ["4", "1"]])
    fill_table(assignment.links_table, [["AB", "A", "B", "4", "50"], ["BA", "B", "A", "4", "50"]])
    window._calculate_project()
    assert tabs.currentIndex() == 5
    assert assignment.current_result.assigned_demand > 0
    assert [item.link.link_id for item in assignment.current_result.link_results] == ["AB", "BA"]


def _wheel(target):
    global_pos = target.mapToGlobal(QPoint(5, 5))
    QApplication.sendEvent(
        target,
        QWheelEvent(
            QPointF(5, 5), QPointF(global_pos), QPoint(), QPoint(0, -120),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase,
            False,
        ),
    )


def test_wheel_scrolls_the_panel_without_editing_focused_controls(window):
    window.resize(850, 420)
    tabs = window.centralWidget()
    window.show()
    tabs.setCurrentIndex(2)
    dist = tabs.widget(2)
    QApplication.processEvents()
    scrollbar = dist.findChild(QScrollArea).verticalScrollBar()
    assert scrollbar.maximum() > 0
    original = dist.beta_input.value()
    dist.beta_input.setFocus()
    scrollbar.setValue(0)
    _wheel(dist.beta_input.lineEdit())
    assert dist.beta_input.value() == original
    assert scrollbar.value() > 0
    dist.beta_input.stepUp()
    assert dist.beta_input.value() > original
    dist.advanced_functions.setChecked(True)
    _wheel(dist.friction_selector)
    assert dist.friction_selector.currentIndex() == 0
    _wheel(tabs.tabBar())
    assert tabs.currentIndex() == 2

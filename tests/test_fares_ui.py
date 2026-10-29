"""Integración sin alterar la apariencia: edición, proyectos, reportes y contacto."""

import copy
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtGui import QDesktopServices  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402

from macronet.application import MainWindow  # noqa: E402
from macronet.exporters import build_summary_tex  # noqa: E402
from macronet.project import load_project  # noqa: E402
from macronet.ui.about_dialog import CONTACT_EMAIL, ContactDialog  # noqa: E402
from macronet.ui.fares_dialog import FaresDialog, fill  # noqa: E402
from macronet.ui.project_state import capture_document  # noqa: E402


@pytest.fixture
def window(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: pytest.fail(str(a[-1])))
    monkeypatch.setattr(QMessageBox, "question", lambda *a: QMessageBox.StandardButton.Discard)
    window = MainWindow()
    yield window
    window._dirty = False
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_dialog_preview_and_cancel_do_not_mutate_exercise(window):
    modal = window.centralWidget().widget(3)
    before = capture_document(window.centralWidget())
    dialog = FaresDialog(modal)
    dialog.mode.setCurrentIndex(1)
    dialog.scheme.setCurrentIndex(dialog.scheme.findData("flat"))
    dialog.fixed.setValue(12)
    preview = dialog.preview()
    assert preview.od_results[0][1].alternatives[1].monetary_cost == 12
    dialog.reject()
    assert capture_document(window.centralWidget()) == before
    dialog.deleteLater()


def apply_tariff(modal, monkeypatch):
    def edit(dialog):
        dialog.mode.setCurrentIndex(1)
        dialog.scheme.setCurrentIndex(dialog.scheme.findData("bands"))
        fill(dialog.bands, [["5", "8"], ["10", "12"], ["", "25"]])
        dialog.source.setCurrentIndex(dialog.source.findData("network"))
        dialog.provenance.setText("Red & medición 2026")
        fill(dialog.distances, [["1", "7.5", "11", "4"] for _ in range(4)])
        dialog.preview()
        inputs = dialog.snapshot()
        dialog.scenarios = [dict(name="Base & tarifa", inputs=inputs)]
        more = copy.deepcopy(inputs)
        more["fare_profiles"][1]["scheme"] = "flat"
        more["fare_profiles"][1]["fixed"] = 20
        dialog.scenarios.append(dict(name="Plana 20", inputs=more))
        return FaresDialog.DialogCode.Accepted

    monkeypatch.setattr(FaresDialog, "exec", edit)
    modal._edit_fares()


def test_apply_roundtrip_report_and_scenarios_preserve_inputs(window, monkeypatch, tmp_path):
    tabs = window.centralWidget()
    modal = tabs.widget(3)
    original_modes = modal.fare_snapshot()["modes"]
    original_total = modal.current_result.total_trips
    apply_tariff(modal, monkeypatch)
    assert modal.fare_snapshot()["modes"] == original_modes
    assert modal.current_result.total_trips == original_total
    assert modal.current_result.od_results[0][1].alternatives[1].monetary_cost == 12
    assert window._dirty
    expected = capture_document(tabs)
    path = tmp_path / "tariffs.mnet"
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
        "Héctor",
        fare_scenarios=expected["fare_scenarios"],
    )
    assert "Tarifas y costos de viaje" in tex and "Distancia (km)" in tex
    assert "Red \\& medición 2026" in tex and "Base \\& tarifa" in tex
    assert "letterpaper" in tex and "fontenc" not in tex
    (tmp_path / "fares-report.tex").write_text(tex, encoding="utf-8")


@pytest.mark.parametrize("version", [1, 2, 3])
def test_old_projects_reopen_with_original_modal_costs(window, tmp_path, version):
    document = capture_document(window.centralWidget())
    original = window.centralWidget().widget(3).current_result
    document["format_version"] = version
    document.pop("fare_scenarios")
    for section in ("draft", "calculated"):
        document[section]["modal"].pop("fare_profiles")
    path = tmp_path / f"old-{version}.mnet"
    path.write_text(json.dumps(document), encoding="utf-8")
    assert load_project(path)["format_version"] == 4
    assert window.open_project_path(path)
    assert window.centralWidget().widget(3).current_result == original


def test_contact_uses_confirmed_address_and_only_opens_mail_client(window, monkeypatch):
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: urls.append(url) or True)
    dialog = ContactDialog(window)
    for button in dialog.findChildren(QPushButton):
        if button.text() == "Escribir sugerencia…":
            button.click()
        if button.text() == "Copiar correo":
            button.click()
    assert CONTACT_EMAIL == "prof.benite.gh@mail.com"
    assert len(urls) == 1 and urls[0].scheme() == "mailto" and urls[0].path() == CONTACT_EMAIL
    assert QApplication.clipboard().text() == CONTACT_EMAIL
    dialog.deleteLater()


def test_saving_only_scenarios_does_not_recalculate_or_change_current_parameters(
    window, monkeypatch
):
    modal = window.centralWidget().widget(3)
    assignment = window.centralWidget().widget(4)
    original_result = modal.current_result
    original_assignment = assignment.current_result
    original_inputs = modal.fare_snapshot()

    def save_only(dialog):
        dialog.scenarios.append(dict(name="Referencia", inputs=dialog.snapshot()))
        return FaresDialog.DialogCode.Accepted

    monkeypatch.setattr(FaresDialog, "exec", save_only)
    modal._edit_fares()
    assert modal.current_result is original_result
    assert assignment.current_result is original_assignment
    assert modal.fare_snapshot() == original_inputs
    assert modal.fare_scenarios[0]["name"] == "Referencia"


def test_cost_preview_is_cleared_when_fare_or_distance_changes(window):
    dialog = FaresDialog(window.centralWidget().widget(3))
    dialog.mode.setCurrentIndex(1)
    dialog.scheme.setCurrentIndex(dialog.scheme.findData("flat"))
    dialog.fixed.setValue(8)
    dialog.preview()
    assert dialog.costs.item(0, 0).text() == "8"
    dialog.fixed.setValue(12)
    assert dialog.costs.item(0, 0) is None
    dialog.deleteLater()

"""Integration checks for zone labels and preservation of user inputs."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox  # noqa: E402

from macronet.application import MainWindow  # noqa: E402


def test_zone_rename_propagates_without_resetting_network(monkeypatch):
    app = QApplication.instance() or QApplication([])

    def unexpected_warning(*args):
        pytest.fail(f"Unexpected UI warning: {args[2]}")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_warning)
    window = MainWindow()
    try:
        tabs = window.centralWidget()
        generation, distribution, modal, assignment = (
            tabs.widget(index) for index in range(1, 5)
        )
        distribution.cost_table.item(0, 1).setText("11.5")
        assignment.links_table.item(0, 3).setText("7.5")
        assignment.links_table.item(0, 4).setText("123")
        generation.table.item(0, 0).setText("Zona A")
        generation.calculate()
        assert distribution.cost_table.horizontalHeaderItem(0).text() == "Zona A"
        assert distribution.cost_table.verticalHeaderItem(0).text() == "Zona A"
        assert distribution.cost_table.item(0, 1).text() == "11.5"
        assert distribution.trip_table.horizontalHeaderItem(0).text() == "Zona A"
        assert modal.od_selector.itemText(0) == "Zona A → Zona A"
        assert modal._modal_matrix_tables[0].horizontalHeaderItem(0).text() == "Zona A"
        assert assignment.zone_nodes_table.item(0, 0).text() == "Zona A"
        assert assignment.zone_nodes_table.item(0, 1).text() == "Zona A"
        assert assignment.links_table.item(0, 1).text() == "Zona A"
        assert assignment.links_table.item(0, 3).text() == "7.5"
        assert assignment.links_table.item(0, 4).text() == "123"
        assert assignment.paths_table.item(0, 0).text() == "Zona A"

        # Recalculation alone must not reset custom centroid node identifiers.
        for row in range(assignment.links_table.rowCount()):
            for column in (1, 2):
                item = assignment.links_table.item(row, column)
                if item.text() == "Zona A":
                    item.setText("N001")
        assignment.zone_nodes_table.item(0, 1).setText("N001")
        generation.table.item(0, 0).setText("Zona B")
        generation.calculate()
        assert assignment.zone_nodes_table.item(0, 0).text() == "Zona B"
        assert assignment.zone_nodes_table.item(0, 1).text() == "N001"
        assert assignment.links_table.item(0, 1).text() == "N001"
        assert assignment.links_table.item(0, 4).text() == "123"
        texts = [label.text() for label in tabs.widget(0).findChildren(QLabel)]
        assert any("Desarrollador: Héctor Benítez García" in text for text in texts)
    finally:
        window.close()
        app.processEvents()

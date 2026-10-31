"""Prueba integral del ejecutable instalado, sin pytest ni intérprete externo."""

from __future__ import annotations

import sys
from pathlib import Path


def check_installation(parent):
    import numpy as np
    import pandas as pd
    from PySide6.QtWidgets import QApplication, QMessageBox

    from macronet import __version__
    from macronet.application import MainWindow
    from macronet.domain.calibration import fit_generation
    from macronet.exporters import build_summary_tex, save_assignment_graphml, save_od_csv
    from macronet.project import load_project
    from macronet.sumo.runner import bundled_bin_directory, detect_tools, run_scenario
    from macronet.sumo.scenario import Node, Road, Settings
    from macronet.ui.appearance import FONT_DIRECTORY
    from macronet.ui.project_state import capture_document

    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    result = {"version": __version__, "python": sys.version, "checks": []}

    def failed_dialog(*args, **kwargs):
        raise RuntimeError(str(args))

    # Un diálogo modal de error haría que la prueba quedara esperando una persona.
    QMessageBox.critical = failed_dialog
    QMessageBox.warning = failed_dialog
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.processEvents()
    tabs = window.centralWidget()
    generation, distribution, modal, assignment = (tabs.widget(i) for i in range(1, 5))
    for widget in (generation, distribution, modal, assignment):
        widget.calculate()
        if widget.current_result is None:
            raise RuntimeError("Una etapa no calculó resultados.")
    result["checks"].append("four_stages_and_qt")
    assignment.method_selector.setCurrentIndex(assignment.method_selector.findData("ue"))
    assignment.calculate()
    if assignment.current_result is None:
        raise RuntimeError("Wardrop no produjo resultados.")
    result["checks"].append("wardrop")

    project = parent / "Práctica México.mnet"
    if not window._write_project(project):
        raise RuntimeError("No se guardó el ejercicio.")
    if load_project(project) != capture_document(tabs) or not window.open_project_path(project):
        raise RuntimeError("El ejercicio guardado no se recuperó.")
    result["checks"].append("mnet_roundtrip")
    tabs = window.centralWidget()
    generation, distribution, modal, assignment = (tabs.widget(i) for i in range(1, 5))

    save_od_csv(parent / "matriz.csv", distribution.current_result)
    save_assignment_graphml(
        parent / "red.graphml",
        assignment.current_result,
        assignment.current_result.zone_names,
        assignment.assigned_mode_name,
    )
    tex = build_summary_tex(
        generation.current_result,
        distribution.current_result,
        modal.current_result,
        assignment.current_result,
        assignment.assigned_mode_name,
        "Prueba de instalación",
    )
    (parent / "informe.tex").write_text(tex, encoding="utf-8")
    frame = pd.DataFrame({"zona": ["México", "Norte"], "viajes": [12, 7]})
    frame.to_excel(parent / "datos.xlsx", index=False)
    if not pd.read_excel(parent / "datos.xlsx").equals(frame):
        raise RuntimeError("No se recuperó el archivo Excel.")
    result["checks"].append("csv_graphml_tex_excel")

    rng = np.random.default_rng(7)
    x = rng.uniform(1, 20, (40, 2))
    fit = fit_generation(x, 5 + x @ np.array([2, 3]))
    if not np.allclose(list(fit.parameters.values()), [5, 2, 3]):
        raise RuntimeError("Falló la calibración OLS.")
    result["checks"].append("statsmodels_calibration")
    if len(list(FONT_DIRECTORY.glob("*.otf"))) != 4:
        raise RuntimeError("Faltan las fuentes de MacroNet.")
    result["checks"].append("fonts")

    paths, versions = detect_tools()
    if getattr(sys, "frozen", False) and any(
        Path(path).parent != bundled_bin_directory() for path in paths.values()
    ):
        raise RuntimeError("La prueba está usando un SUMO externo.")
    source = dict(
        zone_names=["Centro México", "Norte"],
        centroids=[["Centro México", "A"], ["Norte", "B"]],
        links=[["ab", "A", "B", "1", "1000"], ["ba", "B", "A", "1", "1000"]],
        demand_matrix=[[0, 12], [7, 0]],
        mode_name="Automóvil",
        mode_index=0,
        method="aon",
        alpha=0.15,
        beta=4,
        tolerance=0.0001,
        iterations=100,
        comparison=False,
    )
    simulation_parent = parent / "Escenario México"
    simulation_parent.mkdir(exist_ok=True)
    run = run_scenario(
        simulation_parent,
        source,
        [Node("A", 0, 0), Node("B", 500, 0)],
        [Road("ab", 600, 36, 1), Road("ba", 600, 36, 1)],
        Settings(period_s=60, clearance_s=180, demand_unit="vehicles", confirmed=True),
    )
    stats = run["statistics"]
    if stats["generated"] != 19 or stats["arrived"] != 19 or stats["removed"] != 0:
        raise RuntimeError(f"SUMO no conservó la demanda: {stats}")
    result.update(sumo_paths=paths, sumo_versions=versions, sumo_statistics=stats)
    result["checks"].append("bundled_sumo_19_vehicles")
    # Fuerza un render real de todas las pestañas y de sus lienzos.
    for index in range(tabs.count()):
        window.centralWidget().setCurrentIndex(index)
        app.processEvents()
    window.grab().save(str(parent / "ventana.png"))
    window._dirty = False
    window.close()
    app.processEvents()
    return result

"""Verification of MacroNet's open-format exports."""

import csv
from io import StringIO

import networkx as nx
import pytest

from macronet import __version__
from macronet.domain.assignment import Link, assign_all_or_nothing
from macronet.domain.distribution import distribute_trips
from macronet.domain.generation import GenerationCoefficients, ZoneInput, calculate_generation
from macronet.domain.mode_choice import ModeSpecification, choose_modes
from macronet.exporters import (
    build_modal_csv,
    build_od_csv,
    build_summary_tex,
    save_assignment_graphml,
    save_modal_csv,
    save_od_csv,
)

NAMES = ("Centro", "Norte", "Sur", "Oriente")
COSTS = (
    (3.0, 10.0, 15.0, 20.0),
    (10.0, 3.0, 12.0, 18.0),
    (15.0, 12.0, 3.0, 9.0),
    (20.0, 18.0, 9.0, 3.0),
)
MODES = (
    ModeSpecification("Automóvil", 0.3, 1.0, 0.0, 5.0, 0.25),
    ModeSpecification("Transporte público", 0.6, 1.35, 5.0, 6.0, 0.0),
    ModeSpecification("Bicicleta", -0.8, 2.2, 0.0, 0.0, 0.0),
)


def _four_step_results():
    generation = calculate_generation(
        (
            ZoneInput("Centro", 100, 60, 200, 100),
            ZoneInput("Norte", 120, 80, 100, 150),
            ZoneInput("Sur", 110, 70, 80, 150),
            ZoneInput("Oriente", 120, 90, 120, 100),
        ),
        GenerationCoefficients(),
    )
    distribution = distribute_trips(
        NAMES,
        tuple(item.production for item in generation.zones),
        tuple(item.attraction_balanced for item in generation.zones),
        COSTS,
        0.1,
    )
    mode_choice = choose_modes(
        NAMES,
        distribution.trip_matrix,
        COSTS,
        MODES,
        -0.08,
        -0.18,
    )
    auto = mode_choice.mode_summaries[0]
    links = tuple(
        Link(link_id, tail, head, time, capacity)
        for link_id, tail, head, time, capacity in (
            ("L01", "Centro", "Norte", 6.0, 50.0),
            ("L10", "Norte", "Centro", 6.0, 50.0),
            ("L02", "Centro", "Sur", 9.0, 40.0),
            ("L20", "Sur", "Centro", 9.0, 40.0),
            ("L03", "Centro", "Oriente", 16.0, 30.0),
            ("L30", "Oriente", "Centro", 16.0, 30.0),
            ("L12", "Norte", "Sur", 5.0, 40.0),
            ("L21", "Sur", "Norte", 5.0, 40.0),
            ("L13", "Norte", "Oriente", 10.0, 30.0),
            ("L31", "Oriente", "Norte", 10.0, 30.0),
            ("L23", "Sur", "Oriente", 4.0, 45.0),
            ("L32", "Oriente", "Sur", 4.0, 45.0),
        )
    )
    assignment = assign_all_or_nothing(NAMES, NAMES, auto.trip_matrix, links)
    return generation, distribution, mode_choice, assignment


def test_od_csv_contains_labels_values_and_marginals(tmp_path) -> None:
    _, distribution, _, _ = _four_step_results()
    content = build_od_csv(distribution)
    rows = list(csv.reader(StringIO(content)))

    assert rows[0] == ["Origen / destino", *NAMES, "Total origen"]
    assert rows[1][0] == "Centro"
    assert float(rows[1][-1]) == pytest.approx(260.0, abs=0.01)
    assert rows[-1][0] == "Total destino"
    assert float(rows[-1][-1]) == 1200.0

    path = tmp_path / "matriz.csv"
    save_od_csv(path, distribution)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_graphml_preserves_assignment_attributes(tmp_path) -> None:
    _, _, _, assignment = _four_step_results()
    path = tmp_path / "red.graphml"
    save_assignment_graphml(path, assignment, NAMES, "Automóvil")
    graph = nx.read_graphml(path)

    assert graph.is_directed()
    assert graph.nodes["Centro"]["is_centroid"] is True
    assert graph.nodes["Centro"]["zone"] == "Centro"
    l02 = next(data for _, _, data in graph.edges(data=True) if data["id"] == "L02")
    assert l02["free_flow_time"] == 9.0
    assert l02["capacity"] == 40.0
    assert l02["flow"] > 0.0
    assert "volume_capacity_ratio" in l02


def test_summary_tex_contains_all_four_stages() -> None:
    generation, distribution, mode_choice, assignment = _four_step_results()
    content = build_summary_tex(
        generation,
        distribution,
        mode_choice,
        assignment,
        "Automóvil",
        "Héctor & Grupo_3",
    )

    assert r"\section{Generación y atracción}" in content
    assert r"\section{Distribución}" in content
    assert r"\section{Elección modal}" in content
    assert r"\section{Asignación}" in content
    assert "Héctor Benítez García" in content
    assert r"Usuario: Héctor \& Grupo\_3" in content
    assert r"\documentclass[11pt,letterpaper]{article}" in content
    assert r"\usepackage[letterpaper,margin=2.5cm]{geometry}" in content
    assert "fontenc" not in content
    assert r"\end{document}" in content


def test_report_contains_complete_matrices_and_inline_graphs() -> None:
    generation, distribution, modal, assignment = _four_step_results()
    content = build_summary_tex(
        generation, distribution, modal, assignment, "Automóvil", "Héctor"
    )
    assert "MacroNet Transport " + __version__ in content
    assert r"\section{Conclusiones numéricas}" in content
    assert r"\subsection{Matriz OD distribuida}" in content
    assert r"\subsection{Matriz de impedancias de distribución}" in content
    for mode in modal.mode_summaries:
        assert r"\subsection{Matriz OD: " + mode.mode_name + "}" in content
        for row in mode.trip_matrix:
            assert all(f"{value:.6g}" in content for value in row)
    assert r"\begin{tikzpicture}" in content
    assert r"\includegraphics" not in content
    assert "Tarifas y costos de viaje" not in content
    assert "Microsimulación opcional con SUMO" not in content


def test_matrix_annex_splits_destinations_without_losing_marginals() -> None:
    from macronet.exporters import _matrix_tex

    names = tuple(f"Z{i}" for i in range(1, 7))
    matrix = tuple(tuple(10 * i + j for j in range(1, 7)) for i in range(1, 7))
    content = "\n".join(_matrix_tex("OD", names, matrix))
    assert "Destinos 1--4" in content and "Destinos 5--6" in content
    assert r"Z1 & 11 & 12 & 13 & 14 & 81 \\" in content
    assert r"Z1 & 15 & 16 & 81 \\" in content
    assert r"Total destino & 240 & 246 & 1386 \\" in content


def test_modal_csv_preserves_all_matrices_and_totals(tmp_path) -> None:
    _, distribution, modal, _ = _four_step_results()
    rows = list(csv.reader(StringIO(build_modal_csv(modal))))
    assert rows[0] == ["Modo", "Origen / destino", *NAMES, "Total origen"]
    for index, mode in enumerate(modal.mode_summaries):
        block = rows[1 + index * 5 : 1 + (index + 1) * 5]
        assert all(row[0] == mode.mode_name for row in block)
        for origin, row in enumerate(block[:-1]):
            assert row[1] == NAMES[origin]
            assert list(map(float, row[2:-1])) == pytest.approx(mode.trip_matrix[origin])
            assert float(row[-1]) == pytest.approx(sum(mode.trip_matrix[origin]))
        assert block[-1][1] == "Total destino"
        assert float(block[-1][-1]) == pytest.approx(mode.total_trips)
    assert sum(float(rows[5 + i * 5][-1]) for i in range(3)) == pytest.approx(
        sum(distribution.row_totals)
    )
    path = tmp_path / "modales.csv"
    save_modal_csv(path, modal)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_report_requires_an_analyst() -> None:
    with pytest.raises(ValueError, match="nombre"):
        build_summary_tex(*_four_step_results(), "Automóvil", "   ")

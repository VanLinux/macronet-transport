"""Verification of MacroNet's open-format exports."""

import csv
from io import StringIO

import networkx as nx
import pytest

from macronet.domain.assignment import Link, assign_all_or_nothing
from macronet.domain.distribution import distribute_trips
from macronet.domain.generation import GenerationCoefficients, ZoneInput, calculate_generation
from macronet.domain.mode_choice import ModeSpecification, choose_modes
from macronet.exporters import (
    build_od_csv,
    build_summary_tex,
    save_assignment_graphml,
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
    )

    assert r"\section{Generación y atracción}" in content
    assert r"\section{Distribución}" in content
    assert r"\section{Elección modal}" in content
    assert r"\section{Asignación}" in content
    assert "Héctor Benítez García" in content
    assert r"\end{document}" in content

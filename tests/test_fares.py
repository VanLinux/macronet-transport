"""Referencias analíticas, límites tarifarios y comparación con demanda fija."""

import copy
import csv
from io import StringIO

import pytest

from macronet.domain.fare_scenarios import compare_scenarios, evaluate_snapshot
from macronet.domain.fares import default_profile, distance_csv, parse_distance_csv, sync_zones
from macronet.domain.mode_choice import ModeSpecification, choose_modes
from macronet.exporters import build_fare_csv

NAMES = ("A", "B")
MODES = (
    ModeSpecification("Auto", 0.3, 1, 0, 5, 0.25),
    ModeSpecification("Autobús", 0.6, 1.35, 5, 6, 0),
    ModeSpecification("Bicicleta", -0.8, 2.2, 0, 0, 0),
)


def snapshot(scheme="legacy", **kwargs):
    profiles = [default_profile(NAMES) for _ in MODES]
    profiles[1].update(scheme=scheme, **kwargs)
    return dict(
        zone_names=list(NAMES),
        modes=[
            [
                m.name,
                *(
                    str(v)
                    for v in (
                        m.alternative_constant,
                        m.time_multiplier,
                        m.time_constant,
                        m.fixed_cost,
                        m.variable_cost,
                    )
                ),
            ]
            for m in MODES
        ],
        trip_matrix=[[30, 20], [10, 40]],
        impedance_matrix=[[3, 10], [10, 3]],
        time_coefficient=-0.08,
        cost_coefficient=-0.18,
        fare_profiles=profiles,
    )


def test_legacy_configuration_is_identical_to_previous_calculation():
    inputs = snapshot()
    original = choose_modes(
        NAMES, inputs["trip_matrix"], inputs["impedance_matrix"], MODES, -0.08, -0.18
    )
    assert evaluate_snapshot(inputs) == original
    assert not original.fare_details


@pytest.mark.parametrize(
    "scheme,params,cost",
    [
        ("flat", dict(fixed=8), 8),
        ("per_km", dict(rate=2.5), 20),
        ("mixed", dict(fixed=6, rate=1.5), 18),
        (
            "bands",
            dict(bands=[["5", "8"], ["10", "12"], ["15", "16"], ["20", "20"], ["", "25"]]),
            12,
        ),
    ],
)
def test_fares_match_hand_calculations_and_replace_existing_cost(scheme, params, cost):
    distance = "7.5" if scheme == "bands" else "8"
    inputs = snapshot(
        scheme, distance_source="network", distances=[[distance] * 2 for _ in NAMES], **params
    )
    result = evaluate_snapshot(inputs)
    for i, row in enumerate(result.od_results):
        for j, od in enumerate(row):
            assert od.alternatives[1].monetary_cost == cost
            assert od.alternatives[1].utility == pytest.approx(
                0.6 - 0.08 * (5 + 1.35 * inputs["impedance_matrix"][i][j]) - 0.18 * cost
            )
            assert sum(a.trips for a in od.alternatives) == pytest.approx(
                inputs["trip_matrix"][i][j]
            )
    assert result.total_trips == 100


@pytest.mark.parametrize(
    "distance,expected", [("0", 8), ("5", 8), ("5.000000001", 12), ("10", 12), ("10.01", 25)]
)
def test_interval_boundaries_have_no_gaps_or_double_charges(distance, expected):
    inputs = snapshot(
        "bands",
        bands=[["5", "8"], ["10", "12"], ["", "25"]],
        distance_source="estimated",
        distances=[[distance] * 2 for _ in NAMES],
    )
    assert evaluate_snapshot(inputs).od_results[0][1].alternatives[1].monetary_cost == expected


@pytest.mark.parametrize(
    "bands",
    [
        [["5", "8"], ["5", "12"], ["", "20"]],
        [["10", "8"], ["5", "12"], ["", "20"]],
        [["", "8"], ["5", "12"]],
        [["5", "8"]],
        [["5", "-1"], ["", "20"]],
        [],
    ],
)
def test_invalid_intervals_are_rejected(bands):
    with pytest.raises(ValueError):
        evaluate_snapshot(
            snapshot(
                "bands", bands=bands, distance_source="network", distances=[["1", "2"], ["2", "1"]]
            )
        )


@pytest.mark.parametrize("distance", ["", "nan", "inf", "-1"])
def test_invalid_distances_are_rejected_including_intrazonal(distance):
    with pytest.raises(ValueError):
        evaluate_snapshot(
            snapshot(
                "per_km",
                rate=2.5,
                distance_source="estimated",
                distances=[[distance, "8"], ["8", "1"]],
            )
        )


def test_flat_fare_requires_no_distance_but_distance_fare_requires_source():
    assert (
        evaluate_snapshot(snapshot("flat", fixed=8)).od_results[0][1].alternatives[1].monetary_cost
        == 8
    )
    with pytest.raises(ValueError, match="sobre red"):
        evaluate_snapshot(snapshot("per_km", rate=2, distances=[["1"] * 2 for _ in NAMES]))


def test_scenarios_are_independent_reproducible_and_only_redistribute_trips():
    base = snapshot("flat", fixed=8)
    expensive = snapshot("flat", fixed=12)
    scenarios = [dict(name="Base", inputs=base), dict(name="Mayor tarifa", inputs=expensive)]
    original = copy.deepcopy(scenarios)
    rows = compare_scenarios(scenarios)
    assert scenarios == original
    bus = [r for r in rows if r["scenario"] == "Mayor tarifa" and r["mode"] == "Autobús"][0]
    assert bus["delta_trips"] < 0 and bus["delta_pp"] < 0
    assert sum(r["delta_trips"] for r in rows if r["scenario"] == "Mayor tarifa") == pytest.approx(
        0, abs=1e-12
    )
    assert evaluate_snapshot(base).total_trips == evaluate_snapshot(expensive).total_trips == 100
    expensive["trip_matrix"][0][0] += 1
    with pytest.raises(ValueError, match="diferentes"):
        compare_scenarios(scenarios)


def test_distance_csv_preserves_labels_and_rejects_wrong_units_order_and_nans():
    names = ["Centro, mercado", "Norte"]
    matrix = [["0.5", "7.5"], ["8", "1"]]
    content = distance_csv(names, matrix)
    assert parse_distance_csv(content, names) == matrix
    for invalid in (content.replace("(km)", "(min)"), content.replace("7.5", "nan")):
        with pytest.raises(ValueError):
            parse_distance_csv(invalid, names)
    with pytest.raises(ValueError):
        parse_distance_csv(content, names[::-1])


def test_renaming_preserves_distance_positions_and_dimension_change_requires_review():
    profile = snapshot(
        "per_km", rate=2, distance_source="network", distances=[["1", "8"], ["9", "2"]]
    )["fare_profiles"]
    renamed = sync_zones(profile, NAMES, ("Centro", "Norte"))
    assert renamed[1]["distances"] == profile[1]["distances"]
    assert profile[1]["zone_names"] == list(NAMES)
    resized = sync_zones(renamed, ("Centro", "Norte"), ("C", "N", "S"))
    assert resized[1]["distance_source"] == "unspecified"
    assert resized[1]["distances"] == [[""] * 3 for _ in range(3)]


def test_cost_csv_includes_fares_distances_rules_and_choice_results():
    inputs = snapshot(
        "mixed",
        fixed=6,
        rate=1.5,
        distance_source="network",
        distance_note="Medición & red",
        distances=[["1", "8"], ["9", "2"]],
    )
    rows = list(csv.DictReader(StringIO(build_fare_csv([dict(name="Escenario 1", inputs=inputs)]))))
    row = next(
        r for r in rows if r["Modo"] == "Autobús" and r["Origen"] == "A" and r["Destino"] == "B"
    )
    assert float(row["Costo_MXN"]) == 18 and float(row["Distancia_km"]) == 8
    assert row["Fuente_distancia"] == "Medición & red"
    assert row["Tarifa_base_MXN"] == "6" and row["MXN_por_km"] == "1.5"


def test_comparison_rejects_distance_changes_but_flat_fare_needs_no_distance():
    first = snapshot(
        "per_km", rate=2, distance_source="network", distances=[["1", "8"], ["9", "2"]]
    )
    second = copy.deepcopy(first)
    second["fare_profiles"][1]["rate"] = 3
    assert compare_scenarios([dict(name="Base", inputs=first), dict(name="Mayor", inputs=second)])
    second["fare_profiles"][1]["distances"][0][1] = "10"
    with pytest.raises(ValueError, match="distancias"):
        compare_scenarios([dict(name="Base", inputs=first), dict(name="Otra red", inputs=second)])
    assert compare_scenarios(
        [dict(name="Plana", inputs=snapshot("flat", fixed=8)), dict(name="Distancia", inputs=first)]
    )

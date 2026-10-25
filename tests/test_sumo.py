"""Demanda, red, procesos reales y conservación de vehículos del adaptador SUMO."""

import copy
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path
from threading import Event, Timer
from xml.etree import ElementTree as ET

import pytest

from macronet.sumo.runner import command, detect_tools, run_scenario
from macronet.sumo.scenario import (
    Node,
    Road,
    Settings,
    SumoCancelled,
    SumoError,
    integer_demand,
    prepare_scenario,
    validate_saved_state,
)

SUFFIX = ".exe" if os.name == "nt" else ""
HAS_SUMO = all(
    (Path(sys.executable).parent / (tool + SUFFIX)).is_file() or shutil.which(tool)
    for tool in ("sumo", "netconvert", "duarouter")
)
native = pytest.mark.skipif(not HAS_SUMO, reason="Motor SUMO opcional no instalado")


@pytest.fixture
def source():
    return dict(
        zone_names=["Centro & Mercado", "Norte"],
        centroids=[["Centro & Mercado", "A"], ["Norte", "B"]],
        links=[["ab & <>", "A", "B", "6", "1000"], ["ba", "B", "A", "6", "1000"]],
        demand_matrix=[[0, 12], [7, 0]],
        mode_name="Automóvil",
        mode_index=0,
        method="ue",
        alpha=0.15,
        beta=4,
        tolerance=0.0001,
        iterations=100,
        comparison=False,
    )


@pytest.fixture
def nodes():
    return [Node("A", 0, 0), Node("B", 500, 0)]


@pytest.fixture
def roads():
    return [Road("ab & <>", 600, 36, 1), Road("ba", 600, 36, 1)]


@pytest.fixture
def settings():
    return Settings(period_s=60, clearance_s=180, demand_unit="vehicles", confirmed=True)


def test_person_conversion_excludes_intrazonal_and_preserves_rounded_total(source, settings):
    source["demand_matrix"] = [[5, 1.2], [2.4, 7]]
    matrix, converted, excluded = integer_demand(
        source, replace(settings, demand_unit="persons", occupancy=1.5)
    )
    assert matrix == [[0, 1], [1, 0]]
    assert converted == pytest.approx(2.4)
    assert excluded == pytest.approx(8)
    assert abs(sum(map(sum, matrix)) - converted) <= 0.5


@pytest.mark.parametrize(
    "changes",
    [
        dict(confirmed=False),
        dict(seed=True),
        dict(period_s=0),
        dict(occupancy=float("nan")),
        dict(multiplier=float("inf")),
        dict(demand_unit="pedestrians"),
    ],
)
def test_invalid_units_period_and_unconfirmed_settings_are_rejected(settings, changes):
    with pytest.raises(SumoError):
        replace(settings, **changes).validate()


def test_too_many_vehicles_and_empty_external_demand_are_rejected(source, settings):
    for matrix in ([[0, 50001], [0, 0]], [[10, 0], [0, 30]]):
        source["demand_matrix"] = matrix
        with pytest.raises(SumoError):
            integer_demand(source, settings)


def test_export_is_reproducible_and_reference_uses_geometry_without_changing_source(
    tmp_path,
    source,
    nodes,
    roads,
    settings,
):
    original = copy.deepcopy(source)
    first = prepare_scenario(tmp_path / "one", source, nodes, roads, settings)
    second = prepare_scenario(tmp_path / "two", source, nodes, roads, settings)
    assert source == original
    assert first["fingerprint"] == second["fingerprint"]
    assert (tmp_path / "one/trips.trips.xml").read_bytes() == (
        tmp_path / "two/trips.trips.xml"
    ).read_bytes()
    assert first["reference"]["link_results"][0]["link"]["free_flow_time"] == 1
    assert first["reference"]["link_results"][0]["link"]["capacity"] == 1000
    assert first["reference"]["link_results"][0]["volume"] == 12
    for file in (tmp_path / "one").glob("*.xml"):
        ET.parse(file)
    assert set(first["edge_map"]) == {"ab & <>", "ba"}
    assert [
        trip.get("id") for trip in ET.parse(tmp_path / "one/trips.trips.xml").findall("trip")
    ] == [f"v{i}" for i in range(19)]


@pytest.mark.parametrize("bad", ["short", "coincident", "missing"])
def test_geometry_must_match_topology_and_distances(tmp_path, source, nodes, roads, settings, bad):
    if bad == "short":
        roads[0] = replace(roads[0], length_m=100)
    elif bad == "coincident":
        nodes[1] = replace(nodes[1], x=0)
    else:
        roads.pop()
    with pytest.raises(SumoError):
        prepare_scenario(tmp_path, source, nodes, roads, settings)


def test_missing_engine_is_actionable_and_not_required_for_export(
    tmp_path, source, nodes, roads, settings
):
    with pytest.raises(SumoError, match="No se encontraron"):
        detect_tools(str(tmp_path))
    exported = run_scenario(
        tmp_path, source, nodes, roads, settings, execute=False, bin_directory=str(tmp_path)
    )
    assert exported["status"] == "prepared"
    assert not (Path(exported["directory"]) / "tripinfo.xml").exists()
    assert (Path(exported["directory"]) / "simulation.sumocfg").exists()


@pytest.mark.parametrize("operation", ["cancel", "timeout", "error"])
def test_process_is_reaped_on_cancel_timeout_or_failure(tmp_path, monkeypatch, operation):
    from macronet.sumo import runner

    processes = []
    real_popen = subprocess.Popen

    def record(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", record)
    cancel = Event()
    timer = Timer(0.25, cancel.set)
    if operation == "cancel":
        timer.start()
    deadline = time.monotonic() + (0.25 if operation == "timeout" else 5)
    script = "raise SystemExit(7)" if operation == "error" else "import time; time.sleep(30)"
    try:
        with pytest.raises(SumoCancelled if operation == "cancel" else SumoError):
            command([sys.executable, "-c", script], tmp_path, "process.log", cancel, deadline)
    finally:
        timer.cancel()
    assert processes and all(process.poll() is not None for process in processes)


@native
@pytest.mark.parametrize("method", ["aon", "ue"])
def test_real_sumo_conserves_demand_and_link_mapping(
    tmp_path, source, nodes, roads, settings, method
):
    source["method"] = method
    run = run_scenario(tmp_path, source, nodes, roads, settings)
    stats = run["statistics"]
    assert run["status"] == "completed"
    assert stats["generated"] == stats["inserted"] == stats["arrived"] == 19
    assert stats["running"] == stats["pending"] == stats["removed"] == 0
    assert stats["mean_duration_s"] > 60
    assert 0 < stats["mean_speed_kmh"] < 36
    assert [row["sumo_entered"] for row in run["edges"]] == [12, 7]
    assert run["reference"]["method"] == method
    assert run["series"][-1][2] == 19
    assert len(run["series"]) <= 401
    state = dict(
        settings=asdict(settings), nodes=[], roads=[], bin_directory="", stale=False, last_run=run
    )
    validate_saved_state(state)
    disk = json.loads((Path(run["directory"]) / "manifest.json").read_text(encoding="utf-8"))
    assert disk == json.loads(json.dumps(run))
    assert all(run["versions"].values())
    assert run["sha256"] and len(run["commands"]) == 3
    assert (Path(run["directory"]) / "comparison.csv").exists()


@native
def test_unfinished_and_pending_vehicles_are_not_counted_as_arrivals(
    tmp_path, source, nodes, roads, settings
):
    source["demand_matrix"] = [[0, 100], [0, 0]]
    run = run_scenario(
        tmp_path, source, nodes, roads, replace(settings, period_s=10, clearance_s=0)
    )
    stats = run["statistics"]
    assert stats["arrived"] == 0 and stats["mean_duration_s"] is None
    assert stats["running"] > 0 and stats["pending"] > 0
    assert stats["running"] + stats["pending"] == 100


@native
def test_one_way_origin_and_destination_taz_are_usable(tmp_path, source, nodes, roads, settings):
    source["links"] = source["links"][:1]
    source["demand_matrix"] = [[0, 12], [0, 0]]
    run = run_scenario(tmp_path, source, nodes, roads[:1], settings)
    assert run["statistics"]["arrived"] == 12


@native
def test_same_seed_reproduces_completed_statistics(tmp_path, source, nodes, roads, settings):
    settings = replace(settings, departures="random")
    first = run_scenario(tmp_path, source, nodes, roads, settings)
    second = run_scenario(tmp_path, source, nodes, roads, settings)
    assert first["fingerprint"] == second["fingerprint"]
    assert first["statistics"] == second["statistics"]
    assert first["edges"] == second["edges"]

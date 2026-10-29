"""Formato .mnet: JSON versionado y escritura atómica, sin objetos ejecutables."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

from macronet import __version__
from macronet.domain.fare_scenarios import evaluate_snapshot
from macronet.domain.fares import validate_profiles
from macronet.domain.generation import GenerationCoefficients
from macronet.sumo.scenario import validate_saved_state

FORMAT_VERSION = 4
STAGES = ("generation", "distribution", "modal", "assignment")
MAX_PROJECT_BYTES = 10 * 1024 * 1024


class ProjectError(ValueError):
    """Archivo incompatible, incompleto o dañado."""


def validate_project(document: object) -> None:
    """Valida todo antes de modificar el ejercicio abierto, incluidos los borradores."""

    if not isinstance(document, dict) or document.get("format") != "MacroNet Transport":
        raise ProjectError("El archivo no es un ejercicio de MacroNet Transport.")
    if type(document.get("format_version")) is not int or document["format_version"] not in (
        1,
        2,
        3,
        4,
    ):
        raise ProjectError("Versión de archivo .mnet incompatible. Actualice MacroNet.")
    try:
        _safe_tree(document)
        _text(document["analyst_name"])
        for section in ("draft", "calculated"):
            states = document[section]
            if set(states) != set(STAGES):
                raise ValueError("Faltan etapas del ejercicio.")
            for stage in STAGES:
                _validate_state(stage, states[stage])
        sizes = []
        for section in ("draft", "calculated"):
            states = document[section]
            sizes.extend(
                (
                    len(states["generation"]["table"]),
                    len(states["distribution"]["marginals"]),
                    len(states["modal"]["zone_names"]),
                    len(states["assignment"]["zone_names"]),
                )
            )
        if len(set(sizes)) != 1:
            raise ValueError("Las etapas tienen diferentes dimensiones de zonas.")
        view = document["view"]
        _number(view["tab"], 0, 6 if document["format_version"] >= 3 else 5, integer=True)
        _number(view["od"], 0, sizes[0] ** 2 - 1, integer=True)
        if "microsimulation" in document:
            validate_saved_state(document["microsimulation"])
            last_run = document["microsimulation"]["last_run"]
            if last_run:
                _validate_state("assignment", last_run["inputs"]["source"])
        scenarios = document.get("fare_scenarios", [])
        if not isinstance(scenarios, list) or len(scenarios) > 20:
            raise ValueError("Se admiten hasta 20 escenarios tarifarios.")
        scenario_names = []
        for scenario in scenarios:
            _text(scenario["name"])
            if not scenario["name"].strip() or len(scenario["name"]) > 100:
                raise ValueError("Nombre de escenario tarifario inválido.")
            scenario_names.append(scenario["name"].strip().casefold())
            _validate_state("modal", scenario["inputs"])
            evaluate_snapshot(scenario["inputs"])
        if len(set(scenario_names)) != len(scenario_names):
            raise ValueError("Los escenarios deben tener nombres únicos.")
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ProjectError(
            f"El archivo .mnet contiene datos incompletos o inválidos: {error}"
        ) from error


def _validate_state(stage: str, state: dict) -> None:
    if "calibration" in state:
        _calibration(state["calibration"])
    if stage == "generation":
        _table(state["table"], 5)
        names = GenerationCoefficients.__dataclass_fields__
        if set(state["coefficients"]) != set(names):
            raise ValueError("Coeficientes de generación incompletos.")
        for value in state["coefficients"].values():
            _number(value, -1_000_000, 1_000_000)
        for key in ("production_model", "attraction_model"):
            if state.get(key, "ols") not in ("ols", "poisson", "negative_binomial"):
                raise ValueError("Modelo de generación inválido.")
    elif stage == "distribution":
        size = _table(state["marginals"], 3)
        _table(state["costs"], size, rows=size)
        _number(state["beta"], 0, 100)
        _number(state["tolerance"], 0.000001, 1)
        _number(state["iterations"], 1, 10_000, integer=True)
        _number(state.get("alpha", 1), 0, 100)
        if state.get("friction_function", "exponential") not in (
            "exponential",
            "power",
            "combined",
        ):
            raise ValueError("Función de fricción inválida.")
        _boolean(state.get("advanced_functions", False))
        if state.get("friction_function", "exponential") != "exponential" and not state.get(
            "advanced_functions"
        ):
            raise ValueError("La función avanzada de distribución no está habilitada.")
    else:
        names = state["zone_names"]
        if not isinstance(names, list) or not 1 <= len(names) <= 100:
            raise ValueError("Dimensiones de zonas inválidas.")
        for name in names:
            _text(name)
        if stage == "modal":
            validate_profiles(state.get("fare_profiles", []))
            _table(state["modes"], 6, rows=3)
            _number(state["time_coefficient"], -100, 0)
            _number(state["cost_coefficient"], -100, 0)
            _matrix(state["trip_matrix"], len(names))
            _matrix(state["impedance_matrix"], len(names))
        else:
            _table(state["centroids"], 2, rows=len(names))
            _table(state["links"], 5, max_rows=10_000)
            _matrix(state["demand_matrix"], len(names))
            _text(state["mode_name"])
            _number(state["mode_index"], 0, 2, integer=True)
            if state.get("method", "aon") not in ("aon", "ue"):
                raise ValueError("Método de asignación inválido.")
            for key, default, lower, upper in (
                ("alpha", 0.15, 0, 100),
                ("beta", 4, 1, 20),
                ("tolerance", 0.01, 1e-8, 1),
            ):
                _number(state.get(key, default), lower, upper)
            _number(state.get("iterations", 100), 1, 10000, integer=True)
            _boolean(state.get("comparison", False))


def _boolean(value):
    if type(value) is not bool:
        raise ValueError("Se esperaba un booleano.")


def _safe_tree(value, depth=0):
    if depth > 30:
        raise ValueError("Estructura de archivo demasiado profunda.")
    if value is None or type(value) is bool:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            _text(key)
            _safe_tree(child, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _safe_tree(child, depth + 1)
    elif isinstance(value, str):
        _text(value)
    else:
        _number(value, -1e300, 1e300)


def _calibration(state):
    if not isinstance(state, dict) or state.get("mode") not in ("manual", "estimated"):
        raise ValueError("Estado de calibración inválido.")
    for key in ("records", "applied"):
        if not isinstance(state.get(key), dict):
            raise ValueError("Calibración incompleta.")
    for record in state["records"].values():
        if not isinstance(record, dict):
            raise ValueError("Registro de calibración inválido.")
        headers, rows = record["headers"], record["rows"]
        if not isinstance(headers, list) or not 1 <= len(headers) <= 50:
            raise ValueError("Columnas de calibración inválidas.")
        for header in headers:
            _text(header)
        _table(rows, len(headers), max_rows=30000)
        if not isinstance(record["mapping"], dict):
            raise ValueError("Mapeo de columnas inválido.")
        for value in record["mapping"].values():
            _text(value)
        _text(record["filename"])
        if record.get("result") is not None:
            _calibration_result(record["result"])
    for result in state["applied"].values():
        _calibration_result(result)


def _calibration_result(result):
    if result["model"] not in (
        "ols",
        "poisson",
        "negative_binomial",
        "mnl",
        "exponential",
        "power",
        "combined",
    ):
        raise ValueError("Modelo estadístico inválido.")
    for key in ("parameters", "standard_errors", "metrics"):
        if not isinstance(result[key], dict):
            raise ValueError("Resultados estadísticos incompletos.")
        for name, value in result[key].items():
            _text(name)
            _number(value, -1e300, 1e300)
    if not isinstance(result["confidence_intervals"], dict):
        raise ValueError("Intervalos inválidos.")
    for interval in result["confidence_intervals"].values():
        if len(interval) != 2:
            raise ValueError("Intervalo incompatible.")
        for value in interval:
            _number(value, -1e300, 1e300)
    for key in ("observed", "predicted"):
        if not isinstance(result[key], (list, tuple)) or len(result[key]) > 30000:
            raise ValueError("Diagnóstico demasiado grande.")
        for value in result[key]:
            _number(value, -1e300, 1e300)
    for note in result["warnings"]:
        _text(note)
    _boolean(result["converged"])


def _text(value: object) -> None:
    if not isinstance(value, str) or len(value) > 10_000:
        raise ValueError("Texto inválido o demasiado largo.")


def _number(value: object, minimum: float, maximum: float, *, integer: bool = False) -> None:
    if type(value) not in (int, float) or (integer and type(value) is not int):
        raise ValueError("Se esperaba un número.")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Número fuera de rango.")


def _table(value: object, columns: int, *, rows: int | None = None, max_rows: int = 100) -> int:
    if not isinstance(value, list) or not 1 <= len(value) <= max_rows:
        raise ValueError("Tabla vacía o demasiado grande.")
    if rows is not None and len(value) != rows:
        raise ValueError("Dimensiones de tabla incompatibles.")
    for row in value:
        if not isinstance(row, list) or len(row) != columns:
            raise ValueError("Columnas de tabla incompatibles.")
        for cell in row:
            _text(cell)
    return len(value)


def _matrix(value: object, size: int) -> None:
    if not isinstance(value, list) or len(value) != size:
        raise ValueError("Dimensiones de matriz incompatibles.")
    for row in value:
        if not isinstance(row, list) or len(row) != size:
            raise ValueError("La matriz debe ser cuadrada.")
        for cell in row:
            _number(cell, 0, 1e100)


def load_project(path: str | Path) -> dict:
    """Lee un archivo completo sin cambiar ningún dato de la interfaz."""

    try:
        with Path(path).open("rb") as stream:
            content = stream.read(MAX_PROJECT_BYTES + 1)
        if len(content) > MAX_PROJECT_BYTES:
            raise ProjectError("El archivo .mnet supera el tamaño permitido (10 MB).")
        document = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ProjectError("El archivo .mnet está dañado o no contiene JSON válido.") from error
    validate_project(document)
    if document["format_version"] == 1:
        for section in ("draft", "calculated"):
            for stage, state in document[section].items():
                if stage != "assignment":
                    state.setdefault(
                        "calibration", {"mode": "manual", "records": {}, "applied": {}}
                    )
                if stage == "generation":
                    state.setdefault("production_model", "ols")
                    state.setdefault("attraction_model", "ols")
                elif stage == "distribution":
                    state.setdefault("friction_function", "exponential")
                    state.setdefault("advanced_functions", False)
                    state.setdefault("alpha", 1.0)
                elif stage == "assignment":
                    for key, value in dict(
                        method="aon",
                        alpha=0.15,
                        beta=4.0,
                        tolerance=0.01,
                        iterations=100,
                        comparison=False,
                    ).items():
                        state.setdefault(key, value)
    document["format_version"] = FORMAT_VERSION
    for section in ("draft", "calculated"):
        document[section]["modal"].setdefault("fare_profiles", [])
    document.setdefault("fare_scenarios", [])
    return document


def save_project(path: str | Path, document: dict) -> None:
    """Reemplaza el archivo solo después de completar la escritura correctamente."""

    validate_project(document)
    content = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    if len(content.encode("utf-8")) > MAX_PROJECT_BYTES:
        raise ProjectError("El ejercicio supera el tamaño permitido (10 MB).")
    destination = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def project_document(draft: dict, calculated: dict, analyst: str, tab: int, od: int) -> dict:
    """Construye el documento separando entradas en edición y últimos cálculos válidos."""

    return {
        "format": "MacroNet Transport",
        "format_version": FORMAT_VERSION,
        "app_version": __version__,
        "analyst_name": analyst,
        "draft": draft,
        "calculated": calculated,
        "view": {"tab": tab, "od": od},
    }

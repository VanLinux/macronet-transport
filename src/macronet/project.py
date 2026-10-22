"""Formato .mnet: JSON versionado y escritura atómica, sin objetos ejecutables."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

from macronet import __version__
from macronet.domain.generation import GenerationCoefficients

FORMAT_VERSION = 1
STAGES = ("generation", "distribution", "modal", "assignment")
MAX_PROJECT_BYTES = 10 * 1024 * 1024


class ProjectError(ValueError):
    """Archivo incompatible, incompleto o dañado."""


def validate_project(document: object) -> None:
    """Valida todo antes de modificar el ejercicio abierto, incluidos los borradores."""

    if not isinstance(document, dict) or document.get("format") != "MacroNet Transport":
        raise ProjectError("El archivo no es un ejercicio de MacroNet Transport.")
    if type(document.get("format_version")) is not int or document["format_version"] != 1:
        raise ProjectError("Versión de archivo .mnet incompatible. Actualice MacroNet.")
    try:
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
        _number(view["tab"], 0, 5, integer=True)
        _number(view["od"], 0, sizes[0] ** 2 - 1, integer=True)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ProjectError(
            f"El archivo .mnet contiene datos incompletos o inválidos: {error}"
        ) from error


def _validate_state(stage: str, state: dict) -> None:
    if stage == "generation":
        _table(state["table"], 5)
        names = GenerationCoefficients.__dataclass_fields__
        if set(state["coefficients"]) != set(names):
            raise ValueError("Coeficientes de generación incompletos.")
        for value in state["coefficients"].values():
            _number(value, -1_000_000, 1_000_000)
    elif stage == "distribution":
        size = _table(state["marginals"], 3)
        _table(state["costs"], size, rows=size)
        _number(state["beta"], 0, 100)
        _number(state["tolerance"], 0.000001, 1)
        _number(state["iterations"], 1, 10_000, integer=True)
    else:
        names = state["zone_names"]
        if not isinstance(names, list) or not 1 <= len(names) <= 100:
            raise ValueError("Dimensiones de zonas inválidas.")
        for name in names:
            _text(name)
        if stage == "modal":
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

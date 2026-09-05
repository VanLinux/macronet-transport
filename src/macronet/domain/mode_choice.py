"""Modelo logit multinomial transparente para elección modal."""

from __future__ import annotations

from dataclasses import astuple, dataclass
from math import exp, isfinite
from typing import TypeAlias

Matrix: TypeAlias = tuple[tuple[float, ...], ...]


class ModeChoiceError(ValueError):
    """Indica que los datos no permiten calcular la elección modal."""


@dataclass(frozen=True, slots=True)
class ModeSpecification:
    """Parámetros de una alternativa de transporte."""

    name: str
    alternative_constant: float
    time_multiplier: float
    time_constant: float
    fixed_cost: float
    variable_cost: float


@dataclass(frozen=True, slots=True)
class AlternativeChoiceResult:
    """Resultado de una alternativa para un par origen-destino."""

    mode_name: str
    travel_time: float
    monetary_cost: float
    utility: float
    probability: float
    trips: float


@dataclass(frozen=True, slots=True)
class OdModeChoiceResult:
    """Reparto modal de una celda de la matriz OD."""

    origin: str
    destination: str
    total_trips: float
    alternatives: tuple[AlternativeChoiceResult, ...]


@dataclass(frozen=True, slots=True)
class ModeSummary:
    """Matriz y participación agregada de un modo."""

    mode_name: str
    trip_matrix: Matrix
    total_trips: float
    share: float


@dataclass(frozen=True, slots=True)
class ModeChoiceResult:
    """Resultados completos del modelo logit multinomial."""

    zone_names: tuple[str, ...]
    od_results: tuple[tuple[OdModeChoiceResult, ...], ...]
    mode_summaries: tuple[ModeSummary, ...]
    total_trips: float


def choose_modes(
    zone_names: list[str] | tuple[str, ...],
    trip_matrix: list[list[float]] | Matrix,
    impedance_matrix: list[list[float]] | Matrix,
    modes: list[ModeSpecification] | tuple[ModeSpecification, ...],
    time_coefficient: float,
    cost_coefficient: float,
) -> ModeChoiceResult:
    """Divide cada celda OD entre modos mediante un logit multinomial.

    Para cada modo ``m`` y par ``ij`` se aplican:

    ``time_mij = time_constant_m + time_multiplier_m * c_ij``
    ``cost_mij = fixed_cost_m + variable_cost_m * c_ij``
    ``U_mij = ASC_m + beta_time * time_mij + beta_cost * cost_mij``
    ``P_mij = exp(U_mij) / sum_k(exp(U_kij))``
    """

    names = tuple(name.strip() for name in zone_names)
    trips = tuple(tuple(float(value) for value in row) for row in trip_matrix)
    impedances = tuple(tuple(float(value) for value in row) for row in impedance_matrix)
    alternatives = tuple(modes)
    _validate_inputs(
        names,
        trips,
        impedances,
        alternatives,
        time_coefficient,
        cost_coefficient,
    )

    size = len(names)
    modal_matrices = [
        [[0.0 for _ in range(size)] for _ in range(size)] for _ in alternatives
    ]
    od_rows: list[tuple[OdModeChoiceResult, ...]] = []

    for origin in range(size):
        od_row: list[OdModeChoiceResult] = []
        for destination in range(size):
            impedance = impedances[origin][destination]
            attributes = tuple(
                _calculate_attributes(
                    mode,
                    impedance,
                    time_coefficient,
                    cost_coefficient,
                )
                for mode in alternatives
            )
            probabilities = _softmax(tuple(attribute[2] for attribute in attributes))
            choice_results: list[AlternativeChoiceResult] = []
            for mode_index, (mode, attribute, probability) in enumerate(
                zip(alternatives, attributes, probabilities, strict=True)
            ):
                travel_time, monetary_cost, utility = attribute
                modal_trips = trips[origin][destination] * probability
                modal_matrices[mode_index][origin][destination] = modal_trips
                choice_results.append(
                    AlternativeChoiceResult(
                        mode_name=mode.name,
                        travel_time=travel_time,
                        monetary_cost=monetary_cost,
                        utility=utility,
                        probability=probability,
                        trips=modal_trips,
                    )
                )
            od_row.append(
                OdModeChoiceResult(
                    origin=names[origin],
                    destination=names[destination],
                    total_trips=trips[origin][destination],
                    alternatives=tuple(choice_results),
                )
            )
        od_rows.append(tuple(od_row))

    total_trips = sum(sum(row) for row in trips)
    summaries = tuple(
        _summarize_mode(mode.name, matrix, total_trips)
        for mode, matrix in zip(alternatives, modal_matrices, strict=True)
    )
    return ModeChoiceResult(
        zone_names=names,
        od_results=tuple(od_rows),
        mode_summaries=summaries,
        total_trips=total_trips,
    )


def _calculate_attributes(
    mode: ModeSpecification,
    impedance: float,
    time_coefficient: float,
    cost_coefficient: float,
) -> tuple[float, float, float]:
    travel_time = mode.time_constant + mode.time_multiplier * impedance
    monetary_cost = mode.fixed_cost + mode.variable_cost * impedance
    utility = (
        mode.alternative_constant
        + time_coefficient * travel_time
        + cost_coefficient * monetary_cost
    )
    return travel_time, monetary_cost, utility


def _softmax(utilities: tuple[float, ...]) -> tuple[float, ...]:
    maximum = max(utilities)
    exponentials = tuple(exp(utility - maximum) for utility in utilities)
    denominator = sum(exponentials)
    return tuple(value / denominator for value in exponentials)


def _summarize_mode(name: str, matrix: list[list[float]], total: float) -> ModeSummary:
    immutable_matrix = tuple(tuple(value for value in row) for row in matrix)
    mode_total = sum(sum(row) for row in matrix)
    return ModeSummary(
        mode_name=name,
        trip_matrix=immutable_matrix,
        total_trips=mode_total,
        share=mode_total / total,
    )


def _validate_inputs(
    names: tuple[str, ...],
    trips: Matrix,
    impedances: Matrix,
    modes: tuple[ModeSpecification, ...],
    time_coefficient: float,
    cost_coefficient: float,
) -> None:
    size = len(names)
    if size == 0:
        raise ModeChoiceError("Debe existir al menos una zona.")
    if any(not name for name in names) or len(set(names)) != size:
        raise ModeChoiceError("Las zonas deben tener nombres únicos y no vacíos.")
    if len(trips) != size or any(len(row) != size for row in trips):
        raise ModeChoiceError("La matriz de viajes debe ser cuadrada.")
    if len(impedances) != size or any(len(row) != size for row in impedances):
        raise ModeChoiceError("La matriz de impedancias debe ser cuadrada.")
    if len(modes) < 2:
        raise ModeChoiceError("El modelo requiere al menos dos alternativas.")

    mode_names = tuple(mode.name.strip() for mode in modes)
    if any(not name for name in mode_names) or len(set(mode_names)) != len(mode_names):
        raise ModeChoiceError("Los modos deben tener nombres únicos y no vacíos.")

    matrix_values = tuple(value for row in (*trips, *impedances) for value in row)
    if not all(isfinite(value) for value in matrix_values):
        raise ModeChoiceError("Las matrices deben contener valores finitos.")
    if any(value < 0 for row in trips for value in row):
        raise ModeChoiceError("Los viajes no pueden ser negativos.")
    if any(value < 0 for row in impedances for value in row):
        raise ModeChoiceError("Las impedancias no pueden ser negativas.")
    if sum(sum(row) for row in trips) <= 0:
        raise ModeChoiceError("El total de viajes debe ser mayor que cero.")

    if not all(isfinite(value) for value in (time_coefficient, cost_coefficient)):
        raise ModeChoiceError("Los coeficientes de utilidad deben ser finitos.")
    if time_coefficient > 0 or cost_coefficient > 0:
        raise ModeChoiceError("Los coeficientes de tiempo y costo no pueden ser positivos.")

    for mode in modes:
        values = astuple(mode)[1:]
        if not all(isfinite(value) for value in values):
            raise ModeChoiceError(f"El modo {mode.name} contiene parámetros no finitos.")
        if any(value < 0 for value in values[1:]):
            raise ModeChoiceError(
                f"Los parámetros de tiempo y costo del modo {mode.name} no pueden ser negativos."
            )

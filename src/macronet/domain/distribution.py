"""Modelo gravitacional doblemente restringido para distribuir viajes."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isclose, isfinite
from typing import TypeAlias

Matrix: TypeAlias = tuple[tuple[float, ...], ...]


class DistributionError(ValueError):
    """Indica que los datos no permiten distribuir los viajes."""


@dataclass(frozen=True, slots=True)
class FurnessIteration:
    """Errores marginales al terminar una iteración de balanceo."""

    number: int
    maximum_row_error: float
    maximum_column_error: float


@dataclass(frozen=True, slots=True)
class DistributionResult:
    """Matrices y evidencia de convergencia del modelo gravitacional."""

    zone_names: tuple[str, ...]
    friction_matrix: Matrix
    trip_matrix: Matrix
    row_totals: tuple[float, ...]
    column_totals: tuple[float, ...]
    history: tuple[FurnessIteration, ...]
    converged: bool

    @property
    def iterations(self) -> int:
        return len(self.history)

    @property
    def maximum_error(self) -> float:
        if not self.history:
            return 0.0
        last = self.history[-1]
        return max(last.maximum_row_error, last.maximum_column_error)


def distribute_trips(
    zone_names: list[str] | tuple[str, ...],
    productions: list[float] | tuple[float, ...],
    attractions: list[float] | tuple[float, ...],
    costs: list[list[float]] | tuple[tuple[float, ...], ...],
    beta: float,
    *,
    tolerance: float = 1e-6,
    max_iterations: int = 500,
) -> DistributionResult:
    """Distribuye viajes con fricción exponencial y balanceo de Furness.

    La función de fricción es ``f(c_ij) = exp(-beta * c_ij)``. La matriz de
    fricción se escala alternadamente por filas y columnas hasta reproducir
    las producciones y atracciones objetivo.
    """

    names = tuple(name.strip() for name in zone_names)
    origin_totals = tuple(float(value) for value in productions)
    destination_totals = tuple(float(value) for value in attractions)
    cost_matrix = tuple(tuple(float(value) for value in row) for row in costs)
    _validate_inputs(
        names,
        origin_totals,
        destination_totals,
        cost_matrix,
        beta,
        tolerance,
        max_iterations,
    )

    friction_matrix = tuple(
        tuple(exp(-beta * cost) for cost in row) for row in cost_matrix
    )
    working_matrix = [list(row) for row in friction_matrix]
    history: list[FurnessIteration] = []
    converged = False

    for iteration in range(1, max_iterations + 1):
        _scale_rows(working_matrix, origin_totals)
        _scale_columns(working_matrix, destination_totals)

        row_totals = _row_totals(working_matrix)
        column_totals = _column_totals(working_matrix)
        row_error = max(
            abs(calculated - target)
            for calculated, target in zip(row_totals, origin_totals, strict=True)
        )
        column_error = max(
            abs(calculated - target)
            for calculated, target in zip(
                column_totals,
                destination_totals,
                strict=True,
            )
        )
        history.append(FurnessIteration(iteration, row_error, column_error))
        if max(row_error, column_error) <= tolerance:
            converged = True
            break

    final_rows = _row_totals(working_matrix)
    final_columns = _column_totals(working_matrix)
    return DistributionResult(
        zone_names=names,
        friction_matrix=friction_matrix,
        trip_matrix=tuple(tuple(value for value in row) for row in working_matrix),
        row_totals=final_rows,
        column_totals=final_columns,
        history=tuple(history),
        converged=converged,
    )


def _validate_inputs(
    names: tuple[str, ...],
    productions: tuple[float, ...],
    attractions: tuple[float, ...],
    costs: Matrix,
    beta: float,
    tolerance: float,
    max_iterations: int,
) -> None:
    size = len(names)
    if size == 0:
        raise DistributionError("Debe existir al menos una zona.")
    if any(not name for name in names):
        raise DistributionError("Todas las zonas deben tener un nombre.")
    if len(set(names)) != size:
        raise DistributionError("Los nombres de las zonas deben ser únicos.")
    if len(productions) != size or len(attractions) != size:
        raise DistributionError("Los vectores marginales no coinciden con las zonas.")
    if len(costs) != size or any(len(row) != size for row in costs):
        raise DistributionError("La matriz de impedancias debe ser cuadrada.")

    numeric_values = (*productions, *attractions, *(value for row in costs for value in row))
    if not all(isfinite(value) for value in numeric_values):
        raise DistributionError("Todos los datos deben ser valores finitos.")
    if any(value < 0 for value in (*productions, *attractions)):
        raise DistributionError("Las producciones y atracciones no pueden ser negativas.")
    if any(value < 0 for row in costs for value in row):
        raise DistributionError("Las impedancias no pueden ser negativas.")
    if not isfinite(beta) or beta < 0:
        raise DistributionError("El parámetro beta debe ser finito y no negativo.")
    if not isfinite(tolerance) or tolerance <= 0:
        raise DistributionError("La tolerancia debe ser positiva y finita.")
    if max_iterations < 1:
        raise DistributionError("El número máximo de iteraciones debe ser positivo.")

    total_productions = sum(productions)
    total_attractions = sum(attractions)
    if total_productions <= 0:
        raise DistributionError("El total de viajes debe ser mayor que cero.")
    if not isclose(total_productions, total_attractions, rel_tol=1e-9, abs_tol=tolerance):
        raise DistributionError(
            "Los totales no están balanceados: "
            f"ΣP={total_productions:.6g} y ΣA={total_attractions:.6g}."
        )


def _scale_rows(matrix: list[list[float]], targets: tuple[float, ...]) -> None:
    for index, target in enumerate(targets):
        current = sum(matrix[index])
        if target == 0:
            matrix[index] = [0.0] * len(matrix[index])
        elif current == 0:
            raise DistributionError(f"La fila {index + 1} no puede alcanzar su producción.")
        else:
            factor = target / current
            matrix[index] = [value * factor for value in matrix[index]]


def _scale_columns(matrix: list[list[float]], targets: tuple[float, ...]) -> None:
    for column, target in enumerate(targets):
        current = sum(row[column] for row in matrix)
        if target == 0:
            for row in matrix:
                row[column] = 0.0
        elif current == 0:
            raise DistributionError(f"La columna {column + 1} no puede alcanzar su atracción.")
        else:
            factor = target / current
            for row in matrix:
                row[column] *= factor


def _row_totals(matrix: list[list[float]]) -> tuple[float, ...]:
    return tuple(sum(row) for row in matrix)


def _column_totals(matrix: list[list[float]]) -> tuple[float, ...]:
    return tuple(sum(row[column] for row in matrix) for column in range(len(matrix)))

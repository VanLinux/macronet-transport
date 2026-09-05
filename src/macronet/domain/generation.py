"""Cálculo transparente de generación y atracción de viajes."""

from __future__ import annotations

from dataclasses import astuple, dataclass
from math import isfinite


class GenerationError(ValueError):
    """Indica que los datos no permiten ejecutar el modelo."""


@dataclass(frozen=True, slots=True)
class ZoneInput:
    """Variables explicativas de una zona de análisis."""

    name: str
    households: float
    vehicles: float
    jobs: float
    students: float


@dataclass(frozen=True, slots=True)
class GenerationCoefficients:
    """Coeficientes de los modelos lineales de producción y atracción."""

    production_intercept: float = 0.0
    production_households: float = 2.0
    production_vehicles: float = 1.0
    attraction_intercept: float = 0.0
    attraction_jobs: float = 2.0
    attraction_students: float = 1.0


@dataclass(frozen=True, slots=True)
class ZoneGenerationResult:
    """Resultados calculados para una zona."""

    zone: ZoneInput
    production: float
    attraction_raw: float
    attraction_balanced: float


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Resultados zonales y comprobaciones del sistema."""

    zones: tuple[ZoneGenerationResult, ...]
    total_productions: float
    total_attractions_raw: float
    balance_factor: float
    total_attractions_balanced: float


def calculate_generation(
    zones: list[ZoneInput] | tuple[ZoneInput, ...],
    coefficients: GenerationCoefficients,
) -> GenerationResult:
    """Calcula producciones, atracciones y balancea estas últimas.

    Las ecuaciones aplicadas son:

    ``P_i = b0 + bH * H_i + bV * V_i``
    ``A_i = a0 + aE * E_i + aS * S_i``
    ``A_i_bal = (sum(P) / sum(A)) * A_i``
    """

    if not zones:
        raise GenerationError("Debe existir al menos una zona.")

    coefficients_values = astuple(coefficients)
    if not all(isfinite(value) for value in coefficients_values):
        raise GenerationError("Todos los coeficientes deben ser valores finitos.")

    raw_results: list[tuple[ZoneInput, float, float]] = []
    for zone in zones:
        _validate_zone(zone)
        production = (
            coefficients.production_intercept
            + coefficients.production_households * zone.households
            + coefficients.production_vehicles * zone.vehicles
        )
        attraction = (
            coefficients.attraction_intercept
            + coefficients.attraction_jobs * zone.jobs
            + coefficients.attraction_students * zone.students
        )
        if production < 0 or attraction < 0:
            raise GenerationError(
                f"Los coeficientes producen un resultado negativo en la zona {zone.name}."
            )
        raw_results.append((zone, production, attraction))

    total_productions = sum(result[1] for result in raw_results)
    total_attractions_raw = sum(result[2] for result in raw_results)
    if total_attractions_raw == 0:
        if total_productions == 0:
            balance_factor = 1.0
        else:
            raise GenerationError(
                "No es posible balancear: las atracciones totales son iguales a cero."
            )
    else:
        balance_factor = total_productions / total_attractions_raw

    zone_results = tuple(
        ZoneGenerationResult(
            zone=zone,
            production=production,
            attraction_raw=attraction,
            attraction_balanced=attraction * balance_factor,
        )
        for zone, production, attraction in raw_results
    )
    total_attractions_balanced = sum(result.attraction_balanced for result in zone_results)

    return GenerationResult(
        zones=zone_results,
        total_productions=total_productions,
        total_attractions_raw=total_attractions_raw,
        balance_factor=balance_factor,
        total_attractions_balanced=total_attractions_balanced,
    )


def _validate_zone(zone: ZoneInput) -> None:
    if not zone.name.strip():
        raise GenerationError("Todas las zonas deben tener un nombre.")

    values = (zone.households, zone.vehicles, zone.jobs, zone.students)
    if not all(isfinite(value) for value in values):
        raise GenerationError(f"La zona {zone.name} contiene valores no finitos.")
    if any(value < 0 for value in values):
        raise GenerationError(f"La zona {zone.name} contiene valores negativos.")

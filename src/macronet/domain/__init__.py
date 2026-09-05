"""Entidades y reglas independientes de la interfaz gráfica."""

from macronet.domain.distribution import (
    DistributionError,
    DistributionResult,
    FurnessIteration,
    distribute_trips,
)
from macronet.domain.four_step import FOUR_STEP_SEQUENCE, FourStepStage
from macronet.domain.generation import (
    GenerationCoefficients,
    GenerationError,
    GenerationResult,
    ZoneGenerationResult,
    ZoneInput,
    calculate_generation,
)

__all__ = [
    "DistributionError",
    "DistributionResult",
    "FOUR_STEP_SEQUENCE",
    "FourStepStage",
    "FurnessIteration",
    "GenerationCoefficients",
    "GenerationError",
    "GenerationResult",
    "ZoneGenerationResult",
    "ZoneInput",
    "calculate_generation",
    "distribute_trips",
]

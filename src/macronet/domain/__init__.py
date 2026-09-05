"""Entidades y reglas independientes de la interfaz gráfica."""

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
    "FOUR_STEP_SEQUENCE",
    "FourStepStage",
    "GenerationCoefficients",
    "GenerationError",
    "GenerationResult",
    "ZoneGenerationResult",
    "ZoneInput",
    "calculate_generation",
]

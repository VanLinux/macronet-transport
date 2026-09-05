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
from macronet.domain.mode_choice import (
    AlternativeChoiceResult,
    ModeChoiceError,
    ModeChoiceResult,
    ModeSpecification,
    ModeSummary,
    OdModeChoiceResult,
    choose_modes,
)

__all__ = [
    "AlternativeChoiceResult",
    "DistributionError",
    "DistributionResult",
    "FOUR_STEP_SEQUENCE",
    "FourStepStage",
    "FurnessIteration",
    "GenerationCoefficients",
    "GenerationError",
    "GenerationResult",
    "ModeChoiceError",
    "ModeChoiceResult",
    "ModeSpecification",
    "ModeSummary",
    "OdModeChoiceResult",
    "ZoneGenerationResult",
    "ZoneInput",
    "calculate_generation",
    "choose_modes",
    "distribute_trips",
]

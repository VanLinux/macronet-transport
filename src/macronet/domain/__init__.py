"""Entidades y reglas independientes de la interfaz gráfica."""

from macronet.domain.assignment import (
    AssignmentError,
    AssignmentPath,
    AssignmentResult,
    Link,
    LinkAssignmentResult,
    assign_all_or_nothing,
)
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
    "AssignmentError",
    "AssignmentPath",
    "AssignmentResult",
    "DistributionError",
    "DistributionResult",
    "FOUR_STEP_SEQUENCE",
    "FourStepStage",
    "FurnessIteration",
    "GenerationCoefficients",
    "GenerationError",
    "GenerationResult",
    "Link",
    "LinkAssignmentResult",
    "ModeChoiceError",
    "ModeChoiceResult",
    "ModeSpecification",
    "ModeSummary",
    "OdModeChoiceResult",
    "ZoneGenerationResult",
    "ZoneInput",
    "assign_all_or_nothing",
    "calculate_generation",
    "choose_modes",
    "distribute_trips",
]

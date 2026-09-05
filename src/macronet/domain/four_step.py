"""Definición del recorrido del modelo clásico de cuatro etapas."""

from __future__ import annotations

from enum import Enum


class FourStepStage(Enum):
    """Etapas del modelo en su orden lógico de cálculo."""

    TRIP_GENERATION = ("generation", "Generación y atracción de viajes")
    TRIP_DISTRIBUTION = ("distribution", "Distribución de viajes")
    MODE_CHOICE = ("mode-choice", "Elección modal")
    TRAFFIC_ASSIGNMENT = ("assignment", "Asignación de viajes")

    def __init__(self, slug: str, display_name: str) -> None:
        self.slug = slug
        self.display_name = display_name


FOUR_STEP_SEQUENCE: tuple[FourStepStage, ...] = tuple(FourStepStage)

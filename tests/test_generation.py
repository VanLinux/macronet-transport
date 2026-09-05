import pytest

from macronet.domain.generation import (
    GenerationCoefficients,
    GenerationError,
    ZoneInput,
    calculate_generation,
)


EXAMPLE_ZONES = (
    ZoneInput("Centro", 100, 60, 200, 100),
    ZoneInput("Norte", 120, 80, 100, 150),
    ZoneInput("Sur", 110, 70, 80, 150),
    ZoneInput("Oriente", 120, 90, 120, 100),
)


def test_educational_case_matches_manual_solution() -> None:
    result = calculate_generation(EXAMPLE_ZONES, GenerationCoefficients())

    assert [zone.production for zone in result.zones] == [260, 320, 290, 330]
    assert [zone.attraction_raw for zone in result.zones] == [500, 350, 310, 340]
    assert [zone.attraction_balanced for zone in result.zones] == [400, 280, 248, 272]
    assert result.total_productions == 1200
    assert result.total_attractions_raw == 1500
    assert result.balance_factor == pytest.approx(0.8)
    assert result.total_attractions_balanced == pytest.approx(1200)


@pytest.mark.parametrize("field", ["households", "vehicles", "jobs", "students"])
def test_negative_zonal_variables_are_rejected(field: str) -> None:
    values = {
        "name": "Zona 1",
        "households": 1,
        "vehicles": 1,
        "jobs": 1,
        "students": 1,
    }
    values[field] = -1

    with pytest.raises(GenerationError, match="valores negativos"):
        calculate_generation([ZoneInput(**values)], GenerationCoefficients())


def test_zero_attractions_cannot_balance_positive_productions() -> None:
    zone = ZoneInput("Zona 1", households=10, vehicles=0, jobs=0, students=0)

    with pytest.raises(GenerationError, match="atracciones totales"):
        calculate_generation([zone], GenerationCoefficients())

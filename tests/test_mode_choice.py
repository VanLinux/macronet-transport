import pytest

from macronet.domain.mode_choice import (
    ModeChoiceError,
    ModeSpecification,
    choose_modes,
)

NAMES = ("A", "B")
TRIPS = ((30.0, 20.0), (10.0, 40.0))
IMPEDANCES = ((3.0, 10.0), (10.0, 3.0))
MODES = (
    ModeSpecification("Auto", 0.3, 1.0, 0.0, 5.0, 0.25),
    ModeSpecification("Transporte público", 0.6, 1.35, 5.0, 6.0, 0.0),
    ModeSpecification("Bicicleta", -0.8, 2.2, 0.0, 0.0, 0.0),
)


def test_probabilities_and_modal_trips_close_each_od_cell() -> None:
    result = choose_modes(NAMES, TRIPS, IMPEDANCES, MODES, -0.08, -0.18)

    for origin, row in enumerate(result.od_results):
        for destination, od_result in enumerate(row):
            assert sum(item.probability for item in od_result.alternatives) == pytest.approx(1.0)
            assert sum(item.trips for item in od_result.alternatives) == pytest.approx(
                TRIPS[origin][destination]
            )
    assert sum(mode.total_trips for mode in result.mode_summaries) == pytest.approx(100.0)
    assert sum(mode.share for mode in result.mode_summaries) == pytest.approx(1.0)


def test_identical_modes_with_zero_coefficients_split_equally() -> None:
    modes = (
        ModeSpecification("A", 0.0, 1.0, 0.0, 0.0, 0.0),
        ModeSpecification("B", 0.0, 1.0, 0.0, 0.0, 0.0),
    )
    result = choose_modes(("Z",), ((100.0,),), ((5.0,),), modes, 0.0, 0.0)

    alternatives = result.od_results[0][0].alternatives
    assert [alternative.probability for alternative in alternatives] == pytest.approx((0.5, 0.5))
    assert [alternative.trips for alternative in alternatives] == pytest.approx((50.0, 50.0))


def test_positive_time_coefficient_is_rejected() -> None:
    with pytest.raises(ModeChoiceError, match="no pueden ser positivos"):
        choose_modes(NAMES, TRIPS, IMPEDANCES, MODES, 0.08, -0.18)


def test_negative_trip_value_is_rejected() -> None:
    with pytest.raises(ModeChoiceError, match="viajes no pueden"):
        choose_modes(("Z",), ((-1.0,),), ((1.0,),), MODES[:2], -0.08, -0.18)

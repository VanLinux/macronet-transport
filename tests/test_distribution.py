from math import exp

import pytest

from macronet.domain.distribution import DistributionError, distribute_trips

NAMES = ("Centro", "Norte", "Sur", "Oriente")
PRODUCTIONS = (260.0, 320.0, 290.0, 330.0)
ATTRACTIONS = (400.0, 280.0, 248.0, 272.0)
COSTS = (
    (3.0, 10.0, 15.0, 20.0),
    (10.0, 3.0, 12.0, 18.0),
    (15.0, 12.0, 3.0, 9.0),
    (20.0, 18.0, 9.0, 3.0),
)


def test_gravity_model_reproduces_both_marginals() -> None:
    result = distribute_trips(
        NAMES,
        PRODUCTIONS,
        ATTRACTIONS,
        COSTS,
        beta=0.1,
        tolerance=1e-6,
    )

    assert result.converged
    assert result.row_totals == pytest.approx(PRODUCTIONS, abs=1e-6)
    assert result.column_totals == pytest.approx(ATTRACTIONS, abs=1e-6)
    assert sum(result.row_totals) == pytest.approx(1200.0)
    assert result.friction_matrix[0][0] == pytest.approx(exp(-0.3))
    assert result.friction_matrix[0][3] == pytest.approx(exp(-2.0))


def test_default_precision_converges_within_one_hundred_iterations() -> None:
    result = distribute_trips(NAMES, PRODUCTIONS, ATTRACTIONS, COSTS, beta=0.1)

    assert result.converged
    assert result.iterations == 7
    assert result.maximum_error <= 0.01


def test_zero_beta_produces_independent_distribution() -> None:
    result = distribute_trips(
        ("A", "B"),
        (60.0, 40.0),
        (50.0, 50.0),
        ((1.0, 2.0), (2.0, 1.0)),
        beta=0.0,
    )

    assert result.trip_matrix[0] == pytest.approx((30.0, 30.0))
    assert result.trip_matrix[1] == pytest.approx((20.0, 20.0))


def test_unbalanced_marginals_are_rejected() -> None:
    with pytest.raises(DistributionError, match="no están balanceados"):
        distribute_trips(("A",), (100.0,), (90.0,), ((1.0,),), beta=0.1)


def test_negative_impedance_is_rejected() -> None:
    with pytest.raises(DistributionError, match="impedancias"):
        distribute_trips(("A",), (100.0,), (100.0,), ((-1.0,),), beta=0.1)

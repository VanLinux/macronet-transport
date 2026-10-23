"""Recuperación de parámetros, incertidumbre y rechazo de modelos no identificables."""

import numpy as np
import pytest

from macronet.domain.calibration import (
    CalibrationError,
    fit_distribution,
    fit_generation,
    fit_modal,
)
from macronet.domain.distribution import distribute_trips
from macronet.domain.generation import GenerationCoefficients, ZoneInput, calculate_generation


def test_ols_recovers_coefficients_and_independent_validation():
    rng = np.random.default_rng(7)
    x = rng.uniform(1, 20, (100, 2))
    y = 5 + x @ np.array([2, 3])
    fit = fit_generation(x, y, validation=(x[:5], y[:5]))
    assert list(fit.parameters.values()) == pytest.approx([5, 2, 3])
    assert fit.metrics["R2"] == pytest.approx(1)
    assert fit.metrics["validation_RMSE"] < 1e-10
    assert fit.confidence_intervals["x1"][0] <= 2 + 1e-12
    assert fit.confidence_intervals["x1"][1] >= 2 - 1e-12


def test_bad_regression_data_is_rejected():
    with pytest.raises(CalibrationError, match="colinealidad"):
        fit_generation([[i, 2 * i] for i in range(10)], list(range(10)))
    with pytest.raises(CalibrationError, match="más observaciones"):
        fit_generation([[1, 2], [2, 1]], [5, 6])
    with pytest.raises(CalibrationError, match="no finitos"):
        fit_generation([[1, np.nan]], [1])


@pytest.mark.parametrize("model", ["poisson", "negative_binomial"])
def test_optional_count_models_and_log_link(model):
    rng = np.random.default_rng(42)
    x = rng.uniform(0, 3, (2500, 2))
    mu = np.exp(1 + 0.3 * x[:, 0] + 0.2 * x[:, 1])
    y = rng.poisson(mu) if model == "poisson" else rng.negative_binomial(2, 2 / (2 + mu))
    fit = fit_generation(x, y, model=model)
    assert list(fit.parameters.values()) == pytest.approx([1, 0.3, 0.2], abs=0.12)
    assert fit.metrics["log_likelihood"] < 0
    if model == "negative_binomial":
        assert fit.metrics["NB2_dispersion"] == pytest.approx(0.5, abs=0.1)
        assert fit.metrics["Pearson_dispersion"] == pytest.approx(1, abs=0.15)
    coefficients = GenerationCoefficients(
        production_intercept=1, production_households=0.3, production_vehicles=0.2
    )
    result = calculate_generation(
        [ZoneInput("A", 1, 2, 1, 1)], coefficients, production_model=model
    )
    assert result.total_productions == pytest.approx(np.exp(1.7))


@pytest.mark.parametrize(
    "function,alpha,beta", [("exponential", 1, 0.12), ("power", 1.8, 0), ("combined", 0.8, 0.12)]
)
def test_distribution_fits_complete_gravity_not_isolated_friction(function, alpha, beta):
    costs = ((2, 11, 18), (9, 3, 14), (21, 12, 4))
    names, totals = ("A", "B", "C"), (100, 150, 200)
    observed = distribute_trips(
        names,
        totals,
        totals,
        costs,
        beta,
        friction_function=function,
        alpha=alpha,
        tolerance=1e-9,
        max_iterations=3000,
    ).trip_matrix
    fit = fit_distribution(names, totals, totals, costs, observed, friction_function=function)
    assert fit.metrics["RMSE"] < 1e-4
    if function != "power":
        assert fit.parameters["beta"] == pytest.approx(beta, abs=1e-4)
    if function != "exponential":
        assert fit.parameters["alpha"] == pytest.approx(alpha, abs=1e-4)


def test_mnl_recovers_synthetic_parameters_with_availability():
    rng = np.random.default_rng(24)
    n = 6000
    times, costs = rng.uniform(5, 60, (n, 3)), rng.uniform(0, 30, (n, 3))
    available = np.ones((n, 3))
    available[:500, 2] = 0
    u = np.array([0, 0.5, -0.3]) - 0.08 * times - 0.12 * costs
    u[available == 0] = -np.inf
    weights = np.exp(u - u.max(axis=1, keepdims=True))
    probabilities = weights / weights.sum(axis=1, keepdims=True)
    choices = [rng.choice(3, p=p) for p in probabilities]
    fit = fit_modal(times, costs, choices, available)
    assert fit.parameters["ASC_m1"] == 0
    assert fit.parameters["ASC_m2"] == pytest.approx(0.5, abs=0.12)
    assert fit.parameters["beta_time"] == pytest.approx(-0.08, abs=0.01)
    assert fit.parameters["beta_cost"] == pytest.approx(-0.12, abs=0.015)
    assert fit.metrics["VOT_MXN_h"] == pytest.approx(40, abs=5)
    assert fit.standard_errors["beta_time"] > 0
    available[0, choices[0]] = 0
    with pytest.raises(CalibrationError, match="disponible"):
        fit_modal(times, costs, choices, available)


def test_mnl_rejects_unidentified_attributes():
    x = np.tile([1, 2, 3], (30, 1))
    with pytest.raises(CalibrationError):
        fit_modal(x, x, [0, 1, 2] * 10)

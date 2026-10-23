"""Estimación por etapa, independiente de Qt. Datos observados, nunca resultados sintéticos."""

from __future__ import annotations

import warnings
from dataclasses import asdict, dataclass

import numpy as np
from scipy.optimize import least_squares, minimize
from scipy.special import logsumexp
from scipy.stats import norm

from macronet.domain.distribution import distribute_trips


class CalibrationError(ValueError):
    """Datos insuficientes, modelo no identificado o ajuste no utilizable."""


@dataclass(frozen=True)
class CalibrationResult:
    model: str
    parameters: dict[str, float]
    standard_errors: dict[str, float]
    confidence_intervals: dict[str, tuple[float, float]]
    metrics: dict[str, float]
    observed: tuple[float, ...]
    predicted: tuple[float, ...]
    warnings: tuple[str, ...] = ()
    converged: bool = True

    def to_dict(self) -> dict:
        result = asdict(self)
        for key in ("observed", "predicted", "warnings"):
            result[key] = list(result[key])
        result["confidence_intervals"] = {k: list(v) for k, v in self.confidence_intervals.items()}
        return result


def _array(values, *, ndim: int):
    try:
        result = np.asarray(values, dtype=float)
    except (ValueError, TypeError) as error:
        raise CalibrationError("Las observaciones deben ser numéricas.") from error
    if result.ndim != ndim or not np.isfinite(result).all() or not result.size:
        raise CalibrationError("Dimensiones inválidas o datos faltantes/no finitos.")
    return result


def _errors(y, predicted) -> dict[str, float]:
    return {
        "RMSE": float(np.sqrt(np.mean((y - predicted) ** 2))),
        "MAE": float(np.mean(np.abs(y - predicted))),
    }


def fit_generation(
    features, observed, *, model="ols", feature_names=("x1", "x2"), validation=None
) -> CalibrationResult:
    """OLS (enlace identidad), Poisson o NB2 (enlace log). NB2 estima dispersión."""

    import statsmodels.api as sm

    x, y = _array(features, ndim=2), _array(observed, ndim=1)
    if len(x) != len(y) or x.shape[1] != len(feature_names):
        raise CalibrationError("Las variables explicativas no coinciden con las observaciones.")
    design = np.column_stack((np.ones(len(x)), x))
    extra = 1 if model == "negative_binomial" else 0
    if len(y) <= design.shape[1] + extra:
        raise CalibrationError("Se necesitan más observaciones independientes que parámetros.")
    if np.linalg.matrix_rank(design) != design.shape[1]:
        raise CalibrationError("El modelo no es identificable: colinealidad exacta.")
    if np.any(x < 0) or np.any(y < 0):
        raise CalibrationError("Las variables y los viajes observados no pueden ser negativos.")
    if model not in ("ols", "poisson", "negative_binomial"):
        raise CalibrationError("Modelo de generación desconocido.")
    if model != "ols" and (not np.allclose(y, np.round(y)) or not np.any(y)):
        raise CalibrationError(
            "Poisson y binomial negativa requieren conteos enteros no negativos."
        )
    # Escalar evita confundir falta de identificación con diferencias de unidades.
    center, scale = x.mean(axis=0), x.std(axis=0)
    z = np.column_stack((np.ones(len(x)), (x - center) / scale))
    transform = np.eye(design.shape[1])
    transform[0, 1:] = -center / scale
    transform[1:, 1:] = np.diag(1 / scale)
    notes = []
    if np.linalg.cond(z) > 30:
        notes.append("Colinealidad elevada: revise la estabilidad de los coeficientes.")
    try:
        with (
            warnings.catch_warnings(record=True) as caught,
            np.errstate(over="raise", invalid="raise"),
        ):
            warnings.simplefilter("always")
            if model == "ols":
                fitted = sm.OLS(y, z).fit()
                converged = True
            else:
                estimator = sm.Poisson(y, z) if model == "poisson" else sm.NegativeBinomial(y, z)
                fitted = estimator.fit(method="bfgs", maxiter=1000, disp=False)
                converged = bool(fitted.mle_retvals.get("converged", False))
            p = design.shape[1]
            coefficients = transform @ np.asarray(fitted.params[:p])
            covariance = transform @ np.asarray(fitted.cov_params())[:p, :p] @ transform.T
            predicted = np.asarray(fitted.predict(z))
        if caught:
            notes.append("El estimador emitió advertencias numéricas; revise datos y diagnósticos.")
    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
        raise CalibrationError(
            "No se pudo identificar un ajuste estable con estos datos."
        ) from error
    if (
        not converged
        or not np.isfinite(coefficients).all()
        or not np.isfinite(covariance).all()
        or not np.isfinite(predicted).all()
    ):
        raise CalibrationError("El ajuste no convergió o su incertidumbre no es identificable.")
    names = ("intercept", *feature_names)
    params = dict(zip(names, map(float, coefficients), strict=True))
    se = dict(zip(names, map(float, np.sqrt(np.maximum(0, np.diag(covariance)))), strict=True))
    critical = float(norm.ppf(0.975))
    if model == "ols":
        from scipy.stats import t

        critical = float(t.ppf(0.975, fitted.df_resid))
    ci = {
        name: (value - critical * se[name], value + critical * se[name])
        for name, value in params.items()
    }
    metrics = {**_errors(y, predicted), "n": float(len(y))}
    if model == "ols":
        if np.isfinite(fitted.rsquared):
            metrics["R2"] = float(fitted.rsquared)
        if np.any(predicted < 0):
            notes.append("OLS genera predicciones negativas; no deben truncarse silenciosamente.")
    else:
        metrics.update(log_likelihood=float(fitted.llf), AIC=float(fitted.aic))
        metrics["Pearson_dispersion"] = float(
            np.sum((y - predicted) ** 2 / predicted) / (len(y) - p)
        )
        if model == "negative_binomial":
            dispersion = float(fitted.params[-1])
            if dispersion <= 1e-7 or not np.isfinite(dispersion):
                raise CalibrationError("La dispersión NB2 no está identificada; pruebe Poisson.")
            metrics["NB2_dispersion"] = dispersion
    if validation is not None:
        vx, vy = _array(validation[0], ndim=2), _array(validation[1], ndim=1)
        if vx.shape[1] != x.shape[1] or len(vx) != len(vy) or np.any(vx < 0) or np.any(vy < 0):
            raise CalibrationError("Datos de validación incompatibles.")
        vp = np.column_stack((np.ones(len(vx)), vx)) @ coefficients
        if model != "ols":
            vp = np.exp(vp)
        if not np.isfinite(vp).all():
            raise CalibrationError("Predicción de validación fuera del rango numérico.")
        metrics.update({"validation_" + k: v for k, v in _errors(vy, vp).items()})
        if np.any((vx < x.min(axis=0)) | (vx > x.max(axis=0))):
            notes.append("Validación con extrapolación fuera del rango de entrenamiento.")
    else:
        notes.append("Métricas dentro de muestra; no constituyen validación independiente.")
    return CalibrationResult(
        model,
        params,
        se,
        ci,
        metrics,
        tuple(map(float, y)),
        tuple(map(float, predicted)),
        tuple(notes),
    )


def fit_distribution(
    names,
    productions,
    attractions,
    costs,
    observed,
    *,
    friction_function="exponential",
    tolerance=1e-7,
    max_iterations=3000,
):
    """Mínimos cuadrados OD; cada evaluación resuelve el modelo completo de Furness."""

    obs = _array(observed, ndim=2)
    n = len(names)
    if obs.shape != (n, n) or np.any(obs < 0) or obs.sum() <= 0:
        raise CalibrationError("La OD observada debe ser cuadrada, no negativa y con viajes.")
    if not np.allclose(obs.sum(axis=1), productions, atol=0.01, rtol=1e-6) or not np.allclose(
        obs.sum(axis=0), attractions, atol=0.01, rtol=1e-6
    ):
        raise CalibrationError("Los marginales observados deben coincidir con los de distribución.")
    if friction_function == "exponential":
        keys, start, upper = ("beta",), [0.065], [10.0]
    elif friction_function == "power":
        keys, start, upper = ("alpha",), [1.0], [10.0]
    elif friction_function == "combined":
        keys, start, upper = ("alpha", "beta"), [1.0, 0.065], [10.0, 10.0]
    else:
        raise CalibrationError("Función de fricción desconocida.")

    def predict(values):
        parameters = dict(zip(keys, values, strict=True))
        result = distribute_trips(
            names,
            productions,
            attractions,
            costs,
            parameters.get("beta", 0),
            alpha=parameters.get("alpha", 1),
            friction_function=friction_function,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        if not result.converged:
            raise CalibrationError("Furness no convergió en una evaluación; revise impedancias.")
        return np.asarray(result.trip_matrix)

    fit = least_squares(
        lambda values: (predict(values) - obs).ravel(),
        start,
        bounds=(np.zeros(len(keys)), upper),
        max_nfev=400,
        diff_step=1e-4,
        ftol=1e-10,
        xtol=1e-10,
        gtol=1e-8,
    )
    if not fit.success or np.linalg.matrix_rank(fit.jac, tol=1e-5) < len(keys):
        raise CalibrationError("La fricción no está identificada o el ajuste no convergió.")
    predicted = predict(fit.x)
    notes = [
        "Ajuste dentro de muestra; OD cero se incluye en el objetivo, sin logaritmos.",
        "No se reportan intervalos: las celdas OD tienen restricciones marginales.",
    ]
    if np.any(np.isclose(fit.x, 0, atol=1e-5)) or np.any(np.isclose(fit.x, upper, atol=1e-4)):
        notes.append("Parámetro en frontera del rango [0, 10]; revise especificación y unidades.")
    return CalibrationResult(
        friction_function,
        dict(zip(keys, map(float, fit.x), strict=True)),
        {},
        {},
        {**_errors(obs, predicted), "SSE": float(2 * fit.cost)},
        tuple(map(float, obs.ravel())),
        tuple(map(float, predicted.ravel())),
        tuple(notes),
    )


def fit_modal(times, costs, choices, available=None) -> CalibrationResult:
    """MNL con tres alternativas estables m1/m2/m3; ASC_m1 = 0, βt y βc genéricos."""

    times, costs = _array(times, ndim=2), _array(costs, ndim=2)
    chosen_raw = _array(choices, ndim=1)
    if (
        times.shape != costs.shape
        or times.shape[1] != 3
        or len(times) != len(chosen_raw)
        or not np.equal(chosen_raw, np.floor(chosen_raw)).all()
        or np.any((chosen_raw < 0) | (chosen_raw > 2))
    ):
        raise CalibrationError(
            "MNL requiere tres alternativas y una elección válida por observación."
        )
    chosen = chosen_raw.astype(int)
    avail_raw = np.ones_like(times) if available is None else _array(available, ndim=2)
    if avail_raw.shape != times.shape or not np.isin(avail_raw, [0, 1]).all():
        raise CalibrationError("La disponibilidad debe ser 0 o 1 para cada alternativa.")
    avail = avail_raw.astype(bool)
    if np.any(avail.sum(axis=1) < 2) or not avail[np.arange(len(times)), chosen].all():
        raise CalibrationError("Cada elección necesita al menos dos modos y el elegido disponible.")
    if len(times) <= 4 or set(chosen) != {0, 1, 2}:
        raise CalibrationError(
            "Se requieren más de cuatro observaciones y elecciones de los tres modos."
        )
    if np.any(times < 0) or np.any(costs < 0):
        raise CalibrationError("Tiempo (min) y costo (MXN) deben ser no negativos.")
    scales = np.array([max(times.std(), 1e-6), max(costs.std(), 1e-6)])
    design = np.zeros((*times.shape, 4))
    design[:, 1, 0] = 1
    design[:, 2, 1] = 1
    design[:, :, 2] = times / scales[0]
    design[:, :, 3] = costs / scales[1]

    def evaluate(theta):
        utility = np.einsum("nmk,k->nm", design, theta)
        utility[~avail] = -np.inf
        log_p = utility - logsumexp(utility, axis=1, keepdims=True)
        probabilities = np.exp(log_p)
        value = -log_p[np.arange(len(times)), chosen].sum()
        expected = np.einsum("nm,nmk->nk", probabilities, design)
        gradient = (expected - design[np.arange(len(times)), chosen]).sum(axis=0)
        return value, gradient, probabilities, expected

    fit = minimize(
        lambda theta: evaluate(theta)[:2],
        [0, 0, -0.1, -0.1],
        method="BFGS",
        jac=True,
        options={"maxiter": 1000, "gtol": 1e-6},
    )
    value, gradient, probabilities, expected = evaluate(fit.x)
    if not fit.success and np.linalg.norm(gradient, ord=np.inf) > 1e-5:
        raise CalibrationError("MNL no convergió. Revise muestra o separación perfecta.")
    centered = design - expected[:, None, :]
    information = np.einsum("nm,nmk,nml->kl", probabilities, centered, centered)
    if np.linalg.matrix_rank(information) != 4 or np.linalg.cond(information) > 1e10:
        raise CalibrationError("MNL no identificable: atributos colineales o separación.")
    transform = np.diag([1, 1, 1 / scales[0], 1 / scales[1]])
    theta = transform @ fit.x
    covariance = transform @ np.linalg.inv(information) @ transform.T
    names = ("ASC_m2", "ASC_m3", "beta_time", "beta_cost")
    params = {"ASC_m1": 0.0, **dict(zip(names, map(float, theta), strict=True))}
    se = dict(zip(names, map(float, np.sqrt(np.diag(covariance))), strict=True))
    ci = {k: (params[k] - 1.96 * v, params[k] + 1.96 * v) for k, v in se.items()}
    metrics = {
        "log_likelihood": float(-value),
        "n": float(len(times)),
        "AIC": float(8 + 2 * value),
        "accuracy_in_sample": float(np.mean(probabilities.argmax(axis=1) == chosen)),
    }
    for m in range(3):
        metrics[f"observed_share_m{m + 1}"] = float(np.mean(chosen == m))
        metrics[f"predicted_share_m{m + 1}"] = float(probabilities[:, m].mean())
    notes = [
        "Métricas dentro de muestra; requiere validación con observaciones independientes.",
        "ASC de referencia m1 = 0. Tiempo en min; costo en MXN.",
    ]
    if theta[2] > 0 or theta[3] > 0:
        notes.append(
            "Coeficiente de tiempo/costo positivo: diagnóstico visible, "
            "no aplicable al modelo actual."
        )
    if ci["beta_time"][1] < 0 and ci["beta_cost"][1] < 0:
        metrics["VOT_MXN_h"] = float(60 * theta[2] / theta[3])
    else:
        notes.append("Valor del tiempo omitido: coeficientes no utilizables estadísticamente.")
    return CalibrationResult(
        "mnl",
        params,
        se,
        ci,
        metrics,
        tuple(map(float, chosen)),
        tuple(map(float, probabilities[np.arange(len(times)), chosen])),
        tuple(notes),
    )

"""Tarifas monetarias por modo; las distancias se expresan explícitamente en km."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
from io import StringIO
from math import isfinite

SCHEMES = {
    "legacy": "Cálculo actual",
    "flat": "Tarifa plana",
    "bands": "Intervalos de distancia",
    "per_km": "Por kilómetro",
    "mixed": "Mixta: base + distancia",
}
DISTANCE_SOURCES = {
    "unspecified": "Sin especificar",
    "network": "Sobre la red",
    "estimated": "Estimación entre zonas",
}


def default_profile(names):
    return dict(
        scheme="legacy",
        fixed=0.0,
        rate=0.0,
        bands=[["", "0"]],
        distance_source="unspecified",
        distance_note="",
        zone_names=list(names),
        distances=[[""] * len(names) for _ in names],
    )


def nonnegative(value, label):
    if type(value) not in (float, int) or not isfinite(value) or not 0 <= value <= 1e12:
        raise ValueError(f"{label}: se requiere un número finito entre 0 y 10¹².")
    return float(value)


def decimal(text, label):
    try:
        value = float(text.strip().replace(",", "."))
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{label}: falta un valor numérico.") from error
    return nonnegative(value, label)


def validate_profiles(profiles, *, count=3):
    """Valida la estructura guardada, admitiendo celdas todavía en edición."""
    if not isinstance(profiles, list) or len(profiles) not in (0, count):
        raise ValueError("Debe existir una configuración tarifaria por modo.")
    for profile in profiles:
        if profile["scheme"] not in SCHEMES or profile["distance_source"] not in DISTANCE_SOURCES:
            raise ValueError("Esquema tarifario u origen de distancias inválido.")
        nonnegative(profile["fixed"], "Tarifa base")
        nonnegative(profile["rate"], "Tarifa por km")
        if not isinstance(profile["distance_note"], str):
            raise ValueError("Indique la procedencia de las distancias como texto.")
        names = profile["zone_names"]
        if (
            not isinstance(names, list)
            or not 1 <= len(names) <= 100
            or any(not isinstance(name, str) or not name for name in names)
            or len(set(names)) != len(names)
        ):
            raise ValueError("Zonas de la matriz de distancias inválidas.")
        for key, width, maximum in (("bands", 2, 100), ("distances", len(names), len(names))):
            rows = profile[key]
            if not isinstance(rows, list) or not 1 <= len(rows) <= maximum:
                raise ValueError("Tabla tarifaria vacía o demasiado grande.")
            if key == "distances" and len(rows) != len(names):
                raise ValueError("La matriz de distancias debe ser cuadrada.")
            if any(
                not isinstance(row, list)
                or len(row) != width
                or any(not isinstance(cell, str) for cell in row)
                for row in rows
            ):
                raise ValueError("Las celdas tarifarias deben ser texto editable.")


@dataclass(frozen=True)
class FareDetails:
    scheme: str
    fixed: float
    rate: float
    bands: tuple[tuple[float | None, float], ...]
    distance_source: str
    distance_note: str
    distances: tuple[tuple[float, ...], ...] | None
    costs: tuple[tuple[float, ...], ...]


def resolve_fares(profiles, names, modes, impedance):
    """Un esquema activo sustituye el costo anterior completo, sin sumarlo otra vez."""
    validate_profiles(profiles, count=len(modes))
    resolved = []
    for index, mode in enumerate(modes):
        profile = profiles[index] if profiles else default_profile(names)
        scheme = profile["scheme"]
        bands, distances = [], None
        if scheme == "bands":
            previous = 0.0
            for k, (upper, fare) in enumerate(profile["bands"]):
                limit = decimal(upper, "Límite superior (km)") if upper.strip() else None
                if limit is None and k != len(profile["bands"]) - 1:
                    raise ValueError("El intervalo sin límite debe ser el último.")
                if limit is not None and limit <= previous:
                    raise ValueError("Los límites superiores deben ser positivos y crecientes.")
                bands.append((limit, decimal(fare, "Tarifa del intervalo (MXN)")))
                if limit is not None:
                    previous = limit
            if bands[-1][0] is not None:
                raise ValueError(
                    "Deje vacío el límite del último intervalo para cubrir toda distancia."
                )
        if scheme in ("bands", "per_km", "mixed"):
            if profile["zone_names"] != list(names):
                raise ValueError("Revise las zonas de la matriz de distancias del modo.")
            if profile["distance_source"] == "unspecified":
                raise ValueError("Especifique si las distancias son sobre red o estimadas.")
            distances = tuple(
                tuple(
                    decimal(cell, f"Distancia {names[i]} → {names[j]} (km)")
                    for j, cell in enumerate(row)
                )
                for i, row in enumerate(profile["distances"])
            )
        costs = []
        for i in range(len(names)):
            row = []
            for j in range(len(names)):
                distance = distances[i][j] if distances is not None else 0
                if scheme == "legacy":
                    value = mode.fixed_cost + mode.variable_cost * impedance[i][j]
                elif scheme == "flat":
                    value = profile["fixed"]
                elif scheme == "bands":
                    value = next(
                        fare for upper, fare in bands if upper is None or distance <= upper
                    )
                else:
                    value = profile["rate"] * distance + (
                        profile["fixed"] if scheme == "mixed" else 0
                    )
                if not isfinite(value) or value < 0:
                    raise ValueError("El costo monetario calculado no es finito o es negativo.")
                row.append(value)
            costs.append(tuple(row))
        resolved.append(
            FareDetails(
                scheme,
                profile["fixed"],
                profile["rate"],
                tuple(bands),
                profile["distance_source"],
                profile["distance_note"],
                distances,
                tuple(costs),
            )
        )
    return tuple(resolved)


def sync_zones(profiles, old_names, new_names):
    """El editor de zonas conserva posiciones al renombrar; cambios de dimensión exigen revisión."""
    result = copy.deepcopy(profiles)
    for profile in result:
        if profile["zone_names"] == list(old_names):
            profile["zone_names"] = list(new_names)
            if len(old_names) != len(new_names):
                profile["distances"] = [[""] * len(new_names) for _ in new_names]
                profile["distance_source"] = "unspecified"
    return result


def distance_csv(names, distances=None):
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("Origen / destino (km)", *names))
    for i, name in enumerate(names):
        writer.writerow((name, *(distances[i] if distances is not None else [""] * len(names))))
    return output.getvalue()


def parse_distance_csv(text, names):
    rows = list(csv.reader(StringIO(text.lstrip("\ufeff"))))
    if not rows or rows[0] != ["Origen / destino (km)", *names] or len(rows) != len(names) + 1:
        raise ValueError("Use la plantilla de distancias en km con las mismas zonas y orden.")
    values = []
    for i, row in enumerate(rows[1:]):
        if len(row) != len(names) + 1 or row[0] != names[i]:
            raise ValueError("Las filas de distancias no corresponden a las zonas del ejercicio.")
        for value in row[1:]:
            decimal(value, "Distancia CSV (km)")
        values.append(row[1:])
    return values

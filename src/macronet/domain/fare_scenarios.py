"""Instantáneas independientes para comparar cambios tarifarios con la misma OD."""

import copy
import json

from macronet.domain.mode_choice import ModeSpecification, choose_modes

CONTEXT_KEYS = (
    "zone_names",
    "trip_matrix",
    "impedance_matrix",
    "modes",
    "time_coefficient",
    "cost_coefficient",
)


def evaluate_snapshot(inputs):
    modes = tuple(
        ModeSpecification(row[0].strip(), *(float(cell.replace(",", ".")) for cell in row[1:]))
        for row in inputs["modes"]
    )
    return choose_modes(
        inputs["zone_names"],
        inputs["trip_matrix"],
        inputs["impedance_matrix"],
        modes,
        inputs["time_coefficient"],
        inputs["cost_coefficient"],
        fare_profiles=inputs.get("fare_profiles", []),
    )


def context_key(inputs):
    """Compara valores numéricos, no diferencias de escritura como 6 y 6.0."""
    context = {key: copy.deepcopy(inputs[key]) for key in CONTEXT_KEYS}
    context["modes"] = [
        [row[0].strip(), *(float(cell.replace(",", ".")) for cell in row[1:])]
        for row in context["modes"]
    ]
    return json.dumps(context, sort_keys=True, ensure_ascii=False)


def compare_scenarios(scenarios):
    if not scenarios:
        return []
    if len({context_key(s["inputs"]) for s in scenarios}) != 1:
        raise ValueError(
            "Los escenarios tienen OD, tiempos, modos o coeficientes diferentes. "
            "Guarde escenarios con la misma base para aislar el efecto de las tarifas."
        )
    for index in range(len(scenarios[0]["inputs"]["modes"])):
        distance_contexts = set()
        for scenario in scenarios:
            profiles = scenario["inputs"].get("fare_profiles", [])
            if profiles and profiles[index]["scheme"] in ("bands", "per_km", "mixed"):
                profile = profiles[index]
                distance_contexts.add(
                    json.dumps(
                        dict(
                            zone_names=profile["zone_names"],
                            source=profile["distance_source"],
                            distances=[
                                [float(cell.replace(",", ".")) for cell in row]
                                for row in profile["distances"]
                            ],
                        ),
                        sort_keys=True,
                    )
                )
        if len(distance_contexts) > 1:
            raise ValueError(
                "Las distancias o su origen son diferentes. Mantenga la misma "
                "matriz por modo para aislar el efecto de la tarifa."
            )
    results = [evaluate_snapshot(s["inputs"]) for s in scenarios]
    base = results[0]
    return [
        dict(
            scenario=scenario["name"],
            mode=current.mode_name,
            trips=current.total_trips,
            share=current.share,
            delta_trips=current.total_trips - original.total_trips,
            delta_pp=100 * (current.share - original.share),
        )
        for scenario, result in zip(scenarios, results, strict=True)
        for current, original in zip(result.mode_summaries, base.mode_summaries, strict=True)
    ]

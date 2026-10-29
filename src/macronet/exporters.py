"""Exportadores de resultados de MacroNet en formatos abiertos."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

import networkx as nx

from macronet.domain.assignment import AssignmentResult
from macronet.domain.distribution import DistributionResult
from macronet.domain.fare_scenarios import compare_scenarios, evaluate_snapshot
from macronet.domain.fares import DISTANCE_SOURCES, SCHEMES
from macronet.domain.generation import GenerationResult
from macronet.domain.mode_choice import ModeChoiceResult


def build_od_csv(result: DistributionResult) -> str:
    """Devuelve la matriz OD con sus marginales como CSV interoperable."""

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("Origen / destino", *result.zone_names, "Total origen"))
    for name, row, total in zip(
        result.zone_names,
        result.trip_matrix,
        result.row_totals,
        strict=True,
    ):
        writer.writerow((name, *(f"{value:.6f}" for value in row), f"{total:.6f}"))
    writer.writerow(
        (
            "Total destino",
            *(f"{value:.6f}" for value in result.column_totals),
            f"{sum(result.row_totals):.6f}",
        )
    )
    return output.getvalue()


def save_od_csv(path: str | Path, result: DistributionResult) -> None:
    """Guarda una matriz OD en UTF-8 con BOM para facilitar su apertura en hojas de cálculo."""

    Path(path).write_text(build_od_csv(result), encoding="utf-8-sig", newline="")


def build_modal_csv(result: ModeChoiceResult) -> str:
    """Exporta las tres matrices en un CSV, con un bloque y marginales por modo."""

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("Modo", "Origen / destino", *result.zone_names, "Total origen"))
    for mode in result.mode_summaries:
        for name, row in zip(result.zone_names, mode.trip_matrix, strict=True):
            writer.writerow(
                (mode.mode_name, name, *(format(v, ".12g") for v in row), format(sum(row), ".12g"))
            )
        totals = (sum(column) for column in zip(*mode.trip_matrix, strict=True))
        writer.writerow(
            (
                mode.mode_name,
                "Total destino",
                *(format(v, ".12g") for v in totals),
                format(mode.total_trips, ".12g"),
            )
        )
    return output.getvalue()


def save_modal_csv(path: str | Path, result: ModeChoiceResult) -> None:
    """Guarda todas las matrices modales en UTF-8 con BOM."""

    Path(path).write_text(build_modal_csv(result), encoding="utf-8-sig", newline="")


def build_fare_csv(scenarios: list[dict]) -> str:
    """Costos y distancias de cada instantánea; todos los importes activos son MXN."""
    if not scenarios:
        raise ValueError("Guarde al menos un escenario para exportar.")
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "Escenario",
            "Modo",
            "Esquema",
            "Origen",
            "Destino",
            "Distancia_km",
            "Origen_distancia",
            "Fuente_distancia",
            "Costo_MXN",
            "Tiempo_min",
            "Utilidad",
            "Probabilidad",
            "Viajes",
            "Total_OD",
            "Tarifa_base_MXN",
            "MXN_por_km",
            "Intervalos_limite_km_tarifa_MXN",
            "Beta_t",
            "Beta_c",
            "ASC",
            "Costo_fijo_actual",
            "Costo_variable_por_unidad_impedancia_actual",
        )
    )
    for scenario in scenarios:
        inputs = scenario["inputs"]
        result = evaluate_snapshot(inputs)
        for i, row in enumerate(result.od_results):
            for j, od in enumerate(row):
                for k, alternative in enumerate(od.alternatives):
                    detail = result.fare_details[k] if result.fare_details else None
                    writer.writerow(
                        (
                            scenario["name"],
                            alternative.mode_name,
                            detail.scheme if detail else "legacy",
                            od.origin,
                            od.destination,
                            detail.distances[i][j]
                            if detail and detail.distances is not None
                            else "",
                            detail.distance_source
                            if detail and detail.distances is not None
                            else "",
                            detail.distance_note if detail and detail.distances is not None else "",
                            alternative.monetary_cost,
                            alternative.travel_time,
                            alternative.utility,
                            alternative.probability,
                            alternative.trips,
                            od.total_trips,
                            detail.fixed if detail and detail.scheme in ("flat", "mixed") else "",
                            detail.rate if detail and detail.scheme in ("per_km", "mixed") else "",
                            json.dumps(detail.bands, ensure_ascii=False)
                            if detail and detail.bands
                            else "",
                            inputs["time_coefficient"],
                            inputs["cost_coefficient"],
                            inputs["modes"][k][1],
                            inputs["modes"][k][4],
                            inputs["modes"][k][5],
                        )
                    )
    return output.getvalue()


def build_assignment_csv(
    result: AssignmentResult,
    comparison: tuple[AssignmentResult, AssignmentResult] | None = None,
) -> str:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "Metodo",
            "Arco",
            "Desde",
            "Hasta",
            "t0_min",
            "Capacidad_por_periodo",
            "Flujo_por_periodo",
            "v_c",
            "Tiempo_min",
            "Funcion_tiempo",
            "Convergio_UE",
            "Brecha_relativa",
            "Actualizaciones_UE",
            "Tiempo_total_veh_min",
            "Media_interzonal_min",
        )
    )
    for current in comparison or (result,):
        for item in current.link_results:
            writer.writerow(
                (
                    current.method,
                    item.link.link_id,
                    item.link.tail,
                    item.link.head,
                    item.link.free_flow_time,
                    item.link.capacity,
                    item.volume,
                    item.volume_capacity_ratio,
                    item.travel_time,
                    current.cost_function,
                    "" if current.converged is None else current.converged,
                    "" if current.relative_gap is None else current.relative_gap,
                    len(current.history) - 1 if current.history else "",
                    current.total_travel_time,
                    current.mean_travel_time,
                )
            )
    return output.getvalue()


def save_assignment_csv(path, result, comparison=None) -> None:
    Path(path).write_text(
        build_assignment_csv(result, comparison), encoding="utf-8-sig", newline=""
    )


def build_assignment_graph(
    result: AssignmentResult,
    zone_nodes: tuple[str, ...],
    mode_name: str,
) -> nx.MultiDiGraph:
    """Construye un grafo dirigido con atributos completos para exportar a GraphML."""

    graph = nx.MultiDiGraph()
    graph.graph.update(
        {
            "name": "Red asignada de MacroNet Transport",
            "mode": mode_name,
            "assignment": "Wardrop UE" if result.method == "ue" else "Todo-o-Nada",
            "cost_function": result.cost_function,
        }
    )
    zones_by_node = dict(zip(zone_nodes, result.zone_names, strict=True))
    nodes = {item.link.tail for item in result.link_results} | {
        item.link.head for item in result.link_results
    }
    for node in sorted(nodes):
        zone = zones_by_node.get(node, "")
        graph.add_node(
            node,
            label=node,
            is_centroid=node in zones_by_node,
            zone=zone,
        )

    for item in result.link_results:
        ratio = item.volume_capacity_ratio
        if ratio > 1.0:
            status = "sobre_capacidad"
        elif ratio > 0.8:
            status = "proximo_a_capacidad"
        else:
            status = "con_holgura"
        graph.add_edge(
            item.link.tail,
            item.link.head,
            key=item.link.link_id,
            id=item.link.link_id,
            label=item.link.link_id,
            free_flow_time=item.link.free_flow_time,
            travel_time=item.travel_time,
            capacity=item.link.capacity,
            flow=item.volume,
            volume_capacity_ratio=ratio,
            status=status,
        )
    return graph


def save_assignment_graphml(
    path: str | Path,
    result: AssignmentResult,
    zone_nodes: tuple[str, ...],
    mode_name: str,
) -> None:
    """Guarda la red asignada como GraphML compatible con Gephi y NetworkX."""

    graph = build_assignment_graph(result, zone_nodes, mode_name)
    nx.write_graphml(graph, path, encoding="utf-8", prettyprint=True)


def build_summary_tex(
    generation: GenerationResult,
    distribution: DistributionResult,
    mode_choice: ModeChoiceResult,
    assignment: AssignmentResult,
    assigned_mode: str,
    analyst_name: str,
    *,
    comparison: tuple[AssignmentResult, AssignmentResult] | None = None,
    calibration: dict | None = None,
    microsimulation: dict | None = None,
    fare_scenarios: list[dict] | None = None,
) -> str:
    """Crea un informe LaTeX autocontenido con los resultados esenciales."""

    if not analyst_name.strip():
        raise ValueError("Escriba el nombre del usuario que realizó el análisis.")
    critical_link = max(
        assignment.link_results,
        key=lambda item: item.volume_capacity_ratio,
    )
    overloaded = sum(item.volume_capacity_ratio > 1.0 for item in assignment.link_results)
    lines = [
        r"\documentclass[11pt,letterpaper]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{amsmath}",
        r"\usepackage{booktabs}",
        r"\usepackage[letterpaper,margin=2.5cm]{geometry}",
        r"\title{Resumen del modelo de cuatro etapas}",
        r"\author{Usuario: "
        + _latex_escape(analyst_name.strip())
        + r"\\MacroNet Transport\\Desarrollador: Héctor Benítez García}",
        r"\date{\today}",
        r"\begin{document}",
        r"\maketitle",
        r"\section{Generación y atracción}",
        (
            "El sistema produjo "
            f"{generation.total_productions:.2f} viajes. Las atracciones iniciales "
            f"sumaron {generation.total_attractions_raw:.2f} y se balancearon con "
            f"$F={generation.balance_factor:.6f}$ hasta "
            f"{generation.total_attractions_balanced:.2f} viajes."
        ),
        r"\begin{center}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Zona & Producción $P_i$ & Atracción $A_i$ & Balanceada $A_i^*$ \\",
        r"\midrule",
    ]
    if mode_choice.fare_details or fare_scenarios:
        lines.insert(lines.index(r"\begin{document}"), r"\usepackage{longtable}")
    for item in generation.zones:
        lines.append(
            f"{_latex_escape(item.zone.name)} & {item.production:.2f} & "
            f"{item.attraction_raw:.2f} & {item.attraction_balanced:.2f} \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{center}",
            r"\section{Distribución}",
            (
                "El modelo gravitacional doblemente restringido "
                f"{'convergió' if distribution.converged else 'no convergió'} en "
                f"{distribution.iterations} iteraciones, con un error máximo de "
                f"{distribution.maximum_error:.6g} viajes. La matriz OD conserva "
                f"{sum(distribution.row_totals):.2f} viajes."
            ),
            r"\section{Elección modal}",
            r"\begin{center}",
            r"\begin{tabular}{lrr}",
            r"\toprule",
            r"Modo & Viajes & Participación \\",
            r"\midrule",
        ]
    )
    for mode in mode_choice.mode_summaries:
        lines.append(
            f"{_latex_escape(mode.mode_name)} & {mode.total_trips:.2f} & "
            f"{100 * mode.share:.2f}\\% \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{center}",
            r"\section{Asignación}",
            (
                f"Se asignó la matriz del modo {_latex_escape(assigned_mode)} mediante "
                f"{'Wardrop UE (Frank--Wolfe)' if assignment.method == 'ue' else 'Todo-o-Nada'}. "
                "La demanda total fue "
                f"{assignment.total_demand:.2f}; {assignment.assigned_demand:.2f} viajes "
                f"fueron interzonales y {assignment.intrazonal_demand:.2f}, intrazonales."
            ),
            (
                f"El arco crítico fue {_latex_escape(critical_link.link.link_id)} "
                f"({_latex_escape(critical_link.link.tail)} $\\rightarrow$ "
                f"{_latex_escape(critical_link.link.head)}), con "
                f"$v/c={critical_link.volume_capacity_ratio:.3f}$. Se identificaron "
                f"{overloaded} arcos con $v/c>1$."
            ),
            r"\begin{center}",
            r"\begin{tabular}{lrrrr}",
            r"\toprule",
            r"Arco & Tiempo & Capacidad & Flujo & $v/c$ \\",
            r"\midrule",
        ]
    )
    for item in assignment.link_results:
        lines.append(
            f"{_latex_escape(item.link.link_id)} & {item.travel_time:.2f} & "
            f"{item.link.capacity:.2f} & {item.volume:.2f} & "
            f"{item.volume_capacity_ratio:.3f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{center}"])
    if assignment.method == "ue":
        lines.extend(
            [
                r"\subsection{Equilibrio y convergencia}",
                r"$t_a=t_a^0[1+\alpha(v_a/C_a)^\beta]$. "
                f"$\\alpha={assignment.alpha}$, $\\beta={assignment.beta}$. "
                f"Tolerancia: {assignment.tolerance}; "
                f"actualizaciones: {len(assignment.history) - 1}. "
                f"{'Convergió' if assignment.converged else 'No convergió'}; "
                f"brecha relativa final: {assignment.relative_gap:.6g}.",
                r"Brecha: $\max(0,\sum_a t_ax_a-\sum_a t_ay_a)/\sum_a t_ax_a$; "
                r"$y$ es la carga de caminos mínimos con los tiempos actuales. "
                "Demanda interzonal nula: brecha cero. Las rutas mínimas finales son referencias, "
                "no un reparto de demanda por ruta.",
                f"Tiempo total: {assignment.total_travel_time:.4f} veh$\\cdot$min. "
                f"Tiempo medio interzonal: {assignment.mean_travel_time:.4f} min.",
            ]
        )
    if comparison:
        lines.extend(
            [
                r"\subsection{Comparación sobre la misma OD y red}",
                "AON elige rutas con tiempos libres; ambos flujos se evalúan con la misma BPR.",
                r"\begin{center}\begin{tabular}{lrrrr}\toprule",
                r"Arco & Flujo AON & Flujo UE & $t$ AON & $t$ UE \\",
                r"\midrule",
            ]
        )
        for a, u in zip(comparison[0].link_results, comparison[1].link_results, strict=True):
            lines.append(
                f"{_latex_escape(a.link.link_id)} & {a.volume:.3f} & {u.volume:.3f} & "
                f"{a.travel_time:.3f} & {u.travel_time:.3f} \\\\"
            )
        lines.extend(
            [r"\bottomrule\end{tabular}\end{center}", "UE no equivale al óptimo del sistema."]
        )
    if calibration:
        lines.append(r"\section{Parámetros y calibración por etapa}")
        _append_parameters_tex(lines, calibration)
    if mode_choice.fare_details or fare_scenarios:
        _append_fares_tex(lines, mode_choice, fare_scenarios or [])
    if microsimulation and microsimulation.get("last_run"):
        _append_sumo_tex(lines, microsimulation)
    lines.extend(
        [
            r"\section{Alcance}",
            (
                "Los resultados pertenecen a un caso educativo. La asignación Todo-o-Nada "
                "usa costos fijos. Wardrop requiere funciones separables no decrecientes, "
                "red dirigida válida y demanda/capacidades del mismo periodo. "
                "Los parámetros de ejemplo no son calibraciones locales."
            ),
            r"\end{document}",
            "",
        ]
    )
    return "\n".join(lines)


def _fare_description(lines, mode_name, detail):
    lines.append(r"\paragraph{" + _latex_escape(mode_name) + "} " + SCHEMES[detail.scheme] + ". ")
    if detail.scheme in ("flat", "mixed"):
        lines.append(f"Tarifa plana/base: {detail.fixed:.6g} MXN. ")
    if detail.scheme in ("per_km", "mixed"):
        lines.append(f"Cargo: {detail.rate:.6g} MXN/km. ")
    if detail.bands:
        previous = 0
        for k, (upper, fare) in enumerate(detail.bands):
            bound = f"{previous:g} < d" if k else r"0 \leq d"
            if upper is not None:
                bound += r" \leq " + f"{upper:g}"
            lines.append("$" + bound + f"$ km: {fare:g} MXN. ")
            previous = upper
    if detail.distances is not None:
        lines.append(
            "Distancias en km: "
            + DISTANCE_SOURCES[detail.distance_source]
            + ". "
            + _latex_escape(detail.distance_note)
            + ". "
        )
    lines.append(r"\par")


def _append_fares_tex(lines, result, scenarios):
    lines.extend(
        [
            r"\section{Tarifas y costos de viaje}",
            "Los esquemas activos sustituyen el costo monetario anterior del modo. "
            "Tarifas en MXN por persona y viaje; distancias en km, incluidas las intrazonales. "
            "El total OD se mantiene fijo: los escenarios evalúan reparto modal, "
            "sin estimar viajes inducidos ni cambios de destino.",
        ]
    )
    for k, detail in enumerate(result.fare_details):
        if detail.scheme == "legacy":
            continue
        _fare_description(lines, result.mode_summaries[k].mode_name, detail)
        lines.extend(
            [
                r"\begin{longtable}{p{0.25\linewidth}p{0.25\linewidth}rr}\toprule",
                r"Origen & Destino & Distancia (km) & Costo (MXN) \\",
                r"\midrule\endhead",
            ]
        )
        for i, origin in enumerate(result.zone_names):
            for j, destination in enumerate(result.zone_names):
                distance = (
                    f"{detail.distances[i][j]:.6g}" if detail.distances is not None else "---"
                )
                lines.append(
                    _latex_escape(origin)
                    + " & "
                    + _latex_escape(destination)
                    + f" & {distance} & {detail.costs[i][j]:.6g}"
                    + r" \\"
                )
        lines.append(r"\bottomrule\end{longtable}")
    if not scenarios:
        return
    lines.append(r"\subsection{Escenarios tarifarios guardados}")
    try:
        comparison = compare_scenarios(scenarios)
    except ValueError:
        comparison = []
        lines.append(
            "Los escenarios contienen contextos distintos; se muestran resultados "
            "independientes y no se atribuyen sus diferencias sólo a las tarifas."
        )
    delta = {(row["scenario"], row["mode"]): row for row in comparison}
    for scenario in scenarios:
        current = evaluate_snapshot(scenario["inputs"])
        lines.append(r"\subsubsection{" + _latex_escape(scenario["name"]) + "}")
        lines.append(
            f"Total OD: {current.total_trips:.6g}; "
            + r"$\beta_t$="
            + f"{scenario['inputs']['time_coefficient']:.6g}; "
            + r"$\beta_c$="
            + f"{scenario['inputs']['cost_coefficient']:.6g}. "
        )
        for k, mode in enumerate(current.mode_summaries):
            lines.append(
                _latex_escape(mode.mode_name)
                + f": {mode.total_trips:.6g} viajes; {100 * mode.share:.4f}"
                + r"\%. "
            )
            if delta:
                row = delta[(scenario["name"], mode.mode_name)]
                lines.append(
                    f"Cambio respecto al primer escenario: {row['delta_trips']:+.6g} viajes; "
                    f"{row['delta_pp']:+.4f} puntos porcentuales. "
                )
            if current.fare_details and current.fare_details[k].scheme != "legacy":
                _fare_description(lines, mode.mode_name, current.fare_details[k])
            lines.append(r"\par")
        lines.append(
            "Las matrices completas de cada instantánea se conservan en el ejercicio "
            "y en la exportación CSV de escenarios."
        )


def _append_sumo_tex(lines, state):
    run = state["last_run"]
    settings = run["inputs"]["settings"]
    lines.extend(
        [
            r"\section{Microsimulación opcional con SUMO}",
            "Instantánea independiente de las cuatro etapas. "
            + (
                "Corresponde a una ejecución anterior; los datos actuales cambiaron."
                if state.get("stale")
                else "Corresponde al escenario registrado en esta ejecución."
            ),
            "Modo: " + _latex_escape(run["inputs"]["source"]["mode_name"]) + ". ",
            f"Periodo de demanda: {settings['period_s']} s; despeje: {settings['clearance_s']} s; "
            f"semilla: {settings['seed']}; ocupación declarada: {settings['occupancy']:.3f} "
            "personas/vehículo (aplicada sólo a viajes-persona). ",
            "Unidades de origen: "
            + _latex_escape(settings["demand_unit"])
            + "; salidas: "
            + _latex_escape(settings["departures"])
            + f"; multiplicador: {settings['multiplier']:.3f}. ",
            _latex_escape(run["methodology"]),
            f"Vehículos generados: {run['generated']}; demanda intracentroide excluida: "
            f"{run['excluded_intrazonal_vehicles']:.4f} vehículos equivalentes; "
            f"ajuste de redondeo: {run['rounding_error']:+.4f} vehículos. ",
        ]
    )
    if run["status"] == "completed":
        stats = run["statistics"]
        lines.extend(
            [r"\begin{center}\begin{tabular}{lr}\toprule", r"Indicador & Valor \\", r"\midrule"]
        )
        for key, label in (
            ("inserted", "Vehículos insertados"),
            ("arrived", "Recorridos completados"),
            ("running", "Vehículos todavía en red"),
            ("pending", "Pendientes de insertar"),
            ("removed", "Retirados sin completar"),
            ("mean_duration_s", "Tiempo medio de recorrido (s)"),
            ("mean_waiting_s", "Espera media (s)"),
            ("mean_time_loss_s", "Pérdida media de tiempo (s)"),
            ("mean_depart_delay_s", "Retraso medio de inserción (s)"),
            ("mean_speed_kmh", "Velocidad agregada (km/h)"),
        ):
            value = stats[key]
            display = f"{value:.3f}" if value is not None else "Sin llegadas"
            lines.append(_latex_escape(label) + " & " + display + r" \\")
        lines.extend(
            [
                r"\bottomrule\end{tabular}\end{center}",
                "Los promedios de viaje incluyen sólo recorridos completados. "
                "La velocidad agregada es distancia total / tiempo total de esos recorridos. "
                "El contraste por arco usa muestras de todo el horizonte, incluido el despeje. "
                "Estos indicadores no certifican equilibrio dinámico ni calibración local.",
            ]
        )
    else:
        lines.append("Escenario preparado sin ejecutar: no hay resultados de microsimulación.")
    lines.append(
        "Versión SUMO: "
        + _latex_escape(run.get("versions", {}).get("sumo", "sin ejecutar"))
        + ". Huella de entradas: "
        + _latex_escape(run["fingerprint"])
        + "."
    )


def _append_parameters_tex(lines: list[str], states: dict) -> None:
    titles = {
        "generation": "Generación y atracción",
        "distribution": "Distribución",
        "modal": "Elección modal",
        "assignment": "Asignación",
    }
    for stage, state in states.items():
        lines.append(r"\subsection{" + titles.get(stage, _latex_escape(stage)) + "}")
        if stage == "generation":
            values = state["coefficients"]
            lines.append(
                "Producción: "
                + _latex_escape(state.get("production_model", "ols"))
                + "; atracción: "
                + _latex_escape(state.get("attraction_model", "ols"))
                + "."
            )
            lines.append("OLS usa enlace identidad; Poisson y NB2 usan enlace logarítmico.")
        elif stage == "distribution":
            function = state.get("friction_function", "exponential")
            values = {"friction_function": function}
            if function != "power":
                values["beta"] = state["beta"]
            if function != "exponential":
                values["alpha"] = state["alpha"]
            lines.append(
                r"Exponencial: $e^{-\beta c}$; potencia: $c^{-\alpha}$; "
                r"combinada: $c^\alpha e^{-\beta c}$. "
                r"$\beta$ en inverso de la unidad de impedancia, $\alpha$ adimensional."
            )
        elif stage == "modal":
            values = {key: state[key] for key in ("time_coefficient", "cost_coefficient")}
            for i, row in enumerate(state["modes"], 1):
                values[f"ASC_m{i} ({row[0]})"] = row[1]
            lines.append(
                "Tiempo en min y costo en MXN para la calibración; "
                "las unidades de los atributos deben corresponder a la aplicación."
            )
        else:
            values = {"method": state.get("method", "aon")}
            if values["method"] == "ue":
                values.update(
                    {key: state[key] for key in ("alpha", "beta", "tolerance", "iterations")}
                )
            elif state.get("comparison"):
                values.update(
                    {"alpha_BPR_comparacion": state["alpha"], "beta_BPR_comparacion": state["beta"]}
                )
        lines.extend(
            [
                r"\begin{center}\begin{tabular}{lr}\toprule",
                r"Parámetro aplicado & Valor \\",
                r"\midrule",
            ]
        )
        for key, value in values.items():
            display = f"{value:.8g}" if isinstance(value, (int, float)) else str(value)
            lines.append(_latex_escape(key) + " & " + _latex_escape(display) + r" \\")
        lines.append(r"\bottomrule\end{tabular}\end{center}")
        panel = state.get("calibration", {})
        applied = panel.get("applied", {})
        lines.append(
            "Procedencia: "
            + (
                "estimación aplicada en los modelos indicados; otros valores manuales o de ejemplo."
                if applied
                else "valores manuales o de ejemplo; no certificados como calibrados."
            )
        )
        for target, result in applied.items():
            record = panel.get("records", {}).get(target, {})
            lines.append(
                r"\paragraph{"
                + _latex_escape(target)
                + "} "
                + _latex_escape(result["model"])
                + ". Datos: "
                + _latex_escape(
                    result.get("source", record).get("filename", "observaciones integradas")
                )
                + "."
            )
            lines.extend(
                [
                    r"\begin{center}\begin{tabular}{lrrr}\toprule",
                    r"Parámetro & Estimación & EE & IC 95\% \\",
                    r"\midrule",
                ]
            )
            for name, value in result["parameters"].items():
                se, ci = (
                    result["standard_errors"].get(name),
                    result["confidence_intervals"].get(name),
                )
                se_text = f"{se:.5g}" if se is not None else "---"
                ci_text = f"[{ci[0]:.5g}, {ci[1]:.5g}]" if ci else "---"
                lines.append(f"{_latex_escape(name)} & {value:.7g} & {se_text} & {ci_text} \\\\")
            lines.append(r"\bottomrule\end{tabular}\end{center}")
            for key, value in result["metrics"].items():
                lines.append(_latex_escape(key) + f": {value:.7g}. ")
            for note in result["warnings"]:
                lines.append(_latex_escape(note) + r"\par")


def save_summary_tex(
    path: str | Path,
    generation: GenerationResult,
    distribution: DistributionResult,
    mode_choice: ModeChoiceResult,
    assignment: AssignmentResult,
    assigned_mode: str,
    analyst_name: str,
    **options,
) -> None:
    """Guarda el resumen como fuente LaTeX UTF-8."""

    content = build_summary_tex(
        generation,
        distribution,
        mode_choice,
        assignment,
        assigned_mode,
        analyst_name,
        **options,
    )
    Path(path).write_text(content, encoding="utf-8")


def _latex_escape(value: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
    return "".join(replacements.get(character, character) for character in value)

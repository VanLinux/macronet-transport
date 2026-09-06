"""Exportadores de resultados de MacroNet en formatos abiertos."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

import networkx as nx

from macronet.domain.assignment import AssignmentResult
from macronet.domain.distribution import DistributionResult
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
            "assignment": "Todo-o-Nada",
        }
    )
    zones_by_node = dict(zip(zone_nodes, result.zone_names, strict=True))
    nodes = {
        item.link.tail for item in result.link_results
    } | {item.link.head for item in result.link_results}
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
) -> str:
    """Crea un informe LaTeX autocontenido con los resultados esenciales."""

    critical_link = max(
        assignment.link_results,
        key=lambda item: item.volume_capacity_ratio,
    )
    overloaded = sum(
        item.volume_capacity_ratio > 1.0 for item in assignment.link_results
    )
    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{amsmath}",
        r"\usepackage{booktabs}",
        r"\usepackage[margin=2.5cm]{geometry}",
        r"\title{Resumen del modelo de cuatro etapas}",
        r"\author{MacroNet Transport\\Desarrollador: Héctor Benítez García}",
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
                "Todo-o-Nada. La demanda total fue "
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
            f"{_latex_escape(item.link.link_id)} & {item.link.free_flow_time:.2f} & "
            f"{item.link.capacity:.2f} & {item.volume:.2f} & "
            f"{item.volume_capacity_ratio:.3f} \\\\"
        )
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{center}",
            r"\section{Alcance}",
            (
                "Los resultados pertenecen a un caso educativo. La asignación Todo-o-Nada "
                "no representa equilibrio de usuario ni actualiza los tiempos por congestión."
            ),
            r"\end{document}",
            "",
        ]
    )
    return "\n".join(lines)


def save_summary_tex(
    path: str | Path,
    generation: GenerationResult,
    distribution: DistributionResult,
    mode_choice: ModeChoiceResult,
    assignment: AssignmentResult,
    assigned_mode: str,
) -> None:
    """Guarda el resumen como fuente LaTeX UTF-8."""

    content = build_summary_tex(
        generation,
        distribution,
        mode_choice,
        assignment,
        assigned_mode,
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

"""Asignación dirigida AON y equilibrio de Wardrop por Frank–Wolfe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from heapq import heappop, heappush
from math import isfinite
from typing import TypeAlias

Matrix: TypeAlias = tuple[tuple[float, ...], ...]


class AssignmentError(ValueError):
    """Indica que la red o la demanda no permiten ejecutar la asignación."""


@dataclass(frozen=True, slots=True)
class Link:
    """Arco dirigido con tiempo de flujo libre y capacidad."""

    link_id: str
    tail: str
    head: str
    free_flow_time: float
    capacity: float


@dataclass(frozen=True, slots=True)
class AssignmentPath:
    """Ruta mínima utilizada por una relación origen-destino."""

    origin: str
    destination: str
    demand: float
    nodes: tuple[str, ...]
    link_ids: tuple[str, ...]
    cost: float


@dataclass(frozen=True, slots=True)
class LinkAssignmentResult:
    """Flujo asignado y nivel de utilización de un arco."""

    link: Link
    volume: float
    volume_capacity_ratio: float
    travel_time: float = 0.0


@dataclass(frozen=True, slots=True)
class AssignmentIteration:
    number: int
    relative_gap: float
    total_travel_time: float


@dataclass(frozen=True, slots=True)
class BPRCost:
    """Tiempo en minutos; flujo y capacidad correspondientes al mismo periodo."""

    alpha: float = 0.15
    beta: float = 4.0

    def __post_init__(self) -> None:
        if not isfinite(self.alpha) or self.alpha < 0:
            raise AssignmentError("α BPR debe ser finito y no negativo.")
        if not isfinite(self.beta) or self.beta < 1:
            raise AssignmentError("β BPR debe ser finito y al menos 1.")

    def __call__(self, link: Link, volume: float) -> float:
        if not isfinite(volume) or volume < 0:
            raise AssignmentError("BPR requiere flujos finitos no negativos.")
        if self.alpha == 0 or volume == 0:
            return link.free_flow_time
        try:
            value = link.free_flow_time * (1 + self.alpha * (volume / link.capacity) ** self.beta)
        except (OverflowError, ZeroDivisionError) as error:
            raise AssignmentError(
                "BPR excede el rango numérico; revise flujo y capacidad."
            ) from error
        if not isfinite(value) or value <= 0:
            raise AssignmentError("BPR produjo un tiempo inválido; revise los parámetros.")
        return value


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    """Flujos y diagnóstico AON/UE; rutas mínimas de referencia en UE."""

    zone_names: tuple[str, ...]
    paths: tuple[AssignmentPath, ...]
    link_results: tuple[LinkAssignmentResult, ...]
    total_demand: float
    assigned_demand: float
    intrazonal_demand: float
    method: str = "aon"
    history: tuple[AssignmentIteration, ...] = ()
    converged: bool | None = None
    alpha: float | None = None
    beta: float | None = None
    tolerance: float | None = None
    max_iterations: int | None = None
    cost_function: str = "fixed"

    @property
    def total_travel_time(self) -> float:
        return sum(item.volume * item.travel_time for item in self.link_results)

    @property
    def mean_travel_time(self) -> float:
        return self.total_travel_time / self.assigned_demand if self.assigned_demand else 0.0

    @property
    def relative_gap(self) -> float | None:
        return self.history[-1].relative_gap if self.history else None


def assign_all_or_nothing(
    zone_names: list[str] | tuple[str, ...],
    zone_nodes: list[str] | tuple[str, ...],
    demand_matrix: list[list[float]] | Matrix,
    links: list[Link] | tuple[Link, ...],
    *,
    link_costs: tuple[float, ...] | None = None,
) -> AssignmentResult:
    """Asigna toda la demanda OD a una ruta mínima de flujo libre."""

    names = tuple(name.strip() for name in zone_names)
    centroids = tuple(node.strip() for node in zone_nodes)
    demand = tuple(tuple(float(value) for value in row) for row in demand_matrix)
    network_links = tuple(links)
    _validate_inputs(names, centroids, demand, network_links)
    costs = link_costs or tuple(link.free_flow_time for link in network_links)
    if len(costs) != len(network_links) or any(not isfinite(c) or c <= 0 for c in costs):
        raise AssignmentError("Los costos de los arcos deben ser positivos y finitos.")
    cost_by_id = dict(zip((link.link_id for link in network_links), costs, strict=True))

    adjacency: dict[str, list[Link]] = {}
    for link in network_links:
        adjacency.setdefault(link.tail, []).append(link)
    for outgoing_links in adjacency.values():
        outgoing_links.sort(key=lambda link: (link.head, link.link_id))

    link_volumes = {link.link_id: 0.0 for link in network_links}
    paths: list[AssignmentPath] = []
    total_demand = sum(sum(row) for row in demand)
    assigned_demand = 0.0
    intrazonal_demand = 0.0

    for origin_index, origin_name in enumerate(names):
        for destination_index, destination_name in enumerate(names):
            trips = demand[origin_index][destination_index]
            if trips == 0:
                continue

            origin_node = centroids[origin_index]
            destination_node = centroids[destination_index]
            if origin_node == destination_node:
                intrazonal_demand += trips
                paths.append(
                    AssignmentPath(
                        origin=origin_name,
                        destination=destination_name,
                        demand=trips,
                        nodes=(origin_node,),
                        link_ids=(),
                        cost=0.0,
                    )
                )
                continue

            cost, nodes, link_ids = _shortest_path(
                origin_node,
                destination_node,
                adjacency,
                cost_by_id,
            )
            if not nodes:
                raise AssignmentError(
                    f"No existe una ruta dirigida entre {origin_name} y {destination_name}."
                )
            assigned_demand += trips
            for link_id in link_ids:
                link_volumes[link_id] += trips
            paths.append(
                AssignmentPath(
                    origin=origin_name,
                    destination=destination_name,
                    demand=trips,
                    nodes=nodes,
                    link_ids=link_ids,
                    cost=cost,
                )
            )

    link_results = tuple(
        LinkAssignmentResult(
            link=link,
            volume=link_volumes[link.link_id],
            volume_capacity_ratio=link_volumes[link.link_id] / link.capacity,
            travel_time=cost_by_id[link.link_id],
        )
        for link in network_links
    )
    if any(
        not isfinite(item.volume_capacity_ratio) or not isfinite(item.volume)
        for item in link_results
    ) or not isfinite(sum(item.volume * item.travel_time for item in link_results)):
        raise AssignmentError("Los flujos o tiempos totales exceden el rango numérico.")
    return AssignmentResult(
        zone_names=names,
        paths=tuple(paths),
        link_results=link_results,
        total_demand=total_demand,
        assigned_demand=assigned_demand,
        intrazonal_demand=intrazonal_demand,
    )


def _shortest_path(
    origin: str,
    destination: str,
    adjacency: dict[str, list[Link]],
    costs: dict[str, float],
) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    queue: list[tuple[float, tuple[str, ...], tuple[str, ...], str]] = [
        (0.0, (origin,), (), origin)
    ]
    best_cost = {origin: 0.0}

    while queue:
        cost, nodes, link_ids, node = heappop(queue)
        if cost > best_cost.get(node, float("inf")):
            continue
        if node == destination:
            return cost, nodes, link_ids

        for link in adjacency.get(node, []):
            new_cost = cost + costs[link.link_id]
            if new_cost >= best_cost.get(link.head, float("inf")):
                continue
            best_cost[link.head] = new_cost
            heappush(
                queue,
                (
                    new_cost,
                    (*nodes, link.head),
                    (*link_ids, link.link_id),
                    link.head,
                ),
            )

    return float("inf"), (), ()


def _validate_inputs(
    names: tuple[str, ...],
    zone_nodes: tuple[str, ...],
    demand: Matrix,
    links: tuple[Link, ...],
) -> None:
    size = len(names)
    if size == 0:
        raise AssignmentError("Debe existir al menos una zona.")
    if any(not name for name in names) or len(set(names)) != size:
        raise AssignmentError("Las zonas deben tener nombres únicos y no vacíos.")
    if len(zone_nodes) != size or any(not node for node in zone_nodes):
        raise AssignmentError("Cada zona debe estar conectada con un nodo de la red.")
    if len(set(zone_nodes)) != len(zone_nodes):
        raise AssignmentError("Cada zona debe utilizar un nodo centroide diferente.")
    if len(demand) != size or any(len(row) != size for row in demand):
        raise AssignmentError("La matriz de demanda debe ser cuadrada.")
    if not links:
        raise AssignmentError("La red debe contener al menos un arco.")

    demand_values = tuple(value for row in demand for value in row)
    if not all(isfinite(value) for value in demand_values):
        raise AssignmentError("La demanda debe contener valores finitos.")
    if any(value < 0 for value in demand_values):
        raise AssignmentError("La demanda no puede contener valores negativos.")
    if not isfinite(sum(demand_values)):
        raise AssignmentError("La suma de demanda excede el rango numérico.")

    link_ids = tuple(link.link_id.strip() for link in links)
    if any(not link_id for link_id in link_ids) or len(set(link_ids)) != len(link_ids):
        raise AssignmentError("Los identificadores de los arcos deben ser únicos.")
    network_nodes: set[str] = set()
    for link in links:
        if not link.tail.strip() or not link.head.strip() or link.tail == link.head:
            raise AssignmentError("Cada arco debe conectar dos nodos diferentes.")
        if not isfinite(link.free_flow_time) or link.free_flow_time <= 0:
            raise AssignmentError(f"El tiempo del arco {link.link_id} debe ser positivo.")
        if not isfinite(link.capacity) or link.capacity <= 0:
            raise AssignmentError(f"La capacidad del arco {link.link_id} debe ser positiva.")
        network_nodes.update((link.tail, link.head))
    if any(node not in network_nodes for node in zone_nodes):
        raise AssignmentError("Todos los centroides deben existir en la red.")


def assign_user_equilibrium(
    zone_names: list[str] | tuple[str, ...],
    zone_nodes: list[str] | tuple[str, ...],
    demand_matrix: list[list[float]] | Matrix,
    links: list[Link] | tuple[Link, ...],
    *,
    alpha: float = 0.15,
    beta: float = 4.0,
    tolerance: float = 0.01,
    max_iterations: int = 100,
    cost_function: Callable[[Link, float], float] | None = None,
) -> AssignmentResult:
    """UE estático, costos separables no decrecientes y búsqueda de paso por bisección.

    Brecha relativa = max(0, sum(t*x)-sum(t*y)) / sum(t*x). Se evalúa en
    el flujo devuelto, también al agotar las actualizaciones. Los caminos de
    salida son mínimos finales de referencia, no el reparto de demanda por ruta.
    Una función alternativa debe ser continua, positiva y no decreciente.
    """

    if not isfinite(tolerance) or not 0 < tolerance <= 1:
        raise AssignmentError("La tolerancia UE debe estar entre 0 (excluido) y 1.")
    if type(max_iterations) is not int or max_iterations < 1:
        raise AssignmentError("El máximo de iteraciones UE debe ser un entero positivo.")
    bpr = BPRCost(alpha, beta)
    cost = cost_function or bpr
    network = tuple(links)
    initial = assign_all_or_nothing(zone_names, zone_nodes, demand_matrix, network)

    def times(volumes):
        values = tuple(float(cost(link, v)) for link, v in zip(network, volumes, strict=True))
        if any(not isfinite(t) or t <= 0 for t in values):
            raise AssignmentError("La función de costo debe devolver tiempos positivos y finitos.")
        return values

    # El inicio usa costos a flujo cero, también para funciones de prueba distintas de BPR.
    zero_times = times([0.0] * len(network))
    initial = assign_all_or_nothing(
        zone_names, zone_nodes, demand_matrix, network, link_costs=zero_times
    )
    x = [item.volume for item in initial.link_results]
    history = []
    for iteration in range(max_iterations + 1):
        t = times(x)
        auxiliary = assign_all_or_nothing(
            zone_names, zone_nodes, demand_matrix, network, link_costs=t
        )
        y = [item.volume for item in auxiliary.link_results]
        total = sum(v * time for v, time in zip(x, t, strict=True))
        shortest = sum(v * time for v, time in zip(y, t, strict=True))
        if not isfinite(total) or not isfinite(shortest):
            raise AssignmentError("El tiempo total excede el rango numérico.")
        gap = max(0.0, (total - shortest) / total) if total else 0.0
        history.append(AssignmentIteration(iteration, gap, total))
        if gap <= tolerance or iteration == max_iterations:
            break
        direction = [b - a for a, b in zip(x, y, strict=True)]

        def derivative(step, current=x, auxiliary_volumes=y, delta=direction):
            trial = [
                (1 - step) * a + step * b for a, b in zip(current, auxiliary_volumes, strict=True)
            ]
            return sum(d * time for d, time in zip(delta, times(trial), strict=True))

        low, high = 0.0, 1.0
        if derivative(1.0) <= 0:
            step = 1.0
        else:
            for _ in range(60):
                step = (low + high) / 2
                if derivative(step) > 0:
                    high = step
                else:
                    low = step
            step = (low + high) / 2
        x = [max(0.0, (1 - step) * a + step * b) for a, b in zip(x, y, strict=True)]

    return replace(
        initial,
        paths=auxiliary.paths,
        link_results=tuple(
            LinkAssignmentResult(link, v, v / link.capacity, time)
            for link, v, time in zip(network, x, t, strict=True)
        ),
        method="ue",
        history=tuple(history),
        converged=gap <= tolerance,
        alpha=alpha if cost_function is None else None,
        beta=beta if cost_function is None else None,
        tolerance=tolerance,
        max_iterations=max_iterations,
        cost_function="bpr" if cost_function is None else "custom",
    )


def evaluate_bpr(result: AssignmentResult, alpha: float, beta: float) -> AssignmentResult:
    """Evalúa los flujos AON con BPR, sin reasignarlos; permite compararlos con UE."""

    cost = BPRCost(alpha, beta)
    evaluated = replace(
        result,
        link_results=tuple(
            replace(item, travel_time=cost(item.link, item.volume)) for item in result.link_results
        ),
        alpha=alpha,
        beta=beta,
        cost_function="bpr_evaluation",
    )
    if not isfinite(evaluated.total_travel_time):
        raise AssignmentError("El tiempo BPR total excede el rango numérico.")
    return evaluated

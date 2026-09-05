"""Asignación Todo-o-Nada sobre una red dirigida."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    """Rutas y flujos resultantes de la asignación Todo-o-Nada."""

    zone_names: tuple[str, ...]
    paths: tuple[AssignmentPath, ...]
    link_results: tuple[LinkAssignmentResult, ...]
    total_demand: float
    assigned_demand: float
    intrazonal_demand: float


def assign_all_or_nothing(
    zone_names: list[str] | tuple[str, ...],
    zone_nodes: list[str] | tuple[str, ...],
    demand_matrix: list[list[float]] | Matrix,
    links: list[Link] | tuple[Link, ...],
) -> AssignmentResult:
    """Asigna toda la demanda OD a una ruta mínima de flujo libre."""

    names = tuple(name.strip() for name in zone_names)
    centroids = tuple(node.strip() for node in zone_nodes)
    demand = tuple(tuple(float(value) for value in row) for row in demand_matrix)
    network_links = tuple(links)
    _validate_inputs(names, centroids, demand, network_links)

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
        )
        for link in network_links
    )
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
            new_cost = cost + link.free_flow_time
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
    if sum(demand_values) <= 0:
        raise AssignmentError("La demanda total debe ser mayor que cero.")

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

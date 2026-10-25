"""Contratos, conversión de unidades y archivos reproducibles para Eclipse SUMO."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from xml.etree import ElementTree as ET

from macronet import __version__
from macronet.domain.assignment import BPRCost, Link, assign_all_or_nothing, assign_user_equilibrium

MAX_VEHICLES = 50_000


class SumoError(ValueError):
    """Datos o herramientas incompatibles con la simulación solicitada."""


class SumoCancelled(SumoError):
    """Ejecución cancelada por el usuario."""


def number(value, lower, upper, label, *, integer=False):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not lower <= value <= upper
        or (integer and type(value) is not int)
    ):
        raise SumoError(f"{label}: valor fuera de rango [{lower}, {upper}].")


@dataclass(frozen=True)
class Settings:
    period_s: int = 3600
    clearance_s: int = 1800
    seed: int = 42
    demand_unit: str = "persons"
    occupancy: float = 1.3
    multiplier: float = 1.0
    departures: str = "uniform"
    timeout_s: int = 300
    confirmed: bool = False

    def validate(self, *, require_confirmation=True):
        for name, lo, hi in (
            ("period_s", 10, 86400),
            ("clearance_s", 0, 86400),
            ("seed", 0, 2147483647),
            ("timeout_s", 5, 3600),
        ):
            number(getattr(self, name), lo, hi, name, integer=True)
        number(self.occupancy, 1, 100, "Ocupación (personas/vehículo)")
        number(self.multiplier, 0.001, 100, "Multiplicador de demanda")
        if self.demand_unit not in ("persons", "vehicles"):
            raise SumoError("Seleccione viajes-persona o vehículos por periodo.")
        if self.departures not in ("uniform", "random") or type(self.confirmed) is not bool:
            raise SumoError("Configuración temporal o confirmación inválida.")
        if require_confirmation and not self.confirmed:
            raise SumoError("Confirme el modo vial, el periodo, las unidades y la geometría.")


@dataclass(frozen=True)
class Node:
    name: str
    x: float
    y: float

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 10000:
            raise SumoError("Identificador de nodo inválido.")
        number(self.x, -1e7, 1e7, "Coordenada X (m)")
        number(self.y, -1e7, 1e7, "Coordenada Y (m)")


@dataclass(frozen=True)
class Road:
    link_id: str
    length_m: float
    speed_kmh: float
    lanes: int

    def validate(self):
        if not isinstance(self.link_id, str) or not self.link_id.strip():
            raise SumoError("Identificador de arco inválido.")
        number(self.length_m, 10, 1e6, "Longitud (m)")
        number(self.speed_kmh, 1, 160, "Velocidad (km/h)")
        number(self.lanes, 1, 10, "Carriles", integer=True)


def validate_saved_state(state):
    """Valida entradas e indicadores guardados; abrir un .mnet nunca ejecuta SUMO."""
    Settings(**state["settings"]).validate(require_confirmation=False)
    if not isinstance(state["bin_directory"], str) or type(state["stale"]) is not bool:
        raise SumoError("Estado de microsimulación inválido.")
    for key, width, maximum in (("nodes", 3, 1000), ("roads", 6, 10000)):
        rows = state[key]
        if not isinstance(rows, list) or len(rows) > maximum:
            raise SumoError("Geometría SUMO demasiado grande.")
        for row in rows:
            if (
                not isinstance(row, list)
                or len(row) != width
                or any(not isinstance(cell, str) for cell in row)
            ):
                raise SumoError("Tabla de geometría SUMO inválida.")
        # Las celdas son borradores: pueden estar vacías o a medio editar, como
        # en las cuatro etapas. Se validan numéricamente al ejecutar, no al guardar.
    result = state["last_run"]
    if result is None:
        return
    if result["format"] != "MacroNet SUMO" or result["status"] not in ("prepared", "completed"):
        raise SumoError("Resultado SUMO incompatible.")
    if not isinstance(result["directory"], str) or not isinstance(result["fingerprint"], str):
        raise SumoError("Procedencia SUMO incompleta.")
    if not isinstance(result["methodology"], str) or not isinstance(result["versions"], dict):
        raise SumoError("Metodología y versión SUMO incompletas.")
    expected_hash = hashlib.sha256(
        json.dumps(result["inputs"], sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    if expected_hash != result["fingerprint"]:
        raise SumoError("La huella no corresponde a las entradas SUMO guardadas.")
    Settings(**result["inputs"]["settings"]).validate()
    for value in result["inputs"]["nodes"]:
        Node(**value).validate()
    for value in result["inputs"]["roads"]:
        Road(**value).validate()
    for key in ("excluded_intrazonal_vehicles", "converted_interzonal", "elapsed_s"):
        number(result[key], 0, 1e100, key)
    number(result["rounding_error"], -0.501, 0.501, "Ajuste de redondeo")
    number(result["generated"], 1, MAX_VEHICLES, "Vehículos generados", integer=True)
    if result["status"] == "prepared":
        return
    if not isinstance(result["versions"]["sumo"], str):
        raise SumoError("Versión del motor SUMO inválida.")
    stats = result["statistics"]
    for key in ("generated", "inserted", "arrived", "running", "pending", "removed"):
        number(stats[key], 0, MAX_VEHICLES, key, integer=True)
    if (
        stats["generated"] != result["generated"]
        or stats["inserted"] + stats["pending"] != stats["generated"]
        or stats["arrived"] + stats["running"] + stats["removed"] != stats["inserted"]
    ):
        raise SumoError("Los indicadores SUMO no conservan el conteo de vehículos.")
    for key in (
        "mean_duration_s",
        "mean_waiting_s",
        "mean_time_loss_s",
        "mean_depart_delay_s",
        "mean_speed_kmh",
    ):
        if (stats[key] is None) != (stats["arrived"] == 0):
            raise SumoError("Promedios SUMO incompatibles con los recorridos completados.")
        if stats[key] is not None:
            number(stats[key], 0, 1e100, key)
    if not isinstance(result["edges"], list) or len(result["edges"]) > 10000:
        raise SumoError("Resultados por arco inválidos.")
    for edge in result["edges"]:
        if not isinstance(edge["link_id"], str):
            raise SumoError("Arco SUMO inválido.")
        for key in (
            "static_vehicles",
            "static_time_min",
            "sumo_entered",
            "sumo_time_min",
            "sumo_speed_kmh",
        ):
            if key in ("static_vehicles", "static_time_min", "sumo_entered") and edge[key] is None:
                raise SumoError("Comparación por arco incompleta.")
            if edge[key] is not None:
                number(edge[key], 0, 1e100, key)
    if not isinstance(result.get("series", []), list) or len(result.get("series", [])) > 401:
        raise SumoError("Serie temporal SUMO inválida.")
    for row in result.get("series", []):
        if not isinstance(row, list) or len(row) != 3:
            raise SumoError("Serie temporal SUMO inválida.")
        for value in row:
            number(value, 0, 1e9, "Serie temporal")


def defaults(source):
    """Geometría esquemática de ejemplo; debe revisarse antes de simular."""
    names = sorted({cell for row in source["links"] for cell in row[1:3]})
    nodes = [
        Node(
            name,
            round(1000 * math.cos(2 * math.pi * i / len(names)), 3),
            round(1000 * math.sin(2 * math.pi * i / len(names)), 3),
        )
        for i, name in enumerate(names)
    ]
    roads = [
        Road(row[0], max(3000, float(row[3].replace(",", ".")) * 50 / 0.06), 50, 1)
        for row in source["links"]
    ]
    return nodes, roads


def integer_demand(source, settings):
    """Resto mayor determinista: conserva el total intercentroide redondeado."""
    settings.validate()
    factor = settings.multiplier / (settings.occupancy if settings.demand_unit == "persons" else 1)
    matrix = source["demand_matrix"]
    centroids = [row[1] for row in source["centroids"]]
    size = len(centroids)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise SumoError("La matriz OD y los centroides tienen dimensiones diferentes.")
    cells, excluded = [], 0.0
    for i, row in enumerate(matrix):
        for j, original in enumerate(row):
            number(original, 0, 1e100, "Demanda OD")
            converted = original * factor
            if centroids[i] == centroids[j]:
                excluded += converted
            else:
                cells.append((i, j, converted))
    total = math.fsum(cell[2] for cell in cells)
    target = math.floor(total + 0.5)
    if not 1 <= target <= MAX_VEHICLES:
        raise SumoError(
            f"La demanda intercentroide debe generar entre 1 y {MAX_VEHICLES} vehículos."
        )
    counts = [math.floor(cell[2]) for cell in cells]
    ranking = sorted(range(len(cells)), key=lambda k: (-(cells[k][2] - counts[k]), k))
    for k in ranking[: target - sum(counts)]:
        counts[k] += 1
    result = [[0] * size for _ in range(size)]
    for (i, j, _), count in zip(cells, counts, strict=True):
        result[i][j] = count
    return result, total, excluded


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def write_xml(path, root):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def prepare_scenario(directory, source, nodes, roads, settings, *, check=lambda: None):
    """Escribe el escenario sin invocar ejecutables ni modificar las cuatro etapas."""
    settings.validate()
    check()
    for item in (*nodes, *roads):
        item.validate()
    node_map = {node.name: f"n{i}" for i, node in enumerate(nodes)}
    road_map = {road.link_id: f"e{i}" for i, road in enumerate(roads)}
    links = source["links"]
    if len(node_map) != len(nodes) or len(road_map) != len(roads):
        raise SumoError("Hay nodos o arcos duplicados en la geometría.")
    if set(node_map) != {name for row in links for name in row[1:3]}:
        raise SumoError("Actualice los nodos SUMO desde la asignación vigente.")
    if set(road_map) != {row[0] for row in links}:
        raise SumoError("Actualice los arcos SUMO desde la asignación vigente.")
    positions = {node.name: (node.x, node.y) for node in nodes}
    if len(set(positions.values())) != len(nodes):
        raise SumoError("Cada nodo debe tener coordenadas diferentes.")
    geometry = {road.link_id: road for road in roads}
    reference_links = []
    for name, tail, head, _t0, capacity in links:
        road = geometry[name]
        if road.length_m + 0.001 < math.dist(positions[tail], positions[head]):
            raise SumoError(f"Arco {name}: la longitud es menor que la distancia entre nodos.")
        reference_links.append(
            Link(
                name,
                tail,
                head,
                road.length_m / road.speed_kmh * 0.06,
                float(capacity.replace(",", ".")),
            )
        )
    matrix, total, excluded = integer_demand(source, settings)
    centroids = [row[1] for row in source["centroids"]]
    args = source["zone_names"], centroids, matrix, reference_links
    options = {key: source[key] for key in ("alpha", "beta", "tolerance")}
    options["max_iterations"] = source["iterations"]

    def cost(link, volume):
        check()
        return BPRCost(source["alpha"], source["beta"])(link, volume)

    options["cost_function"] = cost
    reference = (
        assign_user_equilibrium(*args, **options)
        if source["method"] == "ue"
        else assign_all_or_nothing(*args)
    )
    if source["method"] == "ue":
        reference = replace(
            reference, alpha=source["alpha"], beta=source["beta"], cost_function="bpr"
        )
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    nod, edg, taz, trips = (ET.Element(tag) for tag in ("nodes", "edges", "tazs", "routes"))
    for node in nodes:
        ET.SubElement(
            nod, "node", id=node_map[node.name], x=str(node.x), y=str(node.y), type="priority"
        )
    for name, tail, head, *_ in links:
        road = geometry[name]
        ET.SubElement(
            edg,
            "edge",
            {
                "id": road_map[name],
                "from": node_map[tail],
                "to": node_map[head],
                "length": str(road.length_m),
                "speed": str(road.speed_kmh / 3.6),
                "numLanes": str(road.lanes),
                "allow": "passenger",
            },
        )
    for i, centroid in enumerate(centroids):
        zone = ET.SubElement(taz, "taz", id=f"z{i}")
        for name, tail, head, *_ in links:
            if tail == centroid:
                ET.SubElement(zone, "tazSource", id=road_map[name], weight="1")
            if head == centroid:
                ET.SubElement(zone, "tazSink", id=road_map[name], weight="1")
    ET.SubElement(
        trips,
        "vType",
        id="car",
        vClass="passenger",
        carFollowModel="Krauss",
        accel="2.6",
        decel="4.5",
        sigma="0.5",
        length="5",
        minGap="2.5",
        tau="1",
        speedFactor="1",
        speedDev="0",
    )
    pairs = [
        (i, j) for i, row in enumerate(matrix) for j, count in enumerate(row) for _ in range(count)
    ]
    rng = random.Random(settings.seed)
    rng.shuffle(pairs)
    times = (
        [(k + 0.5) * settings.period_s / len(pairs) for k in range(len(pairs))]
        if settings.departures == "uniform"
        else sorted(rng.random() * settings.period_s for _ in pairs)
    )
    for k, ((i, j), depart) in enumerate(zip(pairs, times, strict=True)):
        if k % 1000 == 0:
            check()
        ET.SubElement(
            trips,
            "trip",
            id=f"v{k}",
            depart=f"{depart:.6f}",
            fromTaz=f"z{i}",
            toTaz=f"z{j}",
            type="car",
            departLane="best",
            departPos="base",
            arrivalPos="max",
        )
    horizon = settings.period_s + settings.clearance_s
    weights = ET.Element("meandata")
    interval = ET.SubElement(weights, "interval", begin="0", end=str(horizon))
    for item in reference.link_results:
        ET.SubElement(
            interval, "edge", id=road_map[item.link.link_id], traveltime=str(item.travel_time * 60)
        )
    additional = ET.Element("additional")
    ET.SubElement(
        additional,
        "edgeData",
        id="network",
        file="edges.xml",
        begin="0",
        end=str(horizon),
        period=str(horizon),
        excludeEmpty="true",
    )
    config = ET.Element("configuration")
    inputs = ET.SubElement(config, "input")
    for key, value in (
        ("net-file", "network.net.xml"),
        ("route-files", "routes.rou.xml"),
        ("additional-files", "measurements.add.xml"),
    ):
        ET.SubElement(inputs, key, value=value)
    time = ET.SubElement(config, "time")
    for key, value in (("begin", 0), ("end", horizon), ("step-length", 1)):
        ET.SubElement(time, key, value=str(value))
    output = ET.SubElement(config, "output")
    for key, value in (
        ("tripinfo-output", "tripinfo.xml"),
        ("summary-output", "summary.xml"),
        ("tripinfo-output.write-unfinished", "true"),
    ):
        ET.SubElement(output, key, value=value)
    processing = ET.SubElement(config, "processing")
    ET.SubElement(processing, "time-to-teleport", value="-1")
    random_section = ET.SubElement(config, "random_number")
    ET.SubElement(random_section, "seed", value=str(settings.seed))
    for name, tree in (
        ("nodes.nod.xml", nod),
        ("roads.edg.xml", edg),
        ("zones.taz.xml", taz),
        ("trips.trips.xml", trips),
        ("weights.xml", weights),
        ("measurements.add.xml", additional),
        ("simulation.sumocfg", config),
    ):
        write_xml(root / name, tree)
    snapshot = dict(
        source=source,
        nodes=[asdict(n) for n in nodes],
        roads=[asdict(r) for r in roads],
        settings=asdict(settings),
    )
    fingerprint = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()
    manifest = dict(
        format="MacroNet SUMO",
        app_version=__version__,
        status="prepared",
        fingerprint=fingerprint,
        inputs=snapshot,
        vehicle_matrix=matrix,
        generated=len(pairs),
        converted_interzonal=total,
        excluded_intrazonal_vehicles=excluded,
        rounding_error=len(pairs) - total,
        node_map=node_map,
        edge_map=road_map,
        reference=json.loads(json.dumps(asdict(reference))),
        commands=[],
        versions={},
        methodology="Referencia estática recalculada con OD vehicular redondeada y "
        "t0=longitud/velocidad. Enrutamiento único con esos costos, sin DUE; "
        "cruces prioritarios automáticos, automóvil genérico, calentamiento 0 s.",
    )
    with (root / "demand.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Origen", "Destino", "Demanda_original", "Vehiculos_simulados"))
        for i, row in enumerate(source["demand_matrix"]):
            for j, value in enumerate(row):
                writer.writerow(
                    (source["zone_names"][i], source["zone_names"][j], value, matrix[i][j])
                )
    write_json(root / "manifest.json", manifest)
    (root / "README.txt").write_text(
        "Escenario MacroNet SUMO. Revisar manifest.json y demand.csv.\n"
        "Ejecutar desde esta carpeta (SUMO >=1.18):\n"
        "netconvert --node-files nodes.nod.xml --edge-files roads.edg.xml "
        "--output-file network.net.xml\n"
        "duarouter --net-file network.net.xml --additional-files zones.taz.xml "
        "--route-files trips.trips.xml --weight-files weights.xml --with-taz "
        "--output-file routes.rou.xml\n"
        "sumo -c simulation.sumocfg\n\n" + manifest["methodology"] + "\n",
        encoding="utf-8",
    )
    return manifest

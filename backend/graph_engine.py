from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import networkx as nx

from backend.schemas import Location, RouteResult
from backend.traffic_store import TRAFFIC_FILE, read_traffic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_FILE = DATA_DIR / "city_network.graphml"
SAMPLE_GRAPH_FILE = DATA_DIR / "sample_dehradun_graph.graphml"
LOCATIONS_FILE = DATA_DIR / "locations.json"


@lru_cache(maxsize=1)
def load_graph() -> nx.MultiDiGraph:
    graph_path = GRAPH_FILE if GRAPH_FILE.exists() else SAMPLE_GRAPH_FILE
    graph = nx.read_graphml(graph_path)
    return nx.MultiDiGraph(graph)


def graph_mode() -> str:
    return "Full OSM Dehradun graph" if GRAPH_FILE.exists() else "Sample offline graph"


def graph_stats() -> dict[str, int | str]:
    graph = load_graph()
    return {
        "mode": graph_mode(),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
    }


@lru_cache(maxsize=1)
def load_locations() -> dict[str, Location]:
    import json

    with LOCATIONS_FILE.open("r", encoding="utf-8") as file:
        rows = json.load(file)
    return {row["name"]: Location(row["name"], row["lat"], row["lon"]) for row in rows}


def nearest_node(graph: nx.MultiDiGraph, lat: float, lon: float) -> str:
    best_node = None
    best_distance = float("inf")
    for node, data in graph.nodes(data=True):
        d_lat = float(data["y"]) - lat
        d_lon = float(data["x"]) - lon
        distance = (d_lat * d_lat) + (d_lon * d_lon)
        if distance < best_distance:
            best_node = str(node)
            best_distance = distance
    if best_node is None:
        raise ValueError("No nodes are available in the graph")
    return best_node


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _edge_key(graph: nx.MultiDiGraph, from_node: str, to_node: str) -> int | None:
    edge_data = graph.get_edge_data(str(from_node), str(to_node), default={})
    if not edge_data:
        return None
    return next(iter(edge_data.keys()))


def _apply_density_to_edge(
    graph: nx.MultiDiGraph,
    from_node: str,
    to_node: str,
    density: float,
    emergency_multiplier: float,
) -> bool:
    key = _edge_key(graph, from_node, to_node)
    if key is None:
        return False
    penalty = 1.0 + (density**2 * 4.0 * emergency_multiplier)
    edge = graph[from_node][to_node][key]
    current_density = float(edge.get("density", 0.0))
    if density < current_density:
        return True
    edge["density"] = density
    edge["traffic_minutes"] = float(edge["base_minutes"]) * penalty
    return True


def _apply_density_near_camera(
    graph: nx.MultiDiGraph,
    lat: float,
    lon: float,
    density: float,
    emergency_multiplier: float,
    radius_degrees: float = 0.0018,
) -> list[tuple[str, str]]:
    affected: list[tuple[str, str]] = []
    radius_squared = radius_degrees * radius_degrees
    for from_node, to_node in graph.edges():
        a = graph.nodes[str(from_node)]
        b = graph.nodes[str(to_node)]
        mid_lat = (float(a["y"]) + float(b["y"])) / 2
        mid_lon = (float(a["x"]) + float(b["x"])) / 2
        distance = ((mid_lat - lat) ** 2) + ((mid_lon - lon) ** 2)
        if distance > radius_squared:
            continue
        if _apply_density_to_edge(
            graph,
            str(from_node),
            str(to_node),
            density,
            emergency_multiplier,
        ):
            affected.append((str(from_node), str(to_node)))
    return affected


def apply_traffic_weights(
    graph: nx.MultiDiGraph,
    traffic_payload: dict[str, Any],
    emergency_multiplier: float = 1.0,
) -> list[tuple[str, str]]:
    congested: list[tuple[str, str]] = []

    for _, _, _, data in graph.edges(keys=True, data=True):
        length = _coerce_float(data.get("length"), 100.0)
        speed_kph = _coerce_float(data.get("speed_kph"), 30.0)
        travel_time_seconds = data.get("travel_time")
        if travel_time_seconds is not None:
            data["base_minutes"] = _coerce_float(travel_time_seconds, 60.0) / 60.0
        else:
            data["base_minutes"] = (length / 1000.0) / speed_kph * 60.0
        data["length"] = length
        data["traffic_minutes"] = data["base_minutes"]
        data["density"] = 0.0

    for entry in traffic_payload.get("traffic_edges", []):
        from_node = str(entry["from_node"])
        to_node = str(entry["to_node"])
        density = float(entry.get("density", 0.0))
        affected_edges = []
        if _apply_density_to_edge(graph, from_node, to_node, density, emergency_multiplier):
            affected_edges.append((from_node, to_node))

        coordinates = entry.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) == 2:
            affected_edges.extend(
                _apply_density_near_camera(
                    graph,
                    float(coordinates[0]),
                    float(coordinates[1]),
                    density,
                    emergency_multiplier,
                )
            )

        if density >= 0.55:
            congested.extend(affected_edges)

    return list(dict.fromkeys(congested))


def _path_weight(graph: nx.MultiDiGraph, path: list[str], weight: str) -> float:
    total = 0.0
    for from_node, to_node in zip(path, path[1:]):
        edge_data = graph.get_edge_data(str(from_node), str(to_node), default={})
        if not edge_data:
            raise ValueError(f"Missing edge from {from_node} to {to_node}")
        total += min(float(data.get(weight, 0.0)) for data in edge_data.values())
    return total


def _path_points(graph: nx.MultiDiGraph, path: list[str]) -> list[tuple[float, float]]:
    return [(float(graph.nodes[node]["y"]), float(graph.nodes[node]["x"])) for node in path]


def route_edges(path_nodes: list[str]) -> set[tuple[str, str]]:
    return set(zip(path_nodes, path_nodes[1:]))


def calculate_route(
    source_name: str,
    destination_name: str,
    vehicle_type: str = "Ambulance",
    traffic_file: Path = TRAFFIC_FILE,
) -> RouteResult:
    locations = load_locations()
    return calculate_route_between_locations(
        source=locations[source_name],
        destination=locations[destination_name],
        vehicle_type=vehicle_type,
        traffic_file=traffic_file,
    )


def calculate_route_between_locations(
    source: Location,
    destination: Location,
    vehicle_type: str = "Ambulance",
    traffic_file: Path = TRAFFIC_FILE,
) -> RouteResult:
    graph = load_graph()
    traffic = read_traffic(traffic_file)

    emergency_multiplier = {
        "Ambulance": 1.15,
        "Police": 1.00,
        "Fire Brigade": 1.25,
    }.get(vehicle_type, 1.0)

    source_node = nearest_node(graph, source.lat, source.lon)
    destination_node = nearest_node(graph, destination.lat, destination.lon)
    congested = apply_traffic_weights(graph, traffic, emergency_multiplier)

    base_path = nx.shortest_path(graph, source_node, destination_node, weight="base_minutes")
    traffic_path = nx.shortest_path(graph, source_node, destination_node, weight="traffic_minutes")

    base_minutes = _path_weight(graph, base_path, "base_minutes")
    traffic_minutes = _path_weight(graph, traffic_path, "traffic_minutes")
    gps_on_traffic_minutes = _path_weight(graph, base_path, "traffic_minutes")
    distance_m = _path_weight(graph, traffic_path, "length")

    return RouteResult(
        path_nodes=[str(node) for node in traffic_path],
        route_points=_path_points(graph, traffic_path),
        base_route_points=_path_points(graph, base_path),
        base_minutes=round(float(base_minutes), 2),
        traffic_minutes=round(float(traffic_minutes), 2),
        saved_minutes=round(float(gps_on_traffic_minutes - traffic_minutes), 2),
        distance_km=round(float(distance_m) / 1000.0, 2),
        congested_edges=congested,
        source_node=str(source_node),
        destination_node=str(destination_node),
    )

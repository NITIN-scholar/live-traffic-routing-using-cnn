from __future__ import annotations

from dataclasses import dataclass


DENSITY_LABELS = {
    "clear": 0.15,
    "moderate": 0.40,
    "heavy": 0.70,
    "gridlock": 0.90,
}


@dataclass(frozen=True)
class Location:
    name: str
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteResult:
    path_nodes: list[str]
    route_points: list[tuple[float, float]]
    base_route_points: list[tuple[float, float]]
    base_minutes: float
    traffic_minutes: float
    saved_minutes: float
    distance_km: float
    congested_edges: list[tuple[str, str]]
    source_node: str
    destination_node: str

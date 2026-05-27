from __future__ import annotations

import json
from pathlib import Path

import networkx as nx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "sample_dehradun_graph.graphml"
INTERSECTIONS_PATH = DATA_DIR / "dehradun_intersections_sample.json"


NODES = {
    "isbt": (30.2896, 78.0017),
    "patel_nagar": (30.3060, 78.0179),
    "railway_station": (30.3165, 78.0322),
    "prince_chowk": (30.3173, 78.0336),
    "doon_hospital": (30.3207, 78.0448),
    "clock_tower": (30.3256, 78.0437),
    "gandhi_park": (30.3277, 78.0412),
    "parade_ground": (30.3290, 78.0454),
    "survey_chowk": (30.3303, 78.0494),
    "karanpur": (30.3370, 78.0500),
    "dilaram_chowk": (30.3453, 78.0497),
    "jakhan": (30.3622, 78.0580),
    "pacific_mall": (30.3660, 78.0708),
    "sahastradhara_crossing": (30.3540, 78.0825),
    "raipur_chowk": (30.3348, 78.0685),
    "dharampur": (30.3048, 78.0568),
    "nehru_colony": (30.3054, 78.0702),
    "jogiwala": (30.3044, 78.0899),
    "rispana_bridge": (30.3018, 78.0782),
    "kanwali": (30.3104, 78.0074),
    "ballupur_chowk": (30.3343, 78.0118),
    "max_hospital": (30.3373, 78.0115),
    "prem_nagar": (30.3393, 77.9604),
    "rajpur": (30.3850, 78.0867),
}


EDGES = [
    ("isbt", "patel_nagar", 2700, 35, "Saharanpur Road"),
    ("patel_nagar", "railway_station", 1800, 30, "Saharanpur Road"),
    ("railway_station", "prince_chowk", 450, 24, "Station Link"),
    ("prince_chowk", "clock_tower", 1450, 28, "Rajpur Road Link"),
    ("clock_tower", "doon_hospital", 950, 24, "Hospital Road"),
    ("clock_tower", "gandhi_park", 500, 24, "Paltan Bazaar Link"),
    ("gandhi_park", "parade_ground", 450, 24, "Parade Ground Link"),
    ("parade_ground", "survey_chowk", 650, 26, "EC Road"),
    ("clock_tower", "survey_chowk", 1100, 30, "EC Road"),
    ("survey_chowk", "doon_hospital", 1250, 28, "Hospital Bypass"),
    ("survey_chowk", "karanpur", 900, 28, "Karanpur Road"),
    ("karanpur", "dilaram_chowk", 1200, 28, "Dilaram Road"),
    ("dilaram_chowk", "jakhan", 2300, 32, "Rajpur Road"),
    ("jakhan", "pacific_mall", 1100, 30, "Jakhan Mall Link"),
    ("pacific_mall", "sahastradhara_crossing", 2300, 34, "Canal Road"),
    ("sahastradhara_crossing", "raipur_chowk", 2600, 34, "Sahastradhara Road"),
    ("survey_chowk", "raipur_chowk", 2100, 35, "Raipur Road"),
    ("raipur_chowk", "dharampur", 3600, 36, "Raipur-Dharampur Road"),
    ("dharampur", "doon_hospital", 2100, 30, "Haridwar Road Link"),
    ("dharampur", "nehru_colony", 1500, 30, "Dharampur Road"),
    ("nehru_colony", "rispana_bridge", 1000, 28, "Nehru Colony Road"),
    ("rispana_bridge", "jogiwala", 1600, 30, "Haridwar Road"),
    ("dharampur", "prince_chowk", 3300, 32, "Haridwar Road"),
    ("patel_nagar", "kanwali", 1300, 28, "Kanwali Road"),
    ("kanwali", "ballupur_chowk", 3400, 34, "GMS Road"),
    ("ballupur_chowk", "prince_chowk", 3300, 34, "Chakrata Road"),
    ("ballupur_chowk", "max_hospital", 500, 25, "Hospital Link"),
    ("max_hospital", "dilaram_chowk", 4100, 32, "Canal Bypass"),
    ("ballupur_chowk", "prem_nagar", 5200, 38, "Chakrata Road West"),
    ("jakhan", "rajpur", 3400, 34, "Rajpur Road North"),
    ("sahastradhara_crossing", "jogiwala", 4200, 34, "Ring Road"),
    ("kanwali", "railway_station", 1700, 28, "Station Approach"),
]


def add_edge_pair(graph: nx.MultiDiGraph, u: str, v: str, length: float, speed: float, name: str) -> None:
    for source, target in [(u, v), (v, u)]:
        graph.add_edge(
            source,
            target,
            length=float(length),
            speed_kph=float(speed),
            name=name,
        )


def build() -> None:
    graph = nx.MultiDiGraph()
    for node, (lat, lon) in NODES.items():
        graph.add_node(node, y=float(lat), x=float(lon))
    for u, v, length, speed, name in EDGES:
        add_edge_pair(graph, u, v, length, speed, name)

    nx.write_graphml(graph, GRAPH_PATH)

    undirected = graph.to_undirected()
    intersections = []
    for node, degree in undirected.degree():
        data = graph.nodes[node]
        intersections.append(
            {
                "node": node,
                "lat": float(data["y"]),
                "lon": float(data["x"]),
                "degree": int(degree),
            }
        )
    intersections.sort(key=lambda row: row["degree"], reverse=True)
    with INTERSECTIONS_PATH.open("w", encoding="utf-8") as file:
        json.dump(intersections, file, indent=2)
        file.write("\n")

    print(f"Wrote {GRAPH_PATH}")
    print(f"Nodes: {graph.number_of_nodes()} Edges: {graph.number_of_edges()}")


if __name__ == "__main__":
    build()

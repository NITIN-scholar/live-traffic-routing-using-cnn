from __future__ import annotations

from pathlib import Path
import json

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = PROJECT_ROOT / "data" / "city_network.graphml"
INTERSECTIONS_PATH = PROJECT_ROOT / "data" / "dehradun_intersections.json"
TRAFFIC_PATH = PROJECT_ROOT / "data" / "traffic_density.json"


MONITORED_CAMERA_POINTS = [
    {
        "camera_id": "cam_001",
        "intersection": "Prince Chowk",
        "road_name": "Prince Chowk monitored corridor",
        "lat": 30.3173,
        "lon": 78.0336,
    },
    {
        "camera_id": "cam_002",
        "intersection": "Clock Tower",
        "road_name": "Clock Tower monitored corridor",
        "lat": 30.3256,
        "lon": 78.0437,
    },
    {
        "camera_id": "cam_003",
        "intersection": "Survey Chowk",
        "road_name": "Survey Chowk monitored corridor",
        "lat": 30.3303,
        "lon": 78.0494,
    },
    {
        "camera_id": "cam_004",
        "intersection": "Raipur Chowk",
        "road_name": "Raipur Chowk monitored corridor",
        "lat": 30.3348,
        "lon": 78.0685,
    },
    {
        "camera_id": "cam_005",
        "intersection": "Ballupur Chowk",
        "road_name": "Ballupur monitored corridor",
        "lat": 30.3343,
        "lon": 78.0118,
    },
    {
        "camera_id": "cam_006",
        "intersection": "Patel Nagar",
        "road_name": "Patel Nagar monitored corridor",
        "lat": 30.3060,
        "lon": 78.0179,
    },
]


def save_intersections(graph) -> None:
    undirected = graph.to_undirected()
    intersections = []
    for node, degree in undirected.degree():
        if degree < 3:
            continue
        data = graph.nodes[node]
        intersections.append(
            {
                "node": str(node),
                "lat": float(data["y"]),
                "lon": float(data["x"]),
                "degree": int(degree),
            }
        )

    intersections.sort(key=lambda row: row["degree"], reverse=True)
    with INTERSECTIONS_PATH.open("w", encoding="utf-8") as file:
        json.dump(intersections, file, indent=2)
        file.write("\n")


def save_traffic_seed(graph, ox) -> None:
    traffic_edges = []
    for point in MONITORED_CAMERA_POINTS:
        u, v, _ = ox.distance.nearest_edges(graph, point["lon"], point["lat"])
        for suffix, from_node, to_node in [("", u, v), ("_reverse", v, u)]:
            if not graph.has_edge(from_node, to_node):
                continue
            traffic_edges.append(
                {
                    "camera_id": f'{point["camera_id"]}{suffix}',
                    "intersection": point["intersection"],
                    "from_node": str(from_node),
                    "to_node": str(to_node),
                    "road_name": point["road_name"],
                    "density": 0.15,
                    "status": "clear",
                    "coordinates": [point["lat"], point["lon"]],
                    "source": "osm_seed",
                }
            )

    payload = {
        "city": "Dehradun",
        "active_scenario": "Minimal",
        "updated_at": "local-osm-cache",
        "traffic_edges": traffic_edges,
    }
    with TRAFFIC_PATH.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    try:
        import osmnx as ox
    except ImportError as exc:
        raise SystemExit("Install requirements before downloading OSM data.") from exc

    place_name = "Dehradun, Uttarakhand, India"
    graph = ox.graph_from_place(place_name, network_type="drive", simplify=True)
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    save_intersections(graph)
    save_traffic_seed(graph, ox)
    ox.save_graphml(graph, GRAPH_PATH)
    print(f"Saved OSM graph to {GRAPH_PATH}")
    print(f"Saved intersections to {INTERSECTIONS_PATH}")
    print(f"Saved real-graph traffic seed to {TRAFFIC_PATH}")


if __name__ == "__main__":
    main()

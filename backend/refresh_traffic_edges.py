from __future__ import annotations

import json
from pathlib import Path

from backend.download_osm_graph import MONITORED_CAMERA_POINTS, TRAFFIC_PATH
from backend.graph_engine import load_graph
from backend.traffic_store import write_traffic


def nearest_directed_edge(graph, lat: float, lon: float) -> tuple[str, str]:
    best = None
    best_distance = float("inf")
    for u, v in graph.edges():
        a = graph.nodes[u]
        b = graph.nodes[v]
        mid_lat = (float(a["y"]) + float(b["y"])) / 2
        mid_lon = (float(a["x"]) + float(b["x"])) / 2
        distance = ((mid_lat - lat) ** 2) + ((mid_lon - lon) ** 2)
        if distance < best_distance:
            best = (str(u), str(v))
            best_distance = distance
    if best is None:
        raise ValueError("No graph edges available")
    return best


def build_payload() -> dict:
    graph = load_graph()
    traffic_edges = []
    for point in MONITORED_CAMERA_POINTS:
        u, v = nearest_directed_edge(graph, point["lat"], point["lon"])
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
                    "source": "graph_refresh",
                }
            )
    return {
        "city": "Dehradun",
        "active_scenario": "Minimal",
        "updated_at": "local-graph-refresh",
        "traffic_edges": traffic_edges,
    }


def main() -> None:
    payload = build_payload()
    write_traffic(payload, TRAFFIC_PATH)
    print(json.dumps({"traffic_edges": len(payload["traffic_edges"])}, indent=2))


if __name__ == "__main__":
    main()

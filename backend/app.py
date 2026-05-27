from __future__ import annotations

from fastapi import FastAPI

from backend.graph_engine import calculate_route, graph_stats, load_locations
from backend.traffic_store import apply_preset, inject_cnn_snapshot, read_traffic


app = FastAPI(title="LiveRoute Emergency Routing API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/graph")
def graph() -> dict:
    return graph_stats()


@app.get("/locations")
def locations() -> list[dict[str, float | str]]:
    return [location.__dict__ for location in load_locations().values()]


@app.get("/traffic")
def traffic() -> dict:
    return read_traffic()


@app.post("/traffic/preset/{name}")
def traffic_preset(name: str) -> dict:
    return apply_preset(name)


@app.post("/traffic/cnn/{model_mode}")
def traffic_cnn(model_mode: str) -> dict:
    return inject_cnn_snapshot(model_mode)


@app.get("/route")
def route(source: str, destination: str, vehicle_type: str = "Ambulance") -> dict:
    return calculate_route(source, destination, vehicle_type).__dict__

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.schemas import DENSITY_LABELS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
TRAFFIC_FILE = DATA_DIR / "traffic_density.json"


PRESET_FACTORS = {
    "Minimal": 0.15,
    "Rush Hour": 0.65,
    "Gridlock": 0.90,
}

SIMULATION_PROFILES = {
    "calm": {
        "label": "Calm city flow",
        "target_density": 0.18,
        "change_probability": 0.22,
        "max_delta": 0.08,
        "incident_probability": 0.04,
    },
    "balanced": {
        "label": "Balanced city flow",
        "target_density": 0.36,
        "change_probability": 0.35,
        "max_delta": 0.12,
        "incident_probability": 0.09,
    },
    "peak": {
        "label": "Peak-hour pressure",
        "target_density": 0.64,
        "change_probability": 0.48,
        "max_delta": 0.16,
        "incident_probability": 0.14,
    },
}


def density_status(density: float) -> str:
    if density <= 0.25:
        return "clear"
    if density <= 0.50:
        return "moderate"
    if density <= 0.75:
        return "heavy"
    return "gridlock"


def read_traffic(path: Path = TRAFFIC_FILE) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_traffic(payload: dict[str, Any], path: Path = TRAFFIC_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)
        file.write("\n")


def summarize_traffic(payload: dict[str, Any]) -> dict[str, Any]:
    entries = payload.get("traffic_edges", [])
    counts = {"clear": 0, "moderate": 0, "heavy": 0, "gridlock": 0}
    if not entries:
        return {"edge_count": 0, "average_density": 0.0, "status_counts": counts}

    total_density = 0.0
    for entry in entries:
        density = float(entry.get("density", 0.0))
        total_density += density
        counts[density_status(density)] += 1

    return {
        "edge_count": len(entries),
        "average_density": round(total_density / len(entries), 2),
        "status_counts": counts,
    }


def initialize_simulation(profile: str = "balanced", path: Path = TRAFFIC_FILE) -> dict[str, Any]:
    if profile not in SIMULATION_PROFILES:
        raise ValueError(f"Unknown simulation profile: {profile}")

    payload = read_traffic(path)
    config = SIMULATION_PROFILES[profile]
    target = float(config["target_density"])
    entries = payload.get("traffic_edges", [])

    for index, entry in enumerate(entries):
        lane_bias = ((index % 4) - 1.5) * 0.05
        density = max(0.05, min(0.98, target + lane_bias))
        entry["density"] = round(density, 2)
        entry["status"] = density_status(density)
        entry["source"] = "realtime_simulation"

    payload["active_scenario"] = f"Realtime simulation ({config['label']})"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["simulation"] = {
        "tick": 0,
        "changed_edges": len(entries),
        "change_probability": round(float(config["change_probability"]), 2),
        "profile": profile,
        "event": "startup_baseline",
        "average_density": summarize_traffic(payload)["average_density"],
    }
    write_traffic(payload, path)
    return payload


def apply_preset(name: str, path: Path = TRAFFIC_FILE) -> dict[str, Any]:
    if name not in PRESET_FACTORS:
        raise ValueError(f"Unknown traffic preset: {name}")

    payload = read_traffic(path)
    base = PRESET_FACTORS[name]
    entries = payload.get("traffic_edges", [])

    for index, entry in enumerate(entries):
        # Keep one or two edges lighter so the reroute remains visually obvious.
        offset = ((index % 3) - 1) * 0.08
        density = max(0.05, min(0.98, base + offset))
        entry["density"] = round(density, 2)
        entry["status"] = density_status(density)
        entry["source"] = "simulator"

    payload["active_scenario"] = name
    payload["updated_at"] = "preset"
    write_traffic(payload, path)
    return payload


def inject_pretrained_snapshot(model_mode: str, path: Path = TRAFFIC_FILE) -> dict[str, Any]:
    payload = read_traffic(path)
    pattern = ["clear", "gridlock", "heavy", "moderate", "gridlock", "clear"]

    for index, entry in enumerate(payload.get("traffic_edges", [])):
        status = pattern[index % len(pattern)]
        entry["density"] = DENSITY_LABELS[status]
        entry["status"] = status
        entry["source"] = "pretrained_detector"
        entry["model_mode"] = model_mode
        entry["confidence"] = round(0.72 + (index % 4) * 0.06, 2)

    payload["active_scenario"] = f"Pretrained detector snapshot ({model_mode})"
    payload["updated_at"] = "pretrained"
    write_traffic(payload, path)
    return payload


def simulate_realtime_tick(
    change_probability: float = 0.35,
    max_delta: float = 0.12,
    profile: str = "balanced",
    path: Path = TRAFFIC_FILE,
) -> dict[str, Any]:
    if profile not in SIMULATION_PROFILES:
        raise ValueError(f"Unknown simulation profile: {profile}")

    payload = read_traffic(path)
    entries = payload.get("traffic_edges", [])
    simulation = payload.get("simulation", {})
    config = SIMULATION_PROFILES[profile]
    tick = int(simulation.get("tick", 0)) + 1
    changed_edges = 0
    changed_intersections: set[str] = set()
    random.seed()

    target_density = float(config["target_density"])
    incident_probability = float(config["incident_probability"])
    event_roll = random.random()
    if event_roll < incident_probability:
        event = "incident_spike"
    elif event_roll < incident_probability + 0.12:
        event = "clearance_wave"
    elif event_roll < incident_probability + 0.34:
        event = "steady_drift"
    else:
        event = "stable"

    for entry in entries:
        current = float(entry.get("density", 0.15))
        effective_probability = change_probability if change_probability > 0 else float(config["change_probability"])
        if event == "stable":
            effective_probability *= 0.35

        if random.random() > effective_probability:
            continue

        target_pull = (target_density - current) * random.uniform(0.20, 0.55)
        drift = target_pull + random.uniform(-max_delta, max_delta)
        if event == "incident_spike":
            drift += random.uniform(0.10, 0.24)
        elif event == "clearance_wave":
            drift -= random.uniform(0.08, 0.20)
        elif random.random() < 0.12:
            drift += random.choice([-1.0, 1.0]) * random.uniform(0.05, 0.14)

        next_density = max(0.05, min(0.98, current + drift))
        if abs(next_density - current) < 0.03:
            continue

        entry["density"] = round(next_density, 2)
        entry["status"] = density_status(next_density)
        entry["source"] = "realtime_simulation"
        changed_edges += 1
        changed_intersections.add(str(entry.get("intersection", "Unknown")))

    summary = summarize_traffic(payload)
    payload["active_scenario"] = f"Realtime simulation ({config['label']})"
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload["simulation"] = {
        "tick": tick,
        "changed_edges": changed_edges,
        "change_probability": round(change_probability if change_probability > 0 else float(config["change_probability"]), 2),
        "profile": profile,
        "event": event,
        "average_density": summary["average_density"],
        "changed_intersections": sorted(changed_intersections),
    }
    write_traffic(payload, path)
    return payload

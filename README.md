# LiveRoute

LiveRoute is a local proof-of-concept for smart-city emergency routing in Dehradun, India. It shows how traffic density written into a JSON feed can penalize directed road edges and change the fastest path for an emergency vehicle.

## What It Demonstrates

- Dark Streamlit dashboard with an interactive OpenStreetMap/Folium map
- Emergency route calculation over a directed graph
- Traffic density stored in `data/traffic_density.json`
- A simplified route workflow with five main controls:
  - `To`
  - `From`
  - `Vehicle type`
  - `Find route`
  - `Realtime routing`
- `Pick on map` as the first dropdown option for both route ends
- A separate terminal-based simulator that updates traffic JSON every 30 seconds
- Offline-first behavior using cached graph data when available

## Project Structure

```text
route finder/
├── backend/
│   ├── app.py
│   ├── cnn_pretrained.py
│   ├── download_osm_graph.py
│   ├── graph_engine.py
│   ├── traffic_store.py
├── frontend/
│   └── dashboard.py
├── simulator/
│   └── traffic_simulator.py
├── data/
│   ├── city_network.graphml
│   ├── dehradun_intersections.json
│   ├── locations.json
│   ├── sample_dehradun_graph.graphml
│   └── traffic_density.json
├── models/
│   └── pretrained/
├── requirements.txt
├── requirements-ml.txt
├── requirements-osm.txt
└── .env.example
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the dashboard:

```powershell
streamlit run frontend/dashboard.py
```

Run the separate traffic simulator in another terminal:

```powershell
python simulator/traffic_simulator.py
```

The simulator updates `data/traffic_density.json` every 30 seconds by default. The dashboard reads that changing JSON whenever `Realtime routing` is enabled.

Useful simulator options:

```powershell
python simulator/traffic_simulator.py --profile calm
python simulator/traffic_simulator.py --profile peak
python simulator/traffic_simulator.py --once
python simulator/traffic_simulator.py --skip-bootstrap
```

## Pretrained Detector

The project focuses on a pretrained YOLO-style detector for traffic analysis:

- If `models/pretrained/yolov8n.pt` is missing, the app uses a deterministic local fallback so the demo still runs.
- If Ultralytics is installed, [backend/cnn_pretrained.py](D:/live-traffic-routing-using-cnn/backend/cnn_pretrained.py) can estimate density from detected vehicle bounding boxes on a traffic image.

Install ML dependencies only when needed:

```powershell
python -m pip install -r requirements-ml.txt
```

## Traffic JSON Format

Traffic is stored per directed edge:

```json
{
  "camera_id": "cam_001",
  "intersection": "Prince Chowk",
  "from_node": "prince_chowk",
  "to_node": "clock_tower",
  "road_name": "Rajpur Road Link",
  "density": 0.7,
  "status": "heavy",
  "coordinates": [30.3173, 78.0336],
  "source": "pretrained_detector"
}
```

Density values use this scale:

```text
0.00 - 0.25 clear
0.26 - 0.50 moderate
0.51 - 0.75 heavy
0.76 - 1.00 gridlock
```

## OSMnx Graph Download

The project ships with a small offline Dehradun sample graph. To make routing much closer to a real map app, generate a larger real Dehradun graph:

```powershell
python -m pip install -r requirements-osm.txt
python backend/download_osm_graph.py
```

That creates:

- `data/city_network.graphml`
- `data/dehradun_intersections.json`
- a refreshed `data/traffic_density.json` mapped to real OSM graph node IDs

`city_network.graphml` is ignored by git because it can be regenerated.

## Environment Variables

No API key is required for the local demo. Copy `.env.example` to `.env` only if you add external services later.

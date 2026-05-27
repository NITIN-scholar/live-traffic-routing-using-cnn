from __future__ import annotations

import sys
from pathlib import Path

import folium
import streamlit as st
from folium.features import DivIcon
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.graph_engine import calculate_route_between_locations, graph_stats, load_graph, load_locations, route_edges
from backend.schemas import Location
from backend.traffic_store import read_traffic


PICK_ON_MAP = "Pick on map"


st.set_page_config(
    page_title="LiveRoute",
    page_icon="L",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: Inter, Roboto, Arial, sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 20% 0%, rgba(21, 118, 255, 0.13), transparent 25%),
                linear-gradient(135deg, #09090d 0%, #101116 45%, #171820 100%);
            color: #f7f8fb;
        }

        [data-testid="stSidebar"] {
            background: #111217;
            border-right: 1px solid rgba(255,255,255,0.08);
        }

        .hero {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
            padding: 12px 2px 16px;
        }

        .brand {
            font-size: 28px;
            font-weight: 800;
            color: #ffffff;
        }

        .status-pill {
            border: 1px solid rgba(59, 237, 177, 0.45);
            color: #8ff9d0;
            background: rgba(30, 206, 143, 0.12);
            padding: 8px 12px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 700;
            white-space: nowrap;
        }

        .toolbar-card {
            background: linear-gradient(180deg, rgba(20,25,35,0.96), rgba(14,18,26,0.96));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 16px 18px;
            margin-bottom: 14px;
        }

        .toolbar-title {
            color: #d7e4ff;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: .1em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .toolbar-subline {
            color: #93a4c2;
            font-size: 13px;
            line-height: 1.4;
        }

        .metric-card {
            background: #171922;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 15px 16px;
            margin-bottom: 14px;
            min-height: 88px;
        }

        .metric-label {
            color: #f7f8fb;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 8px;
            line-height: 1.25;
        }

        .metric-value {
            color: #ffffff;
            font-size: 28px;
            font-weight: 500;
            line-height: 1.1;
            overflow-wrap: anywhere;
        }

        .section-title {
            color: #f4f6fb;
            font-size: 13px;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
            margin: 18px 0 8px;
        }

        .sidebar-note {
            color: #9eafca;
            font-size: 12px;
            line-height: 1.45;
            margin: 2px 0 12px;
        }

        .map-label {
            background: rgba(12, 14, 19, 0.88);
            border: 1px solid rgba(255,255,255,0.16);
            color: #ffffff;
            border-radius: 8px;
            padding: 5px 8px;
            font-size: 11px;
            font-weight: 800;
            box-shadow: 0 8px 24px rgba(0,0,0,0.32);
            white-space: nowrap;
        }

        .info-pill {
            display: inline-block;
            margin-right: 8px;
            margin-top: 8px;
            padding: 7px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            border: 1px solid rgba(255,255,255,0.1);
            color: #e7f0ff;
            background: rgba(255,255,255,0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def density_color(density: float) -> str:
    if density >= 0.76:
        return "#ff304f"
    if density >= 0.51:
        return "#ff7a45"
    if density >= 0.26:
        return "#ffd166"
    return "#46f0b4"


def map_label(point: list[float], text: str) -> folium.Marker:
    return folium.Marker(
        point,
        icon=DivIcon(
            icon_size=(180, 28),
            icon_anchor=(16, -10),
            html=(
                '<div class="map-label">'
                f"{text}"
                "</div>"
            ),
        ),
    )


def edge_points(graph, from_node: str, to_node: str) -> list[tuple[float, float]]:
    return [
        (float(graph.nodes[from_node]["y"]), float(graph.nodes[from_node]["x"])),
        (float(graph.nodes[to_node]["y"]), float(graph.nodes[to_node]["x"])),
    ]


def add_legend(fmap: folium.Map) -> None:
    legend_html = """
    <div style="position: fixed; z-index: 9999; left: 22px; bottom: 28px;
        background: rgba(17, 18, 23, 0.94); border: 1px solid rgba(255,255,255,0.16);
        border-radius: 12px; padding: 12px 14px; color: #f7f8fb; font-size: 12px;
        box-shadow: 0 16px 40px rgba(0,0,0,0.35); font-family: Inter, Roboto, Arial, sans-serif;">
        <div style="font-weight:800; margin-bottom:8px;">Map Legend</div>
        <div style="display:flex;align-items:center;gap:8px;margin:6px 0;white-space:nowrap;"><span style="width:32px;height:4px;border-radius:999px;display:inline-block;background:#33d6ff;"></span> Active route</div>
        <div style="display:flex;align-items:center;gap:8px;margin:6px 0;white-space:nowrap;"><span style="width:32px;height:4px;border-radius:999px;display:inline-block;background:#46f0b4;"></span> Clear corridor</div>
        <div style="display:flex;align-items:center;gap:8px;margin:6px 0;white-space:nowrap;"><span style="width:32px;height:4px;border-radius:999px;display:inline-block;background:#ffd166;"></span> Moderate corridor</div>
        <div style="display:flex;align-items:center;gap:8px;margin:6px 0;white-space:nowrap;"><span style="width:32px;height:4px;border-radius:999px;display:inline-block;background:#ff7a45;"></span> Heavy corridor</div>
        <div style="display:flex;align-items:center;gap:8px;margin:6px 0;white-space:nowrap;"><span style="width:32px;height:4px;border-radius:999px;display:inline-block;background:#ff304f;"></span> Gridlock corridor</div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))


def set_map_pick(which_end: str, lat: float, lon: float) -> None:
    st.session_state[f"{which_end}_map_pick"] = Location(
        name=f"Picked {which_end.title()}",
        lat=float(lat),
        lon=float(lon),
    )


def choose_map_target(from_choice: str, to_choice: str, lat: float, lon: float) -> str | None:
    from_uses_map = from_choice == PICK_ON_MAP
    to_uses_map = to_choice == PICK_ON_MAP

    if from_uses_map and not to_uses_map:
        return "from"
    if to_uses_map and not from_uses_map:
        return "to"
    if not from_uses_map and not to_uses_map:
        return None

    source_pick = st.session_state.get("from_map_pick")
    destination_pick = st.session_state.get("to_map_pick")

    if source_pick is None:
        return "from"
    if destination_pick is None:
        return "to"

    from_distance = abs(source_pick.lat - lat) + abs(source_pick.lon - lon)
    to_distance = abs(destination_pick.lat - lat) + abs(destination_pick.lon - lon)
    return "from" if from_distance <= to_distance else "to"


def selected_locations(from_choice: str, to_choice: str) -> tuple[Location, Location]:
    locations = load_locations()

    if from_choice == PICK_ON_MAP:
        source = st.session_state.get("from_map_pick") or Location("Pick origin on map", 30.3256, 78.0437)
    else:
        source = locations[from_choice]

    if to_choice == PICK_ON_MAP:
        destination = st.session_state.get("to_map_pick") or Location("Pick destination on map", 30.3373, 78.0115)
    else:
        destination = locations[to_choice]

    return source, destination


def build_map(source: Location, destination: Location, vehicle_type: str) -> tuple[folium.Map, object]:
    graph = load_graph()
    traffic = read_traffic()
    result = calculate_route_between_locations(source, destination, vehicle_type)
    route_edge_set = route_edges(result.path_nodes)

    fmap = folium.Map(
        location=[(source.lat + destination.lat) / 2, (source.lon + destination.lon) / 2],
        zoom_start=13,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )

    for edge in traffic.get("traffic_edges", []):
        from_node = str(edge["from_node"])
        to_node = str(edge["to_node"])
        if from_node not in graph.nodes or to_node not in graph.nodes:
            continue
        density = float(edge.get("density", 0))
        edge_is_on_route = (from_node, to_node) in route_edge_set
        folium.PolyLine(
            edge_points(graph, from_node, to_node),
            color=density_color(density),
            weight=8 if edge_is_on_route and density >= 0.55 else 4,
            opacity=0.82 if edge_is_on_route else 0.24,
            tooltip=f"{edge['road_name']} | {edge['status']} | {density:.2f}",
        ).add_to(fmap)

    folium.PolyLine(
        result.route_points,
        color="#33d6ff",
        weight=8,
        opacity=0.95,
        tooltip="Active route",
    ).add_to(fmap)

    folium.CircleMarker(
        [source.lat, source.lon],
        radius=8,
        color="#46f0b4",
        fill=True,
        fill_color="#46f0b4",
        tooltip=f"From: {source.name}",
    ).add_to(fmap)
    map_label([source.lat, source.lon], f"From: {source.name}").add_to(fmap)

    folium.CircleMarker(
        [destination.lat, destination.lon],
        radius=8,
        color="#ff304f",
        fill=True,
        fill_color="#ff304f",
        tooltip=f"To: {destination.name}",
    ).add_to(fmap)
    map_label([destination.lat, destination.lon], f"To: {destination.name}").add_to(fmap)
    add_legend(fmap)

    return fmap, result


def sidebar_controls() -> tuple[str, str, str, bool, bool]:
    locations = list(load_locations().keys())
    route_options = [PICK_ON_MAP] + locations

    st.sidebar.markdown('<div class="section-title">Routing</div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="sidebar-note">Use the dropdowns to choose named places, or select "Pick on map" and click the map.</div>',
        unsafe_allow_html=True,
    )

    from_choice = st.sidebar.selectbox("From", route_options, index=0)
    to_choice = st.sidebar.selectbox("To", route_options, index=1 if len(route_options) > 1 else 0)
    vehicle_type = st.sidebar.selectbox("Vehicle type", ["Ambulance", "Police", "Fire Brigade"], index=0)
    find_route = st.sidebar.button("Find route", use_container_width=True)

    st.sidebar.markdown('<div class="section-title">Realtime Routing</div>', unsafe_allow_html=True)
    realtime_enabled = st.sidebar.toggle("Realtime routing", value=False, key="realtime_routing_enabled")
    st.sidebar.markdown(
        '<div class="sidebar-note">When enabled, the map keeps re-reading the changing JSON from the separate simulator process.</div>',
        unsafe_allow_html=True,
    )

    stats = graph_stats()
    st.sidebar.markdown('<div class="section-title">Graph</div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        f'<div class="sidebar-note">{stats["mode"]}<br>Nodes: {stats["nodes"]} | Edges: {stats["edges"]}</div>',
        unsafe_allow_html=True,
    )

    return from_choice, to_choice, vehicle_type, find_route or realtime_enabled, realtime_enabled


def handle_map_click(map_state: dict | None, from_choice: str, to_choice: str) -> None:
    if not map_state:
        return
    clicked = map_state.get("last_clicked")
    if not clicked:
        return

    token = f"{clicked.get('lat'):.6f},{clicked.get('lng'):.6f}"
    if st.session_state.get("last_processed_map_click") == token:
        return

    target = choose_map_target(from_choice, to_choice, clicked["lat"], clicked["lng"])
    updated = False
    if target is not None:
        set_map_pick(target, clicked["lat"], clicked["lng"])
        updated = True

    if updated:
        st.session_state["last_processed_map_click"] = token
        st.rerun()


def main() -> None:
    inject_styles()
    st.markdown(
        """
        <div class="hero">
            <div class="brand">LiveRoute</div>
            <div class="status-pill">System Status: Live</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    from_choice, to_choice, vehicle_type, should_route, realtime_enabled = sidebar_controls()

    if realtime_enabled:
        st_autorefresh(interval=5000, key="live_route_refresh")

    if not should_route and "route_source" not in st.session_state:
        source, destination = selected_locations(from_choice, to_choice)
    else:
        source, destination = selected_locations(from_choice, to_choice)
        st.session_state["route_source"] = source
        st.session_state["route_destination"] = destination
        st.session_state["route_vehicle"] = vehicle_type

    source = st.session_state.get("route_source", source)
    destination = st.session_state.get("route_destination", destination)
    vehicle_type = st.session_state.get("route_vehicle", vehicle_type)

    traffic = read_traffic()
    fmap, result = build_map(source, destination, vehicle_type)
    map_col, metrics_col = st.columns([3.4, 1.1], gap="large")

    toolbar_left, toolbar_right = st.columns([1.8, 1.0], gap="large")
    with toolbar_left:
        st.markdown(
            f"""
            <div class="toolbar-card">
                <div class="toolbar-title">Active Route</div>
                <div style="font-size:18px;font-weight:700;color:#fff;line-height:1.35;">{source.name} to {destination.name}</div>
                <div class="toolbar-subline">Choose named places or use "Pick on map" in either dropdown, then click the map to place that end.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with toolbar_right:
        scenario = traffic.get("active_scenario", "Unknown")
        st.markdown(
            f"""
            <div class="toolbar-card">
                <div class="toolbar-title">Routing Mode</div>
                <span class="info-pill">{vehicle_type}</span>
                <span class="info-pill">{scenario}</span>
                <span class="info-pill">{'Realtime on' if realtime_enabled else 'Realtime off'}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with map_col:
        map_state = st_folium(
            fmap,
            height=720,
            use_container_width=True,
            returned_objects=["last_clicked"],
        )
        handle_map_click(map_state, from_choice, to_choice)

    with metrics_col:
        st.markdown('<div class="section-title">Journey Metrics</div>', unsafe_allow_html=True)
        metric_card("Est. travel time", f"{result.traffic_minutes:.2f} min")
        metric_card("Time saved vs GPS", f"{result.saved_minutes:.2f} min")
        metric_card("Route distance", f"{result.distance_km:.2f} km")
        metric_card("Active diverting", "Enabled" if result.saved_minutes > 0 else "Standby")

        st.markdown('<div class="section-title">Traffic Feed</div>', unsafe_allow_html=True)
        st.caption(f"Scenario: {traffic.get('active_scenario', 'Unknown')}")
        sim = traffic.get("simulation", {})
        if sim:
            st.caption(f"Tick: {sim.get('tick', 0)} | Changed corridors: {sim.get('changed_edges', 0)}")


if __name__ == "__main__":
    main()

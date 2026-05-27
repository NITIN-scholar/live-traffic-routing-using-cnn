from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.traffic_store import initialize_simulation, simulate_realtime_tick, summarize_traffic


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone traffic simulator for LiveRoute.")
    parser.add_argument("--interval", type=int, default=30, help="Seconds between traffic updates.")
    parser.add_argument(
        "--profile",
        choices=["calm", "balanced", "peak"],
        default="balanced",
        help="Traffic behavior profile for the city.",
    )
    parser.add_argument(
        "--change-probability",
        type=float,
        default=0.0,
        help="Override the profile change probability. Use 0 to keep the profile default.",
    )
    parser.add_argument(
        "--max-delta",
        type=float,
        default=0.12,
        help="Maximum density movement per tick before event effects are applied.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Start ticking from the existing JSON state instead of reseeding a profile baseline.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one tick and exit. Useful for quick checks.",
    )
    return parser


def format_status_counts(counts: dict[str, int]) -> str:
    return (
        f"clear={counts.get('clear', 0)} "
        f"moderate={counts.get('moderate', 0)} "
        f"heavy={counts.get('heavy', 0)} "
        f"gridlock={counts.get('gridlock', 0)}"
    )


def print_snapshot(prefix: str, payload: dict) -> None:
    sim = payload.get("simulation", {})
    summary = summarize_traffic(payload)
    changed_intersections = sim.get("changed_intersections", [])
    changed_text = ", ".join(changed_intersections[:3]) if changed_intersections else "none"
    if len(changed_intersections) > 3:
        changed_text += ", ..."

    print(
        f"{prefix} "
        f"tick={sim.get('tick', '?')} "
        f"profile={sim.get('profile', 'unknown')} "
        f"event={sim.get('event', 'unknown')} "
        f"changed_edges={sim.get('changed_edges', 0)} "
        f"avg_density={summary['average_density']:.2f}"
    )
    print(f"  status_mix: {format_status_counts(summary['status_counts'])}")
    print(f"  changed_intersections: {changed_text}")


def main() -> None:
    args = build_parser().parse_args()

    print("LiveRoute traffic simulator started.")
    print(
        f"profile={args.profile} interval={args.interval}s "
        f"change_probability={args.change_probability or 'profile-default'} "
        f"max_delta={args.max_delta}"
    )

    if not args.skip_bootstrap:
        payload = initialize_simulation(profile=args.profile)
        print_snapshot("bootstrapped", payload)

    try:
        while True:
            payload = simulate_realtime_tick(
                change_probability=args.change_probability,
                max_delta=args.max_delta,
                profile=args.profile,
            )
            print_snapshot("tick", payload)
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Simulator stopped by user.")


if __name__ == "__main__":
    main()

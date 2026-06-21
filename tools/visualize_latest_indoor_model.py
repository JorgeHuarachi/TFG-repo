#!/usr/bin/env python3
"""Generate standard visual checks for the latest exported indoor_model JSON."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = REPO_ROOT / "outputs" / "indoor_models"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "visual_checks"
VISUALIZER = REPO_ROOT / "tools" / "visualize_indoor_model.py"

VIEWS = [
    ("all", ["--layers", "all"]),
    ("spaces", ["--preset", "spaces"]),
    ("navigable_spaces", ["--layers", "general,transfer"]),
    ("non_navigable_spaces", ["--layers", "non_navigable,object"]),
    ("boundaries", ["--layers", "boundaries"]),
    ("nav_boundaries", ["--layers", "navigable_boundaries"]),
    ("non_nav_boundaries", ["--layers", "non_navigable_boundaries"]),
    ("graph_base_dual", ["--preset", "graph-base-dual"]),
    ("graph_space_adjacency", ["--preset", "graph-space-adjacency"]),
    ("graph_space_connectivity", ["--preset", "graph-space-connectivity"]),
    ("graph_room_adjacency", ["--preset", "graph-room-adjacency"]),
    ("graph_room_to_room", ["--preset", "graph-room-to-room"]),
    ("graph_room_transfer", ["--preset", "graph-room-transfer"]),
    ("graph_transfer_to_transfer", ["--preset", "graph-transfer-to-transfer"]),
    ("graph_door_to_door", ["--preset", "graph-door-to-door"]),
    ("graph_vertical", ["--preset", "graph-vertical"]),
    ("graph_multilevel_vertical", ["--preset", "graph-multilevel-vertical"]),
    ("overlaps", ["--preset", "overlaps"]),
]


def latest_model(model_dir: Path) -> Path:
    candidates = sorted(model_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"No indoor_model JSON files found in {model_dir}")
    return candidates[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Visualize the latest indoor_model export with standard views.")
    parser.add_argument("--model", type=Path, help="Specific model JSON. Defaults to the newest JSON in outputs/indoor_models.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR, help="Directory used when --model is omitted.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for generated PNG files.")
    parser.add_argument("--level", default="LEVEL_00", help="Level id to render.")
    parser.add_argument("--split-levels", action="store_true", help="Save one PNG per level for each selected view.")
    parser.add_argument("--all-levels", action="store_true", help="Render all levels where supported instead of a single --level.")
    parser.add_argument("--fail-on-overlap", action="store_true", help="Fail when overlap check finds CellSpace overlaps.")
    parser.add_argument("--show", action="store_true", help="Open Matplotlib windows instead of using --no-show.")
    parser.add_argument(
        "--only",
        choices=[name for name, _ in VIEWS],
        nargs="+",
        help="Optional subset of views to render.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    model = args.model or latest_model(args.model_dir)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = set(args.only or [name for name, _ in VIEWS])

    print(f"Using model: {model}")
    for name, view_args in VIEWS:
        if name not in selected:
            continue
        save_path = output_dir / f"{model.stem}_{args.level}_{name}.png"
        cmd = [
            sys.executable,
            str(VISUALIZER),
            str(model),
            *view_args,
            "--labels",
            "none",
            "--save",
            str(save_path),
        ]
        if args.split_levels:
            cmd.append("--split-levels")
        elif args.all_levels or name == "graph_multilevel_vertical":
            cmd.append("--all-levels")
        else:
            cmd.extend(["--level", args.level])
        if not args.show:
            cmd.append("--no-show")
        if name == "overlaps" and args.fail_on_overlap:
            cmd.append("--fail-on-overlap")
        print(" ".join(cmd))
        subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

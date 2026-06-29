#!/usr/bin/env python3
"""Create an organized models/<project> workspace from an IndoorModel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.spatial_engine.project_workspace import create_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create models/<name> with spatial/, evacuation/ and outputs/ folders."
    )
    parser.add_argument("--name", required=True, help="Workspace name, for example Single_Floor_01.")
    parser.add_argument("--indoor", required=True, type=Path, help="IndoorModel JSON to copy into the workspace.")
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        type=Path,
        help="Scenario JSON to copy and relink. Repeat for several scenarios.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace existing copied files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = create_workspace(args.name, args.indoor, args.scenario, overwrite=args.overwrite)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

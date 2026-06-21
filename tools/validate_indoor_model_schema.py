#!/usr/bin/env python3
"""Validate an indoor_model JSON against schemas/indoor/indoor_model.schema.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_DIR = REPO_ROOT / "outputs" / "indoor_models"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "indoor" / "indoor_model.schema.json"


def latest_model(model_dir: Path) -> Path:
    candidates = sorted(model_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"No indoor_model JSON files found in {model_dir}")
    return candidates[0]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} does not contain a JSON object.")
    return data


def json_path(path_parts: Any) -> str:
    parts = list(path_parts)
    return "/".join(str(part) for part in parts) if parts else "<root>"


def format_value(value: Any, max_chars: int = 320) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        text = repr(value)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def summarize_model(model: dict[str, Any]) -> list[str]:
    layers = model.get("layers") or []
    cells = sum(len(((layer.get("primalSpace") or {}).get("cellSpaceMember") or [])) for layer in layers if isinstance(layer, dict))
    boundaries = sum(len(((layer.get("primalSpace") or {}).get("cellBoundaryMember") or [])) for layer in layers if isinstance(layer, dict))
    nodes = sum(len(((layer.get("dualSpace") or {}).get("nodeMember") or [])) for layer in layers if isinstance(layer, dict))
    edges = sum(len(((layer.get("dualSpace") or {}).get("edgeMember") or [])) for layer in layers if isinstance(layer, dict))
    return [
        f"levels={len(model.get('levels') or [])}",
        f"layers={len(layers)}",
        f"cellSpaces={cells}",
        f"cellBoundaries={boundaries}",
        f"nodes={nodes}",
        f"edges={edges}",
        f"verticalConnectors={len(model.get('verticalConnectors') or [])}",
        f"layerConnections={len(model.get('layerConnections') or [])}",
        f"sourceFeatures={len(model.get('sourceFeatures') or [])}",
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an indoor_model JSON against the project schema.")
    parser.add_argument("model", nargs="?", type=Path, help="Model JSON. Defaults to the newest JSON in outputs/indoor_models.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR, help="Directory used when model is omitted.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="Schema JSON path.")
    parser.add_argument("--max-errors", type=int, default=80, help="Maximum number of validation errors to print.")
    parser.add_argument("--show-value", action="store_true", help="Print the offending JSON value for each error.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    model_path = args.model or latest_model(args.model_dir)
    schema_path = args.schema

    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise SystemExit("jsonschema is not installed in this Python environment.") from exc

    model = load_json(model_path)
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(model), key=lambda error: list(error.absolute_path))

    print(f"Model: {model_path}")
    print(f"Schema: {schema_path}")
    print("Summary: " + ", ".join(summarize_model(model)))

    if not errors:
        print("OK: indoor_model.json validates against the schema.")
        return 0

    print(f"ERROR: {len(errors)} schema validation error(s). Showing first {min(len(errors), args.max_errors)}.")
    for index, error in enumerate(errors[: args.max_errors], start=1):
        print(f"{index}. {json_path(error.absolute_path)}")
        print(f"   {error.message}")
        if error.absolute_schema_path:
            print(f"   schema: {json_path(error.absolute_schema_path)}")
        if args.show_value:
            print("   value:")
            for line in format_value(error.instance).splitlines():
                print(f"     {line}")
    if len(errors) > args.max_errors:
        print(f"... {len(errors) - args.max_errors} more error(s) not shown.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

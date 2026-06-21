#!/usr/bin/env python3
"""Re-export an existing indoor_model.json from its sourceFeatures.

This is useful after builder/detection fixes: if an exported model preserved
sourceFeatures, we can rebuild the authoring snapshot, run space detection
again, and write a fresh indoor_model without reopening the SpatialEngine UI.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from indoor_authoring import (  # noqa: E402
    AuthoringAreaElement,
    AuthoringLineElement,
    BuildingAuthoringState,
    ConnectorEndpoint,
    LevelAuthoringState,
    VerticalConnector,
    detect_all_levels,
)
from indoor_authoring.connectors import _coverage_rings  # noqa: E402
from indoor_data_model import build_indoor_model  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402


DEFAULT_MODEL_DIR = REPO_ROOT / "outputs" / "indoor_models"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "indoor_models"
DEFAULT_VISUAL_DIR = REPO_ROOT / "outputs" / "visual_checks"
SCHEMA_PATH = REPO_ROOT / "schemas" / "indoor" / "indoor_model.schema.json"
VISUALIZE_LATEST = REPO_ROOT / "tools" / "visualize_latest_indoor_model.py"

SOURCE_LINE_TYPES = {
    "wall_centerline": "muro_interior",
    "door_centerline": "puerta_simple",
    "exit_centerline": "salida",
    "window_centerline": "ventana",
    "virtual_boundary_line": "frontera_virtual",
}


def latest_model(model_dir: Path) -> Path:
    candidates = sorted(model_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No indoor_model JSON files found in {model_dir}")
    return candidates[0]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def state_from_indoor_model(model: dict[str, Any], model_name: str | None = None) -> BuildingAuthoringState:
    source_features = list(model.get("sourceFeatures") or [])
    if not source_features:
        raise ValueError("The model does not contain sourceFeatures; it cannot be re-exported without UI authoring data.")

    levels = [_level_from_model(level, index) for index, level in enumerate(model.get("levels") or [])]
    if not levels:
        levels = [LevelAuthoringState(id="LEVEL_00", name="Level 00", order=0, elevation_m=0.0)]

    state = BuildingAuthoringState(
        levels=levels,
        active_level_id=levels[0].id,
    )
    state.project_id = str(model.get("id") or state.project_id)
    state.config["reexportedFromIndoorModel"] = True
    if model_name:
        state.config["modelName"] = model_name

    level_by_id = {level.id: level for level in state.levels}
    for source in source_features:
        _add_source_feature_to_state(state, level_by_id, source)

    state.vertical_connectors = [_connector_from_model(connector) for connector in model.get("verticalConnectors") or []]
    return state


def snapshot_from_indoor_model_source(model: dict[str, Any], model_name: str, run_detection: bool = True) -> dict[str, Any]:
    state = state_from_indoor_model(model, model_name=model_name)
    if run_detection:
        failed = [result for result in detect_all_levels(state) if not result.ok]
        if failed:
            details = "; ".join(f"{result.level_id}: {result.report.get('message')}" for result in failed)
            raise RuntimeError(f"Space detection failed while re-exporting: {details}")

    return state.to_snapshot(
        model_name=model_name,
        canvas=_canvas_from_levels_or_sources(model),
        crs=model.get("crs"),
    )


def reexport_indoor_model(
    input_path: Path,
    output_path: Path | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    model_name: str | None = None,
    edge_mode: str = "navigation",
    validate_schema: bool = True,
) -> Path:
    model = load_json(input_path)
    resolved_name = model_name or _model_name_from_model(model, input_path)
    snapshot = snapshot_from_indoor_model_source(model, resolved_name, run_detection=True)
    rebuilt = _json_ready(build_indoor_model(snapshot, edge_mode=edge_mode))

    output = output_path or default_output_path(input_path, output_dir, edge_mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rebuilt, indent=2, ensure_ascii=False), encoding="utf-8")

    if validate_schema:
        _validate_schema_if_possible(rebuilt)
    return output


def default_output_path(input_path: Path, output_dir: Path, edge_mode: str) -> Path:
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "reexport"
    if edge_mode == "all_adjacency":
        suffix += "_all_adjacency"
    return output_dir / f"{input_path.stem}_{suffix}_{timestamp}.json"


def _level_from_model(level: dict[str, Any], index: int) -> LevelAuthoringState:
    level_id = str(level.get("id") or f"LEVEL_{index:02d}")
    height = _float_or(level.get("heightM"), 3.0)
    elevation = _float_or(level.get("elevationM", level.get("floorZ")), index * height)
    return LevelAuthoringState(
        id=level_id,
        name=str(level.get("name") or level_id),
        order=int(level.get("order", level.get("levelIndex", index)) or index),
        elevation_m=elevation,
        height_m=height,
        spatial_extent_2d=_polygon_ring(level.get("spatialExtent2D")),
    )


def _add_source_feature_to_state(
    state: BuildingAuthoringState,
    level_by_id: dict[str, LevelAuthoringState],
    source: dict[str, Any],
) -> None:
    source_type = source.get("sourceType")
    attrs = dict(source.get("attributes") or {})
    level_id = str(source.get("level") or state.active_level_id)
    level = level_by_id.get(level_id)
    if level is None:
        level = LevelAuthoringState(id=level_id, name=level_id, order=len(level_by_id), elevation_m=0.0)
        state.levels.append(level)
        level_by_id[level_id] = level

    if source_type in SOURCE_LINE_TYPES:
        coords = _line_coords(source.get("geometry"))
        if len(coords) < 2:
            return
        element_type = str(attrs.get("originalType") or SOURCE_LINE_TYPES[source_type])
        name = str(attrs.get("originalName") or source.get("id") or element_type)
        line_attrs = dict(attrs)
        line_attrs["sourceFeatureId"] = source.get("id")
        element = AuthoringLineElement(
            id=name,
            element_type=element_type,
            start=coords[0],
            end=coords[-1],
            level_id=level_id,
            thickness_m=_optional_float(attrs.get("thicknessM")),
            width_m=_optional_float(attrs.get("widthM")),
            attributes=line_attrs,
        )
        level.add_line(element)
        level.semantic_attributes[element.id] = dict(element.attributes)
        return

    if source_type == "room_polygon":
        footprint = _polygon_ring(source.get("geometry"))
        if not footprint:
            return
        element_type = str(attrs.get("originalType") or "room_polygon")
        name = str(attrs.get("originalName") or source.get("id") or element_type)
        area_attrs = dict(attrs)
        area_attrs["sourceFeatureId"] = source.get("id")
        if element_type == "columna":
            area_attrs.setdefault("clase_indoor", "ObjectSpace")
            area_attrs.setdefault("navigationType", "ObjectSpace")
            area_attrs.setdefault("navigationClass", "NonNavigableSpace")
            area_attrs.setdefault("category", "Column")
            area_attrs.setdefault("function", "Column")
        element = AuthoringAreaElement(
            id=name,
            element_type=element_type,
            footprint=footprint,
            level_id=level_id,
            centroid=_polygon_centroid(footprint),
            attributes=area_attrs,
        )
        level.add_area(element)
        level.semantic_attributes[element.id] = dict(element.attributes)


def _connector_from_model(connector: dict[str, Any]) -> VerticalConnector:
    endpoints = []
    scope = str(connector.get("scope") or "same_level")
    for endpoint in connector.get("endpoints") or []:
        footprint = _footprint_coords(endpoint.get("footprint"))
        attrs = dict(endpoint.get("attributes") or {})
        open_sides = list(endpoint.get("openSides") or [])
        if scope == "inter_level" and open_sides:
            try:
                attrs["sideCoverages"] = _coverage_rings(Polygon(footprint), open_sides)
            except Exception:
                pass
        endpoints.append(
            ConnectorEndpoint(
                id=str(endpoint.get("id") or f"{connector.get('id')}_ENDPOINT"),
                level_id=str(endpoint.get("level") or endpoint.get("levelId") or connector.get("sourceLevel") or "LEVEL_00"),
                footprint=footprint,
                entry_side=endpoint.get("entrySide"),
                exit_side=endpoint.get("exitSide"),
                open_sides=open_sides,
                attributes=attrs,
            )
        )

    return VerticalConnector(
        id=str(connector.get("id") or "VC_REEXPORTED"),
        connector_type=str(connector.get("connectorType") or "Stair"),
        scope=scope,
        endpoints=endpoints,
        source_level=str(connector.get("sourceLevel") or (endpoints[0].level_id if endpoints else "LEVEL_00")),
        target_level=connector.get("targetLevel"),
        from_elevation_m=_float_or(connector.get("fromElevationM"), 0.0),
        to_elevation_m=_float_or(connector.get("toElevationM"), 0.0),
        directionality=str(connector.get("directionality") or "bidirectional"),
        locomotion_types=list(connector.get("locomotionTypes") or ["Walking"]),
        attributes=dict(connector.get("attributes") or {}),
    )


def _line_coords(geometry: dict[str, Any] | None) -> list[tuple[float, float]]:
    if not geometry or geometry.get("type") != "LineString":
        return []
    return [_xy(point) for point in geometry.get("coordinates") or []]


def _polygon_ring(geometry: dict[str, Any] | None) -> list[tuple[float, float]]:
    if not geometry or geometry.get("type") != "Polygon":
        return []
    rings = geometry.get("coordinates") or []
    if not rings:
        return []
    return _footprint_coords(rings[0])


def _footprint_coords(points: Any) -> list[tuple[float, float]]:
    coords = [_xy(point) for point in points or []]
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords.pop()
    return coords


def _xy(point: Any) -> tuple[float, float]:
    return (float(point[0]), float(point[1]))


def _polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _float_or(value: Any, fallback: float) -> float:
    if value is None:
        return float(fallback)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _canvas_from_levels_or_sources(model: dict[str, Any]) -> dict[str, float]:
    points: list[tuple[float, float]] = []
    for level in model.get("levels") or []:
        points.extend(_polygon_ring(level.get("spatialExtent2D")))
    for source in model.get("sourceFeatures") or []:
        geometry = source.get("geometry") or {}
        if geometry.get("type") == "LineString":
            points.extend(_line_coords(geometry))
        elif geometry.get("type") == "Polygon":
            points.extend(_polygon_ring(geometry))
    if not points:
        return {"width": 0.0, "height": 0.0}
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return {"width": float(max_x), "height": float(max_y)}


def _model_name_from_model(model: dict[str, Any], input_path: Path) -> str:
    metadata = model.get("metadata") or {}
    name = metadata.get("name")
    if name:
        return str(name)
    stem = input_path.stem
    if "_indoor_model" in stem:
        return stem.split("_indoor_model", 1)[0]
    return stem


def _validate_schema_if_possible(model: dict[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("Aviso: jsonschema no esta instalado; se omite validacion del schema.")
        return
    schema = load_json(SCHEMA_PATH)
    errors = sorted(Draft202012Validator(schema).iter_errors(model), key=lambda error: list(error.path))
    if errors:
        print("ERROR: indoor_model.json no valida contra schemas/indoor/indoor_model.schema.json")
        for error in errors[:50]:
            path = "/".join(map(str, error.path)) or "<root>"
            print(f" - {path}: {error.message}")
        raise SystemExit(2)
    print("OK: indoor_model.json valida contra schemas/indoor/indoor_model.schema.json")


def _json_ready(value: Any) -> Any:
    """Return JSON-shaped data before schema validation.

    Authoring dataclasses keep points as tuples and sometimes include None for
    optional endpoint sides. json.dump can serialize tuples, but jsonschema sees
    them as Python tuples instead of JSON arrays, so normalize first.
    """
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items() if item is not None}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def run_visual_checks(model_path: Path, level: str, output_dir: Path, fail_on_overlap: bool = False) -> None:
    cmd = [
        sys.executable,
        str(VISUALIZE_LATEST),
        "--model",
        str(model_path),
        "--level",
        level,
        "--output-dir",
        str(output_dir),
    ]
    if fail_on_overlap:
        cmd.append("--fail-on-overlap")
    subprocess.run(cmd, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Re-export an indoor_model JSON from sourceFeatures using the current builder and space detection.",
    )
    parser.add_argument("model", nargs="?", type=Path, help="Existing indoor_model JSON. Defaults to latest output.")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR, help="Directory used when model is omitted.")
    parser.add_argument("--output", type=Path, help="Exact output JSON path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for default output path.")
    parser.add_argument("--model-name", help="Override exported model metadata name.")
    parser.add_argument("--edge-mode", choices=["navigation", "all_adjacency"], default="navigation")
    parser.add_argument("--no-schema", action="store_true", help="Skip schema validation.")
    parser.add_argument("--generate-visual-checks", action="store_true", help="Generate the standard visual check PNGs.")
    parser.add_argument("--visual-output-dir", type=Path, default=DEFAULT_VISUAL_DIR)
    parser.add_argument("--level", default="LEVEL_00", help="Level used for optional visual checks.")
    parser.add_argument("--fail-on-overlap", action="store_true", help="Fail visual overlap check when generating PNGs.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = args.model or latest_model(args.model_dir)
    output_path = reexport_indoor_model(
        input_path=input_path,
        output_path=args.output,
        output_dir=args.output_dir,
        model_name=args.model_name,
        edge_mode=args.edge_mode,
        validate_schema=not args.no_schema,
    )
    print(f"Re-exported indoor_model: {output_path}")
    if args.generate_visual_checks:
        run_visual_checks(output_path, args.level, args.visual_output_dir, fail_on_overlap=args.fail_on_overlap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

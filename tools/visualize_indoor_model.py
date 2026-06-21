#!/usr/bin/env python3
"""Visualize SpatialEngine indoor_model.json exports.

This is a lightweight debugging visualizer for the IndoorJSON-like Indoor Data
Model used by this project. It intentionally performs only a small set of
visual consistency checks; it is not a schema validator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from indoor_data_model.graph_views import derive_graph_views

from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union


plt: Any = None


ALLOWED_LAYERS = {
    "all",
    "source",
    "cells",
    "general",
    "transfer",
    "non_navigable",
    "object",
    "boundaries",
    "navigable_boundaries",
    "non_navigable_boundaries",
    "nodes",
    "edges",
    "dual",
}

GRAPH_VIEWS = {
    "base_dual",
    "space_adjacency",
    "general_space_adjacency",
    "space_connectivity",
    "space_transfer_connectivity",
    "room_adjacency",
    "room_to_room",
    "room_to_room_accessibility",
    "room_transfer_connectivity",
    "transfer_to_transfer",
    "door_to_door",
    "vertical_connectivity",
}

VISUAL_PRESETS = {
    "basic": {"layers": "general,transfer", "labels": "none", "graph_view": None},
    "spaces": {"layers": "general,transfer,object,non_navigable", "labels": "none", "graph_view": None},
    "navigable-boundaries": {"layers": "general,transfer,navigable_boundaries", "labels": "none", "graph_view": None},
    "non-navigable": {"layers": "non_navigable,object", "labels": "none", "graph_view": None},
    "overlaps": {"layers": "general,transfer,object,non_navigable", "labels": "none", "graph_view": None, "show_overlaps": True},
    "graph-base-dual": {"layers": "cells", "labels": "none", "graph_view": "base_dual"},
    "graph-space-adjacency": {"layers": "general,navigable_boundaries", "labels": "none", "graph_view": "space_adjacency"},
    "graph-space-connectivity": {"layers": "general,transfer,navigable_boundaries", "labels": "none", "graph_view": "space_connectivity"},
    "graph-room-adjacency": {"layers": "general,transfer,non_navigable", "labels": "none", "graph_view": "room_adjacency"},
    "graph-room-to-room": {"layers": "general,transfer", "labels": "none", "graph_view": "room_to_room_accessibility"},
    "graph-room-transfer": {"layers": "general,transfer,navigable_boundaries", "labels": "none", "graph_view": "space_connectivity"},
    "graph-transfer-to-transfer": {"layers": "general,transfer,navigable_boundaries,non_navigable_boundaries", "labels": "none", "graph_view": "transfer_to_transfer"},
    "graph-door-to-door": {"layers": "general,transfer", "labels": "none", "graph_view": "door_to_door"},
    "graph-vertical": {"layers": "transfer", "labels": "none", "graph_view": "vertical_connectivity"},
    "graph-multilevel-vertical": {
        "layers": "general,transfer",
        "labels": "none",
        "graph_view": "vertical_connectivity",
        "multilevel_stack": True,
    },
}

OVERLAP_AREA_TOLERANCE = 1e-6
OVERLAP_STYLE = {
    "facecolor": "#ff1744",
    "edgecolor": "#7f0000",
    "alpha": 0.62,
    "linewidth": 1.4,
    "hatch": "xx",
}

CELL_LAYER_BY_NAVIGATION_TYPE = {
    "GeneralSpace": "general",
    "TransferSpace": "transfer",
    "NonNavigableSpace": "non_navigable",
    "ObjectSpace": "object",
}

BOUNDARY_LAYER_BY_TYPE = {
    "NavigableBoundary": "navigable_boundaries",
    "NonNavigableBoundary": "non_navigable_boundaries",
}

CELL_STYLES = {
    "GeneralSpace": {
        "facecolor": "#7fb3d5",
        "edgecolor": "#2874a6",
        "alpha": 0.38,
        "linewidth": 1.2,
        "label": "GeneralSpace",
    },
    "TransferSpace": {
        "facecolor": "#76d7c4",
        "edgecolor": "#138d75",
        "alpha": 0.55,
        "linewidth": 1.4,
        "label": "TransferSpace",
    },
    "NonNavigableSpace": {
        "facecolor": "#bfc4c8",
        "edgecolor": "#566573",
        "alpha": 0.45,
        "linewidth": 1.0,
        "hatch": "///",
        "label": "NonNavigableSpace",
    },
    "ObjectSpace": {
        "facecolor": "#f7dc6f",
        "edgecolor": "#b7950b",
        "alpha": 0.55,
        "linewidth": 1.0,
        "label": "ObjectSpace",
    },
    "fallback": {
        "facecolor": "#d7bde2",
        "edgecolor": "#76448a",
        "alpha": 0.35,
        "linewidth": 1.0,
        "label": "Other CellSpace",
    },
}

BOUNDARY_STYLES = {
    "NavigableBoundary": {
        "color": "#16a085",
        "linewidth": 2.4,
        "linestyle": "-",
        "label": "NavigableBoundary",
    },
    "NonNavigableBoundary": {
        "color": "#2c3e50",
        "linewidth": 1.8,
        "linestyle": "--",
        "label": "NonNavigableBoundary",
    },
    "fallback": {
        "color": "#8e44ad",
        "linewidth": 1.4,
        "linestyle": ":",
        "label": "Other Boundary",
    },
}

SOURCE_LINE_STYLE = {
    "color": "#7f8c8d",
    "linewidth": 0.8,
    "linestyle": "-",
    "alpha": 0.65,
}

SOURCE_POLYGON_STYLE = {
    "color": "#7f8c8d",
    "linewidth": 0.9,
    "linestyle": "--",
    "alpha": 0.75,
}

EDGE_STYLE = {
    "color": "#d35400",
    "linewidth": 1.7,
    "linestyle": "-",
    "alpha": 0.9,
}

GRAPH_VIEW_STYLES = {
    "base_dual": {"color": "#d35400", "linewidth": 1.7, "linestyle": "-"},
    "space_adjacency": {"color": "#8e44ad", "linewidth": 2.0, "linestyle": "--"},
    "general_space_adjacency": {"color": "#8e44ad", "linewidth": 2.0, "linestyle": "--"},
    "space_connectivity": {"color": "#117a65", "linewidth": 2.0, "linestyle": "-"},
    "space_transfer_connectivity": {"color": "#117a65", "linewidth": 2.0, "linestyle": "-"},
    "room_adjacency": {"color": "#5b2c6f", "linewidth": 2.2, "linestyle": "--"},
    "room_to_room": {"color": "#1f618d", "linewidth": 2.2, "linestyle": "-"},
    "room_to_room_accessibility": {"color": "#1f618d", "linewidth": 2.2, "linestyle": "-"},
    "room_transfer_connectivity": {"color": "#117a65", "linewidth": 2.0, "linestyle": "-"},
    "transfer_to_transfer": {"color": "#c0392b", "linewidth": 2.0, "linestyle": ":"},
    "door_to_door": {"color": "#922b21", "linewidth": 2.0, "linestyle": ":"},
    "vertical_connectivity": {"color": "#2e86c1", "linewidth": 2.4, "linestyle": "-."},
}

LEVEL_LABEL_STYLE = {
    "fontsize": 10,
    "fontweight": "bold",
    "color": "#273746",
    "bbox": {"boxstyle": "round,pad=0.25", "facecolor": "#ffffff", "edgecolor": "#85929e", "alpha": 0.9},
}

NODE_STYLE = {
    "s": 40,
    "facecolors": "#ffffff",
    "edgecolors": "#c0392b",
    "linewidths": 1.8,
    "zorder": 8,
}


def configure_matplotlib(no_show: bool) -> None:
    """Select a non-interactive backend only when display is disabled."""
    global plt

    import matplotlib

    if no_show:
        matplotlib.use("Agg", force=True)

    import matplotlib.pyplot as pyplot

    plt = pyplot


def get_pyplot() -> Any:
    global plt
    if plt is None:
        configure_matplotlib(no_show=True)
    return plt


def load_indoor_model(json_path: Path) -> dict[str, Any]:
    """Load an indoor_model.json document."""
    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{json_path} does not contain a JSON object.")
    return data


def nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def item_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or "<sin-id>")


def ref_tail(value: Any) -> str:
    return str(value).split(":")[-1]


def reference_keys(raw_id: Any, layer_id: Any = None, container_id: Any = None) -> set[str]:
    if raw_id is None:
        return set()

    raw = str(raw_id)
    keys = {raw, ref_tail(raw)}
    if layer_id and container_id:
        keys.add(f"{layer_id}:{container_id}:{raw}")
        keys.add(f"{layer_id}:{container_id}:{ref_tail(raw)}")
    return keys


def reference_exists(reference: Any, index: set[str]) -> bool:
    if reference is None:
        return False
    ref = str(reference)
    return ref in index or ref_tail(ref) in index


def display_id(value: Any, raw_ids: bool) -> str:
    text = str(value)
    if raw_ids:
        return text

    text = ref_tail(text)
    prefixes = (
        "CS_L00_",
        "CB_L00_",
        "N_L00_",
        "E_L00_",
        "SF_L00_",
        "CS_",
        "CB_",
        "N_",
        "E_",
        "SF_",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def coord_xy(coord: Any) -> tuple[float, float] | None:
    if not isinstance(coord, (list, tuple)) or len(coord) < 2:
        return None
    try:
        return float(coord[0]), float(coord[1])
    except (TypeError, ValueError):
        return None


def normalize_line_coords(coords: Any) -> list[tuple[float, float]]:
    points = [coord_xy(coord) for coord in as_list(coords)]
    return [point for point in points if point is not None]


def polygon_parts(geometry: Any) -> list[list[list[tuple[float, float]]]]:
    """Return polygons as lists of rings; the first ring is the exterior."""
    if not isinstance(geometry, dict):
        return []

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if geom_type == "Polygon":
        rings: list[list[tuple[float, float]]] = []
        for ring in as_list(coords):
            normalized = normalize_line_coords(ring)
            if len(normalized) >= 3:
                rings.append(normalized)
        return [rings] if rings else []

    if geom_type == "MultiPolygon":
        parts = []
        for polygon_coords in as_list(coords):
            rings = []
            for ring in as_list(polygon_coords):
                normalized = normalize_line_coords(ring)
                if len(normalized) >= 3:
                    rings.append(normalized)
            if rings:
                parts.append(rings)
        return parts

    if geom_type == "GeometryCollection":
        parts = []
        for sub_geometry in as_list(geometry.get("geometries")):
            parts.extend(polygon_parts(sub_geometry))
        return parts

    return []


def line_strings(geometry: Any) -> list[list[tuple[float, float]]]:
    if not isinstance(geometry, dict):
        return []

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if geom_type == "LineString":
        line = normalize_line_coords(coords)
        return [line] if len(line) >= 2 else []

    if geom_type == "MultiLineString":
        lines = []
        for line_coords in as_list(coords):
            line = normalize_line_coords(line_coords)
            if len(line) >= 2:
                lines.append(line)
        return lines

    if geom_type in {"Polygon", "MultiPolygon"}:
        lines = []
        for rings in polygon_parts(geometry):
            for ring in rings:
                if len(ring) >= 2:
                    lines.append(ring)
        return lines

    if geom_type == "GeometryCollection":
        lines = []
        for sub_geometry in as_list(geometry.get("geometries")):
            lines.extend(line_strings(sub_geometry))
        return lines

    return []


def source_line_strings(geometry: Any) -> list[list[tuple[float, float]]]:
    """Return only line-like source geometry, without polygon rings."""
    if not isinstance(geometry, dict):
        return []

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if geom_type == "LineString":
        line = normalize_line_coords(coords)
        return [line] if len(line) >= 2 else []

    if geom_type == "MultiLineString":
        lines = []
        for line_coords in as_list(coords):
            line = normalize_line_coords(line_coords)
            if len(line) >= 2:
                lines.append(line)
        return lines

    if geom_type == "GeometryCollection":
        lines = []
        for sub_geometry in as_list(geometry.get("geometries")):
            lines.extend(source_line_strings(sub_geometry))
        return lines

    return []


def points(geometry: Any) -> list[tuple[float, float]]:
    if not isinstance(geometry, dict):
        return []

    geom_type = geometry.get("type")
    coords = geometry.get("coordinates")

    if geom_type == "Point":
        point = coord_xy(coords)
        return [point] if point is not None else []

    if geom_type == "MultiPoint":
        result = [coord_xy(coord) for coord in as_list(coords)]
        return [point for point in result if point is not None]

    if geom_type == "GeometryCollection":
        result = []
        for sub_geometry in as_list(geometry.get("geometries")):
            result.extend(points(sub_geometry))
        return result

    return []


def cell_geometry(cell: dict[str, Any]) -> Any:
    return nested_get(cell, "cellSpaceGeom", "geometry2D")


def boundary_geometry(boundary: dict[str, Any]) -> Any:
    return nested_get(boundary, "cellBoundaryGeom", "geometry2D")


def collect_indices(model: dict[str, Any]) -> dict[str, Any]:
    records: dict[str, Any] = {
        "cells": [],
        "boundaries": [],
        "nodes": [],
        "edges": [],
        "cell_refs": set(),
        "boundary_refs": set(),
        "node_refs": set(),
        "edge_refs": set(),
    }

    for layer in as_list(model.get("layers")):
        if not isinstance(layer, dict):
            continue

        layer_id = layer.get("id")
        primal = layer.get("primalSpace") if isinstance(layer.get("primalSpace"), dict) else {}
        dual = layer.get("dualSpace") if isinstance(layer.get("dualSpace"), dict) else {}
        primal_id = primal.get("id")
        dual_id = dual.get("id")

        for cell in as_list(primal.get("cellSpaceMember")):
            if not isinstance(cell, dict):
                continue
            records["cells"].append({"layer": layer, "feature": cell})
            records["cell_refs"].update(reference_keys(cell.get("id"), layer_id, primal_id))

        for boundary in as_list(primal.get("cellBoundaryMember")):
            if not isinstance(boundary, dict):
                continue
            records["boundaries"].append({"layer": layer, "feature": boundary})
            records["boundary_refs"].update(reference_keys(boundary.get("id"), layer_id, primal_id))

        for node in as_list(dual.get("nodeMember")):
            if not isinstance(node, dict):
                continue
            records["nodes"].append({"layer": layer, "feature": node})
            records["node_refs"].update(reference_keys(node.get("id"), layer_id, dual_id))

        for edge in as_list(dual.get("edgeMember")):
            if not isinstance(edge, dict):
                continue
            records["edges"].append({"layer": layer, "feature": edge})
            records["edge_refs"].update(reference_keys(edge.get("id"), layer_id, dual_id))

    return records


def level_ids(model: dict[str, Any]) -> list[str]:
    values = []
    for level in as_list(model.get("levels")):
        if isinstance(level, dict) and level.get("id"):
            values.append(str(level["id"]))
    if values:
        return values
    for layer in as_list(model.get("layers")):
        if isinstance(layer, dict) and layer.get("level") and layer["level"] not in values:
            values.append(str(layer["level"]))
    return values


def filter_records_by_level(records: dict[str, Any], level_id: str | None) -> dict[str, Any]:
    if not level_id:
        return records
    filtered = dict(records)
    for key in ("cells", "boundaries", "nodes", "edges"):
        filtered[key] = [record for record in records[key] if record["layer"].get("level") == level_id]
    filtered["cell_refs"] = set()
    filtered["boundary_refs"] = set()
    filtered["node_refs"] = set()
    filtered["edge_refs"] = set()
    for record in filtered["cells"]:
        layer = record["layer"]
        primal = layer.get("primalSpace") or {}
        filtered["cell_refs"].update(reference_keys(record["feature"].get("id"), layer.get("id"), primal.get("id")))
    for record in filtered["boundaries"]:
        layer = record["layer"]
        primal = layer.get("primalSpace") or {}
        filtered["boundary_refs"].update(reference_keys(record["feature"].get("id"), layer.get("id"), primal.get("id")))
    for record in filtered["nodes"]:
        layer = record["layer"]
        dual = layer.get("dualSpace") or {}
        filtered["node_refs"].update(reference_keys(record["feature"].get("id"), layer.get("id"), dual.get("id")))
    for record in filtered["edges"]:
        layer = record["layer"]
        dual = layer.get("dualSpace") or {}
        filtered["edge_refs"].update(reference_keys(record["feature"].get("id"), layer.get("id"), dual.get("id")))
    return filtered


def source_features_for_level(model: dict[str, Any], level_id: str | None) -> list[Any]:
    if not level_id:
        return as_list(model.get("sourceFeatures"))
    return [
        source
        for source in as_list(model.get("sourceFeatures"))
        if isinstance(source, dict) and (source.get("level") or level_id) == level_id
    ]


def validate_model(model: dict[str, Any], records: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    if model.get("featureType") != "IndoorFeatures":
        warnings.append('El documento no declara featureType="IndoorFeatures".')

    for record in records["cells"]:
        cell = record["feature"]
        cell_id = item_id(cell)
        geom = cell_geometry(cell)
        if not polygon_parts(geom):
            warnings.append(f"CellSpace {cell_id} sin geometry2D de poligono dibujable.")

        duality = cell.get("duality")
        if duality and not reference_exists(duality, records["node_refs"]):
            warnings.append(f"CellSpace {cell_id} tiene duality a Node inexistente: {duality}.")

        for boundary_ref in as_list(cell.get("boundedBy")):
            if not reference_exists(boundary_ref, records["boundary_refs"]):
                warnings.append(f"CellSpace {cell_id} boundedBy referencia CellBoundary inexistente: {boundary_ref}.")

    for record in records["boundaries"]:
        boundary = record["feature"]
        boundary_id = item_id(boundary)
        geom = boundary_geometry(boundary)
        if not line_strings(geom):
            warnings.append(f"CellBoundary {boundary_id} sin geometry2D de linea dibujable.")

        duality = boundary.get("duality")
        if duality and not reference_exists(duality, records["edge_refs"]):
            warnings.append(f"CellBoundary {boundary_id} tiene duality a Edge inexistente: {duality}.")

    for record in records["nodes"]:
        node = record["feature"]
        node_id = item_id(node)
        geom = node.get("geometry")
        if not points(geom):
            warnings.append(f"Node {node_id} sin geometry Point dibujable.")

        duality = node.get("duality")
        if duality and not reference_exists(duality, records["cell_refs"]):
            warnings.append(f"Node {node_id} tiene duality a CellSpace inexistente: {duality}.")

    for record in records["edges"]:
        edge = record["feature"]
        edge_id = item_id(edge)
        geom = edge.get("geometry")
        if not line_strings(geom):
            warnings.append(f"Edge {edge_id} sin geometry LineString dibujable.")

        duality = edge.get("duality")
        if duality and not reference_exists(duality, records["boundary_refs"]):
            warnings.append(f"Edge {edge_id} tiene duality a CellBoundary inexistente: {duality}.")

        for node_ref in as_list(edge.get("connects")):
            if not reference_exists(node_ref, records["node_refs"]):
                warnings.append(f"Edge {edge_id} connects referencia Node inexistente: {node_ref}.")

    return warnings


def shapely_polygons(geometry: Any) -> list[ShapelyPolygon]:
    polygons = []
    for rings in polygon_parts(geometry):
        try:
            polygon = ShapelyPolygon(rings[0], rings[1:])
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
        except Exception:
            continue
        if not polygon.is_empty and polygon.area > OVERLAP_AREA_TOLERANCE:
            polygons.append(polygon)
    return polygons


def collect_cell_overlaps(records: dict[str, Any]) -> list[dict[str, Any]]:
    overlaps = []
    cell_records = []
    for record in records["cells"]:
        cell = record["feature"]
        polygons = shapely_polygons(cell_geometry(cell))
        if polygons:
            cell_records.append((record["layer"].get("level"), cell, polygons))

    for index, (level_a, cell_a, polygons_a) in enumerate(cell_records):
        for level_b, cell_b, polygons_b in cell_records[index + 1 :]:
            if level_a != level_b:
                continue
            overlap_area = 0.0
            intersections = []
            for polygon_a in polygons_a:
                for polygon_b in polygons_b:
                    try:
                        intersection = polygon_a.intersection(polygon_b)
                    except Exception:
                        continue
                    if intersection.is_empty:
                        continue
                    overlap_area += intersection.area
                    intersections.append(intersection)
            if overlap_area <= OVERLAP_AREA_TOLERANCE:
                continue
            try:
                geometry = unary_union(intersections)
            except Exception:
                geometry = intersections[0] if intersections else None
            overlaps.append(
                {
                    "level": level_a,
                    "cellA": cell_a,
                    "cellB": cell_b,
                    "area": overlap_area,
                    "geometry": geometry,
                }
            )
    return overlaps


def validate_cell_overlaps(records: dict[str, Any], overlaps: list[dict[str, Any]] | None = None) -> list[str]:
    warnings = []
    for overlap in overlaps if overlaps is not None else collect_cell_overlaps(records):
        cell_a = overlap["cellA"]
        cell_b = overlap["cellB"]
        warnings.append(
                "CellSpace overlap "
                f"level={overlap['level'] or '<sin-nivel>'}: "
                f"{item_id(cell_a)}({cell_a.get('navigationType')}/{cell_a.get('category')}) vs "
                f"{item_id(cell_b)}({cell_b.get('navigationType')}/{cell_b.get('category')}) "
                f"area={overlap['area']:.9f} m2."
        )
    return warnings


def emit_warnings(warnings: list[str]) -> None:
    for message in warnings:
        print(f"[warn] {message}", file=sys.stderr)


def parse_layers(value: str, parser: argparse.ArgumentParser) -> set[str]:
    requested = {part.strip().lower() for part in value.split(",") if part.strip()}
    if not requested:
        parser.error("--layers no puede estar vacio.")

    unknown = requested - ALLOWED_LAYERS
    if unknown:
        parser.error(f"--layers contiene capas no reconocidas: {', '.join(sorted(unknown))}.")

    expanded: set[str] = set()
    for layer in requested:
        if layer == "all":
            expanded.update({"source", "cells", "boundaries", "nodes", "edges"})
        elif layer == "dual":
            expanded.update({"nodes", "edges"})
        else:
            expanded.add(layer)
    return expanded


def cell_selected(cell: dict[str, Any], selected_layers: set[str]) -> bool:
    if "cells" in selected_layers:
        return True
    layer_name = CELL_LAYER_BY_NAVIGATION_TYPE.get(str(cell.get("navigationType")))
    return bool(layer_name and layer_name in selected_layers)


def boundary_selected(boundary: dict[str, Any], selected_layers: set[str]) -> bool:
    if "boundaries" in selected_layers:
        return True
    layer_name = BOUNDARY_LAYER_BY_TYPE.get(str(boundary.get("navigationBoundaryType")))
    return bool(layer_name and layer_name in selected_layers)


def labels_enabled(label_mode: str, feature_kind: str) -> bool:
    return label_mode == "all" or label_mode == feature_kind


def plot_line(ax: Any, coords: list[tuple[float, float]], **style: Any) -> None:
    if len(coords) < 2:
        return
    xs, ys = zip(*coords)
    ax.plot(xs, ys, **style)


def polygon_label_point(geometry: Any) -> tuple[float, float] | None:
    parts = polygon_parts(geometry)
    if not parts or not parts[0]:
        return None

    exterior = parts[0][0]
    if len(exterior) > 1 and exterior[0] == exterior[-1]:
        exterior = exterior[:-1]
    if not exterior:
        return None

    x = sum(point[0] for point in exterior) / len(exterior)
    y = sum(point[1] for point in exterior) / len(exterior)
    return x, y


def line_label_point(geometry: Any) -> tuple[float, float] | None:
    lines = line_strings(geometry)
    if not lines:
        return None

    line = max(lines, key=line_length)
    if len(line) == 2:
        return (line[0][0] + line[1][0]) / 2.0, (line[0][1] + line[1][1]) / 2.0

    total = line_length(line)
    if total <= 0:
        return line[len(line) // 2]

    halfway = total / 2.0
    travelled = 0.0
    for start, end in zip(line, line[1:]):
        segment = ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        if travelled + segment >= halfway and segment > 0:
            ratio = (halfway - travelled) / segment
            return start[0] + ratio * (end[0] - start[0]), start[1] + ratio * (end[1] - start[1])
        travelled += segment
    return line[-1]


def line_length(coords: list[tuple[float, float]]) -> float:
    total = 0.0
    for start, end in zip(coords, coords[1:]):
        total += ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
    return total


def draw_label(ax: Any, x: float, y: float, text: str, color: str = "#1f2d3d") -> None:
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=7,
        color=color,
        zorder=20,
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": "#ffffff",
            "edgecolor": "none",
            "alpha": 0.72,
        },
    )


def draw_source_features(ax: Any, source_features: list[Any]) -> None:
    for source in source_features:
        if not isinstance(source, dict):
            continue
        geometry = source.get("geometry")

        for line in source_line_strings(geometry):
            plot_line(ax, line, zorder=2, **SOURCE_LINE_STYLE)

        for rings in polygon_parts(geometry):
            for ring in rings:
                plot_line(ax, ring, zorder=3, **SOURCE_POLYGON_STYLE)

        for x, y in points(geometry):
            ax.scatter([x], [y], marker="x", c=SOURCE_LINE_STYLE["color"], s=18, linewidths=0.8, zorder=3)


def draw_cell_spaces(
    ax: Any,
    records: dict[str, Any],
    selected_layers: set[str],
    label_mode: str,
    raw_ids: bool,
) -> None:
    for record in records["cells"]:
        cell = record["feature"]
        if not cell_selected(cell, selected_layers):
            continue

        geometry = cell_geometry(cell)
        style = CELL_STYLES.get(str(cell.get("navigationType")), CELL_STYLES["fallback"])

        for rings in polygon_parts(geometry):
            exterior = rings[0]
            patch = MplPolygon(
                exterior,
                closed=True,
                facecolor=style["facecolor"],
                edgecolor=style["edgecolor"],
                linewidth=style["linewidth"],
                alpha=style["alpha"],
                hatch=style.get("hatch"),
                zorder=4,
            )
            ax.add_patch(patch)

            for hole in rings[1:]:
                plot_line(ax, hole, color=style["edgecolor"], linewidth=0.8, linestyle=":", alpha=0.75, zorder=5)

        if labels_enabled(label_mode, "cells"):
            label_point = polygon_label_point(geometry)
            if label_point:
                draw_label(ax, label_point[0], label_point[1], display_id(item_id(cell), raw_ids))


def draw_cell_boundaries(ax: Any, records: dict[str, Any], selected_layers: set[str]) -> None:
    for record in records["boundaries"]:
        boundary = record["feature"]
        if not boundary_selected(boundary, selected_layers):
            continue

        style = BOUNDARY_STYLES.get(str(boundary.get("navigationBoundaryType")), BOUNDARY_STYLES["fallback"])
        for line in line_strings(boundary_geometry(boundary)):
            plot_line(ax, line, zorder=6, **style)


def draw_overlap_areas(
    ax: Any,
    overlaps: list[dict[str, Any]],
    level_id: str | None,
    raw_ids: bool,
) -> None:
    for index, overlap in enumerate(overlaps, start=1):
        if level_id and overlap.get("level") != level_id:
            continue
        geometry = overlap.get("geometry")
        if geometry is None or geometry.is_empty:
            continue
        for rings in polygon_parts(geometry.__geo_interface__):
            patch = MplPolygon(
                rings[0],
                closed=True,
                zorder=30,
                **OVERLAP_STYLE,
            )
            ax.add_patch(patch)
            for hole in rings[1:]:
                plot_line(ax, hole, color=OVERLAP_STYLE["edgecolor"], linewidth=0.9, linestyle=":", alpha=0.9, zorder=31)
        try:
            point = geometry.representative_point()
            x, y = point.x, point.y
        except Exception:
            label_point = polygon_label_point(geometry.__geo_interface__)
            if not label_point:
                continue
            x, y = label_point
        cell_a = overlap["cellA"]
        cell_b = overlap["cellB"]
        label = (
            f"OVERLAP {index}\n"
            f"{overlap['area']:.3f} m2\n"
            f"{display_id(item_id(cell_a), raw_ids)} / {display_id(item_id(cell_b), raw_ids)}"
        )
        draw_label(ax, x, y, label, "#7f0000")


def focus_axis_on_overlaps(ax: Any, overlaps: list[dict[str, Any]], level_id: str | None) -> None:
    geometries = [
        overlap.get("geometry")
        for overlap in overlaps
        if (not level_id or overlap.get("level") == level_id) and overlap.get("geometry") is not None
    ]
    geometries = [geometry for geometry in geometries if not geometry.is_empty]
    if not geometries:
        return
    try:
        minx, miny, maxx, maxy = unary_union(geometries).bounds
    except Exception:
        return
    width = max(maxx - minx, 0.2)
    height = max(maxy - miny, 0.2)
    margin = max(width, height) * 1.5
    ax.set_xlim(minx - margin, maxx + margin)
    ax.set_ylim(miny - margin, maxy + margin)


def draw_dual_space(
    ax: Any,
    records: dict[str, Any],
    selected_layers: set[str],
    label_mode: str,
    raw_ids: bool,
) -> None:
    if "edges" in selected_layers:
        for record in records["edges"]:
            edge = record["feature"]
            geometry = edge.get("geometry")
            for line in line_strings(geometry):
                plot_line(ax, line, zorder=7, **EDGE_STYLE)

            if labels_enabled(label_mode, "edges"):
                label_point = line_label_point(geometry)
                if label_point:
                    draw_label(ax, label_point[0], label_point[1], display_id(item_id(edge), raw_ids), "#7b3f00")

    if "nodes" in selected_layers:
        for record in records["nodes"]:
            node = record["feature"]
            node_points = points(node.get("geometry"))
            if not node_points:
                continue

            xs = [point[0] for point in node_points]
            ys = [point[1] for point in node_points]
            ax.scatter(xs, ys, **NODE_STYLE)

            if labels_enabled(label_mode, "nodes"):
                for x, y in node_points:
                    draw_label(ax, x, y, display_id(item_id(node), raw_ids), "#922b21")


def draw_graph_view(
    ax: Any,
    model: dict[str, Any],
    graph_view: str | None,
    level_id: str | None,
    label_mode: str,
    raw_ids: bool,
) -> None:
    if not graph_view:
        return
    views = derive_graph_views(model)
    view = views.get(graph_view)
    if not view:
        return
    positions = graph_positions(model, level_id)
    style = GRAPH_VIEW_STYLES.get(graph_view, GRAPH_VIEW_STYLES["base_dual"])
    for node in as_list(view.get("nodes")):
        node_id = str(node.get("id"))
        if node_id in positions or ref_tail(node_id) in positions:
            continue
        if isinstance(node.get("geometry"), dict):
            pts = points(node["geometry"])
            if pts:
                positions[node_id] = pts[0]

    for edge in as_list(view.get("edges")):
        connects = as_list(edge.get("connects"))
        if len(connects) < 2:
            continue
        p1 = positions.get(ref_tail(connects[0])) or positions.get(str(connects[0]))
        p2 = positions.get(ref_tail(connects[1])) or positions.get(str(connects[1]))
        if p1 is None or p2 is None:
            continue
        plot_line(ax, [p1, p2], zorder=12, alpha=0.95, **style)
        if labels_enabled(label_mode, "edges"):
            draw_label(ax, (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0, display_id(edge.get("id", ""), raw_ids), style["color"])

    node_points = []
    for node in as_list(view.get("nodes")):
        node_id = str(node.get("id"))
        point = positions.get(ref_tail(node_id)) or positions.get(node_id)
        if point is None and isinstance(node.get("geometry"), dict):
            pts = points(node["geometry"])
            point = pts[0] if pts else None
        if point is None:
            continue
        node_points.append((node_id, point))
    if node_points:
        xs = [point[0] for _, point in node_points]
        ys = [point[1] for _, point in node_points]
        ax.scatter(xs, ys, s=36, facecolors="#ffffff", edgecolors=style["color"], linewidths=1.6, zorder=13)
        if labels_enabled(label_mode, "nodes"):
            for node_id, (x, y) in node_points:
                draw_label(ax, x, y, display_id(node_id, raw_ids), style["color"])


def draw_graph_view_with_positions(
    ax: Any,
    view: dict[str, Any],
    positions: dict[str, tuple[float, float]],
    graph_view: str,
    label_mode: str,
    raw_ids: bool,
    zorder: int = 12,
) -> None:
    style = GRAPH_VIEW_STYLES.get(graph_view, GRAPH_VIEW_STYLES["base_dual"])
    for node in as_list(view.get("nodes")):
        node_id = str(node.get("id"))
        if node_id in positions or ref_tail(node_id) in positions:
            continue
        if isinstance(node.get("geometry"), dict):
            pts = points(node["geometry"])
            if pts:
                positions[node_id] = pts[0]

    for edge in as_list(view.get("edges")):
        connects = as_list(edge.get("connects"))
        if len(connects) < 2:
            continue
        p1 = positions.get(ref_tail(connects[0])) or positions.get(str(connects[0]))
        p2 = positions.get(ref_tail(connects[1])) or positions.get(str(connects[1]))
        if p1 is None or p2 is None:
            continue
        plot_line(ax, [p1, p2], zorder=zorder, alpha=0.95, **style)
        if labels_enabled(label_mode, "edges"):
            draw_label(ax, (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0, display_id(edge.get("id", ""), raw_ids), style["color"])

    node_points = []
    for node in as_list(view.get("nodes")):
        node_id = str(node.get("id"))
        point = positions.get(ref_tail(node_id)) or positions.get(node_id)
        if point is None:
            continue
        node_points.append((node_id, point))
    if node_points:
        xs = [point[0] for _, point in node_points]
        ys = [point[1] for _, point in node_points]
        ax.scatter(xs, ys, s=36, facecolors="#ffffff", edgecolors=style["color"], linewidths=1.6, zorder=zorder + 1)
        if labels_enabled(label_mode, "nodes"):
            for node_id, (x, y) in node_points:
                draw_label(ax, x, y, display_id(node_id, raw_ids), style["color"])


def graph_positions(model: dict[str, Any], level_id: str | None) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    records = filter_records_by_level(collect_indices(model), level_id)
    for record in records["cells"]:
        cell = record["feature"]
        point = polygon_label_point(cell_geometry(cell))
        if point:
            positions[item_id(cell)] = point
    for record in records["nodes"]:
        node = record["feature"]
        pts = points(node.get("geometry"))
        if pts:
            positions[item_id(node)] = pts[0]
    for record in records["boundaries"]:
        boundary = record["feature"]
        if boundary.get("isVirtual"):
            point = line_label_point(boundary_geometry(boundary))
            if point:
                positions[f"VTN_{item_id(boundary)}"] = point
    return positions


def offset_point(point: tuple[float, float], y_offset: float) -> tuple[float, float]:
    return (float(point[0]), float(point[1]) + float(y_offset))


def offset_geometry(geometry: Any, y_offset: float) -> Any:
    if not isinstance(geometry, dict):
        return geometry
    geom_type = geometry.get("type")
    shifted = dict(geometry)

    def shift_coord(coord: Any) -> Any:
        if not isinstance(coord, (list, tuple)) or len(coord) < 2:
            return coord
        result = list(coord)
        result[1] = float(result[1]) + float(y_offset)
        return result

    def shift_coords(coords: Any, depth: int) -> Any:
        if depth <= 0:
            return shift_coord(coords)
        return [shift_coords(item, depth - 1) for item in as_list(coords)]

    if geom_type == "Point":
        shifted["coordinates"] = shift_coord(geometry.get("coordinates"))
    elif geom_type in {"LineString", "MultiPoint"}:
        shifted["coordinates"] = shift_coords(geometry.get("coordinates"), 1)
    elif geom_type in {"Polygon", "MultiLineString"}:
        shifted["coordinates"] = shift_coords(geometry.get("coordinates"), 2)
    elif geom_type == "MultiPolygon":
        shifted["coordinates"] = shift_coords(geometry.get("coordinates"), 3)
    elif geom_type == "GeometryCollection":
        shifted["geometries"] = [offset_geometry(item, y_offset) for item in as_list(geometry.get("geometries"))]
    return shifted


def translated_records(records: dict[str, Any], y_offset: float) -> dict[str, Any]:
    translated = dict(records)
    translated["cells"] = []
    translated["boundaries"] = []
    translated["nodes"] = []
    translated["edges"] = []
    for record in records["cells"]:
        feature = dict(record["feature"])
        copied = dict(record)
        copied["feature"] = feature
        geom = nested_get(feature, "cellSpaceGeom", "geometry2D")
        if isinstance(geom, dict):
            feature["cellSpaceGeom"] = dict(feature.get("cellSpaceGeom") or {})
            feature["cellSpaceGeom"]["geometry2D"] = offset_geometry(geom, y_offset)
        translated["cells"].append(copied)
    for record in records["boundaries"]:
        feature = dict(record["feature"])
        copied = dict(record)
        copied["feature"] = feature
        geom = nested_get(feature, "cellBoundaryGeom", "geometry2D")
        if isinstance(geom, dict):
            feature["cellBoundaryGeom"] = dict(feature.get("cellBoundaryGeom") or {})
            feature["cellBoundaryGeom"]["geometry2D"] = offset_geometry(geom, y_offset)
        translated["boundaries"].append(copied)
    for record in records["nodes"]:
        feature = dict(record["feature"])
        copied = dict(record)
        copied["feature"] = feature
        feature["geometry"] = offset_geometry(feature.get("geometry"), y_offset)
        translated["nodes"].append(copied)
    for record in records["edges"]:
        feature = dict(record["feature"])
        copied = dict(record)
        copied["feature"] = feature
        feature["geometry"] = offset_geometry(feature.get("geometry"), y_offset)
        translated["edges"].append(copied)
    return translated


def translated_source_features(source_features: list[Any], y_offset: float) -> list[Any]:
    translated = []
    for source in source_features:
        if isinstance(source, dict):
            copied = dict(source)
            copied["geometry"] = offset_geometry(copied.get("geometry"), y_offset)
        else:
            copied = source
        translated.append(copied)
    return translated


def level_bounds(records: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points: list[tuple[float, float]] = []
    for record in records["cells"]:
        for rings in polygon_parts(cell_geometry(record["feature"])):
            for ring in rings:
                for point in ring:
                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                        try:
                            points.append((float(point[0]), float(point[1])))
                        except (TypeError, ValueError):
                            continue
    for record in records["boundaries"]:
        for coords in line_strings(boundary_geometry(record["feature"])):
            for point in coords:
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    try:
                        points.append((float(point[0]), float(point[1])))
                    except (TypeError, ValueError):
                        continue
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def stacked_offsets(model: dict[str, Any], records: dict[str, Any]) -> tuple[list[str], dict[str, float], float]:
    levels = level_ids(model)
    bounds_by_level = {}
    max_height = 1.0
    for level_id in levels:
        bounds = level_bounds(filter_records_by_level(records, level_id))
        if bounds is None:
            continue
        bounds_by_level[level_id] = bounds
        max_height = max(max_height, bounds[3] - bounds[1])
    step = max(max_height * 1.35, max_height + 4.0, 4.0)
    return levels, {level_id: index * step for index, level_id in enumerate(levels)}, step


def stacked_graph_positions(model: dict[str, Any], level_offsets: dict[str, float]) -> dict[str, tuple[float, float]]:
    positions = {}
    for level_id, y_offset in level_offsets.items():
        for key, point in graph_positions(model, level_id).items():
            positions[key] = offset_point(point, y_offset)
    return positions


def draw_multilevel_stack(
    model: dict[str, Any],
    records: dict[str, Any],
    selected_layers: set[str],
    label_mode: str,
    raw_ids: bool,
    graph_view: str | None = None,
) -> tuple[Any, Any]:
    pyplot = get_pyplot()
    fig, ax = pyplot.subplots(figsize=(13, 10))
    levels, offsets, step = stacked_offsets(model, records)
    if not levels:
        raise ValueError("No hay niveles para dibujar en multilevel stack.")

    all_bounds = []
    for level_id in levels:
        y_offset = offsets[level_id]
        level_records = filter_records_by_level(records, level_id)
        translated = translated_records(level_records, y_offset)
        if "source" in selected_layers:
            draw_source_features(ax, translated_source_features(source_features_for_level(model, level_id), y_offset))
        draw_cell_spaces(ax, translated, selected_layers, label_mode, raw_ids)
        draw_cell_boundaries(ax, translated, selected_layers)
        draw_dual_space(ax, translated, selected_layers, label_mode, raw_ids)
        bounds = level_bounds(level_records)
        if bounds:
            minx, miny, maxx, maxy = bounds
            all_bounds.append((minx, miny + y_offset, maxx, maxy + y_offset))
            ax.axhline(miny + y_offset, color="#d5d8dc", linewidth=0.8, zorder=1)
            ax.text(minx, maxy + y_offset + step * 0.03, level_id, zorder=30, **LEVEL_LABEL_STYLE)

    positions = stacked_graph_positions(model, offsets)
    views = derive_graph_views(model)
    if graph_view and graph_view in views:
        draw_graph_view_with_positions(ax, views[graph_view], positions, graph_view, label_mode, raw_ids, zorder=12)
    vertical = views.get("vertical_connectivity")
    if vertical and graph_view != "vertical_connectivity":
        draw_graph_view_with_positions(ax, vertical, positions, "vertical_connectivity", label_mode, raw_ids, zorder=16)

    metadata = model.get("metadata") if isinstance(model.get("metadata"), dict) else {}
    title = str(metadata.get("name") or model.get("id") or "indoor_model.json")
    if graph_view:
        title += f" - stacked levels - {graph_view} + vertical_connectivity"
    else:
        title += " - stacked levels"
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("stacked y by level")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="#e5e8e8", linewidth=0.6)
    if all_bounds:
        minx = min(bounds[0] for bounds in all_bounds)
        miny = min(bounds[1] for bounds in all_bounds)
        maxx = max(bounds[2] for bounds in all_bounds)
        maxy = max(bounds[3] for bounds in all_bounds)
        margin = max(maxx - minx, maxy - miny, 1.0) * 0.05
        ax.set_xlim(minx - margin, maxx + margin)
        ax.set_ylim(miny - margin, maxy + margin)
    has_legend = add_legend(ax, selected_layers, graph_view or "vertical_connectivity")
    if has_legend:
        fig.subplots_adjust(right=0.78)
    else:
        fig.subplots_adjust(left=0.08, right=0.96, top=0.92, bottom=0.08)
    return fig, ax


def add_legend(ax: Any, selected_layers: set[str], graph_view: str | None = None) -> bool:
    handles: list[Any] = []

    if "source" in selected_layers:
        handles.append(Line2D([0], [0], label="source line", **SOURCE_LINE_STYLE))
        handles.append(Line2D([0], [0], label="source polygon", **SOURCE_POLYGON_STYLE))

    cell_types = []
    if "cells" in selected_layers:
        cell_types = ["GeneralSpace", "TransferSpace", "NonNavigableSpace", "ObjectSpace"]
    else:
        for nav_type, layer_name in CELL_LAYER_BY_NAVIGATION_TYPE.items():
            if layer_name in selected_layers:
                cell_types.append(nav_type)

    for nav_type in cell_types:
        style = CELL_STYLES[nav_type]
        handles.append(
            Patch(
                facecolor=style["facecolor"],
                edgecolor=style["edgecolor"],
                hatch=style.get("hatch"),
                alpha=style["alpha"],
                label=style["label"],
            )
        )

    boundary_types = []
    if "boundaries" in selected_layers:
        boundary_types = ["NavigableBoundary", "NonNavigableBoundary"]
    else:
        for boundary_type, layer_name in BOUNDARY_LAYER_BY_TYPE.items():
            if layer_name in selected_layers:
                boundary_types.append(boundary_type)

    for boundary_type in boundary_types:
        handles.append(Line2D([0], [0], **BOUNDARY_STYLES[boundary_type]))

    if "edges" in selected_layers:
        handles.append(Line2D([0], [0], label="Edge", **EDGE_STYLE))
    if "nodes" in selected_layers:
        handles.append(
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=NODE_STYLE["facecolors"],
                markeredgecolor=NODE_STYLE["edgecolors"],
                markeredgewidth=NODE_STYLE["linewidths"],
                label="Node",
            )
        )

    if graph_view:
        style = GRAPH_VIEW_STYLES.get(graph_view, GRAPH_VIEW_STYLES["base_dual"])
        handles.append(Line2D([0], [0], label=f"Graph: {graph_view}", **style))

    if handles:
        ax.legend(
            handles=handles,
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            borderaxespad=0.0,
            fontsize=8,
            framealpha=0.88,
        )
        return True
    return False


def draw_model(
    model: dict[str, Any],
    records: dict[str, Any],
    selected_layers: set[str],
    label_mode: str,
    raw_ids: bool,
    level_id: str | None = None,
    graph_view: str | None = None,
    overlap_records: list[dict[str, Any]] | None = None,
    show_overlaps: bool = False,
    focus_overlaps: bool = False,
) -> tuple[Any, Any]:
    pyplot = get_pyplot()
    fig, ax = pyplot.subplots(figsize=(12, 8))

    if "source" in selected_layers:
        draw_source_features(ax, source_features_for_level(model, level_id))

    draw_cell_spaces(ax, records, selected_layers, label_mode, raw_ids)
    draw_cell_boundaries(ax, records, selected_layers)
    draw_dual_space(ax, records, selected_layers, label_mode, raw_ids)
    draw_graph_view(ax, model, graph_view, level_id, label_mode, raw_ids)
    if show_overlaps and overlap_records:
        draw_overlap_areas(ax, overlap_records, level_id, raw_ids)

    metadata = model.get("metadata") if isinstance(model.get("metadata"), dict) else {}
    title_parts = [str(metadata.get("name") or model.get("id") or "indoor_model.json")]
    if level_id:
        title_parts.append(level_id)
    if graph_view:
        title_parts.append(graph_view)
    if model.get("id") and metadata.get("name") != model.get("id"):
        title_parts.append(str(model.get("id")))
    ax.set_title(" - ".join(title_parts))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="#e5e8e8", linewidth=0.6)
    if focus_overlaps and overlap_records:
        focus_axis_on_overlaps(ax, overlap_records, level_id)
    ax.margins(0.05)
    has_legend = add_legend(ax, selected_layers, graph_view)
    if has_legend:
        fig.tight_layout(rect=(0, 0, 0.82, 1))
    else:
        fig.tight_layout()
    return fig, ax


def resolve_save_path(json_path: Path, save_value: str | None) -> Path:
    if save_value:
        return Path(save_value)
    return json_path.with_name(f"{json_path.stem}_visualization.png")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Visualize SpatialEngine indoor_model.json files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("json_path", type=Path, help="Path to an indoor_model.json file.")
    parser.add_argument(
        "--layers",
        default="all",
        help=(
            "Comma-separated layers: all, source, cells, general, transfer, non_navigable, "
            "object, boundaries, navigable_boundaries, non_navigable_boundaries, nodes, edges, dual."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=tuple(sorted(VISUAL_PRESETS)),
        default=None,
        help="Clean preset that sets layers, labels, and graph-view for common visual checks.",
    )
    parser.add_argument(
        "--labels",
        choices=("none", "cells", "nodes", "edges", "all"),
        default="cells",
        help="Feature labels to draw.",
    )
    parser.add_argument("--level", help="Level id to render, for example LEVEL_00.")
    parser.add_argument("--all-levels", action="store_true", help="Render all levels in separated panels.")
    parser.add_argument("--split-levels", action="store_true", help="Save one PNG per level.")
    parser.add_argument(
        "--multilevel-stack",
        action="store_true",
        help="Render all levels stacked in one 2.5D figure and overlay vertical connectivity.",
    )
    parser.add_argument(
        "--graph-view",
        choices=tuple(sorted(GRAPH_VIEWS)),
        default=None,
        help="Overlay a derived graph view.",
    )
    parser.add_argument("--raw-ids", action="store_true", help="Use full raw IDs in labels.")
    parser.add_argument(
        "--fail-on-overlap",
        action="store_true",
        help="Exit with code 3 when any same-level CellSpace overlap is detected.",
    )
    parser.add_argument(
        "--show-overlaps",
        action="store_true",
        help="Draw same-level CellSpace overlaps as red hatched polygons.",
    )
    parser.add_argument(
        "--focus-overlaps",
        action="store_true",
        help="Zoom the figure around detected overlaps. Use together with --show-overlaps or --preset overlaps.",
    )
    parser.add_argument(
        "--save",
        nargs="?",
        const="",
        default=None,
        metavar="PATH",
        help="Save the figure. If PATH is omitted, save next to the JSON file.",
    )
    parser.add_argument("--no-show", action="store_true", help="Do not open the Matplotlib window.")
    return parser


def save_split_levels(
    model: dict[str, Any],
    records: dict[str, Any],
    args: argparse.Namespace,
    selected_layers: set[str],
    overlap_records: list[dict[str, Any]],
) -> list[Path]:
    saved = []
    base_path = resolve_save_path(args.json_path, args.save)
    for level_id in level_ids(model):
        level_records = filter_records_by_level(records, level_id)
        fig, _ = draw_model(
            model,
            level_records,
            selected_layers,
            args.labels,
            args.raw_ids,
            level_id=level_id,
            graph_view=args.graph_view,
            overlap_records=overlap_records,
            show_overlaps=args.show_overlaps,
            focus_overlaps=args.focus_overlaps,
        )
        save_path = base_path.with_name(f"{base_path.stem}_{level_id}{base_path.suffix}")
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        get_pyplot().close(fig)
        saved.append(save_path)
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.preset:
        preset = VISUAL_PRESETS[args.preset]
        if args.layers == parser.get_default("layers"):
            args.layers = preset["layers"]
        if args.labels == parser.get_default("labels"):
            args.labels = preset["labels"]
        if args.graph_view is None:
            args.graph_view = preset["graph_view"]
        if preset.get("show_overlaps"):
            args.show_overlaps = True
        if preset.get("multilevel_stack"):
            args.multilevel_stack = True
    selected_layers = parse_layers(args.layers, parser)

    try:
        configure_matplotlib(args.no_show)
        model = load_indoor_model(args.json_path)
        records = collect_indices(model)
        validation_warnings = validate_model(model, records)
        overlap_records = collect_cell_overlaps(records)
        overlap_warnings = validate_cell_overlaps(records, overlap_records)
        emit_warnings(validation_warnings + overlap_warnings)
        if args.fail_on_overlap and overlap_warnings:
            parser.exit(3, f"error: {len(overlap_warnings)} CellSpace overlap(s) detected.\n")
        target_levels = level_ids(model)
        if args.multilevel_stack:
            fig, _ = draw_multilevel_stack(
                model,
                records,
                selected_layers,
                args.labels,
                args.raw_ids,
                graph_view=args.graph_view,
            )
            if args.save is not None:
                save_path = resolve_save_path(args.json_path, args.save)
                fig.savefig(save_path, dpi=160)
                print(f"Saved visualization to {save_path}")
            if args.no_show:
                get_pyplot().close(fig)
            else:
                get_pyplot().show()
            return 0
        if args.split_levels or (args.all_levels and not args.level and args.save is not None):
            saved = save_split_levels(model, records, args, selected_layers, overlap_records)
            for save_path in saved:
                print(f"Saved visualization to {save_path}")
            return 0
        if args.all_levels and not args.level:
            figs = []
            for each_level in target_levels:
                level_records = filter_records_by_level(records, each_level)
                fig, _ = draw_model(
                    model,
                    level_records,
                    selected_layers,
                    args.labels,
                    args.raw_ids,
                    level_id=each_level,
                    graph_view=args.graph_view,
                    overlap_records=overlap_records,
                    show_overlaps=args.show_overlaps,
                    focus_overlaps=args.focus_overlaps,
                )
                figs.append(fig)
            if args.no_show:
                for fig in figs:
                    get_pyplot().close(fig)
            else:
                get_pyplot().show()
            return 0

        level_id = args.level
        if not level_id and not args.all_levels:
            level_id = target_levels[0] if target_levels else None
        if level_id:
            records = filter_records_by_level(records, level_id)
        fig, _ = draw_model(
            model,
            records,
            selected_layers,
            args.labels,
            args.raw_ids,
            level_id=level_id,
            graph_view=args.graph_view,
            overlap_records=overlap_records,
            show_overlaps=args.show_overlaps,
            focus_overlaps=args.focus_overlaps,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")

    if args.save is not None:
        save_path = resolve_save_path(args.json_path, args.save)
        fig.savefig(save_path, dpi=200, bbox_inches="tight")
        print(f"Saved visualization to {save_path}")

    if args.no_show:
        get_pyplot().close(fig)
    else:
        get_pyplot().show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

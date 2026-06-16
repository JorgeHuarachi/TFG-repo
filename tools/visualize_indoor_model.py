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

from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.patches import Polygon as MplPolygon


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


def add_legend(ax: Any, selected_layers: set[str]) -> None:
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

    if handles:
        ax.legend(handles=handles, loc="best", fontsize=8, framealpha=0.88)


def draw_model(
    model: dict[str, Any],
    records: dict[str, Any],
    selected_layers: set[str],
    label_mode: str,
    raw_ids: bool,
) -> tuple[Any, Any]:
    pyplot = get_pyplot()
    fig, ax = pyplot.subplots(figsize=(12, 8))

    if "source" in selected_layers:
        draw_source_features(ax, as_list(model.get("sourceFeatures")))

    draw_cell_spaces(ax, records, selected_layers, label_mode, raw_ids)
    draw_cell_boundaries(ax, records, selected_layers)
    draw_dual_space(ax, records, selected_layers, label_mode, raw_ids)

    metadata = model.get("metadata") if isinstance(model.get("metadata"), dict) else {}
    title_parts = [str(metadata.get("name") or model.get("id") or "indoor_model.json")]
    if model.get("id") and metadata.get("name") != model.get("id"):
        title_parts.append(str(model.get("id")))
    ax.set_title(" - ".join(title_parts))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="#e5e8e8", linewidth=0.6)
    ax.margins(0.05)
    add_legend(ax, selected_layers)
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
        "--labels",
        choices=("none", "cells", "nodes", "edges", "all"),
        default="cells",
        help="Feature labels to draw.",
    )
    parser.add_argument("--raw-ids", action="store_true", help="Use full raw IDs in labels.")
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    selected_layers = parse_layers(args.layers, parser)

    try:
        configure_matplotlib(args.no_show)
        model = load_indoor_model(args.json_path)
        records = collect_indices(model)
        emit_warnings(validate_model(model, records))
        fig, _ = draw_model(model, records, selected_layers, args.labels, args.raw_ids)
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

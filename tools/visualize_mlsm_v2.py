"""
Visualizador / verificador ligero para MLSM JSON v2.

Uso estático:
    python tools/visualize_mlsm_v2.py examples/mlsm_v2/minimal_two_spaces.json --layers geometry --labels spaces
    python tools/visualize_mlsm_v2.py examples/mlsm_v2/minimal_two_spaces.json --layers all --graph connectivity_graph --labels graph --save outputs/visual_checks/minimal_connectivity.png

Uso interactivo:
    python tools/visualize_mlsm_v2.py examples/mlsm_v2/minimal_two_spaces.json --interactive
    python tools/visualize_mlsm_v2.py examples/mlsm_v2/rich_single_floor_evacuation.json --interactive

Objetivo:
    Verificar visualmente y de forma rápida:
    - spaces
    - physical_elements
    - boundaries
    - beacons
    - hazards
    - adjacency_graph
    - connectivity_graph
    - door_to_door_graph
    - vertical_connectivity_graph

Notas:
    - No sustituye a SpatialEngine.
    - No valida toda la topología ni la geometría; solo ayuda a detectar errores.
    - Los IDs técnicos siguen siendo la fuente de verdad. Para visualización humana, usa label/name si existen.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.widgets import Button, CheckButtons, RadioButtons


Point2D = Tuple[float, float]


STYLE = {
    "space_default": {
        "facecolor": "#D9ECF7",
        "edgecolor": "#1f77b4",
        "alpha": 0.45,
    },
    "space_transfer_door": {
        "facecolor": "#FFE0A3",
        "edgecolor": "#F28E2B",
        "alpha": 0.75,
    },
    "space_transfer_window": {
        "facecolor": "#D6F5FF",
        "edgecolor": "#17A2B8",
        "alpha": 0.70,
    },
    "space_exit": {
        "facecolor": "#DFF5D8",
        "edgecolor": "#2CA02C",
        "alpha": 0.80,
    },
    "space_object": {
        "facecolor": "#D9D9D9",
        "edgecolor": "#606060",
        "alpha": 0.70,
    },
    "wall": {
        "facecolor": "#2B2B2B",
        "edgecolor": "#000000",
        "alpha": 0.55,
        "linewidth": 1.8,
    },
    "door": {
        "facecolor": "#FFE0A3",
        "edgecolor": "#F28E2B",
        "alpha": 0.90,
        "linewidth": 2.0,
    },
    "window": {
        "facecolor": "#D6F5FF",
        "edgecolor": "#17A2B8",
        "alpha": 0.85,
        "linewidth": 2.0,
    },
    "column": {
        "facecolor": "#D9D9D9",
        "edgecolor": "#606060",
        "alpha": 0.75,
        "linewidth": 1.6,
    },
    "boundary_navigable": {
        "color": "#2CA02C",
        "linewidth": 2.5,
        "linestyle": "-",
    },
    "boundary_non_navigable": {
        "color": "#4D4D4D",
        "linewidth": 1.6,
        "linestyle": "--",
    },
    "boundary_special": {
        "color": "#17A2B8",
        "linewidth": 1.8,
        "linestyle": "-.",
    },
    "graph": {
        "adjacency_graph": "#7F7F7F",
        "connectivity_graph": "#2CA02C",
        "door_to_door_graph": "#9467BD",
        "vertical_connectivity_graph": "#D62728",
        "default": "#333333",
    },
}


DEFAULT_GRAPH_ORDER = [
    "adjacency_graph",
    "connectivity_graph",
    "door_to_door_graph",
    "vertical_connectivity_graph",
]

LAYER_KEYS = ["spaces", "physical", "boundaries", "beacons", "hazards"]


# ---------------------------------------------------------------------------
# Carga y normalización de geometría
# ---------------------------------------------------------------------------

def load_json(path: Path) -> Dict[str, Any]:
    """Carga JSON tolerando algunos problemas típicos de codificación en Windows."""
    raw = path.read_bytes()
    last_error: Optional[Exception] = None

    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            return json.loads(text)
        except UnicodeDecodeError as exc:
            last_error = exc
        except json.JSONDecodeError:
            raise

    raise UnicodeDecodeError(
        "unknown",
        raw,
        0,
        len(raw),
        f"No se pudo decodificar el archivo. Último error: {last_error}",
    )


def as_point(coords: Any) -> Optional[Point2D]:
    """Convierte [x, y] o [x, y, z] en (x, y), si es posible."""
    if isinstance(coords, list) and len(coords) >= 2:
        if isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
            return float(coords[0]), float(coords[1])
    return None


def extract_point(geom: Optional[Dict[str, Any]]) -> Optional[Point2D]:
    if not geom:
        return None
    if geom.get("type") == "Point":
        return as_point(geom.get("coordinates"))
    return None


def normalize_linestring(geom: Optional[Dict[str, Any]]) -> List[Point2D]:
    if not geom or geom.get("type") != "LineString":
        return []

    pts: List[Point2D] = []
    for p in geom.get("coordinates", []):
        point = as_point(p)
        if point:
            pts.append(point)
    return pts


def normalize_polygon(geom: Optional[Dict[str, Any]]) -> List[Point2D]:
    """
    Devuelve el anillo exterior de un Polygon.

    Espera GeoJSON estándar:
        [[[x,y], [x,y], ...]]

    También intenta tolerar una estructura parcialmente mal anidada:
        [[x,y], [x,y], ...]
    """
    if not geom or geom.get("type") != "Polygon":
        return []

    coords = geom.get("coordinates", [])
    if not isinstance(coords, list) or not coords:
        return []

    # Caso GeoJSON correcto: coordinates = [ exterior_ring, hole1, ... ]
    if isinstance(coords[0], list) and coords[0] and isinstance(coords[0][0], list):
        ring = coords[0]
    else:
        # Caso tolerado: coordinates = exterior_ring
        ring = coords

    pts: List[Point2D] = []
    for p in ring:
        point = as_point(p)
        if point:
            pts.append(point)
    return pts


def polygon_centroid(points: List[Point2D]) -> Optional[Point2D]:
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def line_midpoint(points: List[Point2D]) -> Optional[Point2D]:
    if len(points) < 2:
        return None
    x1, y1 = points[0]
    x2, y2 = points[-1]
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def humanize_id(value: str) -> str:
    """
    Convierte IDs técnicos en texto algo más legible si no existe label/name.

    Ejemplos:
        S_DOOR_1 -> Door 1
        PE_WALL_EXT_NORTH -> Wall Ext North
        N_CONN_S1 -> S1
    """
    text = str(value)

    prefixes = [
        "N_CONN_",
        "N_D2D_",
        "N_ADJ_",
        "N_VERT_",
        "N_",
        "E_CONN_",
        "E_D2D_",
        "E_ADJ_",
        "E_VERT_",
        "PE_",
        "SPACE_",
    ]

    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    text = text.replace("_", " ").strip()

    # Mantener IDs muy cortos como S1/S2 sin tocar demasiado.
    if len(text) <= 3 and any(ch.isdigit() for ch in text):
        return text

    return text.title()


def display_label(
    item: Dict[str, Any],
    id_keys: Sequence[str],
    *,
    raw_ids: bool = False,
) -> Optional[str]:
    """
    Devuelve una etiqueta humana para dibujar.

    Prioridad:
    1. label
    2. name
    3. primer ID técnico disponible, humanizado salvo raw_ids=True
    """
    if item.get("label"):
        return str(item["label"])

    if item.get("name"):
        return str(item["name"])

    for key in id_keys:
        value = item.get(key)
        if value:
            return str(value) if raw_ids else humanize_id(str(value))

    return None


# ---------------------------------------------------------------------------
# Índices y posiciones
# ---------------------------------------------------------------------------

def build_space_index(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        s.get("space_id"): s
        for s in data.get("spaces", [])
        if isinstance(s, dict) and s.get("space_id")
    }


def build_physical_element_index(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        e.get("element_id"): e
        for e in data.get("physical_elements", [])
        if isinstance(e, dict) and e.get("element_id")
    }


def get_space_position(space: Dict[str, Any]) -> Optional[Point2D]:
    centroid = extract_point(space.get("centroid_2d"))
    if centroid:
        return centroid

    footprint = normalize_polygon(space.get("footprint_2d"))
    if footprint:
        return polygon_centroid(footprint)

    return None


def get_physical_element_position(elem: Dict[str, Any]) -> Optional[Point2D]:
    # 1. Punto de ancla explícito.
    for key in ("anchor_point", "position", "centerline_2d"):
        point = extract_point(elem.get(key))
        if point:
            return point

    # 2. Punto medio de centerline.
    line = normalize_linestring(elem.get("centerline_2d"))
    if line:
        return line_midpoint(line)

    # 3. Centroide de footprint.
    footprint = normalize_polygon(elem.get("derived_footprint_2d"))
    if footprint:
        return polygon_centroid(footprint)

    return None


def display_graph_node_label(
    node: Dict[str, Any],
    spaces_by_id: Dict[str, Dict[str, Any]],
    elements_by_id: Dict[str, Dict[str, Any]],
    *,
    raw_ids: bool = False,
) -> Optional[str]:
    """Etiqueta humana para nodos de grafo."""
    if node.get("label") or node.get("name"):
        return display_label(node, ["node_id"], raw_ids=raw_ids)

    space_ref = node.get("space_ref") or node.get("space_id")
    if space_ref and space_ref in spaces_by_id:
        return display_label(spaces_by_id[space_ref], ["space_id"], raw_ids=raw_ids)

    elem_ref = node.get("physical_element_ref") or node.get("element_ref")
    if elem_ref and elem_ref in elements_by_id:
        return display_label(elements_by_id[elem_ref], ["element_id"], raw_ids=raw_ids)

    return display_label(node, ["node_id"], raw_ids=raw_ids)


def display_graph_edge_label(
    edge: Dict[str, Any],
    *,
    raw_ids: bool = False,
    show_edge_ids: bool = False,
) -> Optional[str]:
    """
    Etiqueta para aristas de grafo.

    Por defecto no mostramos edge_id, porque ensucia mucho la visualización.
    Se muestra si:
      - edge tiene label/name explícito.
      - show_edge_ids=True.
    """
    if edge.get("label") or edge.get("name"):
        return display_label(edge, ["edge_id"], raw_ids=raw_ids)

    if show_edge_ids:
        return display_label(edge, ["edge_id"], raw_ids=raw_ids)

    return None


def build_node_position_index(
    graph: Dict[str, Any],
    spaces_by_id: Dict[str, Dict[str, Any]],
    elements_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Point2D]:
    positions: Dict[str, Point2D] = {}

    for node in graph.get("nodes", []):
        node_id = node.get("node_id")
        if not node_id:
            continue

        # 1. Posición explícita del nodo.
        pos = extract_point(node.get("position"))
        if pos:
            positions[node_id] = pos
            continue

        # 2. Posición heredada del space_ref.
        space_ref = node.get("space_ref") or node.get("space_id")
        if space_ref and space_ref in spaces_by_id:
            space_pos = get_space_position(spaces_by_id[space_ref])
            if space_pos:
                positions[node_id] = space_pos
                continue

        # 3. Posición heredada de physical_element_ref.
        elem_ref = node.get("physical_element_ref") or node.get("element_ref")
        if elem_ref and elem_ref in elements_by_id:
            elem_pos = get_physical_element_position(elements_by_id[elem_ref])
            if elem_pos:
                positions[node_id] = elem_pos
                continue

    return positions


def get_graph(data: Dict[str, Any], graph_name: str) -> Optional[Dict[str, Any]]:
    graphs = data.get("graphs", {})

    if isinstance(graphs, dict):
        graph = graphs.get(graph_name)
        if isinstance(graph, dict):
            return graph

        # Fallback: buscar por graph_type dentro de values.
        for value in graphs.values():
            if isinstance(value, dict) and value.get("graph_type") == graph_name:
                return value

    if isinstance(graphs, list):
        for graph in graphs:
            if graph.get("graph_id") == graph_name or graph.get("graph_type") == graph_name:
                return graph

    return None


def available_graphs(data: Dict[str, Any]) -> List[str]:
    graphs = data.get("graphs", {})
    found: List[str] = []

    if isinstance(graphs, dict):
        for preferred in DEFAULT_GRAPH_ORDER:
            if preferred in graphs and isinstance(graphs[preferred], dict):
                found.append(preferred)

        # Añadir grafos no previstos.
        for name, graph in graphs.items():
            if name not in found and isinstance(graph, dict):
                found.append(name)

    elif isinstance(graphs, list):
        for graph in graphs:
            name = graph.get("graph_type") or graph.get("graph_id")
            if name:
                found.append(name)

    return found


# ---------------------------------------------------------------------------
# Validación básica
# ---------------------------------------------------------------------------

def validate_basic(data: Dict[str, Any], graph_names: Optional[Sequence[str]]) -> List[str]:
    warnings: List[str] = []

    def check_unique(items: Iterable[Dict[str, Any]], key: str, label: str) -> None:
        seen = set()
        for item in items:
            value = item.get(key)
            if not value:
                warnings.append(f"[WARN] {label} sin {key}")
                continue
            if value in seen:
                warnings.append(f"[WARN] {label} duplicado: {value}")
            seen.add(value)

    check_unique(data.get("spaces", []), "space_id", "space")
    check_unique(data.get("physical_elements", []), "element_id", "physical_element")
    check_unique(data.get("boundaries", []), "boundary_id", "boundary")

    space_ids = {s.get("space_id") for s in data.get("spaces", []) if isinstance(s, dict)}
    element_ids = {e.get("element_id") for e in data.get("physical_elements", []) if isinstance(e, dict)}

    for boundary in data.get("boundaries", []):
        # Estilo antiguo: source_space_id / target_space_id.
        for ref_key in ("source_space_id", "target_space_id"):
            ref = boundary.get(ref_key)
            if ref and ref not in space_ids:
                warnings.append(
                    f"[WARN] boundary {boundary.get('boundary_id')} referencia space inexistente: {ref}"
                )

        # Estilo nuevo: source_ref / target_ref.
        for ref_key in ("source_ref", "target_ref"):
            ref_obj = boundary.get(ref_key)
            if not isinstance(ref_obj, dict):
                continue

            entity_type = ref_obj.get("entity_type")
            entity_id = ref_obj.get("entity_id")
            if entity_type == "space" and entity_id not in space_ids:
                warnings.append(
                    f"[WARN] boundary {boundary.get('boundary_id')} referencia space inexistente: {entity_id}"
                )
            if entity_type == "physical_element" and entity_id not in element_ids:
                warnings.append(
                    f"[WARN] boundary {boundary.get('boundary_id')} referencia physical_element inexistente: {entity_id}"
                )

    if graph_names:
        for graph_name in graph_names:
            graph = get_graph(data, graph_name)
            if not graph:
                warnings.append(f"[WARN] No existe graph '{graph_name}'")
                continue

            check_unique(graph.get("nodes", []), "node_id", f"node en {graph_name}")
            node_ids = {n.get("node_id") for n in graph.get("nodes", []) if isinstance(n, dict)}

            for edge in graph.get("edges", []):
                src = edge.get("source_node_id")
                dst = edge.get("target_node_id")

                if src not in node_ids:
                    warnings.append(
                        f"[WARN] edge {edge.get('edge_id')} apunta a source_node_id inexistente: {src}"
                    )
                if dst not in node_ids:
                    warnings.append(
                        f"[WARN] edge {edge.get('edge_id')} apunta a target_node_id inexistente: {dst}"
                    )

    return warnings


# ---------------------------------------------------------------------------
# Estilos y dibujo
# ---------------------------------------------------------------------------

def style_for_space(space: Dict[str, Any]) -> Dict[str, Any]:
    space_type = space.get("space_type")
    category = space.get("category")

    if space_type == "transfer_space" and category == "door_space":
        return STYLE["space_transfer_door"]

    if space_type == "transfer_space" and category == "window_space":
        return STYLE["space_transfer_window"]

    if space_type == "exit_space" or category in ("exit", "exit_space"):
        return STYLE["space_exit"]

    if space_type == "object_space" or category in ("column", "obstacle"):
        return STYLE["space_object"]

    return STYLE["space_default"]


def style_for_physical_element(elem: Dict[str, Any]) -> Dict[str, Any]:
    element_type = elem.get("element_type")

    if element_type == "wall":
        return STYLE["wall"]

    if element_type == "door":
        return STYLE["door"]

    if element_type == "window":
        return STYLE["window"]

    if element_type == "column":
        return STYLE["column"]

    return {
        "facecolor": "#DDDDDD",
        "edgecolor": "#666666",
        "alpha": 0.55,
        "linewidth": 1.4,
    }


def boundary_style(boundary: Dict[str, Any]) -> Dict[str, Any]:
    boundary_type = boundary.get("boundary_type", "")

    if boundary_type == "navigable_boundary":
        return STYLE["boundary_navigable"]

    if boundary_type in ("opening_boundary", "special_boundary", "non_evacuation_boundary"):
        return STYLE["boundary_special"]

    return STYLE["boundary_non_navigable"]


def draw_polygon(
    ax,
    points: List[Point2D],
    label: Optional[str] = None,
    alpha: Optional[float] = None,
    facecolor: Optional[str] = None,
    edgecolor: Optional[str] = None,
    linewidth: float = 1.4,
) -> None:
    if len(points) < 3:
        return

    patch = MplPolygon(
        points,
        closed=True,
        fill=True,
        alpha=alpha if alpha is not None else 0.18,
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )
    ax.add_patch(patch)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, linewidth=linewidth, color=edgecolor)

    if label:
        c = polygon_centroid(points)
        if c:
            ax.text(
                c[0],
                c[1],
                label,
                fontsize=8,
                ha="center",
                va="center",
                bbox=dict(facecolor="white", alpha=0.65, edgecolor="none", pad=1.5),
            )


def draw_line(
    ax,
    points: List[Point2D],
    label: Optional[str] = None,
    linewidth: float = 1.5,
    color: Optional[str] = None,
    linestyle: str = "-",
) -> None:
    if len(points) < 2:
        return

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, linewidth=linewidth, color=color, linestyle=linestyle)

    if label:
        mid = line_midpoint(points)
        if mid:
            ax.text(
                mid[0],
                mid[1],
                label,
                fontsize=7,
                ha="center",
                va="center",
                bbox=dict(facecolor="white", alpha=0.70, edgecolor="none", pad=1.2),
            )


def draw_point(
    ax,
    point: Point2D,
    label: Optional[str] = None,
    marker: str = "o",
    color: Optional[str] = None,
    size: float = 32.0,
) -> None:
    ax.scatter([point[0]], [point[1]], marker=marker, color=color, s=size, zorder=5)
    if label:
        ax.text(
            point[0],
            point[1],
            f" {label}",
            fontsize=8,
            ha="left",
            va="center",
            bbox=dict(facecolor="white", alpha=0.65, edgecolor="none", pad=1.2),
        )


def draw_spaces(ax, data: Dict[str, Any], show_labels: bool, raw_ids: bool) -> None:
    for space in data.get("spaces", []):
        pts = normalize_polygon(space.get("footprint_2d"))
        label = display_label(space, ["space_id"], raw_ids=raw_ids) if show_labels else None
        style = style_for_space(space)

        draw_polygon(
            ax,
            pts,
            label=label,
            alpha=style["alpha"],
            facecolor=style["facecolor"],
            edgecolor=style["edgecolor"],
            linewidth=1.5,
        )


def draw_physical_elements(ax, data: Dict[str, Any], show_labels: bool, raw_ids: bool) -> None:
    for elem in data.get("physical_elements", []):
        label = display_label(elem, ["element_id"], raw_ids=raw_ids) if show_labels else None
        style = style_for_physical_element(elem)

        footprint = normalize_polygon(elem.get("derived_footprint_2d"))
        if footprint:
            draw_polygon(
                ax,
                footprint,
                label=label,
                alpha=style["alpha"],
                facecolor=style["facecolor"],
                edgecolor=style["edgecolor"],
                linewidth=style["linewidth"],
            )
            continue

        line = normalize_linestring(elem.get("centerline_2d"))
        if line:
            draw_line(
                ax,
                line,
                label=label,
                linewidth=style["linewidth"],
                color=style["edgecolor"],
            )
            continue

        point = extract_point(elem.get("centerline_2d")) or extract_point(elem.get("anchor_point"))
        if point:
            draw_point(ax, point, label=label, marker="s", color=style["edgecolor"])


def draw_boundaries(ax, data: Dict[str, Any], show_labels: bool, raw_ids: bool) -> None:
    for boundary in data.get("boundaries", []):
        line = normalize_linestring(boundary.get("geometry_2d"))
        label = display_label(boundary, ["boundary_id"], raw_ids=raw_ids) if show_labels else None
        style = boundary_style(boundary)

        draw_line(
            ax,
            line,
            label=label,
            linewidth=style["linewidth"],
            color=style["color"],
            linestyle=style["linestyle"],
        )


def draw_beacons(
    ax,
    data: Dict[str, Any],
    show_labels: bool,
    raw_ids: bool,
    show_radius: bool = True,
) -> None:
    for beacon in data.get("beacons", []):
        pos = extract_point(beacon.get("position"))
        if not pos:
            continue

        label = display_label(beacon, ["beacon_id"], raw_ids=raw_ids) if show_labels else None
        draw_point(ax, pos, label=label, marker="*", color="#F2C94C", size=90)

        influence = beacon.get("influence", {})
        radius = influence.get("radius_m")

        if show_radius and isinstance(radius, (int, float)):
            circle = plt.Circle(pos, radius, fill=False, linestyle="--", alpha=0.35)
            ax.add_patch(circle)


def draw_hazards(ax, data: Dict[str, Any], show_labels: bool, raw_ids: bool) -> None:
    for hazard in data.get("hazards", []):
        pos = extract_point(hazard.get("initial_position")) or extract_point(hazard.get("position"))
        if not pos:
            continue

        label = display_label(hazard, ["hazard_id"], raw_ids=raw_ids) if show_labels else None
        draw_point(ax, pos, label=label, marker="x", color="#D62728", size=70)

        growth = hazard.get("growth_model", {})
        radius = (
            growth.get("initial_radius_m")
            or growth.get("initial_radius")
            or hazard.get("initial_radius_m")
        )
        if isinstance(radius, (int, float)):
            circle = plt.Circle(pos, radius, fill=False, linestyle=":", alpha=0.5, color="#D62728")
            ax.add_patch(circle)


def draw_graph(
    ax,
    data: Dict[str, Any],
    graph_name: str,
    show_labels: bool,
    raw_ids: bool,
    show_edge_ids: bool,
) -> None:
    graph = get_graph(data, graph_name)
    if not graph:
        print(f"[WARN] No se encontró el grafo: {graph_name}")
        return

    spaces_by_id = build_space_index(data)
    elements_by_id = build_physical_element_index(data)
    node_positions = build_node_position_index(graph, spaces_by_id, elements_by_id)
    graph_color = STYLE["graph"].get(graph_name, STYLE["graph"]["default"])

    for edge in graph.get("edges", []):
        src = edge.get("source_node_id")
        dst = edge.get("target_node_id")

        label = (
            display_graph_edge_label(edge, raw_ids=raw_ids, show_edge_ids=show_edge_ids)
            if show_labels else None
        )

        line = normalize_linestring(edge.get("geometry_2d"))
        if line:
            draw_line(
                ax,
                line,
                label=label,
                linewidth=2.4,
                color=graph_color,
                linestyle="-",
            )
            continue

        if src in node_positions and dst in node_positions:
            p1 = node_positions[src]
            p2 = node_positions[dst]
            draw_line(
                ax,
                [p1, p2],
                label=label,
                linewidth=2.4,
                color=graph_color,
                linestyle="-",
            )

    for node in graph.get("nodes", []):
        node_id = node.get("node_id")
        if not node_id:
            continue

        pos = node_positions.get(node_id)
        if pos:
            label = (
                display_graph_node_label(node, spaces_by_id, elements_by_id, raw_ids=raw_ids)
                if show_labels else None
            )
            draw_point(ax, pos, label=label, marker="o", color=graph_color, size=40)


# ---------------------------------------------------------------------------
# Render estático e interactivo
# ---------------------------------------------------------------------------

def expand_layers(layers: str) -> Dict[str, bool]:
    """Convierte el argumento --layers en un diccionario de capas visibles."""
    visible = {key: False for key in LAYER_KEYS}

    if layers == "all":
        for key in visible:
            visible[key] = True
        return visible

    if layers == "geometry":
        visible["spaces"] = True
        visible["physical"] = True
        return visible

    if layers == "boundaries":
        visible["spaces"] = True
        visible["boundaries"] = True
        return visible

    if layers == "beacons":
        visible["spaces"] = True
        visible["beacons"] = True
        return visible

    if layers == "hazards":
        visible["spaces"] = True
        visible["hazards"] = True
        return visible

    if layers == "graph":
        visible["spaces"] = True
        return visible

    # Modo avanzado: --layers spaces,physical,boundaries
    for part in layers.split(","):
        key = part.strip()
        if key in visible:
            visible[key] = True

    return visible


def label_flags(labels: str) -> Tuple[bool, bool, bool]:
    """Devuelve (space_labels, graph_labels, other_labels)."""
    return (
        labels in ("spaces", "all"),
        labels in ("graph", "all"),
        labels == "all",
    )


def draw_scene(
    ax,
    data: Dict[str, Any],
    json_name: str,
    layer_visible: Dict[str, bool],
    graph_visible: Dict[str, bool],
    labels: str,
    hide_beacon_radius: bool,
    raw_ids: bool,
    show_edge_ids: bool,
) -> None:
    ax.clear()

    show_space_labels, show_graph_labels, show_other_labels = label_flags(labels)

    if layer_visible.get("spaces"):
        draw_spaces(ax, data, show_labels=show_space_labels, raw_ids=raw_ids)

    if layer_visible.get("physical"):
        draw_physical_elements(ax, data, show_labels=show_other_labels, raw_ids=raw_ids)

    if layer_visible.get("boundaries"):
        draw_boundaries(ax, data, show_labels=show_other_labels, raw_ids=raw_ids)

    if layer_visible.get("beacons"):
        draw_beacons(
            ax,
            data,
            show_labels=show_other_labels,
            raw_ids=raw_ids,
            show_radius=not hide_beacon_radius,
        )

    if layer_visible.get("hazards"):
        draw_hazards(ax, data, show_labels=show_other_labels, raw_ids=raw_ids)

    for graph_name, is_visible in graph_visible.items():
        if is_visible:
            draw_graph(
                ax,
                data,
                graph_name=graph_name,
                show_labels=show_graph_labels,
                raw_ids=raw_ids,
                show_edge_ids=show_edge_ids,
            )

    visible_graphs = [g for g, v in graph_visible.items() if v]
    suffix = f" — {', '.join(visible_graphs)}" if visible_graphs else ""
    ax.set_title(f"{json_name}{suffix}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.grid(True, alpha=0.25)
    ax.set_aspect("equal", adjustable="box")


def visualize_static(
    json_path: Path,
    graph_names: List[str],
    save_path: Optional[Path],
    labels: str,
    layers: str,
    hide_beacon_radius: bool,
    raw_ids: bool,
    show_edge_ids: bool,
) -> None:
    data = load_json(json_path)

    warnings = validate_basic(data, graph_names)
    for w in warnings:
        print(w)

    layer_visible = expand_layers(layers)
    graph_visible = {name: True for name in graph_names}

    fig, ax = plt.subplots(figsize=(12, 8))
    draw_scene(
        ax=ax,
        data=data,
        json_name=json_path.name,
        layer_visible=layer_visible,
        graph_visible=graph_visible,
        labels=labels,
        hide_beacon_radius=hide_beacon_radius,
        raw_ids=raw_ids,
        show_edge_ids=show_edge_ids,
    )

    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=180, bbox_inches="tight")
        print(f"[OK] Imagen guardada en: {save_path}")
    else:
        plt.show()


def visualize_interactive(
    json_path: Path,
    labels: str,
    layers: str,
    hide_beacon_radius: bool,
    raw_ids: bool,
    show_edge_ids: bool,
) -> None:
    data = load_json(json_path)
    graph_names = available_graphs(data)

    warnings = validate_basic(data, graph_names)
    for w in warnings:
        print(w)

    layer_visible = expand_layers(layers)
    graph_visible = {name: False for name in graph_names}

    fig, ax = plt.subplots(figsize=(13.5, 8))
    fig.subplots_adjust(right=0.74)

    draw_scene(
        ax=ax,
        data=data,
        json_name=json_path.name,
        layer_visible=layer_visible,
        graph_visible=graph_visible,
        labels=labels,
        hide_beacon_radius=hide_beacon_radius,
        raw_ids=raw_ids,
        show_edge_ids=show_edge_ids,
    )

    # Controles de capas.
    ax_layers = fig.add_axes([0.76, 0.68, 0.22, 0.22])
    layer_labels = ["spaces", "physical", "boundaries", "beacons", "hazards"]
    layer_checks = [layer_visible.get(key, False) for key in layer_labels]
    layer_widget = CheckButtons(ax_layers, layer_labels, layer_checks)
    ax_layers.set_title("Capas", fontsize=10)

    # Controles de grafos.
    ax_graphs = fig.add_axes([0.76, 0.38, 0.22, 0.24])
    graph_labels = graph_names if graph_names else ["(no graphs)"]
    graph_checks = [False for _ in graph_labels]
    graph_widget = CheckButtons(ax_graphs, graph_labels, graph_checks)
    ax_graphs.set_title("Grafos", fontsize=10)

    # Control de etiquetas.
    ax_labels = fig.add_axes([0.76, 0.20, 0.22, 0.13])
    label_options = ["none", "spaces", "graph", "all"]
    labels_initial = labels if labels in label_options else "spaces"
    labels_widget = RadioButtons(ax_labels, label_options, active=label_options.index(labels_initial))
    ax_labels.set_title("Labels", fontsize=10)

    # Botón de reset.
    ax_reset = fig.add_axes([0.76, 0.10, 0.10, 0.05])
    reset_button = Button(ax_reset, "Reset")

    state = {
        "labels": labels_initial,
        "hide_beacon_radius": hide_beacon_radius,
        "raw_ids": raw_ids,
        "show_edge_ids": show_edge_ids,
    }

    def redraw() -> None:
        draw_scene(
            ax=ax,
            data=data,
            json_name=json_path.name,
            layer_visible=layer_visible,
            graph_visible=graph_visible,
            labels=state["labels"],
            hide_beacon_radius=state["hide_beacon_radius"],
            raw_ids=state["raw_ids"],
            show_edge_ids=state["show_edge_ids"],
        )
        fig.canvas.draw_idle()

    def on_layer_clicked(label: str) -> None:
        layer_visible[label] = not layer_visible[label]
        redraw()

    def on_graph_clicked(label: str) -> None:
        if label == "(no graphs)":
            return
        graph_visible[label] = not graph_visible[label]
        redraw()

    def on_label_changed(label: str) -> None:
        state["labels"] = label
        redraw()

    def on_reset(_event: Any) -> None:
        for key in layer_visible:
            layer_visible[key] = key in ("spaces", "physical")
        for key in graph_visible:
            graph_visible[key] = False
        state["labels"] = "spaces"
        redraw()

    layer_widget.on_clicked(on_layer_clicked)
    graph_widget.on_clicked(on_graph_clicked)
    labels_widget.on_clicked(on_label_changed)
    reset_button.on_clicked(on_reset)

    plt.show()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualizador ligero de MLSM JSON v2")
    parser.add_argument("json_path", type=Path, help="Ruta al archivo MLSM JSON v2")

    parser.add_argument(
        "--graph",
        action="append",
        default=None,
        help=(
            "Nombre del grafo a dibujar. Puede repetirse. "
            "Ejemplo: --graph connectivity_graph --graph door_to_door_graph"
        ),
    )

    parser.add_argument(
        "--layers",
        type=str,
        default="all",
        help=(
            "Capas a dibujar: all, geometry, boundaries, graph, beacons, hazards "
            "o lista separada por comas: spaces,physical,boundaries,beacons,hazards"
        ),
    )

    parser.add_argument(
        "--labels",
        choices=["none", "spaces", "graph", "all"],
        default="spaces",
        help="Qué etiquetas mostrar",
    )

    parser.add_argument(
        "--hide-beacon-radius",
        action="store_true",
        help="Ocultar círculos de influencia de balizas",
    )

    parser.add_argument(
        "--raw-ids",
        action="store_true",
        help="Mostrar IDs técnicos completos en vez de labels/nombres humanizados",
    )

    parser.add_argument(
        "--show-edge-ids",
        action="store_true",
        help="Mostrar IDs de aristas si no tienen label explícito",
    )

    # Compatibilidad con comandos anteriores.
    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Ocultar todas las etiquetas. Equivale a --labels none",
    )

    parser.add_argument("--save", type=Path, default=None, help="Ruta de salida PNG")

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Abrir visualizador interactivo con checkboxes de capas/grafos",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.json_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {args.json_path}")

    labels = "none" if args.no_labels else args.labels

    if args.interactive:
        visualize_interactive(
            json_path=args.json_path,
            labels=labels,
            layers=args.layers,
            hide_beacon_radius=args.hide_beacon_radius,
            raw_ids=args.raw_ids,
            show_edge_ids=args.show_edge_ids,
        )
        return

    graph_names = args.graph or []

    visualize_static(
        json_path=args.json_path,
        graph_names=graph_names,
        save_path=args.save,
        labels=labels,
        layers=args.layers,
        hide_beacon_radius=args.hide_beacon_radius,
        raw_ids=args.raw_ids,
        show_edge_ids=args.show_edge_ids,
    )


if __name__ == "__main__":
    main()

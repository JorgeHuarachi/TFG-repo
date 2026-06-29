"""Canonical runtime topology built from graph_views."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
from shapely.geometry import LineString, Point, shape

from .domain import Diagnostic, IndoorModelBundle


@dataclass(slots=True)
class ConnectionResource:
    id: str
    source_ref: str
    endpoints: tuple[str, str]
    length_m: float
    resource_type: str
    locomotion_types: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


class EvacTopology:
    """Directed multigraph with CellSpace IDs as canonical node IDs."""

    def __init__(
        self,
        indoor: IndoorModelBundle,
        graph: nx.MultiDiGraph,
        resources: dict[str, ConnectionResource],
        graph_view_name: str,
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        self.indoor = indoor
        self.graph = graph
        self.resources = resources
        self.graph_view_name = graph_view_name
        self.diagnostics = diagnostics or []

    @classmethod
    def from_indoor_model(cls, indoor: IndoorModelBundle) -> "EvacTopology":
        graph_view_name, view = _preferred_graph_view(indoor.graph_views)
        graph = nx.MultiDiGraph()
        resources: dict[str, ConnectionResource] = {}
        diagnostics: list[Diagnostic] = []
        skipped_nodes: set[str] = set()

        for node in view.get("nodes", []):
            node_id = node.get("id")
            if not node_id:
                continue
            if node.get("traversable") is False:
                skipped_nodes.add(node_id)
                continue
            cell = indoor.cells_by_id.get(node_id)
            if cell and not cell.is_navigable:
                skipped_nodes.add(node_id)
                continue
            level = node.get("level") or (cell.level if cell else None)
            category = node.get("transferCategory") or (cell.category if cell else node.get("nodeType"))
            point = _point_for_node(indoor, node_id, node)
            graph.add_node(
                node_id,
                level=level,
                category=category,
                function=cell.function if cell else None,
                navigationType=cell.navigation_type if cell else node.get("nodeType"),
                isExit=bool(cell and cell.is_exit),
                position=point,
                raw=node,
            )

        arc_index = 0
        for edge in view.get("edges", []):
            connects = list(edge.get("connects") or [])
            if len(connects) != 2:
                diagnostics.append(Diagnostic("warning", "SKIPPED_BAD_EDGE", "Connectivity edge without two endpoints.", [str(edge.get("id"))]))
                continue
            left, right = connects
            if left not in graph or right not in graph:
                if left in skipped_nodes or right in skipped_nodes:
                    continue
                diagnostics.append(
                    Diagnostic("warning", "SKIPPED_DANGLING_EDGE", "Connectivity edge endpoint is not in canonical topology.", [str(edge.get("id")), left, right])
                )
                continue
            if edge.get("traversable") is False:
                continue
            resource_id = str(edge.get("id") or edge.get("viaBaseEdgeRef") or f"EDGE_{len(resources) + 1:06d}")
            length = _edge_length(indoor, graph, left, right, edge)
            locomotion = list(edge.get("locomotionTypes") or _resource_locomotion(indoor, edge) or ["Walking", "Rolling"])
            resource_type = str(edge.get("connectorType") or (edge.get("attributes") or {}).get("connectorType") or edge.get("relationshipType") or "horizontal")
            resource = ConnectionResource(
                id=resource_id,
                source_ref=str(edge.get("viaBaseEdgeRef") or edge.get("id") or resource_id),
                endpoints=(left, right),
                length_m=length,
                resource_type=resource_type,
                locomotion_types=locomotion,
                metadata={
                    "viaBoundaryRef": edge.get("viaBoundaryRef") or edge.get("boundaryRef"),
                    "viaBaseEdgeRef": edge.get("viaBaseEdgeRef"),
                    "viaSpaceRef": edge.get("viaSpaceRef"),
                    "viaSpaceRefs": list(edge.get("viaSpaceRefs") or []),
                    "viaRoomRef": edge.get("viaRoomRef"),
                    "transferSpaceRef": edge.get("transferSpaceRef"),
                    "connectorId": edge.get("connectorId") or (edge.get("attributes") or {}).get("connectorId"),
                    "relationshipType": edge.get("relationshipType"),
                    "raw": edge,
                },
            )
            resources[resource_id] = resource
            for source, target, direction in ((left, right, "forward"), (right, left, "reverse")):
                arc_index += 1
                arc_id = f"ARC_{arc_index:06d}"
                graph.add_edge(
                    source,
                    target,
                    key=arc_id,
                    arcId=arc_id,
                    resourceRef=resource_id,
                    sourceRef=resource.source_ref,
                    direction=direction,
                    lengthM=length,
                    baseTraversalTimeS=_default_traversal_time(length, resource_type),
                    locomotionTypes=locomotion,
                    connectorType=resource_type,
                    viaBoundaryRef=resource.metadata.get("viaBoundaryRef"),
                    viaSpaceRef=resource.metadata.get("viaSpaceRef"),
                    viaSpaceRefs=list(resource.metadata.get("viaSpaceRefs") or []),
                    viaRoomRef=resource.metadata.get("viaRoomRef"),
                    transferSpaceRef=resource.metadata.get("transferSpaceRef"),
                    raw=edge,
                )
        _infer_missing_node_levels(graph)
        return cls(indoor=indoor, graph=graph, resources=resources, graph_view_name=graph_view_name, diagnostics=diagnostics)

    def node_position(self, node_id: str) -> tuple[float, float] | None:
        position = self.graph.nodes.get(node_id, {}).get("position")
        if position:
            return position
        cell = self.indoor.cells_by_id.get(node_id)
        return cell.representative_point if cell else None

    def node_level(self, node_id: str) -> str | None:
        level = self.graph.nodes.get(node_id, {}).get("level")
        if level:
            return level
        cell = self.indoor.cells_by_id.get(node_id)
        return cell.level if cell else None

    def cell_geometry(self, cell_id: str) -> Any | None:
        cell = self.indoor.cells_by_id.get(cell_id)
        return cell.geometry if cell else None

    def exit_candidates(self) -> list[str]:
        exits = [node_id for node_id, data in self.graph.nodes(data=True) if data.get("isExit")]
        if exits:
            return sorted(exits)
        anchors = [
            cell_id
            for cell_id, cell in self.indoor.cells_by_id.items()
            if cell.is_navigable and (cell.function == "AnchorSpace" or cell.category == "Exit")
        ]
        return sorted(cell_id for cell_id in anchors if cell_id in self.graph)

    def transfer_nodes_for_space(self, cell_id: str) -> list[str]:
        """Return transfer graph nodes reachable inside a GeneralSpace cell."""
        result: set[str] = set()
        for node_id, data in self.graph.nodes(data=True):
            raw = data.get("raw") or {}
            if cell_id in set(raw.get("spaceRefs") or []):
                result.add(node_id)
        for source, target, data in self.graph.edges(data=True):
            spaces = set(data.get("viaSpaceRefs") or [])
            via_space = data.get("viaSpaceRef")
            if via_space:
                spaces.add(via_space)
            if cell_id in spaces:
                result.add(source)
                result.add(target)
        return sorted(result)

    def route_corridor_cells_for_arc(self, arc_id: str) -> list[str]:
        for source, target, key, data in self.graph.edges(keys=True, data=True):
            if key != arc_id and data.get("arcId") != arc_id:
                continue
            cells: list[str] = []
            for value in (source, target, data.get("transferSpaceRef"), data.get("viaSpaceRef")):
                if value and value in self.indoor.cells_by_id and value not in cells:
                    cells.append(value)
            for value in data.get("viaSpaceRefs") or []:
                if value in self.indoor.cells_by_id and value not in cells:
                    cells.append(value)
            return cells
        return []

    def to_summary(self) -> dict[str, Any]:
        levels = sorted({data.get("level") for _, data in self.graph.nodes(data=True) if data.get("level")})
        return {
            "nodes": self.graph.number_of_nodes(),
            "arcs": self.graph.number_of_edges(),
            "resources": len(self.resources),
            "graphView": self.graph_view_name,
            "levels": levels,
            "exitCandidates": self.exit_candidates(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


def _preferred_graph_view(graph_views: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for name in ("multilevel_transfer_to_transfer", "transfer_to_transfer", "multilevel_space_connectivity", "space_connectivity"):
        view = graph_views.get(name)
        if view:
            return name, view
    return "transfer_to_transfer", {}


def _point_for_node(indoor: IndoorModelBundle, node_id: str, node: dict[str, Any]) -> tuple[float, float] | None:
    geom = node.get("geometry")
    if geom:
        try:
            shaped = shape(geom)
            if isinstance(shaped, Point):
                return (float(shaped.x), float(shaped.y))
            point = shaped.representative_point()
            return (float(point.x), float(point.y))
        except Exception:
            pass
    cell = indoor.cells_by_id.get(node_id)
    if cell and cell.representative_point:
        return cell.representative_point
    node_ref = indoor.cell_to_node.get(node_id)
    if node_ref:
        raw_node = indoor.nodes_by_id.get(node_ref) or {}
        coords = (raw_node.get("geometry") or {}).get("coordinates") or []
        if len(coords) >= 2:
            return (float(coords[0]), float(coords[1]))
    return None


def _edge_length(indoor: IndoorModelBundle, graph: nx.MultiDiGraph, left: str, right: str, edge: dict[str, Any]) -> float:
    relationship = edge.get("relationshipType") or (edge.get("attributes") or {}).get("relationshipType")
    if relationship == "vertical_connectivity":
        left_level = graph.nodes[left].get("level")
        right_level = graph.nodes[right].get("level")
        left_z = (indoor.levels_by_id.get(left_level) or {}).get("floorZ")
        right_z = (indoor.levels_by_id.get(right_level) or {}).get("floorZ")
        if left_z is not None and right_z is not None and float(left_z) != float(right_z):
            return max(abs(float(left_z) - float(right_z)), 0.01)
    if edge.get("distanceM") is not None:
        return max(float(edge.get("distanceM") or 0.0), 0.01)
    geom = edge.get("geometry")
    if geom:
        try:
            shaped = shape(geom)
            if isinstance(shaped, LineString) and shaped.length > 0:
                return float(shaped.length)
        except Exception:
            pass
    base_edge_ref = edge.get("viaBaseEdgeRef") or edge.get("id")
    base_edge = indoor.edges_by_id.get(str(base_edge_ref)) if base_edge_ref else None
    if base_edge and base_edge.get("geometry"):
        try:
            shaped = shape(base_edge["geometry"])
            if shaped.length > 0:
                return float(shaped.length)
        except Exception:
            pass
    left_pos = graph.nodes[left].get("position")
    right_pos = graph.nodes[right].get("position")
    if left_pos and right_pos:
        return max(math.dist(left_pos, right_pos), 0.01)
    return max(float(edge.get("weight") or 1.0), 0.01)


def _default_traversal_time(length_m: float, connector_type: str) -> float:
    factor = {
        "Stair": 0.55,
        "Ramp": 0.7,
        "Elevator": 0.5,
    }.get(connector_type, 1.0)
    return max(length_m / max(1.2 * factor, 0.01), 0.01)


def _resource_locomotion(indoor: IndoorModelBundle, edge: dict[str, Any]) -> list[str]:
    transfer_ref = edge.get("transferSpaceRef")
    if transfer_ref and transfer_ref in indoor.cells_by_id:
        return list(indoor.cells_by_id[transfer_ref].locomotion_types)
    return []


def _infer_missing_node_levels(graph: nx.MultiDiGraph) -> None:
    for node_id, data in list(graph.nodes(data=True)):
        if data.get("level"):
            continue
        levels = set()
        for neighbor in list(graph.predecessors(node_id)) + list(graph.successors(node_id)):
            level = graph.nodes[neighbor].get("level")
            if level:
                levels.add(level)
        if len(levels) == 1:
            data["level"] = next(iter(levels))

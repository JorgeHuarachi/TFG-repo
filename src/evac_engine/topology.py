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
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        self.indoor = indoor
        self.graph = graph
        self.resources = resources
        self.diagnostics = diagnostics or []

    @classmethod
    def from_indoor_model(cls, indoor: IndoorModelBundle) -> "EvacTopology":
        view = indoor.graph_views.get("multilevel_space_connectivity") or indoor.graph_views.get("space_connectivity") or {}
        graph = nx.MultiDiGraph()
        resources: dict[str, ConnectionResource] = {}
        diagnostics: list[Diagnostic] = []

        for node in view.get("nodes", []):
            node_id = node.get("id")
            if not node_id:
                continue
            cell = indoor.cells_by_id.get(node_id)
            if cell and not cell.is_navigable:
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
                    transferSpaceRef=resource.metadata.get("transferSpaceRef"),
                    raw=edge,
                )
        _infer_missing_node_levels(graph)
        return cls(indoor=indoor, graph=graph, resources=resources, diagnostics=diagnostics)

    def node_position(self, node_id: str) -> tuple[float, float] | None:
        return self.graph.nodes.get(node_id, {}).get("position")

    def node_level(self, node_id: str) -> str | None:
        return self.graph.nodes.get(node_id, {}).get("level")

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

    def to_summary(self) -> dict[str, Any]:
        levels = sorted({data.get("level") for _, data in self.graph.nodes(data=True) if data.get("level")})
        return {
            "nodes": self.graph.number_of_nodes(),
            "arcs": self.graph.number_of_edges(),
            "resources": len(self.resources),
            "levels": levels,
            "exitCandidates": self.exit_candidates(),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


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

"""Derived graph views for Indoor Data Model documents."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union


def derive_graph_views(model: dict[str, Any]) -> dict[str, Any]:
    index = _index_model(model)
    space_adjacency = _space_adjacency(index)
    space_connectivity = _space_connectivity(index)
    room_adjacency = _room_adjacency(index)
    room_to_room = _room_to_room_accessibility(room_adjacency)
    transfer_to_transfer = _transfer_to_transfer(
        index,
        include_virtual=True,
        include_non_traversable=True,
        allowed_categories=None,
        id_prefix="T2T",
        group_by_logical_room=False,
    )
    door_to_door = _transfer_to_transfer(
        index,
        include_virtual=False,
        include_non_traversable=False,
        allowed_categories={"Door", "Exit"},
        id_prefix="D2D",
        group_by_logical_room=False,
    )
    return {
        "base_dual": _base_dual(index),
        "space_adjacency": space_adjacency,
        "general_space_adjacency": space_adjacency,
        "space_connectivity": space_connectivity,
        "space_transfer_connectivity": space_connectivity,
        "room_transfer_connectivity": space_connectivity,
        "room_adjacency": room_adjacency,
        "room_to_room_accessibility": room_to_room,
        "room_to_room": room_to_room,
        "transfer_to_transfer": transfer_to_transfer,
        "door_to_door": door_to_door,
        "vertical_connectivity": _vertical_connectivity(model, index),
    }


def _index_model(model: dict[str, Any]) -> dict[str, Any]:
    cells = {}
    nodes = {}
    edges = {}
    boundaries = {}
    node_by_cell = {}
    cell_by_node = {}
    boundaries_by_cell = defaultdict(list)
    edges_by_cell = defaultdict(list)
    layer_by_id = {}

    for layer in model.get("layers", []):
        layer_id = layer.get("id")
        layer_by_id[layer_id] = layer
        primal = layer.get("primalSpace") or {}
        dual = layer.get("dualSpace") or {}
        for cell in primal.get("cellSpaceMember", []):
            cells[cell["id"]] = {"feature": cell, "layer": layer, "geometry": _polygon(cell)}
        for boundary in primal.get("cellBoundaryMember", []):
            boundaries[boundary["id"]] = {"feature": boundary, "layer": layer, "geometry": _line(boundary)}
            for cell_id in boundary.get("cellRefs", []):
                boundaries_by_cell[cell_id].append(boundary["id"])
        for node in dual.get("nodeMember", []):
            nodes[node["id"]] = {"feature": node, "layer": layer, "geometry": _point(node)}
            cell_id = _ref_tail(node.get("duality"))
            node_by_cell[cell_id] = node["id"]
            cell_by_node[node["id"]] = cell_id
        for edge in dual.get("edgeMember", []):
            edges[edge["id"]] = {"feature": edge, "layer": layer, "geometry": _line_feature(edge)}
            for node_ref in edge.get("connects", []):
                cell_id = cell_by_node.get(_ref_tail(node_ref))
                if cell_id:
                    edges_by_cell[cell_id].append(edge["id"])

    return {
        "cells": cells,
        "nodes": nodes,
        "edges": edges,
        "boundaries": boundaries,
        "nodeByCell": node_by_cell,
        "cellByNode": cell_by_node,
        "boundariesByCell": boundaries_by_cell,
        "edgesByCell": edges_by_cell,
        "layerById": layer_by_id,
    }


def _base_dual(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [record["feature"] for record in index["nodes"].values()],
        "edges": [record["feature"] for record in index["edges"].values()],
    }


def _space_adjacency(index: dict[str, Any]) -> dict[str, Any]:
    """GeneralSpace adjacency after virtual-boundary decomposition.

    This includes direct GeneralSpace contacts and indirect contacts through a
    TransferSpace such as a door, exit, window, ramp, or stair endpoint.
    """
    nodes = [_room_node(cell_id, record) for cell_id, record in index["cells"].items() if _nav(record) == "GeneralSpace"]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for boundary_id, record in index["boundaries"].items():
        boundary = record["feature"]
        cell_refs = [cell_id for cell_id in boundary.get("cellRefs", []) if _nav(index["cells"].get(cell_id)) == "GeneralSpace"]
        if len(cell_refs) == 2:
            _merge_space_edge(
                grouped,
                cell_refs[0],
                cell_refs[1],
                via_boundary=boundary_id,
                via_virtual=_virtual_transfer_node_id(boundary_id) if boundary.get("isVirtual") else None,
                traversable=bool(boundary.get("traversable")),
                contact_type="direct_virtual" if boundary.get("isVirtual") else "direct",
            )

    transfer_spaces: dict[str, set[str]] = defaultdict(set)
    transfer_boundaries: dict[str, list[str]] = defaultdict(list)
    for boundary_id, record in index["boundaries"].items():
        cell_refs = list(record["feature"].get("cellRefs") or [])
        general_refs = [cell_id for cell_id in cell_refs if _nav(index["cells"].get(cell_id)) == "GeneralSpace"]
        transfer_refs = [cell_id for cell_id in cell_refs if _nav(index["cells"].get(cell_id)) == "TransferSpace"]
        for transfer_id in transfer_refs:
            for general_id in general_refs:
                transfer_spaces[transfer_id].add(general_id)
                _unique_append(transfer_boundaries[transfer_id], boundary_id)

    for transfer_id, space_ids in transfer_spaces.items():
        transfer = index["cells"].get(transfer_id)
        for space_a, space_b in _pairs(sorted(space_ids)):
            _merge_space_edge(
                grouped,
                space_a,
                space_b,
                via_boundaries=transfer_boundaries[transfer_id],
                via_transfer=transfer_id,
                traversable=_transfer_is_traversable(transfer),
                contact_type="transfer",
            )
    edges = []
    for index_number, edge in enumerate(grouped.values(), start=1):
        edge["id"] = f"SAG_{index_number:03d}_{edge['connects'][0]}_{edge['connects'][1]}"
        edges.append(edge)
    return {"nodes": nodes, "edges": edges}


def _room_adjacency(index: dict[str, Any]) -> dict[str, Any]:
    """Logical room adjacency before virtual-boundary splits.

    Nodes are connected components of GeneralSpaces merged across virtual
    boundaries. Edges are grouped once per logical room pair and collect the
    walls, transfer spaces, or direct boundaries that explain the adjacency.
    """
    component_by_space, components = _logical_room_components(index)
    nodes = [_component_node(component) for component in components.values()]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    transfer_components: dict[str, set[str]] = defaultdict(set)
    transfer_boundaries: dict[str, list[str]] = defaultdict(list)
    connector_components: dict[str, set[str]] = defaultdict(set)
    connector_transfers: dict[str, list[str]] = defaultdict(list)
    connector_boundaries: dict[str, list[str]] = defaultdict(list)
    wall_components: dict[str, set[str]] = defaultdict(set)
    wall_boundaries: dict[str, list[str]] = defaultdict(list)

    for boundary_id, record in index["boundaries"].items():
        boundary = record["feature"]
        cell_refs = list(boundary.get("cellRefs") or [])
        general_refs = [cell_id for cell_id in cell_refs if cell_id in component_by_space]
        transfer_refs = [cell_id for cell_id in cell_refs if _nav(index["cells"].get(cell_id)) == "TransferSpace"]
        wall_refs = [cell_id for cell_id in cell_refs if _is_wall_cell(index["cells"].get(cell_id))]

        if len(general_refs) == 2:
            comp_a = component_by_space[general_refs[0]]
            comp_b = component_by_space[general_refs[1]]
            if comp_a != comp_b:
                _merge_room_edge(
                    grouped,
                    comp_a,
                    comp_b,
                    components,
                    via_boundary=boundary_id,
                    contact_type="direct",
                    traversable=bool(boundary.get("traversable")),
                )

        for transfer_id in transfer_refs:
            for general_id in general_refs:
                transfer_components[transfer_id].add(component_by_space[general_id])
                _unique_append(transfer_boundaries[transfer_id], boundary_id)
                connector_id = _connector_id(index["cells"].get(transfer_id))
                if connector_id:
                    connector_components[connector_id].add(component_by_space[general_id])
                    _unique_append(connector_transfers[connector_id], transfer_id)
                    _unique_append(connector_boundaries[connector_id], boundary_id)

        for wall_id in wall_refs:
            for general_id in general_refs:
                wall_components[wall_id].add(component_by_space[general_id])
                _unique_append(wall_boundaries[wall_id], boundary_id)

    for transfer_id, component_ids in transfer_components.items():
        transfer = index["cells"].get(transfer_id)
        for comp_a, comp_b in _pairs(sorted(component_ids)):
            _merge_room_edge(
                grouped,
                comp_a,
                comp_b,
                components,
                via_boundaries=transfer_boundaries[transfer_id],
                via_transfer=transfer_id,
                contact_type="transfer",
                traversable=_transfer_is_traversable(transfer),
            )

    for wall_id, component_ids in wall_components.items():
        for comp_a, comp_b in _pairs(sorted(component_ids)):
            _merge_room_edge(
                grouped,
                comp_a,
                comp_b,
                components,
                via_boundaries=wall_boundaries[wall_id],
                via_wall=wall_id,
                contact_type="wall",
                traversable=False,
            )

    for connector_id, component_ids in connector_components.items():
        for comp_a, comp_b in _pairs(sorted(component_ids)):
            for transfer_id in connector_transfers[connector_id]:
                _merge_room_edge(
                    grouped,
                    comp_a,
                    comp_b,
                    components,
                    via_boundaries=connector_boundaries[connector_id],
                    via_transfer=transfer_id,
                    contact_type="connector",
                    traversable=True,
                )

    edges = []
    for index_number, edge in enumerate(grouped.values(), start=1):
        edge["id"] = f"RADJ_{index_number:03d}_{edge['connects'][0]}_{edge['connects'][1]}"
        edges.append(edge)
    return {"nodes": nodes, "edges": edges}


def _room_to_room_accessibility(room_adjacency: dict[str, Any]) -> dict[str, Any]:
    edges = []
    for edge in room_adjacency.get("edges", []):
        if not edge.get("viaTraversableTransferSpaceRefs"):
            continue
        filtered = dict(edge)
        filtered["id"] = str(filtered.get("id", "")).replace("RADJ_", "R2R_", 1) or f"R2R_{len(edges)+1:03d}"
        filtered["attributes"] = dict(filtered.get("attributes") or {})
        filtered["attributes"]["graphSemantics"] = "room_to_room_accessibility"
        edges.append(filtered)
    return {"nodes": list(room_adjacency.get("nodes", [])), "edges": edges}


def _space_connectivity(index: dict[str, Any]) -> dict[str, Any]:
    """GeneralSpace + TransferSpace connectivity graph.

    GeneralSpaces are the already split spaces from the primal model. Virtual
    boundaries are represented as explicit intermediate VirtualTransferNode
    nodes, so this graph keeps the distinction between adjacency and a
    traversable logical connection.
    """
    nodes = []
    edges = []
    for cell_id, record in index["cells"].items():
        nav = _nav(record)
        if nav in {"GeneralSpace", "TransferSpace"}:
            nodes.append({"id": cell_id, "nodeType": nav, "level": record["feature"].get("level")})

    for boundary_id, record in index["boundaries"].items():
        boundary = record["feature"]
        if boundary.get("isVirtual") and boundary.get("traversable"):
            transfer_id = _virtual_transfer_node_id(boundary_id)
            nodes.append(
                {
                    "id": transfer_id,
                    "nodeType": "VirtualTransferNode",
                    "geometry": _midpoint_geojson(record["geometry"]),
                    "viaBoundaryRef": boundary_id,
                }
            )
            for cell_id in boundary.get("cellRefs", []):
                if _nav(index["cells"].get(cell_id)) == "GeneralSpace":
                    edges.append({"connects": [cell_id, transfer_id], "traversable": True, "viaBoundaryRef": boundary_id})

    for edge_id, record in index["edges"].items():
        edge = record["feature"]
        if not edge.get("traversable") or not edge.get("transferSpaceRef"):
            continue
        cells = [_cell_for_node(index, node_ref) for node_ref in edge.get("connects", [])]
        rooms = [cell_id for cell_id in cells if _nav(index["cells"].get(cell_id)) == "GeneralSpace"]
        for room_id in rooms:
            edges.append(
                {
                    "id": f"RTC_{edge_id}_{room_id}",
                    "connects": [room_id, edge["transferSpaceRef"]],
                    "traversable": True,
                    "viaBaseEdgeRef": edge_id,
                    "viaBoundaryRef": edge.get("boundaryRef"),
                }
            )
    return {"nodes": nodes, "edges": edges}


def _transfer_to_transfer(
    index: dict[str, Any],
    include_virtual: bool,
    include_non_traversable: bool,
    allowed_categories: set[str] | None,
    id_prefix: str,
    group_by_logical_room: bool,
) -> dict[str, Any]:
    component_by_space, components = (
        _logical_room_components(index) if group_by_logical_room else _split_general_space_components(index)
    )
    transfer_nodes, memberships = _transfer_memberships(
        index,
        component_by_space,
        include_virtual=include_virtual,
        include_non_traversable=include_non_traversable,
        allowed_categories=allowed_categories,
    )

    edges = []
    seen = set()
    for component_id, transfer_ids in sorted(memberships.items()):
        room_poly = components.get(component_id, {}).get("geometry")
        room_spaces = sorted(components.get(component_id, {}).get("spaceRefs", []))
        for a, b in _pairs(sorted(transfer_ids)):
            key = (component_id, a, b)
            if key in seen:
                continue
            seen.add(key)
            distance, warning = _distance_inside_room(
                transfer_nodes[a].get("_geometry"),
                transfer_nodes[b].get("_geometry"),
                room_poly,
            )
            edge = {
                "id": f"{id_prefix}_{component_id}_{a}_{b}",
                "connects": [a, b],
                "viaRoomRef": component_id if group_by_logical_room else None,
                "viaSpaceRef": room_spaces[0] if len(room_spaces) == 1 else None,
                "viaSpaceRefs": room_spaces,
                "distanceM": round(distance, 6),
                "locomotionTypes": _shared_locomotion(transfer_nodes[a], transfer_nodes[b]),
            }
            if warning:
                edge["warning"] = warning
            edges.append(edge)

    public_nodes = []
    used_nodes = {node_id for edge in edges for node_id in edge.get("connects", [])}
    for node_id in sorted(used_nodes):
        node = dict(transfer_nodes[node_id])
        node.pop("_geometry", None)
        public_nodes.append(node)
    return {"nodes": public_nodes, "edges": edges}


def _split_general_space_components(index: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    by_space = {}
    components = {}
    for cell_id, record in index["cells"].items():
        if _nav(record) != "GeneralSpace":
            continue
        component_id = f"SPACE_{cell_id}"
        by_space[cell_id] = component_id
        components[component_id] = {
            "id": component_id,
            "level": record["feature"].get("level"),
            "spaceRefs": [cell_id],
            "geometry": record.get("geometry"),
        }
    return by_space, components


def _logical_room_components(index: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    general_ids = sorted(cell_id for cell_id, record in index["cells"].items() if _nav(record) == "GeneralSpace")
    parent = {cell_id: cell_id for cell_id in general_ids}

    def find(cell_id: str) -> str:
        while parent[cell_id] != cell_id:
            parent[cell_id] = parent[parent[cell_id]]
            cell_id = parent[cell_id]
        return cell_id

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        parent[max(root_left, root_right)] = min(root_left, root_right)

    for record in index["boundaries"].values():
        boundary = record["feature"]
        if not boundary.get("isVirtual"):
            continue
        cell_refs = [cell_id for cell_id in boundary.get("cellRefs", []) if cell_id in parent]
        if len(cell_refs) == 2:
            union(cell_refs[0], cell_refs[1])

    by_space = {cell_id: f"ROOM_{find(cell_id)}" for cell_id in general_ids}
    grouped: dict[str, dict[str, Any]] = {}
    for cell_id in general_ids:
        component_id = by_space[cell_id]
        component = grouped.setdefault(
            component_id,
            {
                "id": component_id,
                "level": index["cells"][cell_id]["feature"].get("level"),
                "spaceRefs": [],
                "geometryParts": [],
            },
        )
        component["spaceRefs"].append(cell_id)
        geometry = index["cells"][cell_id].get("geometry")
        if geometry is not None and not geometry.is_empty:
            component["geometryParts"].append(geometry)

    for component in grouped.values():
        parts = component.pop("geometryParts")
        component["geometry"] = unary_union(parts) if parts else None
    return by_space, grouped


def _component_node(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": component["id"],
        "nodeType": "LogicalRoom",
        "level": component.get("level"),
        "spaceRefs": list(component.get("spaceRefs", [])),
        "geometry": _representative_point_geojson(component.get("geometry")),
    }


def _merge_space_edge(
    grouped: dict[tuple[str, str], dict[str, Any]],
    space_a: str,
    space_b: str,
    via_boundary: str | None = None,
    via_boundaries: list[str] | None = None,
    via_transfer: str | None = None,
    via_virtual: str | None = None,
    contact_type: str = "unknown",
    traversable: bool = False,
) -> None:
    key = tuple(sorted([space_a, space_b]))
    edge = grouped.setdefault(
        key,
        {
            "connects": list(key),
            "traversable": False,
            "viaBoundaryRefs": [],
            "viaTransferSpaceRefs": [],
            "viaTransferNodeRefs": [],
            "attributes": {
                "contactTypes": [],
                "graphSemantics": "general_space_adjacency",
            },
        },
    )
    if via_boundary:
        _unique_append(edge["viaBoundaryRefs"], via_boundary)
    for boundary_id in via_boundaries or []:
        _unique_append(edge["viaBoundaryRefs"], boundary_id)
    if via_transfer:
        _unique_append(edge["viaTransferSpaceRefs"], via_transfer)
    if via_virtual:
        _unique_append(edge["viaTransferNodeRefs"], via_virtual)
    _unique_append(edge["attributes"]["contactTypes"], contact_type)
    edge["traversable"] = bool(edge["traversable"] or traversable)


def _merge_room_edge(
    grouped: dict[tuple[str, str], dict[str, Any]],
    comp_a: str,
    comp_b: str,
    components: dict[str, dict[str, Any]],
    via_boundary: str | None = None,
    via_boundaries: list[str] | None = None,
    via_transfer: str | None = None,
    via_wall: str | None = None,
    contact_type: str = "unknown",
    traversable: bool = False,
) -> None:
    key = tuple(sorted([comp_a, comp_b]))
    edge = grouped.setdefault(
        key,
        {
            "connects": list(key),
            "traversable": False,
            "viaBoundaryRefs": [],
            "viaTransferSpaceRefs": [],
            "viaTraversableTransferSpaceRefs": [],
            "viaWallRefs": [],
            "viaSpaceRefs": sorted(
                set(components[key[0]].get("spaceRefs", [])) | set(components[key[1]].get("spaceRefs", []))
            ),
            "attributes": {
                "contactTypes": [],
                "graphSemantics": "logical_room_adjacency",
            },
        },
    )
    if via_boundary:
        _unique_append(edge["viaBoundaryRefs"], via_boundary)
    for boundary_id in via_boundaries or []:
        _unique_append(edge["viaBoundaryRefs"], boundary_id)
    if via_transfer:
        _unique_append(edge["viaTransferSpaceRefs"], via_transfer)
        if traversable:
            _unique_append(edge["viaTraversableTransferSpaceRefs"], via_transfer)
    if via_wall:
        _unique_append(edge["viaWallRefs"], via_wall)
    _unique_append(edge["attributes"]["contactTypes"], contact_type)
    edge["traversable"] = bool(edge["traversable"] or (via_transfer and traversable))


def _transfer_memberships(
    index: dict[str, Any],
    component_by_space: dict[str, str],
    include_virtual: bool,
    include_non_traversable: bool,
    allowed_categories: set[str] | None,
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    nodes: dict[str, dict[str, Any]] = {}
    memberships: dict[str, set[str]] = defaultdict(set)

    for cell_id, record in index["cells"].items():
        if _nav(record) != "TransferSpace":
            continue
        category = str(record["feature"].get("category") or "")
        if allowed_categories is not None and category not in allowed_categories:
            continue
        traversable = _transfer_is_traversable(record)
        if not include_non_traversable and not traversable:
            continue
        geom = record.get("geometry")
        nodes[cell_id] = {
            "id": cell_id,
            "nodeType": "TransferSpace",
            "transferCategory": category,
            "traversable": traversable,
            "level": record["feature"].get("level"),
            "geometry": _representative_point_geojson(geom),
            "cellSpaceRef": cell_id,
            "locomotionTypes": record["feature"].get("locomotionTypes") or ["Walking", "Rolling"],
            "_geometry": geom,
        }

    for boundary_id, record in index["boundaries"].items():
        boundary = record["feature"]
        cell_refs = list(boundary.get("cellRefs") or [])
        general_refs = [cell_id for cell_id in cell_refs if cell_id in component_by_space]
        transfer_refs = [cell_id for cell_id in cell_refs if cell_id in nodes]
        for transfer_id in transfer_refs:
            for general_id in general_refs:
                memberships[component_by_space[general_id]].add(transfer_id)

        if include_virtual and boundary.get("isVirtual"):
            virtual_id = _virtual_transfer_node_id(boundary_id)
            if virtual_id not in nodes:
                nodes[virtual_id] = {
                    "id": virtual_id,
                    "nodeType": "VirtualTransferNode",
                    "transferCategory": "VirtualBoundary",
                    "traversable": bool(boundary.get("traversable", True)),
                    "geometry": _midpoint_geojson(record["geometry"]),
                    "viaBoundaryRef": boundary_id,
                    "_geometry": record["geometry"],
                }
            for general_id in general_refs:
                memberships[component_by_space[general_id]].add(virtual_id)

    return nodes, memberships


def _vertical_connectivity(model: dict[str, Any], index: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    edges = []
    for cell_id, record in index["cells"].items():
        attrs = record["feature"].get("attributes", {})
        if attrs.get("connectorId") and record["feature"].get("function") == "VerticalConnectorEndpoint":
            nodes.append({"id": cell_id, "nodeType": "ConnectorEndpoint", "connectorId": attrs.get("connectorId")})
    for edge_id, record in index["edges"].items():
        edge = record["feature"]
        if edge.get("relationshipType") == "vertical_connectivity":
            edges.append({"id": edge_id, "connects": edge.get("connects", []), "attributes": edge.get("attributes", {})})
    for connection in model.get("layerConnections", []):
        attrs = connection.get("attributes", {})
        if attrs.get("relationshipType") == "vertical_connectivity":
            edges.append(
                {
                    "id": connection.get("id"),
                    "connects": connection.get("connectedNodes", []),
                    "connectedCells": connection.get("connectedCells", []),
                    "attributes": attrs,
                }
            )
    return {"nodes": nodes, "edges": edges}


def _polygon(cell: dict[str, Any]) -> Polygon | None:
    geom = ((cell.get("cellSpaceGeom") or {}).get("geometry2D") or {})
    coords = geom.get("coordinates") or []
    try:
        return Polygon(coords[0], coords[1:]) if coords else None
    except Exception:
        return None


def _line(boundary: dict[str, Any]) -> LineString | None:
    geom = ((boundary.get("cellBoundaryGeom") or {}).get("geometry2D") or {})
    return _line_from_geojson(geom)


def _line_feature(feature: dict[str, Any]) -> LineString | None:
    return _line_from_geojson(feature.get("geometry") or {})


def _line_from_geojson(geom: dict[str, Any]) -> LineString | None:
    try:
        return LineString(geom.get("coordinates") or [])
    except Exception:
        return None


def _point(node: dict[str, Any]) -> Point | None:
    coords = (node.get("geometry") or {}).get("coordinates") or []
    try:
        return Point(coords)
    except Exception:
        return None


def _room_node(cell_id: str, record: dict[str, Any]) -> dict[str, Any]:
    return {"id": cell_id, "level": record["feature"].get("level"), "cellSpaceName": record["feature"].get("cellSpaceName")}


def _nav(record: dict[str, Any] | None) -> str | None:
    return (record or {}).get("feature", {}).get("navigationType")


def _cell_for_node(index: dict[str, Any], node_ref: str) -> str | None:
    return index["cellByNode"].get(_ref_tail(node_ref))


def _ref_tail(value: Any) -> str:
    return str(value).split(":")[-1]


def _pairs(values):
    for i, left in enumerate(values):
        for right in values[i + 1 :]:
            yield left, right


def _unique_append(values: list[Any], value: Any) -> None:
    if value and value not in values:
        values.append(value)


def _virtual_transfer_node_id(boundary_id: str) -> str:
    return f"VTN_{boundary_id}"


def _midpoint_geojson(line: LineString | None) -> dict[str, Any] | None:
    if line is None or line.is_empty:
        return None
    point = line.interpolate(0.5, normalized=True)
    return {"type": "Point", "coordinates": [round(point.x, 6), round(point.y, 6)]}


def _representative_point_geojson(geom: Any) -> dict[str, Any] | None:
    point = _representative_point(geom)
    if point is None:
        return None
    return {"type": "Point", "coordinates": [round(point.x, 6), round(point.y, 6)]}


def _representative_point(geom: Any) -> Point | None:
    if geom is None or getattr(geom, "is_empty", True):
        return None
    try:
        if isinstance(geom, Point):
            return geom
        if isinstance(geom, LineString):
            return geom.interpolate(0.5, normalized=True)
        return geom.representative_point()
    except Exception:
        return None


def _distance_inside_room(geom_a: Any, geom_b: Any, room_poly: Polygon | None) -> tuple[float, str | None]:
    pa = _representative_point(geom_a)
    pb = _representative_point(geom_b)
    if pa is None or pb is None:
        return 0.0, "missing_transfer_geometry"
    direct = LineString([pa, pb])
    if room_poly is not None and room_poly.buffer(1e-6).covers(direct):
        return pa.distance(pb), None
    if room_poly is None:
        return pa.distance(pb), "missing_room_geometry_euclidean_fallback"
    candidates = [pa, pb]
    try:
        candidates.extend(Point(coord) for coord in room_poly.exterior.coords[:-1])
    except Exception:
        return pa.distance(pb), "visibility_graph_failed_euclidean_fallback"
    distance = _visibility_shortest_path(candidates, room_poly, 0, 1)
    if math.isfinite(distance):
        return distance, None
    return pa.distance(pb), "visibility_graph_failed_euclidean_fallback"


def _visibility_shortest_path(points: list[Point], polygon: Polygon, start_index: int, end_index: int) -> float:
    graph = defaultdict(list)
    for i, point_a in enumerate(points):
        for j in range(i + 1, len(points)):
            point_b = points[j]
            segment = LineString([point_a, point_b])
            if polygon.buffer(1e-6).covers(segment):
                distance = point_a.distance(point_b)
                graph[i].append((j, distance))
                graph[j].append((i, distance))
    distances = {start_index: 0.0}
    visited = set()
    while True:
        current = None
        current_distance = math.inf
        for node, distance in distances.items():
            if node not in visited and distance < current_distance:
                current = node
                current_distance = distance
        if current is None:
            return math.inf
        if current == end_index:
            return current_distance
        visited.add(current)
        for neighbor, weight in graph[current]:
            distances[neighbor] = min(distances.get(neighbor, math.inf), current_distance + weight)


def _shared_locomotion(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    left = set(a.get("locomotionTypes") or ["Walking", "Rolling"])
    right = set(b.get("locomotionTypes") or ["Walking", "Rolling"])
    shared = sorted(left & right)
    return shared or sorted(left | right) or ["Unspecified"]


def _transfer_is_traversable(record: dict[str, Any] | None) -> bool:
    if not record:
        return False
    feature = record.get("feature", {})
    attrs = feature.get("attributes") or {}
    if attrs.get("defaultTraversable") is False:
        return False
    return str(feature.get("category") or "") in {"Door", "Exit", "Stair", "Ramp", "Elevator"}


def _connector_id(record: dict[str, Any] | None) -> str | None:
    if not record:
        return None
    feature = record.get("feature", {})
    attrs = feature.get("attributes") or {}
    connector_id = attrs.get("connectorId")
    if connector_id and str(feature.get("category") or "") in {"Stair", "Ramp", "Elevator"}:
        return str(connector_id)
    return None


def _is_wall_cell(record: dict[str, Any] | None) -> bool:
    if _nav(record) != "NonNavigableSpace":
        return False
    feature = record.get("feature", {})
    return feature.get("function") == "Wall" and feature.get("category") in {"WallSegment", "WallJunction"}

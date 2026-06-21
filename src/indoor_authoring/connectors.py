"""Vertical connector authoring helpers."""

from __future__ import annotations

from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .model import BuildingAuthoringState, ConnectorEndpoint, VerticalConnector


SIDE_VECTORS = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}
CONNECTOR_TYPES = {"Stair", "Ramp", "Elevator"}
SCOPES = {"same_level", "inter_level"}
COVERAGE_THICKNESS_M = 0.12


def create_tile_chain_connector(
    state: BuildingAuthoringState,
    connector_type: str,
    tile_origins: list[tuple[float, float]],
    entry_side: str,
    exit_side: str,
    scope: str = "same_level",
    target_level_id: str | None = None,
    tile_size_m: float = 1.0,
    attributes: dict | None = None,
) -> VerticalConnector:
    if connector_type not in CONNECTOR_TYPES:
        raise ValueError(f"Unsupported connector type: {connector_type}")
    if scope not in SCOPES:
        raise ValueError(f"Unsupported connector scope: {scope}")
    if connector_type in {"Stair", "Ramp"}:
        _validate_tile_chain(tile_origins, tile_size_m)
    if not tile_origins:
        raise ValueError("At least one tile is required.")

    active = state.active_level
    target_level_id = target_level_id or _default_target_level(state, active.id)
    connector_index = state.next_counter("connector")
    connector_id = f"VC_{connector_index:03d}"
    footprint = _union_tile_footprint(tile_origins, tile_size_m)
    open_sides = _unique_sides([entry_side, exit_side])
    endpoint_attrs = {
        "tileSizeM": tile_size_m,
        "tileOrigins": [(float(x), float(y)) for x, y in tile_origins],
        "sideCoverages": _coverage_rings(footprint, open_sides),
    }
    endpoint_attrs.update(attributes or {})

    endpoints = []
    if scope == "same_level" and len(tile_origins) > 1:
        first_tile = _union_tile_footprint([tile_origins[0]], tile_size_m)
        last_tile = _union_tile_footprint([tile_origins[-1]], tile_size_m)
        endpoints.append(
            ConnectorEndpoint(
                id=f"EP_{connector_id}_{active.id}_ENTRY",
                level_id=active.id,
                footprint=_polygon_ring(first_tile),
                entry_side=entry_side,
                exit_side=None,
                open_sides=[entry_side],
                attributes=dict(endpoint_attrs),
            )
        )
        endpoint_exit_attrs = dict(endpoint_attrs)
        endpoint_exit_attrs["sideCoverages"] = []
        endpoints.append(
            ConnectorEndpoint(
                id=f"EP_{connector_id}_{active.id}_EXIT",
                level_id=active.id,
                footprint=_polygon_ring(last_tile),
                entry_side=None,
                exit_side=exit_side,
                open_sides=[exit_side],
                attributes=endpoint_exit_attrs,
            )
        )
    else:
        source_endpoint_attrs = dict(endpoint_attrs)
        if scope == "inter_level":
            source_endpoint_attrs["sideCoverages"] = _coverage_rings(footprint, [entry_side])
        endpoints.append(
            ConnectorEndpoint(
                id=f"EP_{connector_id}_{active.id}",
                level_id=active.id,
                footprint=_polygon_ring(footprint),
                entry_side=entry_side,
                exit_side=exit_side if scope == "same_level" else None,
                open_sides=open_sides if scope == "same_level" else [entry_side],
                attributes=source_endpoint_attrs,
            )
        )

    target_level = active.id
    if scope == "inter_level":
        target = state.level_by_id(target_level_id)
        target_level = target.id
        target_endpoint_attrs = dict(endpoint_attrs)
        target_endpoint_attrs["sideCoverages"] = _coverage_rings(footprint, [exit_side])
        endpoints.append(
            ConnectorEndpoint(
                id=f"EP_{connector_id}_{target.id}",
                level_id=target.id,
                footprint=_polygon_ring(footprint),
                entry_side=None,
                exit_side=exit_side,
                open_sides=[exit_side],
                attributes=target_endpoint_attrs,
            )
        )

    locomotion = _locomotion_for(connector_type)
    connector = VerticalConnector(
        id=connector_id,
        connector_type=connector_type,
        scope=scope,
        endpoints=endpoints,
        source_level=active.id,
        target_level=target_level,
        from_elevation_m=active.elevation_m,
        to_elevation_m=state.level_by_id(target_level).elevation_m,
        locomotion_types=locomotion,
        attributes=_connector_attributes(connector_type, tile_size_m, tile_origins, attributes or {}),
    )
    state.vertical_connectors.append(connector)
    for endpoint in endpoints:
        state.level_by_id(endpoint.level_id).geometry_dirty = True
    return connector


def create_elevator_connector(
    state: BuildingAuthoringState,
    footprint: list[tuple[float, float]],
    served_level_ids: list[str],
    entry_side: str = "south",
    exit_side: str | None = None,
    attributes: dict | None = None,
) -> VerticalConnector:
    if not served_level_ids:
        served_level_ids = [state.active_level_id]
    exit_side = exit_side or entry_side
    polygon = Polygon(footprint)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty:
        raise ValueError("Elevator footprint is invalid.")

    connector_index = state.next_counter("connector")
    connector_id = f"VC_{connector_index:03d}"
    endpoints = []
    for level_id in served_level_ids:
        endpoint_attrs = {
            "sideCoverages": _coverage_rings(polygon, _unique_sides([entry_side, exit_side])),
        }
        endpoint_attrs.update(attributes or {})
        endpoints.append(
            ConnectorEndpoint(
                id=f"EP_{connector_id}_{level_id}",
                level_id=level_id,
                footprint=_polygon_ring(polygon),
                entry_side=entry_side,
                exit_side=exit_side,
                open_sides=_unique_sides([entry_side, exit_side]),
                attributes=endpoint_attrs,
            )
        )
        state.level_by_id(level_id).geometry_dirty = True

    levels = [state.level_by_id(level_id) for level_id in served_level_ids]
    connector = VerticalConnector(
        id=connector_id,
        connector_type="Elevator",
        scope="inter_level" if len(served_level_ids) > 1 else "same_level",
        endpoints=endpoints,
        source_level=served_level_ids[0],
        target_level=served_level_ids[-1],
        from_elevation_m=levels[0].elevation_m,
        to_elevation_m=levels[-1].elevation_m,
        locomotion_types=["Walking", "Rolling"],
        attributes={
            "capacityPersons": (attributes or {}).get("capacityPersons", 8),
            "estimatedWaitSeconds": (attributes or {}).get("estimatedWaitSeconds", 20),
            "travelSpeedMps": (attributes or {}).get("travelSpeedMps", 1.0),
        },
    )
    state.vertical_connectors.append(connector)
    return connector


def _validate_tile_chain(tile_origins: list[tuple[float, float]], tile_size: float) -> None:
    seen: set[tuple[int, int]] = set()
    previous = None
    for origin in tile_origins:
        key = (round(float(origin[0]) / tile_size), round(float(origin[1]) / tile_size))
        if key in seen:
            raise ValueError("Connector tile chain contains a duplicate tile.")
        seen.add(key)
        if previous is not None:
            distance = abs(key[0] - previous[0]) + abs(key[1] - previous[1])
            if distance != 1:
                raise ValueError("Connector tiles must be contiguous by side.")
        previous = key


def _union_tile_footprint(tile_origins: list[tuple[float, float]], tile_size: float) -> Polygon:
    tiles = [box(x, y, x + tile_size, y + tile_size) for x, y in tile_origins]
    geom = unary_union(tiles)
    if not isinstance(geom, Polygon):
        geom = geom.convex_hull
    return geom


def _coverage_rings(footprint: Polygon, open_sides: list[str]) -> list[list[tuple[float, float]]]:
    try:
        t = COVERAGE_THICKNESS_M
        open_set = set(_unique_sides(open_sides))
        if len(open_set) >= len(SIDE_VECTORS):
            return []
        minx, miny, maxx, maxy = footprint.bounds
        coverage = footprint.buffer(t, join_style=2).difference(footprint)
        for side in open_set:
            coverage = coverage.difference(_open_side_aperture((minx, miny, maxx, maxy), side, t))
        coverage = coverage.buffer(0, join_style=2)
    except Exception:
        return []
    rings = []
    geoms = coverage.geoms if hasattr(coverage, "geoms") else [coverage]
    for geom in geoms:
        if isinstance(geom, Polygon) and geom.area > 1e-6:
            rings.append(_polygon_ring(geom))
    return rings


def _open_side_aperture(bounds: tuple[float, float, float, float], side: str, thickness: float) -> Polygon:
    minx, miny, maxx, maxy = bounds
    margin = thickness * 1.25
    inside = min(thickness * 0.05, 0.01)
    if side == "north":
        return box(minx - margin, miny - margin, maxx + margin, miny + inside)
    if side == "south":
        return box(minx - margin, maxy - inside, maxx + margin, maxy + margin)
    if side == "east":
        return box(maxx - inside, miny - margin, maxx + margin, maxy + margin)
    if side == "west":
        return box(minx - margin, miny - margin, minx + inside, maxy + margin)
    return Polygon()


def _segment_side(footprint: Polygon, segment: LineString) -> str | None:
    minx, miny, maxx, maxy = footprint.bounds
    point = segment.interpolate(0.5, normalized=True)
    eps = 1e-6
    if abs(point.y - miny) <= eps:
        return "north"
    if abs(point.y - maxy) <= eps:
        return "south"
    if abs(point.x - maxx) <= eps:
        return "east"
    if abs(point.x - minx) <= eps:
        return "west"
    return None


def _side_line(footprint: Polygon, side: str) -> LineString | None:
    if side not in SIDE_VECTORS:
        return None
    minx, miny, maxx, maxy = footprint.bounds
    if side == "north":
        return LineString([(minx, miny), (maxx, miny)])
    if side == "south":
        return LineString([(minx, maxy), (maxx, maxy)])
    if side == "east":
        return LineString([(maxx, miny), (maxx, maxy)])
    if side == "west":
        return LineString([(minx, miny), (minx, maxy)])
    return None


def _polygon_ring(poly: Polygon) -> list[tuple[float, float]]:
    coords = [(round(float(x), 6), round(float(y), 6)) for x, y in poly.exterior.coords]
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    return coords


def _unique_sides(sides: list[str | None]) -> list[str]:
    values = []
    for side in sides:
        if side and side not in values:
            if side not in SIDE_VECTORS:
                raise ValueError(f"Unsupported connector side: {side}")
            values.append(side)
    return values


def _default_target_level(state: BuildingAuthoringState, active_level_id: str) -> str:
    levels = state.sorted_levels()
    for index, level in enumerate(levels):
        if level.id == active_level_id:
            if index + 1 < len(levels):
                return levels[index + 1].id
            return level.id
    return active_level_id


def _locomotion_for(connector_type: str) -> list[str]:
    if connector_type == "Elevator":
        return ["Walking", "Rolling"]
    if connector_type == "Ramp":
        return ["Walking", "Rolling"]
    return ["Walking"]


def _connector_attributes(connector_type: str, tile_size: float, tile_origins, attrs: dict) -> dict:
    result = dict(attrs)
    result["tileSizeM"] = tile_size
    result["tileOrigins"] = [(float(x), float(y)) for x, y in tile_origins]
    if connector_type == "Stair":
        result.setdefault("requiresSteps", True)
        result.setdefault("wheelchairAccessible", False)
        result.setdefault("stepCount", max(1, len(tile_origins)) * 3)
    elif connector_type == "Ramp":
        result.setdefault("requiresSteps", False)
        result.setdefault("wheelchairAccessible", True)
        result.setdefault("slope", 0.08)
        result.setdefault("maxGradient", 0.083)
    return result

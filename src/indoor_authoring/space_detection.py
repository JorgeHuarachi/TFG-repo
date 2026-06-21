"""Automatic room detection from authoring centerlines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize_full, unary_union

from .model import BuildingAuthoringState, DetectedSpace, LevelAuthoringState, VirtualBoundary, level_code
from .space_decomposition import decompose_space

try:
    from indoor_data_model import derive_wall_mass_from_snapshot
except ImportError:  # Package import path used by unittest from repository root.
    from src.indoor_data_model import derive_wall_mass_from_snapshot


MIN_SPACE_AREA = 1e-4
IOU_REUSE_THRESHOLD = 0.55
WALL_BUFFER_DEFAULT_M = 0.05
CONNECTOR_OBSTACLE_TYPES = {"Stair", "Ramp", "Elevator"}


@dataclass
class DetectionResult:
    ok: bool
    level_id: str
    report: dict[str, object]


def detect_all_levels(state: BuildingAuthoringState) -> list[DetectionResult]:
    return [detect_spaces(state, level.id) for level in state.sorted_levels()]


def detect_spaces(state: BuildingAuthoringState, level_id: str | None = None) -> DetectionResult:
    level = state.level_by_id(level_id or state.active_level_id)
    previous_spaces = list(level.detected_spaces)

    exterior_lines = [_line_from_coords(line.centerline()) for line in level.wall_centerlines if line.element_type == "muro_exterior"]
    exterior_lines = [line for line in exterior_lines if line is not None]
    shell, shell_report = _derive_shell(exterior_lines)
    if shell is None:
        report = {
            "status": "error",
            "error": "open_exterior_shell",
            "message": "Exterior wall centerlines do not form a closed shell; previous detected spaces were preserved.",
            **shell_report,
        }
        level.detection_report = report
        return DetectionResult(False, level.id, report)

    linework = []
    for line in level.wall_centerlines:
        geom = _line_from_coords(line.centerline())
        if geom is not None:
            linework.append(geom)
    # Automatic virtual boundaries are an output of this pass. Feeding old ones
    # back into polygonization makes repeated detections split spaces on stale
    # derived geometry instead of on the current wall authoring.
    for boundary in level.manual_virtual_boundaries:
        geom = _line_from_coords(boundary.line)
        if geom is not None:
            linework.append(geom)

    if not linework:
        report = {"status": "error", "error": "empty_linework", "message": "No authoring linework available."}
        level.detection_report = report
        return DetectionResult(False, level.id, report)

    merged = unary_union(linework)
    polygons, dangles, cuts, invalids = polygonize_full(merged)
    face_polygons = [
        face
        for face in _iter_polygon_geoms(polygons)
        if face.area > MIN_SPACE_AREA and shell.covers(face.representative_point())
    ]

    obstacle_union = _obstacle_union(level, state)
    detected: list[DetectedSpace] = []
    automatic_boundaries: list[VirtualBoundary] = []
    reusable = _previous_polygons(previous_spaces)
    code = level_code(level.id)
    space_index = 1
    boundary_index = 1
    decomp_reports = []

    for face_index, face in enumerate(sorted(face_polygons, key=lambda p: (-p.area, p.bounds[1], p.bounds[0])), start=1):
        try:
            free_geom = face.difference(obstacle_union) if obstacle_union and not obstacle_union.is_empty else face
        except Exception:
            free_geom = face
        for free_poly in _iter_polygon_geoms(free_geom):
            if free_poly.area <= MIN_SPACE_AREA or not free_poly.is_valid:
                continue
            decomp = decompose_space(free_poly)
            decomp_reports.append({"faceIndex": face_index, **decomp.report})
            for part in decomp.parts:
                if part.area <= MIN_SPACE_AREA:
                    continue
                space_id = _stable_space_id(part, reusable, f"CS_{code}_ROOM_{space_index:03d}")
                detected.append(
                    DetectedSpace(
                        id=space_id,
                        level_id=level.id,
                        polygon=_polygon_to_rings(part),
                        source_face_id=f"FACE_{code}_{face_index:03d}",
                        attributes={
                            "category": "Room",
                            "function": "General",
                            "locomotion": ["Walking", "Rolling"],
                            "detectedAutomatically": True,
                            "areaM2": round(float(part.area), 6),
                        },
                    )
                )
                space_index += 1

            reason = str(decomp.report.get("generationReason") or "concavity_split")
            for line in decomp.virtual_boundaries:
                automatic_boundaries.append(
                    VirtualBoundary(
                        id=f"VB_{code}_AUTO_{boundary_index:03d}",
                        level_id=level.id,
                        line=_line_to_coords(line),
                        generated_automatically=True,
                        generation_reason=reason,
                        traversable=True,
                        attributes={
                            "sourceFaceId": f"FACE_{code}_{face_index:03d}",
                            "isVirtual": True,
                        },
                    )
                )
                boundary_index += 1

    level.detected_spaces = detected
    level.automatic_virtual_boundaries = automatic_boundaries
    level.geometry_dirty = False
    report = {
        "status": "ok",
        "polygons": len(face_polygons),
        "detectedSpaces": len(detected),
        "automaticVirtualBoundaries": len(automatic_boundaries),
        "dangles": _geom_count(dangles),
        "cuts": _geom_count(cuts),
        "invalidRings": _geom_count(invalids),
        "shellAreaM2": round(float(shell.area), 6),
        "decomposition": decomp_reports,
    }
    level.detection_report = report
    return DetectionResult(True, level.id, report)


def _derive_shell(exterior_lines: list[LineString]) -> tuple[Polygon | None, dict[str, object]]:
    if not exterior_lines:
        return None, {"exteriorLineCount": 0}
    merged = unary_union(exterior_lines)
    polygons, dangles, cuts, invalids = polygonize_full(merged)
    shells = [poly for poly in _iter_polygon_geoms(polygons) if poly.area > MIN_SPACE_AREA]
    report = {
        "exteriorLineCount": len(exterior_lines),
        "shellCandidates": len(shells),
        "shellDangles": _geom_count(dangles),
        "shellCuts": _geom_count(cuts),
        "shellInvalidRings": _geom_count(invalids),
    }
    if not shells:
        return None, report
    return max(shells, key=lambda poly: poly.area), report


def _obstacle_union(level: LevelAuthoringState, state: BuildingAuthoringState):
    obstacles = []
    wall_union = _final_wall_union(level, state)
    if wall_union is not None and not wall_union.is_empty:
        obstacles.append(wall_union)
    for column in level.columns:
        poly = _polygon_from_ring(column.footprint)
        if poly is not None:
            obstacles.append(poly)
    for connector in state.vertical_connectors:
        if connector.connector_type not in CONNECTOR_OBSTACLE_TYPES:
            continue
        for endpoint in connector.endpoints:
            if endpoint.level_id != level.id:
                continue
            poly = _polygon_from_ring(endpoint.footprint)
            if poly is not None:
                obstacles.append(poly)
            for coverage in endpoint.attributes.get("sideCoverages", []):
                coverage_poly = _polygon_from_ring(coverage)
                if coverage_poly is not None:
                    obstacles.append(coverage_poly)
    if not obstacles:
        return Polygon()
    try:
        return unary_union(obstacles)
    except Exception:
        return Polygon()


def _final_wall_union(level: LevelAuthoringState, state: BuildingAuthoringState):
    try:
        snapshot = state.to_snapshot(
            "space_detection",
            {"width": 0, "height": 0},
            crs={"type": "local", "unit": "meters", "origin": {"x": 0, "y": 0, "z": 0}, "axisOrder": "xyz"},
        )
        result = derive_wall_mass_from_snapshot(snapshot, level.id)
        wall_union = result.get("solidWallUnion")
        if wall_union is None or wall_union.is_empty:
            wall_union = result.get("wallUnion")
        if wall_union is not None and not wall_union.is_empty:
            return wall_union
    except Exception:
        pass

    fallback = []
    for wall in level.wall_centerlines:
        geom = _line_from_coords(wall.centerline())
        if geom is None:
            continue
        thickness = wall.thickness_m or WALL_BUFFER_DEFAULT_M
        try:
            fallback.append(geom.buffer(float(thickness) / 2.0, cap_style=3, join_style=2))
        except Exception:
            continue
    try:
        return unary_union(fallback) if fallback else Polygon()
    except Exception:
        return Polygon()


def _previous_polygons(spaces: Iterable[DetectedSpace]) -> dict[str, Polygon]:
    result = {}
    for space in spaces:
        poly = _polygon_from_rings(space.polygon)
        if poly is not None:
            result[space.id] = poly
    return result


def _stable_space_id(candidate: Polygon, previous: dict[str, Polygon], fallback: str) -> str:
    best_id = None
    best_iou = 0.0
    for space_id, poly in previous.items():
        try:
            inter = candidate.intersection(poly).area
            union = candidate.union(poly).area
        except Exception:
            continue
        if union <= 0:
            continue
        iou = inter / union
        if iou > best_iou:
            best_iou = iou
            best_id = space_id
    if best_id is not None and best_iou >= IOU_REUSE_THRESHOLD:
        previous.pop(best_id, None)
        return best_id
    return fallback


def _line_from_coords(coords) -> LineString | None:
    try:
        line = LineString(coords)
    except Exception:
        return None
    if line.is_empty or line.length <= 0:
        return None
    return line


def _polygon_from_ring(coords) -> Polygon | None:
    try:
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception:
        return None
    if poly.is_empty or poly.area <= MIN_SPACE_AREA:
        return None
    return poly


def _polygon_from_rings(rings) -> Polygon | None:
    if not rings:
        return None
    try:
        poly = Polygon(rings[0], rings[1:])
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception:
        return None
    if poly.is_empty or poly.area <= MIN_SPACE_AREA:
        return None
    return poly


def _iter_polygon_geoms(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if hasattr(geom, "geoms"):
        result: list[Polygon] = []
        for part in geom.geoms:
            result.extend(_iter_polygon_geoms(part))
        return result
    return []


def _geom_count(geom) -> int:
    if geom is None or geom.is_empty:
        return 0
    if hasattr(geom, "geoms"):
        return len(geom.geoms)
    return 1


def _polygon_to_rings(poly: Polygon) -> list[list[tuple[float, float]]]:
    rings = [_coords_to_tuples(poly.exterior.coords)]
    for interior in poly.interiors:
        rings.append(_coords_to_tuples(interior.coords))
    return rings


def _line_to_coords(line: LineString) -> list[tuple[float, float]]:
    return _coords_to_tuples(line.coords)


def _coords_to_tuples(coords) -> list[tuple[float, float]]:
    return [(round(float(x), 6), round(float(y), 6)) for x, y in coords]

"""Automatic decomposition of detected indoor faces into simpler cells."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import triangulate, unary_union


AREA_TOLERANCE = 1e-6
MIN_PART_AREA = 1e-5
MIN_BOUNDARY_LENGTH = 1e-4


@dataclass
class DecompositionResult:
    parts: list[Polygon]
    virtual_boundaries: list[LineString]
    report: dict[str, object]


def decompose_space(polygon: Polygon) -> DecompositionResult:
    poly = _clean_polygon(polygon)
    if poly is None:
        return DecompositionResult([], [], {"status": "invalid_input"})

    if _is_simple_convex(poly):
        return DecompositionResult([poly], [], {"status": "already_simple", "partCount": 1})

    pieces = _triangulated_parts(poly)
    if not pieces:
        return DecompositionResult([poly], [], {"status": "fallback_original", "partCount": 1})

    merged = _merge_greedily(pieces)
    boundaries = _shared_boundaries(merged)
    union_area_error = _symmetric_difference_area(poly, unary_union(merged))

    if union_area_error > AREA_TOLERANCE:
        # Preserve correctness over pretty decomposition.
        pieces = _triangulated_parts(poly)
        merged = pieces or [poly]
        boundaries = _shared_boundaries(merged)
        union_area_error = _symmetric_difference_area(poly, unary_union(merged))

    reason = "hole_bridge" if len(poly.interiors) else "concavity_split"
    return DecompositionResult(
        parts=merged,
        virtual_boundaries=boundaries,
        report={
            "status": "decomposed",
            "generationReason": reason,
            "partCount": len(merged),
            "virtualBoundaryCount": len(boundaries),
            "unionAreaError": round(float(union_area_error), 9),
        },
    )


def _clean_polygon(geom) -> Polygon | None:
    if geom is None or geom.is_empty:
        return None
    try:
        cleaned = geom if geom.is_valid else geom.buffer(0)
    except Exception:
        return None
    if cleaned.is_empty:
        return None
    if isinstance(cleaned, Polygon):
        return cleaned if cleaned.area > MIN_PART_AREA else None
    if isinstance(cleaned, MultiPolygon):
        parts = [part for part in cleaned.geoms if part.area > MIN_PART_AREA]
        if not parts:
            return None
        return max(parts, key=lambda part: part.area)
    return None


def _is_simple_convex(poly: Polygon) -> bool:
    if len(poly.interiors):
        return False
    try:
        return _symmetric_difference_area(poly, poly.convex_hull) <= AREA_TOLERANCE
    except Exception:
        return False


def _triangulated_parts(poly: Polygon) -> list[Polygon]:
    pieces: list[Polygon] = []
    for triangle in triangulate(poly):
        try:
            clipped = triangle.intersection(poly)
        except Exception:
            continue
        for part in _iter_polygons(clipped):
            if part.area <= MIN_PART_AREA:
                continue
            point = part.representative_point()
            if not poly.buffer(AREA_TOLERANCE).covers(point):
                continue
            pieces.append(part)
    return pieces


def _merge_greedily(parts: list[Polygon]) -> list[Polygon]:
    merged = list(parts)
    changed = True
    while changed:
        changed = False
        best_pair: tuple[int, int] | None = None
        best_length = 0.0
        best_union: Polygon | None = None
        for i, left in enumerate(merged):
            for j in range(i + 1, len(merged)):
                right = merged[j]
                shared_length = _shared_length(left, right)
                if shared_length <= MIN_BOUNDARY_LENGTH or shared_length <= best_length:
                    continue
                unioned = _clean_polygon(left.union(right))
                if unioned is None or isinstance(unioned, MultiPolygon):
                    continue
                if _is_simple_convex(unioned):
                    best_pair = (i, j)
                    best_length = shared_length
                    best_union = unioned
        if best_pair is not None and best_union is not None:
            i, j = best_pair
            next_parts = []
            for index, part in enumerate(merged):
                if index not in {i, j}:
                    next_parts.append(part)
            next_parts.append(best_union)
            merged = next_parts
            changed = True
    return sorted(merged, key=lambda part: (round(part.bounds[1], 6), round(part.bounds[0], 6), -part.area))


def _shared_boundaries(parts: list[Polygon]) -> list[LineString]:
    lines: list[LineString] = []
    for i, left in enumerate(parts):
        for right in parts[i + 1 :]:
            try:
                shared = left.boundary.intersection(right.boundary)
            except Exception:
                continue
            for line in _iter_lines(shared):
                if line.length > MIN_BOUNDARY_LENGTH:
                    lines.append(line)
    return _dedupe_lines(lines)


def _shared_length(left: Polygon, right: Polygon) -> float:
    try:
        return sum(line.length for line in _iter_lines(left.boundary.intersection(right.boundary)))
    except Exception:
        return 0.0


def _iter_polygons(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        result: list[Polygon] = []
        for part in geom.geoms:
            result.extend(_iter_polygons(part))
        return result
    return []


def _iter_lines(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    if isinstance(geom, GeometryCollection):
        result: list[LineString] = []
        for part in geom.geoms:
            result.extend(_iter_lines(part))
        return result
    return []


def _dedupe_lines(lines: list[LineString]) -> list[LineString]:
    seen: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    result: list[LineString] = []
    for line in lines:
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        start = _rounded_coord(coords[0])
        end = _rounded_coord(coords[-1])
        key = tuple(sorted((start, end)))  # type: ignore[arg-type]
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def _rounded_coord(coord) -> tuple[float, float]:
    return round(float(coord[0]), 6), round(float(coord[1]), 6)


def _symmetric_difference_area(left: Polygon, right) -> float:
    try:
        return left.symmetric_difference(right).area
    except Exception:
        return float("inf")

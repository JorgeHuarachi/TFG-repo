"""Geometry conversion helpers for the Indoor Data Model exporter."""

from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import unary_union


MIN_AREA = 1e-9
MIN_LENGTH = 1e-6


def _coord(value):
    rounded = round(float(value), 6)
    return 0.0 if rounded == -0.0 else rounded


def close_ring(coords):
    ring = [[_coord(x), _coord(y)] for x, y in coords]
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return ring


def point_geojson(point):
    return {"type": "Point", "coordinates": [_coord(point.x), _coord(point.y)]}


def line_geojson(line):
    return {
        "type": "LineString",
        "coordinates": [[_coord(x), _coord(y)] for x, y in line.coords],
    }


def polygon_geojson(poly):
    rings = [close_ring(poly.exterior.coords)]
    for interior in poly.interiors:
        rings.append(close_ring(interior.coords))
    return {"type": "Polygon", "coordinates": rings}


def polygon_from_coords(coords):
    if not coords or len(coords) < 3:
        return None
    try:
        poly = Polygon(coords)
        return clean_polygon(poly)
    except Exception:
        return None


def line_from_coords(coords):
    if not coords or len(coords) < 2:
        return None
    try:
        line = LineString(coords)
    except Exception:
        return None
    if line.is_empty or line.length <= MIN_LENGTH:
        return None
    return line


def footprint_from_centerline(coords, thickness):
    line = line_from_coords(coords)
    if line is None:
        return None
    try:
        return clean_polygon(line.buffer(float(thickness) / 2.0, cap_style=2, join_style=2))
    except Exception:
        return None


def clean_polygon(poly):
    if poly is None or poly.is_empty:
        return None
    try:
        if not poly.is_valid:
            poly = poly.buffer(0)
    except Exception:
        return None
    if poly.is_empty:
        return None
    if isinstance(poly, Polygon):
        return poly if poly.area > MIN_AREA else None
    if isinstance(poly, MultiPolygon):
        parts = [part for part in poly.geoms if part.area > MIN_AREA]
        if not parts:
            return None
        return MultiPolygon(parts) if len(parts) > 1 else parts[0]
    return None


def iter_polygons(geom):
    geom = clean_polygon(geom) if isinstance(geom, (Polygon, MultiPolygon)) else geom
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom] if geom.area > MIN_AREA else []
    if isinstance(geom, MultiPolygon):
        return [part for part in geom.geoms if part.area > MIN_AREA]
    if isinstance(geom, GeometryCollection):
        parts = []
        for part in geom.geoms:
            parts.extend(iter_polygons(part))
        return parts
    return []


def union_polygons(polygons):
    useful = [poly for poly in polygons if poly is not None and not poly.is_empty and poly.area > MIN_AREA]
    if not useful:
        return Polygon()
    try:
        return unary_union(useful)
    except Exception:
        return Polygon()


def extract_lines(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom] if geom.length > MIN_LENGTH else []
    if isinstance(geom, MultiLineString):
        lines = []
        for part in geom.geoms:
            lines.extend(extract_lines(part))
        return lines
    if isinstance(geom, Polygon):
        lines = []
        coords = list(geom.exterior.coords)
        for start, end in zip(coords, coords[1:]):
            line = LineString([start, end])
            if line.length > MIN_LENGTH:
                lines.append(line)
        return lines
    if isinstance(geom, MultiPolygon):
        lines = []
        for part in geom.geoms:
            lines.extend(extract_lines(part.boundary))
        return lines
    if isinstance(geom, GeometryCollection):
        lines = []
        for part in geom.geoms:
            lines.extend(extract_lines(part))
        return lines
    return []


def longest_line(geom_or_lines, min_length=0.05):
    lines = geom_or_lines if isinstance(geom_or_lines, list) else extract_lines(geom_or_lines)
    useful = [line for line in lines if line.length >= min_length]
    if not useful:
        return None
    return max(useful, key=lambda line: line.length)


def contact_line(poly_a, poly_b, min_length=0.05, tolerance=0.0):
    candidates = []
    try:
        candidates.extend(extract_lines(poly_a.boundary.intersection(poly_b.boundary)))
        candidates.extend(extract_lines(poly_a.boundary.intersection(poly_b)))
        candidates.extend(extract_lines(poly_b.boundary.intersection(poly_a)))
        overlap = poly_a.intersection(poly_b)
        candidates.extend(extract_lines(overlap.boundary if hasattr(overlap, "boundary") else overlap))
    except Exception:
        return None

    line = longest_line(candidates, min_length=min_length)
    if line is not None:
        return line

    if tolerance <= 0:
        return None

    try:
        inflated_overlap = poly_a.buffer(tolerance).intersection(poly_b)
        if inflated_overlap.area <= MIN_AREA:
            return None
        return longest_line(
            extract_lines(inflated_overlap.boundary if hasattr(inflated_overlap, "boundary") else inflated_overlap),
            min_length=min_length,
        )
    except Exception:
        return None


def node_point_for_polygon(poly):
    centroid = poly.centroid
    if poly.contains(centroid) or poly.touches(centroid):
        return centroid
    return poly.representative_point()

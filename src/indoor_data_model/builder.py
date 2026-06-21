"""Build IndoorJSON-like indoor_model.json documents from SpatialEngine snapshots."""

import datetime

from shapely.geometry import LineString, Point, Polygon, box

from .geometry import (
    clean_boolean_polygon,
    contact_line,
    extract_lines,
    footprint_from_centerline,
    iter_polygons,
    line_from_coords,
    line_geojson,
    node_point_for_polygon,
    point_geojson,
    polygon_from_coords,
    polygon_geojson,
    union_polygons,
)
from .ids import compact_cell_token, edge_id_for_boundary, node_id_for_cell, normalize_token, ref


WALL_TYPES = {"muro_exterior", "muro_interior"}
DOOR_TYPES = {"puerta_simple", "puerta_doble"}
EXIT_TYPES = {"salida"}
VIRTUAL_BOUNDARY_TYPES = {"frontera_virtual"}
WINDOW_TYPES = {"ventana", "ventana_practicable"}
LEVEL_ID = "LEVEL_00"
LEVEL_CODE = "L00"
LAYER_ID = "TL_NAV_L00"
PRIMAL_ID = "PS_NAV_L00"
DUAL_ID = "DS_NAV_L00"
WALL_CAP_STYLE = 2
OPENING_CAP_STYLE = 2
JOIN_STYLE = 2
OVERLAP_AREA_TOLERANCE = 1e-6
WALL_CONNECTION_TOLERANCE = 0.05
MIN_JUNCTION_SIN = 0.05
WALL_MITER_LIMIT = 0.6
JUNCTION_EPSILON = 0.002
MIN_WALL_PART_AREA = 1e-6
BOUNDARY_CONTACT_TOLERANCE = 0.01
EXTERIOR_BOUNDARY_MIN_LENGTH = 0.05
EXPORT_WALL_WALL_BOUNDARIES = False
EDGE_MODE_NAVIGATION = "navigation"
EDGE_MODE_ALL_ADJACENCY = "all_adjacency"
EDGE_MODES = {EDGE_MODE_NAVIGATION, EDGE_MODE_ALL_ADJACENCY}


def is_wall_type(tipo):
    return tipo in WALL_TYPES


def is_door_type(tipo):
    return tipo in DOOR_TYPES


def is_exit_type(tipo):
    return tipo in EXIT_TYPES


def is_virtual_boundary_type(tipo):
    return tipo in VIRTUAL_BOUNDARY_TYPES


def is_opening_type(tipo):
    return is_door_type(tipo) or is_exit_type(tipo) or tipo in WINDOW_TYPES


def is_solid_wall_type(tipo):
    return is_wall_type(tipo)


def is_transfer_authoring_type(tipo):
    return is_door_type(tipo) or is_exit_type(tipo)


def is_non_solid_topology_type(tipo):
    return is_virtual_boundary_type(tipo)


def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _unique_append(values, value):
    if value and value not in values:
        values.append(value)


def _normalize_locomotion(values):
    allowed = {"Flying", "Rolling", "Walking", "Unspecified"}
    mapping = {
        "flying": "Flying",
        "rolling": "Rolling",
        "walking": "Walking",
        "unspecified": "Unspecified",
        "step": "Walking",
        "stairs": "Walking",
    }
    result = []
    for value in values or []:
        normalized = mapping.get(str(value).strip().lower(), str(value).strip())
        if normalized in allowed:
            _unique_append(result, normalized)
    return result or ["Walking", "Rolling"]


class IndoorModelBuilder:
    def __init__(self, snapshot, edge_mode=EDGE_MODE_NAVIGATION):
        if edge_mode not in EDGE_MODES:
            allowed = ", ".join(sorted(EDGE_MODES))
            raise ValueError(f"edge_mode no soportado: {edge_mode!r}. Valores permitidos: {allowed}.")
        self.snapshot = snapshot
        self.edge_mode = edge_mode
        self.now = snapshot.get("createdAt") or _now_utc()
        self.level = self._snapshot_level()
        self.level_id = self.level.get("id") or LEVEL_ID
        self.level_index = int(self.level.get("levelIndex", self.level.get("order", 0)) or 0)
        self.level_code = self._level_code(self.level_id)
        self.layer_id = f"TL_NAV_{self.level_code}"
        self.primal_id = f"PS_NAV_{self.level_code}"
        self.dual_id = f"DS_NAV_{self.level_code}"
        self.source_features = []
        self.source_by_id = {}
        self.source_by_line_name = {}
        self.source_by_space_name = {}
        self.line_by_name = {}
        self.authoring_lines = []
        self.cells = []
        self.boundaries = []
        self.edges = []
        self.nodes = []
        self.node_connects = {}
        self.wall_parts = []
        self.wall_union = None
        self.solid_wall_union = None
        self.object_union = None
        self.transfer_union = None
        self.connector_union = None
        self.opening_union = None
        self.overlap_warnings = []
        self.connector_endpoint_cells = {}
        self.same_level_connector_boundary_by_connector = {}

    def _snapshot_level(self):
        levels = self.snapshot.get("levels") or []
        if levels:
            return dict(levels[0])
        return {
            "id": LEVEL_ID,
            "name": "Ground floor",
            "levelIndex": 0,
            "floorZ": 0.0,
            "ceilingZ": 3.0,
            "heightM": 3.0,
        }

    def _level_code(self, level_id):
        token = str(level_id or LEVEL_ID).upper()
        if token.startswith("LEVEL_"):
            token = token[len("LEVEL_") :]
        if token.isdigit():
            return f"L{int(token):02d}"
        return normalize_token(token, "L00")

    def _ref(self, container_id, object_id):
        return ref(self.layer_id, container_id, object_id)

    def build(self):
        self._prepare_authoring_lines()
        self._create_source_features()
        self._derive_wall_parts()
        self._create_object_spaces()
        self._create_transfer_spaces()
        self._create_connector_spaces()
        self._create_general_spaces()
        self._create_wall_spaces()

        if not self.cells:
            raise ValueError("No hay CellSpaces exportables para indoor_model.json.")

        self._validate_cell_overlaps()
        self._create_boundaries()
        self._create_dual_space()
        self._sync_cell_boundary_refs()

        return self._root_document()

    def _prepare_authoring_lines(self):
        for line in self.snapshot.get("authoringElements", []):
            prepared = dict(line)
            tipo = prepared.get("type")
            prepared["level"] = prepared.get("level") or self.level_id
            if prepared["level"] != self.level_id:
                continue
            prepared["centerline"] = list(prepared.get("centerline") or [])
            prepared["attributes"] = dict(prepared.get("attributes") or {})
            self.authoring_lines.append(prepared)

        self._extend_solid_wall_centerlines()

        for prepared in self.authoring_lines:
            tipo = prepared.get("type")
            prepared["_footprint_poly"] = self._derived_line_footprint(prepared)
            if tipo and prepared.get("name"):
                self.line_by_name[prepared["name"]] = prepared

    def _extend_solid_wall_centerlines(self):
        for line in self.authoring_lines:
            if not is_solid_wall_type(line.get("type")):
                continue
            coords = list(line.get("centerline") or [])
            if len(coords) < 2:
                continue
            line["_derived_centerline"] = coords

    def _wall_pair_junction_candidates(self, wall_a, wall_b):
        candidates = []
        segments_a = self._wall_centerline_segments(wall_a)
        segments_b = self._wall_centerline_segments(wall_b)
        if not segments_a or not segments_b:
            return candidates

        endpoints_a = self._wall_terminal_points(wall_a)
        endpoints_b = self._wall_terminal_points(wall_b)

        for endpoint_a in endpoints_a:
            point_a = endpoint_a["point"]
            for endpoint_b in endpoints_b:
                point_b = endpoint_b["point"]
                if point_a.distance(point_b) > WALL_CONNECTION_TOLERANCE:
                    continue
                seg_a = self._nearest_segment(point_a, segments_a)
                seg_b = self._nearest_segment(point_b, segments_b)
                sin_theta = self._segment_sin(seg_a, seg_b)
                if sin_theta < MIN_JUNCTION_SIN:
                    continue
                point = Point((point_a.x + point_b.x) / 2.0, (point_a.y + point_b.y) / 2.0)
                candidates.append(
                    self._junction_candidate(
                        "endpoint-endpoint",
                        point,
                        wall_a,
                        wall_b,
                        sin_theta,
                        endpoint_a=endpoint_a["index"],
                        endpoint_b=endpoint_b["index"],
                        distance=point_a.distance(point_b),
                    )
                )

        for endpoint in endpoints_a:
            point = endpoint["point"]
            for segment_b in segments_b:
                projected = self._project_point_to_segment(point, segment_b)
                if projected is None or point.distance(projected) > WALL_CONNECTION_TOLERANCE:
                    continue
                if self._point_is_terminal(projected, endpoints_b):
                    continue
                segment_a = self._nearest_segment(point, segments_a)
                sin_theta = self._segment_sin(segment_a, segment_b)
                if sin_theta < MIN_JUNCTION_SIN:
                    continue
                candidates.append(
                    self._junction_candidate(
                        "endpoint-segment",
                        projected,
                        wall_a,
                        wall_b,
                        sin_theta,
                        endpoint_a=endpoint["index"],
                        distance=point.distance(projected),
                    )
                )

        for endpoint in endpoints_b:
            point = endpoint["point"]
            for segment_a in segments_a:
                projected = self._project_point_to_segment(point, segment_a)
                if projected is None or point.distance(projected) > WALL_CONNECTION_TOLERANCE:
                    continue
                if self._point_is_terminal(projected, endpoints_a):
                    continue
                segment_b = self._nearest_segment(point, segments_b)
                sin_theta = self._segment_sin(segment_a, segment_b)
                if sin_theta < MIN_JUNCTION_SIN:
                    continue
                candidates.append(
                    self._junction_candidate(
                        "endpoint-segment",
                        projected,
                        wall_a,
                        wall_b,
                        sin_theta,
                        endpoint_b=endpoint["index"],
                        distance=point.distance(projected),
                    )
                )

        for segment_a in segments_a:
            for segment_b in segments_b:
                sin_theta = self._segment_sin(segment_a, segment_b)
                if sin_theta < MIN_JUNCTION_SIN:
                    continue
                try:
                    intersection = segment_a["line"].intersection(segment_b["line"])
                except Exception:
                    continue
                if intersection.is_empty or intersection.geom_type != "Point":
                    continue
                if self._point_is_terminal(intersection, endpoints_a) and self._point_is_terminal(
                    intersection,
                    endpoints_b,
                ):
                    continue
                candidates.append(
                    self._junction_candidate(
                        "segment-segment",
                        intersection,
                        wall_a,
                        wall_b,
                        sin_theta,
                    )
                )

        return candidates

    def _junction_candidate(
        self,
        kind,
        point,
        wall_a,
        wall_b,
        sin_theta,
        endpoint_a=None,
        endpoint_b=None,
        distance=0.0,
    ):
        pair = {
            "kind": kind,
            "wallA": wall_a["index"],
            "wallB": wall_b["index"],
            "sinTheta": sin_theta,
            "extensions": {
                wall_a["index"]: {0: 0.0, -1: 0.0},
                wall_b["index"]: {0: 0.0, -1: 0.0},
            },
        }
        if endpoint_a is not None:
            pair["extensions"][wall_a["index"]][endpoint_a] = self._junction_extension_length(
                wall_b["thickness"],
                sin_theta,
                distance,
            )
        if endpoint_b is not None:
            pair["extensions"][wall_b["index"]][endpoint_b] = self._junction_extension_length(
                wall_a["thickness"],
                sin_theta,
                distance,
            )
        return {
            "kind": kind,
            "point": point,
            "wallIndices": {wall_a["index"], wall_b["index"]},
            "pairs": [pair],
        }

    def _junction_extension_length(self, receiver_thickness, sin_theta, distance=0.0):
        safe_sin = max(abs(float(sin_theta)), MIN_JUNCTION_SIN)
        required = float(receiver_thickness) / (2.0 * safe_sin) + float(distance) + JUNCTION_EPSILON
        return min(required, WALL_MITER_LIMIT)

    def _wall_centerline_segments(self, wall):
        centerline = wall.get("centerline")
        if centerline is None or centerline.is_empty:
            return []
        try:
            coords = list(centerline.coords)
        except Exception:
            return []

        segments = []
        for index, (start, end) in enumerate(zip(coords, coords[1:])):
            try:
                x0, y0 = start
                x1, y1 = end
                dx = float(x1) - float(x0)
                dy = float(y1) - float(y0)
                length = (dx * dx + dy * dy) ** 0.5
            except Exception:
                continue
            if length <= 0:
                continue
            segment_line = line_from_coords([(x0, y0), (x1, y1)])
            if segment_line is None:
                continue
            segments.append(
                {
                    "index": index,
                    "line": segment_line,
                    "unit": (dx / length, dy / length),
                    "length": length,
                }
            )
        return segments

    def _wall_terminal_points(self, wall):
        try:
            coords = list(wall["centerline"].coords)
            start = coords[0]
            end = coords[-1]
        except Exception:
            return []
        return [
            {"index": 0, "point": Point(float(start[0]), float(start[1]))},
            {"index": -1, "point": Point(float(end[0]), float(end[1]))},
        ]

    def _nearest_segment(self, point, segments):
        best_segment = None
        best_distance = None
        for segment in segments:
            try:
                distance = point.distance(segment["line"])
            except Exception:
                continue
            if best_distance is None or distance < best_distance:
                best_segment = segment
                best_distance = distance
        return best_segment

    def _project_point_to_segment(self, point, segment):
        if segment is None:
            return None
        try:
            projected_distance = segment["line"].project(point)
            if projected_distance < -JUNCTION_EPSILON or projected_distance > segment["length"] + JUNCTION_EPSILON:
                return None
            return segment["line"].interpolate(projected_distance)
        except Exception:
            return None

    def _point_is_terminal(self, point, endpoints):
        for endpoint in endpoints:
            try:
                if point.distance(endpoint["point"]) <= WALL_CONNECTION_TOLERANCE:
                    return True
            except Exception:
                continue
        return False

    def _segment_sin(self, segment_a, segment_b):
        if segment_a is None or segment_b is None:
            return 0.0
        ux, uy = segment_a["unit"]
        vx, vy = segment_b["unit"]
        return abs(ux * vy - uy * vx)

    def _group_junction_candidates(self, candidates):
        groups = []
        for candidate in candidates:
            target = None
            for group in groups:
                if candidate["point"].distance(group["point"]) <= WALL_CONNECTION_TOLERANCE:
                    target = group
                    break
            if target is None:
                groups.append(
                    {
                        "point": candidate["point"],
                        "points": [candidate["point"]],
                        "wallIndices": set(candidate["wallIndices"]),
                        "pairs": list(candidate["pairs"]),
                    }
                )
                continue
            target["points"].append(candidate["point"])
            target["wallIndices"].update(candidate["wallIndices"])
            target["pairs"].extend(candidate["pairs"])
            x = sum(point.x for point in target["points"]) / len(target["points"])
            y = sum(point.y for point in target["points"]) / len(target["points"])
            target["point"] = Point(x, y)
        return groups

    def _angle_aware_junction_polygons(self, raw_walls):
        candidates = []
        for index, wall_a in enumerate(raw_walls):
            for wall_b in raw_walls[index + 1 :]:
                candidates.extend(self._wall_pair_junction_candidates(wall_a, wall_b))

        walls_by_index = {wall["index"]: wall for wall in raw_walls}
        junctions = []
        for group in self._group_junction_candidates(candidates):
            polygon = self._junction_polygon_for_group(group, walls_by_index)
            if polygon is None or polygon.is_empty:
                continue
            for part in iter_polygons(polygon):
                if part.area > MIN_WALL_PART_AREA:
                    junctions.append(part)
        return junctions

    def _junction_polygon_for_group(self, group, walls_by_index):
        if not group["wallIndices"]:
            return None

        max_thickness = max(walls_by_index[index]["thickness"] for index in group["wallIndices"])
        center = group["point"]
        radius = max(WALL_MITER_LIMIT, max_thickness * 2.0) + WALL_CONNECTION_TOLERANCE + JUNCTION_EPSILON
        local_envelope = box(center.x - radius, center.y - radius, center.x + radius, center.y + radius)

        extensions = {
            index: {0: 0.0, -1: 0.0}
            for index in group["wallIndices"]
        }
        for pair in group["pairs"]:
            for wall_index, endpoint_extensions in pair["extensions"].items():
                if wall_index not in extensions:
                    extensions[wall_index] = {0: 0.0, -1: 0.0}
                for endpoint_index, extension in endpoint_extensions.items():
                    extensions[wall_index][endpoint_index] = max(
                        extensions[wall_index].get(endpoint_index, 0.0),
                        extension,
                    )

        temporary_polygons = {}
        for wall_index in group["wallIndices"]:
            wall = walls_by_index[wall_index]
            coords = self._extended_wall_coords(wall["line"], extensions.get(wall_index, {}))
            temporary = footprint_from_centerline(
                coords,
                wall["thickness"],
                cap_style=WALL_CAP_STYLE,
                join_style=JOIN_STYLE,
            )
            if temporary is None or temporary.is_empty:
                temporary = wall["polygon"]
            temporary_polygons[wall_index] = temporary

        local_masses = []
        seen_pair_keys = set()
        for pair in group["pairs"]:
            wall_a = pair["wallA"]
            wall_b = pair["wallB"]
            pair_key = tuple(sorted((wall_a, wall_b)))
            if pair_key in seen_pair_keys:
                continue
            seen_pair_keys.add(pair_key)
            try:
                local_mass = temporary_polygons[wall_a].intersection(temporary_polygons[wall_b]).intersection(
                    local_envelope
                )
            except Exception:
                continue
            cleaned = clean_boolean_polygon(local_mass)
            if cleaned.area > MIN_WALL_PART_AREA:
                local_masses.append(cleaned)

        return clean_boolean_polygon(union_polygons(local_masses))

    def _extended_wall_coords(self, line, extensions):
        coords = list(line.get("centerline") or [])
        if len(coords) < 2:
            return coords
        extended = list(coords)
        start_extension = max(0.0, float(extensions.get(0, 0.0) or 0.0))
        end_extension = max(0.0, float(extensions.get(-1, 0.0) or 0.0))
        if start_extension > 0:
            ux, uy = self._endpoint_outward_unit(extended, 0)
            x, y = extended[0]
            extended[0] = (float(x) + ux * start_extension, float(y) + uy * start_extension)
        if end_extension > 0:
            ux, uy = self._endpoint_outward_unit(extended, -1)
            x, y = extended[-1]
            extended[-1] = (float(x) + ux * end_extension, float(y) + uy * end_extension)
        return extended

    def _endpoint_outward_unit(self, coords, endpoint_index):
        try:
            if endpoint_index == 0:
                x0, y0 = coords[0]
                x1, y1 = coords[1]
            else:
                x0, y0 = coords[-1]
                x1, y1 = coords[-2]
            dx = float(x0) - float(x1)
            dy = float(y0) - float(y1)
            length = (dx * dx + dy * dy) ** 0.5
        except Exception:
            return 0.0, 0.0
        if length <= 0:
            return 0.0, 0.0
        return dx / length, dy / length

    def _positive_float(self, value, fallback):
        try:
            number = float(value)
            return number if number > 0 else fallback
        except (TypeError, ValueError):
            return fallback

    def _derived_line_footprint(self, line):
        tipo = line.get("type")
        if is_solid_wall_type(tipo):
            return footprint_from_centerline(
                line.get("_derived_centerline") or line.get("centerline"),
                line.get("thicknessM") or 0.1,
                cap_style=WALL_CAP_STYLE,
                join_style=JOIN_STYLE,
            )
        if is_opening_type(tipo):
            return self._opening_footprint(line)
        if line.get("footprint"):
            return polygon_from_coords(line["footprint"])
        return footprint_from_centerline(
            line.get("centerline"),
            line.get("thicknessM") or 0.1,
        )

    def _opening_footprint(self, line):
        thickness = self._opening_thickness(line)
        centerline = self._opening_centerline(line)
        poly = footprint_from_centerline(
            centerline,
            thickness,
            cap_style=OPENING_CAP_STYLE,
            join_style=JOIN_STYLE,
        )
        if poly is None and line.get("footprint"):
            return polygon_from_coords(line["footprint"])
        return poly

    def _opening_thickness(self, line):
        host_thickness = line.get("hostWallThicknessM")
        try:
            if host_thickness is not None and float(host_thickness) > 0:
                return float(host_thickness)
        except (TypeError, ValueError):
            pass

        attrs = line.setdefault("attributes", {})
        attrs["openingThicknessSource"] = "opening_fallback"
        attrs["warning"] = "opening_host_wall_metadata_missing"
        try:
            return float(line.get("thicknessM") or 0.1)
        except (TypeError, ValueError):
            return 0.1

    def _opening_centerline(self, line):
        coords = line.get("centerline") or []
        geom_line = line_from_coords(coords)
        if geom_line is None:
            return coords

        width = line.get("widthM")
        try:
            width = float(width) if width is not None else None
        except (TypeError, ValueError):
            width = None
        if not width or width <= 0:
            return coords

        midpoint = geom_line.interpolate(0.5, normalized=True)
        start = coords[0]
        end = coords[-1]
        dx = float(end[0]) - float(start[0])
        dy = float(end[1]) - float(start[1])
        length = (dx * dx + dy * dy) ** 0.5
        if length <= 0:
            unit = line.get("wallUnitVector") or (1.0, 0.0)
            dx, dy = float(unit[0]), float(unit[1])
            length = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / length, dy / length
        half_width = width / 2.0
        return [
            (midpoint.x - ux * half_width, midpoint.y - uy * half_width),
            (midpoint.x + ux * half_width, midpoint.y + uy * half_width),
        ]

    def _create_source_features(self):
        counters = {"wall": 0, "door": 0, "exit": 0, "window": 0, "virtual": 0, "room": 0, "other": 0}

        for line in self.authoring_lines:
            tipo = line.get("type")
            centerline = line.get("centerline") or []
            geom_line = line_from_coords(centerline)
            if geom_line is None:
                continue

            if is_wall_type(tipo):
                key, source_type = "wall", "wall_centerline"
            elif is_door_type(tipo):
                key, source_type = "door", "door_centerline"
            elif is_exit_type(tipo):
                key, source_type = "exit", "exit_centerline"
            elif tipo in WINDOW_TYPES:
                key, source_type = "window", "window_centerline"
            elif is_virtual_boundary_type(tipo):
                key, source_type = "virtual", "virtual_boundary_line"
            else:
                key, source_type = "other", "other"

            counters[key] += 1
            source_id = f"SF_{self.level_code}_{normalize_token(key)}_{counters[key]:03d}"
            attrs = {
                "originalName": line.get("name"),
                "originalType": tipo,
            }
            if line.get("thicknessM") is not None:
                attrs["thicknessM"] = line.get("thicknessM")
            if line.get("widthM") is not None:
                attrs["widthM"] = line.get("widthM")
            for key in ("hostWallName", "hostWallType", "hostWallThicknessM", "hostWallRef"):
                if line.get(key) is not None:
                    attrs[key] = line.get(key)

            self._add_source_feature(
                {
                    "id": source_id,
                    "featureType": "SourceFeature",
                    "sourceType": source_type,
                    "level": line.get("level") or self.level_id,
                    "geometry": line_geojson(geom_line),
                    "attributes": attrs,
                }
            )
            self.source_by_line_name[line.get("name")] = source_id

        for space in self.snapshot.get("spaceFootprints", []):
            name = space.get("name")
            if (space.get("level") or self.level_id) != self.level_id:
                continue
            if not name or self._space_is_transfer_or_virtual(space):
                continue
            poly = polygon_from_coords(space.get("footprint"))
            if poly is None:
                continue
            counters["room"] += 1
            source_id = f"SF_{self.level_code}_ROOM_{counters['room']:03d}"
            self._add_source_feature(
                {
                    "id": source_id,
                    "featureType": "SourceFeature",
                    "sourceType": "room_polygon",
                    "level": space.get("level") or self.level_id,
                    "geometry": polygon_geojson(poly),
                    "attributes": {
                        "originalName": name,
                        "originalType": space.get("authoringType") or "room_polygon",
                    },
                }
            )
            self.source_by_space_name[name] = source_id

    def _add_source_feature(self, source_feature):
        self.source_features.append(source_feature)
        self.source_by_id[source_feature["id"]] = source_feature

    def _space_is_transfer_or_virtual(self, space):
        name = space.get("name")
        authoring_type = space.get("authoringType")
        if not authoring_type and name in self.line_by_name:
            authoring_type = self.line_by_name[name].get("type")
        attrs = space.get("attributes") or {}
        lower_name = str(name or "").lower()
        return (
            is_transfer_authoring_type(authoring_type)
            or authoring_type in WINDOW_TYPES
            or is_non_solid_topology_type(authoring_type)
            or "puerta" in lower_name
            or "salida" in lower_name
            or "ventana" in lower_name
            or "window" in lower_name
            or "frontera" in lower_name
            or attrs.get("clase_indoor") in {"TransferSpace", "AnchorSpace"}
        )

    def _space_is_object(self, space):
        attrs = space.get("attributes") or {}
        markers = {
            attrs.get("clase_indoor"),
            attrs.get("navigationType"),
            attrs.get("navigationClass"),
            attrs.get("category"),
            attrs.get("categoria"),
        }
        lowered = {str(value).strip().lower() for value in markers if value is not None}
        return bool({"objectspace", "object", "column", "obstacle"} & lowered)

    def _create_object_spaces(self):
        object_polys = []
        index = 1
        for space in self.snapshot.get("spaceFootprints", []):
            if (space.get("level") or self.level_id) != self.level_id:
                continue
            if not self._space_is_object(space):
                continue
            poly = polygon_from_coords(space.get("footprint"))
            if poly is None:
                continue
            source_ref = self.source_by_space_name.get(space.get("name"))
            attrs = dict(space.get("attributes") or {})
            attrs["derivationStatus"] = "derived_from_object_footprint"
            cell_id = f"CS_{self.level_code}_OBJ_{index:03d}"
            index += 1
            self._add_cell(
                cell_id=cell_id,
                name=space.get("name"),
                polygon=poly,
                navigation_type="ObjectSpace",
                navigation_class="NonNavigableSpace",
                category=attrs.get("categoria") or attrs.get("category") or "Object",
                function=attrs.get("function") or attrs.get("funcion") or "Object",
                locomotion=[],
                source_refs=[source_ref] if source_ref else [],
                attributes=attrs,
            )
            object_polys.append(poly)
        self.object_union = union_polygons(object_polys)

    def _derive_wall_parts(self):
        openings = []
        raw_walls = []
        for line in self.authoring_lines:
            tipo = line.get("type")
            poly = self._line_footprint(line)
            if poly is None:
                continue
            if is_opening_type(tipo):
                openings.append(poly)
            elif is_solid_wall_type(tipo):
                centerline = line_from_coords(line.get("centerline"))
                if centerline is None:
                    continue
                raw_walls.append(
                    {
                        "index": len(raw_walls),
                        "line": line,
                        "centerline": centerline,
                        "polygon": poly,
                        "thickness": self._positive_float(line.get("thicknessM"), 0.1),
                    }
                )

        opening_union = union_polygons(openings)
        self.opening_union = opening_union
        junction_candidates = self._angle_aware_junction_polygons(raw_walls)
        raw_wall_union = union_polygons([wall["polygon"] for wall in raw_walls])
        raw_junction_union = clean_boolean_polygon(union_polygons(junction_candidates))
        self.solid_wall_union = clean_boolean_polygon(union_polygons([raw_wall_union, raw_junction_union]))

        junction_union = raw_junction_union
        if not opening_union.is_empty and not junction_union.is_empty:
            junction_union = clean_boolean_polygon(junction_union.difference(opening_union))
        wall_polys = []
        assigned_wall_polys = []
        if not junction_union.is_empty:
            assigned_wall_polys.append(junction_union)
        assigned_wall_union = union_polygons(assigned_wall_polys)

        junction_parts = iter_polygons(junction_union)
        for index, part in enumerate(junction_parts, start=1):
            contributing_lines = []
            for wall in raw_walls:
                try:
                    overlap_area = part.intersection(wall["polygon"]).area
                except Exception:
                    overlap_area = 0.0
                try:
                    centerline_distance = part.distance(wall["centerline"])
                except Exception:
                    centerline_distance = None
                if (
                    overlap_area > OVERLAP_AREA_TOLERANCE
                    or (
                        centerline_distance is not None
                        and centerline_distance <= wall["thickness"] / 2.0 + WALL_CONNECTION_TOLERANCE
                    )
                ):
                    contributing_lines.append(wall["line"])
            self.wall_parts.append(
                {
                    "category": "WallJunction",
                    "lines": contributing_lines,
                    "polygon": part,
                    "partIndex": index,
                    "partCount": len(junction_parts),
                }
            )
            wall_polys.append(part)

        for wall in raw_walls:
            line = wall["line"]
            wall_poly = wall["polygon"]
            try:
                derived = wall_poly
                if not opening_union.is_empty:
                    derived = clean_boolean_polygon(derived.difference(opening_union))
                if not junction_union.is_empty:
                    derived = clean_boolean_polygon(derived.difference(junction_union))
                if not assigned_wall_union.is_empty:
                    derived = clean_boolean_polygon(derived.difference(assigned_wall_union))
            except Exception:
                derived = wall_poly
            parts = iter_polygons(derived)
            accepted_parts = []
            for index, part in enumerate(parts, start=1):
                if part.area <= MIN_WALL_PART_AREA:
                    continue
                accepted_parts.append(part)
                self.wall_parts.append(
                    {
                        "category": "WallSegment",
                        "line": line,
                        "lines": [line],
                        "polygon": part,
                        "partIndex": index,
                        "partCount": len(parts),
                    }
                )
                wall_polys.append(part)
            if accepted_parts:
                assigned_wall_polys.extend(accepted_parts)
                assigned_wall_union = clean_boolean_polygon(union_polygons(assigned_wall_polys))
        self.wall_union = union_polygons(wall_polys)

    def _line_footprint(self, line):
        prepared = self.line_by_name.get(line.get("name"), line)
        poly = prepared.get("_footprint_poly")
        if poly is not None:
            return poly
        return footprint_from_centerline(prepared.get("centerline"), prepared.get("thicknessM") or 0.1)

    def _create_general_spaces(self):
        detected_spaces = [
            space
            for space in self.snapshot.get("detectedSpaces", [])
            if (space.get("level") or self.level_id) == self.level_id
        ]
        if detected_spaces:
            self._create_detected_general_spaces(detected_spaces)
            return

        index = 1
        for space in self.snapshot.get("spaceFootprints", []):
            if (space.get("level") or self.level_id) != self.level_id:
                continue
            if self._space_is_transfer_or_virtual(space) or self._space_is_object(space):
                continue
            source_ref = self.source_by_space_name.get(space.get("name"))
            original_poly = polygon_from_coords(space.get("footprint"))
            if original_poly is None:
                continue

            attrs = dict(space.get("attributes") or {})
            try:
                clipping_polys = []
                if self.wall_union is not None and not self.wall_union.is_empty:
                    clipping_polys.append(self.wall_union)
                if self.object_union is not None and not self.object_union.is_empty:
                    clipping_polys.append(self.object_union)
                if self.transfer_union is not None and not self.transfer_union.is_empty:
                    clipping_polys.append(self.transfer_union)
                clipping_union = union_polygons(clipping_polys)
                derived = original_poly.difference(clipping_union) if not clipping_union.is_empty else original_poly
                parts = iter_polygons(derived)
                if not parts:
                    raise ValueError("empty clipped geometry")
                derivation_attrs = {
                    "derivationStatus": "clipped_from_authoring_polygon",
                    "clippedAgainst": ["NonNavigableSpace", "ObjectSpace", "TransferSpace"],
                }
            except Exception:
                parts = [original_poly]
                derivation_attrs = {
                    "derivationStatus": "authoring_geometry_fallback",
                    "warning": "navigable_space_not_clipped",
                }

            if len(parts) > 1:
                derivation_attrs["splitFromAuthoringSpace"] = True

            for part_index, part in enumerate(parts, start=1):
                base_id = f"CS_{self.level_code}_ROOM_{index:03d}"
                cell_id = base_id if len(parts) == 1 else f"{base_id}_PART_{part_index:03d}"
                cell_attrs = dict(attrs)
                cell_attrs.update(derivation_attrs)
                if len(parts) > 1:
                    cell_attrs["partIndex"] = part_index

                self._add_cell(
                    cell_id=cell_id,
                    name=space.get("name") if len(parts) == 1 else f"{space.get('name')} part {part_index}",
                    polygon=part,
                    navigation_type="GeneralSpace",
                    navigation_class="NavigableSpace",
                    category=attrs.get("categoria") or attrs.get("category") or "Room",
                    function=attrs.get("function") or attrs.get("funcion") or "General",
                    locomotion=_normalize_locomotion(attrs.get("locomotion")),
                    source_refs=[source_ref] if source_ref else [],
                    attributes=cell_attrs,
                )
            index += 1

    def _create_detected_general_spaces(self, detected_spaces):
        clipping_union, clipping_labels = self._detected_general_space_clipping()
        for index, space in enumerate(detected_spaces, start=1):
            poly = self._polygon_from_detected_space(space)
            if poly is None:
                continue
            attrs = dict(space.get("attributes") or {})
            base_id = space.get("id") or f"CS_{self.level_code}_ROOM_{index:03d}"
            name = attrs.get("name") or attrs.get("cellSpaceName") or base_id
            derivation_attrs = {
                "derivationStatus": "automatic_space_detection",
                "sourceFaceId": space.get("sourceFaceId"),
            }
            parts = [poly]
            if not clipping_union.is_empty:
                try:
                    clipped = clean_boolean_polygon(poly.difference(clipping_union))
                    clipped_parts = iter_polygons(clipped)
                    if clipped_parts:
                        parts = clipped_parts
                        derivation_attrs["clippedAgainst"] = clipping_labels
                        if len(parts) > 1:
                            derivation_attrs["splitFromDetectedSpace"] = True
                except Exception:
                    derivation_attrs["warning"] = "detected_space_not_clipped"

            for part_index, part in enumerate(parts, start=1):
                cell_id = base_id if len(parts) == 1 else f"{base_id}_PART_{part_index:03d}"
                cell_attrs = dict(attrs)
                cell_attrs.update(derivation_attrs)
                if len(parts) > 1:
                    cell_attrs["partIndex"] = part_index
                self._add_cell(
                    cell_id=cell_id,
                    name=name if len(parts) == 1 else f"{name} part {part_index}",
                    polygon=part,
                    navigation_type="GeneralSpace",
                    navigation_class="NavigableSpace",
                    category=attrs.get("categoria") or attrs.get("category") or "Room",
                    function=attrs.get("function") or attrs.get("funcion") or "General",
                    locomotion=_normalize_locomotion(attrs.get("locomotion")),
                    source_refs=[],
                    attributes=cell_attrs,
                )

    def _detected_general_space_clipping(self):
        clipping_polys = []
        clipping_labels = []

        def add_clipping(geom, label):
            if geom is None or geom.is_empty:
                return
            clipping_polys.append(geom)
            _unique_append(clipping_labels, label)

        add_clipping(self.wall_union, "NonNavigableSpace")
        add_clipping(self.object_union, "ObjectSpace")
        transfer_polys = self._transfer_spaces_that_clip_general_spaces()
        if transfer_polys:
            clipping_polys.extend(transfer_polys)
            _unique_append(clipping_labels, "TransferSpace")
        return union_polygons(clipping_polys), clipping_labels

    def _transfer_spaces_that_clip_general_spaces(self):
        result = []
        for cell in self.cells:
            if cell["navigationType"] != "TransferSpace":
                continue
            category = self._cell_category(cell)
            if category in {"Stair", "Ramp", "Elevator"} or cell["function"] == "VerticalConnectorEndpoint":
                result.append(cell["polygon"])
            elif category in {"Door", "Exit", "Window"} and self._opening_transfer_clips_general_space(cell):
                result.append(cell["polygon"])
        return result

    def _opening_transfer_clips_general_space(self, cell):
        attrs = cell["json"].get("attributes", {})
        if attrs.get("hostWallName") or attrs.get("hostWallRef") or attrs.get("hostWallType"):
            return True
        if self.wall_union is None or self.wall_union.is_empty:
            return False
        try:
            return cell["polygon"].buffer(BOUNDARY_CONTACT_TOLERANCE).intersects(self.wall_union)
        except Exception:
            return False

    def _polygon_from_detected_space(self, space):
        rings = space.get("polygon") or []
        if not rings:
            return None
        try:
            poly = Polygon(rings[0], rings[1:])
            if not poly.is_valid:
                poly = poly.buffer(0)
        except Exception:
            return None
        if poly.is_empty or poly.area <= MIN_WALL_PART_AREA:
            return None
        return poly

    def _create_transfer_spaces(self):
        door_index = 1
        exit_index = 1
        window_index = 1
        transfer_polys = []
        for line in self.authoring_lines:
            tipo = line.get("type")
            if not is_opening_type(tipo):
                continue
            poly = self._line_footprint(line)
            if poly is None:
                continue
            source_ref = self.source_by_line_name.get(line.get("name"))
            attrs = dict(line.get("attributes") or {})
            for key in ("hostWallName", "hostWallType", "hostWallThicknessM", "hostWallRef", "widthM", "thicknessM"):
                if line.get(key) is not None:
                    attrs[key] = line.get(key)
            if is_exit_type(tipo):
                cell_id = f"CS_{self.level_code}_EXIT_{exit_index:03d}"
                exit_index += 1
                function = "AnchorSpace"
                category = "Exit"
            elif tipo in WINDOW_TYPES:
                cell_id = f"CS_{self.level_code}_WINDOW_{window_index:03d}"
                window_index += 1
                function = "ConnectionSpace"
                category = "Window"
                attrs.setdefault("windowType", "fixed")
                attrs.setdefault("defaultTraversable", False)
                attrs.setdefault("scenarioControllable", True)
                attrs.setdefault("sillHeightM", 0.9)
            else:
                cell_id = f"CS_{self.level_code}_DOOR_{door_index:03d}"
                door_index += 1
                function = "ConnectionSpace"
                category = "Door"
                attrs.setdefault("defaultTraversable", True)

            attrs.update(
                {
                    "originalType": tipo,
                    "derivationStatus": "derived_from_centerline_footprint",
                }
            )
            self._add_cell(
                cell_id=cell_id,
                name=line.get("name"),
                polygon=poly,
                navigation_type="TransferSpace",
                navigation_class="NavigableSpace",
                category=category,
                function=function,
                locomotion=_normalize_locomotion(attrs.get("locomotion")),
                source_refs=[source_ref] if source_ref else [],
                attributes=attrs,
                width_m=line.get("widthM"),
            )
            transfer_polys.append(poly)
        self.transfer_union = union_polygons(transfer_polys)

    def _create_connector_spaces(self):
        connector_transfer_polys = []
        coverage_polys = []
        endpoint_index = 1
        coverage_index = 1
        level_endpoint_polys = []
        for connector in self.snapshot.get("verticalConnectors", []):
            for endpoint in connector.get("endpoints", []):
                if (endpoint.get("level") or endpoint.get("level_id") or endpoint.get("levelId")) != self.level_id:
                    continue
                poly = polygon_from_coords(endpoint.get("footprint"))
                if poly is not None:
                    level_endpoint_polys.append(poly)
        level_endpoint_union = union_polygons(level_endpoint_polys)
        for connector in self.snapshot.get("verticalConnectors", []):
            connector_type = connector.get("connectorType") or "Stair"
            scope = connector.get("scope") or "same_level"
            locomotion = _normalize_locomotion(connector.get("locomotionTypes"))
            for endpoint in connector.get("endpoints", []):
                if (endpoint.get("level") or endpoint.get("level_id") or endpoint.get("levelId")) != self.level_id:
                    continue
                poly = polygon_from_coords(endpoint.get("footprint"))
                if poly is None:
                    continue
                endpoint_token = normalize_token(endpoint.get("id") or f"ENDPOINT_{endpoint_index:03d}")
                cell_id = f"CS_{self.level_code}_{endpoint_token}"
                attrs = dict(endpoint.get("attributes") or {})
                attrs.update(
                    {
                        "connectorId": connector.get("id"),
                        "connectorType": connector_type,
                        "scope": scope,
                        "entrySide": endpoint.get("entrySide"),
                        "exitSide": endpoint.get("exitSide"),
                        "openSides": endpoint.get("openSides") or [],
                        "directionality": connector.get("directionality", "bidirectional"),
                    }
                )
                if connector_type == "Stair":
                    attrs.setdefault("requiresSteps", True)
                    attrs.setdefault("wheelchairAccessible", False)
                elif connector_type == "Ramp":
                    attrs.setdefault("requiresSteps", False)
                    attrs.setdefault("wheelchairAccessible", True)
                    attrs.setdefault("slope", (connector.get("attributes") or {}).get("slope", 0.08))
                elif connector_type == "Elevator":
                    attrs.setdefault("requiresSteps", False)
                    attrs.setdefault("wheelchairAccessible", True)
                self._add_cell(
                    cell_id=cell_id,
                    name=endpoint.get("id") or cell_id,
                    polygon=poly,
                    navigation_type="TransferSpace",
                    navigation_class="NavigableSpace",
                    category=connector_type,
                    function="VerticalConnectorEndpoint",
                    locomotion=locomotion,
                    source_refs=[],
                    attributes=attrs,
                )
                self.connector_endpoint_cells[endpoint.get("id")] = cell_id
                connector_transfer_polys.append(poly)
                endpoint_index += 1

                for coverage in attrs.get("sideCoverages", []):
                    coverage_poly = polygon_from_coords(coverage)
                    if coverage_poly is None:
                        continue
                    try:
                        if self.wall_union is not None and not self.wall_union.is_empty:
                            coverage_poly = clean_boolean_polygon(coverage_poly.difference(self.wall_union))
                        if not level_endpoint_union.is_empty:
                            coverage_poly = clean_boolean_polygon(coverage_poly.difference(level_endpoint_union))
                        existing_coverage_union = union_polygons(coverage_polys)
                        if not existing_coverage_union.is_empty:
                            coverage_poly = clean_boolean_polygon(coverage_poly.difference(existing_coverage_union))
                    except Exception:
                        pass
                    if coverage_poly is None or coverage_poly.is_empty:
                        continue
                    for coverage_part in iter_polygons(coverage_poly):
                        coverage_id = f"CS_{self.level_code}_CONNCOVER_{coverage_index:03d}"
                        self._add_cell(
                            cell_id=coverage_id,
                            name=f"{connector.get('id') or 'connector'} side coverage {coverage_index}",
                            polygon=coverage_part,
                            navigation_type="NonNavigableSpace",
                            navigation_class="NonNavigableSpace",
                            category="ConnectorSideCoverage",
                            function="VerticalConnectorCoverage",
                            locomotion=[],
                            source_refs=[],
                            attributes={
                                "connectorId": connector.get("id"),
                                "connectorType": connector_type,
                                "derivationStatus": "connector_side_coverage",
                            },
                        )
                        coverage_polys.append(coverage_part)
                        coverage_index += 1

        if connector_transfer_polys:
            unions = [self.transfer_union, union_polygons(connector_transfer_polys)]
            self.transfer_union = union_polygons(unions)
        if coverage_polys:
            unions = [self.object_union, union_polygons(coverage_polys)]
            self.object_union = union_polygons(unions)

    def _create_wall_spaces(self):
        wall_indices = {}
        next_wall_index = 1
        junction_index = 1
        for wall in self.wall_parts:
            category = wall.get("category") or "WallSegment"
            lines = wall.get("lines") or ([wall["line"]] if wall.get("line") else [])
            source_refs = self._source_refs_for_lines(lines)
            source_names = [line.get("name") for line in lines if line.get("name")]

            if category == "WallJunction":
                base_id = f"CS_{self.level_code}_WALLJUNC_{junction_index:03d}"
                cell_id = base_id
                junction_index += 1
                name = "Wall junction " + " + ".join(source_names) if source_names else base_id
            else:
                line = lines[0] if lines else {}
                wall_key = line.get("name") or id(line)
                if wall_key not in wall_indices:
                    wall_indices[wall_key] = next_wall_index
                    next_wall_index += 1
                wall_index = wall_indices[wall_key]
                base_id = f"CS_{self.level_code}_WALLSEG_{wall_index:03d}"
                cell_id = base_id if wall["partCount"] == 1 else f"{base_id}_PART_{wall['partIndex']:03d}"
                name = line.get("name") if wall["partCount"] == 1 else f"{line.get('name')} part {wall['partIndex']}"

            attrs = {
                "sourceWallNames": source_names,
                "sourceWallTypes": [line.get("type") for line in lines if line.get("type")],
                "derivationStatus": "wall_mass_partition",
            }
            if category == "WallSegment" and lines:
                attrs["originalName"] = lines[0].get("name")
                attrs["originalType"] = lines[0].get("type")
                attrs["thicknessM"] = lines[0].get("thicknessM")
                if lines[0].get("_wall_centerline_extension"):
                    attrs["centerlineExtension"] = lines[0]["_wall_centerline_extension"]
            if wall["partCount"] > 1:
                attrs["partIndex"] = wall["partIndex"]
                attrs["partCount"] = wall["partCount"]

            self._add_cell(
                cell_id=cell_id,
                name=name,
                polygon=wall["polygon"],
                navigation_type="NonNavigableSpace",
                navigation_class="NonNavigableSpace",
                category=category,
                function="Wall",
                locomotion=[],
                source_refs=source_refs,
                attributes=attrs,
            )

    def _source_refs_for_lines(self, lines):
        refs = []
        for line in lines:
            source_ref = self.source_by_line_name.get(line.get("name"))
            _unique_append(refs, source_ref)
        return refs

    def _add_cell(
        self,
        cell_id,
        name,
        polygon,
        navigation_type,
        navigation_class,
        category,
        function,
        locomotion,
        source_refs,
        attributes,
        width_m=None,
    ):
        node_id = node_id_for_cell(cell_id)
        cell = {
            "id": cell_id,
            "featureType": "CellSpace",
            "cellSpaceName": str(name or cell_id),
            "level": self.level_id,
            "poi": False,
            "duality": self._ref(self.dual_id, node_id),
            "cellSpaceGeom": {"geometry2D": polygon_geojson(polygon)},
            "boundedBy": [],
            "navigationType": navigation_type,
            "navigationClass": navigation_class,
            "category": str(category or "Unclassified"),
            "function": str(function or "Unclassified"),
            "sourceFeatureRefs": [source for source in source_refs if source],
            "attributes": attributes or {},
        }
        if locomotion:
            cell["locomotionTypes"] = locomotion
        record = {
            "id": cell_id,
            "nodeId": node_id,
            "json": cell,
            "polygon": polygon,
            "navigationType": navigation_type,
            "navigationClass": navigation_class,
            "category": category,
            "function": function,
            "sourceRefs": cell["sourceFeatureRefs"],
            "locomotionTypes": locomotion,
            "widthM": width_m,
        }
        self.cells.append(record)
        for source_ref in record["sourceRefs"]:
            self._add_source_cell_ref(source_ref, cell_id)

    def _add_source_cell_ref(self, source_ref, cell_id):
        source = self.source_by_id.get(source_ref)
        if source is None:
            return
        values = source.setdefault("derivedCellSpaceRefs", [])
        _unique_append(values, cell_id)

    def _add_source_boundary_ref(self, source_ref, boundary_id):
        source = self.source_by_id.get(source_ref)
        if source is None:
            return
        values = source.setdefault("derivedBoundaryRefs", [])
        _unique_append(values, boundary_id)

    def _validate_cell_overlaps(self):
        for i, cell_a in enumerate(self.cells):
            for cell_b in self.cells[i + 1 :]:
                try:
                    area = cell_a["polygon"].intersection(cell_b["polygon"]).area
                except Exception:
                    continue
                if area <= OVERLAP_AREA_TOLERANCE:
                    continue

                warning = {
                    "cellRefs": [cell_a["id"], cell_b["id"]],
                    "navigationTypes": [cell_a["navigationType"], cell_b["navigationType"]],
                    "intersectionAreaM2": round(float(area), 9),
                }
                self.overlap_warnings.append(warning)
                for cell, other in ((cell_a, cell_b), (cell_b, cell_a)):
                    attrs = cell["json"].setdefault("attributes", {})
                    warnings = attrs.setdefault("cellSpaceOverlapWarnings", [])
                    if len(warnings) < 20:
                        warnings.append(
                            {
                                "otherCellRef": other["id"],
                                "otherNavigationType": other["navigationType"],
                                "intersectionAreaM2": warning["intersectionAreaM2"],
                            }
                        )
                print(
                    "WARNING indoor_model CellSpace overlap: "
                    f"{cell_a['id']}({cell_a['navigationType']}) / "
                    f"{cell_b['id']}({cell_b['navigationType']}) "
                    f"area={warning['intersectionAreaM2']}"
                )

    def _create_boundaries(self):
        used_ids = set()
        for i, cell_a in enumerate(self.cells):
            for cell_b in self.cells[i + 1 :]:
                boundary_role = self._boundary_role(cell_a, cell_b)
                if boundary_role is None:
                    continue
                tolerance = BOUNDARY_CONTACT_TOLERANCE if boundary_role.startswith("general_transfer_contact") else 0.0
                line = contact_line(cell_a["polygon"], cell_b["polygon"], min_length=0.05, tolerance=tolerance)
                if line is None:
                    continue

                boundary_id = self._boundary_id(cell_a["id"], cell_b["id"], used_ids)
                traversable = boundary_role == "general_transfer_contact"
                transfer_cell = self._transfer_cell(cell_a, cell_b) if self._is_general_transfer_pair(cell_a, cell_b) else None
                is_anchor = traversable and transfer_cell is not None and transfer_cell.get("function") == "AnchorSpace"
                boundary_type = "NavigableBoundary" if traversable else "NonNavigableBoundary"
                relationship_type = "connectivity" if traversable else "adjacency"
                edge_id = (
                    edge_id_for_boundary(boundary_id)
                    if self._should_export_edge(cell_a, cell_b, traversable)
                    else None
                )
                source_refs = []
                for source_ref in cell_a["sourceRefs"] + cell_b["sourceRefs"]:
                    _unique_append(source_refs, source_ref)

                boundary = {
                    "id": boundary_id,
                    "featureType": "CellBoundary",
                    "isVirtual": False,
                    "cellBoundaryGeom": {"geometry2D": line_geojson(line)},
                    "navigationBoundaryType": boundary_type,
                    "traversable": traversable,
                    "cellRefs": [cell_a["id"], cell_b["id"]],
                    "sourceFeatureRefs": source_refs,
                    "attributes": {
                        "derivationStatus": "geometry_contact",
                        "boundaryRole": boundary_role,
                        "relationshipType": relationship_type,
                    },
                }
                if edge_id is not None:
                    boundary["duality"] = self._ref(self.dual_id, edge_id)
                if traversable:
                    boundary["navigableBoundaryFunction"] = "AnchorBoundary" if is_anchor else "ConnectionBoundary"

                self.boundaries.append(
                    {
                        "json": boundary,
                        "edgeId": edge_id,
                        "cellA": cell_a,
                        "cellB": cell_b,
                        "traversable": traversable,
                        "isAnchor": is_anchor,
                    }
                )
                for source_ref in source_refs:
                    self._add_source_boundary_ref(source_ref, boundary_id)
        self._create_same_level_connector_boundaries(used_ids)
        self._create_virtual_boundaries(used_ids)
        self._create_exterior_boundaries(used_ids)

    def _create_exterior_boundaries(self, used_ids):
        for cell in self.cells:
            boundary_role = self._exterior_boundary_role(cell)
            if boundary_role is None:
                continue

            traversable = boundary_role == "exterior_anchor"
            boundary_type = "NavigableBoundary" if traversable else "NonNavigableBoundary"
            relationship_type = "connectivity" if traversable else "adjacency"
            for line in self._exposed_boundary_lines(cell):
                boundary_id = self._exterior_boundary_id(cell["id"], boundary_role, used_ids)
                source_refs = list(cell["sourceRefs"])
                boundary = {
                    "id": boundary_id,
                    "featureType": "CellBoundary",
                    "isVirtual": False,
                    "cellBoundaryGeom": {"geometry2D": line_geojson(line)},
                    "navigationBoundaryType": boundary_type,
                    "traversable": traversable,
                    "cellRefs": [cell["id"]],
                    "sourceFeatureRefs": source_refs,
                    "attributes": {
                        "derivationStatus": "exposed_exterior_contact",
                        "boundaryRole": boundary_role,
                        "relationshipType": relationship_type,
                    },
                }
                if traversable:
                    boundary["navigableBoundaryFunction"] = "AnchorBoundary"

                self.boundaries.append(
                    {
                        "json": boundary,
                        "edgeId": None,
                        "cellA": cell,
                        "cellB": None,
                        "traversable": traversable,
                        "isAnchor": traversable,
                    }
                )
                for source_ref in source_refs:
                    self._add_source_boundary_ref(source_ref, boundary_id)

    def _create_virtual_boundaries(self, used_ids):
        for record in self.snapshot.get("virtualBoundaries", []):
            if (record.get("level") or self.level_id) != self.level_id:
                continue
            line = line_from_coords(record.get("line"))
            if line is None:
                continue
            adjacent = self._cells_adjacent_to_virtual_line(line)
            if len(adjacent) < 2:
                continue
            cell_a, cell_b = adjacent[0], adjacent[1]
            base = f"CB_{self.level_code}_VIRTUAL_{normalize_token(record.get('id') or 'VB')}"
            boundary_id = base
            suffix = 2
            while boundary_id in used_ids:
                boundary_id = f"{base}_{suffix:02d}"
                suffix += 1
            used_ids.add(boundary_id)
            edge_id = edge_id_for_boundary(boundary_id)
            boundary = {
                "id": boundary_id,
                "featureType": "CellBoundary",
                "isVirtual": True,
                "duality": self._ref(self.dual_id, edge_id),
                "cellBoundaryGeom": {"geometry2D": line_geojson(line)},
                "navigationBoundaryType": "NavigableBoundary",
                "navigableBoundaryFunction": "ConnectionBoundary",
                "traversable": bool(record.get("traversable", True)),
                "cellRefs": [cell_a["id"], cell_b["id"]],
                "sourceFeatureRefs": [],
                "attributes": {
                    "derivationStatus": "manual_virtual_boundary"
                    if not record.get("generatedAutomatically")
                    else "automatic_virtual_boundary",
                    "boundaryRole": "virtual_general_general_contact",
                    "relationshipType": "connectivity",
                    "virtualBoundaryRef": record.get("id"),
                    "generatedAutomatically": bool(record.get("generatedAutomatically")),
                    "generationReason": record.get("generationReason"),
                },
            }
            self.boundaries.append(
                {
                    "json": boundary,
                    "edgeId": edge_id,
                    "cellA": cell_a,
                    "cellB": cell_b,
                    "traversable": boundary["traversable"],
                    "isAnchor": False,
                    "virtualBoundaryRef": record.get("id"),
                }
            )

    def _create_same_level_connector_boundaries(self, used_ids):
        cell_by_id = {cell["id"]: cell for cell in self.cells}
        for connector in self.snapshot.get("verticalConnectors", []):
            if (connector.get("scope") or "same_level") != "same_level":
                continue
            endpoints = [
                endpoint
                for endpoint in connector.get("endpoints", [])
                if (endpoint.get("level") or endpoint.get("level_id") or endpoint.get("levelId")) == self.level_id
            ]
            if len(endpoints) < 2:
                continue
            endpoint_a, endpoint_b = endpoints[0], endpoints[-1]
            cell_a = cell_by_id.get(self.connector_endpoint_cells.get(endpoint_a.get("id")))
            cell_b = cell_by_id.get(self.connector_endpoint_cells.get(endpoint_b.get("id")))
            if not cell_a or not cell_b or cell_a["id"] == cell_b["id"]:
                continue
            line = contact_line(cell_a["polygon"], cell_b["polygon"], min_length=0.05, tolerance=BOUNDARY_CONTACT_TOLERANCE)
            if line is None:
                continue
            token = normalize_token(connector.get("id") or "CONNECTOR")
            boundary_id = f"CB_{self.level_code}_VERT_{token}"
            suffix = 2
            while boundary_id in used_ids:
                boundary_id = f"CB_{self.level_code}_VERT_{token}_{suffix:02d}"
                suffix += 1
            used_ids.add(boundary_id)
            edge_id = f"E_{self.level_code}_VERT_{token}"
            boundary = {
                "id": boundary_id,
                "featureType": "CellBoundary",
                "isVirtual": False,
                "duality": self._ref(self.dual_id, edge_id),
                "cellBoundaryGeom": {"geometry2D": line_geojson(line)},
                "navigationBoundaryType": "NavigableBoundary",
                "navigableBoundaryFunction": "ConnectionBoundary",
                "traversable": True,
                "cellRefs": [cell_a["id"], cell_b["id"]],
                "sourceFeatureRefs": [],
                "attributes": {
                    "derivationStatus": "same_level_connector_internal_boundary",
                    "boundaryRole": "same_level_connector_internal_contact",
                    "relationshipType": "vertical_connectivity",
                    "connectorId": connector.get("id"),
                    "connectorType": connector.get("connectorType"),
                    "scope": connector.get("scope"),
                    "locomotionTypes": _normalize_locomotion(connector.get("locomotionTypes")),
                },
            }
            self.boundaries.append(
                {
                    "json": boundary,
                    "edgeId": edge_id,
                    "cellA": cell_a,
                    "cellB": cell_b,
                    "traversable": True,
                    "isAnchor": False,
                }
            )
            self.same_level_connector_boundary_by_connector[connector.get("id")] = boundary_id

    def _cells_adjacent_to_virtual_line(self, line):
        ranked = []
        for cell in self.cells:
            if cell["navigationType"] != "GeneralSpace":
                continue
            try:
                shared = cell["polygon"].boundary.intersection(line.buffer(BOUNDARY_CONTACT_TOLERANCE, cap_style=2))
                length = sum(part.length for part in extract_lines(shared))
                if length <= 0:
                    length = cell["polygon"].intersection(line.buffer(BOUNDARY_CONTACT_TOLERANCE, cap_style=2)).area
            except Exception:
                length = 0.0
            if length > 0:
                ranked.append((length, cell))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [cell for _, cell in ranked[:2]]

    def _exterior_boundary_role(self, cell):
        if cell["navigationType"] == "TransferSpace" and cell["function"] == "AnchorSpace":
            return "exterior_anchor"
        if cell["navigationType"] != "NonNavigableSpace" or cell["function"] != "Wall":
            return None
        source_wall_types = cell["json"].get("attributes", {}).get("sourceWallTypes") or []
        return "outer_shell" if "muro_exterior" in source_wall_types else None

    def _exposed_boundary_lines(self, cell):
        try:
            exposed = cell["polygon"].boundary
        except Exception:
            return []

        for other in self.cells:
            if other is cell:
                continue
            try:
                shared = cell["polygon"].boundary.intersection(other["polygon"].buffer(BOUNDARY_CONTACT_TOLERANCE))
                if not shared.is_empty:
                    exposed = exposed.difference(shared.buffer(BOUNDARY_CONTACT_TOLERANCE, cap_style=2))
            except Exception:
                continue

        return [
            line
            for line in extract_lines(exposed)
            if line.length >= EXTERIOR_BOUNDARY_MIN_LENGTH
        ]

    def _exterior_boundary_id(self, cell_id, boundary_role, used_ids):
        role_token = "ANCHOR" if boundary_role == "exterior_anchor" else "OUTER"
        base = f"CB_{self.level_code}_{role_token}_{compact_cell_token(cell_id)}"
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}_{suffix:02d}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    def _should_boundary_be_created(self, cell_a, cell_b):
        return self._boundary_role(cell_a, cell_b) is not None

    def _should_export_edge(self, cell_a, cell_b, traversable):
        if cell_b is None:
            return False
        if self.edge_mode == EDGE_MODE_ALL_ADJACENCY:
            return True
        if self._is_wall_junction_cell(cell_a) or self._is_wall_junction_cell(cell_b):
            return False

        types = {cell_a["navigationType"], cell_b["navigationType"]}
        if traversable:
            return types == {"GeneralSpace", "TransferSpace"} or types == {"GeneralSpace"}
        return False

    def _boundary_role(self, cell_a, cell_b):
        types = {cell_a["navigationType"], cell_b["navigationType"]}
        if types == {"GeneralSpace", "TransferSpace"}:
            transfer = self._transfer_cell(cell_a, cell_b)
            if transfer["json"].get("attributes", {}).get("defaultTraversable") is False:
                return "general_transfer_contact_blocked"
            return "general_transfer_contact"
        if "GeneralSpace" in types and any(self._is_non_navigable_cell(cell) for cell in (cell_a, cell_b)):
            return "general_non_navigable_contact"
        if "TransferSpace" in types and any(
            cell["navigationType"] == "NonNavigableSpace" for cell in (cell_a, cell_b)
        ):
            return "transfer_non_navigable_contact"
        if (
            EXPORT_WALL_WALL_BOUNDARIES
            and types == {"NonNavigableSpace"}
            and self._is_wall_cell(cell_a)
            and self._is_wall_cell(cell_b)
        ):
            return "internal_wall_contact"
        return None

    def _is_non_navigable_cell(self, cell):
        return cell["navigationClass"] == "NonNavigableSpace" or cell["navigationType"] in {
            "NonNavigableSpace",
            "ObjectSpace",
        }

    def _is_wall_cell(self, cell):
        return cell["function"] == "Wall" and cell["json"].get("category") in {"WallSegment", "WallJunction"}

    def _cell_category(self, cell):
        return str(cell.get("category") or cell["json"].get("category") or "")

    def _is_wall_segment_cell(self, cell):
        return cell["function"] == "Wall" and self._cell_category(cell) == "WallSegment"

    def _is_wall_junction_cell(self, cell):
        return cell["function"] == "Wall" and self._cell_category(cell) == "WallJunction"

    def _is_general_transfer_pair(self, cell_a, cell_b):
        types = {cell_a["navigationType"], cell_b["navigationType"]}
        return types == {"GeneralSpace", "TransferSpace"}

    def _transfer_cell(self, cell_a, cell_b):
        return cell_a if cell_a["navigationType"] == "TransferSpace" else cell_b

    def _boundary_id(self, cell_a_id, cell_b_id, used_ids):
        token_a = compact_cell_token(cell_a_id)
        token_b = compact_cell_token(cell_b_id)
        base = f"CB_{self.level_code}_{token_a}_{token_b}"
        candidate = base
        suffix = 2
        while candidate in used_ids:
            candidate = f"{base}_{suffix:02d}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    def _create_dual_space(self):
        cell_by_id = {cell["id"]: cell for cell in self.cells}
        for cell in self.cells:
            point = node_point_for_polygon(cell["polygon"])
            node_ref = self._ref(self.dual_id, cell["nodeId"])
            self.node_connects[cell["nodeId"]] = []
            self.nodes.append(
                {
                    "id": cell["nodeId"],
                    "featureType": "Node",
                    "duality": self._ref(self.primal_id, cell["id"]),
                    "geometry": point_geojson(point),
                    "connects": self.node_connects[cell["nodeId"]],
                    "attributes": {
                        "navigationType": cell["navigationType"],
                    },
                }
            )
            cell["nodeRef"] = node_ref

        for boundary in self.boundaries:
            if boundary.get("cellB") is None or boundary.get("edgeId") is None:
                continue
            cell_a = boundary["cellA"]
            cell_b = boundary["cellB"]
            edge_id = boundary["edgeId"]
            edge_ref = self._ref(self.dual_id, edge_id)
            _unique_append(self.node_connects[cell_a["nodeId"]], edge_ref)
            _unique_append(self.node_connects[cell_b["nodeId"]], edge_ref)
            node_a = node_point_for_polygon(cell_a["polygon"])
            node_b = node_point_for_polygon(cell_b["polygon"])
            transfer = self._transfer_cell(cell_a, cell_b) if boundary["traversable"] and self._is_general_transfer_pair(cell_a, cell_b) else None
            distance = node_a.distance(node_b)
            relationship_type = boundary["json"].get("attributes", {}).get("relationshipType")
            if not relationship_type:
                relationship_type = "connectivity" if boundary["traversable"] else "adjacency"

            edge = {
                "id": edge_id,
                "featureType": "Edge",
                "duality": self._ref(self.primal_id, boundary["json"]["id"]),
                "weight": round(float(distance if distance > 0 else 1.0), 6),
                "geometry": line_geojson(line_from_coords([(node_a.x, node_a.y), (node_b.x, node_b.y)])),
                "connects": [
                    self._ref(self.dual_id, cell_a["nodeId"]),
                    self._ref(self.dual_id, cell_b["nodeId"]),
                ],
                "relationshipType": relationship_type,
                "traversable": boundary["traversable"],
                "boundaryRef": boundary["json"]["id"],
                "attributes": {
                    "boundaryType": boundary["json"]["navigationBoundaryType"],
                    "boundaryRole": boundary["json"].get("attributes", {}).get("boundaryRole"),
                    "edgeMode": self.edge_mode,
                },
            }
            if self.edge_mode == EDGE_MODE_ALL_ADJACENCY and not boundary["traversable"]:
                edge["attributes"]["debugOnly"] = True
            if (
                self.edge_mode == EDGE_MODE_NAVIGATION
                and not boundary["traversable"]
                and (self._is_wall_segment_cell(cell_a) or self._is_wall_segment_cell(cell_b))
            ):
                edge["attributes"]["wallAdjacency"] = True
                edge["attributes"]["wallBreakCandidate"] = True
            if transfer is not None:
                edge["transferSpaceRef"] = transfer["id"]
                edge["locomotionTypes"] = transfer.get("locomotionTypes") or ["Walking", "Rolling"]
                if transfer.get("widthM") is not None:
                    width = float(transfer["widthM"])
                    edge["widthM"] = width
                    edge["capacityPersons"] = max(1.0, round(width / 0.6, 2))
                edge["attributes"]["transferSpaceRef"] = transfer["id"]
                if edge.get("widthM") is not None:
                    edge["attributes"]["widthM"] = edge["widthM"]
            if boundary.get("virtualBoundaryRef"):
                edge["attributes"]["virtualBoundaryRef"] = boundary["virtualBoundaryRef"]
                edge["attributes"]["sourceBoundaryType"] = "VirtualBoundary"
            if relationship_type == "vertical_connectivity":
                boundary_attrs = boundary["json"].get("attributes", {})
                edge["locomotionTypes"] = boundary_attrs.get("locomotionTypes") or ["Walking"]
                for key in ("connectorId", "connectorType", "scope"):
                    if boundary_attrs.get(key) is not None:
                        edge["attributes"][key] = boundary_attrs[key]

            self.edges.append(edge)

        self._create_same_level_connector_edges()

        for cell in cell_by_id.values():
            cell["json"]["duality"] = self._ref(self.dual_id, cell["nodeId"])

    def _create_same_level_connector_edges(self):
        for connector in self.snapshot.get("verticalConnectors", []):
            if self.same_level_connector_boundary_by_connector.get(connector.get("id")):
                continue
            endpoints = [
                endpoint
                for endpoint in connector.get("endpoints", [])
                if (endpoint.get("level") or endpoint.get("level_id") or endpoint.get("levelId")) == self.level_id
            ]
            if len(endpoints) < 2:
                continue
            endpoint_a, endpoint_b = endpoints[0], endpoints[-1]
            cell_a_id = self.connector_endpoint_cells.get(endpoint_a.get("id"))
            cell_b_id = self.connector_endpoint_cells.get(endpoint_b.get("id"))
            if not cell_a_id or not cell_b_id or cell_a_id == cell_b_id:
                continue
            cell_by_id = {cell["id"]: cell for cell in self.cells}
            cell_a = cell_by_id.get(cell_a_id)
            cell_b = cell_by_id.get(cell_b_id)
            if not cell_a or not cell_b:
                continue
            node_a = node_point_for_polygon(cell_a["polygon"])
            node_b = node_point_for_polygon(cell_b["polygon"])
            edge_id = f"E_{self.level_code}_VERT_{normalize_token(connector.get('id') or 'CONNECTOR')}"
            edge_ref = self._ref(self.dual_id, edge_id)
            _unique_append(self.node_connects[cell_a["nodeId"]], edge_ref)
            _unique_append(self.node_connects[cell_b["nodeId"]], edge_ref)
            self.edges.append(
                {
                    "id": edge_id,
                    "featureType": "Edge",
                    "weight": round(float(node_a.distance(node_b) or 1.0), 6),
                    "geometry": line_geojson(line_from_coords([(node_a.x, node_a.y), (node_b.x, node_b.y)])),
                    "connects": [
                        self._ref(self.dual_id, cell_a["nodeId"]),
                        self._ref(self.dual_id, cell_b["nodeId"]),
                    ],
                    "relationshipType": "vertical_connectivity",
                    "traversable": True,
                    "locomotionTypes": _normalize_locomotion(connector.get("locomotionTypes")),
                    "attributes": {
                        "connectorId": connector.get("id"),
                        "connectorType": connector.get("connectorType"),
                        "scope": connector.get("scope"),
                    },
                }
            )

    def _sync_cell_boundary_refs(self):
        cell_by_id = {cell["id"]: cell for cell in self.cells}
        for boundary in self.boundaries:
            boundary_ref = self._ref(self.primal_id, boundary["json"]["id"])
            for cell_id in boundary["json"].get("cellRefs", []):
                cell = cell_by_id.get(cell_id)
                if cell:
                    _unique_append(cell["json"]["boundedBy"], boundary_ref)

    def _root_document(self):
        model_name = self.snapshot.get("modelName") or "indoor_model"
        model_id = "IF_" + normalize_token(model_name, "BUILDING")
        level_extent = self._level_extent()
        cell_json = [cell["json"] for cell in self.cells]
        boundary_json = [boundary["json"] for boundary in self.boundaries]

        return {
            "id": model_id,
            "featureType": "IndoorFeatures",
            "metadata": {
                "name": model_name,
                "description": "Indoor model exported from SpatialEngine.",
                "createdAt": self.now,
                "modifiedAt": self.now,
                "generator": "MLSM_SpatialEngine.exportar_indoor_model",
                "source": "SpatialEngine authoring snapshot",
            },
            "crs": self.snapshot.get("crs")
            or {
                "type": "local",
                "unit": "meters",
                "origin": {"x": 0, "y": 0, "z": 0},
                "axisOrder": "xyz",
                "description": "Local 2D coordinate system with level-based Z.",
            },
            "levels": [
                {
                    "id": self.level_id,
                    "name": self.level.get("name") or f"Level {self.level_index:02d}",
                    "order": self.level.get("order", self.level_index),
                    "levelIndex": self.level_index,
                    "elevationM": self.level.get("elevationM", self.level.get("floorZ", 0.0)),
                    "floorZ": self.level.get("floorZ", self.level.get("elevationM", 0.0)),
                    "ceilingZ": self.level.get(
                        "ceilingZ",
                        float(self.level.get("elevationM", self.level.get("floorZ", 0.0)) or 0.0)
                        + float(self.level.get("heightM", 3.0) or 3.0),
                    ),
                    "heightM": self.level.get("heightM", 3.0),
                    "spatialExtent2D": level_extent,
                }
            ],
            "layers": [
                {
                    "id": self.layer_id,
                    "featureType": "ThematicLayer",
                    "semanticExtension": True,
                    "theme": "Physical",
                    "name": f"Physical navigation layer - {self.level_id}",
                    "level": self.level_id,
                    "primalSpace": {
                        "id": self.primal_id,
                        "featureType": "PrimalSpaceLayer",
                        "creationDatetime": self.now,
                        "cellSpaceMember": cell_json,
                        "cellBoundaryMember": boundary_json,
                    },
                    "dualSpace": {
                        "id": self.dual_id,
                        "featureType": "DualSpaceLayer",
                        "creationDatetime": self.now,
                        "isLogical": False,
                        "isDirected": False,
                        "nodeMember": self.nodes,
                        "edgeMember": self.edges,
                        "attributes": {
                            "edgeMode": self.edge_mode,
                        },
                    },
                }
            ],
            "layerConnections": [],
            "verticalConnectors": self.snapshot.get("verticalConnectors", []),
            "sourceFeatures": self.source_features,
            "indoorDataModel": {
                "modelName": "indoor_data_model",
                "modelVersion": "0.1-draft",
                "profile": "indoorjson_like",
                "compatibility": "Conceptually aligned with IndoorGML/IndoorJSON; project schema profile.",
                "supersedes": ["mlsm_json_v2_transitional"],
            },
        }

    def _level_extent(self):
        if self.level.get("spatialExtent2D"):
            return self.level["spatialExtent2D"]
        width = float(self.snapshot.get("canvas", {}).get("width", 0) or 0)
        height = float(self.snapshot.get("canvas", {}).get("height", 0) or 0)
        if width > 0 and height > 0:
            return {
                "type": "Polygon",
                "coordinates": [
                    [
                        [0.0, 0.0],
                        [width, 0.0],
                        [width, height],
                        [0.0, height],
                        [0.0, 0.0],
                    ]
                ],
            }

        polygons = [cell["polygon"] for cell in self.cells]
        extent = union_polygons(polygons).envelope
        return polygon_geojson(extent)


class MultiLevelIndoorModelBuilder:
    def __init__(self, snapshot, edge_mode=EDGE_MODE_NAVIGATION):
        self.snapshot = snapshot
        self.edge_mode = edge_mode
        self.now = snapshot.get("createdAt") or _now_utc()

    def build(self):
        levels = self._levels()
        subdocuments = []
        for level in levels:
            level_snapshot = self._snapshot_for_level(level)
            try:
                subdocuments.append(IndoorModelBuilder(level_snapshot, edge_mode=self.edge_mode).build())
            except ValueError:
                # Empty levels are still represented in levels[], but they do not
                # create a ThematicLayer until they contain exportable cells.
                continue
        if not subdocuments:
            raise ValueError("No hay CellSpaces exportables para indoor_model.json.")

        first = subdocuments[0]
        root = {
            "id": "IF_" + normalize_token(self.snapshot.get("modelName") or "indoor_model", "BUILDING"),
            "featureType": "IndoorFeatures",
            "metadata": dict(first.get("metadata") or {}),
            "crs": self.snapshot.get("crs") or first.get("crs"),
            "levels": [self._normalize_level(level) for level in levels],
            "layers": [],
            "layerConnections": [],
            "verticalConnectors": self.snapshot.get("verticalConnectors", []),
            "sourceFeatures": [],
            "indoorDataModel": first.get("indoorDataModel"),
        }
        root["metadata"]["modifiedAt"] = self.now
        for document in subdocuments:
            root["layers"].extend(document.get("layers", []))
            root["sourceFeatures"].extend(document.get("sourceFeatures", []))
        root["layerConnections"].extend(self._inter_level_connections())
        return root

    def _levels(self):
        levels = [dict(level) for level in (self.snapshot.get("levels") or [])]
        if not levels:
            levels = [
                {
                    "id": LEVEL_ID,
                    "name": "Ground floor",
                    "levelIndex": 0,
                    "order": 0,
                    "floorZ": 0.0,
                    "ceilingZ": 3.0,
                    "heightM": 3.0,
                }
            ]
        return sorted(levels, key=lambda level: (level.get("order", level.get("levelIndex", 0)), level.get("id", "")))

    def _snapshot_for_level(self, level):
        level_id = level.get("id") or LEVEL_ID
        copy_snapshot = dict(self.snapshot)
        copy_snapshot["levels"] = [level]
        copy_snapshot["authoringElements"] = [
            line
            for line in self.snapshot.get("authoringElements", [])
            if (line.get("level") or level_id) == level_id
        ]
        copy_snapshot["spaceFootprints"] = [
            space
            for space in self.snapshot.get("spaceFootprints", [])
            if (space.get("level") or level_id) == level_id
        ]
        copy_snapshot["detectedSpaces"] = [
            space
            for space in self.snapshot.get("detectedSpaces", [])
            if (space.get("level") or level_id) == level_id
        ]
        copy_snapshot["virtualBoundaries"] = [
            boundary
            for boundary in self.snapshot.get("virtualBoundaries", [])
            if (boundary.get("level") or level_id) == level_id
        ]
        copy_snapshot["verticalConnectors"] = [
            connector
            for connector in self.snapshot.get("verticalConnectors", [])
            if any((endpoint.get("level") or endpoint.get("levelId")) == level_id for endpoint in connector.get("endpoints", []))
        ]
        return copy_snapshot

    def _normalize_level(self, level):
        normalized = dict(level)
        normalized.setdefault("levelIndex", normalized.get("order", 0))
        normalized.setdefault("order", normalized.get("levelIndex", 0))
        normalized.setdefault("elevationM", normalized.get("floorZ", 0.0))
        normalized.setdefault("floorZ", normalized.get("elevationM", 0.0))
        normalized.setdefault("heightM", 3.0)
        normalized.setdefault("ceilingZ", float(normalized.get("floorZ") or 0.0) + float(normalized.get("heightM") or 3.0))
        return normalized

    def _inter_level_connections(self):
        connections = []
        for connector in self.snapshot.get("verticalConnectors", []):
            endpoints = sorted(connector.get("endpoints", []), key=lambda endpoint: endpoint.get("level") or "")
            if len(endpoints) < 2:
                continue
            for index, endpoint_a in enumerate(endpoints[:-1], start=1):
                endpoint_b = endpoints[index]
                level_a = endpoint_a.get("level")
                level_b = endpoint_b.get("level")
                if not level_a or not level_b or level_a == level_b:
                    continue
                code_a = self._level_code(level_a)
                code_b = self._level_code(level_b)
                cell_a = f"CS_{code_a}_{normalize_token(endpoint_a.get('id') or 'ENDPOINT')}"
                cell_b = f"CS_{code_b}_{normalize_token(endpoint_b.get('id') or 'ENDPOINT')}"
                node_a = node_id_for_cell(cell_a)
                node_b = node_id_for_cell(cell_b)
                connections.append(
                    {
                        "id": f"ILC_{normalize_token(connector.get('id') or 'CONNECTOR')}_{index:03d}",
                        "featureType": "InterLayerConnection",
                        "connectedLayers": [f"TL_NAV_{code_a}", f"TL_NAV_{code_b}"],
                        "connectedNodes": [
                            ref(f"TL_NAV_{code_a}", f"DS_NAV_{code_a}", node_a),
                            ref(f"TL_NAV_{code_b}", f"DS_NAV_{code_b}", node_b),
                        ],
                        "connectedCells": [
                            ref(f"TL_NAV_{code_a}", f"PS_NAV_{code_a}", cell_a),
                            ref(f"TL_NAV_{code_b}", f"PS_NAV_{code_b}", cell_b),
                        ],
                        "typeOfTopoExpression": "OTHERS",
                        "comment": f"{connector.get('connectorType')} inter-level connector {connector.get('id')}",
                        "attributes": {
                            "relationshipType": "vertical_connectivity",
                            "connectorId": connector.get("id"),
                            "connectorType": connector.get("connectorType"),
                            "directionality": connector.get("directionality", "bidirectional"),
                            "locomotionTypes": _normalize_locomotion(connector.get("locomotionTypes")),
                        },
                    }
                )
        return connections

    def _level_code(self, level_id):
        token = str(level_id or LEVEL_ID).upper()
        if token.startswith("LEVEL_"):
            token = token[len("LEVEL_") :]
        if token.isdigit():
            return f"L{int(token):02d}"
        return normalize_token(token, "L00")


def _requires_multilevel_builder(snapshot):
    levels = snapshot.get("levels") or []
    if len(levels) > 1:
        return True
    return bool(snapshot.get("verticalConnectors"))


def build_indoor_model(snapshot, edge_mode=EDGE_MODE_NAVIGATION):
    if _requires_multilevel_builder(snapshot):
        return MultiLevelIndoorModelBuilder(snapshot, edge_mode=edge_mode).build()
    return IndoorModelBuilder(snapshot, edge_mode=edge_mode).build()


def derive_wall_mass_from_snapshot(snapshot, level_id=None):
    """Return final wall geometries for one level without building full CellSpaces."""
    level_snapshot = _single_level_snapshot(snapshot, level_id)
    builder = IndoorModelBuilder(level_snapshot)
    builder._prepare_authoring_lines()
    builder._derive_wall_parts()
    return {
        "levelId": builder.level_id,
        "wallParts": [
            {
                "category": part.get("category"),
                "polygon": part.get("polygon"),
                "lines": part.get("lines") or ([part.get("line")] if part.get("line") else []),
            }
            for part in builder.wall_parts
        ],
        "wallUnion": builder.wall_union,
        "solidWallUnion": builder.solid_wall_union,
    }


def _single_level_snapshot(snapshot, level_id=None):
    levels = [dict(level) for level in (snapshot.get("levels") or [])]
    if level_id is None:
        level = levels[0] if levels else {"id": LEVEL_ID, "name": "Ground floor", "levelIndex": 0, "order": 0}
        level_id = level.get("id") or LEVEL_ID
    else:
        level = next((level for level in levels if level.get("id") == level_id), None)
        if level is None:
            level = {"id": level_id, "name": str(level_id), "levelIndex": 0, "order": 0}

    copy_snapshot = dict(snapshot)
    copy_snapshot["levels"] = [level]
    copy_snapshot["authoringElements"] = [
        line
        for line in snapshot.get("authoringElements", [])
        if (line.get("level") or level_id) == level_id
    ]
    copy_snapshot["spaceFootprints"] = [
        space
        for space in snapshot.get("spaceFootprints", [])
        if (space.get("level") or level_id) == level_id
    ]
    copy_snapshot["detectedSpaces"] = [
        space
        for space in snapshot.get("detectedSpaces", [])
        if (space.get("level") or level_id) == level_id
    ]
    copy_snapshot["virtualBoundaries"] = [
        boundary
        for boundary in snapshot.get("virtualBoundaries", [])
        if (boundary.get("level") or level_id) == level_id
    ]
    copy_snapshot["verticalConnectors"] = [
        connector
        for connector in snapshot.get("verticalConnectors", [])
        if any((endpoint.get("level") or endpoint.get("levelId")) == level_id for endpoint in connector.get("endpoints", []))
    ]
    return copy_snapshot

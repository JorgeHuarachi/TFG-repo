"""Build IndoorJSON-like indoor_model.json documents from SpatialEngine snapshots."""

import datetime

from shapely.geometry import Point

from .geometry import (
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
WALL_CAP_STYLE = 3
OPENING_CAP_STYLE = 2
JOIN_STYLE = 2
OVERLAP_AREA_TOLERANCE = 1e-6
WALL_CONNECTION_TOLERANCE = 0.05
WALL_EXTENSION_EPSILON = 0.002
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
    allowed = {"Flying", "Rolling", "Walking", "Unspecified", "Step"}
    mapping = {
        "flying": "Flying",
        "rolling": "Rolling",
        "walking": "Walking",
        "unspecified": "Unspecified",
        "step": "Step",
        "stairs": "Step",
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
        self.object_union = None
        self.transfer_union = None
        self.opening_union = None
        self.overlap_warnings = []

    def build(self):
        self._prepare_authoring_lines()
        self._create_source_features()
        self._derive_wall_parts()
        self._create_object_spaces()
        self._create_transfer_spaces()
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
            prepared["level"] = prepared.get("level") or LEVEL_ID
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
        wall_records = []
        for line in self.authoring_lines:
            if not is_solid_wall_type(line.get("type")):
                continue
            centerline = line_from_coords(line.get("centerline"))
            if centerline is None:
                continue
            thickness = self._positive_float(line.get("thicknessM"), 0.1)
            footprint = footprint_from_centerline(
                line.get("centerline"),
                thickness,
                cap_style=WALL_CAP_STYLE,
                join_style=JOIN_STYLE,
            )
            if footprint is None:
                continue
            wall_records.append(
                {
                    "line": line,
                    "centerline": centerline,
                    "polygon": footprint,
                    "thickness": thickness,
                }
            )

        for record in wall_records:
            coords = list(record["line"].get("centerline") or [])
            if len(coords) < 2:
                continue

            start_extension = self._wall_endpoint_extension(record, 0, wall_records)
            end_extension = self._wall_endpoint_extension(record, -1, wall_records)
            if start_extension <= 0 and end_extension <= 0:
                record["line"]["_derived_centerline"] = coords
                continue

            derived = list(coords)
            if start_extension > 0:
                ux, uy = self._endpoint_outward_unit(coords, 0)
                x, y = derived[0]
                derived[0] = (float(x) + ux * start_extension, float(y) + uy * start_extension)
            if end_extension > 0:
                ux, uy = self._endpoint_outward_unit(coords, -1)
                x, y = derived[-1]
                derived[-1] = (float(x) + ux * end_extension, float(y) + uy * end_extension)

            record["line"]["_derived_centerline"] = derived
            record["line"]["_wall_centerline_extension"] = {
                "startM": round(float(start_extension), 6),
                "endM": round(float(end_extension), 6),
                "reason": "junction_closure",
            }

    def _wall_endpoint_extension(self, record, endpoint_index, wall_records):
        coords = list(record["line"].get("centerline") or [])
        if len(coords) < 2:
            return 0.0

        endpoint = coords[0] if endpoint_index == 0 else coords[-1]
        ux, uy = self._endpoint_outward_unit(coords, endpoint_index)
        if ux == 0.0 and uy == 0.0:
            return 0.0

        point = Point(float(endpoint[0]), float(endpoint[1]))
        extension = 0.0
        for other in wall_records:
            if other is record:
                continue
            other_polygon = other.get("polygon")
            other_centerline = other.get("centerline")
            if other_polygon is None or other_polygon.is_empty or other_centerline is None:
                continue

            try:
                touches_receiver = (
                    point.distance(other_polygon) <= WALL_CONNECTION_TOLERANCE
                    or point.distance(other_centerline) <= WALL_CONNECTION_TOLERANCE
                )
            except Exception:
                touches_receiver = False
            if not touches_receiver:
                continue

            desired_penetration = max(record["thickness"] / 2.0, other["thickness"] / 2.0)
            ray_length = max(desired_penetration + other["thickness"] + WALL_CONNECTION_TOLERANCE + 0.5, 1.0)
            ray = line_from_coords(
                [
                    (float(endpoint[0]), float(endpoint[1])),
                    (float(endpoint[0]) + ux * ray_length, float(endpoint[1]) + uy * ray_length),
                ]
            )
            if ray is None:
                continue

            try:
                ray_overlap = ray.intersection(other_polygon)
            except Exception:
                ray_overlap = None
            farthest = self._max_projected_distance(ray_overlap, point, (ux, uy))
            if farthest is not None and farthest > 0:
                desired_penetration = max(desired_penetration, farthest)
            extension = max(
                extension,
                self._centerline_extension_for_penetration(desired_penetration, record["thickness"]),
            )

        return extension

    def _centerline_extension_for_penetration(self, desired_penetration, self_thickness):
        cap_contribution = self_thickness / 2.0 if WALL_CAP_STYLE == 3 else 0.0
        if desired_penetration <= cap_contribution + WALL_EXTENSION_EPSILON:
            return 0.0
        return max(0.0, desired_penetration - cap_contribution + WALL_EXTENSION_EPSILON)

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

    def _max_projected_distance(self, geom, origin, unit):
        if geom is None or geom.is_empty:
            return None

        ux, uy = unit
        distances = []

        def collect_coords(part):
            if part is None or part.is_empty:
                return
            geom_type = getattr(part, "geom_type", "")
            if geom_type in {"LineString", "LinearRing", "Point"}:
                for x, y, *unused in part.coords:
                    distances.append((float(x) - origin.x) * ux + (float(y) - origin.y) * uy)
            elif hasattr(part, "geoms"):
                for child in part.geoms:
                    collect_coords(child)
            elif geom_type == "Polygon" and hasattr(part, "exterior"):
                collect_coords(part.exterior)

        collect_coords(geom)
        positive = [distance for distance in distances if distance > WALL_CONNECTION_TOLERANCE / -10.0]
        return max(positive) if positive else None

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
        counters = {"wall": 0, "door": 0, "exit": 0, "virtual": 0, "room": 0, "other": 0}

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
            elif is_virtual_boundary_type(tipo):
                key, source_type = "virtual", "virtual_boundary_line"
            else:
                key, source_type = "other", "other"

            counters[key] += 1
            source_id = f"SF_{LEVEL_CODE}_{normalize_token(key)}_{counters[key]:03d}"
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
                    "level": line.get("level") or LEVEL_ID,
                    "geometry": line_geojson(geom_line),
                    "attributes": attrs,
                }
            )
            self.source_by_line_name[line.get("name")] = source_id

        for space in self.snapshot.get("spaceFootprints", []):
            name = space.get("name")
            if not name or self._space_is_transfer_or_virtual(space):
                continue
            poly = polygon_from_coords(space.get("footprint"))
            if poly is None:
                continue
            counters["room"] += 1
            source_id = f"SF_{LEVEL_CODE}_ROOM_{counters['room']:03d}"
            self._add_source_feature(
                {
                    "id": source_id,
                    "featureType": "SourceFeature",
                    "sourceType": "room_polygon",
                    "level": space.get("level") or LEVEL_ID,
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
            or is_non_solid_topology_type(authoring_type)
            or "puerta" in lower_name
            or "salida" in lower_name
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
            if not self._space_is_object(space):
                continue
            poly = polygon_from_coords(space.get("footprint"))
            if poly is None:
                continue
            source_ref = self.source_by_space_name.get(space.get("name"))
            attrs = dict(space.get("attributes") or {})
            attrs["derivationStatus"] = "derived_from_object_footprint"
            cell_id = f"CS_{LEVEL_CODE}_OBJ_{index:03d}"
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
                raw_walls.append({"line": line, "polygon": poly})

        opening_union = union_polygons(openings)
        self.opening_union = opening_union
        junction_candidates = []
        for index, wall_a in enumerate(raw_walls):
            for wall_b in raw_walls[index + 1 :]:
                try:
                    intersection = wall_a["polygon"].intersection(wall_b["polygon"])
                except Exception:
                    continue
                for part in iter_polygons(intersection):
                    if part.area > OVERLAP_AREA_TOLERANCE:
                        junction_candidates.append(part)

        junction_union = union_polygons(junction_candidates)
        wall_polys = []
        try:
            junction_geom = junction_union.difference(opening_union) if not opening_union.is_empty else junction_union
        except Exception:
            junction_geom = junction_union

        junction_parts = iter_polygons(junction_geom)
        for index, part in enumerate(junction_parts, start=1):
            contributing_lines = []
            for wall in raw_walls:
                try:
                    overlap_area = part.intersection(wall["polygon"]).area
                except Exception:
                    overlap_area = 0.0
                if overlap_area > OVERLAP_AREA_TOLERANCE:
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
                    derived = derived.difference(opening_union)
                if not junction_union.is_empty:
                    derived = derived.difference(junction_union)
            except Exception:
                derived = wall_poly
            parts = iter_polygons(derived)
            for index, part in enumerate(parts, start=1):
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
        self.wall_union = union_polygons(wall_polys)

    def _line_footprint(self, line):
        prepared = self.line_by_name.get(line.get("name"), line)
        poly = prepared.get("_footprint_poly")
        if poly is not None:
            return poly
        return footprint_from_centerline(prepared.get("centerline"), prepared.get("thicknessM") or 0.1)

    def _create_general_spaces(self):
        index = 1
        for space in self.snapshot.get("spaceFootprints", []):
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
                base_id = f"CS_{LEVEL_CODE}_ROOM_{index:03d}"
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

    def _create_transfer_spaces(self):
        door_index = 1
        exit_index = 1
        transfer_polys = []
        for line in self.authoring_lines:
            tipo = line.get("type")
            if not is_transfer_authoring_type(tipo):
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
                cell_id = f"CS_{LEVEL_CODE}_EXIT_{exit_index:03d}"
                exit_index += 1
                function = "AnchorSpace"
                category = "Exit"
            else:
                cell_id = f"CS_{LEVEL_CODE}_DOOR_{door_index:03d}"
                door_index += 1
                function = "ConnectionSpace"
                category = "Door"

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
                base_id = f"CS_{LEVEL_CODE}_WALLJUNC_{junction_index:03d}"
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
                base_id = f"CS_{LEVEL_CODE}_WALLSEG_{wall_index:03d}"
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
            "level": LEVEL_ID,
            "poi": False,
            "duality": ref(LAYER_ID, DUAL_ID, node_id),
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
                tolerance = BOUNDARY_CONTACT_TOLERANCE if boundary_role == "general_transfer_contact" else 0.0
                line = contact_line(cell_a["polygon"], cell_b["polygon"], min_length=0.05, tolerance=tolerance)
                if line is None:
                    continue

                boundary_id = self._boundary_id(cell_a["id"], cell_b["id"], used_ids)
                traversable = boundary_role == "general_transfer_contact"
                is_anchor = traversable and self._transfer_cell(cell_a, cell_b).get("function") == "AnchorSpace"
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
                    boundary["duality"] = ref(LAYER_ID, DUAL_ID, edge_id)
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
        base = f"CB_{LEVEL_CODE}_{role_token}_{compact_cell_token(cell_id)}"
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

        if types == {"GeneralSpace", "NonNavigableSpace"}:
            return self._is_wall_segment_cell(cell_a) or self._is_wall_segment_cell(cell_b)
        return False

    def _boundary_role(self, cell_a, cell_b):
        types = {cell_a["navigationType"], cell_b["navigationType"]}
        if types == {"GeneralSpace", "TransferSpace"}:
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
        base = f"CB_{LEVEL_CODE}_{token_a}_{token_b}"
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
            node_ref = ref(LAYER_ID, DUAL_ID, cell["nodeId"])
            self.node_connects[cell["nodeId"]] = []
            self.nodes.append(
                {
                    "id": cell["nodeId"],
                    "featureType": "Node",
                    "duality": ref(LAYER_ID, PRIMAL_ID, cell["id"]),
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
            edge_ref = ref(LAYER_ID, DUAL_ID, edge_id)
            _unique_append(self.node_connects[cell_a["nodeId"]], edge_ref)
            _unique_append(self.node_connects[cell_b["nodeId"]], edge_ref)
            node_a = node_point_for_polygon(cell_a["polygon"])
            node_b = node_point_for_polygon(cell_b["polygon"])
            transfer = self._transfer_cell(cell_a, cell_b) if boundary["traversable"] else None
            distance = node_a.distance(node_b)

            edge = {
                "id": edge_id,
                "featureType": "Edge",
                "duality": ref(LAYER_ID, PRIMAL_ID, boundary["json"]["id"]),
                "weight": round(float(distance if distance > 0 else 1.0), 6),
                "geometry": line_geojson(line_from_coords([(node_a.x, node_a.y), (node_b.x, node_b.y)])),
                "connects": [
                    ref(LAYER_ID, DUAL_ID, cell_a["nodeId"]),
                    ref(LAYER_ID, DUAL_ID, cell_b["nodeId"]),
                ],
                "relationshipType": "connectivity" if boundary["traversable"] else "adjacency",
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

            self.edges.append(edge)

        for cell in cell_by_id.values():
            cell["json"]["duality"] = ref(LAYER_ID, DUAL_ID, cell["nodeId"])

    def _sync_cell_boundary_refs(self):
        cell_by_id = {cell["id"]: cell for cell in self.cells}
        for boundary in self.boundaries:
            boundary_ref = ref(LAYER_ID, PRIMAL_ID, boundary["json"]["id"])
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
                    "id": LEVEL_ID,
                    "name": "Ground floor",
                    "levelIndex": 0,
                    "floorZ": 0.0,
                    "ceilingZ": 3.0,
                    "heightM": 3.0,
                    "spatialExtent2D": level_extent,
                }
            ],
            "layers": [
                {
                    "id": LAYER_ID,
                    "featureType": "ThematicLayer",
                    "semanticExtension": True,
                    "theme": "Physical",
                    "name": "Physical navigation layer - level 00",
                    "level": LEVEL_ID,
                    "primalSpace": {
                        "id": PRIMAL_ID,
                        "featureType": "PrimalSpaceLayer",
                        "creationDatetime": self.now,
                        "cellSpaceMember": cell_json,
                        "cellBoundaryMember": boundary_json,
                    },
                    "dualSpace": {
                        "id": DUAL_ID,
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


def build_indoor_model(snapshot, edge_mode=EDGE_MODE_NAVIGATION):
    return IndoorModelBuilder(snapshot, edge_mode=edge_mode).build()

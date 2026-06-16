"""Build IndoorJSON-like indoor_model.json documents from SpatialEngine snapshots."""

import datetime

from .geometry import (
    contact_line,
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
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.now = snapshot.get("createdAt") or _now_utc()
        self.source_features = []
        self.source_by_id = {}
        self.source_by_line_name = {}
        self.source_by_space_name = {}
        self.line_by_name = {}
        self.cells = []
        self.boundaries = []
        self.edges = []
        self.nodes = []
        self.node_connects = {}
        self.wall_parts = []
        self.wall_union = None

    def build(self):
        self._prepare_authoring_lines()
        self._create_source_features()
        self._derive_wall_parts()
        self._create_general_spaces()
        self._create_transfer_spaces()
        self._create_wall_spaces()

        if not self.cells:
            raise ValueError("No hay CellSpaces exportables para indoor_model.json.")

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
            if prepared.get("footprint"):
                prepared["_footprint_poly"] = polygon_from_coords(prepared["footprint"])
            else:
                prepared["_footprint_poly"] = footprint_from_centerline(
                    prepared.get("centerline"),
                    prepared.get("thicknessM") or 0.1,
                )
            if tipo and prepared.get("name"):
                self.line_by_name[prepared["name"]] = prepared

    def _create_source_features(self):
        counters = {"wall": 0, "door": 0, "exit": 0, "virtual": 0, "room": 0, "other": 0}

        for line in self.snapshot.get("authoringElements", []):
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

    def _derive_wall_parts(self):
        openings = []
        walls = []
        for line in self.snapshot.get("authoringElements", []):
            tipo = line.get("type")
            poly = self._line_footprint(line)
            if poly is None:
                continue
            if is_opening_type(tipo):
                openings.append(poly)
            elif is_solid_wall_type(tipo):
                walls.append((line, poly))

        opening_union = union_polygons(openings)
        wall_polys = []
        for line, wall_poly in walls:
            try:
                derived = wall_poly.difference(opening_union) if not opening_union.is_empty else wall_poly
            except Exception:
                derived = wall_poly
            parts = iter_polygons(derived)
            for index, part in enumerate(parts, start=1):
                self.wall_parts.append(
                    {
                        "line": line,
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
            if self._space_is_transfer_or_virtual(space):
                continue
            source_ref = self.source_by_space_name.get(space.get("name"))
            original_poly = polygon_from_coords(space.get("footprint"))
            if original_poly is None:
                continue

            attrs = dict(space.get("attributes") or {})
            try:
                if self.wall_union is not None and not self.wall_union.is_empty:
                    derived = original_poly.difference(self.wall_union)
                else:
                    derived = original_poly
                parts = iter_polygons(derived)
                if not parts:
                    raise ValueError("empty clipped geometry")
                derivation_attrs = {"derivationStatus": "clipped_by_solid_walls"}
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
        for line in self.snapshot.get("authoringElements", []):
            tipo = line.get("type")
            if not is_transfer_authoring_type(tipo):
                continue
            poly = self._line_footprint(line)
            if poly is None:
                continue
            source_ref = self.source_by_line_name.get(line.get("name"))
            attrs = dict(line.get("attributes") or {})
            if is_exit_type(tipo):
                cell_id = f"CS_{LEVEL_CODE}_EXIT_{exit_index:03d}"
                exit_index += 1
                function = "AnchorSpace"
            else:
                cell_id = f"CS_{LEVEL_CODE}_DOOR_{door_index:03d}"
                door_index += 1
                function = "ConnectionSpace"

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
                category="Door",
                function=function,
                locomotion=_normalize_locomotion(attrs.get("locomotion")),
                source_refs=[source_ref] if source_ref else [],
                attributes=attrs,
                width_m=line.get("widthM"),
            )

    def _create_wall_spaces(self):
        wall_indices = {}
        next_wall_index = 1
        for wall in self.wall_parts:
            line = wall["line"]
            wall_key = line.get("name") or id(line)
            if wall_key not in wall_indices:
                wall_indices[wall_key] = next_wall_index
                next_wall_index += 1
            wall_index = wall_indices[wall_key]
            source_ref = self.source_by_line_name.get(line.get("name"))
            base_id = f"CS_{LEVEL_CODE}_WALL_{wall_index:03d}"
            cell_id = base_id if wall["partCount"] == 1 else f"{base_id}_PART_{wall['partIndex']:03d}"
            attrs = {
                "originalName": line.get("name"),
                "originalType": line.get("type"),
                "thicknessM": line.get("thicknessM"),
                "derivationStatus": "wall_footprint_clipped_by_openings",
            }
            if wall["partCount"] > 1:
                attrs["partIndex"] = wall["partIndex"]
                attrs["partCount"] = wall["partCount"]

            self._add_cell(
                cell_id=cell_id,
                name=line.get("name") if wall["partCount"] == 1 else f"{line.get('name')} part {wall['partIndex']}",
                polygon=wall["polygon"],
                navigation_type="NonNavigableSpace",
                navigation_class="NonNavigableSpace",
                category="Wall",
                function="Wall",
                locomotion=[],
                source_refs=[source_ref] if source_ref else [],
                attributes=attrs,
            )

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

    def _create_boundaries(self):
        used_ids = set()
        for i, cell_a in enumerate(self.cells):
            for cell_b in self.cells[i + 1 :]:
                if not self._should_boundary_be_created(cell_a, cell_b):
                    continue
                tolerance = 0.20 if self._is_general_transfer_pair(cell_a, cell_b) else 0.0
                line = contact_line(cell_a["polygon"], cell_b["polygon"], min_length=0.05, tolerance=tolerance)
                if line is None:
                    continue

                boundary_id = self._boundary_id(cell_a["id"], cell_b["id"], used_ids)
                edge_id = edge_id_for_boundary(boundary_id)
                traversable = self._is_general_transfer_pair(cell_a, cell_b)
                is_anchor = traversable and self._transfer_cell(cell_a, cell_b).get("function") == "AnchorSpace"
                boundary_type = "NavigableBoundary" if traversable else "NonNavigableBoundary"
                source_refs = []
                for source_ref in cell_a["sourceRefs"] + cell_b["sourceRefs"]:
                    _unique_append(source_refs, source_ref)

                boundary = {
                    "id": boundary_id,
                    "featureType": "CellBoundary",
                    "isVirtual": False,
                    "duality": ref(LAYER_ID, DUAL_ID, edge_id),
                    "cellBoundaryGeom": {"geometry2D": line_geojson(line)},
                    "navigationBoundaryType": boundary_type,
                    "traversable": traversable,
                    "cellRefs": [cell_a["id"], cell_b["id"]],
                    "sourceFeatureRefs": source_refs,
                    "attributes": {
                        "derivationStatus": "geometry_contact",
                    },
                }
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

    def _should_boundary_be_created(self, cell_a, cell_b):
        types = {cell_a["navigationType"], cell_b["navigationType"]}
        if types == {"NonNavigableSpace"}:
            return False
        if "GeneralSpace" in types:
            return True
        return False

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
                },
            }
            if transfer is not None:
                edge["transferSpaceRef"] = transfer["id"]
                edge["locomotionTypes"] = transfer.get("locomotionTypes") or ["Walking", "Rolling"]
                if transfer.get("widthM") is not None:
                    width = float(transfer["widthM"])
                    edge["widthM"] = width
                    edge["capacityPersons"] = max(1.0, round(width / 0.6, 2))

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


def build_indoor_model(snapshot):
    return IndoorModelBuilder(snapshot).build()

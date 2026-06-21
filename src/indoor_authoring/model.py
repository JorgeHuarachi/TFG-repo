"""Multilevel authoring state for SpatialEngine.

The objects in this module are the source of truth while editing. Legacy lists
such as ``self.muros`` can be rebuilt from this state, but they should not carry
new semantics on their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_LEVEL_HEIGHT_M = 3.0


def level_code(level_id: str) -> str:
    token = str(level_id or "LEVEL_00").upper()
    if token.startswith("LEVEL_"):
        token = token[len("LEVEL_") :]
    return "L" + token if token.isdigit() else token.replace("_", "")


def default_level_id(order: int) -> str:
    return f"LEVEL_{int(order):02d}"


@dataclass
class AuthoringLineElement:
    id: str
    element_type: str
    start: tuple[float, float]
    end: tuple[float, float]
    level_id: str
    thickness_m: float | None = None
    width_m: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def centerline(self) -> list[tuple[float, float]]:
        return [self.start, self.end]

    def to_legacy_tuple(self) -> tuple[str, str, float, float, float, float]:
        return (
            self.id,
            self.element_type,
            float(self.start[0]),
            float(self.start[1]),
            float(self.end[0]),
            float(self.end[1]),
        )

    def to_snapshot(self) -> dict[str, Any]:
        data = {
            "name": self.id,
            "type": self.element_type,
            "level": self.level_id,
            "centerline": self.centerline(),
            "thicknessM": self.thickness_m,
            "attributes": dict(self.attributes),
        }
        if self.width_m is not None:
            data["widthM"] = self.width_m
        for key in (
            "hostWallName",
            "hostWallType",
            "hostWallThicknessM",
            "hostWallRef",
            "projectedPoint",
            "wallUnitVector",
            "windowType",
            "defaultTraversable",
            "scenarioControllable",
            "sillHeightM",
        ):
            if key in self.attributes:
                data[key] = self.attributes[key]
        return data


@dataclass
class AuthoringAreaElement:
    id: str
    element_type: str
    footprint: list[tuple[float, float]]
    level_id: str
    centroid: tuple[float, float] | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_legacy_bound(self) -> tuple[str, list[tuple[float, float]]]:
        return self.id, list(self.footprint)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "name": self.id,
            "level": self.level_id,
            "footprint": list(self.footprint),
            "centroid": self.centroid,
            "attributes": dict(self.attributes),
            "authoringType": self.element_type,
        }


@dataclass
class DetectedSpace:
    id: str
    level_id: str
    polygon: list[list[tuple[float, float]]]
    source_face_id: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level_id,
            "polygon": self.polygon,
            "sourceFaceId": self.source_face_id,
            "attributes": dict(self.attributes),
        }


@dataclass
class VirtualBoundary:
    id: str
    level_id: str
    line: list[tuple[float, float]]
    generated_automatically: bool = False
    generation_reason: str = "manual"
    traversable: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level_id,
            "line": list(self.line),
            "generatedAutomatically": self.generated_automatically,
            "generationReason": self.generation_reason,
            "traversable": self.traversable,
            "attributes": dict(self.attributes),
        }


@dataclass
class ConnectorEndpoint:
    id: str
    level_id: str
    footprint: list[tuple[float, float]]
    entry_side: str | None = None
    exit_side: str | None = None
    open_sides: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Any]:
        snapshot = {
            "id": self.id,
            "level": self.level_id,
            "footprint": list(self.footprint),
            "openSides": list(self.open_sides),
            "attributes": dict(self.attributes),
        }
        if self.entry_side is not None:
            snapshot["entrySide"] = self.entry_side
        if self.exit_side is not None:
            snapshot["exitSide"] = self.exit_side
        return snapshot


@dataclass
class VerticalConnector:
    id: str
    connector_type: str
    scope: str
    endpoints: list[ConnectorEndpoint]
    source_level: str
    target_level: str | None = None
    from_elevation_m: float = 0.0
    to_elevation_m: float = 0.0
    directionality: str = "bidirectional"
    locomotion_types: list[str] = field(default_factory=lambda: ["Walking"])
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "connectorType": self.connector_type,
            "scope": self.scope,
            "endpoints": [endpoint.to_snapshot() for endpoint in self.endpoints],
            "sourceLevel": self.source_level,
            "targetLevel": self.target_level,
            "fromElevationM": self.from_elevation_m,
            "toElevationM": self.to_elevation_m,
            "directionality": self.directionality,
            "locomotionTypes": list(self.locomotion_types),
            "attributes": dict(self.attributes),
        }


@dataclass
class LevelAuthoringState:
    id: str
    name: str
    order: int
    elevation_m: float
    height_m: float = DEFAULT_LEVEL_HEIGHT_M
    spatial_extent_2d: list[tuple[float, float]] | None = None
    wall_centerlines: list[AuthoringLineElement] = field(default_factory=list)
    doors: list[AuthoringLineElement] = field(default_factory=list)
    exits: list[AuthoringLineElement] = field(default_factory=list)
    windows: list[AuthoringLineElement] = field(default_factory=list)
    manual_virtual_boundaries: list[VirtualBoundary] = field(default_factory=list)
    automatic_virtual_boundaries: list[VirtualBoundary] = field(default_factory=list)
    columns: list[AuthoringAreaElement] = field(default_factory=list)
    manual_spaces: list[AuthoringAreaElement] = field(default_factory=list)
    detected_spaces: list[DetectedSpace] = field(default_factory=list)
    semantic_attributes: dict[str, dict[str, Any]] = field(default_factory=dict)
    geometry_dirty: bool = True
    detection_report: dict[str, Any] = field(default_factory=dict)

    @property
    def floor_z(self) -> float:
        return self.elevation_m

    @property
    def ceiling_z(self) -> float:
        return self.elevation_m + self.height_m

    def add_line(self, element: AuthoringLineElement) -> None:
        if element.element_type in {"muro_exterior", "muro_interior"}:
            self.wall_centerlines.append(element)
        elif element.element_type in {"puerta_simple", "puerta_doble"}:
            self.doors.append(element)
        elif element.element_type == "salida":
            self.exits.append(element)
        elif element.element_type in {"ventana", "ventana_practicable"}:
            self.windows.append(element)
        elif element.element_type == "frontera_virtual":
            self.manual_virtual_boundaries.append(
                VirtualBoundary(
                    id=element.id,
                    level_id=element.level_id,
                    line=element.centerline(),
                    generated_automatically=False,
                    generation_reason="manual",
                    traversable=True,
                    attributes=dict(element.attributes),
                )
            )
        else:
            self.wall_centerlines.append(element)
        self.geometry_dirty = True

    def add_area(self, element: AuthoringAreaElement) -> None:
        if element.element_type == "columna":
            self.columns.append(element)
        else:
            self.manual_spaces.append(element)
        self.geometry_dirty = True

    def all_line_elements(self) -> list[AuthoringLineElement]:
        return self.wall_centerlines + self.doors + self.exits + self.windows

    def all_virtual_boundaries(self) -> list[VirtualBoundary]:
        return self.manual_virtual_boundaries + self.automatic_virtual_boundaries

    def legacy_lines(self) -> list[tuple[str, str, float, float, float, float]]:
        lines = [line.to_legacy_tuple() for line in self.all_line_elements()]
        for boundary in self.manual_virtual_boundaries:
            if len(boundary.line) >= 2:
                (x1, y1), (x2, y2) = boundary.line[0], boundary.line[-1]
                lines.append((boundary.id, "frontera_virtual", x1, y1, x2, y2))
        return lines

    def legacy_space_centroids(self) -> dict[str, tuple[float, float]]:
        values: dict[str, tuple[float, float]] = {}
        for area in self.manual_spaces + self.columns:
            if area.centroid is not None:
                values[area.id] = area.centroid
        for line in self.doors + self.exits + self.windows:
            sx, sy = line.start
            ex, ey = line.end
            values[line.id] = ((sx + ex) / 2.0, (sy + ey) / 2.0)
        for boundary in self.manual_virtual_boundaries:
            if len(boundary.line) >= 2:
                sx, sy = boundary.line[0]
                ex, ey = boundary.line[-1]
                values[boundary.id] = ((sx + ex) / 2.0, (sy + ey) / 2.0)
        return values

    def legacy_space_bounds(self) -> list[tuple[str, list[tuple[float, float]]]]:
        values = [area.to_legacy_bound() for area in self.manual_spaces + self.columns]
        for line in self.doors + self.exits + self.windows:
            footprint = line.attributes.get("footprint")
            if footprint:
                values.append((line.id, footprint))
        for boundary in self.manual_virtual_boundaries:
            footprint = boundary.attributes.get("footprint")
            if footprint:
                values.append((boundary.id, footprint))
        return values

    def legacy_attributes(self) -> dict[str, dict[str, Any]]:
        attrs = {key: dict(value) for key, value in self.semantic_attributes.items()}
        for area in self.manual_spaces + self.columns:
            attrs.setdefault(area.id, dict(area.attributes))
        for line in self.doors + self.exits + self.windows:
            attrs.setdefault(line.id, dict(line.attributes))
        for boundary in self.manual_virtual_boundaries:
            attrs.setdefault(boundary.id, dict(boundary.attributes))
        return attrs

    def to_level_document(self) -> dict[str, Any]:
        extent = self.spatial_extent_2d
        return {
            "id": self.id,
            "name": self.name,
            "order": self.order,
            "levelIndex": self.order,
            "elevationM": self.elevation_m,
            "floorZ": self.floor_z,
            "ceilingZ": self.ceiling_z,
            "heightM": self.height_m,
            "spatialExtent2D": polygon_geojson_from_coords(extent) if extent else None,
        }


@dataclass
class BuildingAuthoringState:
    project_id: str = "PROJECT_SPATIAL_ENGINE"
    building_id: str = "BUILDING_001"
    levels: list[LevelAuthoringState] = field(default_factory=list)
    active_level_id: str = "LEVEL_00"
    vertical_connectors: list[VerticalConnector] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "wall": 1,
            "opening": 1,
            "space": 1,
            "column": 1,
            "level": 1,
            "connector": 1,
        }
    )

    def __post_init__(self) -> None:
        if not self.levels:
            self.levels.append(
                LevelAuthoringState(
                    id="LEVEL_00",
                    name="Level 00",
                    order=0,
                    elevation_m=0.0,
                    height_m=DEFAULT_LEVEL_HEIGHT_M,
                )
            )
        if not any(level.id == self.active_level_id for level in self.levels):
            self.active_level_id = self.levels[0].id

    @property
    def active_level(self) -> LevelAuthoringState:
        for level in self.levels:
            if level.id == self.active_level_id:
                return level
        self.active_level_id = self.levels[0].id
        return self.levels[0]

    def level_by_id(self, level_id: str) -> LevelAuthoringState:
        for level in self.levels:
            if level.id == level_id:
                return level
        raise KeyError(f"Unknown level id: {level_id}")

    def sorted_levels(self) -> list[LevelAuthoringState]:
        return sorted(self.levels, key=lambda level: (level.order, level.id))

    def add_level(self, name: str | None = None, height_m: float = DEFAULT_LEVEL_HEIGHT_M) -> LevelAuthoringState:
        order = max((level.order for level in self.levels), default=-1) + 1
        level_id = default_level_id(order)
        existing_ids = {level.id for level in self.levels}
        while level_id in existing_ids:
            order += 1
            level_id = default_level_id(order)
        elevation = order * height_m
        level = LevelAuthoringState(
            id=level_id,
            name=name or f"Level {order:02d}",
            order=order,
            elevation_m=elevation,
            height_m=height_m,
        )
        self.levels.append(level)
        self.active_level_id = level.id
        self.counters["level"] = max(self.counters.get("level", 1), order + 1)
        return level

    def set_active_level(self, level_id: str) -> LevelAuthoringState:
        self.level_by_id(level_id)
        self.active_level_id = level_id
        return self.active_level

    def previous_level(self) -> LevelAuthoringState:
        levels = self.sorted_levels()
        index = max(0, next((i for i, level in enumerate(levels) if level.id == self.active_level_id), 0) - 1)
        self.active_level_id = levels[index].id
        return levels[index]

    def next_level(self) -> LevelAuthoringState:
        levels = self.sorted_levels()
        index = next((i for i, level in enumerate(levels) if level.id == self.active_level_id), 0)
        index = min(len(levels) - 1, index + 1)
        self.active_level_id = levels[index].id
        return levels[index]

    def next_counter(self, name: str) -> int:
        current = int(self.counters.get(name, 1))
        self.counters[name] = current + 1
        return current

    def add_line_to_active(
        self,
        element_id: str,
        element_type: str,
        start: tuple[float, float],
        end: tuple[float, float],
        thickness_m: float | None = None,
        width_m: float | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> AuthoringLineElement:
        element = AuthoringLineElement(
            id=element_id,
            element_type=element_type,
            start=start,
            end=end,
            level_id=self.active_level_id,
            thickness_m=thickness_m,
            width_m=width_m,
            attributes=dict(attributes or {}),
        )
        self.active_level.add_line(element)
        self.active_level.semantic_attributes[element.id] = dict(element.attributes)
        return element

    def add_area_to_active(
        self,
        element_id: str,
        element_type: str,
        footprint: list[tuple[float, float]],
        centroid: tuple[float, float] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> AuthoringAreaElement:
        element = AuthoringAreaElement(
            id=element_id,
            element_type=element_type,
            footprint=list(footprint),
            level_id=self.active_level_id,
            centroid=centroid,
            attributes=dict(attributes or {}),
        )
        self.active_level.add_area(element)
        self.active_level.semantic_attributes[element.id] = dict(element.attributes)
        return element

    def to_snapshot(self, model_name: str, canvas: dict[str, float], crs: dict[str, Any] | None = None) -> dict[str, Any]:
        authoring_elements: list[dict[str, Any]] = []
        space_footprints: list[dict[str, Any]] = []
        detected_spaces: list[dict[str, Any]] = []
        virtual_boundaries: list[dict[str, Any]] = []

        for level in self.sorted_levels():
            for line in level.all_line_elements():
                authoring_elements.append(line.to_snapshot())
            for boundary in level.manual_virtual_boundaries:
                element = AuthoringLineElement(
                    id=boundary.id,
                    element_type="frontera_virtual",
                    start=boundary.line[0],
                    end=boundary.line[-1],
                    level_id=boundary.level_id,
                    attributes=dict(boundary.attributes),
                )
                authoring_elements.append(element.to_snapshot())
            for area in level.manual_spaces + level.columns:
                space_footprints.append(area.to_snapshot())
            detected_spaces.extend(space.to_snapshot() for space in level.detected_spaces)
            virtual_boundaries.extend(boundary.to_snapshot() for boundary in level.all_virtual_boundaries())

        return {
            "modelName": model_name,
            "canvas": canvas,
            "crs": crs
            or {
                "type": "local",
                "unit": "meters",
                "origin": {"x": 0, "y": 0, "z": 0},
                "axisOrder": "xyz",
                "description": "Local 2D coordinate system with level-based Z.",
            },
            "levels": [strip_none(level.to_level_document()) for level in self.sorted_levels()],
            "activeLevel": self.active_level_id,
            "authoringElements": authoring_elements,
            "spaceFootprints": space_footprints,
            "detectedSpaces": detected_spaces,
            "virtualBoundaries": virtual_boundaries,
            "verticalConnectors": [connector.to_snapshot() for connector in self.vertical_connectors],
        }


def strip_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


def polygon_geojson_from_coords(coords: list[tuple[float, float]]) -> dict[str, Any]:
    ring = [[float(x), float(y)] for x, y in coords]
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    return {"type": "Polygon", "coordinates": [ring]}

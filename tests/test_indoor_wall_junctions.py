import json
import math
import unittest
from pathlib import Path

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from src.indoor_data_model.builder import (
    WALL_CONNECTION_TOLERANCE,
    WALL_MITER_LIMIT,
    IndoorModelBuilder,
)

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - optional repo dependency.
    Draft202012Validator = None


OVERLAP_TOLERANCE = 1e-6
MIN_CELL_AREA = 1e-5


def _wall(name, start, end, thickness):
    return {
        "name": name,
        "type": "muro_interior",
        "centerline": [start, end],
        "thicknessM": thickness,
    }


def _door(name, center, host_wall_name, host_wall_thickness=0.2, width=0.3):
    x, y = center
    return {
        "name": name,
        "type": "puerta_simple",
        "centerline": [(x, y - host_wall_thickness / 2.0), (x, y + host_wall_thickness / 2.0)],
        "thicknessM": host_wall_thickness,
        "hostWallThicknessM": host_wall_thickness,
        "hostWallName": host_wall_name,
        "widthM": width,
    }


def _snapshot(name, elements):
    return {
        "modelName": name,
        "createdAt": "2026-01-01T00:00:00Z",
        "canvas": {"width": 8.0, "height": 8.0},
        "authoringElements": elements,
        "spaceFootprints": [],
    }


def _polygon_from_cell(cell):
    rings = cell["cellSpaceGeom"]["geometry2D"]["coordinates"]
    return Polygon(rings[0], rings[1:])


class IndoorWallJunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = None
        if Draft202012Validator is not None:
            schema_path = Path(__file__).resolve().parents[1] / "schemas" / "indoor" / "indoor_model.schema.json"
            cls.schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def build_case(self, name, elements):
        builder = IndoorModelBuilder(_snapshot(name, elements))
        document = builder.build()
        cells = document["layers"][0]["primalSpace"]["cellSpaceMember"]
        boundaries = document["layers"][0]["primalSpace"]["cellBoundaryMember"]
        nodes = document["layers"][0]["dualSpace"]["nodeMember"]
        cell_polygons = [(cell, _polygon_from_cell(cell)) for cell in cells]

        self.assertFalse(builder.overlap_warnings)
        self.assertGreater(len(cells), 0)
        self.assertEqual(len(nodes), len(cells))
        self.assert_valid_document(document, cells, boundaries)
        self.assert_valid_cell_geometry(cell_polygons)
        self.assert_no_cell_overlaps(cell_polygons)
        return document, cell_polygons

    def assert_valid_document(self, document, cells, boundaries):
        cell_ids = {cell["id"] for cell in cells}
        node_ids = {node["id"] for node in document["layers"][0]["dualSpace"]["nodeMember"]}

        for cell in cells:
            self.assertIn("duality", cell)
            self.assertTrue(cell["duality"].split(":")[-1] in node_ids)

        for boundary in boundaries:
            self.assertTrue(set(boundary.get("cellRefs", [])).issubset(cell_ids))

        if self.schema is not None:
            errors = sorted(Draft202012Validator(self.schema).iter_errors(document), key=lambda error: list(error.path))
            self.assertEqual([], errors, [error.message for error in errors[:3]])

    def assert_valid_cell_geometry(self, cell_polygons):
        for cell, polygon in cell_polygons:
            self.assertTrue(polygon.is_valid, cell["id"])
            self.assertGreater(polygon.area, MIN_CELL_AREA, cell["id"])

    def assert_no_cell_overlaps(self, cell_polygons):
        for index, (cell_a, polygon_a) in enumerate(cell_polygons):
            for cell_b, polygon_b in cell_polygons[index + 1 :]:
                area = polygon_a.intersection(polygon_b).area
                self.assertLessEqual(area, OVERLAP_TOLERANCE, (cell_a["id"], cell_b["id"], area))

    def assert_junction_coverage(self, cell_polygons, point=(0.0, 0.0)):
        non_navigable = [
            polygon
            for cell, polygon in cell_polygons
            if cell["navigationType"] == "NonNavigableSpace" and cell["function"] == "Wall"
        ]
        self.assertTrue(unary_union(non_navigable).covers(Point(point)))
        self.assertGreaterEqual(len(self.cells_by_category(cell_polygons, "WallJunction")), 1)

    def cells_by_category(self, cell_polygons, category):
        return [(cell, polygon) for cell, polygon in cell_polygons if cell["category"] == category]

    def wall_segments_for_source(self, cell_polygons, source_name):
        return [
            (cell, polygon)
            for cell, polygon in cell_polygons
            if cell["category"] == "WallSegment"
            and source_name in cell.get("attributes", {}).get("sourceWallNames", [])
        ]

    def assert_receiver_split(self, cell_polygons, source_name):
        self.assertEqual(2, len(self.wall_segments_for_source(cell_polygons, source_name)))

    def test_l_90_equal_thickness(self):
        _, cells = self.build_case(
            "l_90_equal",
            [
                _wall("west", (-2.0, 0.0), (0.0, 0.0), 0.2),
                _wall("south", (0.0, -2.0), (0.0, 0.0), 0.2),
            ],
        )
        self.assert_junction_coverage(cells)

    def test_v_60_equal_thickness(self):
        angle = math.radians(60.0)
        _, cells = self.build_case(
            "v_60_equal",
            [
                _wall("base", (-2.0, 0.0), (0.0, 0.0), 0.2),
                _wall("diag", (-2.0 * math.cos(angle), -2.0 * math.sin(angle)), (0.0, 0.0), 0.2),
            ],
        )
        self.assert_junction_coverage(cells)

    def test_v_45_different_thicknesses(self):
        angle = math.radians(45.0)
        _, cells = self.build_case(
            "v_45_different",
            [
                _wall("thick", (-2.0, 0.0), (0.0, 0.0), 0.3),
                _wall("thin", (-2.0 * math.cos(angle), -2.0 * math.sin(angle)), (0.0, 0.0), 0.12),
            ],
        )
        self.assert_junction_coverage(cells)

    def test_t_90_thin_against_thick(self):
        _, cells = self.build_case(
            "t_90_thin_thick",
            [
                _wall("receiver", (-2.0, 0.0), (2.0, 0.0), 0.3),
                _wall("terminal", (0.0, -2.0), (0.0, 0.0), 0.1),
            ],
        )
        self.assert_junction_coverage(cells)
        self.assert_receiver_split(cells, "receiver")

    def test_t_45_thin_against_thick(self):
        root = math.sqrt(2.0)
        _, cells = self.build_case(
            "t_45_thin_thick",
            [
                _wall("receiver", (-2.0, 0.0), (2.0, 0.0), 0.3),
                _wall("terminal", (-root, -root), (0.0, 0.0), 0.1),
            ],
        )
        self.assert_junction_coverage(cells)
        self.assert_receiver_split(cells, "receiver")

    def test_x_90(self):
        _, cells = self.build_case(
            "x_90",
            [
                _wall("horizontal", (-2.0, 0.0), (2.0, 0.0), 0.2),
                _wall("vertical", (0.0, -2.0), (0.0, 2.0), 0.2),
            ],
        )
        self.assert_junction_coverage(cells)
        self.assertEqual(1, len(self.cells_by_category(cells, "WallJunction")))
        self.assert_receiver_split(cells, "horizontal")
        self.assert_receiver_split(cells, "vertical")

    def test_x_45(self):
        root = math.sqrt(2.0)
        _, cells = self.build_case(
            "x_45",
            [
                _wall("horizontal", (-2.0, 0.0), (2.0, 0.0), 0.2),
                _wall("diagonal", (-root, -root), (root, root), 0.2),
            ],
        )
        self.assert_junction_coverage(cells)
        self.assertEqual(1, len(self.cells_by_category(cells, "WallJunction")))
        self.assert_receiver_split(cells, "horizontal")
        self.assert_receiver_split(cells, "diagonal")

    def test_acute_angle_uses_miter_limit(self):
        angle = math.radians(8.0)
        _, cells = self.build_case(
            "acute_miter_limit",
            [
                _wall("base", (-2.0, 0.0), (0.0, 0.0), 0.2),
                _wall("acute", (-2.0 * math.cos(angle), -2.0 * math.sin(angle)), (0.0, 0.0), 0.2),
            ],
        )
        self.assert_junction_coverage(cells)
        junction = self.cells_by_category(cells, "WallJunction")[0][1]
        minx, miny, maxx, maxy = junction.bounds
        max_dimension = max(maxx - minx, maxy - miny)
        self.assertLessEqual(max_dimension, 2.0 * (WALL_MITER_LIMIT + WALL_CONNECTION_TOLERANCE + 0.01))

    def test_junction_near_door_does_not_fill_opening(self):
        _, cells = self.build_case(
            "junction_near_door",
            [
                _wall("receiver", (-2.0, 0.0), (2.0, 0.0), 0.2),
                _wall("terminal", (0.0, -2.0), (0.0, 0.0), 0.2),
                _door("door", (0.55, 0.0), "receiver"),
            ],
        )
        self.assert_junction_coverage(cells)

        door_cells = [(cell, polygon) for cell, polygon in cells if cell["navigationType"] == "TransferSpace"]
        self.assertEqual(1, len(door_cells))
        door_polygon = door_cells[0][1]
        wall_union = unary_union(
            [
                polygon
                for cell, polygon in cells
                if cell["navigationType"] == "NonNavigableSpace" and cell["function"] == "Wall"
            ]
        )
        self.assertLessEqual(wall_union.intersection(door_polygon).area, OVERLAP_TOLERANCE)
        self.assertFalse(wall_union.covers(Point(0.55, 0.0)))


if __name__ == "__main__":
    unittest.main()

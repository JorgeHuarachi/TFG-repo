import unittest

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from tools.reexport_indoor_model import _connector_from_model, _json_ready, snapshot_from_indoor_model_source
from indoor_data_model import build_indoor_model


class ReexportIndoorModelTests(unittest.TestCase):
    def test_json_ready_removes_none_and_converts_tuples(self):
        normalized = _json_ready({"side": None, "footprint": [(1.0, 2.0), (3.0, 4.0)]})

        self.assertNotIn("side", normalized)
        self.assertEqual(normalized["footprint"], [[1.0, 2.0], [3.0, 4.0]])

    def test_reexport_rebuilds_snapshot_from_source_features(self):
        model = {
            "id": "IF_REEXPORT_SOURCE",
            "featureType": "IndoorFeatures",
            "metadata": {"name": "reexport_source"},
            "crs": {"type": "local", "unit": "meters", "origin": {"x": 0, "y": 0, "z": 0}, "axisOrder": "xyz"},
            "levels": [
                {
                    "id": "LEVEL_00",
                    "name": "Level 00",
                    "order": 0,
                    "levelIndex": 0,
                    "elevationM": 0.0,
                    "floorZ": 0.0,
                    "ceilingZ": 3.0,
                    "heightM": 3.0,
                    "spatialExtent2D": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [6, 0], [6, 4], [0, 4], [0, 0]]],
                    },
                }
            ],
            "verticalConnectors": [],
            "sourceFeatures": [
                self._line_source("SF_WALL_001", "wall_centerline", "Muro_exterior_1", "muro_exterior", [0, 0], [6, 0], 0.2),
                self._line_source("SF_WALL_002", "wall_centerline", "Muro_exterior_2", "muro_exterior", [6, 0], [6, 4], 0.2),
                self._line_source("SF_WALL_003", "wall_centerline", "Muro_exterior_3", "muro_exterior", [6, 4], [0, 4], 0.2),
                self._line_source("SF_WALL_004", "wall_centerline", "Muro_exterior_4", "muro_exterior", [0, 4], [0, 0], 0.2),
                self._line_source(
                    "SF_DOOR_001",
                    "door_centerline",
                    "Puerta_simple_1",
                    "puerta_simple",
                    [2.5, 0],
                    [3.4, 0],
                    0.2,
                    width=0.9,
                    host="Muro_exterior_1",
                ),
                {
                    "id": "SF_ROOM_001",
                    "featureType": "SourceFeature",
                    "sourceType": "room_polygon",
                    "level": "LEVEL_00",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[2.4, 2.4], [2.8, 2.4], [2.8, 2.0], [2.4, 2.0], [2.4, 2.4]]],
                    },
                    "attributes": {"originalName": "Columna_1", "originalType": "columna"},
                },
            ],
        }

        snapshot = snapshot_from_indoor_model_source(model, "reexported_model", run_detection=True)
        rebuilt = build_indoor_model(snapshot)
        cells = [
            cell
            for layer in rebuilt["layers"]
            for cell in layer["primalSpace"]["cellSpaceMember"]
        ]

        self.assertTrue(snapshot["detectedSpaces"])
        self.assertTrue(any(cell["navigationType"] == "GeneralSpace" for cell in cells))
        self.assertTrue(any(cell["navigationType"] == "TransferSpace" for cell in cells))
        self.assertTrue(any(cell["navigationType"] == "ObjectSpace" for cell in cells))

    def test_reexport_normalizes_inter_level_connector_coverages(self):
        connector = _connector_from_model(
            {
                "id": "VC_OLD",
                "connectorType": "Stair",
                "scope": "inter_level",
                "sourceLevel": "LEVEL_00",
                "targetLevel": "LEVEL_01",
                "endpoints": [
                    {
                        "id": "EP_VC_OLD_LEVEL_00",
                        "level": "LEVEL_00",
                        "footprint": [(1, 1), (3, 1), (3, 2), (1, 2)],
                        "entrySide": "west",
                        "openSides": ["west"],
                        "attributes": {"sideCoverages": []},
                    },
                    {
                        "id": "EP_VC_OLD_LEVEL_01",
                        "level": "LEVEL_01",
                        "footprint": [(1, 1), (3, 1), (3, 2), (1, 2)],
                        "exitSide": "east",
                        "openSides": ["east"],
                        "attributes": {"sideCoverages": []},
                    },
                ],
            }
        )

        source_endpoint, target_endpoint = connector.endpoints
        source_coverage = unary_union([Polygon(ring) for ring in source_endpoint.attributes["sideCoverages"]])
        target_coverage = unary_union([Polygon(ring) for ring in target_endpoint.attributes["sideCoverages"]])
        minx, miny, maxx, maxy = Polygon(source_endpoint.footprint).bounds
        west_probe = box(minx - 0.10, miny + 0.20, minx, maxy - 0.20)
        east_probe = box(maxx, miny + 0.20, maxx + 0.10, maxy - 0.20)

        self.assertLessEqual(source_coverage.intersection(west_probe).area, 1e-6)
        self.assertGreater(source_coverage.intersection(east_probe).area, 1e-4)
        self.assertGreater(target_coverage.intersection(west_probe).area, 1e-4)
        self.assertLessEqual(target_coverage.intersection(east_probe).area, 1e-6)

    @staticmethod
    def _line_source(source_id, source_type, name, original_type, start, end, thickness, width=None, host=None):
        attrs = {
            "originalName": name,
            "originalType": original_type,
            "thicknessM": thickness,
        }
        if width is not None:
            attrs["widthM"] = width
        if host is not None:
            attrs["hostWallName"] = host
            attrs["hostWallType"] = "muro_exterior"
            attrs["hostWallThicknessM"] = thickness
            attrs["hostWallRef"] = host
        return {
            "id": source_id,
            "featureType": "SourceFeature",
            "sourceType": source_type,
            "level": "LEVEL_00",
            "geometry": {"type": "LineString", "coordinates": [start, end]},
            "attributes": attrs,
        }


if __name__ == "__main__":
    unittest.main()

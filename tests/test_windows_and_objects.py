import unittest

from shapely.geometry import Polygon

from src.indoor_data_model import build_indoor_model


class WindowsAndObjectsTests(unittest.TestCase):
    def test_window_is_non_traversable_transfer_space(self):
        snapshot = {
            "modelName": "window",
            "canvas": {"width": 4, "height": 4},
            "authoringElements": [
                {"name": "wall", "type": "muro_exterior", "level": "LEVEL_00", "centerline": [(0, 0), (4, 0)], "thicknessM": 0.2},
                {
                    "name": "window",
                    "type": "ventana",
                    "level": "LEVEL_00",
                    "centerline": [(1, 0), (2.2, 0)],
                    "thicknessM": 0.2,
                    "widthM": 1.2,
                    "attributes": {"defaultTraversable": False},
                },
            ],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot, edge_mode="all_adjacency")
        cells = model["layers"][0]["primalSpace"]["cellSpaceMember"]
        window = next(cell for cell in cells if cell["category"] == "Window")
        self.assertEqual("TransferSpace", window["navigationType"])
        self.assertFalse(window["attributes"]["defaultTraversable"])

    def test_column_recuts_general_space_without_overlap(self):
        snapshot = {
            "modelName": "column",
            "canvas": {"width": 5, "height": 5},
            "authoringElements": [],
            "spaceFootprints": [
                {"name": "room", "level": "LEVEL_00", "footprint": [(0, 0), (5, 0), (5, 5), (0, 5)], "attributes": {"categoria": "Room"}},
                {
                    "name": "column",
                    "level": "LEVEL_00",
                    "footprint": [(2, 2), (3, 2), (3, 3), (2, 3)],
                    "authoringType": "columna",
                    "attributes": {"category": "Column", "navigationType": "ObjectSpace"},
                },
            ],
        }
        model = build_indoor_model(snapshot)
        cells = model["layers"][0]["primalSpace"]["cellSpaceMember"]
        room = next(cell for cell in cells if cell["navigationType"] == "GeneralSpace")
        column = next(cell for cell in cells if cell["navigationType"] == "ObjectSpace")
        room_poly = Polygon(room["cellSpaceGeom"]["geometry2D"]["coordinates"][0], room["cellSpaceGeom"]["geometry2D"]["coordinates"][1:])
        column_poly = Polygon(column["cellSpaceGeom"]["geometry2D"]["coordinates"][0])
        self.assertEqual("Column", column["category"])
        self.assertLessEqual(room_poly.intersection(column_poly).area, 1e-6)


if __name__ == "__main__":
    unittest.main()

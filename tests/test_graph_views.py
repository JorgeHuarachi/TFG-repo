import unittest

from src.indoor_authoring import BuildingAuthoringState
from src.indoor_authoring.connectors import create_tile_chain_connector
from src.indoor_data_model import build_indoor_model, derive_graph_views


class GraphViewsTests(unittest.TestCase):
    def test_virtual_boundary_creates_logical_transfer_node_only(self):
        snapshot = {
            "modelName": "virtual",
            "levels": [{"id": "LEVEL_00", "name": "L0", "levelIndex": 0, "order": 0}],
            "detectedSpaces": [
                {"id": "CS_L00_A", "level": "LEVEL_00", "polygon": [[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
                {"id": "CS_L00_B", "level": "LEVEL_00", "polygon": [[(2, 0), (4, 0), (4, 2), (2, 2), (2, 0)]], "sourceFaceId": "F2", "attributes": {}},
            ],
            "virtualBoundaries": [{"id": "VB1", "level": "LEVEL_00", "line": [(2, 0), (2, 2)], "traversable": True}],
            "authoringElements": [],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot)
        cells = model["layers"][0]["primalSpace"]["cellSpaceMember"]
        self.assertFalse(any(cell["category"] == "VirtualBoundary" for cell in cells))
        boundaries = model["layers"][0]["primalSpace"]["cellBoundaryMember"]
        self.assertEqual(1, len([boundary for boundary in boundaries if boundary["isVirtual"]]))

        views = derive_graph_views(model)
        rtc_nodes = views["room_transfer_connectivity"]["nodes"]
        self.assertEqual(views["space_connectivity"], views["space_transfer_connectivity"])
        self.assertEqual(views["space_connectivity"], views["room_transfer_connectivity"])
        self.assertTrue(any(node["nodeType"] == "VirtualTransferNode" for node in rtc_nodes))
        self.assertEqual(1, len(views["space_adjacency"]["edges"]))
        self.assertEqual(0, len(views["room_adjacency"]["edges"]))

    def test_room_door_room_and_door_to_door(self):
        snapshot = {
            "modelName": "doors",
            "detectedSpaces": [
                {"id": "CS_L00_ROOM_A", "level": "LEVEL_00", "polygon": [[(0, 0), (2, 0), (2, 3), (0, 3), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
                {"id": "CS_L00_ROOM_B", "level": "LEVEL_00", "polygon": [[(3, 0), (5, 0), (5, 3), (3, 3), (3, 0)]], "sourceFaceId": "F2", "attributes": {}},
            ],
            "authoringElements": [
                {"name": "door_a", "type": "puerta_simple", "level": "LEVEL_00", "centerline": [(2, 1), (3, 1)], "thicknessM": 0.2, "widthM": 1.0},
                {"name": "door_b", "type": "puerta_simple", "level": "LEVEL_00", "centerline": [(2, 2), (3, 2)], "thicknessM": 0.2, "widthM": 1.0},
            ],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot)
        views = derive_graph_views(model)
        self.assertGreaterEqual(len(views["room_transfer_connectivity"]["edges"]), 2)
        self.assertGreaterEqual(len(views["space_adjacency"]["edges"]), 1)
        self.assertGreaterEqual(len(views["transfer_to_transfer"]["edges"]), 1)
        self.assertGreaterEqual(len(views["door_to_door"]["edges"]), 1)

    def test_transfer_to_transfer_includes_virtual_boundaries_and_windows(self):
        snapshot = {
            "modelName": "transfer_all",
            "detectedSpaces": [
                {"id": "CS_L00_A", "level": "LEVEL_00", "polygon": [[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
                {"id": "CS_L00_B", "level": "LEVEL_00", "polygon": [[(2, 0), (4, 0), (4, 2), (2, 2), (2, 0)]], "sourceFaceId": "F2", "attributes": {}},
            ],
            "virtualBoundaries": [{"id": "VB1", "level": "LEVEL_00", "line": [(2, 0), (2, 2)], "traversable": True}],
            "authoringElements": [
                {"name": "wall", "type": "muro_exterior", "level": "LEVEL_00", "centerline": [(0, 0), (2, 0)], "thicknessM": 0.2},
                {
                    "name": "window",
                    "type": "ventana",
                    "level": "LEVEL_00",
                    "centerline": [(0.4, 0), (1.6, 0)],
                    "thicknessM": 0.2,
                    "widthM": 1.2,
                    "hostWallName": "wall",
                    "hostWallRef": "wall",
                    "hostWallType": "muro_exterior",
                    "hostWallThicknessM": 0.2,
                    "attributes": {"defaultTraversable": False},
                },
            ],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot)
        views = derive_graph_views(model)

        t2t_node_types = {node["nodeType"] for node in views["transfer_to_transfer"]["nodes"]}
        t2t_categories = {node.get("transferCategory") for node in views["transfer_to_transfer"]["nodes"]}
        self.assertIn("VirtualTransferNode", t2t_node_types)
        self.assertIn("Window", t2t_categories)
        self.assertFalse(any(node.get("transferCategory") == "Window" for node in views["door_to_door"]["nodes"]))

    def test_transfer_to_transfer_stays_inside_split_general_space(self):
        snapshot = {
            "modelName": "split_t2t",
            "detectedSpaces": [
                {"id": "CS_L00_A", "level": "LEVEL_00", "polygon": [[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
                {"id": "CS_L00_B", "level": "LEVEL_00", "polygon": [[(2, 0), (4, 0), (4, 2), (2, 2), (2, 0)]], "sourceFaceId": "F2", "attributes": {}},
            ],
            "virtualBoundaries": [{"id": "VB1", "level": "LEVEL_00", "line": [(2, 0), (2, 2)], "traversable": True}],
            "authoringElements": [
                {"name": "door_a", "type": "puerta_simple", "level": "LEVEL_00", "centerline": [(-0.1, 0.4), (-0.1, 1.3)], "thicknessM": 0.2, "widthM": 0.9},
                {"name": "door_b", "type": "puerta_simple", "level": "LEVEL_00", "centerline": [(4.1, 0.4), (4.1, 1.3)], "thicknessM": 0.2, "widthM": 0.9},
                {
                    "name": "window_a",
                    "type": "ventana",
                    "level": "LEVEL_00",
                    "centerline": [(0.4, 2.1), (1.6, 2.1)],
                    "thicknessM": 0.2,
                    "widthM": 1.2,
                    "attributes": {"defaultTraversable": False},
                },
            ],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot)
        transfer_to_transfer = derive_graph_views(model)["transfer_to_transfer"]

        for edge in transfer_to_transfer["edges"]:
            self.assertEqual(1, len(edge["viaSpaceRefs"]))
        self.assertFalse(
            any({"CS_L00_DOOR_001", "CS_L00_DOOR_002"} <= set(edge["connects"]) for edge in transfer_to_transfer["edges"])
        )

    def test_room_adjacency_groups_general_spaces_across_wall_and_room_to_room_uses_doors(self):
        snapshot = {
            "modelName": "room_adjacency",
            "detectedSpaces": [
                {"id": "CS_L00_LEFT", "level": "LEVEL_00", "polygon": [[(0, 0), (2, 0), (2, 3), (0, 3), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
                {"id": "CS_L00_RIGHT", "level": "LEVEL_00", "polygon": [[(2.2, 0), (4.2, 0), (4.2, 3), (2.2, 3), (2.2, 0)]], "sourceFaceId": "F2", "attributes": {}},
            ],
            "authoringElements": [
                {"name": "wall", "type": "muro_interior", "level": "LEVEL_00", "centerline": [(2.1, 0), (2.1, 3)], "thicknessM": 0.2},
                {"name": "door", "type": "puerta_simple", "level": "LEVEL_00", "centerline": [(2.1, 1), (2.1, 1.9)], "thicknessM": 0.2, "widthM": 0.9},
            ],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot, edge_mode="all_adjacency")
        views = derive_graph_views(model)

        self.assertEqual(1, len(views["room_adjacency"]["edges"]))
        self.assertEqual(1, len(views["room_to_room_accessibility"]["edges"]))

    def test_room_to_room_uses_same_level_ramp_connector(self):
        snapshot = {
            "modelName": "connector_room_to_room",
            "detectedSpaces": [
                {"id": "CS_L00_LEFT", "level": "LEVEL_00", "polygon": [[(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
                {"id": "CS_L00_RIGHT", "level": "LEVEL_00", "polygon": [[(3, 0), (4, 0), (4, 1), (3, 1), (3, 0)]], "sourceFaceId": "F2", "attributes": {}},
            ],
            "authoringElements": [],
            "spaceFootprints": [],
            "verticalConnectors": [
                {
                    "id": "VC_RAMP",
                    "connectorType": "Ramp",
                    "scope": "same_level",
                    "endpoints": [
                        {"id": "EP_RAMP_A", "level": "LEVEL_00", "footprint": [(1, 0), (2, 0), (2, 1), (1, 1)], "openSides": ["west"], "attributes": {}},
                        {"id": "EP_RAMP_B", "level": "LEVEL_00", "footprint": [(2, 0), (3, 0), (3, 1), (2, 1)], "openSides": ["east"], "attributes": {}},
                    ],
                    "sourceLevel": "LEVEL_00",
                    "targetLevel": "LEVEL_00",
                    "locomotionTypes": ["Walking", "Rolling"],
                    "attributes": {"tileSizeM": 1.0},
                }
            ],
        }
        model = build_indoor_model(snapshot)
        room_to_room = derive_graph_views(model)["room_to_room_accessibility"]

        self.assertEqual(1, len(room_to_room["edges"]))
        self.assertIn("connector", room_to_room["edges"][0]["attributes"]["contactTypes"])

    def test_navigation_mode_excludes_non_traversable_wall_edges(self):
        snapshot = {
            "modelName": "wall_edges",
            "detectedSpaces": [
                {"id": "CS_L00_ROOM_A", "level": "LEVEL_00", "polygon": [[(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]], "sourceFaceId": "F1", "attributes": {}},
            ],
            "authoringElements": [
                {"name": "wall", "type": "muro_interior", "level": "LEVEL_00", "centerline": [(2, 0), (2, 2)], "thicknessM": 0.2},
            ],
            "spaceFootprints": [],
        }
        model = build_indoor_model(snapshot)
        edges = model["layers"][0]["dualSpace"]["edgeMember"]
        self.assertFalse(any(edge.get("relationshipType") == "adjacency" and not edge.get("traversable") for edge in edges))

    def test_vertical_graph_view_and_no_walljunction_navigation_edge(self):
        state = BuildingAuthoringState()
        create_tile_chain_connector(state, "Ramp", [(1, 1), (2, 1)], "west", "east")
        model = build_indoor_model(state.to_snapshot("vertical", {"width": 5, "height": 4}))
        vertical = derive_graph_views(model)["vertical_connectivity"]
        self.assertEqual(1, len(vertical["edges"]))

        nav_edges = model["layers"][0]["dualSpace"]["edgeMember"]
        self.assertFalse(any("WALLJUNC" in " ".join(edge.get("connects", [])) for edge in nav_edges if edge.get("traversable")))


if __name__ == "__main__":
    unittest.main()

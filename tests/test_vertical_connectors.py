import unittest
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from src.indoor_authoring import BuildingAuthoringState, detect_spaces
from src.indoor_authoring.connectors import create_elevator_connector, create_tile_chain_connector
from src.indoor_data_model import build_indoor_model, derive_graph_views


def add_shell(state, width=5.0, height=4.0):
    walls = [
        ((0, 0), (width, 0)),
        ((width, 0), (width, height)),
        ((width, height), (0, height)),
        ((0, height), (0, 0)),
    ]
    for index, (start, end) in enumerate(walls):
        state.add_line_to_active(f"wall_{index}", "muro_exterior", start, end, thickness_m=0.2)


def cell_polygon(cell):
    coords = cell["cellSpaceGeom"]["geometry2D"]["coordinates"]
    return Polygon(coords[0], coords[1:])


def assert_cellspace_endpoint(testcase, endpoint_id):
    testcase.assertTrue(endpoint_id.startswith("CS_"), endpoint_id)
    testcase.assertNotIn(":", endpoint_id)
    testcase.assertFalse(endpoint_id.startswith("N_"), endpoint_id)


def reachable_component(node_id, edges):
    graph = {}
    for edge in edges:
        connects = edge.get("connects") or []
        if len(connects) != 2:
            continue
        left, right = connects
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)
    seen = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(sorted(graph.get(current, set()) - seen))
    return seen


class VerticalConnectorsTests(unittest.TestCase):
    def test_ramp_same_level_has_endpoint_edge(self):
        state = BuildingAuthoringState()
        create_tile_chain_connector(state, "Ramp", [(1, 1), (2, 1)], "west", "east")
        model = build_indoor_model(state.to_snapshot("ramp", {"width": 5, "height": 4}))
        edges = model["layers"][0]["dualSpace"]["edgeMember"]
        vertical_edges = [edge for edge in edges if edge["relationshipType"] == "vertical_connectivity"]
        self.assertEqual(1, len(vertical_edges))
        self.assertEqual(["Walking", "Rolling"], vertical_edges[0]["locomotionTypes"])
        boundaries = model["layers"][0]["primalSpace"]["cellBoundaryMember"]
        connector_boundaries = [
            boundary
            for boundary in boundaries
            if boundary.get("attributes", {}).get("boundaryRole") == "same_level_connector_internal_contact"
        ]
        self.assertEqual(1, len(connector_boundaries))
        self.assertEqual("NavigableBoundary", connector_boundaries[0]["navigationBoundaryType"])
        self.assertEqual("vertical_connectivity", connector_boundaries[0]["attributes"]["relationshipType"])

        views = derive_graph_views(model)
        vertical = views["vertical_connectivity"]
        space = views["space_connectivity"]
        vertical_nodes = {node["id"] for node in vertical["nodes"]}
        space_nodes = {node["id"] for node in space["nodes"]}
        self.assertEqual(1, len(vertical["edges"]))
        derived_edge = vertical["edges"][0]
        self.assertEqual("vertical_connectivity", derived_edge["relationshipType"])
        self.assertEqual(["Walking", "Rolling"], derived_edge["locomotionTypes"])
        self.assertTrue(derived_edge["sourceConnectedNodeRefs"])
        self.assertTrue(all(":" in ref and ":N_" in ref for ref in derived_edge["sourceConnectedNodeRefs"]))
        for endpoint_id in derived_edge["connects"]:
            assert_cellspace_endpoint(self, endpoint_id)
            self.assertIn(endpoint_id, vertical_nodes)
            self.assertIn(endpoint_id, space_nodes)

    def test_stair_inter_level_and_elevator_three_levels(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.set_active_level("LEVEL_00")
        create_tile_chain_connector(state, "Stair", [(1, 1), (2, 1)], "west", "east", scope="inter_level", target_level_id="LEVEL_01")
        state.add_level()
        create_elevator_connector(state, [(3, 1), (4, 1), (4, 2), (3, 2)], ["LEVEL_00", "LEVEL_01", "LEVEL_02"])

        model = build_indoor_model(state.to_snapshot("vertical", {"width": 6, "height": 4}))
        self.assertEqual(3, len(model["levels"]))
        self.assertGreaterEqual(len(model["layerConnections"]), 3)
        for connector in model["verticalConnectors"]:
            for endpoint in connector["endpoints"]:
                if "entrySide" in endpoint:
                    self.assertIsNotNone(endpoint["entrySide"])
                if "exitSide" in endpoint:
                    self.assertIsNotNone(endpoint["exitSide"])
        vertical = derive_graph_views(model)["vertical_connectivity"]
        self.assertGreaterEqual(len(vertical["edges"]), 3)

    def test_inter_level_stair_uses_cellspace_ids_in_multilevel_views(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.set_active_level("LEVEL_00")
        create_tile_chain_connector(
            state,
            "Stair",
            [(1, 1), (2, 1)],
            "west",
            "east",
            scope="inter_level",
            target_level_id="LEVEL_01",
        )

        views = derive_graph_views(build_indoor_model(state.to_snapshot("stair_interlevel", {"width": 5, "height": 4})))
        vertical = views["vertical_connectivity"]
        multilevel = views["multilevel_space_connectivity"]
        vertical_nodes = {node["id"]: node for node in vertical["nodes"]}
        multilevel_nodes = {node["id"] for node in multilevel["nodes"]}
        stair_edges = [edge for edge in vertical["edges"] if edge.get("connectorType") == "Stair"]

        self.assertEqual(1, len(stair_edges))
        edge = stair_edges[0]
        self.assertEqual(2, len(edge["connects"]))
        self.assertNotEqual(vertical_nodes[edge["connects"][0]]["level"], vertical_nodes[edge["connects"][1]]["level"])
        self.assertTrue(edge["sourceConnectedCellRefs"])
        self.assertTrue(edge["sourceConnectedNodeRefs"])
        for endpoint_id in edge["connects"]:
            assert_cellspace_endpoint(self, endpoint_id)
            self.assertIn(endpoint_id, vertical_nodes)
            self.assertIn(endpoint_id, multilevel_nodes)
        self.assertIn(tuple(edge["connects"]), [tuple(item["connects"]) for item in multilevel["edges"]])
        self.assertTrue(all(endpoint in multilevel_nodes for item in multilevel["edges"] for endpoint in item.get("connects", [])))

    def test_three_level_elevator_is_connected_in_multilevel_space_connectivity(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.add_level()
        create_elevator_connector(state, [(1, 1), (2, 1), (2, 2), (1, 2)], ["LEVEL_00", "LEVEL_01", "LEVEL_02"])

        views = derive_graph_views(build_indoor_model(state.to_snapshot("elevator_three_levels", {"width": 4, "height": 4})))
        vertical = views["vertical_connectivity"]
        multilevel = views["multilevel_space_connectivity"]
        elevator_edges = [edge for edge in vertical["edges"] if edge.get("connectorType") == "Elevator"]
        elevator_nodes = [node for node in vertical["nodes"] if node.get("connectorType") == "Elevator"]
        by_level = {node["level"]: node["id"] for node in elevator_nodes}

        self.assertEqual({"LEVEL_00", "LEVEL_01", "LEVEL_02"}, set(by_level))
        pairs = {tuple(edge["connects"]) for edge in elevator_edges}
        self.assertIn((by_level["LEVEL_00"], by_level["LEVEL_01"]), pairs)
        self.assertIn((by_level["LEVEL_01"], by_level["LEVEL_02"]), pairs)
        reached = reachable_component(by_level["LEVEL_00"], multilevel["edges"])
        self.assertTrue(set(by_level.values()) <= reached)

    def test_inter_layer_connection_falls_back_to_connected_nodes(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.set_active_level("LEVEL_00")
        create_tile_chain_connector(
            state,
            "Stair",
            [(1, 1), (2, 1)],
            "west",
            "east",
            scope="inter_level",
            target_level_id="LEVEL_01",
        )
        model = build_indoor_model(state.to_snapshot("fallback_nodes", {"width": 5, "height": 4}))
        for connection in model["layerConnections"]:
            connection.pop("connectedCells", None)

        vertical = derive_graph_views(model)["vertical_connectivity"]
        self.assertFalse(vertical.get("diagnostics"))
        self.assertEqual(1, len(vertical["edges"]))
        edge = vertical["edges"][0]
        self.assertTrue(edge["sourceConnectedNodeRefs"])
        self.assertNotIn("sourceConnectedCellRefs", edge)
        for endpoint_id in edge["connects"]:
            assert_cellspace_endpoint(self, endpoint_id)

    def test_invalid_inter_layer_endpoint_reports_diagnostic_without_dangling_edge(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.set_active_level("LEVEL_00")
        create_tile_chain_connector(
            state,
            "Stair",
            [(1, 1), (2, 1)],
            "west",
            "east",
            scope="inter_level",
            target_level_id="LEVEL_01",
        )
        model = build_indoor_model(state.to_snapshot("invalid_layer_connection", {"width": 5, "height": 4}))
        model["layerConnections"].append(
            {
                "id": "ILC_INVALID",
                "featureType": "InterLayerConnection",
                "connectedLayers": ["TL_NAV_L00", "TL_NAV_L01"],
                "connectedCells": ["TL_NAV_L00:PS_NAV_L00:CS_L00_MISSING", "TL_NAV_L01:PS_NAV_L01:CS_L01_MISSING"],
                "typeOfTopoExpression": "OTHERS",
                "attributes": {"relationshipType": "vertical_connectivity", "connectorId": "VC_INVALID"},
            }
        )

        vertical = derive_graph_views(model)["vertical_connectivity"]
        self.assertEqual(1, len(vertical["edges"]))
        self.assertFalse(any(edge.get("id") == "ILC_INVALID" for edge in vertical["edges"]))
        self.assertIn("UNRESOLVED_VERTICAL_ENDPOINT", {item.get("code") for item in vertical.get("diagnostics", [])})

    def test_duplicate_vertical_sources_are_merged(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.set_active_level("LEVEL_00")
        create_tile_chain_connector(
            state,
            "Stair",
            [(1, 1), (2, 1)],
            "west",
            "east",
            scope="inter_level",
            target_level_id="LEVEL_01",
        )
        model = build_indoor_model(state.to_snapshot("dedupe_layer_connection", {"width": 5, "height": 4}))
        duplicate = dict(model["layerConnections"][0])
        duplicate["id"] = "ILC_DUPLICATE"
        duplicate["connectedCells"] = list(model["layerConnections"][0]["connectedCells"])
        duplicate["connectedNodes"] = list(model["layerConnections"][0]["connectedNodes"])
        duplicate["attributes"] = dict(model["layerConnections"][0]["attributes"])
        model["layerConnections"].append(duplicate)

        vertical = derive_graph_views(model)["vertical_connectivity"]
        self.assertEqual(1, len(vertical["edges"]))
        edge = vertical["edges"][0]
        self.assertEqual(["ILC_VC_001_001", "ILC_DUPLICATE"], edge["sourceRefs"])
        self.assertEqual(2, len(edge["connects"]))

    def test_real_three_floor_example_has_no_vertical_phantom_nodes(self):
        example = Path(__file__).resolve().parents[1] / "examples" / "indoor_data_model" / "tres_plantas_indoor_model.json"
        if not example.exists():
            self.skipTest("tres_plantas_indoor_model.json not available")
        import json

        with example.open("r", encoding="utf-8") as file:
            model = json.load(file)
        views = derive_graph_views(model)

        for view_name in ("vertical_connectivity", "multilevel_space_connectivity"):
            view = views[view_name]
            self.assertFalse(view.get("diagnostics"))
            node_ids = {node["id"] for node in view["nodes"]}
            for edge in view["edges"]:
                if view_name == "multilevel_space_connectivity" and edge.get("relationshipType") != "vertical_connectivity":
                    continue
                self.assertEqual(2, len(edge.get("connects", [])), edge)
                for endpoint_id in edge["connects"]:
                    assert_cellspace_endpoint(self, endpoint_id)
                    self.assertIn(endpoint_id, node_ids)

    def test_inter_level_connector_closes_non_local_mouths(self):
        state = BuildingAuthoringState()
        state.add_level()
        state.set_active_level("LEVEL_00")
        connector = create_tile_chain_connector(
            state,
            "Stair",
            [(1, 1), (2, 1)],
            "west",
            "east",
            scope="inter_level",
            target_level_id="LEVEL_01",
        )

        source_endpoint, target_endpoint = connector.endpoints
        self.assertEqual(["west"], source_endpoint.open_sides)
        self.assertEqual(["east"], target_endpoint.open_sides)
        self.assertEqual(1, len(source_endpoint.attributes["sideCoverages"]))
        self.assertEqual(1, len(target_endpoint.attributes["sideCoverages"]))

        source_coverage = unary_union([Polygon(ring) for ring in source_endpoint.attributes["sideCoverages"]])
        target_coverage = unary_union([Polygon(ring) for ring in target_endpoint.attributes["sideCoverages"]])
        footprint = Polygon(source_endpoint.footprint)
        minx, miny, maxx, maxy = footprint.bounds
        west_probe = box(minx - 0.10, miny + 0.20, minx, maxy - 0.20)
        east_probe = box(maxx, miny + 0.20, maxx + 0.10, maxy - 0.20)

        self.assertLessEqual(source_coverage.intersection(west_probe).area, 1e-6)
        self.assertGreater(source_coverage.intersection(east_probe).area, 1e-4)
        self.assertGreater(target_coverage.intersection(west_probe).area, 1e-4)
        self.assertLessEqual(target_coverage.intersection(east_probe).area, 1e-6)

    def test_single_mouth_connector_coverage_is_continuous(self):
        state = BuildingAuthoringState()
        connector = create_elevator_connector(state, [(1, 1), (2, 1), (2, 2), (1, 2)], ["LEVEL_00"], entry_side="south")
        endpoint = connector.endpoints[0]
        self.assertEqual(["south"], endpoint.open_sides)
        self.assertEqual(1, len(endpoint.attributes["sideCoverages"]))

    def test_side_coverage_is_valid_and_does_not_overlap_footprint(self):
        state = BuildingAuthoringState()
        connector = create_tile_chain_connector(state, "Stair", [(1, 1), (2, 1)], "west", "east")
        endpoint = connector.endpoints[0]
        footprint = Polygon(endpoint.footprint)
        coverages = [Polygon(ring) for ring in endpoint.attributes["sideCoverages"]]
        self.assertTrue(coverages)
        for coverage in coverages:
            self.assertTrue(coverage.is_valid)
            self.assertLessEqual(coverage.intersection(footprint).area, 1e-6)
        for index, left in enumerate(coverages):
            for right in coverages[index + 1 :]:
                self.assertLessEqual(left.intersection(right).area, 1e-6)

    def test_connector_endpoint_and_coverages_do_not_overlap_general_spaces(self):
        state = BuildingAuthoringState()
        add_shell(state)
        create_tile_chain_connector(state, "Ramp", [(1, 1), (2, 1)], "west", "east")
        result = detect_spaces(state)
        self.assertTrue(result.ok)

        model = build_indoor_model(state.to_snapshot("connector_no_overlap", {"width": 5, "height": 4}))
        cells = model["layers"][0]["primalSpace"]["cellSpaceMember"]
        general_cells = [cell for cell in cells if cell["navigationType"] == "GeneralSpace"]
        connector_cells = [
            cell
            for cell in cells
            if cell["attributes"].get("connectorId") or cell["category"] == "ConnectorSideCoverage"
        ]
        self.assertTrue(general_cells)
        self.assertTrue(connector_cells)

        for general in general_cells:
            general_polygon = cell_polygon(general)
            for connector_cell in connector_cells:
                overlap = general_polygon.intersection(cell_polygon(connector_cell)).area
                self.assertLessEqual(overlap, 1e-6, (general["id"], connector_cell["id"], overlap))

    def test_connector_side_coverage_is_clipped_by_wall_junction_mass(self):
        state = BuildingAuthoringState()
        add_shell(state, width=6, height=4)
        state.add_line_to_active("divider_top", "muro_interior", (3, 0), (3, 1), thickness_m=0.15)
        state.add_line_to_active("divider_bottom", "muro_interior", (3, 2), (3, 4), thickness_m=0.15)
        create_tile_chain_connector(state, "Ramp", [(2, 1), (3, 1)], "west", "east")

        model = build_indoor_model(state.to_snapshot("connector_wall_junction", {"width": 6, "height": 4}))
        cells = model["layers"][0]["primalSpace"]["cellSpaceMember"]
        coverage_cells = [cell for cell in cells if cell["category"] == "ConnectorSideCoverage"]
        wall_cells = [cell for cell in cells if cell["category"] in {"WallSegment", "WallJunction"}]
        self.assertTrue(coverage_cells)
        self.assertTrue(wall_cells)

        for coverage in coverage_cells:
            coverage_polygon = cell_polygon(coverage)
            for wall in wall_cells:
                overlap = coverage_polygon.intersection(cell_polygon(wall)).area
                self.assertLessEqual(overlap, 1e-6, (coverage["id"], wall["id"], overlap))


if __name__ == "__main__":
    unittest.main()

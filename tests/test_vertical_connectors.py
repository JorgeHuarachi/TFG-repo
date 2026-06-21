import unittest

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

    def test_inter_level_connector_closes_non_local_mouths(self):
        state = BuildingAuthoringState()
        state.add_level()
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

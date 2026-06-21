import unittest

from shapely.geometry import Polygon
from shapely.ops import unary_union

from src.indoor_authoring import BuildingAuthoringState, VirtualBoundary, detect_spaces
from src.indoor_authoring.space_detection import _obstacle_union
from src.indoor_authoring.connectors import create_tile_chain_connector
from src.indoor_data_model import derive_wall_mass_from_snapshot
from src.indoor_data_model.builder import IndoorModelBuilder


def add_shell(state, width=4.0, height=3.0):
    walls = [
        ((0, 0), (width, 0)),
        ((width, 0), (width, height)),
        ((width, height), (0, height)),
        ((0, height), (0, 0)),
    ]
    for index, (start, end) in enumerate(walls):
        state.add_line_to_active(f"wall_{index}", "muro_exterior", start, end, thickness_m=0.2)


class SpaceDetectionTests(unittest.TestCase):
    def polygons(self, state):
        return [Polygon(space.polygon[0], space.polygon[1:]) for space in state.active_level.detected_spaces]

    def assert_no_overlaps(self, polygons):
        for index, left in enumerate(polygons):
            for right in polygons[index + 1 :]:
                self.assertLessEqual(left.intersection(right).area, 1e-6)

    def test_rectangle_and_two_rooms(self):
        state = BuildingAuthoringState()
        add_shell(state)
        result = detect_spaces(state)
        self.assertTrue(result.ok)
        self.assertEqual(1, len(state.active_level.detected_spaces))

        state = BuildingAuthoringState()
        add_shell(state)
        state.add_line_to_active("divider", "muro_interior", (2, 0), (2, 3), thickness_m=0.2)
        result = detect_spaces(state)
        self.assertTrue(result.ok)
        self.assertEqual(2, len(state.active_level.detected_spaces))
        self.assert_no_overlaps(self.polygons(state))

    def test_open_shell_preserves_previous_detection(self):
        state = BuildingAuthoringState()
        add_shell(state)
        self.assertTrue(detect_spaces(state).ok)
        previous_ids = [space.id for space in state.active_level.detected_spaces]

        state.active_level.wall_centerlines.pop()
        result = detect_spaces(state)
        self.assertFalse(result.ok)
        self.assertEqual(previous_ids, [space.id for space in state.active_level.detected_spaces])

    def test_detection_preserves_manual_authoring_and_reuses_ids(self):
        state = BuildingAuthoringState()
        add_shell(state, 5, 4)
        state.add_line_to_active("door", "puerta_simple", (2, 0), (2.9, 0), thickness_m=0.2, width_m=0.9)
        state.add_line_to_active("window", "ventana", (1, 0), (2.2, 0), thickness_m=0.2, width_m=1.2)
        state.add_area_to_active("column", "columna", [(3, 1), (3.4, 1), (3.4, 1.4), (3, 1.4)])
        create_tile_chain_connector(state, "Stair", [(1, 1), (2, 1)], "west", "east")

        result = detect_spaces(state)
        self.assertTrue(result.ok)
        first_ids = [space.id for space in state.active_level.detected_spaces]
        self.assertEqual(1, len(state.active_level.doors))
        self.assertEqual(1, len(state.active_level.windows))
        self.assertEqual(1, len(state.active_level.columns))
        self.assertEqual(1, len(state.vertical_connectors))

        result = detect_spaces(state)
        self.assertTrue(result.ok)
        self.assertEqual(first_ids, [space.id for space in state.active_level.detected_spaces])

    def test_connector_is_obstacle_when_clipping_general_space(self):
        plain = BuildingAuthoringState()
        add_shell(plain, 5, 4)
        detect_spaces(plain)
        plain_area = unary_union(self.polygons(plain)).area

        with_connector = BuildingAuthoringState()
        add_shell(with_connector, 5, 4)
        create_tile_chain_connector(with_connector, "Ramp", [(1, 1), (2, 1)], "west", "east")
        detect_spaces(with_connector)
        clipped_area = unary_union([poly for poly in self.polygons(with_connector)]).area
        self.assertLess(clipped_area, plain_area)

    def test_detection_wall_obstacles_match_final_wall_mass(self):
        state = BuildingAuthoringState()
        add_shell(state, 6, 4)
        state.add_line_to_active("divider_top", "muro_interior", (3, 0), (3, 1.7), thickness_m=0.15)
        state.add_line_to_active("divider_bottom", "muro_interior", (3, 2.3), (3, 4), thickness_m=0.15)
        snapshot = state.to_snapshot("wall_mass_detection", {"width": 6, "height": 4})

        final_wall_union = derive_wall_mass_from_snapshot(snapshot, "LEVEL_00")["solidWallUnion"]
        detection_obstacles = _obstacle_union(state.active_level, state)

        difference_area = final_wall_union.symmetric_difference(detection_obstacles).area
        self.assertLessEqual(difference_area, 1e-6)

    def test_stale_automatic_virtual_boundaries_do_not_split_detection(self):
        state = BuildingAuthoringState()
        add_shell(state, 4, 3)
        state.active_level.automatic_virtual_boundaries.append(
            VirtualBoundary(
                id="VB_STALE_AUTO",
                level_id=state.active_level_id,
                line=[(2, 0), (2, 3)],
                generated_automatically=True,
                generation_reason="stale_previous_detection",
            )
        )

        result = detect_spaces(state)

        self.assertTrue(result.ok)
        self.assertEqual(1, result.report.get("polygons"))
        self.assertEqual(1, len(state.active_level.detected_spaces))

    def test_transfer_openings_do_not_split_space_detection(self):
        state = BuildingAuthoringState()
        add_shell(state, 4, 3)
        state.add_line_to_active("door_crossing", "puerta_simple", (2, 0), (2, 3), thickness_m=0.15, width_m=0.9)
        state.add_line_to_active("exit_crossing", "salida", (0, 1.5), (4, 1.5), thickness_m=0.2, width_m=2.0)

        result = detect_spaces(state)

        self.assertTrue(result.ok)
        self.assertEqual(1, result.report.get("polygons"))
        self.assertEqual(1, len(state.active_level.detected_spaces))

    def test_hosted_internal_opening_does_not_create_virtual_boundaries(self):
        state = BuildingAuthoringState()
        add_shell(state, 6, 4)
        state.add_line_to_active("divider", "muro_interior", (3, 0), (3, 4), thickness_m=0.2)
        state.add_line_to_active(
            "door",
            "puerta_simple",
            (3, 1.5),
            (3, 2.4),
            thickness_m=0.2,
            width_m=0.9,
            attributes={
                "hostWallName": "divider",
                "hostWallRef": "divider",
                "hostWallType": "muro_interior",
                "hostWallThicknessM": 0.2,
            },
        )

        result = detect_spaces(state)

        self.assertTrue(result.ok)
        self.assertEqual(2, len(state.active_level.detected_spaces))
        self.assertEqual(0, result.report.get("automaticVirtualBoundaries"))

    def test_hosted_transfer_openings_cut_general_space_without_overlap(self):
        state = BuildingAuthoringState()
        add_shell(state, 5, 4)
        wall_attrs = {
            "hostWallType": "muro_exterior",
            "hostWallThicknessM": 0.2,
        }
        state.add_line_to_active(
            "door",
            "puerta_simple",
            (2, 0),
            (2.9, 0),
            thickness_m=0.2,
            width_m=0.9,
            attributes={**wall_attrs, "hostWallName": "wall_0", "hostWallRef": "wall_0"},
        )
        state.add_line_to_active(
            "exit",
            "salida",
            (5, 1),
            (5, 3),
            thickness_m=0.2,
            width_m=2.0,
            attributes={**wall_attrs, "hostWallName": "wall_1", "hostWallRef": "wall_1"},
        )

        result = detect_spaces(state)
        builder = IndoorModelBuilder(state.to_snapshot("hosted_openings", {"width": 5, "height": 4}))
        builder.build()

        self.assertTrue(result.ok)
        self.assertEqual(1, len(state.active_level.detected_spaces))
        self.assertFalse(builder.overlap_warnings)


if __name__ == "__main__":
    unittest.main()

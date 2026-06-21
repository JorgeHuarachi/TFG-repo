import unittest

from src.indoor_authoring import BuildingAuthoringState
from src.indoor_data_model import build_indoor_model


class MultilevelAuthoringTests(unittest.TestCase):
    def test_default_level_and_dynamic_level_snapshot(self):
        state = BuildingAuthoringState()
        self.assertEqual("LEVEL_00", state.active_level_id)
        state.add_area_to_active("room_l0", "hitos", [(0, 0), (2, 0), (2, 2), (0, 2)])
        level_1 = state.add_level()
        self.assertEqual("LEVEL_01", level_1.id)
        state.add_area_to_active("room_l1", "hitos", [(0, 0), (2, 0), (2, 2), (0, 2)])

        snapshot = state.to_snapshot("multi", {"width": 3, "height": 3})
        model = build_indoor_model(snapshot)
        self.assertEqual(["LEVEL_00", "LEVEL_01"], [level["id"] for level in model["levels"]])
        self.assertEqual(["TL_NAV_L00", "TL_NAV_L01"], [layer["id"] for layer in model["layers"]])
        self.assertEqual(["LEVEL_00", "LEVEL_01"], [layer["level"] for layer in model["layers"]])

    def test_switching_levels_keeps_authoring_separate(self):
        state = BuildingAuthoringState()
        state.add_line_to_active("wall_l0", "muro_interior", (0, 0), (1, 0), thickness_m=0.1)
        state.add_level()
        state.add_line_to_active("wall_l1", "muro_interior", (0, 1), (1, 1), thickness_m=0.1)
        state.set_active_level("LEVEL_00")
        self.assertEqual(["wall_l0"], [line[0] for line in state.active_level.legacy_lines()])
        state.set_active_level("LEVEL_01")
        self.assertEqual(["wall_l1"], [line[0] for line in state.active_level.legacy_lines()])


if __name__ == "__main__":
    unittest.main()

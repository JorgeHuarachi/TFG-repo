import unittest

from src.indoor_authoring import BuildingAuthoringState, SnapshotHistory, detect_spaces
from src.indoor_authoring.connectors import create_tile_chain_connector


def checkpoint_and_apply(history, state, label, fn):
    history.checkpoint(label, state)
    fn()
    return state


class AuthoringHistoryTests(unittest.TestCase):
    def test_undo_redo_wall_opening_column_detection_level_and_connector(self):
        state = BuildingAuthoringState()
        history = SnapshotHistory(state)

        checkpoint_and_apply(history, state, "wall", lambda: state.add_line_to_active("wall", "muro_interior", (0, 0), (1, 0), thickness_m=0.1))
        restored = history.undo(state)
        self.assertEqual(0, len(restored.active_level.wall_centerlines))
        state = history.redo(restored)
        self.assertEqual(1, len(state.active_level.wall_centerlines))

        checkpoint_and_apply(history, state, "opening", lambda: state.add_line_to_active("door", "puerta_simple", (0, 0), (0.9, 0), thickness_m=0.2, width_m=0.9))
        state = history.undo(state)
        self.assertEqual(0, len(state.active_level.doors))
        state = history.redo(state)
        self.assertEqual(1, len(state.active_level.doors))

        checkpoint_and_apply(history, state, "column", lambda: state.add_area_to_active("column", "columna", [(2, 2), (3, 2), (3, 3), (2, 3)], attributes={"category": "Column"}))
        state = history.undo(state)
        self.assertEqual(0, len(state.active_level.columns))
        state = history.redo(state)
        self.assertEqual(1, len(state.active_level.columns))

        def add_shell_and_detect():
            for index, (start, end) in enumerate([((0, 0), (4, 0)), ((4, 0), (4, 4)), ((4, 4), (0, 4)), ((0, 4), (0, 0))]):
                state.add_line_to_active(f"shell_{index}", "muro_exterior", start, end, thickness_m=0.2)
            detect_spaces(state)

        checkpoint_and_apply(history, state, "detect", add_shell_and_detect)
        self.assertTrue(state.active_level.detected_spaces)
        state = history.undo(state)
        self.assertFalse(state.active_level.detected_spaces)
        state = history.redo(state)
        self.assertTrue(state.active_level.detected_spaces)

        checkpoint_and_apply(history, state, "level", lambda: state.add_level())
        self.assertEqual("LEVEL_01", state.active_level_id)
        state = history.undo(state)
        self.assertEqual("LEVEL_00", state.active_level_id)
        state = history.redo(state)
        self.assertEqual("LEVEL_01", state.active_level_id)

        state.set_active_level("LEVEL_00")
        checkpoint_and_apply(history, state, "connector", lambda: create_tile_chain_connector(state, "Stair", [(1, 1), (2, 1)], "west", "east"))
        self.assertEqual(1, len(state.vertical_connectors))
        state = history.undo(state)
        self.assertEqual(0, len(state.vertical_connectors))
        state = history.redo(state)
        self.assertEqual(1, len(state.vertical_connectors))


if __name__ == "__main__":
    unittest.main()

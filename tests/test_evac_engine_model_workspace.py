import shutil
import tempfile
import unittest
from pathlib import Path

from src.evac_engine.loaders import load_project
from src.evac_engine.model_workspace import ensure_model_baseline_scenario
from src.evac_engine.routing import RoutingEngine
from src.evac_engine.topology import EvacTopology


REPO_ROOT = Path(__file__).resolve().parents[1]


class EvacEngineModelWorkspaceTests(unittest.TestCase):
    def test_ensure_model_baseline_scenario_creates_loadable_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            model_dir = base_dir / "models" / "Demo_Model"
            spatial_dir = model_dir / "spatial"
            spatial_dir.mkdir(parents=True)
            shutil.copy2(REPO_ROOT / "examples" / "indoor_data_model" / "minimal_indoor_model.json", spatial_dir / "indoor_model.json")

            scenario_path = ensure_model_baseline_scenario("Demo_Model", base_dir=base_dir)
            indoor, scenario = load_project(None, scenario_path)

            self.assertEqual(scenario_path.relative_to(base_dir).as_posix(), "models/Demo_Model/evacuation/scenarios/baseline.json")
            self.assertEqual(scenario.indoor_model_ref["path"], "../../spatial/indoor_model.json")
            self.assertTrue(scenario.groups)
            self.assertTrue(scenario.spawns)
            self.assertTrue((scenario.routing.get("destination") or {}).get("cellSpaceRefs"))
            self.assertEqual(indoor.path, (spatial_dir / "indoor_model.json").resolve())
            topology = EvacTopology.from_indoor_model(indoor)
            spawn = scenario.spawns[0]
            coords = (spawn.get("position") or {}).get("coordinates") or []
            route = RoutingEngine(topology).find_route(
                spawn["cellSpaceRef"],
                (scenario.routing.get("destination") or {}).get("cellSpaceRefs") or [],
                algorithm="astar",
                origin_position=(float(coords[0]), float(coords[1])) if len(coords) >= 2 else None,
                origin_level=spawn.get("levelRef"),
            )
            self.assertTrue(route.reachable)

    def test_ensure_model_baseline_scenario_reuses_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            model_dir = base_dir / "models" / "Demo_Model"
            spatial_dir = model_dir / "spatial"
            scenario_dir = model_dir / "evacuation" / "scenarios"
            spatial_dir.mkdir(parents=True)
            scenario_dir.mkdir(parents=True)
            shutil.copy2(REPO_ROOT / "examples" / "indoor_data_model" / "minimal_indoor_model.json", spatial_dir / "indoor_model.json")
            existing = scenario_dir / "baseline.json"
            existing.write_text('{"scenarioId":"already_here"}', encoding="utf-8")

            scenario_path = ensure_model_baseline_scenario("Demo_Model", base_dir=base_dir)

            self.assertEqual(scenario_path, existing)
            self.assertEqual(existing.read_text(encoding="utf-8"), '{"scenarioId":"already_here"}')


if __name__ == "__main__":
    unittest.main()

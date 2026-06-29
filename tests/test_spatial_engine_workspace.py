import tempfile
import unittest
from pathlib import Path

from src.spatial_engine.project_workspace import (
    REPO_ROOT,
    create_workspace,
    discover_indoor_models,
    load_json,
    related_scenarios_for_model,
)
from src.spatial_engine.web_app import build_model_payload


class SpatialEngineWorkspaceTests(unittest.TestCase):
    def test_discovers_curated_indoor_models(self):
        models = discover_indoor_models(REPO_ROOT)
        paths = {model["path"] for model in models}

        self.assertIn("examples/indoor_data_model/minimal_indoor_model.json", paths)
        self.assertIn("examples/indoor_data_model/una_sola_planta_indoor_model.json", paths)

    def test_finds_related_example_scenarios(self):
        model = REPO_ROOT / "examples" / "indoor_data_model" / "una_sola_planta_indoor_model.json"
        scenarios = related_scenarios_for_model(model, REPO_ROOT)
        paths = {scenario["path"] for scenario in scenarios}

        self.assertIn("examples/indoor_data_model/scenario_single_floor.json", paths)

    def test_workbench_payload_includes_graph_views_and_scenarios(self):
        payload = build_model_payload("examples/indoor_data_model/minimal_indoor_model.json")

        self.assertEqual(payload["path"], "examples/indoor_data_model/minimal_indoor_model.json")
        self.assertIn("model", payload)
        self.assertIn("graphViews", payload)
        self.assertIsInstance(payload["scenarios"], list)

    def test_create_workspace_relinks_scenario_to_local_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            examples = tmp_root / "examples" / "indoor_data_model"
            examples.mkdir(parents=True)
            indoor = examples / "demo_indoor_model.json"
            scenario = examples / "scenario_demo.json"
            indoor.write_text(
                '{"featureType":"IndoorFeatures","metadata":{"name":"demo"},"layers":[]}',
                encoding="utf-8",
            )
            scenario.write_text(
                '{"scenarioId":"S","indoorModelRef":{"path":"demo_indoor_model.json"},"outputs":{}}',
                encoding="utf-8",
            )

            result = create_workspace("Demo Model", indoor, [scenario], base_dir=tmp_root)
            copied = tmp_root / result["scenarios"][0]
            copied_data = load_json(copied)

            self.assertEqual(result["workspace"], "models/Demo_Model")
            self.assertEqual(result["indoorModel"], "models/Demo_Model/spatial/indoor_model.json")
            self.assertEqual(
                copied_data["indoorModelRef"]["path"],
                "../../spatial/indoor_model.json",
            )
            self.assertEqual(copied_data["outputs"]["outputFolder"], "models/Demo_Model/outputs/demo")

    def test_related_scenarios_include_baseline_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            model_dir = tmp_root / "models" / "Demo_Model"
            spatial = model_dir / "spatial"
            scenarios = model_dir / "evacuation" / "scenarios"
            spatial.mkdir(parents=True)
            scenarios.mkdir(parents=True)
            indoor = spatial / "indoor_model.json"
            scenario = scenarios / "baseline.json"
            indoor.write_text(
                '{"featureType":"IndoorFeatures","metadata":{"name":"demo"},"layers":[]}',
                encoding="utf-8",
            )
            scenario.write_text(
                '{"scenarioId":"S","indoorModelRef":{"path":"../../spatial/indoor_model.json"},"outputs":{}}',
                encoding="utf-8",
            )

            related = related_scenarios_for_model(indoor, tmp_root)

            self.assertEqual([{"label": "S", "path": "models/Demo_Model/evacuation/scenarios/baseline.json"}], related)

    def test_create_workspace_validates_inputs_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            examples = tmp_root / "examples" / "indoor_data_model"
            examples.mkdir(parents=True)
            indoor = examples / "demo_indoor_model.json"
            indoor.write_text(
                '{"featureType":"IndoorFeatures","metadata":{"name":"demo"},"layers":[]}',
                encoding="utf-8",
            )

            with self.assertRaises(FileNotFoundError):
                create_workspace("Demo Model", indoor, [examples / "missing_scenario.json"], base_dir=tmp_root)

            self.assertFalse((tmp_root / "models" / "Demo_Model").exists())


if __name__ == "__main__":
    unittest.main()

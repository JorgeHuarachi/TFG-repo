import copy
import json
import tempfile
import unittest
from pathlib import Path

import networkx as nx

from src.evac_engine.loaders import LoaderError, ScenarioModelLoader, load_project
from src.evac_engine.overlays import BeaconState
from src.evac_engine.route_recommendation import EvacuationRouteRecommendationService, RouteRecommendationConfig
from src.evac_engine.routing import RoutingEngine
from src.evac_engine.simulation import EvacuationModel
from src.evac_engine.topology import EvacTopology
from src.evac_engine.visualization import save_result_gif, save_result_html, trajectory_quality_metrics
from src.evac_engine.web_app import discover_model_library, load_model_summary, run_configured_simulation


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "indoor_data_model"


class EvacEngineRefactorTests(unittest.TestCase):
    def test_new_scenario_examples_validate_against_schema(self):
        loader = ScenarioModelLoader()
        for name in (
            "minimal_scenario_model.json",
            "scenario_single_floor.json",
            "scenario_multilevel.json",
            "scenario_beacons_demo.json",
        ):
            with self.subTest(name=name):
                scenario = loader.load(EXAMPLES / name)
                self.assertTrue(scenario.scenario_id)

    def test_old_dynamic_weighted_route_selection_is_rejected(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        invalid = copy.deepcopy(source)
        invalid["routing"]["algorithm"] = "dynamic_weighted"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid_scenario.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(LoaderError):
                ScenarioModelLoader().load(path)

    def test_evacuation_centrality_counts_efficient_dissimilar_paths(self):
        graph = nx.DiGraph()
        graph.add_weighted_edges_from(
            [
                ("S", "A", 1.0),
                ("A", "T", 1.0),
                ("S", "B", 1.0),
                ("B", "T", 1.0),
                ("S", "C", 1.0),
                ("C", "T", 1.0),
            ]
        )

        service = EvacuationRouteRecommendationService()
        centrality = service.evacuation_centrality(
            graph,
            ["T"],
            sources=["S"],
            tolerance=0.1,
            max_paths=5,
            max_overlap=0.0,
        )

        self.assertEqual(3.0, centrality["S"])

    def test_recommendation_can_prefer_robust_route_within_tolerance(self):
        graph = nx.DiGraph()
        graph.add_weighted_edges_from(
            [
                ("S", "X", 1.0),
                ("X", "T", 1.0),
                ("S", "A", 1.2),
                ("A", "T", 1.2),
                ("S", "B", 1.2),
                ("B", "A", 0.1),
                ("A", "C", 0.1),
                ("C", "T", 1.2),
            ]
        )
        service = EvacuationRouteRecommendationService()
        candidate = service.recommend(
            graph,
            "S",
            ["T"],
            config=RouteRecommendationConfig(
                algorithm="yen_ksp",
                route_selection="highest_robustness",
                k_shortest_paths=5,
                candidate_cost_tolerance=0.5,
                robustness_tolerance=0.1,
            ),
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(["S", "A", "T"], candidate.node_sequence)
        self.assertEqual(1.0, candidate.metrics["robustness"])

    def test_robust_agility_algorithm_validates_and_plans(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        source["routing"]["algorithm"] = "robust_agility"
        source["routing"]["routeRecommendation"] = {
            "kShortestPaths": 4,
            "routeSelection": "robust_agility",
            "candidateCostTolerance": 0.5,
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "robust_agility_scenario.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            indoor, scenario = load_project(EXAMPLES / "minimal_indoor_model.json", path)
        topology = EvacTopology.from_indoor_model(indoor)
        route = RoutingEngine(topology).find_route(
            "CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=scenario.mobility_profiles["MP_WALKING_ROLLING"],
            algorithm=scenario.routing["algorithm"],
            routing_config=scenario.routing,
        )

        self.assertTrue(route.reachable)
        self.assertEqual("robust_agility", route.algorithm)
        self.assertIn("routeMetrics", route.weight_breakdown)

    def test_minimal_route_uses_cellspace_ids_and_preserves_edges(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        topology = EvacTopology.from_indoor_model(indoor)
        route = RoutingEngine(topology).find_route(
            "CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=scenario.mobility_profiles["MP_WALKING_ROLLING"],
            routing_config=scenario.routing,
        )

        self.assertTrue(route.reachable)
        self.assertEqual(["CS_L00_ROOM_A", "CS_L00_DOOR_1", "CS_L00_ROOM_B"], route.node_sequence)
        self.assertEqual(2, len(route.arc_sequence))
        for node_id in route.node_sequence:
            self.assertFalse(node_id.startswith("N_"))
            self.assertNotIn(":", node_id)

    def test_beacon_block_threshold_removes_unsafe_cells_from_routes(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        topology = EvacTopology.from_indoor_model(indoor)
        route = RoutingEngine(topology).find_route(
            "CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=scenario.mobility_profiles["MP_WALKING_ROLLING"],
            beacon_state=BeaconState(cell_risk={"CS_L00_DOOR_1": 1.0}),
            routing_config={"useBeaconRisk": True, "beaconBlockThreshold": 0.85},
        )

        self.assertFalse(route.reachable)

    def test_no_route_agent_recovers_after_beacon_unblocks_path(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        source["population"]["agentGroups"][0]["count"] = 1
        source["beaconSystem"] = {
            "enabled": True,
            "fusion": {"method": "conservative_min", "defaultRadiusM": 1.0},
            "beacons": [
                {
                    "beaconId": "BC_DOOR_BLOCK",
                    "levelRef": "LEVEL_00",
                    "position": {"type": "Point", "coordinates": [2.1, 1.0]},
                    "sensorTypes": ["smoke"],
                    "influence": {"type": "radius", "innerRadiusM": 0.25, "radiusM": 0.25},
                    "effects": {"riskPenalty": 1.0},
                }
            ],
        }
        source["routing"].update(
            {
                "useBeaconRisk": True,
                "beaconBlockThreshold": 0.85,
                "replanPolicy": "on_blocked_or_interval",
                "replanIntervalSteps": 2,
                "noRouteRetryIntervalSteps": 1,
            }
        )
        source["simulationConfig"]["maxSteps"] = 30
        source["scheduledEvents"] = [
            {
                "eventId": "EV_DOOR_UNBLOCKS",
                "step": 3,
                "eventType": "beacon_update",
                "beaconRef": "BC_DOOR_BLOCK",
                "patch": {"effects": {"riskPenalty": 0.0}},
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario_no_route_recovery.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            indoor, scenario = load_project(EXAMPLES / "minimal_indoor_model.json", path)
            result = EvacuationModel(indoor, scenario).run()

        event_types = [event["eventType"] for event in result.events]
        self.assertIn("agent_no_route", event_types)
        self.assertIn("agent_route_recovered", event_types)
        self.assertEqual(1, result.metrics["evacuated"])
        self.assertEqual(0, result.metrics["noRoute"])

    def test_agent_inside_beacon_blocked_cell_escapes_to_safer_neighbor(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        source["population"]["agentGroups"][0]["count"] = 1
        source["population"]["agentGroups"][0]["distribution"] = "fixed"
        source["beaconSystem"] = {
            "enabled": True,
            "fusion": {"method": "conservative_min", "defaultRadiusM": 1.0},
            "beacons": [
                {
                    "beaconId": "BC_ROOM_A_BLOCK",
                    "levelRef": "LEVEL_00",
                    "position": {"type": "Point", "coordinates": [0.8, 1.0]},
                    "sensorTypes": ["smoke"],
                    "influence": {"type": "radius", "innerRadiusM": 0.4, "radiusM": 0.6},
                    "effects": {"riskPenalty": 1.0},
                }
            ],
        }
        source["routing"].update(
            {
                "useBeaconRisk": True,
                "beaconBlockThreshold": 0.85,
                "replanPolicy": "on_blocked_or_interval",
                "replanIntervalSteps": 1,
            }
        )
        source["simulationConfig"]["maxSteps"] = 20
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario_beacon_escape.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            indoor, scenario = load_project(EXAMPLES / "minimal_indoor_model.json", path)
            result = EvacuationModel(indoor, scenario).run()

        event_types = [event["eventType"] for event in result.events]
        self.assertIn("agent_beacon_escape", event_types)
        self.assertGreaterEqual(result.metrics["evacuated"], 1)
        self.assertEqual(0, result.metrics["noRoute"])

    def test_vertical_endpoint_route_and_accessibility_filters(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_multilevel.json")
        topology = EvacTopology.from_indoor_model(indoor)
        engine = RoutingEngine(topology)

        elevator_route = engine.find_route(
            "CS_L02_EP_VC_004_LEVEL_02",
            target_refs=["CS_L01_EP_VC_004_LEVEL_01"],
            mobility_profile=scenario.mobility_profiles["MP_ROLLING_ACCESSIBLE"],
            routing_config=scenario.routing,
        )
        self.assertTrue(elevator_route.reachable)
        self.assertEqual(
            ["CS_L02_EP_VC_004_LEVEL_02", "CS_L01_EP_VC_004_LEVEL_01"],
            elevator_route.node_sequence,
        )
        self.assertGreater(elevator_route.total_cost, 0.5)

        walking_stair_route = engine.find_route(
            "CS_L00_EP_VC_002_LEVEL_00",
            target_refs=["CS_L01_EP_VC_002_LEVEL_01"],
            mobility_profile=scenario.mobility_profiles["MP_WALKING_VERTICAL"],
            routing_config=scenario.routing,
        )
        self.assertTrue(walking_stair_route.reachable)
        self.assertEqual(
            ["CS_L00_EP_VC_002_LEVEL_00", "CS_L01_EP_VC_002_LEVEL_01"],
            walking_stair_route.node_sequence,
        )

        rolling_snapshot = engine.compiler.compile(
            mobility_profile=scenario.mobility_profiles["MP_ROLLING_ACCESSIBLE"],
            routing_config=scenario.routing,
        )
        self.assertFalse(
            rolling_snapshot.graph.has_edge("CS_L00_EP_VC_002_LEVEL_00", "CS_L01_EP_VC_002_LEVEL_01")
        )

    def test_minimal_simulation_writes_required_outputs(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        with tempfile.TemporaryDirectory() as tmp:
            result = model.run(tmp)
            self.assertTrue(result.completed)
            self.assertEqual(5, result.metrics["evacuated"])
            for name in (
                "run_manifest.json",
                "events.ndjson",
                "routes.json",
                "trajectories.ndjson",
                "metrics.json",
                "metrics.csv",
            ):
                self.assertTrue((Path(tmp) / name).exists(), name)

    def test_trajectories_keep_agents_visible_and_profiled(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        result = model.run()
        expected_agents = result.metrics["agentCount"]
        by_step = {}
        for row in result.trajectories:
            by_step.setdefault(row["step"], set()).add(row["agentId"])
            self.assertIn("profileId", row)
            self.assertIn("intentX", row)
            self.assertIn("bodyRadiusM", row)
            self.assertIn("personalRadiusM", row)
        for agent_ids in by_step.values():
            self.assertEqual(expected_agents, len(agent_ids))
        qa = trajectory_quality_metrics(result.trajectories)
        self.assertEqual(expected_agents, qa["agentCount"])

    def test_minimal_simulation_can_render_gif(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        result = model.run()
        with tempfile.TemporaryDirectory() as tmp:
            gif_path = save_result_gif(model.topology, result, Path(tmp) / "minimal.gif", fps=4, max_frames=12)
            self.assertTrue(gif_path.exists())
            self.assertGreater(gif_path.stat().st_size, 1000)

    def test_minimal_simulation_can_render_html_viewer(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        result = model.run()
        with tempfile.TemporaryDirectory() as tmp:
            html_path = save_result_html(model.topology, result, Path(tmp) / "viewer.html")
            html = html_path.read_text(encoding="utf-8")
            self.assertIn("EvacEngine Viewer", html)
            self.assertIn("SCENARIO_MINIMAL_001", html)

    def test_scheduled_beacon_update_changes_runtime_beacon(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_beacons_demo.json")
        model = EvacuationModel(indoor, scenario)
        self.assertEqual(0.4, model.beacons[0]["effects"]["riskPenalty"])
        model.step()
        model.step()
        model.step()
        self.assertEqual(0.7, model.beacons[0]["effects"]["riskPenalty"])
        self.assertTrue(any(event["eventType"] == "scheduled_beacon_update" for event in model.events))

    def test_workbench_model_summary_lists_cells_and_defaults(self):
        summary = load_model_summary(None, str(EXAMPLES / "scenario_single_floor.json"))
        self.assertTrue(summary["cells"])
        self.assertTrue(summary["levels"])
        self.assertTrue(summary["groups"])
        self.assertTrue(summary["spawns"])
        self.assertIn("firstGroupCount", summary["config"])

    def test_workbench_model_summary_exposes_visual_categories(self):
        summary = load_model_summary(None, str(EXAMPLES / "scenario_single_floor.json"))
        categories = {space["category"] for space in summary["spaces"]}
        self.assertIn("Column", categories)
        self.assertIn("Stair", categories)
        self.assertIn("Ramp", categories)

    def test_workbench_library_lists_available_scenarios_and_models(self):
        library = discover_model_library(EXAMPLES)
        scenario_paths = {item["path"] for item in library["scenarios"]}
        indoor_paths = {item["path"] for item in library["indoorModels"]}
        self.assertIn("examples/indoor_data_model/scenario_single_floor.json", scenario_paths)
        self.assertIn("examples/indoor_data_model/scenario_multilevel.json", scenario_paths)
        self.assertIn("examples/indoor_data_model/una_sola_planta_indoor_model.json", indoor_paths)
        self.assertIn("examples/indoor_data_model/tres_plantas_indoor_model.json", indoor_paths)

    def test_workbench_runs_configured_payload(self):
        payload = run_configured_simulation(
            {
                "scenarioPath": str(EXAMPLES / "minimal_scenario_model.json"),
                "config": {
                    "timeStepS": 0.25,
                    "maxSteps": 40,
                    "randomSeed": 7,
                    "firstGroupCount": 3,
                    "algorithm": "astar",
                    "costPolicy": "shortest_distance",
                    "destinationCells": ["CS_L00_ROOM_B"],
                    "useBeaconRisk": True,
                    "beaconBlockThreshold": 0.95,
                },
                "beacons": [
                    {
                        "beaconId": "BC_WORKBENCH_SNAPSHOT",
                        "levelRef": "LEVEL_00",
                        "position": {"type": "Point", "coordinates": [0.8, 1.0]},
                        "sensorTypes": ["smoke"],
                        "influence": {"type": "radius", "innerRadiusM": 0.1, "radiusM": 0.2},
                        "effects": {"riskPenalty": 0.2},
                    }
                ],
                "scheduledEvents": [
                    {
                        "eventId": "EV_WORKBENCH_SNAPSHOT",
                        "step": 2,
                        "eventType": "beacon_update",
                        "beaconRef": "BC_WORKBENCH_SNAPSHOT",
                        "patch": {"effects": {"riskPenalty": 0.3}},
                    }
                ],
            },
            str(EXAMPLES / "minimal_scenario_model.json"),
        )
        self.assertEqual(3, payload["metrics"]["agentCount"])
        self.assertIn("qa", payload)
        self.assertTrue(payload["trajectories"])
        self.assertEqual("BC_WORKBENCH_SNAPSHOT", payload["beacons"][0]["beaconId"])
        self.assertEqual("EV_WORKBENCH_SNAPSHOT", payload["scheduledEvents"][0]["eventId"])
        self.assertTrue(payload["routingConfig"]["useBeaconRisk"])
        self.assertTrue(any(space.get("isNavigable") for space in payload["spaces"]))

    def test_workbench_manual_multilevel_agent_uses_all_scenario_exits(self):
        payload = run_configured_simulation(
            {
                "scenarioPath": str(EXAMPLES / "scenario_multilevel.json"),
                "config": {
                    "timeStepS": 0.25,
                    "maxSteps": 220,
                    "randomSeed": 7,
                    "algorithm": "astar",
                    "costPolicy": "minimum_travel_time",
                    "destinationCells": ["CS_L00_EXIT_001", "CS_L01_EXIT_001", "CS_L02_EXIT_001"],
                },
                "manualAgents": [
                    {
                        "agentId": "MANUAL_L02_001",
                        "mobilityProfileRef": "MP_WALKING_VERTICAL",
                        "initialCellSpaceRef": "CS_L02_ROOM_001",
                        "initialPosition": {"type": "Point", "coordinates": [1.0, 1.0]},
                    }
                ],
                "beacons": [],
                "scheduledEvents": [],
            },
            str(EXAMPLES / "scenario_multilevel.json"),
        )
        self.assertEqual(1, payload["metrics"]["agentCount"])
        self.assertEqual(0, payload["metrics"]["noRoute"])
        self.assertEqual(1, payload["metrics"]["evacuated"])
        final_row = payload["trajectories"][-1]
        self.assertEqual("CS_L02_EXIT_001", final_row["cellSpaceRef"])
        self.assertEqual("LEVEL_02", final_row["levelRef"])

    def test_multilevel_ramp_route_exits_virtual_boundary_without_stalling(self):
        payload = run_configured_simulation(
            {
                "scenarioPath": str(EXAMPLES / "scenario_multilevel.json"),
                "config": {
                    "timeStepS": 0.25,
                    "maxSteps": 180,
                    "randomSeed": 7,
                    "algorithm": "astar",
                    "costPolicy": "minimum_travel_time",
                    "destinationCells": ["CS_L00_EXIT_001"],
                },
                "manualAgents": [
                    {
                        "agentId": "MANUAL_RAMP_001",
                        "mobilityProfileRef": "MP_WALKING_VERTICAL",
                        "initialCellSpaceRef": "CS_L01_ROOM_013",
                        "initialPosition": {"type": "Point", "coordinates": [22.9375, 16.6875]},
                    }
                ],
                "beacons": [],
                "scheduledEvents": [],
            },
            str(EXAMPLES / "scenario_multilevel.json"),
        )
        self.assertEqual(0, payload["metrics"]["noRoute"])
        self.assertEqual(1, payload["metrics"]["evacuated"])
        self.assertEqual("CS_L00_EXIT_001", payload["trajectories"][-1]["cellSpaceRef"])


if __name__ == "__main__":
    unittest.main()

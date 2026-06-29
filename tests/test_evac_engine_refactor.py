import copy
import json
import tempfile
import unittest
from pathlib import Path

import networkx as nx
from shapely.geometry import box

from src.evac_engine.loaders import LoaderError, ScenarioModelLoader, load_project
from src.evac_engine.overlays import BeaconState
from src.evac_engine.experiments import available_routing_presets, compare_routing_presets
from src.evac_engine.route_recommendation import EvacuationRouteRecommendationService, RouteRecommendationConfig
from src.evac_engine.routing import RoutingEngine
from src.evac_engine.simulation import EvacuationModel
from src.evac_engine.topology import EvacTopology
from src.evac_engine.visualization import graph_edge_payload, save_result_gif, save_result_html, trajectory_quality_metrics
from src.evac_engine.web_app import (
    WORKBENCH_HTML,
    compare_configured_routing,
    discover_model_library,
    load_model_summary,
    run_configured_simulation,
    save_configured_routing_comparison,
    save_configured_scenario,
)


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

    def test_shortest_distance_cost_policy_is_rejected(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        invalid = copy.deepcopy(source)
        invalid["routing"]["costPolicy"] = "shortest_distance"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid_cost_policy_scenario.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(LoaderError):
                ScenarioModelLoader().load(path)

    def test_floyd_warshall_algorithm_validates(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        source["routing"]["algorithm"] = "floyd_warshall"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "floyd_warshall_scenario.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            scenario = ScenarioModelLoader().load(path)

        self.assertEqual("floyd_warshall", scenario.routing["algorithm"])

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

    def test_floyd_warshall_route_matches_dijkstra_for_minimal_graph(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        topology = EvacTopology.from_indoor_model(indoor)
        engine = RoutingEngine(topology)
        profile = scenario.mobility_profiles["MP_WALKING_ROLLING"]
        dijkstra = engine.find_route(
            "CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=profile,
            algorithm="dijkstra",
            cost_policy="minimum_travel_time",
            routing_config=scenario.routing,
        )
        floyd = engine.find_route(
            "CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=profile,
            algorithm="floyd_warshall",
            cost_policy="minimum_travel_time",
            routing_config=scenario.routing,
        )

        self.assertTrue(floyd.reachable)
        self.assertEqual(dijkstra.node_sequence, floyd.node_sequence)
        self.assertAlmostEqual(dijkstra.total_cost, floyd.total_cost, places=6)

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

    def test_multiplicative_risk_cost_model_is_configurable(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        topology = EvacTopology.from_indoor_model(indoor)
        route = RoutingEngine(topology).find_route(
            "CS_L00_ROOM_A",
            target_refs=["CS_L00_DOOR_1"],
            mobility_profile=scenario.mobility_profiles["MP_WALKING_ROLLING"],
            cost_policy="minimum_travel_time",
            beacon_state=BeaconState(cell_risk={"CS_L00_DOOR_1": 0.5}),
            routing_config={
                "useBeaconRisk": True,
                "useHazardRisk": False,
                "riskCostModel": "multiplicative_beta",
                "riskEndpointPolicy": "target",
                "riskEdgePrecedence": False,
                "riskAlpha": 1.0,
                "beaconBeta": 2.0,
            },
        )

        self.assertTrue(route.reachable)
        breakdown = route.weight_breakdown

        self.assertAlmostEqual(breakdown["base"] * 2.0, breakdown["total"], places=5)

    def test_time_cost_uses_profile_speed_and_connector_slowdown(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_multilevel.json")
        topology = EvacTopology.from_indoor_model(indoor)
        engine = RoutingEngine(topology)
        profile = scenario.mobility_profiles["MP_WALKING_VERTICAL"]
        route = engine.find_route(
            "CS_L00_EP_VC_002_LEVEL_00",
            target_refs=["CS_L01_EP_VC_002_LEVEL_01"],
            mobility_profile=profile,
            routing_config={**scenario.physics, **scenario.routing},
        )

        self.assertTrue(route.reachable)
        self.assertEqual("s", route.weight_breakdown["baseUnit"])
        self.assertGreater(route.weight_breakdown["lengthM"], 0.0)
        self.assertGreater(route.weight_breakdown["base"], route.weight_breakdown["lengthM"] / profile.base_speed_mps)

    def test_simulation_speed_factor_slows_vertical_connectors(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_multilevel.json")
        model = EvacuationModel(indoor, scenario)

        self.assertAlmostEqual(0.55, model._movement_speed_factor("CS_L00_ROOM_015", "CS_L00_EP_VC_002_LEVEL_00"))
        self.assertAlmostEqual(0.7, model._movement_speed_factor("CS_L00_ROOM_018", "CS_L00_EP_VC_003_LEVEL_00"))
        self.assertAlmostEqual(0.5, model._movement_speed_factor("CS_L00_ROOM_005", "CS_L00_EP_VC_001_LEVEL_00"))

    def test_compare_routing_presets_writes_summary_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = compare_routing_presets(
                EXAMPLES / "minimal_indoor_model.json",
                EXAMPLES / "minimal_scenario_model.json",
                preset_ids=["dijkstra_time", "astar_time"],
                output_dir=Path(tmp) / "routing_compare",
                runtime_overrides={"maxSteps": 12, "firstGroupCount": 1},
                write_run_outputs=False,
                write_plot=False,
            )

            output = Path(summary["outputDir"])

            self.assertEqual(["dijkstra_time", "astar_time"], summary["presetIds"])
            self.assertEqual(2, len(summary["runs"]))
            self.assertTrue((output / "comparison_summary.json").exists())
            self.assertTrue((output / "comparison_metrics.csv").exists())
            self.assertTrue((output / "comparison_routes.csv").exists())

    def test_builtin_routing_presets_include_floyd_warshall(self):
        presets = available_routing_presets()

        self.assertIn("floyd_warshall_time", presets)
        self.assertEqual("floyd_warshall", presets["floyd_warshall_time"]["routing"]["algorithm"])

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

    def test_static_single_agent_periodically_replans_when_interval_is_enabled(self):
        source = json.loads((EXAMPLES / "minimal_scenario_model.json").read_text(encoding="utf-8"))
        source["population"]["agentGroups"][0]["count"] = 1
        source["routing"].update(
            {
                "useBeaconRisk": False,
                "useHazardRisk": False,
                "useCongestion": True,
                "replanPolicy": "on_blocked_or_interval",
                "replanIntervalSteps": 1,
            }
        )
        source["simulationConfig"]["maxSteps"] = 12
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario_static_single_agent.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            indoor, scenario = load_project(EXAMPLES / "minimal_indoor_model.json", path)
            result = EvacuationModel(indoor, scenario).run()

        self.assertGreater(result.metrics["routePlans"], 1)

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

    def test_proximity_slowdown_memory_recovers_quickly(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        scenario.physics["proximitySlowdownMemoryS"] = 0.2
        model = EvacuationModel(indoor, scenario)
        agent = model.agents[0]
        model.agents = [agent]

        model._mark_proximity_slowdown(agent, 0.3)
        self.assertEqual(0.3, agent.proximity_slowdown_scale)
        model._mark_proximity_slowdown(agent, 0.8)
        self.assertEqual(0.8, agent.proximity_slowdown_scale)
        model.time_s = 0.1
        self.assertLess(model._social_speed_scale(agent, (1.0, 0.0)), 1.0)
        model.time_s = 0.25
        self.assertEqual(1.0, model._social_speed_scale(agent, (1.0, 0.0)))
        self.assertEqual(1.0, agent.proximity_slowdown_scale)

    def test_agent_closer_to_immediate_goal_slows_less_in_queue(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        leader, follower = model.agents[:2]
        profile = scenario.mobility_profiles[leader.profile_id]
        route = model.routing_engine.find_route(
            origin="CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=profile,
            routing_config={**scenario.physics, **scenario.routing},
        )
        for agent in (leader, follower):
            agent.current_cell = "CS_L00_ROOM_A"
            agent.route = route
            agent.route_index = 0
            agent.velocity = (0.0, 0.0)
        leader.position = (1.82, 1.0)
        follower.position = (1.42, 1.0)
        model.agents = [leader, follower]

        leader_scale = model._social_speed_scale(leader, (1.0, 0.0))
        follower_scale = model._social_speed_scale(follower, (1.0, 0.0))

        self.assertGreater(leader_scale, follower_scale)

    def test_body_collision_uses_hard_body_radius_not_personal_space(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        scenario.mobility_profiles["MP_WALKING_ROLLING"].attributes["bodyRadiusM"] = 0.24
        scenario.mobility_profiles["MP_WALKING_ROLLING"].attributes["personalRadiusM"] = 1.0
        model = EvacuationModel(indoor, scenario)
        left, right = model.agents[:2]
        for agent in (left, right):
            agent.current_cell = "CS_L00_ROOM_A"
            agent.level = "LEVEL_00"
            agent.status = "active"
        left.position = (1.0, 1.0)
        right.position = (1.05, 1.0)

        model._resolve_overlaps([left, right])

        distance = ((right.position[0] - left.position[0]) ** 2 + (right.position[1] - left.position[1]) ** 2) ** 0.5
        hard_body_distance = model._body_radius(left) + model._body_radius(right)
        personal_distance = (
            scenario.mobility_profiles[left.profile_id].attributes["personalRadiusM"]
            + scenario.mobility_profiles[right.profile_id].attributes["personalRadiusM"]
        )
        self.assertGreaterEqual(distance, hard_body_distance - 1e-4)
        self.assertLess(distance, personal_distance)

    def test_transfer_capacity_lets_closest_agent_enter_first(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        far_agent, mid_agent, near_agent = model.agents[:3]
        far_agent.current_cell = "CS_L00_ROOM_A"
        mid_agent.current_cell = "CS_L00_ROOM_A"
        near_agent.current_cell = "CS_L00_ROOM_A"
        far_agent.position = (1.4, 1.0)
        mid_agent.position = (1.55, 1.0)
        near_agent.position = (1.85, 1.0)
        model.agents = [far_agent, mid_agent, near_agent]

        filtered = model._apply_transfer_capacity(
            [
                (far_agent, "CS_L00_DOOR_1", far_agent.position, (1.0, 0.0)),
                (mid_agent, "CS_L00_DOOR_1", mid_agent.position, (1.0, 0.0)),
                (near_agent, "CS_L00_DOOR_1", near_agent.position, (1.0, 0.0)),
            ]
        )
        by_agent = {agent.agent_id: (new_cell, new_pos, new_velocity) for agent, new_cell, new_pos, new_velocity in filtered}

        self.assertEqual("CS_L00_ROOM_A", by_agent[far_agent.agent_id][0])
        self.assertEqual("CS_L00_ROOM_A", by_agent[mid_agent.agent_id][0])
        self.assertEqual("CS_L00_DOOR_1", by_agent[near_agent.agent_id][0])
        self.assertEqual("transfer_capacity", far_agent.wait_reason)
        self.assertEqual("transfer_capacity", mid_agent.wait_reason)
        self.assertEqual("CS_L00_DOOR_1", far_agent.waiting_for_cell)
        self.assertEqual((0.0, 0.0), by_agent[far_agent.agent_id][2])
        self.assertNotEqual(by_agent[far_agent.agent_id][1], by_agent[mid_agent.agent_id][1])

        profile = scenario.mobility_profiles[far_agent.profile_id]
        far_agent.route = model.routing_engine.find_route(
            origin="CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=profile,
            routing_config={**scenario.physics, **scenario.routing},
        )
        model._record_trajectory(far_agent)
        self.assertEqual("transfer_capacity", model.trajectories[-1]["waitReason"])
        self.assertIsNone(model.trajectories[-1]["intentX"])

    def test_agent_queues_before_full_transfer_without_forward_dash(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        scenario.physics["doorQueueCorrectionMaxM"] = 2.0
        scenario.physics["queueCorrectionSpeedScale"] = 0.35
        model = EvacuationModel(indoor, scenario)
        approaching, blocker = model.agents[:2]
        profile = scenario.mobility_profiles[approaching.profile_id]
        route = model.routing_engine.find_route(
            origin="CS_L00_ROOM_A",
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=profile,
            routing_config={**scenario.physics, **scenario.routing},
        )
        approaching.current_cell = "CS_L00_ROOM_A"
        approaching.position = (1.7, 1.0)
        approaching.route = route
        approaching.route_index = 0
        blocker.current_cell = "CS_L00_DOOR_1"
        blocker.position = (2.1, 1.0)
        model.agents = [approaching, blocker]

        filtered = model._apply_transfer_capacity(
            [(approaching, "CS_L00_ROOM_A", (1.95, 1.0), (0.5, 0.0))]
        )
        _, new_cell, new_pos, new_velocity = filtered[0]

        self.assertEqual("CS_L00_ROOM_A", new_cell)
        self.assertEqual("transfer_capacity", approaching.wait_reason)
        self.assertEqual("CS_L00_DOOR_1", approaching.waiting_for_cell)
        self.assertEqual((0.0, 0.0), new_velocity)
        self.assertLessEqual(new_pos[0], approaching.position[0])
        self.assertLessEqual(
            ((new_pos[0] - approaching.position[0]) ** 2 + (new_pos[1] - approaching.position[1]) ** 2) ** 0.5,
            profile.base_speed_mps * scenario.time_step_s * scenario.physics["queueCorrectionSpeedScale"] + 1e-6,
        )

        waiting_position = new_pos
        approaching.position = waiting_position
        approaching.wait_reason = "transfer_capacity"
        blocker.current_cell = "CS_L00_ROOM_A"
        blocker.position = waiting_position
        model._resolve_overlaps([approaching, blocker])
        self.assertEqual(waiting_position, approaching.position)

    def test_trajectory_intent_is_hidden_when_line_of_sight_crosses_wall(self):
        indoor, scenario = load_project(None, EXAMPLES / "minimal_scenario_model.json")
        model = EvacuationModel(indoor, scenario)
        agent = model.agents[0]
        profile = scenario.mobility_profiles[agent.profile_id]
        agent.route = model.routing_engine.find_route(
            origin=agent.current_cell,
            target_refs=["CS_L00_ROOM_B"],
            mobility_profile=profile,
            routing_config={**scenario.physics, **scenario.routing},
        )
        model._wall_geometries_by_level[agent.level or ""] = box(1.0, 0.5, 1.5, 1.5)

        model._record_trajectory(agent)
        row = model.trajectories[-1]

        self.assertIsNone(row["intentX"])
        self.assertIsNone(row["intentY"])

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
        self.assertIn("navigationType", summary["cells"][0])

    def test_workbench_model_summary_exposes_visual_categories(self):
        summary = load_model_summary(None, str(EXAMPLES / "scenario_single_floor.json"))
        categories = {space["category"] for space in summary["spaces"]}
        self.assertIn("Column", categories)
        self.assertIn("Stair", categories)
        self.assertIn("Ramp", categories)

    def test_workbench_model_summary_exposes_routing_experiments(self):
        summary = load_model_summary(None, str(EXAMPLES / "minimal_scenario_model.json"))

        self.assertIn("routingPresets", summary)
        self.assertIn("dijkstra_time", summary["routingPresets"])
        self.assertIn("floyd_warshall_time", summary["routingPresets"])
        self.assertIn("riskCostModel", summary["config"])
        self.assertIn("routeRecommendation", summary["config"])

    def test_workbench_model_summary_includes_complete_graph_edges(self):
        summary = load_model_summary(None, str(EXAMPLES / "scenario_single_floor.json"))
        graph_edges = summary["graphEdges"]
        virtual_edges = [edge for edge in graph_edges if str(edge["source"]).startswith("VTN_") or str(edge["target"]).startswith("VTN_")]
        stair_edges = [edge for edge in graph_edges if edge.get("sourceCategory") == "Stair" or edge.get("targetCategory") == "Stair"]

        self.assertEqual("multilevel_transfer_to_transfer", summary["graphView"])
        self.assertGreater(len(graph_edges), 0)
        self.assertGreater(len(summary["virtualBoundaries"]), 0)
        self.assertGreater(len(virtual_edges), 0)
        self.assertGreater(len(stair_edges), 0)
        self.assertTrue(all(edge.get("levels") for edge in virtual_edges))

    def test_graph_edge_payload_infers_levels_for_virtual_to_virtual_edges(self):
        indoor, _ = load_project(None, EXAMPLES / "scenario_multilevel.json")
        topology = EvacTopology.from_indoor_model(indoor)
        graph_edges = graph_edge_payload(topology)
        virtual_edges = [edge for edge in graph_edges if str(edge["source"]).startswith("VTN_") or str(edge["target"]).startswith("VTN_")]

        self.assertTrue(virtual_edges)
        self.assertFalse([edge for edge in virtual_edges if not edge.get("levels")])

    def test_workbench_routing_experiments_are_after_beacons_and_use_safety_labels(self):
        self.assertLess(WORKBENCH_HTML.index("<h2>Beacons</h2>"), WORKBENCH_HTML.index("<h2>Routing Experiments</h2>"))
        self.assertIn("Safety-cost model", WORKBENCH_HTML)
        self.assertIn("Advanced safety/cost parameters", WORKBENCH_HTML)
        self.assertIn("Safety loss curve preview", WORKBENCH_HTML)
        self.assertIn("Stair capacity", WORKBENCH_HTML)
        self.assertIn("Ramp capacity", WORKBENCH_HTML)
        self.assertIn("linearTransferFlowMode", WORKBENCH_HTML)
        self.assertIn("Stair/ramp flow", WORKBENCH_HTML)
        self.assertIn("isConnectorAccessEdge", WORKBENCH_HTML)
        self.assertNotIn("if (virtualEdge) ctx.setLineDash", WORKBENCH_HTML)
        self.assertNotIn("if (isVirtualEdge(e)) continue", WORKBENCH_HTML)
        self.assertIn("Save scenario", WORKBENCH_HTML)
        self.assertIn("Save GIF/HTML", WORKBENCH_HTML)
        self.assertIn("Save comparison viewer", WORKBENCH_HTML)
        self.assertIn("Scenarios for loaded model", WORKBENCH_HTML)
        self.assertIn("sessionInfo", WORKBENCH_HTML)
        self.assertIn("workbenchSession", WORKBENCH_HTML)
        self.assertIn("activeEdges", WORKBENCH_HTML)
        self.assertIn("routeDebugSummary", WORKBENCH_HTML)
        self.assertIn("drawRouteDebug", WORKBENCH_HTML)
        self.assertIn("routeNodePoints", WORKBENCH_HTML)
        self.assertIn("plannedRouteForAgent", WORKBENCH_HTML)
        self.assertIn("routeCostChart", WORKBENCH_HTML)
        self.assertIn("drawRouteCostChart", WORKBENCH_HTML)
        self.assertIn("routeCostHistory", WORKBENCH_HTML)
        self.assertIn("Estimated total evacuation time", WORKBENCH_HTML)
        self.assertIn("estimatedTotalEvacuationS", WORKBENCH_HTML)
        self.assertIn("pixelsPerMeter", WORKBENCH_HTML)
        self.assertIn("agentBodyRadiusPx", WORKBENCH_HTML)
        self.assertIn("Apply preset + run", WORKBENCH_HTML)
        self.assertIn("drawVirtualBoundaries", WORKBENCH_HTML)
        self.assertIn("activeVirtualBoundaries", WORKBENCH_HTML)
        self.assertIn("edgeVisibleOnLevel", WORKBENCH_HTML)
        self.assertNotIn("drawGraphNodes", WORKBENCH_HTML)
        self.assertIn("section-description", WORKBENCH_HTML)
        self.assertIn("setupSidebarSections", WORKBENCH_HTML)
        self.assertIn("updateControlAvailability", WORKBENCH_HTML)
        self.assertIn("floyd_warshall", WORKBENCH_HTML)
        self.assertIn("plans | routeCost", WORKBENCH_HTML)
        self.assertIn("durationHint", WORKBENCH_HTML)
        self.assertIn("SET batch", WORKBENCH_HTML)
        self.assertIn("DELETE cell", WORKBENCH_HTML)
        self.assertIn("routingParameterStatus", WORKBENCH_HTML)
        self.assertIn("active/ignored parameters", WORKBENCH_HTML)
        self.assertIn("automaticAgentsFromControls", WORKBENCH_HTML)
        self.assertIn("spaceIsSpawnable", WORKBENCH_HTML)
        self.assertIn("spawnRegionSpaces", WORKBENCH_HTML)
        self.assertIn("Automatic spawn selected", WORKBENCH_HTML)

    def test_workbench_can_compare_routing_presets(self):
        comparison = compare_configured_routing(
            {
                "scenarioPath": str(EXAMPLES / "minimal_scenario_model.json"),
                "indoorPath": str(EXAMPLES / "minimal_indoor_model.json"),
                "presetIds": ["dijkstra_time", "astar_time"],
                "config": {
                    "timeStepS": 0.25,
                    "maxSteps": 12,
                    "randomSeed": 7,
                    "firstGroupCount": 1,
                    "algorithm": "astar",
                    "costPolicy": "minimum_travel_time",
                    "useBeaconRisk": False,
                },
                "beacons": [],
                "scheduledEvents": [],
            },
            str(EXAMPLES / "minimal_scenario_model.json"),
        )

        self.assertEqual(["dijkstra_time", "astar_time"], comparison["presetIds"])
        self.assertEqual(2, len(comparison["runs"]))
        self.assertTrue(comparison["routeRows"])

    def test_workbench_can_save_configured_scenario(self):
        saved = save_configured_scenario(
            {
                "scenarioPath": str(EXAMPLES / "minimal_scenario_model.json"),
                "saveName": "unit_workbench_saved",
                "config": {
                    "timeStepS": 0.25,
                    "maxSteps": 12,
                    "randomSeed": 7,
                    "firstGroupCount": 1,
                    "algorithm": "astar",
                    "costPolicy": "minimum_travel_time",
                    "destinationCells": ["CS_L00_ROOM_B"],
                    "useBeaconRisk": False,
                },
                "beacons": [],
                "scheduledEvents": [],
            },
            str(EXAMPLES / "minimal_scenario_model.json"),
        )
        saved_path = ROOT / saved["scenarioPath"]
        try:
            _, scenario = load_project(None, saved_path)
            self.assertEqual("unit_workbench_saved", saved_path.stem)
            self.assertEqual("astar", scenario.routing["algorithm"])
            self.assertEqual(12, scenario.max_steps)
        finally:
            saved_path.unlink(missing_ok=True)

    def test_workbench_can_save_routing_comparison_viewer(self):
        comparison = save_configured_routing_comparison(
            {
                "scenarioPath": str(EXAMPLES / "minimal_scenario_model.json"),
                "indoorPath": str(EXAMPLES / "minimal_indoor_model.json"),
                "comparisonOutputDir": "outputs/test_workbench_routing_compare",
                "presetIds": ["dijkstra_time", "astar_time"],
                "config": {
                    "timeStepS": 0.25,
                    "maxSteps": 8,
                    "randomSeed": 7,
                    "firstGroupCount": 1,
                    "algorithm": "astar",
                    "costPolicy": "minimum_travel_time",
                    "useBeaconRisk": False,
                },
                "beacons": [],
                "scheduledEvents": [],
            },
            str(EXAMPLES / "minimal_scenario_model.json"),
        )
        self.assertTrue((ROOT / comparison["html"]).exists())
        self.assertTrue((ROOT / comparison["metricsCsv"]).exists())
        self.assertEqual(["dijkstra_time", "astar_time"], comparison["presetIds"])

    def test_workbench_library_lists_available_scenarios_and_models(self):
        library = discover_model_library(EXAMPLES)
        scenario_paths = {item["path"] for item in library["scenarios"]}
        indoor_paths = {item["path"] for item in library["indoorModels"]}
        self.assertIn("examples/indoor_data_model/scenario_single_floor.json", scenario_paths)
        self.assertIn("examples/indoor_data_model/scenario_multilevel.json", scenario_paths)
        self.assertIn("examples/indoor_data_model/una_sola_planta_indoor_model.json", indoor_paths)
        self.assertIn("examples/indoor_data_model/tres_plantas_indoor_model.json", indoor_paths)

    def test_default_workbench_library_shows_user_models_only(self):
        library = discover_model_library()
        indoor_paths = {item["path"] for item in library["indoorModels"]}

        self.assertTrue(all(path.startswith("models/") for path in indoor_paths))
        self.assertNotIn("examples/indoor_data_model/una_sola_planta_indoor_model.json", indoor_paths)
        self.assertFalse(any(path.startswith("outputs/indoor_models/") for path in indoor_paths))

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
                    "costPolicy": "minimum_travel_time",
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
        self.assertGreaterEqual(payload["metrics"]["routePlans"], 1)
        self.assertIn("routeRecoveries", payload["metrics"])
        self.assertIn("noRouteEvents", payload["metrics"])
        self.assertIn("qa", payload)
        self.assertTrue(payload["trajectories"])
        self.assertIn("events", payload)
        self.assertTrue(any(event.get("eventType") == "route_planned" for event in payload["events"]))
        self.assertTrue(payload["routes"])
        self.assertIn("agentId", payload["routes"][0])
        self.assertIn("profileId", payload["routes"][0])
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

    def test_transfer_capacity_is_released_while_crossing_via_room(self):
        payload = run_configured_simulation(
            {
                "scenarioPath": str(EXAMPLES / "scenario_single_floor.json"),
                "config": {
                    "timeStepS": 0.5,
                    "maxSteps": 20,
                    "randomSeed": 7,
                    "algorithm": "astar",
                    "costPolicy": "minimum_travel_time",
                    "destinationCells": ["CS_L00_EXIT_001"],
                },
                "manualAgents": [
                    {
                        "agentId": "MANUAL_DOOR_RELEASE_001",
                        "mobilityProfileRef": "MP_WALKING",
                        "initialCellSpaceRef": "CS_L00_DOOR_001",
                        "initialPosition": {"type": "Point", "coordinates": [3.5, 8.55]},
                    }
                ],
                "beacons": [],
                "scheduledEvents": [],
            },
            str(EXAMPLES / "scenario_single_floor.json"),
        )

        self.assertTrue(
            any(
                row["cellSpaceRef"] == "CS_L00_ROOM_029" and row["routeNextCell"] == "CS_L00_DOOR_012"
                for row in payload["trajectories"]
            )
        )

    def test_walking_profiles_keep_stairs_and_rolling_filters_them(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_single_floor.json")
        topology = EvacTopology.from_indoor_model(indoor)

        def connector_counts(profile_id: str) -> tuple[int, int]:
            snapshot = RoutingEngine(topology).compiler.compile(
                mobility_profile=scenario.mobility_profiles[profile_id],
                routing_config={**scenario.physics, **scenario.routing},
            )
            stair = 0
            ramp = 0
            for source, target, data in snapshot.graph.edges(data=True):
                raw = data.get("raw") or {}
                refs = [source, target, raw.get("viaSpaceRef"), raw.get("transferSpaceRef"), *((raw.get("viaSpaceRefs") or []))]
                categories = {indoor.cells_by_id[ref].category for ref in refs if ref in indoor.cells_by_id}
                if raw.get("connectorType") == "Stair" or "Stair" in categories:
                    stair += 1
                if raw.get("connectorType") == "Ramp" or "Ramp" in categories:
                    ramp += 1
            return stair, ramp

        walking_stair, walking_ramp = connector_counts("MP_WALKING")
        rolling_stair, rolling_ramp = connector_counts("MP_ROLLING_ACCESSIBLE")

        self.assertGreater(walking_stair, 0)
        self.assertGreater(walking_ramp, 0)
        self.assertEqual(0, rolling_stair)
        self.assertGreater(rolling_ramp, 0)

    def test_walking_route_can_use_stair_on_transfer_to_transfer_graph(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_single_floor.json")
        topology = EvacTopology.from_indoor_model(indoor)
        route = RoutingEngine(topology).find_route(
            "CS_L00_ROOM_017",
            target_refs=scenario.routing["destination"]["cellSpaceRefs"],
            mobility_profile=scenario.mobility_profiles["MP_WALKING"],
            algorithm="dijkstra",
            routing_config={**scenario.physics, **scenario.routing},
        )

        self.assertEqual("multilevel_transfer_to_transfer", topology.graph_view_name)
        self.assertTrue(route.reachable)
        categories = [indoor.cells_by_id[node].category for node in route.node_sequence if node in indoor.cells_by_id]
        self.assertIn("Stair", categories)
        self.assertIn("firstStep", route.weight_breakdown)
        self.assertIn("originCandidates", route.weight_breakdown)
        self.assertTrue(route.weight_breakdown["originCandidates"])
        self.assertIn("routeTotal", route.weight_breakdown["originCandidates"][0])
        self.assertIn("suffixPath", route.weight_breakdown["originCandidates"][0])

    def test_graph_origin_position_reduces_remaining_first_edge_cost(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_single_floor.json")
        topology = EvacTopology.from_indoor_model(indoor)
        engine = RoutingEngine(topology)
        routing_config = {**scenario.physics, **scenario.routing}
        found_progressive_edge = False
        for source, target, data in topology.graph.edges(data=True):
            source_pos = topology.node_position(source)
            target_pos = topology.node_position(target)
            if not source_pos or not target_pos or float(data.get("lengthM") or 0) <= 0.5:
                continue
            near_target = (source_pos[0] * 0.2 + target_pos[0] * 0.8, source_pos[1] * 0.2 + target_pos[1] * 0.8)
            baseline = engine.find_route(
                source,
                target_refs=[target],
                mobility_profile=scenario.mobility_profiles["MP_WALKING"],
                algorithm="dijkstra",
                routing_config=routing_config,
            )
            progressed = engine.find_route(
                source,
                target_refs=[target],
                mobility_profile=scenario.mobility_profiles["MP_WALKING"],
                algorithm="dijkstra",
                routing_config=routing_config,
                origin_position=near_target,
                origin_level=topology.node_level(source),
            )
            if baseline.reachable and progressed.reachable and progressed.total_cost < baseline.total_cost:
                found_progressive_edge = True
                break

        self.assertTrue(found_progressive_edge)

    def test_stair_and_ramp_capacity_apply_to_vertical_endpoints(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_single_floor.json")
        scenario.physics["stairCapacity"] = 3
        scenario.physics["rampCapacity"] = 2
        model = EvacuationModel(indoor, scenario)

        self.assertEqual(3, model._transfer_capacity("CS_L00_EP_VC_004_LEVEL_00_ENTRY"))
        self.assertEqual(2, model._transfer_capacity("CS_L00_EP_VC_001_LEVEL_00_ENTRY"))

    def test_linear_transfer_does_not_self_block_after_entry(self):
        indoor, scenario = load_project(None, EXAMPLES / "scenario_single_floor.json")
        model = EvacuationModel(indoor, scenario)

        self.assertTrue(model._requires_transfer_capacity("CS_L00_ROOM_017", "CS_L00_EP_VC_003_LEVEL_00_ENTRY"))
        self.assertFalse(model._requires_transfer_capacity("CS_L00_EP_VC_003_LEVEL_00_ENTRY", "CS_L00_EP_VC_003_LEVEL_00_EXIT"))


if __name__ == "__main__":
    unittest.main()

import unittest

import networkx as nx

from src.evac_engine.rerouting_centrality import (
    cer_node_scores,
    failure_units_for_path,
    remove_failure_units,
    rerouting_evacuation_centrality,
)
from src.evac_engine.route_recommendation import EvacuationRouteRecommendationService, RouteRecommendationConfig


def edge(graph: nx.DiGraph, source: str, target: str, weight: float, resource: str) -> None:
    graph.add_edge(source, target, weight=weight, resourceRef=resource, arcId=f"{source}_{target}")


class ReroutingCentralityTests(unittest.TestCase):
    def test_chain_has_zero_cer_when_single_failure_breaks_route(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")

        result = rerouting_evacuation_centrality(
            graph,
            ["T"],
            sources=["S"],
            failure_profiles=[(1,)],
            max_runtime_ms=500,
        ).to_dict()

        self.assertEqual(0, result["nodes"]["S"]["targets"]["T"]["profiles"]["(1)"]["distinctRoutes"])

    def test_equivalent_alternative_counts_once_in_exact_mode(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")

        result = rerouting_evacuation_centrality(
            graph,
            ["T"],
            sources=["S"],
            failure_profiles=[(1,)],
            max_runtime_ms=500,
        ).to_dict()

        profile = result["nodes"]["S"]["targets"]["T"]["profiles"]["(1)"]
        self.assertEqual(1, profile["distinctRoutes"])
        self.assertEqual(2, profile["acceptedCases"])
        self.assertEqual(1, profile["duplicateRouteCases"])

    def test_multiple_targets_skip_self_target_without_hiding_detail(self):
        graph = nx.DiGraph()
        edge(graph, "A", "B", 1.0, "R_AB")
        edge(graph, "B", "EXIT_1", 1.0, "R_B1")
        edge(graph, "B", "EXIT_2", 1.0, "R_B2")

        result = rerouting_evacuation_centrality(
            graph,
            ["EXIT_1", "EXIT_2"],
            sources=["A", "EXIT_1"],
            failure_profiles=[(1,)],
            max_runtime_ms=500,
        ).to_dict()

        self.assertIn("EXIT_1", result["nodes"]["A"]["targets"])
        self.assertIn("EXIT_2", result["nodes"]["A"]["targets"])
        self.assertTrue(result["nodes"]["EXIT_1"]["targets"]["EXIT_1"]["skippedSelf"])
        self.assertIn("EXIT_2", result["nodes"]["EXIT_1"]["targets"])

    def test_profile_1_1_replans_then_fails_edge_on_new_route(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")
        edge(graph, "S", "C", 1.1, "R_SC")
        edge(graph, "C", "T", 1.1, "R_CT")

        result = rerouting_evacuation_centrality(
            graph,
            ["T"],
            sources=["S"],
            failure_profiles=[(1, 1)],
            cost_tolerance=0.2,
            max_runtime_ms=500,
        ).to_dict()

        profile = result["nodes"]["S"]["targets"]["T"]["profiles"]["(1,1)"]
        self.assertGreaterEqual(profile["evaluatedFailureCases"], 4)
        self.assertGreaterEqual(profile["distinctRoutes"], 1)

    def test_profile_2_removes_simultaneous_failures(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")

        result = rerouting_evacuation_centrality(
            graph,
            ["T"],
            sources=["S"],
            failure_profiles=[(2,)],
            max_runtime_ms=500,
        ).to_dict()

        profile = result["nodes"]["S"]["targets"]["T"]["profiles"]["(2)"]
        self.assertEqual(1, profile["evaluatedFailureCases"])
        self.assertEqual(1, profile["distinctRoutes"])

    def test_tolerance_rejects_route_above_cost_limit(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 2.0, "R_SB")
        edge(graph, "B", "T", 2.0, "R_BT")

        result = rerouting_evacuation_centrality(
            graph,
            ["T"],
            sources=["S"],
            failure_profiles=[(1,)],
            cost_tolerance=0.1,
            max_runtime_ms=500,
        ).to_dict()

        profile = result["nodes"]["S"]["targets"]["T"]["profiles"]["(1)"]
        self.assertEqual(0, profile["distinctRoutes"])
        self.assertEqual(2, profile["overToleranceCases"])

    def test_failure_unit_resource_removes_all_arcs_with_same_resource(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SHARED")
        edge(graph, "A", "S", 1.0, "R_SHARED")
        units = failure_units_for_path(graph, ["S", "A"], "resource")

        remove_failure_units(graph, units)

        self.assertFalse(graph.has_edge("S", "A"))
        self.assertFalse(graph.has_edge("A", "S"))

    def test_cer_weighted_policy_prefers_higher_cer_route(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.1, "R_SB")
        edge(graph, "B", "T", 1.1, "R_BT")

        service = EvacuationRouteRecommendationService()
        candidate = service.recommend(
            graph,
            "S",
            ["T"],
            config=RouteRecommendationConfig(
                algorithm="dijkstra",
                route_selection="cer_weighted",
                centrality_type="rerouting",
                rerouting_enabled=True,
                rerouting_centrality_by_node={"A": 0.0, "B": 10.0, "T": 0.0},
                agility_weight=0.5,
            ),
        )

        self.assertIsNotNone(candidate)
        self.assertEqual(["S", "B", "T"], candidate.node_sequence)
        self.assertEqual("cer_weighted", candidate.metrics["routeSelection"])
        self.assertGreater(candidate.metrics["reroutingAgility"], 0.0)

    def test_node_scores_sum_primary_detail(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")

        result = rerouting_evacuation_centrality(graph, ["T"], sources=["S"], failure_profiles=[(1,)])
        scores = cer_node_scores(result)

        self.assertEqual(1.0, scores["S"])


if __name__ == "__main__":
    unittest.main()

import unittest

import networkx as nx

from src.evac_engine.cer_tree import CERTreeConfig, compute_cer_tree, path_to_failure_units, remove_failure_units


def edge(graph: nx.DiGraph, source: str, target: str, weight: float, resource: str) -> None:
    graph.add_edge(source, target, weight=weight, resourceRef=resource, arcId=f"{source}_{target}")


class CERTreeTests(unittest.TestCase):
    def test_tree_reports_profiles_and_core_metrics(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")
        edge(graph, "S", "C", 1.2, "R_SC")
        edge(graph, "C", "T", 1.2, "R_CT")

        payload = compute_cer_tree(
            graph,
            ["T"],
            origins=["S"],
            config=CERTreeConfig(tau=0.3, max_depth=2, max_k=1, max_total_failures=2, max_runtime_ms=1000),
        )

        target = payload["nodes"]["S"]["targets"]["T"]
        profile_1 = target["failureProfiles"]["(1)"]
        self.assertGreaterEqual(profile_1["distinctRoutes"], 1)
        self.assertGreaterEqual(profile_1["acceptedCases"], profile_1["distinctRoutes"])
        self.assertGreater(profile_1["totalCases"], 0)
        self.assertIn("(1,1)", target["failureProfiles"])
        self.assertFalse(payload["metadata"]["truncatedByRuntime"])

    def test_resource_failure_removes_all_edges_with_same_resource(self):
        graph = nx.DiGraph()
        edge(graph, "A", "B", 1.0, "R_SHARED")
        edge(graph, "B", "A", 1.0, "R_SHARED")

        units = path_to_failure_units(graph, ["A", "B"], "resource")
        remove_failure_units(graph, units)

        self.assertFalse(graph.has_edge("A", "B"))
        self.assertFalse(graph.has_edge("B", "A"))

    def test_failure_profiles_filter_expansion(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")
        edge(graph, "S", "C", 1.2, "R_SC")
        edge(graph, "C", "T", 1.2, "R_CT")

        payload = compute_cer_tree(
            graph,
            ["T"],
            origins=["S"],
            config=CERTreeConfig(
                tau=0.3,
                max_depth=2,
                max_k=1,
                max_total_failures=2,
                max_runtime_ms=1000,
                failure_profiles=((1,),),
            ),
        )

        profiles = payload["nodes"]["S"]["targets"]["T"]["failureProfiles"]
        self.assertIn("(1)", profiles)
        self.assertNotIn("(1,1)", profiles)

    def test_target_summary_deduplicates_routes_across_profiles(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")
        edge(graph, "S", "C", 1.2, "R_SC")
        edge(graph, "C", "T", 1.2, "R_CT")

        payload = compute_cer_tree(
            graph,
            ["T"],
            origins=["S"],
            config=CERTreeConfig(tau=0.3, max_depth=2, max_k=1, max_total_failures=2, max_runtime_ms=1000),
        )

        target = payload["nodes"]["S"]["targets"]["T"]
        summary = target["summary"]
        profile_sum = sum(profile["distinctRoutes"] for profile in target["failureProfiles"].values())

        self.assertEqual(summary["profileDistinctRoutes"], profile_sum)
        self.assertLessEqual(summary["uniqueDistinctRoutes"], summary["profileDistinctRoutes"])
        self.assertEqual(summary["distinctRoutes"], summary["uniqueDistinctRoutes"])
        self.assertEqual(
            summary["repeatedRoutesAcrossProfiles"],
            summary["profileDistinctRoutes"] - summary["uniqueDistinctRoutes"],
        )

    def test_debug_none_keeps_aggregate_counters_without_steps(self):
        graph = nx.DiGraph()
        edge(graph, "S", "A", 1.0, "R_SA")
        edge(graph, "A", "T", 1.0, "R_AT")
        edge(graph, "S", "B", 1.0, "R_SB")
        edge(graph, "B", "T", 1.0, "R_BT")

        payload = compute_cer_tree(
            graph,
            ["T"],
            origins=["S"],
            config=CERTreeConfig(tau=0.3, max_depth=2, max_k=1, max_total_failures=2, max_runtime_ms=1000, debug_steps="none"),
        )

        self.assertEqual(payload["debugSteps"], [])
        self.assertEqual(payload["metadata"]["debugStepCount"], 0)
        self.assertGreater(payload["metadata"]["calculationStepCount"], 0)
        self.assertTrue(payload["metadata"]["decisionCounts"])
        self.assertTrue(payload["metadata"]["branchDeathReasonCounts"])


if __name__ == "__main__":
    unittest.main()

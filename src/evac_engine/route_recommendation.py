"""Route recommendation metrics derived from evacuation-centrality research."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import islice
from typing import Any, Callable, Iterable

import networkx as nx


SUPPORTED_ROUTE_ALGORITHMS = {"dijkstra", "astar", "yen_ksp", "robust_agility"}
ADVANCED_ROUTE_SELECTIONS = {"highest_robustness", "highest_agility", "robust_agility"}


@dataclass(slots=True)
class RouteRecommendationConfig:
    algorithm: str = "dijkstra"
    route_selection: str = "lowest_cost"
    k_shortest_paths: int = 6
    candidate_cost_tolerance: float = 0.35
    robustness_tolerance: float = 0.2
    centrality_tolerance: float = 0.35
    centrality_max_paths: int = 8
    centrality_max_overlap: float = 0.8
    cost_weight: float = 1.0
    robustness_weight: float = 0.35
    agility_weight: float = 0.35
    agility_aggregation: str = "mean"

    @classmethod
    def from_routing_config(cls, algorithm: str, routing_config: dict[str, Any] | None = None) -> "RouteRecommendationConfig":
        routing_config = routing_config or {}
        raw = dict(routing_config.get("routeRecommendation") or {})
        selection = str(raw.get("routeSelection") or ("robust_agility" if algorithm == "robust_agility" else "lowest_cost"))
        return cls(
            algorithm=algorithm,
            route_selection=selection,
            k_shortest_paths=_positive_int(raw.get("kShortestPaths"), 6),
            candidate_cost_tolerance=_non_negative_float(raw.get("candidateCostTolerance"), 0.35),
            robustness_tolerance=_non_negative_float(raw.get("robustnessTolerance"), 0.2),
            centrality_tolerance=_non_negative_float(raw.get("centralityTolerance"), 0.35),
            centrality_max_paths=_positive_int(raw.get("centralityMaxPaths"), 8),
            centrality_max_overlap=_bounded_float(raw.get("centralityMaxOverlap"), 0.8, 0.0, 1.0),
            cost_weight=_non_negative_float(raw.get("costWeight"), 1.0),
            robustness_weight=_non_negative_float(raw.get("robustnessWeight"), 0.35),
            agility_weight=_non_negative_float(raw.get("agilityWeight"), 0.35),
            agility_aggregation=str(raw.get("agilityAggregation") or "mean"),
        )


@dataclass(slots=True)
class RouteCandidate:
    node_sequence: list[str]
    destination: str
    total_cost: float
    metrics: dict[str, Any] = field(default_factory=dict)


class EvacuationRouteRecommendationService:
    """Select routes using cost, robustness and evacuation-centrality proxies.

    The centrality approximation counts efficient, sufficiently dissimilar paths
    from a node to any evacuation target. It keeps the research idea explicit
    while staying cheap enough to run against the current per-tick graph.
    """

    def recommend(
        self,
        graph: nx.Graph,
        origin: str,
        targets: Iterable[str],
        *,
        heuristic: Callable[[str, str], float] | None = None,
        config: RouteRecommendationConfig | None = None,
        weight: str = "weight",
    ) -> RouteCandidate | None:
        config = config or RouteRecommendationConfig()
        targets = [target for target in targets if target in graph]
        if origin not in graph or not targets:
            return None
        if config.algorithm not in SUPPORTED_ROUTE_ALGORITHMS:
            return None

        use_k_paths = config.algorithm in {"yen_ksp", "robust_agility"} or config.route_selection in ADVANCED_ROUTE_SELECTIONS
        if use_k_paths:
            candidates = self._k_shortest_candidates(graph, origin, targets, config.k_shortest_paths, weight)
        else:
            candidates = self._single_shortest_candidates(graph, origin, targets, config.algorithm, heuristic, weight)
        if not candidates:
            return None

        if config.route_selection == "lowest_cost" and config.algorithm != "robust_agility":
            selected = min(candidates, key=lambda item: (item.total_cost, len(item.node_sequence), item.destination))
            selected.metrics = self._basic_metrics(graph, selected, candidates, config, targets, weight)
            return selected

        filtered = self._within_cost_tolerance(candidates, config.candidate_cost_tolerance)
        self._annotate_candidates(graph, filtered, config, targets, weight)
        selected = self._select_advanced_candidate(filtered, config)
        selected.metrics["candidateCount"] = len(candidates)
        selected.metrics["eligibleCandidateCount"] = len(filtered)
        return selected

    def evacuation_centrality(
        self,
        graph: nx.Graph,
        targets: Iterable[str],
        *,
        sources: Iterable[str] | None = None,
        tolerance: float = 0.35,
        max_paths: int = 8,
        max_overlap: float = 0.8,
        weight: str = "weight",
    ) -> dict[Any, float]:
        targets = [target for target in targets if target in graph]
        if not targets:
            return {}
        source_list = list(sources) if sources is not None else list(graph.nodes)
        centrality: dict[Any, float] = {}
        for source in source_list:
            if source not in graph:
                centrality[source] = 0.0
                continue
            accepted_count = 0
            for target in targets:
                if source == target:
                    continue
                accepted_signatures: list[set[Any]] = []
                base_cost: float | None = None
                try:
                    path_iter = nx.shortest_simple_paths(graph, source, target, weight=weight)
                    for path in islice(path_iter, max_paths):
                        cost = _path_cost(graph, path, weight)
                        if not math.isfinite(cost):
                            continue
                        if base_cost is None:
                            base_cost = cost
                        if base_cost is not None and cost > base_cost * (1.0 + tolerance):
                            break
                        signature = _path_signature(graph, path)
                        if _is_sufficiently_dissimilar(signature, accepted_signatures, max_overlap):
                            accepted_signatures.append(signature)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    pass
                accepted_count += len(accepted_signatures)
            centrality[source] = float(accepted_count)
        return centrality

    def robustness_index(self, graph: nx.Graph, path: list[str], tolerance: float = 0.2, weight: str = "weight") -> float:
        if len(path) < 2:
            return 0.0
        base_cost = _path_cost(graph, path, weight)
        if not math.isfinite(base_cost):
            return 0.0
        limit = base_cost * (1.0 + tolerance)
        robust_edges = 0
        total_edges = 0
        for source, target in zip(path, path[1:]):
            total_edges += 1
            test_graph = graph.copy()
            _remove_failed_connection(test_graph, source, target)
            try:
                alternative_cost = nx.shortest_path_length(test_graph, path[0], path[-1], weight=weight)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if float(alternative_cost) <= limit:
                robust_edges += 1
        return robust_edges / total_edges if total_edges else 0.0

    def route_agility(
        self,
        path: list[str],
        centrality: dict[Any, float],
        *,
        aggregation: str = "mean",
    ) -> float:
        intermediates = path[1:-1]
        if not intermediates:
            return 0.0
        values = [max(0.0, float(centrality.get(node, 0.0))) for node in intermediates]
        if aggregation == "geometric":
            product = 1.0
            for value in values:
                product *= max(value, 1e-9)
            return product ** (1.0 / len(values))
        return sum(values) / len(values)

    def _single_shortest_candidates(
        self,
        graph: nx.Graph,
        origin: str,
        targets: list[str],
        algorithm: str,
        heuristic: Callable[[str, str], float] | None,
        weight: str,
    ) -> list[RouteCandidate]:
        candidates = []
        for target in targets:
            try:
                if algorithm == "astar":
                    path = nx.astar_path(graph, origin, target, heuristic=heuristic or _zero_heuristic, weight=weight)
                else:
                    path = nx.shortest_path(graph, origin, target, weight=weight)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            candidates.append(RouteCandidate(list(path), target, _path_cost(graph, path, weight)))
        return candidates

    def _k_shortest_candidates(
        self,
        graph: nx.Graph,
        origin: str,
        targets: list[str],
        k_paths: int,
        weight: str,
    ) -> list[RouteCandidate]:
        candidates = []
        seen: set[tuple[str, ...]] = set()
        for target in targets:
            try:
                path_iter = nx.shortest_simple_paths(graph, origin, target, weight=weight)
                for path in islice(path_iter, k_paths):
                    key = tuple(path)
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(RouteCandidate(list(path), target, _path_cost(graph, path, weight)))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        candidates.sort(key=lambda item: (item.total_cost, len(item.node_sequence), item.destination))
        return candidates

    def _within_cost_tolerance(self, candidates: list[RouteCandidate], tolerance: float) -> list[RouteCandidate]:
        best_cost = min(item.total_cost for item in candidates)
        if best_cost <= 0.0 or not math.isfinite(best_cost):
            return list(candidates)
        limit = best_cost * (1.0 + tolerance)
        return [item for item in candidates if item.total_cost <= limit] or [min(candidates, key=lambda item: item.total_cost)]

    def _annotate_candidates(
        self,
        graph: nx.Graph,
        candidates: list[RouteCandidate],
        config: RouteRecommendationConfig,
        targets: list[str],
        weight: str,
    ) -> None:
        route_nodes = {node for candidate in candidates for node in candidate.node_sequence[1:-1]}
        centrality = self.evacuation_centrality(
            graph,
            targets,
            sources=route_nodes,
            tolerance=config.centrality_tolerance,
            max_paths=config.centrality_max_paths,
            max_overlap=config.centrality_max_overlap,
            weight=weight,
        )
        best_cost = min(item.total_cost for item in candidates)
        max_agility = 0.0
        for candidate in candidates:
            robustness = self.robustness_index(graph, candidate.node_sequence, config.robustness_tolerance, weight)
            agility = self.route_agility(candidate.node_sequence, centrality, aggregation=config.agility_aggregation)
            candidate.metrics = {
                "robustness": round(robustness, 6),
                "agility": round(agility, 6),
                "evacuationCentrality": {node: round(float(centrality.get(node, 0.0)), 6) for node in candidate.node_sequence[1:-1]},
                "costRatio": round(candidate.total_cost / best_cost, 6) if best_cost > 0 else 1.0,
            }
            max_agility = max(max_agility, agility)
        for candidate in candidates:
            cost_ratio = float(candidate.metrics["costRatio"])
            robustness = float(candidate.metrics["robustness"])
            agility = float(candidate.metrics["agility"])
            agility_norm = agility / max_agility if max_agility > 0 else 0.0
            score = (
                config.robustness_weight * robustness
                + config.agility_weight * agility_norm
                - config.cost_weight * max(0.0, cost_ratio - 1.0)
            )
            candidate.metrics["selectionScore"] = round(score, 6)

    def _basic_metrics(
        self,
        graph: nx.Graph,
        candidate: RouteCandidate,
        candidates: list[RouteCandidate],
        config: RouteRecommendationConfig,
        targets: list[str],
        weight: str,
    ) -> dict[str, Any]:
        if config.algorithm not in {"yen_ksp", "robust_agility"}:
            return {}
        filtered = self._within_cost_tolerance(candidates, config.candidate_cost_tolerance)
        self._annotate_candidates(graph, filtered, config, targets, weight)
        for item in filtered:
            if item.node_sequence == candidate.node_sequence:
                item.metrics["candidateCount"] = len(candidates)
                item.metrics["eligibleCandidateCount"] = len(filtered)
                return item.metrics
        return {"candidateCount": len(candidates), "eligibleCandidateCount": len(filtered)}

    @staticmethod
    def _select_advanced_candidate(candidates: list[RouteCandidate], config: RouteRecommendationConfig) -> RouteCandidate:
        if config.route_selection == "highest_robustness":
            return max(candidates, key=lambda item: (item.metrics["robustness"], -item.total_cost, item.metrics["agility"]))
        if config.route_selection == "highest_agility":
            return max(candidates, key=lambda item: (item.metrics["agility"], item.metrics["robustness"], -item.total_cost))
        return max(candidates, key=lambda item: (item.metrics["selectionScore"], item.metrics["robustness"], -item.total_cost))


def _path_cost(graph: nx.Graph, path: Iterable[str], weight: str) -> float:
    nodes = list(path)
    total = 0.0
    for source, target in zip(nodes, nodes[1:]):
        data = graph.get_edge_data(source, target)
        if data is None:
            return math.inf
        edge_data = _edge_data(data, weight)
        total += float(edge_data.get(weight, 1.0))
    return total


def _edge_data(data: dict[str, Any], weight: str) -> dict[str, Any]:
    if weight in data:
        return data
    weighted_edges = [value for value in data.values() if isinstance(value, dict)]
    if not weighted_edges:
        return {}
    return min(weighted_edges, key=lambda item: float(item.get(weight, 1.0)))


def _path_signature(graph: nx.Graph, path: list[str]) -> set[Any]:
    signature = set()
    for source, target in zip(path, path[1:]):
        data = graph.get_edge_data(source, target) or {}
        edge_data = _edge_data(data, "weight")
        signature.add(edge_data.get("resourceRef") or edge_data.get("arcId") or (source, target))
    return signature


def _is_sufficiently_dissimilar(signature: set[Any], accepted: list[set[Any]], max_overlap: float) -> bool:
    if not signature:
        return False
    for existing in accepted:
        union = signature | existing
        overlap = len(signature & existing) / len(union) if union else 1.0
        if overlap > max_overlap:
            return False
    return True


def _remove_failed_connection(graph: nx.Graph, source: str, target: str) -> None:
    data = graph.get_edge_data(source, target) or {}
    edge_data = _edge_data(data, "weight")
    resource_ref = edge_data.get("resourceRef")
    if resource_ref:
        for left, right, item in list(graph.edges(data=True)):
            if item.get("resourceRef") == resource_ref and graph.has_edge(left, right):
                graph.remove_edge(left, right)
        return
    if graph.has_edge(source, target):
        graph.remove_edge(source, target)


def _zero_heuristic(_left: str, _right: str) -> float:
    return 0.0


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0.0 else default


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    parsed = _non_negative_float(value, default)
    return min(max(parsed, minimum), maximum)

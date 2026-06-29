"""Rerouting-based evacuation centrality (CER).

CER is intentionally separate from the lighter evacuation_centrality proxy in
route_recommendation.py. It counts distinct acceptable reroutes after resource
failures on the weighted operational graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, product
import math
import time
from typing import Any, Iterable

import networkx as nx


FailureUnit = tuple[str, str]


@dataclass(slots=True)
class CERDebugStep:
    origin: str
    target: str
    failure_profile: tuple[int, ...]
    failure_depth: int
    failed_units: list[FailureUnit]
    newly_failed_units: list[FailureUnit]
    base_path: list[str]
    failure_source_path: list[str]
    candidate_path: list[str]
    base_cost: float
    candidate_cost: float | None
    cost_limit: float
    accepted: bool
    reason: str
    distinct_route_count: int
    evaluated_failure_cases: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "target": self.target,
            "failureProfile": profile_label(self.failure_profile),
            "failureProfileRaw": list(self.failure_profile),
            "failureDepth": self.failure_depth,
            "failedUnits": [{"kind": kind, "value": value} for kind, value in self.failed_units],
            "newlyFailedUnits": [{"kind": kind, "value": value} for kind, value in self.newly_failed_units],
            "failedResources": [value for kind, value in self.failed_units if kind == "resource"],
            "newlyFailedResources": [value for kind, value in self.newly_failed_units if kind == "resource"],
            "failedArcs": [value for kind, value in self.failed_units if kind == "arc"],
            "newlyFailedArcs": [value for kind, value in self.newly_failed_units if kind == "arc"],
            "basePath": list(self.base_path),
            "failureSourcePath": list(self.failure_source_path),
            "candidatePath": list(self.candidate_path),
            "baseCost": round(self.base_cost, 6),
            "candidateCost": round(self.candidate_cost, 6) if self.candidate_cost is not None else None,
            "costLimit": round(self.cost_limit, 6),
            "accepted": self.accepted,
            "reason": self.reason,
            "distinctRouteCount": self.distinct_route_count,
            "evaluatedFailureCases": self.evaluated_failure_cases,
        }


@dataclass(slots=True)
class CERProfileStats:
    profile: tuple[int, ...]
    base_path: list[str]
    base_cost: float
    cost_limit: float
    distinct_routes: int = 0
    accepted_cases: int = 0
    evaluated_failure_cases: int = 0
    no_path_cases: int = 0
    over_tolerance_cases: int = 0
    duplicate_route_cases: int = 0
    pruned_cases: int = 0
    timeout: bool = False
    truncated: bool = False
    accepted_route_signatures: set[tuple[str, ...]] = field(default_factory=set)

    def to_dict(self, *, store_routes: bool = False) -> dict[str, Any]:
        payload = {
            "distinctRoutes": self.distinct_routes,
            "acceptedCases": self.accepted_cases,
            "evaluatedFailureCases": self.evaluated_failure_cases,
            "noPathCases": self.no_path_cases,
            "overToleranceCases": self.over_tolerance_cases,
            "duplicateRouteCases": self.duplicate_route_cases,
            "prunedCases": self.pruned_cases,
            "baseCost": round(self.base_cost, 6),
            "costLimit": round(self.cost_limit, 6),
            "basePath": list(self.base_path) if store_routes else None,
            "timeout": self.timeout,
            "truncated": self.truncated,
        }
        if store_routes:
            payload["distinctRouteSignatures"] = [list(item) for item in sorted(self.accepted_route_signatures)]
        else:
            payload.pop("basePath")
        return payload


@dataclass(slots=True)
class CERResult:
    metadata: dict[str, Any]
    nodes: dict[str, dict[str, Any]]
    debug_steps: list[CERDebugStep] = field(default_factory=list)

    def to_dict(self, *, store_routes: bool | None = None) -> dict[str, Any]:
        should_store_routes = bool(self.metadata.get("storeRoutes")) if store_routes is None else store_routes
        nodes: dict[str, Any] = {}
        for origin, origin_payload in self.nodes.items():
            targets: dict[str, Any] = {}
            for target, target_payload in origin_payload.get("targets", {}).items():
                profiles: dict[str, Any] = {}
                for label, stats in target_payload.get("profiles", {}).items():
                    profiles[label] = stats.to_dict(store_routes=should_store_routes) if isinstance(stats, CERProfileStats) else dict(stats)
                targets[target] = {"profiles": profiles}
                if target_payload.get("skippedSelf"):
                    targets[target]["skippedSelf"] = True
                if target_payload.get("unreachable"):
                    targets[target]["unreachable"] = True
            nodes[origin] = {
                "targets": targets,
                "summary": dict(origin_payload.get("summary") or {}),
            }
        return {
            "metadata": dict(self.metadata),
            "nodes": nodes,
            "debugSteps": [step.to_dict() for step in self.debug_steps],
        }


def rerouting_evacuation_centrality(
    graph: nx.Graph,
    targets: Iterable[str],
    *,
    sources: Iterable[str] | None = None,
    failure_profiles: Iterable[Iterable[int]] | None = None,
    failure_unit: str = "resource",
    cost_tolerance: float = 0.35,
    distinctness_policy: str = "exact",
    max_depth: int = 3,
    max_k: int = 3,
    max_combinations: int = 500,
    max_runtime_ms: int = 1000,
    max_overlap: float = 0.8,
    weight: str = "weight",
    graph_view: str | None = None,
    store_routes: bool = False,
    store_failure_cases: bool = False,
    debug_pairs: set[tuple[str, str]] | None = None,
) -> CERResult:
    """Compute CER per origin, target and failure profile.

    The input graph is assumed to be the operational routing graph. If it is a
    weighted snapshot, its existing node/edge filtering is respected.
    """

    start = time.perf_counter()
    targets = [str(target) for target in targets if target in graph]
    source_list = [str(source) for source in (sources if sources is not None else graph.nodes) if source in graph]
    profiles = normalize_failure_profiles(failure_profiles, max_depth=max_depth, max_k=max_k)
    max_combinations = max(1, int(max_combinations))
    max_runtime_s = max(0.001, float(max_runtime_ms) / 1000.0)
    cost_tolerance = max(0.0, float(cost_tolerance))
    failure_unit = str(failure_unit or "resource")
    distinctness_policy = str(distinctness_policy or "exact")
    metadata = {
        "metric": "rerouting_evacuation_centrality",
        "graphView": graph_view,
        "failureUnit": failure_unit,
        "failureProfiles": [profile_label(profile) for profile in profiles],
        "costTolerance": cost_tolerance,
        "gamma": 1.0 + cost_tolerance,
        "distinctnessPolicy": distinctness_policy,
        "maxDepth": int(max_depth),
        "maxK": int(max_k),
        "maxCombinations": max_combinations,
        "maxRuntimeMs": int(max_runtime_ms),
        "maxOverlap": float(max_overlap),
        "storeRoutes": bool(store_routes),
    }
    nodes: dict[str, dict[str, Any]] = {}
    debug_steps: list[CERDebugStep] = []

    for origin in source_list:
        origin_payload: dict[str, Any] = {"targets": {}, "summary": {}}
        for target in targets:
            if origin == target:
                origin_payload["targets"][target] = {"skippedSelf": True, "profiles": {}}
                continue
            target_profiles: dict[str, CERProfileStats] = {}
            try:
                base_path = [str(node) for node in nx.shortest_path(graph, origin, target, weight=weight)]
                base_cost = path_cost(graph, base_path, weight)
                if not math.isfinite(base_cost):
                    raise nx.NetworkXNoPath
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                origin_payload["targets"][target] = {"unreachable": True, "profiles": {}}
                continue
            cost_limit = base_cost * (1.0 + cost_tolerance)
            should_debug_pair = store_failure_cases and (debug_pairs is None or (origin, target) in debug_pairs)
            for profile in profiles:
                stats = CERProfileStats(profile=profile, base_path=base_path, base_cost=base_cost, cost_limit=cost_limit)
                seen_failures: set[tuple[FailureUnit, ...]] = set()
                _explore_failure_profile(
                    graph,
                    origin,
                    target,
                    profile,
                    depth=0,
                    current_path=base_path,
                    failed_units=[],
                    base_path=base_path,
                    base_cost=base_cost,
                    cost_limit=cost_limit,
                    failure_unit=failure_unit,
                    distinctness_policy=distinctness_policy,
                    max_overlap=float(max_overlap),
                    max_combinations=max_combinations,
                    deadline=start + max_runtime_s,
                    weight=weight,
                    stats=stats,
                    seen_failures=seen_failures,
                    debug_steps=debug_steps if should_debug_pair else None,
                )
                target_profiles[profile_label(profile)] = stats
            origin_payload["targets"][target] = {"profiles": target_profiles}
        origin_payload["summary"] = _origin_summary(origin_payload)
        nodes[origin] = origin_payload
        if (time.perf_counter() - start) >= max_runtime_s:
            metadata["timeout"] = True
            break
    metadata["runtimeMs"] = round((time.perf_counter() - start) * 1000.0, 6)
    return CERResult(metadata=metadata, nodes=nodes, debug_steps=debug_steps)


def cer_node_scores(result: CERResult | dict[str, Any], *, profile: str | None = None, target: str | None = None) -> dict[str, float]:
    payload = result.to_dict() if isinstance(result, CERResult) else result
    scores: dict[str, float] = {}
    for origin, origin_payload in (payload.get("nodes") or {}).items():
        total = 0.0
        for target_id, target_payload in (origin_payload.get("targets") or {}).items():
            if target is not None and target_id != target:
                continue
            if target_payload.get("skippedSelf") or target_payload.get("unreachable"):
                continue
            for label, stats in (target_payload.get("profiles") or {}).items():
                if profile is not None and label != profile:
                    continue
                total += float((stats or {}).get("distinctRoutes") or 0.0)
        scores[str(origin)] = total
    return scores


def normalize_failure_profiles(
    failure_profiles: Iterable[Iterable[int]] | None,
    *,
    max_depth: int,
    max_k: int,
) -> list[tuple[int, ...]]:
    if failure_profiles:
        profiles = []
        for raw in failure_profiles:
            profile = tuple(int(value) for value in raw if int(value) > 0)
            if profile:
                profiles.append(profile)
        return profiles or [(1,)]
    max_depth = max(1, int(max_depth))
    max_k = max(1, int(max_k))
    profiles = []
    for depth in range(1, max_depth + 1):
        profiles.extend(tuple(values) for values in product(range(1, max_k + 1), repeat=depth))
    return profiles


def profile_label(profile: Iterable[int]) -> str:
    return "(" + ",".join(str(int(value)) for value in profile) + ")"


def path_edges(path: list[str]) -> list[tuple[str, str]]:
    return [(str(path[index]), str(path[index + 1])) for index in range(len(path) - 1)]


def path_cost(graph: nx.Graph, path: Iterable[str], weight: str = "weight") -> float:
    total = 0.0
    nodes = list(path)
    for source, target in zip(nodes, nodes[1:]):
        edge = _selected_edge_data(graph, str(source), str(target), weight)
        if edge is None:
            return math.inf
        total += float(edge.get(weight, 1.0))
    return total


def _explore_failure_profile(
    graph: nx.Graph,
    origin: str,
    target: str,
    profile: tuple[int, ...],
    *,
    depth: int,
    current_path: list[str],
    failed_units: list[FailureUnit],
    base_path: list[str],
    base_cost: float,
    cost_limit: float,
    failure_unit: str,
    distinctness_policy: str,
    max_overlap: float,
    max_combinations: int,
    deadline: float,
    weight: str,
    stats: CERProfileStats,
    seen_failures: set[tuple[FailureUnit, ...]],
    debug_steps: list[CERDebugStep] | None,
) -> None:
    if stats.evaluated_failure_cases >= max_combinations:
        stats.truncated = True
        return
    if time.perf_counter() >= deadline:
        stats.timeout = True
        return
    k = int(profile[depth])
    units = failure_units_for_path(graph, current_path, failure_unit, weight)
    if len(units) < k:
        stats.pruned_cases += 1
        return
    for combo in combinations(units, k):
        accumulated = _canonical_failed_units([*failed_units, *combo])
        if accumulated in seen_failures:
            continue
        seen_failures.add(accumulated)
        newly_failed = _canonical_failed_units(combo)
        if stats.evaluated_failure_cases >= max_combinations:
            stats.truncated = True
            return
        if time.perf_counter() >= deadline:
            stats.timeout = True
            return
        stats.evaluated_failure_cases += 1
        test_graph = graph.copy()
        remove_failure_units(test_graph, accumulated)
        try:
            candidate_path = [str(node) for node in nx.shortest_path(test_graph, origin, target, weight=weight)]
            candidate_cost = path_cost(test_graph, candidate_path, weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            stats.no_path_cases += 1
            _append_debug(debug_steps, origin, target, profile, depth, accumulated, newly_failed, base_path, current_path, [], base_cost, None, cost_limit, False, "no_path", stats)
            continue
        if not math.isfinite(candidate_cost):
            stats.no_path_cases += 1
            _append_debug(debug_steps, origin, target, profile, depth, accumulated, newly_failed, base_path, current_path, [], base_cost, None, cost_limit, False, "no_path", stats)
            continue
        if candidate_cost > cost_limit:
            stats.over_tolerance_cases += 1
            _append_debug(
                debug_steps,
                origin,
                target,
                profile,
                depth,
                accumulated,
                newly_failed,
                base_path,
                current_path,
                candidate_path,
                base_cost,
                candidate_cost,
                cost_limit,
                False,
                "over_tolerance",
                stats,
            )
            continue
        signature = route_signature(test_graph, candidate_path, distinctness_policy)
        duplicate = _route_duplicate(signature, stats.accepted_route_signatures, max_overlap, distinctness_policy)
        stats.accepted_cases += 1
        if duplicate:
            stats.duplicate_route_cases += 1
            reason = "duplicate_route"
        else:
            stats.accepted_route_signatures.add(signature)
            stats.distinct_routes = len(stats.accepted_route_signatures)
            reason = "within_tolerance"
        _append_debug(
            debug_steps,
            origin,
            target,
            profile,
            depth,
            accumulated,
            newly_failed,
            base_path,
            current_path,
            candidate_path,
            base_cost,
            candidate_cost,
            cost_limit,
            not duplicate,
            reason,
            stats,
        )
        if depth + 1 < len(profile):
            _explore_failure_profile(
                test_graph,
                origin,
                target,
                profile,
                depth=depth + 1,
                current_path=candidate_path,
                failed_units=list(accumulated),
                base_path=base_path,
                base_cost=base_cost,
                cost_limit=cost_limit,
                failure_unit=failure_unit,
                distinctness_policy=distinctness_policy,
                max_overlap=max_overlap,
                max_combinations=max_combinations,
                deadline=deadline,
                weight=weight,
                stats=stats,
                seen_failures=seen_failures,
                debug_steps=debug_steps,
            )


def failure_units_for_path(graph: nx.Graph, path: list[str], failure_unit: str, weight: str = "weight") -> list[FailureUnit]:
    units: list[FailureUnit] = []
    seen: set[FailureUnit] = set()
    for source, target in path_edges(path):
        edge = _selected_edge_data(graph, source, target, weight)
        if edge is None:
            continue
        if failure_unit == "arc":
            unit = ("arc", f"{source}->{target}|{edge.get('arcId') or edge.get('resourceRef') or ''}")
        elif failure_unit == "undirected_pair":
            left, right = sorted((source, target))
            unit = ("undirected_pair", f"{left}|{right}")
        elif failure_unit == "cell":
            unit = ("cell", target)
        else:
            unit = ("resource", str(edge.get("resourceRef") or edge.get("arcId") or f"{source}->{target}"))
        if unit not in seen:
            seen.add(unit)
            units.append(unit)
    return units


def remove_failure_units(graph: nx.Graph, units: Iterable[FailureUnit]) -> None:
    for kind, value in units:
        if kind == "resource":
            _remove_resource(graph, value)
        elif kind == "arc":
            source, target, arc_id = _parse_arc_value(value)
            _remove_arc(graph, source, target, arc_id)
        elif kind == "undirected_pair":
            left, right = value.split("|", 1)
            if graph.has_edge(left, right):
                graph.remove_edge(left, right)
            if graph.has_edge(right, left):
                graph.remove_edge(right, left)
        elif kind == "cell" and graph.has_node(value):
            graph.remove_node(value)


def route_signature(graph: nx.Graph, path: list[str], distinctness_policy: str = "exact") -> tuple[str, ...]:
    if distinctness_policy == "overlap":
        signature = []
        for source, target in path_edges(path):
            edge = _selected_edge_data(graph, source, target, "weight") or {}
            signature.append(str(edge.get("resourceRef") or edge.get("arcId") or f"{source}->{target}"))
        return tuple(signature)
    return tuple(path)


def _route_duplicate(
    signature: tuple[str, ...],
    accepted: set[tuple[str, ...]],
    max_overlap: float,
    distinctness_policy: str,
) -> bool:
    if distinctness_policy != "overlap":
        return signature in accepted
    current = set(signature)
    if not current:
        return True
    for existing_signature in accepted:
        existing = set(existing_signature)
        union = current | existing
        overlap = len(current & existing) / len(union) if union else 1.0
        if overlap > max_overlap:
            return True
    return False


def _selected_edge_data(graph: nx.Graph, source: str, target: str, weight: str) -> dict[str, Any] | None:
    data = graph.get_edge_data(source, target)
    if data is None:
        return None
    if weight in data:
        return data
    weighted_edges = [value for value in data.values() if isinstance(value, dict)]
    if weighted_edges:
        return min(weighted_edges, key=lambda item: float(item.get(weight, 1.0)))
    return data if isinstance(data, dict) else None


def _remove_resource(graph: nx.Graph, resource_ref: str) -> None:
    if isinstance(graph, (nx.MultiDiGraph, nx.MultiGraph)):
        for source, target, key, data in list(graph.edges(keys=True, data=True)):
            if str(data.get("resourceRef") or data.get("arcId") or "") == resource_ref and graph.has_edge(source, target, key):
                graph.remove_edge(source, target, key)
        return
    for source, target, data in list(graph.edges(data=True)):
        if str(data.get("resourceRef") or data.get("arcId") or "") == resource_ref and graph.has_edge(source, target):
            graph.remove_edge(source, target)


def _remove_arc(graph: nx.Graph, source: str, target: str, arc_id: str) -> None:
    if not graph.has_edge(source, target):
        return
    if isinstance(graph, (nx.MultiDiGraph, nx.MultiGraph)):
        for key, data in list((graph.get_edge_data(source, target) or {}).items()):
            if str(data.get("arcId") or key) == arc_id:
                graph.remove_edge(source, target, key)
        return
    data = graph.get_edge_data(source, target) or {}
    if not arc_id or str(data.get("arcId") or data.get("resourceRef") or "") == arc_id:
        graph.remove_edge(source, target)


def _parse_arc_value(value: str) -> tuple[str, str, str]:
    edge, _, arc_id = value.partition("|")
    source, _, target = edge.partition("->")
    return source, target, arc_id


def _canonical_failed_units(units: Iterable[FailureUnit]) -> tuple[FailureUnit, ...]:
    return tuple(sorted(set(units), key=lambda item: (item[0], item[1])))


def _append_debug(
    debug_steps: list[CERDebugStep] | None,
    origin: str,
    target: str,
    profile: tuple[int, ...],
    depth: int,
    failed_units: Iterable[FailureUnit],
    newly_failed_units: Iterable[FailureUnit],
    base_path: list[str],
    failure_source_path: list[str],
    candidate_path: list[str],
    base_cost: float,
    candidate_cost: float | None,
    cost_limit: float,
    accepted: bool,
    reason: str,
    stats: CERProfileStats,
) -> None:
    if debug_steps is None:
        return
    debug_steps.append(
        CERDebugStep(
            origin=origin,
            target=target,
            failure_profile=profile,
            failure_depth=depth + 1,
            failed_units=list(failed_units),
            newly_failed_units=list(newly_failed_units),
            base_path=list(base_path),
            failure_source_path=list(failure_source_path),
            candidate_path=list(candidate_path),
            base_cost=base_cost,
            candidate_cost=candidate_cost,
            cost_limit=cost_limit,
            accepted=accepted,
            reason=reason,
            distinct_route_count=stats.distinct_routes,
            evaluated_failure_cases=stats.evaluated_failure_cases,
        )
    )


def _origin_summary(origin_payload: dict[str, Any]) -> dict[str, Any]:
    total = 0
    best_target = None
    best_profile = None
    best_value = -1
    for target, target_payload in origin_payload.get("targets", {}).items():
        if target_payload.get("skippedSelf") or target_payload.get("unreachable"):
            continue
        for label, stats in (target_payload.get("profiles") or {}).items():
            value = int(stats.distinct_routes if isinstance(stats, CERProfileStats) else stats.get("distinctRoutes", 0))
            total += value
            if value > best_value:
                best_value = value
                best_target = target
                best_profile = label
    return {
        "sumDistinctRoutes": total,
        "bestTarget": best_target,
        "bestProfile": best_profile,
        "nodeScore": total,
    }

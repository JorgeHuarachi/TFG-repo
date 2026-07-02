"""Auditable CER tree computation on weighted EvacEngine snapshots.

This module is intentionally separate from ``rerouting_centrality.py``.  It is
an audit/calibration tool: it explores a bounded failure tree, reports where
the combinatorics stop, and preserves metrics by origin, target and failure
profile before the result is used by any route recommendation policy.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from itertools import combinations, islice
import csv
import json
import math
from pathlib import Path
import time
from typing import Any, Iterable

import networkx as nx

from .domain import IndoorModelBundle, MobilityProfile, ScenarioDefinition
from .overlays import BeaconSimulator, BeaconState, HazardScheduler, HazardState
from .routing import RoutingEngine
from .topology import EvacTopology
from .cer_tree_visualization import save_cer_tree_debug_html


FailureUnit = tuple[str, str]


@dataclass(slots=True)
class CERTreeConfig:
    tau: float = 0.3
    max_depth: int = 2
    max_k: int = 2
    max_total_failures: int = 4
    max_combinations: int = 1000
    max_runtime_ms: int = 1000
    max_distinct_routes: int | None = None
    failure_profiles: tuple[tuple[int, ...], ...] | None = None
    failure_unit: str = "resource"
    weight: str = "weight"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tau": self.tau,
            "maxDepth": self.max_depth,
            "maxK": self.max_k,
            "maxTotalFailures": self.max_total_failures,
            "maxCombinations": self.max_combinations,
            "maxRuntimeMs": self.max_runtime_ms,
            "maxDistinctRoutes": self.max_distinct_routes,
            "failureProfiles": [list(profile) for profile in self.failure_profiles] if self.failure_profiles else None,
            "failureUnit": self.failure_unit,
            "weight": self.weight,
        }


@dataclass(slots=True)
class CERTreeProfileStats:
    failure_profile: tuple[int, ...]
    distinct_route_signatures: set[tuple[str, ...]] = field(default_factory=set)
    total_cases: int = 0
    accepted_cases: int = 0
    no_path_cases: int = 0
    over_tolerance_cases: int = 0
    duplicate_route_cases: int = 0
    visited_state_cases: int = 0
    combinations_truncated_cases: int = 0
    max_depth_reached: int = 0
    max_total_failures_reached: int = 0
    max_distinct_routes_reached: bool = False
    truncated_by_runtime: bool = False
    truncated_by_combinations: bool = False
    runtime_ms: float = 0.0

    @property
    def distinct_routes(self) -> int:
        return len(self.distinct_route_signatures)

    @property
    def coverage(self) -> float:
        return self.accepted_cases / self.total_cases if self.total_cases else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "failureProfile": profile_label(self.failure_profile),
            "failureProfileRaw": list(self.failure_profile),
            "distinctRoutes": self.distinct_routes,
            "acceptedCases": self.accepted_cases,
            "totalCases": self.total_cases,
            "coverage": round(self.coverage, 6),
            "noPathCases": self.no_path_cases,
            "overToleranceCases": self.over_tolerance_cases,
            "duplicateRouteCases": self.duplicate_route_cases,
            "visitedStateCases": self.visited_state_cases,
            "combinationsTruncatedCases": self.combinations_truncated_cases,
            "maxDepthReached": self.max_depth_reached,
            "maxTotalFailuresReached": self.max_total_failures_reached,
            "maxDistinctRoutesReached": self.max_distinct_routes_reached,
            "truncatedByRuntime": self.truncated_by_runtime,
            "truncatedByCombinations": self.truncated_by_combinations,
            "runtimeMs": round(self.runtime_ms, 6),
            "distinctRouteSignatures": [list(path) for path in sorted(self.distinct_route_signatures)],
        }


@dataclass(slots=True)
class _TreeState:
    origin: str
    target: str
    path: list[str]
    path_cost: float
    failed_units: frozenset[FailureUnit]
    failure_profile: tuple[int, ...]
    depth: int
    parent_branch_id: str
    route_history: list[list[str]]


@dataclass(slots=True)
class _CachedEvaluation:
    path: list[str]
    path_cost: float | None
    branch_live: bool
    decision: str


def compute_cer_tree(
    graph: nx.Graph,
    targets: Iterable[str],
    *,
    origins: Iterable[str] | None = None,
    config: CERTreeConfig | None = None,
    graph_view: str | None = None,
) -> dict[str, Any]:
    config = config or CERTreeConfig()
    config.failure_profiles = normalize_failure_profiles(config.failure_profiles)
    started = time.perf_counter()
    deadline = started + max(1, int(config.max_runtime_ms)) / 1000.0
    target_list = [str(target) for target in targets if str(target) in graph]
    origin_list = [str(origin) for origin in origins] if origins is not None else [str(node) for node in graph.nodes]
    payload: dict[str, Any] = {
        "metadata": {
            "metric": "cer_tree",
            "graphView": graph_view,
            "config": config.to_dict(),
            "graph": {"nodes": graph.number_of_nodes(), "arcs": graph.number_of_edges()},
            "truncatedByRuntime": False,
            "startedPairs": 0,
            "completedPairs": 0,
        },
        "nodes": {},
        "debugSteps": [],
    }
    visited_states: dict[tuple[str, str, frozenset[FailureUnit]], _CachedEvaluation] = {}

    for origin in origin_list:
        origin_payload = payload["nodes"].setdefault(str(origin), {"targets": {}, "summary": {}})
        for target in target_list:
            if time.perf_counter() >= deadline:
                payload["metadata"]["truncatedByRuntime"] = True
                break
            target_payload = _compute_pair_tree(
                graph,
                str(origin),
                str(target),
                config,
                started,
                deadline,
                visited_states,
                payload["debugSteps"],
            )
            origin_payload["targets"][str(target)] = target_payload
            if target_payload.get("truncatedByRuntime"):
                payload["metadata"]["truncatedByRuntime"] = True
            payload["metadata"]["startedPairs"] += 1
            if not target_payload.get("truncatedByRuntime"):
                payload["metadata"]["completedPairs"] += 1
        origin_payload["summary"] = _origin_summary(origin_payload)
    payload["metadata"]["runtimeMs"] = round((time.perf_counter() - started) * 1000.0, 6)
    payload["metadata"]["debugStepCount"] = len(payload["debugSteps"])
    return payload


def export_cer_tree_for_scenario(
    indoor: IndoorModelBundle,
    scenario: ScenarioDefinition,
    *,
    profile_ids: Iterable[str] | None,
    origins: Iterable[str] | None,
    targets: Iterable[str] | None,
    output_dir: str | Path,
    formats: Iterable[str] = ("json", "csv", "html"),
    config: CERTreeConfig | None = None,
    structural: bool = True,
    step: int = 0,
    time_s: float = 0.0,
    visual_level: str | None = None,
    visual_order: str = "tree",
    visual_layout: str = "wide",
) -> dict[str, Any]:
    topology = EvacTopology.from_indoor_model(indoor)
    engine = RoutingEngine(topology)
    config = config or CERTreeConfig()
    profile_list = _resolve_profiles(scenario, profile_ids)
    target_ids = _resolve_targets(indoor, topology, scenario, targets)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    requested = {str(item).lower() for item in formats}
    runs: dict[str, Any] = {}
    paths: dict[str, str] = {}

    for profile in profile_list:
        routing_config = dict(scenario.physics)
        routing_config.update(scenario.routing)
        if structural:
            routing_config.update({"useHazardRisk": False, "useBeaconRisk": False, "useCongestion": False})
            hazard_state = HazardState()
            beacon_state = BeaconState()
        else:
            hazard_state = HazardScheduler(topology, scenario.hazards).state_at(step, time_s)
            beacon_state = BeaconSimulator(topology, scenario.beacons, (scenario.raw.get("beaconSystem") or {}).get("fusion")).state_at(step, time_s)
        cost_policy = str(routing_config.get("costPolicy", "minimum_travel_time"))
        snapshot = engine.compiler.compile(
            step=step,
            time_s=time_s,
            mobility_profile=profile,
            cost_policy=cost_policy,
            hazard_state=hazard_state,
            beacon_state=beacon_state,
            routing_config=routing_config,
        )
        origin_ids = _resolve_origins(indoor, snapshot.graph, origins)
        payload = compute_cer_tree(
            snapshot.graph,
            target_ids,
            origins=origin_ids,
            config=config,
            graph_view=topology.graph_view_name,
        )
        payload["metadata"].update(
            {
                "scenarioId": scenario.scenario_id,
                "profileId": profile.id,
                "snapshot": "structural" if structural else "dynamic",
                "step": step,
                "timeS": time_s,
                "targets": target_ids,
                "originCount": len(origin_ids),
            }
        )
        runs[profile.id] = payload
        prefix = _slug(profile.id)
        if "json" in requested:
            path = output / f"cer_tree_{prefix}.json"
            path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            paths[f"{profile.id}:json"] = str(path)
        if "csv" in requested:
            path = output / f"cer_tree_summary_{prefix}.csv"
            _write_summary_csv(payload, path)
            paths[f"{profile.id}:csv"] = str(path)
        if "html" in requested:
            path = output / f"cer_tree_{prefix}.html"
            path.write_text(_html_summary(payload), encoding="utf-8")
            paths[f"{profile.id}:html"] = str(path)
        if "visual-html" in requested or "visual" in requested:
            path = output / f"cer_tree_{prefix}_visual.html"
            save_cer_tree_debug_html(
                topology,
                payload,
                path,
                level=visual_level,
                visual_order=visual_order,
                visual_layout=visual_layout,
            )
            paths[f"{profile.id}:visual-html"] = str(path)
    manifest = {
        "scenarioId": scenario.scenario_id,
        "profiles": [profile.id for profile in profile_list],
        "targets": target_ids,
        "outputDir": str(output),
        "outputs": paths,
        "config": config.to_dict(),
    }
    manifest_path = output / "cer_tree_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    paths["manifest"] = str(manifest_path)
    return {**manifest, "outputs": paths, "runs": runs}


def default_cer_tree_output_dir(scenario_path: str | Path, indoor_path: str | Path) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    scenario = Path(scenario_path).resolve()
    indoor = Path(indoor_path).resolve()
    try:
        relative = indoor.relative_to((project_root / "models").resolve())
        model_name = relative.parts[0]
        return project_root / "models" / model_name / "outputs" / "cer_tree" / _slug(scenario.stem)
    except ValueError:
        return project_root / "outputs" / "cer_tree" / _slug(scenario.stem)


def profile_label(profile: Iterable[int]) -> str:
    return "(" + ",".join(str(int(item)) for item in profile) + ")"


def normalize_failure_profiles(profiles: Iterable[Iterable[int]] | None) -> tuple[tuple[int, ...], ...] | None:
    if profiles is None:
        return None
    normalized: set[tuple[int, ...]] = set()
    for raw_profile in profiles:
        profile = tuple(int(item) for item in raw_profile if int(item) > 0)
        if profile:
            normalized.add(profile)
    return tuple(sorted(normalized, key=lambda item: (len(item), item))) or None


def _profile_prefixes(profiles: tuple[tuple[int, ...], ...] | None) -> set[tuple[int, ...]] | None:
    if profiles is None:
        return None
    prefixes: set[tuple[int, ...]] = set()
    for profile in profiles:
        for index in range(1, len(profile) + 1):
            prefixes.add(profile[:index])
    return prefixes


def path_cost(graph: nx.Graph, path: Iterable[str], weight: str = "weight") -> float:
    nodes = [str(node) for node in path]
    total = 0.0
    for source, target in zip(nodes, nodes[1:]):
        data = _selected_edge_data(graph, source, target, weight)
        if data is None:
            return math.inf
        total += float(data.get(weight, 1.0))
    return total


def path_to_failure_units(graph: nx.Graph, path: Iterable[str], failure_unit: str, weight: str = "weight") -> list[FailureUnit]:
    units: list[FailureUnit] = []
    seen: set[FailureUnit] = set()
    failure_unit = _normal_failure_unit(failure_unit)
    nodes = [str(node) for node in path]
    for source, target in zip(nodes, nodes[1:]):
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


def _compute_pair_tree(
    graph: nx.Graph,
    origin: str,
    target: str,
    config: CERTreeConfig,
    started: float,
    deadline: float,
    visited_states: dict[tuple[str, str, frozenset[FailureUnit]], _CachedEvaluation],
    debug_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    if origin == target:
        return {"skippedSelf": True, "failureProfiles": {}, "summary": {}}
    if origin not in graph or target not in graph:
        return {"unreachable": True, "failureProfiles": {}, "summary": {"reason": "missing_origin_or_target"}}
    try:
        base_path = [str(node) for node in nx.shortest_path(graph, origin, target, weight=config.weight)]
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {"unreachable": True, "failureProfiles": {}, "summary": {"reason": "no_base_path"}}
    base_cost = path_cost(graph, base_path, config.weight)
    if not math.isfinite(base_cost):
        return {"unreachable": True, "failureProfiles": {}, "summary": {"reason": "invalid_base_cost"}}
    cost_limit = base_cost * (1.0 + max(0.0, float(config.tau)))
    stats: dict[tuple[int, ...], CERTreeProfileStats] = {}
    queue: deque[_TreeState] = deque(
        [
            _TreeState(
                origin=origin,
                target=target,
                path=base_path,
                path_cost=base_cost,
                failed_units=frozenset(),
                failure_profile=(),
                depth=0,
                parent_branch_id="root",
                route_history=[base_path],
            )
        ]
    )
    pair_limit_hits = Counter()
    pair_truncated_runtime = False
    allowed_profile_prefixes = _profile_prefixes(config.failure_profiles)

    while queue:
        if time.perf_counter() >= deadline:
            pair_truncated_runtime = True
            break
        state = queue.popleft()
        if state.depth >= config.max_depth:
            pair_limit_hits["maxDepth"] += 1
            continue
        current_failures = len(state.failed_units)
        if current_failures >= config.max_total_failures:
            pair_limit_hits["maxTotalFailures"] += 1
            continue
        max_k = min(config.max_k, config.max_total_failures - current_failures)
        units = [unit for unit in path_to_failure_units(graph, state.path, config.failure_unit, config.weight) if unit not in state.failed_units]
        if not units:
            pair_limit_hits["noAvailableFailures"] += 1
            continue
        for k in range(1, max_k + 1):
            possible_count = math.comb(len(units), k) if len(units) >= k else 0
            if possible_count <= 0:
                continue
            combos = list(islice(combinations(units, k), max(1, int(config.max_combinations))))
            truncated_combos = possible_count > len(combos)
            if truncated_combos:
                pair_limit_hits["maxCombinations"] += 1
            for index, combo in enumerate(combos, start=1):
                if time.perf_counter() >= deadline:
                    pair_truncated_runtime = True
                    break
                profile = (*state.failure_profile, k)
                if allowed_profile_prefixes is not None and profile not in allowed_profile_prefixes:
                    pair_limit_hits["filteredProfiles"] += 1
                    continue
                profile_stats = stats.setdefault(profile, CERTreeProfileStats(profile))
                if truncated_combos:
                    profile_stats.truncated_by_combinations = True
                    profile_stats.combinations_truncated_cases += 1
                step_started = time.perf_counter()
                new_failed = frozenset((*state.failed_units, *combo))
                state_key = (origin, target, new_failed)
                profile_stats.total_cases += 1
                profile_stats.max_depth_reached = max(profile_stats.max_depth_reached, len(profile))
                profile_stats.max_total_failures_reached = max(profile_stats.max_total_failures_reached, len(new_failed))
                cached = visited_states.get(state_key)
                if cached is not None:
                    profile_stats.visited_state_cases += 1
                    _append_debug_step(
                        debug_steps,
                        origin,
                        target,
                        base_path,
                        base_cost,
                        cost_limit,
                        state,
                        profile,
                        combo,
                        index,
                        possible_count,
                        new_failed,
                        cached.path,
                        cached.path_cost,
                        "visited_state",
                        profile_stats,
                        started,
                        step_started,
                        branch_status="dead",
                        branch_death_reason="visited_state",
                        note=f"cached previous decision={cached.decision}",
                    )
                    continue
                test_graph = graph.copy()
                remove_failure_units(test_graph, new_failed)
                try:
                    candidate_path = [str(node) for node in nx.shortest_path(test_graph, origin, target, weight=config.weight)]
                    candidate_cost = path_cost(test_graph, candidate_path, config.weight)
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    candidate_path = []
                    candidate_cost = None
                decision = "accepted"
                branch_live = False
                branch_death_reason = ""
                if candidate_cost is None or not candidate_path or not math.isfinite(candidate_cost):
                    decision = "no_path"
                    branch_death_reason = "no_path"
                    profile_stats.no_path_cases += 1
                elif candidate_cost > cost_limit:
                    decision = "over_tolerance"
                    branch_death_reason = "over_tolerance"
                    profile_stats.over_tolerance_cases += 1
                else:
                    signature = tuple(candidate_path)
                    profile_stats.accepted_cases += 1
                    branch_live = True
                    if signature in profile_stats.distinct_route_signatures or signature == tuple(base_path):
                        decision = "duplicate_route"
                        profile_stats.duplicate_route_cases += 1
                    else:
                        profile_stats.distinct_route_signatures.add(signature)
                    if config.max_distinct_routes is not None and profile_stats.distinct_routes >= config.max_distinct_routes:
                        profile_stats.max_distinct_routes_reached = True
                        branch_live = False
                        branch_death_reason = "max_distinct_routes"
                        pair_limit_hits["maxDistinctRoutes"] += 1
                    elif len(profile) >= config.max_depth:
                        branch_live = False
                        branch_death_reason = "max_depth"
                    elif len(new_failed) >= config.max_total_failures:
                        branch_live = False
                        branch_death_reason = "max_total_failures"
                visited_states[state_key] = _CachedEvaluation(candidate_path, candidate_cost, branch_live, decision)
                branch_status = "live" if branch_live else "dead"
                if branch_death_reason in {"max_depth", "max_total_failures"}:
                    branch_status = "terminal"
                _append_debug_step(
                    debug_steps,
                    origin,
                    target,
                    base_path,
                    base_cost,
                    cost_limit,
                    state,
                    profile,
                    combo,
                    index,
                    possible_count,
                    new_failed,
                    candidate_path,
                    candidate_cost,
                    decision,
                    profile_stats,
                    started,
                    step_started,
                    branch_status=branch_status,
                    branch_death_reason=branch_death_reason,
                )
                if branch_live:
                    queue.append(
                        _TreeState(
                            origin=origin,
                            target=target,
                            path=candidate_path,
                            path_cost=float(candidate_cost or 0.0),
                            failed_units=new_failed,
                            failure_profile=profile,
                            depth=state.depth + 1,
                            parent_branch_id=_branch_id(profile, new_failed),
                            route_history=[*state.route_history, candidate_path],
                        )
                    )
            if pair_truncated_runtime:
                break
        if pair_truncated_runtime:
            break

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    for profile_stats in stats.values():
        profile_stats.runtime_ms = elapsed_ms
        if pair_truncated_runtime:
            profile_stats.truncated_by_runtime = True
    failure_profiles = {profile_label(profile): item.to_dict() for profile, item in sorted(stats.items(), key=lambda pair: pair[0])}
    summary = _target_summary(failure_profiles)
    summary.update(
        {
            "basePath": base_path,
            "baseCost": round(base_cost, 6),
            "Cmax": round(cost_limit, 6),
            "limitHits": dict(pair_limit_hits),
        }
    )
    return {
        "basePath": base_path,
        "baseCost": round(base_cost, 6),
        "Cmax": round(cost_limit, 6),
        "truncatedByRuntime": pair_truncated_runtime,
        "failureProfiles": failure_profiles,
        "summary": summary,
    }


def _append_debug_step(
    debug_steps: list[dict[str, Any]],
    origin: str,
    target: str,
    base_path: list[str],
    base_cost: float,
    cost_limit: float,
    state: _TreeState,
    profile: tuple[int, ...],
    combo: Iterable[FailureUnit],
    combination_index: int,
    combination_count: int,
    failed_units: frozenset[FailureUnit],
    candidate_path: list[str],
    candidate_cost: float | None,
    decision: str,
    stats: CERTreeProfileStats,
    started: float,
    step_started: float,
    *,
    branch_status: str,
    branch_death_reason: str,
    note: str = "",
) -> None:
    debug_steps.append(
        {
            "origin": origin,
            "target": target,
            "basePath": list(base_path),
            "baseCost": round(base_cost, 6),
            "Cmax": round(cost_limit, 6),
            "failureProfile": profile_label(profile),
            "failureProfileRaw": list(profile),
            "depth": len(profile),
            "sourcePath": list(state.path),
            "sourceCost": round(state.path_cost, 6),
            "removedCombination": _units_to_dicts(combo),
            "combinationIndex": combination_index,
            "combinationCount": combination_count,
            "failedUnits": _units_to_dicts(sorted(failed_units)),
            "recalculatedPath": list(candidate_path),
            "recalculatedCost": round(candidate_cost, 6) if candidate_cost is not None else None,
            "decision": decision,
            "distinctRoutes": stats.distinct_routes,
            "acceptedCases": stats.accepted_cases,
            "totalCases": stats.total_cases,
            "coverage": round(stats.coverage, 6),
            "stepMs": round((time.perf_counter() - step_started) * 1000.0, 6),
            "totalMs": round((time.perf_counter() - started) * 1000.0, 6),
            "branchId": _branch_id(profile, failed_units),
            "parentBranchId": state.parent_branch_id,
            "branchStatus": branch_status,
            "branchDeathReason": branch_death_reason,
            "note": note,
            "routeHistory": [list(path) for path in state.route_history] + ([list(candidate_path)] if candidate_path else []),
        }
    )


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


def _normal_failure_unit(value: str) -> str:
    if value == "undirected_connection":
        return "undirected_pair"
    if value in {"resource", "arc", "undirected_pair", "cell"}:
        return value
    return "resource"


def _units_to_dicts(units: Iterable[FailureUnit]) -> list[dict[str, str]]:
    return [{"kind": kind, "value": value} for kind, value in units]


def _branch_id(profile: Iterable[int], failed_units: Iterable[FailureUnit]) -> str:
    units = "_".join(f"{kind}:{value}" for kind, value in sorted(failed_units))
    return f"{profile_label(profile)}|{units}" if units else "root"


def _target_summary(failure_profiles: dict[str, Any]) -> dict[str, Any]:
    distinct = sum(int(profile.get("distinctRoutes") or 0) for profile in failure_profiles.values())
    accepted = sum(int(profile.get("acceptedCases") or 0) for profile in failure_profiles.values())
    total = sum(int(profile.get("totalCases") or 0) for profile in failure_profiles.values())
    coverage = accepted / total if total else 0.0
    return {
        "distinctRoutes": distinct,
        "acceptedCases": accepted,
        "totalCases": total,
        "coverage": round(coverage, 6),
    }


def _origin_summary(origin_payload: dict[str, Any]) -> dict[str, Any]:
    best_distinct = None
    best_coverage = None
    best_distinct_value = -1
    best_coverage_value = -1.0
    for target, target_payload in (origin_payload.get("targets") or {}).items():
        summary = target_payload.get("summary") or {}
        distinct = int(summary.get("distinctRoutes") or 0)
        coverage = float(summary.get("coverage") or 0.0)
        if distinct > best_distinct_value:
            best_distinct = target
            best_distinct_value = distinct
        if coverage > best_coverage_value:
            best_coverage = target
            best_coverage_value = coverage
    return {
        "bestTargetByDistinctRoutes": best_distinct,
        "bestTargetByCoverage": best_coverage,
        "sumDistinctRoutes": max(best_distinct_value, 0),
    }


def _resolve_profiles(scenario: ScenarioDefinition, profile_ids: Iterable[str] | None) -> list[MobilityProfile]:
    if profile_ids:
        profiles = [scenario.mobility_profiles[item] for item in profile_ids if item in scenario.mobility_profiles]
        if profiles:
            return profiles
    return list(scenario.mobility_profiles.values())


def _resolve_targets(indoor: IndoorModelBundle, topology: EvacTopology, scenario: ScenarioDefinition, targets: Iterable[str] | None) -> list[str]:
    raw_targets = list(targets or [])
    if not raw_targets:
        raw_targets = list(((scenario.routing.get("destination") or {}).get("cellSpaceRefs") or []))
    if not raw_targets:
        raw_targets = topology.exit_candidates()
    resolved: list[str] = []
    for target in raw_targets:
        target_id = indoor.resolve_cell_ref(target) or str(target)
        if target_id not in resolved:
            resolved.append(target_id)
    return resolved


def _resolve_origins(indoor: IndoorModelBundle, graph: nx.Graph, origins: Iterable[str] | None) -> list[str]:
    if origins is None:
        return [str(node) for node in graph.nodes]
    resolved: list[str] = []
    for origin in origins:
        origin_id = indoor.resolve_cell_ref(origin) or str(origin)
        if origin_id in graph and origin_id not in resolved:
            resolved.append(origin_id)
    return resolved


def _write_summary_csv(payload: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "origin",
                "target",
                "failureProfile",
                "distinctRoutes",
                "acceptedCases",
                "totalCases",
                "coverage",
                "noPathCases",
                "overToleranceCases",
                "duplicateRouteCases",
                "visitedStateCases",
                "truncatedByRuntime",
                "truncatedByCombinations",
                "runtimeMs",
            ],
        )
        writer.writeheader()
        for origin, origin_payload in (payload.get("nodes") or {}).items():
            for target, target_payload in (origin_payload.get("targets") or {}).items():
                for label, stats in (target_payload.get("failureProfiles") or {}).items():
                    writer.writerow(
                        {
                            "origin": origin,
                            "target": target,
                            "failureProfile": label,
                            "distinctRoutes": stats.get("distinctRoutes"),
                            "acceptedCases": stats.get("acceptedCases"),
                            "totalCases": stats.get("totalCases"),
                            "coverage": stats.get("coverage"),
                            "noPathCases": stats.get("noPathCases"),
                            "overToleranceCases": stats.get("overToleranceCases"),
                            "duplicateRouteCases": stats.get("duplicateRouteCases"),
                            "visitedStateCases": stats.get("visitedStateCases"),
                            "truncatedByRuntime": stats.get("truncatedByRuntime"),
                            "truncatedByCombinations": stats.get("truncatedByCombinations"),
                            "runtimeMs": stats.get("runtimeMs"),
                        }
                    )
    return output


def _html_summary(payload: dict[str, Any]) -> str:
    rows = []
    for origin, origin_payload in (payload.get("nodes") or {}).items():
        for target, target_payload in (origin_payload.get("targets") or {}).items():
            for label, stats in (target_payload.get("failureProfiles") or {}).items():
                rows.append(
                    "<tr>"
                    f"<td>{origin}</td><td>{target}</td><td>{label}</td>"
                    f"<td>{stats.get('distinctRoutes')}</td><td>{stats.get('acceptedCases')}</td><td>{stats.get('totalCases')}</td>"
                    f"<td>{stats.get('coverage')}</td><td>{stats.get('truncatedByRuntime')}</td><td>{stats.get('truncatedByCombinations')}</td>"
                    "</tr>"
                )
    debug = payload.get("debugSteps") or []
    debug_rows = []
    for step in debug[:500]:
        debug_rows.append(
            "<tr>"
            f"<td>{step.get('origin')}</td><td>{step.get('target')}</td><td>{step.get('failureProfile')}</td>"
            f"<td>{step.get('depth')}</td><td>{step.get('decision')}</td><td>{step.get('recalculatedCost')}</td>"
            f"<td>{step.get('distinctRoutes')}</td><td>{step.get('acceptedCases')}</td><td>{step.get('totalCases')}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>CER tree audit</title>
<style>
body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 18px; color:#111827; background:#f8fafc; }}
table {{ border-collapse: collapse; width: 100%; background:#fff; margin: 12px 0 24px; }}
th, td {{ border:1px solid #d7dee8; padding:6px 8px; font-size:12px; text-align:left; }}
th {{ background:#e2e8f0; }}
code, pre {{ background:#eef2f7; padding:8px; border-radius:6px; }}
</style></head><body>
<h1>CER tree audit</h1>
<pre>{json.dumps(payload.get("metadata") or {{}}, ensure_ascii=True, indent=2)}</pre>
<h2>Resumen por perfil</h2>
<table><thead><tr><th>origin</th><th>target</th><th>profile</th><th>distinctRoutes</th><th>acceptedCases</th><th>totalCases</th><th>coverage</th><th>runtime</th><th>comb.</th></tr></thead><tbody>
{''.join(rows)}
</tbody></table>
<h2>Debug steps first 500</h2>
<table><thead><tr><th>origin</th><th>target</th><th>profile</th><th>depth</th><th>decision</th><th>cost</th><th>distinct</th><th>accepted</th><th>total</th></tr></thead><tbody>
{''.join(debug_rows)}
</tbody></table>
</body></html>"""


def _slug(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    return re.sub(r"_+", "_", cleaned).strip("._-") or "item"

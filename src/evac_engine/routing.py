"""Route planning and immutable weight snapshot compilation."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

import networkx as nx
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from .domain import Diagnostic, MobilityProfile, Route, WeightedSnapshot
from .overlays import BeaconState, HazardState
from .route_recommendation import (
    RouteRecommendationConfig,
    EvacuationRouteRecommendationService,
    SUPPORTED_ROUTE_ALGORITHMS,
)
from .topology import EvacTopology


class WeightSnapshotCompiler:
    """Builds a fresh weighted graph from immutable base topology every tick."""

    def __init__(self, topology: EvacTopology) -> None:
        self.topology = topology
        self._mobility_edge_cache: dict[tuple[Any, ...], list[tuple[str, str, str, dict[str, Any]]]] = {}

    def compile(
        self,
        step: int = 0,
        time_s: float = 0.0,
        mobility_profile: MobilityProfile | None = None,
        cost_policy: str = "minimum_travel_time",
        hazard_state: HazardState | None = None,
        beacon_state: BeaconState | None = None,
        congestion: dict[str, int] | None = None,
        routing_config: dict[str, Any] | None = None,
    ) -> WeightedSnapshot:
        hazard_state = hazard_state or HazardState()
        beacon_state = beacon_state or BeaconState()
        congestion = congestion or {}
        routing_config = routing_config or {}
        blocked_cells = set(hazard_state.blocked_cells)
        if bool(routing_config.get("useBeaconRisk", True)):
            threshold = routing_config.get("beaconBlockThreshold")
            if threshold is not None:
                try:
                    block_threshold = float(threshold)
                except (TypeError, ValueError):
                    block_threshold = 1.1
                if 0.0 <= block_threshold <= 1.0:
                    blocked_cells.update(cell_id for cell_id, risk in beacon_state.cell_risk.items() if float(risk) >= block_threshold)
        graph = nx.DiGraph()
        edge_weights: dict[str, dict[str, Any]] = {}
        for node_id, data in self.topology.graph.nodes(data=True):
            if node_id not in blocked_cells:
                graph.add_node(node_id, **data)

        for source, target, key, data in self._mobility_edges(mobility_profile):
            if source not in graph or target not in graph:
                continue
            resource_ref = str(data.get("resourceRef") or key)
            if resource_ref in hazard_state.blocked_resources:
                continue
            breakdown = self._weight_breakdown(data, source, target, cost_policy, mobility_profile, hazard_state, beacon_state, congestion, routing_config)
            existing = graph.get_edge_data(source, target)
            if existing is None or breakdown["total"] < existing["weight"]:
                graph.add_edge(source, target, weight=breakdown["total"], arcId=key, resourceRef=resource_ref, breakdown=breakdown, raw=data)
            edge_weights[str(key)] = breakdown
        return WeightedSnapshot(
            step=step,
            time_s=time_s,
            graph=graph,
            edge_weights=edge_weights,
            blocked_cells=blocked_cells,
            active_hazards=list(hazard_state.active_hazards),
        )

    def _mobility_edges(self, mobility_profile: MobilityProfile | None) -> list[tuple[str, str, str, dict[str, Any]]]:
        key = _mobility_cache_key(mobility_profile)
        cached = self._mobility_edge_cache.get(key)
        if cached is not None:
            return cached
        allowed = [
            (source, target, key, data)
            for source, target, key, data in self.topology.graph.edges(keys=True, data=True)
            if _profile_allows(data, mobility_profile)
        ]
        self._mobility_edge_cache[key] = allowed
        return allowed

    @staticmethod
    def _weight_breakdown(
        edge_data: dict[str, Any],
        source: str,
        target: str,
        cost_policy: str,
        mobility_profile: MobilityProfile | None,
        hazard_state: HazardState,
        beacon_state: BeaconState,
        congestion: dict[str, int],
        routing_config: dict[str, Any],
    ) -> dict[str, Any]:
        length_m = _non_negative_float(edge_data.get("lengthM"), 1.0)
        base, movement_overhead = _profile_traversal_time(edge_data, source, target, mobility_profile, routing_config)
        resource_ref = str(edge_data.get("resourceRef") or "")
        endpoint_policy = str(routing_config.get("riskEndpointPolicy", "target"))
        edge_precedence = bool(routing_config.get("riskEdgePrecedence", True))
        hazard = _risk_for_edge(hazard_state.edge_risk, hazard_state.cell_risk, resource_ref, source, target, endpoint_policy, edge_precedence)
        beacon = _risk_for_edge(beacon_state.edge_risk, beacon_state.cell_risk, resource_ref, source, target, endpoint_policy, edge_precedence)
        crowd = float(congestion.get(target, 0))
        use_hazard = bool(routing_config.get("useHazardRisk", True))
        use_beacon = bool(routing_config.get("useBeaconRisk", True))
        use_congestion = bool(routing_config.get("useCongestion", False))
        hazard = hazard if use_hazard else 0.0
        beacon = beacon if use_beacon else 0.0
        risk_model = str(routing_config.get("riskCostModel", "legacy_additive"))
        alpha = _non_negative_float(routing_config.get("riskAlpha"), 1.0)
        hazard_beta = _non_negative_float(routing_config.get("hazardBeta"), 20.0 if risk_model == "legacy_additive" else 1.0)
        beacon_beta = _non_negative_float(routing_config.get("beaconBeta"), 5.0 if risk_model == "legacy_additive" else 1.0)
        combined_risk = _combine_risk(hazard, beacon, str(routing_config.get("riskAggregation", "sum")))
        if risk_model == "linear_time_risk":
            risk_unit_cost = _non_negative_float(routing_config.get("riskUnitCost"), base)
            risk_penalty = risk_unit_cost * (hazard_beta * hazard + beacon_beta * beacon)
            base_component = alpha * base
            hazard_penalty = risk_unit_cost * hazard_beta * hazard
            beacon_penalty = risk_unit_cost * beacon_beta * beacon
            total_without_congestion = base_component + risk_penalty
        elif risk_model == "multiplicative_beta":
            base_component = alpha * base
            hazard_penalty = base * hazard_beta * hazard
            beacon_penalty = base * beacon_beta * beacon
            total_without_congestion = base_component + hazard_penalty + beacon_penalty
        else:
            base_component = base
            hazard_penalty = base * hazard * hazard_beta
            beacon_penalty = base * beacon * beacon_beta
            total_without_congestion = base_component + hazard_penalty + beacon_penalty
        congestion_penalty = crowd * 0.2 if use_congestion else 0.0
        total = total_without_congestion + congestion_penalty
        return {
            "base": round(base, 6),
            "baseComponent": round(base_component, 6),
            "baseUnit": "s",
            "costPolicy": cost_policy,
            "lengthM": round(length_m, 6),
            "movementOverhead": round(movement_overhead, 6),
            "riskCostModel": risk_model,
            "riskEndpointPolicy": endpoint_policy,
            "hazardRisk": round(hazard, 6),
            "beaconRisk": round(beacon, 6),
            "combinedRisk": round(combined_risk, 6),
            "riskAlpha": round(alpha, 6),
            "hazardBeta": round(hazard_beta, 6),
            "beaconBeta": round(beacon_beta, 6),
            "hazardPenalty": round(hazard_penalty, 6),
            "beaconPenalty": round(beacon_penalty, 6),
            "congestionPenalty": round(congestion_penalty, 6),
            "total": round(total, 6),
        }


class RoutingEngine:
    def __init__(self, topology: EvacTopology) -> None:
        self.topology = topology
        self.compiler = WeightSnapshotCompiler(topology)
        self.recommendations = EvacuationRouteRecommendationService()
        self._rerouting_centrality_cache: dict[tuple[Any, ...], tuple[dict[str, float], dict[str, Any]]] = {}

    def find_route(
        self,
        origin: str,
        target_refs: list[str] | None = None,
        mobility_profile: MobilityProfile | None = None,
        algorithm: str = "dijkstra",
        cost_policy: str = "minimum_travel_time",
        hazard_state: HazardState | None = None,
        beacon_state: BeaconState | None = None,
        congestion: dict[str, int] | None = None,
        routing_config: dict[str, Any] | None = None,
        step: int = 0,
        time_s: float = 0.0,
        origin_position: tuple[float, float] | None = None,
        origin_level: str | None = None,
    ) -> Route:
        origin_id = self.topology.indoor.resolve_cell_ref(origin) or origin
        raw_targets = self._target_refs(target_refs)
        if algorithm not in SUPPORTED_ROUTE_ALGORITHMS:
            destination = raw_targets[0] if raw_targets else ""
            return self._unreachable(origin_id, destination, algorithm, cost_policy, "UNSUPPORTED_ALGORITHM")

        compile_start = time.perf_counter()
        hazard_state = hazard_state or HazardState()
        beacon_state = beacon_state or BeaconState()
        congestion = congestion or {}
        routing_config = routing_config or {}
        snapshot = self.compiler.compile(
            step=step,
            time_s=time_s,
            mobility_profile=mobility_profile,
            cost_policy=cost_policy,
            hazard_state=hazard_state,
            beacon_state=beacon_state,
            congestion=congestion,
            routing_config=routing_config,
        )
        snapshot_compile_ms = (time.perf_counter() - compile_start) * 1000.0
        self._attach_cell_endpoint(
            snapshot.graph,
            origin_id,
            origin_position,
            origin_level,
            mobility_profile,
            cost_policy,
            hazard_state,
            beacon_state,
            congestion,
            routing_config,
            direction="out",
        )
        if origin_position is not None and origin_id in self.topology.graph:
            self._adjust_origin_edges_from_position(
                snapshot.graph,
                origin_id,
                origin_position,
                mobility_profile,
                cost_policy,
                hazard_state,
                beacon_state,
                congestion,
                routing_config,
            )
        for target_id in raw_targets:
            if target_id not in snapshot.graph:
                self._attach_cell_endpoint(
                    snapshot.graph,
                    target_id,
                    None,
                    None,
                    mobility_profile,
                    cost_policy,
                    hazard_state,
                    beacon_state,
                    congestion,
                    routing_config,
                    direction="in",
                )
        targets = [target for target in raw_targets if target in snapshot.graph]
        if origin_id not in snapshot.graph:
            return self._unreachable(origin_id, targets[0] if targets else "", algorithm, cost_policy, "UNKNOWN_ORIGIN")
        if not targets:
            return self._unreachable(origin_id, "", algorithm, cost_policy, "NO_TARGETS")
        planning_start = time.perf_counter()
        recommendation_config = RouteRecommendationConfig.from_routing_config(algorithm, routing_config)
        if recommendation_config.rerouting_enabled or recommendation_config.route_selection in {"cer_weighted", "cer_agility_yen"}:
            scores, metadata = self._rerouting_centrality_scores(
                snapshot,
                targets,
                mobility_profile,
                cost_policy,
                routing_config,
                recommendation_config,
            )
            recommendation_config.rerouting_centrality_by_node = scores
            recommendation_config.rerouting_metadata = metadata
        candidate = self.recommendations.recommend(
            snapshot.graph,
            origin_id,
            targets,
            heuristic=self._time_heuristic(mobility_profile),
            config=recommendation_config,
        )
        planning_ms = (time.perf_counter() - planning_start) * 1000.0
        if candidate:
            route = self._route_from_path(candidate.node_sequence, snapshot, origin_id, candidate.destination, algorithm, cost_policy)
            route.weight_breakdown["snapshotCompileMs"] = round(snapshot_compile_ms, 6)
            route.weight_breakdown["planningMs"] = round(planning_ms, 6)
            route.weight_breakdown["originCandidates"] = self._origin_candidates(snapshot.graph, origin_id, targets)
            if candidate.metrics:
                route.weight_breakdown["routeMetrics"] = dict(candidate.metrics)
            return route
        route = self._unreachable(origin_id, targets[0], algorithm, cost_policy, "NO_ROUTE")
        route.weight_breakdown["snapshotCompileMs"] = round(snapshot_compile_ms, 6)
        route.weight_breakdown["planningMs"] = round(planning_ms, 6)
        route.weight_breakdown["originCandidates"] = self._origin_candidates(snapshot.graph, origin_id, targets)
        return route

    def _rerouting_centrality_scores(
        self,
        snapshot: WeightedSnapshot,
        targets: list[str],
        mobility_profile: MobilityProfile | None,
        cost_policy: str,
        routing_config: dict[str, Any],
        config: RouteRecommendationConfig,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        structural = bool(config.rerouting_use_structural_precompute)
        cache_key = (
            "structural" if structural else "dynamic",
            _mobility_cache_key(mobility_profile),
            cost_policy,
            tuple(sorted(targets)),
            tuple(config.rerouting_failure_profiles),
            config.rerouting_failure_unit,
            config.rerouting_distinctness_policy,
            round(config.rerouting_cost_tolerance, 6),
            config.rerouting_max_combinations,
            config.rerouting_max_runtime_ms,
            snapshot.step if not structural else 0,
        )
        cached = self._rerouting_centrality_cache.get(cache_key)
        if cached is not None:
            return cached
        if structural:
            structural_config = dict(routing_config)
            structural_config.update({"useHazardRisk": False, "useBeaconRisk": False, "useCongestion": False})
            graph = self.compiler.compile(
                mobility_profile=mobility_profile,
                cost_policy=cost_policy,
                routing_config=structural_config,
            ).graph
        else:
            graph = snapshot.graph
        scores, metadata = self.recommendations.compute_rerouting_scores(
            graph,
            targets,
            config,
            graph_view=self.topology.graph_view_name,
        )
        self._rerouting_centrality_cache[cache_key] = (scores, metadata)
        return scores, metadata

    def _target_refs(self, target_refs: list[str] | None) -> list[str]:
        raw_targets = target_refs or self.topology.exit_candidates()
        targets = []
        for target in raw_targets:
            resolved = self.topology.indoor.resolve_cell_ref(target) or target
            if resolved not in targets:
                targets.append(resolved)
        return targets

    def _attach_cell_endpoint(
        self,
        graph: nx.DiGraph,
        cell_id: str,
        position: tuple[float, float] | None,
        level: str | None,
        mobility_profile: MobilityProfile | None,
        cost_policy: str,
        hazard_state: HazardState,
        beacon_state: BeaconState,
        congestion: dict[str, int],
        routing_config: dict[str, Any],
        *,
        direction: str,
    ) -> None:
        if cell_id in graph:
            if position is not None:
                graph.nodes[cell_id]["position"] = position
            return
        cell = self.topology.indoor.cells_by_id.get(cell_id)
        if not cell or not cell.is_navigable:
            return
        point = position or cell.representative_point
        if point is None:
            return
        graph.add_node(
            cell_id,
            level=level or cell.level,
            category=cell.category,
            function=cell.function,
            navigationType=cell.navigation_type,
            isExit=cell.is_exit,
            position=point,
            raw={"syntheticEndpoint": True, "cellSpaceRef": cell_id},
        )
        transfer_nodes = [node_id for node_id in self.topology.transfer_nodes_for_space(cell_id) if node_id in graph]
        for transfer_id in transfer_nodes:
            transfer_cell = self.topology.indoor.cells_by_id.get(transfer_id)
            if transfer_cell and not _profile_allows_cell(transfer_cell, mobility_profile):
                continue
            transfer_position = self.topology.node_position(transfer_id)
            if transfer_position is None:
                continue
            corridor_geometries = [geom for geom in (self.topology.cell_geometry(cell_id), self.topology.cell_geometry(transfer_id)) if geom is not None and not geom.is_empty]
            corridor_geometry = unary_union(corridor_geometries) if corridor_geometries else None
            length = _distance_within_cell(point, transfer_position, corridor_geometry)
            via_space_refs = [cell_id] + ([] if transfer_id == cell_id else [transfer_id])
            edge_data = {
                "resourceRef": f"SYN_{cell_id}_{transfer_id}",
                "lengthM": length,
                "baseTraversalTimeS": max(length / 1.2, 0.01),
                "locomotionTypes": list((transfer_cell.locomotion_types if transfer_cell else cell.locomotion_types) or ["Walking", "Rolling"]),
                "connectorType": transfer_cell.category if transfer_cell and transfer_cell.category in {"Stair", "Ramp", "Elevator"} else "horizontal",
                "viaSpaceRef": cell_id,
                "viaSpaceRefs": via_space_refs,
            }
            if not _profile_allows(edge_data, mobility_profile):
                continue
            if direction == "out":
                self._add_synthetic_edge(graph, cell_id, transfer_id, edge_data, cost_policy, mobility_profile, hazard_state, beacon_state, congestion, routing_config)
            elif direction == "in":
                self._add_synthetic_edge(graph, transfer_id, cell_id, edge_data, cost_policy, mobility_profile, hazard_state, beacon_state, congestion, routing_config)
            else:
                self._add_synthetic_edge(graph, cell_id, transfer_id, edge_data, cost_policy, mobility_profile, hazard_state, beacon_state, congestion, routing_config)
                self._add_synthetic_edge(graph, transfer_id, cell_id, edge_data, cost_policy, mobility_profile, hazard_state, beacon_state, congestion, routing_config)

    def _adjust_origin_edges_from_position(
        self,
        graph: nx.DiGraph,
        origin_id: str,
        origin_position: tuple[float, float],
        mobility_profile: MobilityProfile | None,
        cost_policy: str,
        hazard_state: HazardState,
        beacon_state: BeaconState,
        congestion: dict[str, int],
        routing_config: dict[str, Any],
    ) -> None:
        for _, target, data in list(graph.out_edges(origin_id, data=True)):
            target_position = graph.nodes.get(target, {}).get("position") or self.topology.node_position(target)
            if target_position is None:
                continue
            edge_data = _edge_data_for_remainder(data)
            edge_data["lengthM"] = self._remaining_edge_length(origin_id, target, origin_position, target_position, edge_data)
            edge_data["baseTraversalTimeS"] = max(float(edge_data["lengthM"]) / 1.2, 0.01)
            if not _profile_allows(edge_data, mobility_profile):
                continue
            breakdown = WeightSnapshotCompiler._weight_breakdown(
                edge_data,
                origin_id,
                target,
                cost_policy,
                mobility_profile,
                hazard_state,
                beacon_state,
                congestion,
                routing_config,
            )
            arc_id = str(data.get("arcId") or data.get("resourceRef") or "ARC")
            graph[origin_id][target].update(weight=breakdown["total"], arcId=arc_id, breakdown=breakdown, raw=edge_data)

    def _remaining_edge_length(
        self,
        source: str,
        target: str,
        start: tuple[float, float],
        end: tuple[float, float],
        edge_data: dict[str, Any],
    ) -> float:
        geometries = []
        refs = [source, target, edge_data.get("viaSpaceRef"), edge_data.get("transferSpaceRef"), *(edge_data.get("viaSpaceRefs") or [])]
        for ref in refs:
            geom = self.topology.cell_geometry(str(ref)) if ref else None
            if geom is not None and not geom.is_empty:
                geometries.append(geom)
        if not geometries:
            return max(math.dist(start, end), 0.01)
        return _distance_within_cell(start, end, unary_union(geometries))

    @staticmethod
    def _add_synthetic_edge(
        graph: nx.DiGraph,
        source: str,
        target: str,
        edge_data: dict[str, Any],
        cost_policy: str,
        mobility_profile: MobilityProfile | None,
        hazard_state: HazardState,
        beacon_state: BeaconState,
        congestion: dict[str, int],
        routing_config: dict[str, Any],
    ) -> None:
        breakdown = WeightSnapshotCompiler._weight_breakdown(
            edge_data,
            source,
            target,
            cost_policy,
            mobility_profile,
            hazard_state,
            beacon_state,
            congestion,
            routing_config,
        )
        arc_id = f"{edge_data['resourceRef']}_{source}_{target}"
        graph.add_edge(source, target, weight=breakdown["total"], arcId=arc_id, resourceRef=edge_data["resourceRef"], breakdown=breakdown, raw=edge_data)

    def _time_heuristic(self, mobility_profile: MobilityProfile | None) -> Callable[[str, str], float]:
        speed = float(mobility_profile.base_speed_mps if mobility_profile else 1.2)
        speed = max(speed, 0.01)

        def heuristic(left: str, right: str) -> float:
            distance = self._euclidean_distance(left, right)
            return distance / speed if distance is not None else 0.0

        return heuristic

    def _euclidean_distance(self, left: str, right: str) -> float | None:
        left_pos = self.topology.node_position(left)
        right_pos = self.topology.node_position(right)
        if left_pos and right_pos:
            return math.dist(left_pos, right_pos)
        return None

    @staticmethod
    def _route_from_path(path: list[str], snapshot: WeightedSnapshot, origin: str, target: str, algorithm: str, cost_policy: str) -> Route:
        arc_sequence = []
        total = 0.0
        breakdown = {
            "base": 0.0,
            "lengthM": 0.0,
            "movementOverhead": 0.0,
            "hazardPenalty": 0.0,
            "beaconPenalty": 0.0,
            "congestionPenalty": 0.0,
        }
        first_step = None
        for source, dest in zip(path, path[1:]):
            data = snapshot.graph[source][dest]
            arc_sequence.append(str(data.get("arcId")))
            total += float(data.get("weight", 0.0))
            for key in breakdown:
                breakdown[key] += float((data.get("breakdown") or {}).get(key, 0.0))
            if first_step is None:
                raw = data.get("raw") or {}
                first_step = {
                    "from": source,
                    "to": dest,
                    "weight": round(float(data.get("weight", 0.0)), 6),
                    "arcId": str(data.get("arcId") or ""),
                    "connectorType": raw.get("connectorType") or data.get("connectorType"),
                    "viaSpaceRef": raw.get("viaSpaceRef") or data.get("viaSpaceRef"),
                    "viaSpaceRefs": list(raw.get("viaSpaceRefs") or data.get("viaSpaceRefs") or []),
                    "breakdown": dict(data.get("breakdown") or {}),
                }
        breakdown = {key: round(value, 6) for key, value in breakdown.items()}
        breakdown["baseUnit"] = "s"
        breakdown["total"] = round(total, 6)
        if first_step:
            breakdown["firstStep"] = first_step
        return Route(
            origin=origin,
            destination=target,
            node_sequence=list(path),
            arc_sequence=arc_sequence,
            total_cost=round(total, 6),
            cost_policy=cost_policy,
            algorithm=algorithm,
            weight_breakdown=breakdown,
        )

    @staticmethod
    def _unreachable(origin: str, destination: str, algorithm: str, cost_policy: str, code: str) -> Route:
        return Route(
            origin=origin,
            destination=destination,
            node_sequence=[origin] if origin else [],
            arc_sequence=[],
            total_cost=math.inf,
            cost_policy=cost_policy,
            algorithm=algorithm,
            weight_breakdown={"total": math.inf},
            diagnostics=[Diagnostic("warning", code, "No reachable evacuation route was found.", [origin, destination])],
        )

    @staticmethod
    def _origin_candidates(graph: nx.DiGraph, origin_id: str, targets: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if origin_id not in graph:
            return []
        candidates = []
        for _, target, data in graph.out_edges(origin_id, data=True):
            raw = data.get("raw") or {}
            breakdown = data.get("breakdown") or {}
            route_total, suffix_target, suffix_path = _best_suffix_from_candidate(graph, target, targets or [])
            candidates.append(
                {
                    "to": target,
                    "weight": round(float(data.get("weight", 0.0)), 6),
                    "routeTotal": round(float(data.get("weight", 0.0)) + route_total, 6) if math.isfinite(route_total) else math.inf,
                    "suffixTarget": suffix_target,
                    "suffixPath": suffix_path,
                    "arcId": str(data.get("arcId") or ""),
                    "connectorType": raw.get("connectorType") or data.get("connectorType"),
                    "viaSpaceRef": raw.get("viaSpaceRef") or data.get("viaSpaceRef"),
                    "viaSpaceRefs": list(raw.get("viaSpaceRefs") or data.get("viaSpaceRefs") or []),
                    "lengthM": breakdown.get("lengthM"),
                    "base": breakdown.get("base"),
                    "total": breakdown.get("total"),
                }
            )
        return sorted(candidates, key=lambda item: float(item.get("routeTotal") or math.inf))[:limit]


def _profile_allows(edge_data: dict[str, Any], profile: MobilityProfile | None) -> bool:
    if profile is None:
        return True
    edge_locomotion = set(edge_data.get("locomotionTypes") or ["Walking", "Rolling"])
    if edge_locomotion and not edge_locomotion.intersection(profile.locomotion_types):
        return False
    connector_type = str(edge_data.get("connectorType") or "")
    if connector_type == "Stair" and not profile.can_use_stairs:
        return False
    if connector_type == "Ramp" and not profile.can_use_ramps:
        return False
    if connector_type == "Elevator" and not profile.can_use_elevators:
        return False
    return True


def _edge_data_for_remainder(data: dict[str, Any]) -> dict[str, Any]:
    raw = dict(data.get("raw") or {})
    edge_data = dict(raw)
    for key in (
        "resourceRef",
        "locomotionTypes",
        "connectorType",
        "viaBoundaryRef",
        "viaSpaceRef",
        "viaSpaceRefs",
        "viaRoomRef",
        "transferSpaceRef",
    ):
        if key not in edge_data and data.get(key) is not None:
            value = data.get(key)
            edge_data[key] = list(value) if isinstance(value, list) else value
    edge_data["resourceRef"] = str(edge_data.get("resourceRef") or data.get("resourceRef") or "ORIGIN_REMAINING")
    edge_data["locomotionTypes"] = list(edge_data.get("locomotionTypes") or data.get("locomotionTypes") or ["Walking", "Rolling"])
    edge_data["connectorType"] = str(edge_data.get("connectorType") or data.get("connectorType") or "horizontal")
    edge_data["viaSpaceRefs"] = list(edge_data.get("viaSpaceRefs") or [])
    return edge_data


def _best_suffix_from_candidate(graph: nx.DiGraph, candidate: str, targets: list[str]) -> tuple[float, str | None, list[str]]:
    if not targets or candidate not in graph:
        return math.inf, None, []
    best_cost = math.inf
    best_target: str | None = None
    best_path: list[str] = []
    for target in targets:
        if target not in graph:
            continue
        try:
            cost = float(nx.shortest_path_length(graph, candidate, target, weight="weight"))
            path = [str(node) for node in nx.shortest_path(graph, candidate, target, weight="weight")]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
        if cost < best_cost:
            best_cost = cost
            best_target = target
            best_path = path
    return best_cost, best_target, best_path[:12]


def _profile_allows_cell(cell: Any, profile: MobilityProfile | None) -> bool:
    if profile is None:
        return True
    locomotion = set(cell.locomotion_types or ["Walking", "Rolling"])
    if locomotion and not locomotion.intersection(profile.locomotion_types):
        return False
    if cell.category == "Stair" and not profile.can_use_stairs:
        return False
    if cell.category == "Ramp" and not profile.can_use_ramps:
        return False
    if cell.category == "Elevator" and not profile.can_use_elevators:
        return False
    return True


def _mobility_cache_key(profile: MobilityProfile | None) -> tuple[Any, ...]:
    if profile is None:
        return ("__none__",)
    return (
        profile.id,
        tuple(sorted(profile.locomotion_types)),
        bool(profile.can_use_stairs),
        bool(profile.can_use_ramps),
        bool(profile.can_use_elevators),
    )


def _distance_within_cell(start: tuple[float, float], end: tuple[float, float], geom: Any | None) -> float:
    direct = max(math.dist(start, end), 0.01)
    if geom is None or getattr(geom, "is_empty", True):
        return direct
    segment = LineString([start, end])
    try:
        if geom.buffer(1e-6).covers(segment):
            return direct
        representative = geom.representative_point()
        via = (float(representative.x), float(representative.y))
        return max(math.dist(start, via) + math.dist(via, end), direct, 0.01)
    except Exception:
        return direct


def _profile_traversal_time(
    edge_data: dict[str, Any],
    source: str,
    target: str,
    profile: MobilityProfile | None,
    routing_config: dict[str, Any],
) -> tuple[float, float]:
    length_m = max(_non_negative_float(edge_data.get("lengthM"), 1.0), 0.01)
    fallback_time = max(_non_negative_float(edge_data.get("baseTraversalTimeS"), length_m / 1.2), 0.01)
    speed = float(profile.base_speed_mps if profile else 1.2)
    if speed <= 0.0:
        return fallback_time, 0.0
    connector_type = str(edge_data.get("connectorType") or "")
    factor = _connector_speed_factor(connector_type, profile, routing_config)
    travel_time = max(length_m / max(speed * factor, 0.01), 0.01)
    overhead = _edge_time_overhead(edge_data, source, target, routing_config)
    return travel_time + overhead, overhead


def _edge_time_overhead(
    edge_data: dict[str, Any],
    source: str,
    target: str,
    routing_config: dict[str, Any],
) -> float:
    refs = [
        source,
        target,
        edge_data.get("resourceRef"),
        edge_data.get("viaBoundaryRef"),
        edge_data.get("viaSpaceRef"),
        edge_data.get("transferSpaceRef"),
        *(edge_data.get("viaSpaceRefs") or []),
    ]
    text = " ".join(str(ref).upper() for ref in refs if ref)
    connector_type = str(edge_data.get("connectorType") or "")
    overhead = _non_negative_float(routing_config.get("edgeAccelerationDelayS"), 0.12)
    if "_DOOR_" in text:
        overhead += _non_negative_float(routing_config.get("doorTraversalPenaltyS"), 0.35)
    if "VTN_" in text or "VIRTUAL" in text:
        overhead += _non_negative_float(routing_config.get("virtualBoundaryTraversalPenaltyS"), 0.10)
    if connector_type in {"Stair", "Ramp"}:
        overhead += _non_negative_float(routing_config.get("linearTransferTraversalPenaltyS"), 0.35)
    elif connector_type == "Elevator":
        overhead += _non_negative_float(routing_config.get("elevatorTraversalPenaltyS"), 1.0)
    elif "_EP_VC_" in text:
        overhead += _non_negative_float(routing_config.get("transferTraversalPenaltyS"), 0.12)
    return max(overhead, 0.0)


def _connector_speed_factor(
    connector_type: str,
    profile: MobilityProfile | None,
    routing_config: dict[str, Any],
) -> float:
    defaults = {
        "Stair": 0.55,
        "Ramp": 0.7,
        "Elevator": 0.5,
    }
    field = {
        "Stair": "stairSpeedFactor",
        "Ramp": "rampSpeedFactor",
        "Elevator": "elevatorSpeedFactor",
    }.get(connector_type)
    if not field:
        return 1.0
    raw_value = None
    if profile and field in profile.attributes:
        raw_value = profile.attributes.get(field)
    if raw_value is None:
        raw_value = routing_config.get(field)
    factor = _non_negative_float(raw_value, defaults[connector_type])
    return min(max(factor, 0.01), 1.0)


def _risk_for_edge(
    edge_risk: dict[str, float],
    cell_risk: dict[str, float],
    resource_ref: str,
    source: str,
    target: str,
    endpoint_policy: str,
    edge_precedence: bool,
) -> float:
    if edge_precedence and resource_ref in edge_risk:
        return _bounded_risk(edge_risk.get(resource_ref, 0.0))
    source_risk = _bounded_risk(cell_risk.get(source, 0.0))
    target_risk = _bounded_risk(cell_risk.get(target, 0.0))
    if endpoint_policy == "source":
        return source_risk
    if endpoint_policy == "mean":
        return (source_risk + target_risk) * 0.5
    if endpoint_policy == "min":
        return min(source_risk, target_risk)
    if endpoint_policy == "max":
        return max(source_risk, target_risk)
    return target_risk


def _combine_risk(hazard: float, beacon: float, aggregation: str) -> float:
    if aggregation == "max":
        return max(hazard, beacon)
    if aggregation == "mean":
        active = [value for value in (hazard, beacon) if value > 0.0]
        return sum(active) / len(active) if active else 0.0
    return min(1.0, hazard + beacon)


def _bounded_risk(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, parsed))


def _non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0.0 else default

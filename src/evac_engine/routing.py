"""Route planning and immutable weight snapshot compilation."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

import networkx as nx

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

        for source, target, key, data in self.topology.graph.edges(keys=True, data=True):
            if source not in graph or target not in graph:
                continue
            resource_ref = str(data.get("resourceRef") or key)
            if resource_ref in hazard_state.blocked_resources:
                continue
            if not _profile_allows(data, mobility_profile):
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
        base = _profile_traversal_time(edge_data, mobility_profile, routing_config)
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
    ) -> Route:
        origin_id = self.topology.indoor.resolve_cell_ref(origin) or origin
        targets = self._targets(target_refs)
        if origin_id not in self.topology.graph:
            return self._unreachable(origin_id, "", algorithm, cost_policy, "UNKNOWN_ORIGIN")
        if not targets:
            return self._unreachable(origin_id, "", algorithm, cost_policy, "NO_TARGETS")
        if algorithm not in SUPPORTED_ROUTE_ALGORITHMS:
            return self._unreachable(origin_id, targets[0], algorithm, cost_policy, "UNSUPPORTED_ALGORITHM")

        compile_start = time.perf_counter()
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
        planning_start = time.perf_counter()
        candidate = self.recommendations.recommend(
            snapshot.graph,
            origin_id,
            targets,
            heuristic=self._time_heuristic(mobility_profile),
            config=RouteRecommendationConfig.from_routing_config(algorithm, routing_config),
        )
        planning_ms = (time.perf_counter() - planning_start) * 1000.0
        if candidate:
            route = self._route_from_path(candidate.node_sequence, snapshot, origin_id, candidate.destination, algorithm, cost_policy)
            route.weight_breakdown["snapshotCompileMs"] = round(snapshot_compile_ms, 6)
            route.weight_breakdown["planningMs"] = round(planning_ms, 6)
            if candidate.metrics:
                route.weight_breakdown["routeMetrics"] = dict(candidate.metrics)
            return route
        route = self._unreachable(origin_id, targets[0], algorithm, cost_policy, "NO_ROUTE")
        route.weight_breakdown["snapshotCompileMs"] = round(snapshot_compile_ms, 6)
        route.weight_breakdown["planningMs"] = round(planning_ms, 6)
        return route

    def _targets(self, target_refs: list[str] | None) -> list[str]:
        raw_targets = target_refs or self.topology.exit_candidates()
        targets = []
        for target in raw_targets:
            resolved = self.topology.indoor.resolve_cell_ref(target) or target
            if resolved in self.topology.graph and resolved not in targets:
                targets.append(resolved)
        return targets

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
        breakdown = {"base": 0.0, "lengthM": 0.0, "hazardPenalty": 0.0, "beaconPenalty": 0.0, "congestionPenalty": 0.0}
        for source, dest in zip(path, path[1:]):
            data = snapshot.graph[source][dest]
            arc_sequence.append(str(data.get("arcId")))
            total += float(data.get("weight", 0.0))
            for key in breakdown:
                breakdown[key] += float((data.get("breakdown") or {}).get(key, 0.0))
        breakdown = {key: round(value, 6) for key, value in breakdown.items()}
        breakdown["baseUnit"] = "s"
        breakdown["total"] = round(total, 6)
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


def _profile_traversal_time(
    edge_data: dict[str, Any],
    profile: MobilityProfile | None,
    routing_config: dict[str, Any],
) -> float:
    length_m = max(_non_negative_float(edge_data.get("lengthM"), 1.0), 0.01)
    fallback_time = max(_non_negative_float(edge_data.get("baseTraversalTimeS"), length_m / 1.2), 0.01)
    speed = float(profile.base_speed_mps if profile else 1.2)
    if speed <= 0.0:
        return fallback_time
    connector_type = str(edge_data.get("connectorType") or "")
    factor = _connector_speed_factor(connector_type, profile, routing_config)
    return max(length_m / max(speed * factor, 0.01), 0.01)


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

"""Route planning and immutable weight snapshot compilation."""

from __future__ import annotations

import math
from typing import Any

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
        cost_policy: str = "shortest_distance",
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
            breakdown = self._weight_breakdown(data, target, cost_policy, hazard_state, beacon_state, congestion, routing_config)
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
        target: str,
        cost_policy: str,
        hazard_state: HazardState,
        beacon_state: BeaconState,
        congestion: dict[str, int],
        routing_config: dict[str, Any],
    ) -> dict[str, Any]:
        if cost_policy == "minimum_travel_time":
            base = float(edge_data.get("baseTraversalTimeS") or edge_data.get("lengthM") or 1.0)
        else:
            base = float(edge_data.get("lengthM") or 1.0)
        resource_ref = str(edge_data.get("resourceRef") or "")
        hazard = float(hazard_state.edge_risk.get(resource_ref, 0.0) or hazard_state.cell_risk.get(target, 0.0))
        beacon = float(beacon_state.edge_risk.get(resource_ref, 0.0) or beacon_state.cell_risk.get(target, 0.0))
        crowd = float(congestion.get(target, 0))
        use_hazard = bool(routing_config.get("useHazardRisk", True))
        use_beacon = bool(routing_config.get("useBeaconRisk", True))
        use_congestion = bool(routing_config.get("useCongestion", False))
        hazard_penalty = base * hazard * 20.0 if use_hazard else 0.0
        beacon_penalty = base * beacon * 5.0 if use_beacon else 0.0
        congestion_penalty = crowd * 0.2 if use_congestion else 0.0
        total = base + hazard_penalty + beacon_penalty + congestion_penalty
        return {
            "base": round(base, 6),
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
        cost_policy: str = "shortest_distance",
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
        candidate = self.recommendations.recommend(
            snapshot.graph,
            origin_id,
            targets,
            heuristic=self._heuristic,
            config=RouteRecommendationConfig.from_routing_config(algorithm, routing_config),
        )
        if candidate:
            route = self._route_from_path(candidate.node_sequence, snapshot, origin_id, candidate.destination, algorithm, cost_policy)
            if candidate.metrics:
                route.weight_breakdown["routeMetrics"] = dict(candidate.metrics)
            return route
        return self._unreachable(origin_id, targets[0], algorithm, cost_policy, "NO_ROUTE")

    def _targets(self, target_refs: list[str] | None) -> list[str]:
        raw_targets = target_refs or self.topology.exit_candidates()
        targets = []
        for target in raw_targets:
            resolved = self.topology.indoor.resolve_cell_ref(target) or target
            if resolved in self.topology.graph and resolved not in targets:
                targets.append(resolved)
        return targets

    def _heuristic(self, left: str, right: str) -> float:
        left_pos = self.topology.node_position(left)
        right_pos = self.topology.node_position(right)
        if left_pos and right_pos:
            return math.dist(left_pos, right_pos)
        return 0.0

    @staticmethod
    def _route_from_path(path: list[str], snapshot: WeightedSnapshot, origin: str, target: str, algorithm: str, cost_policy: str) -> Route:
        arc_sequence = []
        total = 0.0
        breakdown = {"base": 0.0, "hazardPenalty": 0.0, "beaconPenalty": 0.0, "congestionPenalty": 0.0}
        for source, dest in zip(path, path[1:]):
            data = snapshot.graph[source][dest]
            arc_sequence.append(str(data.get("arcId")))
            total += float(data.get("weight", 0.0))
            for key in breakdown:
                breakdown[key] += float((data.get("breakdown") or {}).get(key, 0.0))
        breakdown = {key: round(value, 6) for key, value in breakdown.items()}
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

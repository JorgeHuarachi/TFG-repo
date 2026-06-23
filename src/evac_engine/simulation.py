"""Synchronous evacuation simulation over the canonical topology."""

from __future__ import annotations

import csv
import copy
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any

from shapely.geometry import LineString, Point
from shapely.ops import nearest_points, unary_union

from .domain import AgentState, IndoorModelBundle, MobilityProfile, ScenarioDefinition, SimulationResult
from .overlays import BeaconSimulator, HazardScheduler
from .routing import RoutingEngine
from .topology import EvacTopology

try:  # Mesa remains optional at import-time for documentation and static tooling.
    from mesa.space import ContinuousSpace
except Exception:  # pragma: no cover - exercised only when Mesa is unavailable.
    ContinuousSpace = None


class EvacuationModel:
    """Tick-synchronous model.

    All agents sense the same overlay snapshot for a tick, decide against that
    immutable snapshot, and then commit their movement together.
    """

    def __init__(self, indoor: IndoorModelBundle, scenario: ScenarioDefinition) -> None:
        self.indoor = indoor
        self.scenario = scenario
        self.topology = EvacTopology.from_indoor_model(indoor)
        self.routing_engine = RoutingEngine(self.topology)
        self.hazard_scheduler = HazardScheduler(self.topology, scenario.hazards)
        self.beacons = copy.deepcopy(scenario.beacons)
        self.scheduled_events = list(scenario.raw.get("scheduledEvents") or [])
        self._applied_scheduled_events: set[str] = set()
        self._visibility_corridors: dict[tuple[str, ...], Any] = {}
        self.beacon_simulator = BeaconSimulator(
            self.topology,
            self.beacons,
            (scenario.raw.get("beaconSystem") or {}).get("fusion"),
        )
        self.random = random.Random(_stable_seed(scenario.random_seed, scenario.scenario_id))
        self.step_count = 0
        self.time_s = 0.0
        self.events: list[dict[str, Any]] = []
        self.trajectories: list[dict[str, Any]] = []
        self._spaces = self._build_continuous_spaces()
        self._wall_geometries_by_level = self._build_wall_geometries()
        self.agents = self._materialize_agents()
        self._resolve_overlaps(self.agents)
        self._initial_agent_count = len(self.agents)

    def step(self) -> None:
        self._apply_scheduled_events()
        hazard_state = self.hazard_scheduler.state_at(self.step_count, self.time_s)
        self.beacon_simulator.beacons = self.beacons
        beacon_state = self.beacon_simulator.state_at(self.step_count, self.time_s)
        congestion = self._congestion()
        route_targets = list(((self.scenario.routing.get("destination") or {}).get("cellSpaceRefs") or []))
        routing_config = dict(self.scenario.routing)
        cost_policy = str(routing_config.get("costPolicy", "shortest_distance"))
        algorithm = str(routing_config.get("algorithm", "dijkstra"))
        replan = str(routing_config.get("replanPolicy", "on_blocked_or_interval"))
        replan_interval = int(routing_config.get("replanIntervalSteps", 10))

        decisions: list[tuple[AgentState, str, tuple[float, float], tuple[float, float]]] = []
        for agent in self.agents:
            if agent.status != "active":
                agent.velocity = (0.0, 0.0)
                self._record_trajectory(agent)
                continue
            if agent.current_cell in hazard_state.blocked_cells:
                agent.status = "trapped"
                agent.velocity = (0.0, 0.0)
                agent.no_route_reason = "current_cell_blocked"
                self._event("agent_trapped", agent, {"cellSpaceRef": agent.current_cell})
                self._record_trajectory(agent)
                continue
            profile = self.scenario.mobility_profiles[agent.profile_id]
            if self._needs_route(agent, replan, replan_interval, hazard_state.blocked_cells):
                agent.route = self.routing_engine.find_route(
                    origin=agent.current_cell,
                    target_refs=route_targets,
                    mobility_profile=profile,
                    algorithm=algorithm,
                    cost_policy=cost_policy,
                    hazard_state=hazard_state,
                    beacon_state=beacon_state,
                    congestion=congestion,
                    routing_config=routing_config,
                    step=self.step_count,
                    time_s=self.time_s,
                )
                agent.route_index = 0
                if not agent.route.reachable:
                    agent.status = "no_route"
                    agent.velocity = (0.0, 0.0)
                    agent.no_route_reason = (agent.route.diagnostics[0].code if agent.route.diagnostics else "NO_ROUTE")
                    self._event("agent_no_route", agent, {"reason": agent.no_route_reason})
                    self._record_trajectory(agent)
                    continue
                self._event("route_planned", agent, {"route": agent.route.to_dict()})

            self._consume_embedded_route_progress(agent)
            target_cell = self._next_route_cell(agent)
            if target_cell is None:
                agent.status = "evacuated"
                agent.velocity = (0.0, 0.0)
                agent.evacuation_time_s = self.time_s
                self._event("agent_evacuated", agent, {"cellSpaceRef": agent.current_cell})
                self._record_trajectory(agent)
                continue
            if agent.current_cell.startswith("VTN_") and self._point_inside_cell(target_cell, agent.position):
                decisions.append((agent, target_cell, agent.position, agent.velocity))
                continue
            self._advance_visible_route(agent)
            target_cell = self._next_route_cell(agent)
            if target_cell is None:
                agent.status = "evacuated"
                agent.velocity = (0.0, 0.0)
                agent.evacuation_time_s = self.time_s
                self._event("agent_evacuated", agent, {"cellSpaceRef": agent.current_cell})
                self._record_trajectory(agent)
                continue
            speed = profile.base_speed_mps * hazard_state.speed_factors.get(agent.current_cell, 1.0)
            next_pos, arrived, next_velocity = self._advance(agent, target_cell, speed)
            decisions.append((agent, target_cell if arrived else agent.current_cell, next_pos, next_velocity))

        decisions = self._apply_transfer_capacity(decisions)
        for agent, new_cell, new_pos, new_velocity in decisions:
            agent.position = new_pos
            agent.velocity = new_velocity
            if new_cell != agent.current_cell:
                agent.current_cell = new_cell
                agent.level = self.topology.node_level(new_cell)
                agent.route_index += 1
                self._event("agent_entered_cell", agent, {"cellSpaceRef": new_cell})
            agent.travel_time_s += self.scenario.time_step_s

        self._resolve_overlaps([agent for agent, _, _, _ in decisions if agent.status == "active"])
        for agent, _, _, _ in decisions:
            self._record_trajectory(agent)

        self.step_count += 1
        self.time_s = round(self.time_s + self.scenario.time_step_s, 9)

    def run(self, output_dir: str | Path | None = None) -> SimulationResult:
        while self.step_count < self.scenario.max_steps and any(agent.status == "active" for agent in self.agents):
            self.step()
        result = SimulationResult(
            scenario_id=self.scenario.scenario_id,
            steps_executed=self.step_count,
            completed=not any(agent.status == "active" for agent in self.agents),
            metrics=self.metrics(),
            routes=[agent.route.to_dict() for agent in self.agents if agent.route],
            events=list(self.events),
            trajectories=list(self.trajectories),
        )
        resolved_output = output_dir or self.scenario.outputs.get("outputFolder")
        if resolved_output:
            result.output_dir = write_outputs(result, Path(resolved_output))
        return result

    def metrics(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        evacuation_times = []
        for agent in self.agents:
            status_counts[agent.status] = status_counts.get(agent.status, 0) + 1
            if agent.evacuation_time_s is not None:
                evacuation_times.append(agent.evacuation_time_s)
        return {
            "scenarioId": self.scenario.scenario_id,
            "stepsExecuted": self.step_count,
            "timeS": round(self.time_s, 6),
            "agentCount": self._initial_agent_count,
            "statusCounts": status_counts,
            "evacuated": status_counts.get("evacuated", 0),
            "noRoute": status_counts.get("no_route", 0),
            "trapped": status_counts.get("trapped", 0),
            "meanEvacuationTimeS": round(sum(evacuation_times) / len(evacuation_times), 6) if evacuation_times else None,
            "maxEvacuationTimeS": max(evacuation_times) if evacuation_times else None,
            "topology": self.topology.to_summary(),
        }

    def _build_continuous_spaces(self) -> dict[str, Any]:
        if ContinuousSpace is None:
            return {}
        spaces: dict[str, Any] = {}
        for level_id, level in self.indoor.levels_by_id.items():
            coords = (((level.get("spatialExtent2D") or {}).get("coordinates") or [[]])[0] or [])
            if coords:
                xs = [coord[0] for coord in coords]
                ys = [coord[1] for coord in coords]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
            else:
                x_min, y_min, x_max, y_max = 0.0, 0.0, 100.0, 100.0
            try:
                spaces[level_id] = ContinuousSpace(x_max=x_max, y_max=y_max, torus=False, x_min=x_min, y_min=y_min)
            except TypeError:
                spaces[level_id] = ContinuousSpace(x_max, y_max, False)
        return spaces

    def _build_wall_geometries(self) -> dict[str, Any]:
        by_level: dict[str, list[Any]] = {}
        for cell in self.indoor.cells_by_id.values():
            if cell.level and cell.geometry is not None and not cell.geometry.is_empty and not cell.is_navigable:
                by_level.setdefault(cell.level, []).append(cell.geometry)
        return {level: unary_union(geoms) for level, geoms in by_level.items() if geoms}

    def _materialize_agents(self) -> list[AgentState]:
        spawns = {spawn["spawnId"]: spawn for spawn in self.scenario.spawns}
        agents: list[AgentState] = []
        for raw in self.scenario.agents:
            spawn_cell = self.indoor.resolve_cell_ref(raw.get("initialCellSpaceRef"))
            if not spawn_cell:
                continue
            position = _coords(raw.get("initialPosition")) or self.topology.node_position(spawn_cell) or (0.0, 0.0)
            agents.append(
                AgentState(
                    agent_id=raw["agentId"],
                    group_id=raw.get("groupRef"),
                    profile_id=raw["mobilityProfileRef"],
                    current_cell=spawn_cell,
                    level=self.topology.node_level(spawn_cell),
                    position=position,
                )
            )
        for group in self.scenario.groups:
            spawn = spawns[group["spawnRef"]]
            profile_id = group["mobilityProfileRef"]
            cell_id = self.indoor.resolve_cell_ref(spawn.get("cellSpaceRef"))
            if not cell_id:
                continue
            count = int(group.get("count", 0))
            for index in range(count):
                position = self._spawn_position(spawn, cell_id, str(group.get("distribution", "fixed")))
                agents.append(
                    AgentState(
                        agent_id=f"{group['groupId']}_{index + 1:04d}",
                        group_id=group.get("groupId"),
                        profile_id=profile_id,
                        current_cell=cell_id,
                        level=self.topology.node_level(cell_id),
                        position=position,
                    )
                )
        return agents

    def _spawn_position(self, spawn: dict[str, Any], cell_id: str, distribution: str) -> tuple[float, float]:
        fixed = _coords(spawn.get("position")) or self.topology.node_position(cell_id) or (0.0, 0.0)
        if distribution != "random_within_space":
            return fixed
        geom = self.topology.cell_geometry(cell_id)
        if geom is None or geom.is_empty:
            return fixed
        minx, miny, maxx, maxy = geom.bounds
        for _ in range(100):
            point = Point(self.random.uniform(minx, maxx), self.random.uniform(miny, maxy))
            if geom.covers(point):
                return (float(point.x), float(point.y))
        return fixed

    def _resolve_overlaps(self, agents: list[AgentState]) -> None:
        by_level: dict[str, list[AgentState]] = {}
        for agent in agents:
            if agent.status != "active" or not agent.level:
                continue
            cell = self.indoor.cells_by_id.get(agent.current_cell)
            if not cell or cell.navigation_type != "GeneralSpace":
                continue
            if self._is_transfer_like(self._next_route_cell(agent) or ""):
                continue
            by_level.setdefault(agent.level, []).append(agent)
        for level_agents in by_level.values():
            for _ in range(12):
                moved = False
                for index, left in enumerate(level_agents):
                    for right in level_agents[index + 1 :]:
                        min_distance = self._body_radius(left) + self._body_radius(right)
                        dx = right.position[0] - left.position[0]
                        dy = right.position[1] - left.position[1]
                        distance = (dx * dx + dy * dy) ** 0.5
                        if distance >= min_distance:
                            continue
                        if distance < 1e-6:
                            jitter = self.random.random() * 6.283185307179586
                            dx, dy, distance = math_cos(jitter), math_sin(jitter), 1.0
                        overlap = (min_distance - distance) * 0.55
                        ux, uy = dx / distance, dy / distance
                        left_candidate = (left.position[0] - ux * overlap, left.position[1] - uy * overlap)
                        right_candidate = (right.position[0] + ux * overlap, right.position[1] + uy * overlap)
                        left.position = self._limited_soft_project(left.current_cell, left.position, left_candidate)
                        right.position = self._limited_soft_project(right.current_cell, right.position, right_candidate)
                        moved = True
                if not moved:
                    break

    def _apply_transfer_capacity(
        self, decisions: list[tuple[AgentState, str, tuple[float, float], tuple[float, float]]]
    ) -> list[tuple[AgentState, str, tuple[float, float], tuple[float, float]]]:
        occupied: dict[str, int] = {}
        for agent in self.agents:
            if agent.status == "active" and self._is_transfer_like(agent.current_cell):
                occupied[agent.current_cell] = occupied.get(agent.current_cell, 0) + 1
        reserved: dict[str, int] = {}
        filtered = []
        for agent, new_cell, new_pos, new_velocity in decisions:
            if new_cell == agent.current_cell or not self._is_transfer_like(new_cell):
                filtered.append((agent, new_cell, new_pos, new_velocity))
                continue
            if occupied.get(new_cell, 0) + reserved.get(new_cell, 0) >= self._transfer_capacity(new_cell):
                filtered.append((agent, agent.current_cell, agent.position, (0.0, 0.0)))
                if not any(
                    event.get("eventType") == "agent_waited_capacity"
                    and event.get("agentId") == agent.agent_id
                    and event.get("step") == self.step_count
                    for event in self.events
                ):
                    self._event("agent_waited_capacity", agent, {"cellSpaceRef": new_cell})
                continue
            reserved[new_cell] = reserved.get(new_cell, 0) + 1
            filtered.append((agent, new_cell, new_pos, new_velocity))
        return filtered

    def _is_transfer_like(self, cell_id: str) -> bool:
        if cell_id.startswith("VTN_"):
            return True
        cell = self.indoor.cells_by_id.get(cell_id)
        return bool(cell and cell.navigation_type == "TransferSpace")

    def _transfer_capacity(self, cell_id: str) -> int:
        if cell_id.startswith("VTN_"):
            return 2
        cell = self.indoor.cells_by_id.get(cell_id)
        if not cell:
            return 1
        if cell.category in {"Stair", "Ramp"}:
            return 3
        if cell.category == "Elevator":
            return 4
        if cell.category == "Exit":
            return 6
        return 2

    def _consume_embedded_route_progress(self, agent: AgentState) -> None:
        for _ in range(3):
            target_cell = self._next_route_cell(agent)
            if not target_cell or self._is_transfer_like(target_cell):
                return
            if not self._point_inside_cell(target_cell, agent.position):
                return
            agent.current_cell = target_cell
            agent.level = self.topology.node_level(target_cell)
            agent.route_index += 1
            self._event("agent_entered_cell", agent, {"cellSpaceRef": target_cell})

    def _soft_project(self, cell_id: str, position: tuple[float, float]) -> tuple[float, float]:
        geom = self.topology.cell_geometry(cell_id)
        if geom is None or geom.is_empty:
            return position
        point = Point(position)
        if geom.buffer(-1e-6).covers(point) or geom.covers(point):
            return position
        try:
            _, nearest = nearest_points(point, geom)
            return (float(nearest.x), float(nearest.y))
        except Exception:
            representative = geom.representative_point()
            return (float(representative.x), float(representative.y))

    def _limited_soft_project(
        self,
        cell_id: str,
        original: tuple[float, float],
        candidate: tuple[float, float],
    ) -> tuple[float, float]:
        projected = self._soft_project(cell_id, candidate)
        projection_distance = _distance(candidate, projected)
        requested_distance = max(_distance(original, candidate), 1e-9)
        if projection_distance > max(requested_distance * 2.0, 0.25):
            return original
        return projected

    def _body_radius(self, agent: AgentState) -> float:
        profile = self.scenario.mobility_profiles.get(agent.profile_id)
        if not profile:
            return float(self.scenario.physics.get("bodyRadiusM", 0.25))
        return float(profile.attributes.get("bodyRadiusM", self.scenario.physics.get("bodyRadiusM", 0.25)))

    def _point_inside_cell(self, cell_id: str, position: tuple[float, float]) -> bool:
        geom = self.topology.cell_geometry(cell_id)
        return bool(geom is not None and not geom.is_empty and geom.buffer(1e-6).covers(Point(position)))

    def _needs_route(self, agent: AgentState, replan: str, interval: int, blocked_cells: set[str]) -> bool:
        if agent.route is None:
            return True
        if replan == "never":
            return False
        remaining = set(agent.route.node_sequence[agent.route_index + 1 :])
        if remaining & blocked_cells:
            return True
        return interval > 0 and self.step_count > 0 and self.step_count % interval == 0

    def _next_route_cell(self, agent: AgentState) -> str | None:
        if not agent.route or not agent.route.reachable:
            return None
        if agent.route_index >= len(agent.route.node_sequence) - 1:
            return None
        return agent.route.node_sequence[agent.route_index + 1]

    def _advance_visible_route(self, agent: AgentState) -> None:
        return

    def _has_line_of_sight(self, agent: AgentState, candidate_index: int) -> bool:
        if not agent.route:
            return False
        candidate = agent.route.node_sequence[candidate_index]
        waypoint = self._local_waypoint(agent, candidate)
        if _distance(agent.position, waypoint) > float(self.scenario.physics.get("lineOfSightDistanceM", 12.0)):
            return False
        corridor = self._route_corridor(list(agent.route.node_sequence[agent.route_index : candidate_index + 1]))
        if corridor is None or corridor.is_empty:
            return False
        return bool(corridor.buffer(1e-6).covers(LineString([agent.position, waypoint])))

    def _advance(self, agent: AgentState, target_cell: str, speed_mps: float) -> tuple[tuple[float, float], bool, tuple[float, float]]:
        current = agent.position
        waypoint = self._local_waypoint(agent, target_cell)
        distance_to_waypoint = _distance(current, waypoint)
        arrival_radius = self._arrival_radius(target_cell)
        if self._is_transfer_like(agent.current_cell) and target_cell in self.indoor.cells_by_id:
            arrival_radius = min(arrival_radius, 0.05)
        max_distance = speed_mps * self.scenario.time_step_s
        target_geom = self.topology.cell_geometry(target_cell)
        hold_center = self._transfer_center_hold(agent, target_cell, max_distance)
        if hold_center is not None:
            waypoint = hold_center
            distance_to_waypoint = _distance(current, waypoint)
        inside_target = bool(target_geom is not None and not target_geom.is_empty and target_geom.buffer(1e-6).covers(Point(current)))
        close_entry = None if hold_center is not None else self._close_transfer_entry(agent, current, target_cell, target_geom, max_distance)
        if close_entry is not None:
            velocity = ((close_entry[0] - current[0]) / max(self.scenario.time_step_s, 1e-9), (close_entry[1] - current[1]) / max(self.scenario.time_step_s, 1e-9))
            return close_entry, True, velocity
        arrived = False if hold_center is not None else inside_target or distance_to_waypoint <= arrival_radius + max(max_distance, 1e-9)
        target = self._motion_target(agent, target_cell, waypoint, arrived, hold_center is not None)
        desired = _unit((target[0] - current[0], target[1] - current[1]))
        social = self._social_repulsion(agent)
        wall = self._wall_repulsion(agent, target_cell)
        center_pull = self._transfer_center_direction(agent, target_cell)
        desired_weight = 1.8
        center_weight = 0.0
        social_weight = float(self.scenario.physics.get("socialRepulsion", 2.0))
        in_transfer_corridor = self._is_transfer_like(target_cell) or self._is_transfer_like(agent.current_cell)
        if in_transfer_corridor:
            social_weight *= 0.05
            desired_weight = 3.6
            center_weight = 0.0
        wall_weight = float(self.scenario.physics.get("wallRepulsion", 4.0))
        if in_transfer_corridor:
            wall_weight *= min(self._transfer_wall_scale(target_cell), self._transfer_wall_scale(agent.current_cell))
        if self._is_linear_transfer(agent.current_cell) or self._is_linear_transfer(target_cell):
            social_weight *= 0.2
            wall_weight *= 0.2
            desired_weight = max(desired_weight, 4.2)
        vector = (
            desired[0] * desired_weight + center_pull[0] * center_weight + social[0] * social_weight + wall[0] * wall_weight,
            desired[1] * desired_weight + center_pull[1] * center_weight + social[1] * social_weight + wall[1] * wall_weight,
        )
        direction = _unit(vector)
        if direction == (0.0, 0.0):
            direction = desired
        direction = self._steered_direction(agent.velocity, direction)
        target_velocity = (direction[0] * speed_mps, direction[1] * speed_mps)
        next_velocity = self._accelerated_velocity(agent.velocity, target_velocity)
        travel = min(_distance((0.0, 0.0), next_velocity) * self.scenario.time_step_s, max_distance)
        if arrived:
            entry_margin = min(0.12, max_distance)
            travel = 0.0 if inside_target else min(max_distance, distance_to_waypoint + entry_margin)
            if not inside_target:
                next_velocity = (direction[0] * (travel / max(self.scenario.time_step_s, 1e-9)), direction[1] * (travel / max(self.scenario.time_step_s, 1e-9)))
        turn_scale = self._turn_speed_scale(agent.velocity, direction)
        if turn_scale < 1.0 and travel > 0:
            travel *= turn_scale
            next_velocity = (next_velocity[0] * turn_scale, next_velocity[1] * turn_scale)
        next_position = (current[0] + direction[0] * travel, current[1] + direction[1] * travel)
        if arrived and target_cell in self.indoor.cells_by_id:
            next_position = self._constrain_step(agent, target_cell, current, next_position)
            next_position = self._wall_clearance_project(agent, target_cell, current, next_position)
            target_geom = self.topology.cell_geometry(target_cell)
            if target_geom is not None and target_geom.buffer(1e-6).covers(Point(next_position)):
                next_position = self._soft_project(target_cell, next_position)
            else:
                arrived = False
        elif not arrived:
            next_position = self._constrain_step(agent, target_cell, current, next_position)
            next_position = self._wall_clearance_project(agent, target_cell, current, next_position)
        return next_position, arrived, next_velocity

    def _constrain_step(
        self,
        agent: AgentState,
        target_cell: str,
        current: tuple[float, float],
        proposed: tuple[float, float],
    ) -> tuple[float, float]:
        allowed = self._movement_geometry(agent, target_cell)
        if allowed is None or allowed.is_empty:
            return proposed
        segment = LineString([current, proposed])
        safe_area = allowed.buffer(1e-6)
        if agent.current_cell.startswith("VTN_") and not safe_area.covers(Point(current)):
            try:
                _, nearest = nearest_points(Point(current), allowed)
                projected = (float(nearest.x), float(nearest.y))
                limit = max(_distance(current, proposed), 1e-9)
                distance = _distance(current, projected)
                if distance <= limit:
                    return projected
                direction = _unit((projected[0] - current[0], projected[1] - current[1]))
                return (current[0] + direction[0] * limit, current[1] + direction[1] * limit)
            except Exception:
                return proposed
        if safe_area.covers(segment):
            return proposed
        step_length = _distance(current, proposed)
        dy = proposed[1] - current[1]
        dx = proposed[0] - current[0]
        slide_candidates = [(current[0], proposed[1]), (proposed[0], current[1])]
        if abs(dy) > 1e-9:
            slide_candidates.append((current[0], current[1] + (1.0 if dy > 0 else -1.0) * step_length))
        if abs(dx) > 1e-9:
            slide_candidates.append((current[0] + (1.0 if dx > 0 else -1.0) * step_length, current[1]))
        valid_slides = []
        for candidate in slide_candidates:
            candidate_segment = LineString([current, candidate])
            if safe_area.covers(candidate_segment):
                valid_slides.append(candidate)
        if valid_slides:
            return min(valid_slides, key=lambda item: _distance(item, proposed))
        best = current
        lo, hi = 0.0, 1.0
        for _ in range(16):
            mid = (lo + hi) * 0.5
            candidate = (current[0] + (proposed[0] - current[0]) * mid, current[1] + (proposed[1] - current[1]) * mid)
            candidate_segment = LineString([current, candidate])
            if safe_area.covers(candidate_segment):
                best = candidate
                lo = mid
            else:
                hi = mid
        return best

    def _movement_geometry(self, agent: AgentState, target_cell: str) -> Any | None:
        geometries = []
        route_cells = self._movement_route_cells(agent, target_cell)
        if route_cells:
            corridor = self._route_corridor(route_cells)
            if corridor is not None and not corridor.is_empty:
                return corridor
        for cell_id in (agent.current_cell, target_cell):
            geom = self.topology.cell_geometry(cell_id)
            if geom is not None and not geom.is_empty:
                geometries.append(geom)
        if (agent.current_cell.startswith("VTN_") or target_cell.startswith("VTN_")) and agent.route:
            for index in range(max(agent.route_index - 1, 0), min(agent.route_index + 3, len(agent.route.node_sequence))):
                geom = self.topology.cell_geometry(agent.route.node_sequence[index])
                if geom is not None and not geom.is_empty:
                    geometries.append(geom)
        if not geometries:
            return None
        return unary_union(geometries)

    def _movement_route_cells(self, agent: AgentState, target_cell: str) -> list[str]:
        if not agent.route or not agent.route.reachable:
            return []
        nodes = list(agent.route.node_sequence)
        target_indices = [index for index, node in enumerate(nodes) if node == target_cell]
        if not target_indices:
            return []
        target_index = min(target_indices, key=lambda index: abs(index - agent.route_index))
        current_indices = [index for index, node in enumerate(nodes) if node == agent.current_cell]
        if current_indices:
            current_index = min(current_indices, key=lambda index: abs(index - target_index))
        else:
            current_index = max(min(agent.route_index, len(nodes) - 1), 0)
        left, right = sorted((current_index, target_index))
        if right - left > 5:
            return []
        return nodes[left : right + 1]

    def _route_corridor(self, cell_ids: list[str]) -> Any | None:
        key = tuple(cell_ids)
        if key in self._visibility_corridors:
            return self._visibility_corridors[key]
        geometries = []
        for cell_id in cell_ids:
            geom = self.topology.cell_geometry(cell_id)
            if geom is not None and not geom.is_empty:
                geometries.append(geom)
        if not geometries:
            return None
        corridor = unary_union(geometries)
        self._visibility_corridors[key] = corridor
        return corridor

    def _accelerated_velocity(self, current: tuple[float, float], target: tuple[float, float]) -> tuple[float, float]:
        dt = max(self.scenario.time_step_s, 1e-9)
        max_delta = float(self.scenario.physics.get("maxAccelerationMps2", 6.0)) * dt
        delta = (target[0] - current[0], target[1] - current[1])
        delta_len = _distance((0.0, 0.0), delta)
        if delta_len > max_delta > 0:
            unit = _unit(delta)
            target = (current[0] + unit[0] * max_delta, current[1] + unit[1] * max_delta)
        inertia = float(self.scenario.physics.get("velocityInertia", 0.16))
        inertia = min(max(inertia, 0.0), 0.85)
        return (current[0] * inertia + target[0] * (1.0 - inertia), current[1] * inertia + target[1] * (1.0 - inertia))

    def _turn_speed_scale(self, current_velocity: tuple[float, float], direction: tuple[float, float]) -> float:
        current_speed = _distance((0.0, 0.0), current_velocity)
        if current_speed < 1e-6 or direction == (0.0, 0.0):
            return 1.0
        current_dir = _unit(current_velocity)
        dot = max(-1.0, min(1.0, current_dir[0] * direction[0] + current_dir[1] * direction[1]))
        if dot < 0.0:
            return 0.35
        if dot < 0.5:
            return 0.62
        if dot < 0.86:
            return 0.85
        return 1.0

    def _steered_direction(self, current_velocity: tuple[float, float], desired: tuple[float, float]) -> tuple[float, float]:
        if desired == (0.0, 0.0):
            return desired
        current_speed = _distance((0.0, 0.0), current_velocity)
        if current_speed < 1e-6:
            return desired
        current = _unit(current_velocity)
        current_angle = math.atan2(current[1], current[0])
        desired_angle = math.atan2(desired[1], desired[0])
        delta = (desired_angle - current_angle + math.pi) % (2 * math.pi) - math.pi
        max_turn = float(self.scenario.physics.get("maxTurnRateRadS", 4.2)) * max(self.scenario.time_step_s, 1e-9)
        max_turn = max(max_turn, 0.14)
        if abs(delta) <= max_turn:
            return desired
        angle = current_angle + (max_turn if delta > 0 else -max_turn)
        return (math.cos(angle), math.sin(angle))

    def _transfer_wall_scale(self, target_cell: str) -> float:
        if target_cell.startswith("VTN_"):
            return 0.18
        cell = self.indoor.cells_by_id.get(target_cell)
        if not cell:
            return 0.45
        if cell.category == "Door":
            return 0.08
        if cell.category in {"Stair", "Ramp"}:
            return 0.12
        return 0.45

    def _close_transfer_entry(
        self,
        agent: AgentState,
        current: tuple[float, float],
        target_cell: str,
        target_geom: Any | None,
        max_distance: float,
    ) -> tuple[float, float] | None:
        if not self._is_transfer_like(target_cell):
            return None
        if target_geom is None or target_geom.is_empty:
            return None
        point = Point(current)
        if target_geom.buffer(1e-6).covers(point):
            return None
        if point.distance(target_geom) > max(max_distance * 1.5, 0.3):
            return None
        current_geom = self.topology.cell_geometry(agent.current_cell)
        candidate = self._transfer_center_waypoint(current_geom, target_geom)
        if candidate == current:
            return None
        if _distance(current, candidate) > max(max_distance * 1.1, 0.2):
            return None
        constrained = self._constrain_step_for_cells([target_cell], current, candidate)
        if target_geom.buffer(1e-6).covers(Point(constrained)):
            return constrained
        if target_geom.buffer(1e-6).covers(Point(candidate)):
            return candidate
        return None

    def _constrain_step_for_cells(
        self,
        cell_ids: list[str],
        current: tuple[float, float],
        proposed: tuple[float, float],
    ) -> tuple[float, float]:
        geometries = []
        for cell_id in cell_ids:
            geom = self.topology.cell_geometry(cell_id)
            if geom is not None and not geom.is_empty:
                geometries.append(geom)
        if not geometries:
            return proposed
        allowed = unary_union(geometries).buffer(1e-6)
        if allowed.covers(LineString([current, proposed])):
            return proposed
        return current

    def _local_waypoint(self, agent: AgentState, target_cell: str) -> tuple[float, float]:
        waypoint = self.topology.node_position(target_cell) or agent.position
        current_geom = self.topology.cell_geometry(agent.current_cell)
        target_geom = self.topology.cell_geometry(target_cell)
        if target_cell.startswith("VTN_"):
            return waypoint
        if self._is_transfer_like(target_cell) and target_geom is not None and not target_geom.is_empty:
            return self._transfer_center_waypoint(current_geom, target_geom)
        if self._is_transfer_like(agent.current_cell) and target_geom is not None and not target_geom.is_empty:
            transfer_exit = self._target_entry_waypoint(current_geom, target_geom)
            if transfer_exit is not None:
                return transfer_exit
        if current_geom is None or current_geom.is_empty or target_geom is None or target_geom.is_empty:
            return waypoint
        try:
            connector = nearest_points(current_geom.boundary, target_geom.boundary)[0]
            if _distance(agent.position, (float(connector.x), float(connector.y))) < _distance(agent.position, waypoint):
                return (float(connector.x), float(connector.y))
        except Exception:
            pass
        return waypoint

    def _motion_target(
        self,
        agent: AgentState,
        target_cell: str,
        waypoint: tuple[float, float],
        arrived: bool,
        holding_transfer_center: bool = False,
    ) -> tuple[float, float]:
        if holding_transfer_center or arrived:
            return waypoint
        if self._is_transfer_like(agent.current_cell):
            return waypoint
        if self._is_transfer_like(target_cell):
            return self._transfer_approach_target(agent, target_cell, waypoint)
        return self._lookahead_target(agent, waypoint)

    def _transfer_center_hold(self, agent: AgentState, target_cell: str, max_distance: float) -> tuple[float, float] | None:
        if not self._is_transfer_like(agent.current_cell) or target_cell.startswith("VTN_"):
            return None
        geom = self.topology.cell_geometry(agent.current_cell)
        if geom is None or geom.is_empty:
            return None
        center = geom.representative_point()
        center_xy = (float(center.x), float(center.y))
        target_geom = self.topology.cell_geometry(target_cell)
        if target_geom is not None and not target_geom.is_empty:
            if not self._is_transfer_like(target_cell):
                clearance = self._post_transfer_clearance(agent.current_cell, target_cell)
                target_waypoint = self._target_entry_waypoint(geom, target_geom, clearance)
                entry = self._shared_entry_point(geom, target_geom)
                if target_waypoint is not None and entry is not None:
                    if not self._waypoint_reachable(agent, target_cell, target_waypoint):
                        if self._waypoint_reachable(agent, target_cell, entry):
                            target_waypoint = entry
                        else:
                            return None
                    if _distance(target_waypoint, entry) <= 1e-6:
                        if _distance(agent.position, target_waypoint) > max(0.04, max_distance * 0.2):
                            return target_waypoint
                        return None
                    exit_direction = _unit((target_waypoint[0] - entry[0], target_waypoint[1] - entry[1]))
                    progress = (agent.position[0] - entry[0]) * exit_direction[0] + (agent.position[1] - entry[1]) * exit_direction[1]
                    if progress < clearance - max(0.035, max_distance * 0.2):
                        return target_waypoint
                    return None
                if target_waypoint is not None and _distance(agent.position, target_waypoint) > max(0.08, max_distance * 0.25):
                    return target_waypoint
                return None
            target_waypoint = self._target_entry_waypoint(geom, target_geom)
            if target_waypoint is None:
                target_waypoint = self._transfer_center_waypoint(geom, target_geom)
            if target_waypoint is not None:
                exit_direction = _unit((target_waypoint[0] - center_xy[0], target_waypoint[1] - center_xy[1]))
                if exit_direction != (0.0, 0.0):
                    progress = (agent.position[0] - center_xy[0]) * exit_direction[0] + (agent.position[1] - center_xy[1]) * exit_direction[1]
                    if progress >= -max(0.03, max_distance * 0.2):
                        return None
        if _distance(agent.position, center_xy) <= max(0.08, max_distance * 0.25):
            return None
        return center_xy

    def _waypoint_reachable(self, agent: AgentState, target_cell: str, waypoint: tuple[float, float]) -> bool:
        allowed = self._movement_geometry(agent, target_cell)
        if allowed is None or allowed.is_empty:
            return True
        return bool(allowed.buffer(1e-6).covers(LineString([agent.position, waypoint])))

    def _transfer_center_waypoint(self, current_geom: Any | None, target_geom: Any) -> tuple[float, float]:
        center = target_geom.representative_point()
        center_xy = (float(center.x), float(center.y))
        entry = self._shared_entry_point(current_geom, target_geom)
        if entry is None:
            return center_xy
        inset = float(self.scenario.physics.get("doorEntryInsetM", 0.035))
        if inset > 0:
            inward = _unit((center_xy[0] - entry[0], center_xy[1] - entry[1]))
            max_inset = _distance(entry, center_xy)
            inset = min(max(inset, 0.0), max_inset)
            entry = (entry[0] + inward[0] * inset, entry[1] + inward[1] * inset)
        center_bias = float(self.scenario.physics.get("doorCenterBias", 0.0))
        center_bias = min(max(center_bias, 0.0), 1.0)
        return (entry[0] * (1.0 - center_bias) + center_xy[0] * center_bias, entry[1] * (1.0 - center_bias) + center_xy[1] * center_bias)

    def _target_entry_waypoint(self, current_geom: Any | None, target_geom: Any, inset_m: float | None = None) -> tuple[float, float] | None:
        entry = self._shared_entry_point(current_geom, target_geom)
        if entry is None:
            return None
        center = target_geom.representative_point()
        inward = _unit((float(center.x) - entry[0], float(center.y) - entry[1]))
        if inward == (0.0, 0.0):
            return entry
        inset = float(inset_m) if inset_m is not None else max(float(self.scenario.physics.get("doorEntryInsetM", 0.035)), 0.035)
        max_inset = max(_distance(entry, (float(center.x), float(center.y))), 0.035)
        inset = min(max(inset, 0.0), max_inset)
        return (entry[0] + inward[0] * inset, entry[1] + inward[1] * inset)

    def _transfer_approach_target(
        self, agent: AgentState, target_cell: str, fallback: tuple[float, float]
    ) -> tuple[float, float]:
        current_geom = self.topology.cell_geometry(agent.current_cell)
        target_geom = self.topology.cell_geometry(target_cell)
        entry = self._shared_entry_point(current_geom, target_geom)
        if entry is None or target_geom is None or target_geom.is_empty:
            return fallback
        center = target_geom.representative_point()
        center_xy = (float(center.x), float(center.y))
        axis = _unit((center_xy[0] - entry[0], center_xy[1] - entry[1]))
        if axis == (0.0, 0.0):
            return fallback
        pre_entry_distance = float(self.scenario.physics.get("doorPreEntryDistanceM", 0.36))
        if self._is_linear_transfer(target_cell):
            pre_entry_distance = max(pre_entry_distance, float(self.scenario.physics.get("linearTransferPreEntryDistanceM", 0.65)))
        pre_entry = (entry[0] - axis[0] * pre_entry_distance, entry[1] - axis[1] * pre_entry_distance)
        if current_geom is not None and not current_geom.is_empty and current_geom.buffer(1e-6).covers(Point(pre_entry)):
            offset = (agent.position[0] - entry[0], agent.position[1] - entry[1])
            progress = offset[0] * axis[0] + offset[1] * axis[1]
            lateral = _distance(offset, (axis[0] * progress, axis[1] * progress))
            far_enough = progress < -pre_entry_distance * 0.75
            off_axis = progress < -pre_entry_distance * 0.5 and lateral > float(self.scenario.physics.get("doorApproachLateralToleranceM", 0.18))
            if far_enough or off_axis:
                return pre_entry
        lookahead = float(self.scenario.physics.get("doorApproachLookaheadM", 0.55))
        if self._is_linear_transfer(target_cell):
            lookahead = max(lookahead, float(self.scenario.physics.get("linearTransferLookaheadM", 0.9)))
        depth = max(_distance(entry, center_xy), lookahead)
        return (entry[0] + axis[0] * depth, entry[1] + axis[1] * depth)

    def _post_transfer_clearance(self, current_cell: str, target_cell: str) -> float:
        physics = self.scenario.physics
        if self._is_linear_transfer(current_cell) or self._is_linear_transfer(target_cell):
            return float(physics.get("linearTransferExitInsetM", 0.45))
        if current_cell.startswith("VTN_") or target_cell.startswith("VTN_"):
            return float(physics.get("virtualBoundaryExitInsetM", 0.28))
        return float(physics.get("doorExitInsetM", 0.32))

    def _transfer_center_direction(self, agent: AgentState, target_cell: str) -> tuple[float, float]:
        if not self._is_transfer_like(target_cell):
            return (0.0, 0.0)
        geom = self.topology.cell_geometry(target_cell)
        if geom is None or geom.is_empty:
            return (0.0, 0.0)
        center = geom.representative_point()
        return _unit((float(center.x) - agent.position[0], float(center.y) - agent.position[1]))

    def _is_linear_transfer(self, cell_id: str) -> bool:
        cell = self.indoor.cells_by_id.get(cell_id)
        return bool(cell and cell.category in {"Stair", "Ramp"})

    def _shared_entry_point(self, current_geom: Any | None, target_geom: Any | None) -> tuple[float, float] | None:
        if current_geom is None or current_geom.is_empty or target_geom is None or target_geom.is_empty:
            return None
        try:
            shared = current_geom.boundary.intersection(target_geom.boundary)
            if not shared.is_empty:
                if shared.geom_type == "LineString":
                    point = shared.interpolate(0.5, normalized=True)
                    return (float(point.x), float(point.y))
                if shared.geom_type == "MultiLineString":
                    longest = max(shared.geoms, key=lambda geom: geom.length)
                    point = longest.interpolate(0.5, normalized=True)
                    return (float(point.x), float(point.y))
                if shared.geom_type == "Point":
                    return (float(shared.x), float(shared.y))
                if hasattr(shared, "geoms"):
                    lines = [geom for geom in shared.geoms if geom.geom_type == "LineString" and geom.length > 0]
                    if lines:
                        longest = max(lines, key=lambda geom: geom.length)
                        point = longest.interpolate(0.5, normalized=True)
                        return (float(point.x), float(point.y))
            left, right = nearest_points(current_geom.boundary, target_geom.boundary)
            if left.distance(right) <= 0.15:
                return ((float(left.x) + float(right.x)) * 0.5, (float(left.y) + float(right.y)) * 0.5)
        except Exception:
            return None
        return None

    def _lookahead_target(self, agent: AgentState, waypoint: tuple[float, float]) -> tuple[float, float]:
        if not agent.route:
            return waypoint
        first_lookahead_index = agent.route_index + 2
        if first_lookahead_index >= len(agent.route.node_sequence):
            return waypoint
        lookahead = None
        max_index = min(agent.route_index + 4, len(agent.route.node_sequence) - 1)
        for candidate_index in range(first_lookahead_index, max_index + 1):
            lookahead_cell = agent.route.node_sequence[candidate_index]
            if self.topology.node_level(lookahead_cell) != agent.level:
                break
            if not self._has_line_of_sight(agent, candidate_index):
                continue
            lookahead = self._local_waypoint(agent, lookahead_cell)
        if not lookahead:
            return waypoint
        distance = _distance(agent.position, waypoint)
        far_blend = float(self.scenario.physics.get("lineOfSightBlend", 0.35))
        near_blend = float(self.scenario.physics.get("nearLineOfSightBlend", 0.55))
        blend = far_blend if distance > 0.6 else near_blend
        blend = min(max(blend, 0.0), 0.9)
        return (waypoint[0] * (1.0 - blend) + lookahead[0] * blend, waypoint[1] * (1.0 - blend) + lookahead[1] * blend)

    def _arrival_radius(self, target_cell: str) -> float:
        if target_cell.startswith("VTN_"):
            return 0.65
        cell = self.indoor.cells_by_id.get(target_cell)
        if not cell:
            return 0.25
        if cell.category == "Door":
            return 0.25
        if cell.navigation_type == "GeneralSpace":
            return 0.95
        if cell.category in {"Stair", "Ramp", "Elevator"}:
            return 1.0
        if cell.category == "Exit":
            return 1.0
        if cell.navigation_type == "TransferSpace":
            return 0.8
        return 0.45

    def _social_repulsion(self, agent: AgentState) -> tuple[float, float]:
        profile = self.scenario.mobility_profiles.get(agent.profile_id)
        personal_radius = float((profile.attributes if profile else {}).get("personalRadiusM", self.scenario.physics.get("personalRadiusM", 0.5)))
        fx, fy = 0.0, 0.0
        for other in self.agents:
            if other is agent or other.status != "active" or other.level != agent.level:
                continue
            dx = agent.position[0] - other.position[0]
            dy = agent.position[1] - other.position[1]
            distance = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            other_profile = self.scenario.mobility_profiles.get(other.profile_id)
            other_personal = float((other_profile.attributes if other_profile else {}).get("personalRadiusM", self.scenario.physics.get("personalRadiusM", 0.5)))
            influence = max(personal_radius + self._body_radius(other), self._body_radius(agent) + other_personal)
            if distance >= influence:
                continue
            strength = (influence - distance) / influence
            fx += (dx / distance) * strength
            fy += (dy / distance) * strength
        return (fx, fy)

    def _wall_repulsion(self, agent: AgentState, target_cell: str | None = None) -> tuple[float, float]:
        if (target_cell or "").startswith("VTN_"):
            return (0.0, 0.0)
        if self._is_linear_transfer(agent.current_cell) or self._is_linear_transfer(target_cell or ""):
            return (0.0, 0.0)
        wall_geom = self._wall_geometries_by_level.get(agent.level or "")
        point = Point(agent.position)
        threshold = float(self.scenario.physics.get("wallRepulsionDistanceM", 0.75))
        if wall_geom is not None and not wall_geom.is_empty:
            distance = point.distance(wall_geom)
            if distance < threshold:
                try:
                    _, nearest = nearest_points(point, wall_geom)
                    away = _unit((point.x - nearest.x, point.y - nearest.y))
                    strength = (threshold - distance) / threshold
                    return (away[0] * strength, away[1] * strength)
                except Exception:
                    pass
        if self._is_transfer_like(target_cell or "") or self._is_transfer_like(agent.current_cell):
            return (0.0, 0.0)
        geom = self.topology.cell_geometry(agent.current_cell)
        if geom is None or geom.is_empty:
            return (0.0, 0.0)
        if not geom.buffer(0.05).covers(point):
            return (0.0, 0.0)
        distance = point.distance(geom.boundary)
        if distance >= threshold:
            return (0.0, 0.0)
        try:
            _, nearest = nearest_points(point, geom.boundary)
        except Exception:
            return (0.0, 0.0)
        away = _unit((point.x - nearest.x, point.y - nearest.y))
        strength = (threshold - distance) / threshold
        return (away[0] * strength, away[1] * strength)

    def _wall_clearance_project(
        self,
        agent: AgentState,
        target_cell: str,
        current: tuple[float, float],
        proposed: tuple[float, float],
    ) -> tuple[float, float]:
        if self._is_transfer_like(agent.current_cell) or self._is_linear_transfer(target_cell):
            return proposed
        wall_geom = self._wall_geometries_by_level.get(agent.level or "")
        if wall_geom is None or wall_geom.is_empty:
            return proposed
        clearance = float(self.scenario.physics.get("wallClearanceM", 0.24))
        if self._is_transfer_like(agent.current_cell) or self._is_transfer_like(target_cell):
            clearance = min(clearance, float(self.scenario.physics.get("transferWallClearanceM", 0.14)))
        if target_cell.startswith("VTN_"):
            clearance = min(clearance, 0.04)
        if clearance <= 0:
            return proposed
        point = Point(proposed)
        distance = point.distance(wall_geom)
        if distance >= clearance:
            return proposed
        try:
            _, nearest = nearest_points(point, wall_geom)
        except Exception:
            return proposed
        away = _unit((point.x - nearest.x, point.y - nearest.y))
        if away == (0.0, 0.0):
            return proposed
        candidate = (proposed[0] + away[0] * (clearance - distance), proposed[1] + away[1] * (clearance - distance))
        allowed = self._movement_geometry(agent, target_cell)
        if allowed is None or allowed.is_empty:
            return proposed
        safe_area = allowed.buffer(1e-6)
        if safe_area.covers(LineString([current, candidate])):
            return candidate
        return proposed

    def _congestion(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for agent in self.agents:
            if agent.status == "active":
                counts[agent.current_cell] = counts.get(agent.current_cell, 0) + 1
        return counts

    def _event(self, event_type: str, agent: AgentState, data: dict[str, Any]) -> None:
        self.events.append(
            {
                "step": self.step_count,
                "timeS": round(self.time_s, 6),
                "eventType": event_type,
                "agentId": agent.agent_id,
                **data,
            }
        )

    def _record_trajectory(self, agent: AgentState) -> None:
        profile = self.scenario.mobility_profiles.get(agent.profile_id)
        next_cell = self._next_route_cell(agent)
        intent = None
        if agent.status == "active" and next_cell:
            waypoint = self._local_waypoint(agent, next_cell)
            hold_center = self._transfer_center_hold(agent, next_cell, self._profile_speed(agent) * self.scenario.time_step_s)
            if hold_center is not None:
                waypoint = hold_center
            intent = self._motion_target(agent, next_cell, waypoint, arrived=False, holding_transfer_center=hold_center is not None)
        self.trajectories.append(
            {
                "step": self.step_count,
                "timeS": round(self.time_s, 6),
                "agentId": agent.agent_id,
                "groupId": agent.group_id,
                "profileId": agent.profile_id,
                "cellSpaceRef": agent.current_cell,
                "levelRef": agent.level,
                "x": round(agent.position[0], 6),
                "y": round(agent.position[1], 6),
                "status": agent.status,
                "routeIndex": agent.route_index,
                "routeNextCell": next_cell,
                "intentX": round(intent[0], 6) if intent else None,
                "intentY": round(intent[1], 6) if intent else None,
                "bodyRadiusM": float((profile.attributes or {}).get("bodyRadiusM", self.scenario.physics.get("bodyRadiusM", 0.25))) if profile else 0.25,
                "personalRadiusM": float((profile.attributes or {}).get("personalRadiusM", self.scenario.physics.get("personalRadiusM", 0.5))) if profile else 0.5,
            }
        )

    def _profile_speed(self, agent: AgentState) -> float:
        profile = self.scenario.mobility_profiles.get(agent.profile_id)
        return float(profile.base_speed_mps if profile else 1.0)

    def _apply_scheduled_events(self) -> None:
        for event in self.scheduled_events:
            event_id = str(event.get("eventId") or f"event_{id(event)}")
            if event_id in self._applied_scheduled_events:
                continue
            if int(event.get("step", -1)) != self.step_count:
                continue
            event_type = str(event.get("eventType") or "")
            if event_type == "beacon_update":
                beacon = self._find_beacon(event.get("beaconRef") or event.get("beaconId"))
                if beacon is not None:
                    _deep_update(beacon, dict(event.get("patch") or {}))
                    self.events.append(
                        {
                            "step": self.step_count,
                            "timeS": round(self.time_s, 6),
                            "eventType": "scheduled_beacon_update",
                            "eventId": event_id,
                            "beaconId": beacon.get("beaconId"),
                        }
                    )
            elif event_type in {"beacon_enable", "beacon_disable"}:
                beacon = self._find_beacon(event.get("beaconRef") or event.get("beaconId"))
                if beacon is not None:
                    beacon["enabled"] = event_type == "beacon_enable"
                    self.events.append(
                        {
                            "step": self.step_count,
                            "timeS": round(self.time_s, 6),
                            "eventType": event_type,
                            "eventId": event_id,
                            "beaconId": beacon.get("beaconId"),
                        }
                    )
            elif event_type == "beacon_add" and event.get("beacon"):
                beacon = copy.deepcopy(event["beacon"])
                self.beacons.append(beacon)
                self.events.append(
                    {
                        "step": self.step_count,
                        "timeS": round(self.time_s, 6),
                        "eventType": "scheduled_beacon_add",
                        "eventId": event_id,
                        "beaconId": beacon.get("beaconId"),
                    }
                )
            self._applied_scheduled_events.add(event_id)

    def _find_beacon(self, beacon_id: Any) -> dict[str, Any] | None:
        if beacon_id is None:
            return None
        for beacon in self.beacons:
            if beacon.get("beaconId") == beacon_id:
                return beacon
        return None


def write_outputs(result: SimulationResult, output_dir: Path) -> Path:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "scenarioId": result.scenario_id,
        "stepsExecuted": result.steps_executed,
        "completed": result.completed,
        "files": {
            "events": "events.ndjson",
            "routes": "routes.json",
            "trajectories": "trajectories.ndjson",
            "metrics": "metrics.json",
            "metricsCsv": "metrics.csv",
        },
    }
    _write_json(output_dir / "run_manifest.json", manifest)
    _write_json(output_dir / "routes.json", result.routes)
    _write_json(output_dir / "metrics.json", result.metrics)
    _write_ndjson(output_dir / "events.ndjson", result.events)
    _write_ndjson(output_dir / "trajectories.ndjson", result.trajectories)
    with (output_dir / "metrics.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["scenarioId", "stepsExecuted", "timeS", "agentCount", "evacuated", "noRoute", "trapped"])
        writer.writeheader()
        writer.writerow(
            {
                "scenarioId": result.metrics.get("scenarioId"),
                "stepsExecuted": result.metrics.get("stepsExecuted"),
                "timeS": result.metrics.get("timeS"),
                "agentCount": result.metrics.get("agentCount"),
                "evacuated": result.metrics.get("evacuated"),
                "noRoute": result.metrics.get("noRoute"),
                "trapped": result.metrics.get("trapped"),
            }
        )
    return output_dir


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=True, indent=2)
        file.write("\n")


def _write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")


def _coords(point: dict[str, Any] | None) -> tuple[float, float] | None:
    coords = (point or {}).get("coordinates") or []
    if len(coords) >= 2:
        return (float(coords[0]), float(coords[1]))
    return None


def _stable_seed(seed: int, scenario_id: str) -> int:
    digest = hashlib.sha256(f"{seed}:{scenario_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _deep_update(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def math_cos(value: float) -> float:
    import math

    return math.cos(value)


def math_sin(value: float) -> float:
    import math

    return math.sin(value)


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return ((right[0] - left[0]) ** 2 + (right[1] - left[1]) ** 2) ** 0.5


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = (vector[0] * vector[0] + vector[1] * vector[1]) ** 0.5
    if length <= 1e-9:
        return (0.0, 0.0)
    return (vector[0] / length, vector[1] / length)

"""Dynamic overlays: hazards and beacon observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Point, shape

from .topology import EvacTopology


@dataclass(slots=True)
class BeaconState:
    cell_risk: dict[str, float] = field(default_factory=dict)
    edge_risk: dict[str, float] = field(default_factory=dict)
    observations: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class HazardState:
    blocked_cells: set[str] = field(default_factory=set)
    blocked_resources: set[str] = field(default_factory=set)
    cell_risk: dict[str, float] = field(default_factory=dict)
    edge_risk: dict[str, float] = field(default_factory=dict)
    speed_factors: dict[str, float] = field(default_factory=dict)
    active_hazards: list[dict[str, Any]] = field(default_factory=list)


def smoothstep(distance_m: float, inner_radius_m: float, outer_radius_m: float) -> float:
    if outer_radius_m <= inner_radius_m:
        return 1.0 if distance_m <= outer_radius_m else 0.0
    if distance_m <= inner_radius_m:
        return 1.0
    if distance_m >= outer_radius_m:
        return 0.0
    t = (distance_m - inner_radius_m) / (outer_radius_m - inner_radius_m)
    return 1.0 - (t * t * (3.0 - 2.0 * t))


class BeaconSimulator:
    def __init__(self, topology: EvacTopology, beacons: list[dict[str, Any]], config: dict[str, Any] | None = None) -> None:
        self.topology = topology
        self.beacons = beacons
        self.config = config or {}

    def state_at(self, step: int, time_s: float) -> BeaconState:
        state = BeaconState()
        by_cell: dict[str, list[float]] = {}
        for beacon in self.beacons:
            if beacon.get("enabled") is False:
                continue
            position = _point(beacon.get("position"))
            if position is None:
                continue
            level = beacon.get("levelRef")
            influence = beacon.get("influence") or {}
            radius = float(influence.get("radiusM", self.config.get("defaultRadiusM", 8.0)))
            inner = float(influence.get("innerRadiusM", 0.0))
            risk = float(((beacon.get("effects") or beacon.get("affects") or {}).get("riskPenalty", 1.0)))
            for cell_id, cell in self.topology.indoor.cells_by_id.items():
                if not cell.is_navigable:
                    continue
                if level and cell.level != level:
                    continue
                cell_pos = cell.representative_point
                if not cell_pos:
                    continue
                distance = position.distance(Point(cell_pos))
                signal = smoothstep(distance, inner, radius)
                if signal <= 0:
                    continue
                value = max(0.0, min(1.0, signal * risk))
                by_cell.setdefault(cell_id, []).append(value)
                state.observations.append(
                    {
                        "step": step,
                        "timeS": round(time_s, 6),
                        "beaconId": beacon.get("beaconId"),
                        "cellSpaceRef": cell_id,
                        "distanceM": round(distance, 6),
                        "risk": round(value, 6),
                    }
                )
        fusion = self.config.get("method") or self.config.get("fusion") or "conservative_min"
        for cell_id, values in by_cell.items():
            if fusion == "weighted_mean":
                fused = sum(values) / len(values)
            else:
                fused = max(values)
            state.cell_risk[cell_id] = max(0.0, min(1.0, fused))
        for source, target, key, data in self.topology.graph.edges(keys=True, data=True):
            risk_cells = [source, target, data.get("transferSpaceRef"), data.get("viaSpaceRef")]
            risk_cells.extend(data.get("viaSpaceRefs") or [])
            risk = max((state.cell_risk.get(cell_id, 0.0) for cell_id in risk_cells if cell_id), default=0.0)
            if risk:
                state.edge_risk[str(data.get("resourceRef") or key)] = risk
        return state


class HazardScheduler:
    def __init__(self, topology: EvacTopology, hazards: list[dict[str, Any]]) -> None:
        self.topology = topology
        self.hazards = hazards

    def state_at(self, step: int, time_s: float) -> HazardState:
        state = HazardState()
        for hazard in self.hazards:
            if not self._is_active(hazard, step, time_s):
                continue
            active = dict(hazard)
            active["activeStep"] = step
            active["activeTimeS"] = time_s
            state.active_hazards.append(active)
            self._apply_hazard(hazard, state, step, time_s)
        return state

    @staticmethod
    def _is_active(hazard: dict[str, Any], step: int, time_s: float) -> bool:
        activation = hazard.get("activation") or {"mode": "initial"}
        mode = activation.get("mode", "initial")
        if mode == "initial":
            return True
        if mode == "scheduled":
            if "startStep" in activation and step >= int(activation["startStep"]):
                return True
            if "startTimeS" in activation and time_s >= float(activation["startTimeS"]):
                return True
            return False
        return False

    def _apply_hazard(self, hazard: dict[str, Any], state: HazardState, step: int, time_s: float) -> None:
        effects = hazard.get("effects") or hazard.get("affects") or {}
        affects = hazard.get("affects") or {}
        severity = float(hazard.get("severity", effects.get("riskPenalty", 1.0)))
        risk = max(0.0, float(effects.get("riskPenalty", severity)))
        speed_factor = max(0.0, min(1.0, float(effects.get("speedFactor", 1.0))))
        block = bool(effects.get("blockRouting", False))

        affected_cells = {str(cell) for cell in affects.get("cellSpaceRefs") or []}
        affected_cells.update(self._cells_from_geometry(hazard, step, time_s))
        for cell_id in affected_cells:
            state.cell_risk[cell_id] = max(state.cell_risk.get(cell_id, 0.0), risk)
            if speed_factor < 1.0:
                state.speed_factors[cell_id] = min(state.speed_factors.get(cell_id, 1.0), speed_factor)
            if block:
                state.blocked_cells.add(cell_id)

        resource_refs = {str(edge) for edge in affects.get("edgeRefs") or []}
        for resource_id, resource in self.topology.resources.items():
            if resource_id in resource_refs or resource.source_ref in resource_refs or set(resource.endpoints) & affected_cells:
                state.edge_risk[resource_id] = max(state.edge_risk.get(resource_id, 0.0), risk)
                if block:
                    state.blocked_resources.add(resource_id)

    def _cells_from_geometry(self, hazard: dict[str, Any], step: int, time_s: float) -> set[str]:
        point = _point(hazard.get("initialPosition"))
        area = _shape(hazard.get("initialArea"))
        growth = hazard.get("growthModel") or {}
        if point is not None:
            radius = float(growth.get("initialRadiusM", hazard.get("radiusM", 0.0)))
            if growth.get("type") == "linear_radius":
                radius += float(growth.get("radiusPerStep", 0.0)) * step
                if growth.get("maxRadiusM") is not None:
                    radius = min(radius, float(growth["maxRadiusM"]))
            area = point.buffer(radius)
        if area is None:
            return set()
        level = hazard.get("levelRef")
        touched = set()
        for cell_id, cell in self.topology.indoor.cells_by_id.items():
            if level and cell.level != level:
                continue
            if cell.geometry is not None and area.intersects(cell.geometry):
                touched.add(cell_id)
        return touched


def _point(geojson: dict[str, Any] | None) -> Point | None:
    if not geojson:
        return None
    try:
        value = shape(geojson)
        if isinstance(value, Point):
            return value
    except Exception:
        return None
    return None


def _shape(geojson: dict[str, Any] | None) -> Any | None:
    if not geojson:
        return None
    try:
        return shape(geojson)
    except Exception:
        return None

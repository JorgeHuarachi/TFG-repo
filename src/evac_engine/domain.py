"""Shared dataclasses for EvacEngine.

The runtime keeps parsed Indoor Data Model and scenario documents immutable-ish:
loaders build indexes and the simulation owns transient state separately.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


JsonDict = dict[str, Any]


@dataclass(slots=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    refs: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass(slots=True)
class CellSpaceRecord:
    id: str
    level: str | None
    navigation_type: str | None
    navigation_class: str | None
    category: str | None
    function: str | None
    locomotion_types: list[str]
    feature: JsonDict
    geometry: Any | None = None
    representative_point: tuple[float, float] | None = None

    @property
    def is_navigable(self) -> bool:
        return self.navigation_class != "NonNavigableSpace" and self.navigation_type in {
            "GeneralSpace",
            "TransferSpace",
        }

    @property
    def is_exit(self) -> bool:
        return self.category == "Exit" or self.function == "AnchorSpace"


@dataclass(slots=True)
class IndoorModelBundle:
    path: Path
    raw: JsonDict
    graph_views: JsonDict
    levels_by_id: dict[str, JsonDict]
    layers_by_id: dict[str, JsonDict]
    cells_by_id: dict[str, CellSpaceRecord]
    boundaries_by_id: dict[str, JsonDict]
    nodes_by_id: dict[str, JsonDict]
    edges_by_id: dict[str, JsonDict]
    cell_ref_index: dict[str, str]
    node_ref_index: dict[str, str]
    node_to_cell: dict[str, str]
    cell_to_node: dict[str, str]
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def id(self) -> str:
        return str(self.raw.get("id") or self.path.stem)

    def resolve_cell_ref(self, value: Any) -> str | None:
        if value is None:
            return None
        ref = str(value)
        if ref in self.cells_by_id:
            return ref
        if ref in self.cell_ref_index:
            return self.cell_ref_index[ref]
        tail = ref.split(":")[-1]
        return tail if tail in self.cells_by_id else None

    def resolve_node_ref(self, value: Any) -> str | None:
        if value is None:
            return None
        ref = str(value)
        if ref in self.nodes_by_id:
            return ref
        if ref in self.node_ref_index:
            return self.node_ref_index[ref]
        tail = ref.split(":")[-1]
        return tail if tail in self.nodes_by_id else None

    def cell_for_node_ref(self, value: Any) -> str | None:
        node_id = self.resolve_node_ref(value)
        if not node_id:
            return None
        return self.node_to_cell.get(node_id)


@dataclass(slots=True)
class MobilityProfile:
    id: str
    locomotion_types: list[str]
    base_speed_mps: float
    can_use_stairs: bool = True
    can_use_ramps: bool = True
    can_use_elevators: bool = True
    attributes: JsonDict = field(default_factory=dict)


@dataclass(slots=True)
class ScenarioDefinition:
    path: Path
    raw: JsonDict
    scenario_id: str
    name: str
    indoor_model_ref: JsonDict
    mobility_profiles: dict[str, MobilityProfile]
    spawns: list[JsonDict]
    groups: list[JsonDict]
    agents: list[JsonDict]
    beacons: list[JsonDict]
    hazards: list[JsonDict]
    routing: JsonDict
    physics: JsonDict
    simulation_config: JsonDict
    outputs: JsonDict
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def time_step_s(self) -> float:
        return float(self.simulation_config.get("timeStepS", 1.0))

    @property
    def max_steps(self) -> int:
        return int(self.simulation_config.get("maxSteps", 1))

    @property
    def random_seed(self) -> int:
        return int(self.simulation_config.get("randomSeed", 0))


@dataclass(slots=True)
class Route:
    origin: str
    destination: str
    node_sequence: list[str]
    arc_sequence: list[str]
    total_cost: float
    cost_policy: str
    algorithm: str
    weight_breakdown: JsonDict
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def reachable(self) -> bool:
        return len(self.node_sequence) >= 1 and self.destination == self.node_sequence[-1]

    def to_dict(self) -> JsonDict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "nodeSequence": list(self.node_sequence),
            "arcSequence": list(self.arc_sequence),
            "totalCost": self.total_cost,
            "costPolicy": self.cost_policy,
            "algorithm": self.algorithm,
            "reachable": self.reachable,
            "weightBreakdown": dict(self.weight_breakdown),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


@dataclass(slots=True)
class WeightedSnapshot:
    step: int
    time_s: float
    graph: Any
    edge_weights: dict[str, JsonDict]
    blocked_cells: set[str] = field(default_factory=set)
    active_hazards: list[JsonDict] = field(default_factory=list)


@dataclass(slots=True)
class AgentState:
    agent_id: str
    group_id: str | None
    profile_id: str
    current_cell: str
    level: str | None
    position: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    status: str = "active"
    route: Route | None = None
    route_index: int = 0
    travel_time_s: float = 0.0
    evacuation_time_s: float | None = None
    no_route_reason: str | None = None
    proximity_slowdown_until_s: float = 0.0
    proximity_slowdown_scale: float = 1.0

    def to_dict(self) -> JsonDict:
        return {
            "agentId": self.agent_id,
            "groupId": self.group_id,
            "profileId": self.profile_id,
            "currentCell": self.current_cell,
            "level": self.level,
            "position": list(self.position),
            "velocity": list(self.velocity),
            "status": self.status,
            "route": self.route.to_dict() if self.route else None,
            "routeIndex": self.route_index,
            "travelTimeS": round(self.travel_time_s, 6),
            "evacuationTimeS": self.evacuation_time_s,
            "noRouteReason": self.no_route_reason,
        }


@dataclass(slots=True)
class SimulationResult:
    scenario_id: str
    steps_executed: int
    completed: bool
    metrics: JsonDict
    routes: list[JsonDict]
    events: list[JsonDict]
    trajectories: list[JsonDict]
    output_dir: Path | None = None

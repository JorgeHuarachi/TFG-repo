"""Application service boundary for UI, CLI and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .domain import IndoorModelBundle, ScenarioDefinition, SimulationResult
from .loaders import IndoorModelLoader, ScenarioModelLoader, load_project
from .routing import RoutingEngine
from .simulation import EvacuationModel
from .topology import EvacTopology


@dataclass(slots=True)
class ApplicationSnapshot:
    indoor_path: str | None
    scenario_path: str | None
    loaded: bool
    running: bool
    step: int
    metrics: dict[str, Any]
    diagnostics: list[dict[str, Any]]


class ApplicationService:
    def __init__(self) -> None:
        self.indoor: IndoorModelBundle | None = None
        self.scenario: ScenarioDefinition | None = None
        self.model: EvacuationModel | None = None
        self.running = False
        self.events: list[dict[str, Any]] = []

    def load(self, indoor_path: str | Path | None, scenario_path: str | Path) -> ApplicationSnapshot:
        self.indoor, self.scenario = load_project(indoor_path, scenario_path)
        self.model = EvacuationModel(self.indoor, self.scenario)
        self.events.append({"eventType": "project_loaded", "scenarioId": self.scenario.scenario_id})
        return self.snapshot()

    def validate(self, indoor_path: str | Path | None, scenario_path: str | Path) -> dict[str, Any]:
        indoor, scenario = load_project(indoor_path, scenario_path)
        topology = EvacTopology.from_indoor_model(indoor)
        return {
            "ok": True,
            "indoorModelId": indoor.id,
            "scenarioId": scenario.scenario_id,
            "diagnostics": [item.to_dict() for item in indoor.diagnostics + scenario.diagnostics + topology.diagnostics],
            "topology": topology.to_summary(),
        }

    def plan_route(
        self,
        origin: str,
        target_refs: list[str] | None = None,
        profile_id: str | None = None,
        origin_position: tuple[float, float] | None = None,
        origin_level: str | None = None,
    ) -> dict[str, Any]:
        self._require_loaded()
        assert self.indoor is not None and self.scenario is not None
        topology = EvacTopology.from_indoor_model(self.indoor)
        engine = RoutingEngine(topology)
        profile = self.scenario.mobility_profiles.get(profile_id or next(iter(self.scenario.mobility_profiles)))
        route = engine.find_route(
            origin=origin,
            target_refs=target_refs or ((self.scenario.routing.get("destination") or {}).get("cellSpaceRefs") or []),
            mobility_profile=profile,
            algorithm=str(self.scenario.routing.get("algorithm", "dijkstra")),
            cost_policy=str(self.scenario.routing.get("costPolicy", "minimum_travel_time")),
            routing_config={**self.scenario.physics, **self.scenario.routing},
            origin_position=origin_position,
            origin_level=origin_level,
        )
        return route.to_dict()

    def step(self) -> ApplicationSnapshot:
        self._require_loaded()
        assert self.model is not None
        self.model.step()
        return self.snapshot()

    def run(self, output_dir: str | Path | None = None) -> SimulationResult:
        self._require_loaded()
        assert self.model is not None
        self.running = True
        try:
            return self.model.run(output_dir)
        finally:
            self.running = False

    def reset(self) -> ApplicationSnapshot:
        self._require_loaded()
        assert self.indoor is not None and self.scenario is not None
        self.model = EvacuationModel(self.indoor, self.scenario)
        self.running = False
        return self.snapshot()

    def apply_runtime_settings(
        self,
        *,
        time_step_s: float | None = None,
        max_steps: int | None = None,
        random_seed: int | None = None,
        output_folder: str | None = None,
        routing_algorithm: str | None = None,
        cost_policy: str | None = None,
        first_group_count: int | None = None,
    ) -> ApplicationSnapshot:
        self._require_loaded()
        assert self.indoor is not None and self.scenario is not None
        if time_step_s is not None:
            self.scenario.simulation_config["timeStepS"] = float(time_step_s)
            self.scenario.raw.setdefault("simulationConfig", {})["timeStepS"] = float(time_step_s)
        if max_steps is not None:
            self.scenario.simulation_config["maxSteps"] = int(max_steps)
            self.scenario.raw.setdefault("simulationConfig", {})["maxSteps"] = int(max_steps)
        if random_seed is not None:
            self.scenario.simulation_config["randomSeed"] = int(random_seed)
            self.scenario.raw.setdefault("simulationConfig", {})["randomSeed"] = int(random_seed)
        if output_folder is not None:
            self.scenario.outputs["outputFolder"] = output_folder
            self.scenario.raw.setdefault("outputs", {})["outputFolder"] = output_folder
        if routing_algorithm is not None:
            self.scenario.routing["algorithm"] = routing_algorithm
            self.scenario.raw.setdefault("routing", {})["algorithm"] = routing_algorithm
        if cost_policy is not None:
            self.scenario.routing["costPolicy"] = cost_policy
            self.scenario.raw.setdefault("routing", {})["costPolicy"] = cost_policy
        if first_group_count is not None and self.scenario.groups:
            self.scenario.groups[0]["count"] = int(first_group_count)
            self.scenario.raw.setdefault("population", {}).setdefault("agentGroups", [])[0]["count"] = int(first_group_count)
        self.model = EvacuationModel(self.indoor, self.scenario)
        self.events.append({"eventType": "runtime_settings_applied", "scenarioId": self.scenario.scenario_id})
        return self.snapshot()

    def snapshot(self) -> ApplicationSnapshot:
        diagnostics = []
        if self.indoor:
            diagnostics.extend(item.to_dict() for item in self.indoor.diagnostics)
        if self.scenario:
            diagnostics.extend(item.to_dict() for item in self.scenario.diagnostics)
        metrics = self.model.metrics() if self.model else {}
        return ApplicationSnapshot(
            indoor_path=str(self.indoor.path) if self.indoor else None,
            scenario_path=str(self.scenario.path) if self.scenario else None,
            loaded=bool(self.indoor and self.scenario and self.model),
            running=self.running,
            step=self.model.step_count if self.model else 0,
            metrics=metrics,
            diagnostics=diagnostics,
        )

    def _require_loaded(self) -> None:
        if not self.indoor or not self.scenario or not self.model:
            raise RuntimeError("No indoor/scenario project is loaded")


def validate_files(indoor_path: str | Path | None, scenario_path: str | Path) -> dict[str, Any]:
    return ApplicationService().validate(indoor_path, scenario_path)


def load_indoor_only(indoor_path: str | Path) -> IndoorModelBundle:
    return IndoorModelLoader().load(indoor_path)


def load_scenario_only(scenario_path: str | Path) -> ScenarioDefinition:
    return ScenarioModelLoader().load(scenario_path)

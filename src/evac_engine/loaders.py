"""Loaders and validators for indoor_model.json and scenario_model.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from shapely.geometry import shape

from src.indoor_data_model import derive_graph_views

from .domain import CellSpaceRecord, Diagnostic, IndoorModelBundle, MobilityProfile, ScenarioDefinition


REPO_ROOT = Path(__file__).resolve().parents[2]
INDOOR_SCHEMA = REPO_ROOT / "schemas" / "indoor" / "indoor_model.schema.json"
SCENARIO_SCHEMA = REPO_ROOT / "schemas" / "indoor" / "scenario_model.schema.json"


class LoaderError(ValueError):
    """Raised when JSON or cross-reference validation fails."""


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_schema(path: Path) -> dict[str, Any]:
    return _read_json(path)


def _validate_schema(instance: dict[str, Any], schema_path: Path, label: str) -> None:
    schema = _load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
    if not errors:
        return
    details = []
    for error in errors[:8]:
        path = "/".join(str(item) for item in error.path) or "<root>"
        details.append(f"{path}: {error.message}")
    suffix = "\n".join(details)
    raise LoaderError(f"{label} does not validate against {schema_path}: \n{suffix}")


def _qualified_ref(layer_id: str | None, container_id: str | None, object_id: str | None) -> str | None:
    if not layer_id or not container_id or not object_id:
        return None
    return f"{layer_id}:{container_id}:{object_id}"


def _point_tuple(geom: Any | None) -> tuple[float, float] | None:
    if geom is None or getattr(geom, "is_empty", True):
        return None
    try:
        point = geom.representative_point()
        return (float(point.x), float(point.y))
    except Exception:
        return None


def _shape_from_cell(cell: dict[str, Any]) -> Any | None:
    geom = ((cell.get("cellSpaceGeom") or {}).get("geometry2D") or {})
    if not geom:
        return None
    try:
        return shape(geom)
    except Exception:
        return None


class IndoorModelLoader:
    """Validated loader for Indoor Data Model documents."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path = schema_path or INDOOR_SCHEMA

    def load(self, path: str | Path) -> IndoorModelBundle:
        model_path = Path(path).resolve()
        raw = _read_json(model_path)
        _validate_schema(raw, self.schema_path, "indoor_model")
        if raw.get("featureType") != "IndoorFeatures":
            raise LoaderError("indoor_model.featureType must be IndoorFeatures")
        unit = ((raw.get("crs") or {}).get("unit") or "").lower()
        if unit and unit != "meters":
            raise LoaderError(f"EvacEngine expects metric indoor models, got unit={unit!r}")

        levels_by_id = {level["id"]: level for level in raw.get("levels", [])}
        layers_by_id: dict[str, dict[str, Any]] = {}
        cells_by_id: dict[str, CellSpaceRecord] = {}
        boundaries_by_id: dict[str, dict[str, Any]] = {}
        nodes_by_id: dict[str, dict[str, Any]] = {}
        edges_by_id: dict[str, dict[str, Any]] = {}
        cell_ref_index: dict[str, str] = {}
        node_ref_index: dict[str, str] = {}
        node_to_cell: dict[str, str] = {}
        cell_to_node: dict[str, str] = {}
        diagnostics: list[Diagnostic] = []

        for layer in raw.get("layers", []):
            layer_id = layer.get("id")
            if layer_id:
                layers_by_id[layer_id] = layer
            primal = layer.get("primalSpace") or {}
            dual = layer.get("dualSpace") or {}
            primal_id = primal.get("id")
            dual_id = dual.get("id")

            for cell in primal.get("cellSpaceMember", []):
                cell_id = cell.get("id")
                geom = _shape_from_cell(cell)
                record = CellSpaceRecord(
                    id=cell_id,
                    level=cell.get("level"),
                    navigation_type=cell.get("navigationType"),
                    navigation_class=cell.get("navigationClass"),
                    category=cell.get("category"),
                    function=cell.get("function"),
                    locomotion_types=list(cell.get("locomotionTypes") or ["Walking", "Rolling"]),
                    feature=cell,
                    geometry=geom,
                    representative_point=_point_tuple(geom),
                )
                cells_by_id[cell_id] = record
                for ref in (cell_id, _qualified_ref(layer_id, primal_id, cell_id)):
                    if ref:
                        cell_ref_index[ref] = cell_id

            for boundary in primal.get("cellBoundaryMember", []):
                boundary_id = boundary.get("id")
                boundaries_by_id[boundary_id] = boundary

            for node in dual.get("nodeMember", []):
                node_id = node.get("id")
                nodes_by_id[node_id] = node
                for ref in (node_id, _qualified_ref(layer_id, dual_id, node_id)):
                    if ref:
                        node_ref_index[ref] = node_id

            for node in dual.get("nodeMember", []):
                node_id = node.get("id")
                cell_ref = self._resolve_cell_from_index(cell_ref_index, node.get("duality"))
                if cell_ref:
                    node_to_cell[node_id] = cell_ref
                    cell_to_node[cell_ref] = node_id

            for edge in dual.get("edgeMember", []):
                edge_id = edge.get("id")
                edges_by_id[edge_id] = edge

        graph_views = derive_graph_views(raw)
        for item in graph_views.get("vertical_connectivity", {}).get("diagnostics", []):
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=str(item.get("code") or "GRAPH_VIEW_DIAGNOSTIC"),
                    message="Graph view reported unresolved vertical connectivity.",
                    refs=[str(ref) for ref in item.get("references", [])],
                )
            )

        return IndoorModelBundle(
            path=model_path,
            raw=raw,
            graph_views=graph_views,
            levels_by_id=levels_by_id,
            layers_by_id=layers_by_id,
            cells_by_id=cells_by_id,
            boundaries_by_id=boundaries_by_id,
            nodes_by_id=nodes_by_id,
            edges_by_id=edges_by_id,
            cell_ref_index=cell_ref_index,
            node_ref_index=node_ref_index,
            node_to_cell=node_to_cell,
            cell_to_node=cell_to_node,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _resolve_cell_from_index(index: dict[str, str], value: Any) -> str | None:
        if value is None:
            return None
        ref = str(value)
        if ref in index:
            return index[ref]
        tail = ref.split(":")[-1]
        return index.get(tail)


class ScenarioModelLoader:
    """Validated loader for scenario_model.json overlays."""

    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path = schema_path or SCENARIO_SCHEMA

    def load(self, path: str | Path, indoor: IndoorModelBundle | None = None) -> ScenarioDefinition:
        scenario_path = Path(path).resolve()
        raw = _read_json(scenario_path)
        _validate_schema(raw, self.schema_path, "scenario_model")
        population = raw.get("population") or {}
        profiles = {}
        for item in population.get("mobilityProfiles", []):
            attributes = dict(item.get("attributes") or {})
            for copied_key in ("bodyRadiusM", "personalRadiusM"):
                if copied_key in item:
                    attributes[copied_key] = item[copied_key]
            profiles[item["profileId"]] = MobilityProfile(
                id=item["profileId"],
                locomotion_types=list(item.get("locomotionTypes") or ["Walking"]),
                base_speed_mps=float(item.get("baseSpeedMps", 1.2)),
                can_use_stairs=bool(item.get("canUseStairs", True)),
                can_use_ramps=bool(item.get("canUseRamps", True)),
                can_use_elevators=bool(item.get("canUseElevators", True)),
                attributes=attributes,
            )
        beacon_system = raw.get("beaconSystem") or {}
        hazards = raw.get("hazards") or {}
        legacy_beacons = raw.get("beacons") if isinstance(raw.get("beacons"), list) else []
        legacy_hazards = raw.get("hazards") if isinstance(raw.get("hazards"), list) else []
        scenario = ScenarioDefinition(
            path=scenario_path,
            raw=raw,
            scenario_id=str(raw.get("scenarioId")),
            name=str(raw.get("scenarioName") or (raw.get("metadata") or {}).get("name") or raw.get("scenarioId")),
            indoor_model_ref=dict(raw.get("indoorModelRef") or {}),
            mobility_profiles=profiles,
            spawns=list(population.get("agentSpawns") or []),
            groups=list(population.get("agentGroups") or []),
            agents=list(population.get("agents") or []),
            beacons=list(beacon_system.get("beacons") if beacon_system.get("beacons") is not None else legacy_beacons),
            hazards=list(hazards.get("sources") if isinstance(hazards, dict) and hazards.get("sources") is not None else legacy_hazards),
            routing=dict(raw.get("routing") or {}),
            physics=dict(raw.get("physics") or {}),
            simulation_config=dict(raw.get("simulationConfig") or {}),
            outputs=dict(raw.get("outputs") or {}),
        )
        diagnostics = self._semantic_validate(scenario, indoor)
        blocking = [item for item in diagnostics if item.severity == "error"]
        scenario.diagnostics.extend(diagnostics)
        if blocking:
            details = "\n".join(f"{item.code}: {item.message}" for item in blocking[:8])
            raise LoaderError(f"scenario_model semantic validation failed:\n{details}")
        return scenario

    def resolve_indoor_path(self, scenario: ScenarioDefinition) -> Path:
        path_value = scenario.indoor_model_ref.get("path")
        if not path_value:
            raise LoaderError("indoorModelRef.path is required")
        indoor_path = Path(path_value)
        if not indoor_path.is_absolute():
            indoor_path = scenario.path.parent / indoor_path
        return indoor_path.resolve()

    @staticmethod
    def _semantic_validate(scenario: ScenarioDefinition, indoor: IndoorModelBundle | None) -> list[Diagnostic]:
        diagnostics: list[Diagnostic] = []
        spawn_ids = {spawn.get("spawnId") for spawn in scenario.spawns}
        for group in scenario.groups:
            profile_ref = group.get("mobilityProfileRef")
            if profile_ref not in scenario.mobility_profiles:
                diagnostics.append(Diagnostic("error", "UNKNOWN_MOBILITY_PROFILE", f"Unknown profile {profile_ref}", [str(profile_ref)]))
            spawn_ref = group.get("spawnRef")
            if spawn_ref not in spawn_ids:
                diagnostics.append(Diagnostic("error", "UNKNOWN_SPAWN", f"Unknown spawn {spawn_ref}", [str(spawn_ref)]))
        if indoor is None:
            return diagnostics

        for spawn in scenario.spawns:
            cell_ref = indoor.resolve_cell_ref(spawn.get("cellSpaceRef"))
            node_cell = indoor.cell_for_node_ref(spawn.get("nodeRef")) if spawn.get("nodeRef") else None
            if not cell_ref:
                diagnostics.append(Diagnostic("error", "UNKNOWN_SPAWN_CELL", f"Unknown spawn cell {spawn.get('cellSpaceRef')}", [str(spawn.get("cellSpaceRef"))]))
            if spawn.get("nodeRef") and not node_cell:
                diagnostics.append(Diagnostic("error", "UNKNOWN_SPAWN_NODE", f"Unknown spawn node {spawn.get('nodeRef')}", [str(spawn.get("nodeRef"))]))
            if cell_ref and node_cell and cell_ref != node_cell:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "SPAWN_NODE_CELL_MISMATCH",
                        f"Spawn {spawn.get('spawnId')} node duality points to {node_cell}, not {cell_ref}",
                        [str(spawn.get("spawnId"))],
                    )
                )
        target_refs = ((scenario.routing.get("destination") or {}).get("cellSpaceRefs") or [])
        for target_ref in target_refs:
            if not indoor.resolve_cell_ref(target_ref):
                diagnostics.append(Diagnostic("error", "UNKNOWN_TARGET_CELL", f"Unknown target cell {target_ref}", [str(target_ref)]))
        for beacon in scenario.beacons:
            level_ref = beacon.get("levelRef")
            if level_ref and level_ref not in indoor.levels_by_id:
                diagnostics.append(Diagnostic("error", "UNKNOWN_BEACON_LEVEL", f"Unknown beacon level {level_ref}", [str(level_ref)]))
        for hazard in scenario.hazards:
            affects = hazard.get("affects") or {}
            for cell_ref in affects.get("cellSpaceRefs") or []:
                if not indoor.resolve_cell_ref(cell_ref):
                    diagnostics.append(Diagnostic("error", "UNKNOWN_HAZARD_CELL", f"Unknown hazard cell {cell_ref}", [str(cell_ref)]))
        return diagnostics


def load_project(
    indoor_path: str | Path | None,
    scenario_path: str | Path,
    indoor_loader: IndoorModelLoader | None = None,
    scenario_loader: ScenarioModelLoader | None = None,
) -> tuple[IndoorModelBundle, ScenarioDefinition]:
    scenario_loader = scenario_loader or ScenarioModelLoader()
    indoor_loader = indoor_loader or IndoorModelLoader()
    scenario = scenario_loader.load(scenario_path)
    resolved_indoor = Path(indoor_path).resolve() if indoor_path else scenario_loader.resolve_indoor_path(scenario)
    indoor = indoor_loader.load(resolved_indoor)
    scenario = scenario_loader.load(scenario_path, indoor=indoor)
    if scenario.indoor_model_ref.get("indoorModelId") and scenario.indoor_model_ref["indoorModelId"] != indoor.id:
        raise LoaderError(
            f"scenario indoorModelId={scenario.indoor_model_ref['indoorModelId']} does not match indoor model id={indoor.id}"
        )
    return indoor, scenario

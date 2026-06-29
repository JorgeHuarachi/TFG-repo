"""Convenience helpers for opening EvacEngine from a user model workspace."""

from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Any

from .loaders import IndoorModelLoader
from .routing import RoutingEngine
from .topology import EvacTopology


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIRNAME = "models"
TEMPLATE_SCENARIO = PROJECT_ROOT / "examples" / "indoor_data_model" / "scenario_single_floor.json"


def ensure_model_baseline_scenario(
    model_name: str,
    *,
    scenario_name: str = "baseline",
    base_dir: Path = PROJECT_ROOT,
    overwrite: bool = False,
) -> Path:
    """Return a usable scenario for ``models/<model_name>``, creating it when needed."""

    model_dir = _resolve_model_dir(model_name, base_dir)
    indoor_path = model_dir / "spatial" / "indoor_model.json"
    if not indoor_path.exists():
        raise FileNotFoundError(f"No indoor_model.json found at {indoor_path}")
    scenario_path = model_dir / "evacuation" / "scenarios" / f"{_slugify(scenario_name)}.json"
    return ensure_baseline_for_indoor(indoor_path, scenario_path=scenario_path, base_dir=base_dir, overwrite=overwrite)


def ensure_baseline_for_indoor(
    indoor_path: str | Path,
    *,
    scenario_path: str | Path | None = None,
    scenario_name: str = "baseline",
    base_dir: Path = PROJECT_ROOT,
    overwrite: bool = False,
) -> Path:
    """Create or return a baseline scenario associated with an IndoorModel."""

    base_dir = base_dir.resolve()
    indoor = _resolve_repo_path(indoor_path, base_dir)
    if not indoor.exists():
        raise FileNotFoundError(indoor)
    if scenario_path is None:
        scenario_path = _default_scenario_path_for_indoor(indoor, scenario_name, base_dir)
    scenario = _resolve_repo_path(scenario_path, base_dir)
    if scenario.exists() and not overwrite:
        return scenario
    scenario.parent.mkdir(parents=True, exist_ok=True)
    document = build_baseline_scenario(indoor, scenario, base_dir)
    with scenario.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    return scenario


def build_baseline_scenario(indoor_path: Path, scenario_path: Path, base_dir: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Build a valid, editable EvacEngine scenario from an IndoorModel."""

    indoor = IndoorModelLoader().load(indoor_path)
    topology = EvacTopology.from_indoor_model(indoor)
    cells = list(indoor.cells_by_id.values())
    exits = sorted((cell for cell in cells if cell.is_exit and cell.is_navigable), key=lambda cell: cell.id)
    spawn_cells = sorted((cell for cell in cells if _is_spawnable(cell)), key=lambda cell: cell.id)
    if not spawn_cells:
        spawn_cells = sorted((cell for cell in cells if cell.is_navigable), key=lambda cell: cell.id)
    if not spawn_cells:
        raise ValueError(f"{indoor_path} has no navigable cell suitable for an initial scenario.")

    destination_cells = [cell.id for cell in exits]
    spawn = _select_reachable_spawn(spawn_cells, topology, destination_cells)
    spawn_point = spawn.representative_point or (0.0, 0.0)
    if not destination_cells:
        destination_cells = [cell.id for cell in cells if cell.is_navigable and cell.id != spawn.id][:1]
    slug = _scenario_slug_from_path(scenario_path)
    model_name = _model_name_for_path(indoor_path, base_dir) or _slugify(indoor_path.stem)
    template = _load_template()
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    scenario = copy.deepcopy(template)
    scenario["scenarioId"] = f"SCENARIO_{_slugify(model_name).upper()}_{_slugify(slug).upper()}"
    scenario["scenarioName"] = f"{model_name}_{slug}"
    scenario["metadata"] = {
        "name": scenario["scenarioName"],
        "description": "Baseline editable generado desde un indoor_model.json para abrir EvacEngine.",
        "createdAt": now,
        "modifiedAt": now,
        "generator": "evac_engine.model_workspace.ensure_baseline_for_indoor",
    }
    scenario["indoorModelRef"] = {
        "path": os.path.relpath(indoor_path, scenario_path.parent).replace("\\", "/"),
        "schemaRef": os.path.relpath(PROJECT_ROOT / "schemas" / "indoor" / "indoor_model.schema.json", scenario_path.parent).replace("\\", "/"),
    }
    scenario["population"]["agentGroups"] = [
        {
            "groupId": "AG_BASELINE_001",
            "count": 8,
            "mobilityProfileRef": "MP_WALKING",
            "spawnRef": "SPAWN_BASELINE_001",
            "distribution": "random_within_space",
        }
    ]
    scenario["population"]["agentSpawns"] = [
        {
            "spawnId": "SPAWN_BASELINE_001",
            "levelRef": spawn.level or "LEVEL_00",
            "cellSpaceRef": spawn.id,
            "position": {"type": "Point", "coordinates": [round(spawn_point[0], 3), round(spawn_point[1], 3)]},
            "capacity": 50,
            "description": "Spawn inicial editable creado automaticamente.",
        }
    ]
    scenario["population"]["agents"] = []
    scenario["beaconSystem"] = {
        "enabled": False,
        "fusion": {"method": "conservative_min", "defaultRadiusM": 6.0},
        "beacons": [],
    }
    scenario["hazards"] = {"enabled": False, "sources": []}
    scenario["scheduledEvents"] = []
    scenario["routing"]["algorithm"] = "astar"
    scenario["routing"]["costPolicy"] = "minimum_travel_time"
    scenario["routing"]["destination"] = {"mode": "explicit_cells", "cellSpaceRefs": destination_cells}
    scenario["routing"]["deriveConnectivityFromEdges"] = True
    scenario["routing"]["useDynamicWeights"] = True
    scenario["routing"]["useBeaconRisk"] = False
    scenario["routing"]["useHazardRisk"] = True
    scenario["routing"]["useCongestion"] = True
    scenario["routing"]["replanPolicy"] = "on_blocked_or_interval"
    scenario["routing"]["replanIntervalSteps"] = 2
    scenario["routing"]["noRouteRetryIntervalSteps"] = 2
    scenario["simulationConfig"] = {"timeStepS": 0.5, "maxSteps": 220, "randomSeed": 22, "enabledOverlays": ["population"]}
    scenario["outputs"] = {
        "outputFolder": _default_output_folder(model_name, slug, indoor_path, base_dir),
        "saveRoutes": True,
        "saveMetrics": True,
        "saveTimeSeries": False,
        "saveEvents": True,
        "saveTrajectories": True,
    }
    return scenario


def _default_scenario_path_for_indoor(indoor_path: Path, scenario_name: str, base_dir: Path) -> Path:
    model_name = _model_name_for_path(indoor_path, base_dir)
    slug = _slugify(scenario_name) or "baseline"
    if model_name:
        return base_dir / MODELS_DIRNAME / model_name / "evacuation" / "scenarios" / f"{slug}.json"
    return base_dir / "outputs" / "workbench_scenarios" / f"{_slugify(indoor_path.stem)}_{slug}.json"


def _default_output_folder(model_name: str, scenario_slug: str, indoor_path: Path, base_dir: Path) -> str:
    if _model_name_for_path(indoor_path, base_dir):
        return f"{MODELS_DIRNAME}/{model_name}/outputs/{scenario_slug}"
    return f"outputs/{model_name}/{scenario_slug}"


def _resolve_model_dir(model_name: str, base_dir: Path) -> Path:
    candidate = Path(model_name)
    if candidate.is_absolute() or len(candidate.parts) > 1:
        model_dir = _resolve_repo_path(candidate, base_dir)
    else:
        model_dir = base_dir / MODELS_DIRNAME / model_name
    if not model_dir.exists():
        raise FileNotFoundError(f"Model workspace not found: {model_dir}")
    return model_dir


def _resolve_repo_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    resolved = path.resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"Path is outside the repository: {value}") from exc
    return resolved


def _model_name_for_path(path: Path, base_dir: Path) -> str | None:
    try:
        relative = path.resolve().relative_to((base_dir / MODELS_DIRNAME).resolve())
    except ValueError:
        return None
    return relative.parts[0] if relative.parts else None


def _scenario_slug_from_path(path: Path) -> str:
    return _slugify(path.stem) or "baseline"


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "model"


def _load_template() -> dict[str, Any]:
    with TEMPLATE_SCENARIO.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _is_spawnable(cell: Any) -> bool:
    return bool(cell.is_navigable and cell.navigation_type == "GeneralSpace" and cell.category not in {"Door", "Exit"})


def _select_reachable_spawn(spawn_cells: list[Any], topology: EvacTopology, destination_cells: list[str]) -> Any:
    candidates: list[Any] = []
    if destination_cells:
        routing = RoutingEngine(topology)
        for cell in spawn_cells:
            route = routing.find_route(
                cell.id,
                destination_cells,
                algorithm="astar",
                origin_position=cell.representative_point,
                origin_level=cell.level,
            )
            if route.reachable:
                candidates.append(cell)
    if not candidates:
        candidates = [cell for cell in spawn_cells if cell.id in topology.graph or topology.transfer_nodes_for_space(cell.id)]
    if not candidates:
        return spawn_cells[0]
    return max(candidates, key=lambda cell: (_cell_area(cell), cell.id))


def _cell_area(cell: Any) -> float:
    geometry = getattr(cell, "geometry", None)
    if geometry is None or getattr(geometry, "is_empty", True):
        return 0.0
    return float(getattr(geometry, "area", 0.0) or 0.0)

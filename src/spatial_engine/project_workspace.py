"""Model workspace helpers for SpatialEngine and EvacEngine.

The canonical source examples stay in ``examples/indoor_data_model``. User work
lives under ``models/<model_name>`` so the spatial model, evacuation scenarios,
experiments and outputs for one building stay close together.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples" / "indoor_data_model"
MODELS_DIR = REPO_ROOT / "models"
OUTPUTS_DIR = REPO_ROOT / "outputs"


def repo_relative(path: Path, base_dir: Path = REPO_ROOT) -> str:
    try:
        return path.resolve().relative_to(base_dir.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def resolve_repo_path(value: str | Path, base_dir: Path = REPO_ROOT) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    resolved = path.resolve()
    try:
        resolved.relative_to(base_dir.resolve())
    except ValueError as exc:
        raise ValueError(f"Path is outside the repository: {value}") from exc
    return resolved


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object.")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=True, indent=2)
        file.write("\n")


def discover_indoor_models(base_dir: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """Return IndoorModel candidates from user models, examples and backups."""

    base_dir = base_dir.resolve()
    roots = [
        ("models", base_dir / "models", "**/spatial/*indoor_model*.json"),
        ("examples", base_dir / "examples" / "indoor_data_model", "*indoor_model*.json"),
        ("outputs_backup", base_dir / "outputs" / "indoor_models", "*.json"),
    ]
    candidates: list[dict[str, Any]] = []
    seen: set[Path] = set()

    for source, root, pattern in roots:
        if not root.exists():
            continue
        for path in sorted(root.glob(pattern)):
            resolved = path.resolve()
            if resolved in seen or not _looks_like_indoor_model(path):
                continue
            seen.add(resolved)
            model = _safe_load(path)
            summary = _model_summary(model)
            candidates.append(
                {
                    "label": _model_label(path, model),
                    "path": repo_relative(path, base_dir),
                    "source": source,
                    "project": _project_name_for_model(path, base_dir),
                    "scenarioCount": len(related_scenarios_for_model(path, base_dir)),
                    **summary,
                }
            )
    return candidates


def related_scenarios_for_model(model_path: Path, base_dir: Path = REPO_ROOT) -> list[dict[str, str]]:
    """Find scenario overlays that reference a given IndoorModel."""

    base_dir = base_dir.resolve()
    model_path = resolve_repo_path(model_path, base_dir)
    search_roots = [
        base_dir / "models",
        base_dir / "examples" / "indoor_data_model",
    ]
    related: list[dict[str, str]] = []
    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists():
            continue
        scenario_candidates: list[Path]
        if root.name == "models":
            scenario_candidates = sorted(root.glob("*/evacuation/scenarios/*.json"))
        else:
            scenario_candidates = sorted(root.glob("**/*.json"))
        for scenario_path in scenario_candidates:
            resolved = scenario_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if _scenario_references_model(scenario_path, model_path, base_dir):
                related.append(
                    {
                        "label": _scenario_label(scenario_path),
                        "path": repo_relative(scenario_path, base_dir),
                    }
                )
    return related


def create_workspace(
    name: str,
    indoor_model: Path,
    scenarios: list[Path] | None = None,
    *,
    base_dir: Path = REPO_ROOT,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create ``models/<name>`` with one indoor model and scenario overlays."""

    base_dir = base_dir.resolve()
    slug = slugify(name)
    if not slug:
        raise ValueError("Workspace name cannot be empty.")
    source_model = resolve_repo_path(indoor_model, base_dir)
    if not source_model.exists():
        raise FileNotFoundError(source_model)
    source_scenarios = []
    for scenario_path in scenarios or []:
        source_scenario = resolve_repo_path(scenario_path, base_dir)
        if not source_scenario.exists():
            raise FileNotFoundError(source_scenario)
        source_scenarios.append(source_scenario)

    workspace = base_dir / "models" / slug
    spatial_dir = workspace / "spatial"
    scenario_dir = workspace / "evacuation" / "scenarios"
    experiment_dir = workspace / "evacuation" / "experiments"
    outputs_dir = workspace / "outputs"
    model_target = spatial_dir / "indoor_model.json"
    spatial_dir.mkdir(parents=True, exist_ok=True)
    scenario_dir.mkdir(parents=True, exist_ok=True)
    experiment_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    if model_target.exists() and not overwrite:
        raise FileExistsError(f"{model_target} already exists. Use --overwrite to replace it.")
    shutil.copy2(source_model, model_target)

    copied_scenarios = []
    for source_scenario in source_scenarios:
        scenario_data = load_json(source_scenario)
        scenario_name = slugify(source_scenario.stem.replace("scenario_", "")) or source_scenario.stem
        target = scenario_dir / f"{scenario_name}.json"
        if target.exists() and not overwrite:
            raise FileExistsError(f"{target} already exists. Use --overwrite to replace it.")
        _rewrite_scenario_for_workspace(scenario_data, slug, scenario_name)
        write_json(target, scenario_data)
        copied_scenarios.append(repo_relative(target, base_dir))

    readme = workspace / "README.md"
    readme.write_text(_workspace_readme(slug, source_model, copied_scenarios, base_dir), encoding="utf-8")

    return {
        "workspace": repo_relative(workspace, base_dir),
        "indoorModel": repo_relative(model_target, base_dir),
        "scenarios": copied_scenarios,
    }


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned


def _safe_load(path: Path) -> dict[str, Any]:
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def _looks_like_indoor_model(path: Path) -> bool:
    data = _safe_load(path)
    return data.get("featureType") == "IndoorFeatures" or isinstance(data.get("layers"), list)


def _model_label(path: Path, model: dict[str, Any]) -> str:
    metadata = model.get("metadata") if isinstance(model.get("metadata"), dict) else {}
    name = metadata.get("name") or model.get("id") or path.stem
    return str(name)


def _model_summary(model: dict[str, Any]) -> dict[str, Any]:
    levels = model.get("levels") if isinstance(model.get("levels"), list) else []
    layers = model.get("layers") if isinstance(model.get("layers"), list) else []
    cell_count = 0
    general_space_count = 0
    points: list[tuple[float, float]] = []

    for layer in layers:
        if not isinstance(layer, dict):
            continue
        primal_space = layer.get("primalSpace") if isinstance(layer.get("primalSpace"), dict) else {}
        cells = primal_space.get("cellSpaceMember") or primal_space.get("cellSpaceMembers") or []
        if not isinstance(cells, list):
            continue
        cell_count += len(cells)
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            if cell.get("category") == "GeneralSpace":
                general_space_count += 1
            geometry = cell.get("cellSpaceGeom") if isinstance(cell.get("cellSpaceGeom"), dict) else {}
            geometry_2d = geometry.get("geometry2D") if isinstance(geometry.get("geometry2D"), dict) else {}
            _collect_xy(geometry_2d.get("coordinates"), points)

    extent = ""
    if points:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        extent = f"{max(xs) - min(xs):.1f}x{max(ys) - min(ys):.1f}m"

    return {
        "levelCount": len(levels),
        "cellCount": cell_count,
        "generalSpaceCount": general_space_count,
        "extentM": extent,
    }


def _collect_xy(value: Any, points: list[tuple[float, float]]) -> None:
    if not isinstance(value, list):
        return
    if len(value) >= 2 and isinstance(value[0], (int, float)) and isinstance(value[1], (int, float)):
        points.append((float(value[0]), float(value[1])))
        return
    for item in value:
        _collect_xy(item, points)


def _project_name_for_model(path: Path, base_dir: Path) -> str:
    for root_name in ("models",):
        try:
            relative = path.resolve().relative_to((base_dir / root_name).resolve())
        except ValueError:
            continue
        return relative.parts[0] if relative.parts else ""
    return ""


def _scenario_label(path: Path) -> str:
    data = _safe_load(path)
    return str(data.get("scenarioName") or data.get("scenarioId") or path.stem)


def _scenario_references_model(scenario_path: Path, model_path: Path, base_dir: Path) -> bool:
    data = _safe_load(scenario_path)
    ref = data.get("indoorModelRef") if isinstance(data.get("indoorModelRef"), dict) else {}
    ref_path = ref.get("path")
    if not ref_path:
        return False
    candidate = Path(str(ref_path))
    if not candidate.is_absolute():
        candidate = scenario_path.parent / candidate
    try:
        return candidate.resolve() == model_path.resolve()
    except OSError:
        fallback = (base_dir / ref_path).resolve()
        return fallback == model_path.resolve()


def _rewrite_scenario_for_workspace(data: dict[str, Any], project_slug: str, scenario_slug: str) -> None:
    indoor_ref = data.setdefault("indoorModelRef", {})
    if isinstance(indoor_ref, dict):
        indoor_ref["path"] = "../../spatial/indoor_model.json"
    outputs = data.setdefault("outputs", {})
    if isinstance(outputs, dict):
        outputs["outputFolder"] = f"models/{project_slug}/outputs/{scenario_slug}"


def _workspace_readme(slug: str, source_model: Path, copied_scenarios: list[str], base_dir: Path) -> str:
    scenario_lines = "\n".join(f"- `{path}`" for path in copied_scenarios) or "- pendiente de crear"
    return (
        f"# {slug}\n\n"
        "Model workspace asociado a un `indoor_model.json` de SpatialEngine.\n\n"
        f"- Modelo origen: `{repo_relative(source_model, base_dir)}`\n"
        "- Modelo local: `spatial/indoor_model.json`\n"
        "- Escenarios: `evacuation/scenarios/`\n"
        "- Experimentos de routing: `evacuation/experiments/`\n"
        "- Salidas generadas: `outputs/`\n\n"
        "## Escenarios actuales\n\n"
        f"{scenario_lines}\n\n"
        "## Comandos utiles\n\n"
        "```powershell\n"
        f"python -m src.evac_engine validate --scenario models/{slug}/evacuation/scenarios/<scenario>.json\n"
        f"python -m src.evac_engine workbench --model {slug}\n"
        f"python -m src.spatial_engine.web_app --model models/{slug}/spatial/indoor_model.json\n"
        "```\n"
    )

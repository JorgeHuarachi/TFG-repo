"""High-level CER analysis/export workflow for CLI and workbench."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .cer_visualization import save_cer_debug_gif, save_cer_debug_html, save_cer_debug_json, save_cer_summary_png
from .domain import IndoorModelBundle, ScenarioDefinition
from .overlays import BeaconSimulator, BeaconState, HazardScheduler, HazardState
from .rerouting_centrality import normalize_failure_profiles, rerouting_evacuation_centrality
from .routing import RoutingEngine
from .topology import EvacTopology


DEFAULT_CER_FAILURE_PROFILES = [[1], [1, 1], [1, 1, 1], [1, 2]]


def export_cer_analysis(
    indoor: IndoorModelBundle,
    scenario: ScenarioDefinition,
    *,
    origin: str,
    target: str | None = None,
    profile_id: str | None = None,
    output_dir: str | Path,
    formats: Iterable[str] = ("json", "png", "html"),
    level: str | None = None,
    use_dynamic_snapshot: bool = False,
    step: int = 0,
    time_s: float = 0.0,
    include_gif: bool | None = None,
    fps: int = 2,
    max_frames: int | None = 120,
    failure_profiles: Iterable[Iterable[int]] | None = None,
    cost_tolerance: float | None = None,
) -> dict[str, Any]:
    topology = EvacTopology.from_indoor_model(indoor)
    engine = RoutingEngine(topology)
    origin_id = indoor.resolve_cell_ref(origin) or origin
    target_id = _resolve_target(indoor, topology, scenario, target)
    profile = _resolve_profile(scenario, profile_id)
    routing_config = dict(scenario.physics)
    routing_config.update(scenario.routing)
    recommendation = dict(routing_config.get("routeRecommendation") or {})
    if use_dynamic_snapshot:
        hazard_state = HazardScheduler(topology, scenario.hazards).state_at(step, time_s)
        beacon_state = BeaconSimulator(topology, scenario.beacons, (scenario.raw.get("beaconSystem") or {}).get("fusion")).state_at(step, time_s)
    else:
        hazard_state = None
        beacon_state = None
        routing_config.update({"useHazardRisk": False, "useBeaconRisk": False, "useCongestion": False})
    cost_policy = str(routing_config.get("costPolicy", "minimum_travel_time"))
    snapshot = engine.compiler.compile(
        step=step,
        time_s=time_s,
        mobility_profile=profile,
        cost_policy=cost_policy,
        hazard_state=hazard_state,
        beacon_state=beacon_state,
        routing_config=routing_config,
    )
    engine._attach_cell_endpoint(
        snapshot.graph,
        origin_id,
        None,
        None,
        profile,
        cost_policy,
        hazard_state or HazardState(),
        beacon_state or BeaconState(),
        {},
        routing_config,
        direction="out",
    )
    if target_id not in snapshot.graph:
        engine._attach_cell_endpoint(
            snapshot.graph,
            target_id,
            None,
            None,
            profile,
            cost_policy,
            hazard_state or HazardState(),
            beacon_state or BeaconState(),
            {},
            routing_config,
            direction="in",
        )
    raw_profiles = failure_profiles or recommendation.get("reroutingFailureProfiles") or DEFAULT_CER_FAILURE_PROFILES
    profiles = normalize_failure_profiles(
        raw_profiles,
        max_depth=int(recommendation.get("reroutingMaxDepth") or 3),
        max_k=int(recommendation.get("reroutingMaxK") or 3),
    )
    result = rerouting_evacuation_centrality(
        snapshot.graph,
        [target_id],
        sources=[origin_id],
        failure_profiles=profiles,
        failure_unit=str(recommendation.get("reroutingFailureUnit") or "resource"),
        cost_tolerance=float(
            cost_tolerance
            if cost_tolerance is not None
            else recommendation.get("reroutingCostTolerance", recommendation.get("candidateCostTolerance", 0.35))
        ),
        distinctness_policy=str(recommendation.get("reroutingDistinctnessPolicy") or "exact"),
        max_depth=int(recommendation.get("reroutingMaxDepth") or 3),
        max_k=int(recommendation.get("reroutingMaxK") or 3),
        max_combinations=int(recommendation.get("reroutingMaxCombinations") or 500),
        max_runtime_ms=int(recommendation.get("reroutingMaxRuntimeMs") or 10000),
        max_overlap=float(recommendation.get("reroutingMaxOverlap", recommendation.get("centralityMaxOverlap", 0.8))),
        graph_view=topology.graph_view_name,
        store_routes=bool(recommendation.get("reroutingStoreRoutes", True)),
        store_failure_cases=True,
        debug_pairs={(origin_id, target_id)},
    )
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    requested = {str(item).lower() for item in formats}
    if include_gif is True:
        requested.add("gif")
    paths: dict[str, str] = {}
    if "json" in requested:
        paths["json"] = str(save_cer_debug_json(result, output / "cer_debug.json"))
    if "png" in requested:
        paths["png"] = str(save_cer_summary_png(topology, result, output / "cer_summary.png", level=level))
    if "html" in requested:
        paths["html"] = str(save_cer_debug_html(topology, result, output / "cer_explanation.html", level=level))
    if "gif" in requested:
        paths["gif"] = str(save_cer_debug_gif(topology, result, output / "cer_explanation.gif", level=level, fps=fps, max_frames=max_frames))
    summary = result.to_dict(store_routes=True)
    manifest = {
        "scenarioId": scenario.scenario_id,
        "origin": origin_id,
        "target": target_id,
        "profileId": profile.id if profile else None,
        "graphView": topology.graph_view_name,
        "snapshot": "dynamic" if use_dynamic_snapshot else "structural",
        "step": step,
        "timeS": time_s,
        "outputs": paths,
        "metadata": summary.get("metadata"),
        "nodeSummary": (summary.get("nodes") or {}).get(origin_id, {}).get("summary"),
    }
    manifest_path = output / "cer_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    paths["manifest"] = str(manifest_path)
    return {
        **manifest,
        "outputDir": str(output),
        "outputs": paths,
        "result": summary,
    }


def default_cer_output_dir(scenario_path: str | Path, indoor_path: str | Path, origin: str, target: str) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    scenario = Path(scenario_path).resolve()
    indoor = Path(indoor_path).resolve()
    slug = f"{_slug(scenario.stem)}__{_slug(origin)}__{_slug(target)}"
    try:
        relative = indoor.relative_to((project_root / "models").resolve())
        model_name = relative.parts[0]
        return project_root / "models" / model_name / "outputs" / "cer" / slug
    except ValueError:
        return project_root / "outputs" / "cer" / slug


def _resolve_profile(scenario: ScenarioDefinition, profile_id: str | None) -> Any | None:
    if profile_id:
        return scenario.mobility_profiles.get(profile_id)
    if scenario.groups:
        candidate = scenario.groups[0].get("mobilityProfileRef")
        if candidate in scenario.mobility_profiles:
            return scenario.mobility_profiles[candidate]
    if scenario.agents:
        candidate = scenario.agents[0].get("mobilityProfileRef")
        if candidate in scenario.mobility_profiles:
            return scenario.mobility_profiles[candidate]
    return next(iter(scenario.mobility_profiles.values()), None)


def _resolve_target(indoor: IndoorModelBundle, topology: EvacTopology, scenario: ScenarioDefinition, target: str | None) -> str:
    if target:
        return indoor.resolve_cell_ref(target) or target
    configured = list(((scenario.routing.get("destination") or {}).get("cellSpaceRefs") or []))
    if configured:
        return indoor.resolve_cell_ref(configured[0]) or configured[0]
    exits = topology.exit_candidates()
    if exits:
        return exits[0]
    raise ValueError("CER target is required because the scenario has no exit candidate.")


def _slug(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    return re.sub(r"_+", "_", cleaned).strip("._-") or "item"

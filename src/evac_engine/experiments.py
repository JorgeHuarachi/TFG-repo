"""Routing experiment presets and comparison utilities."""

from __future__ import annotations

import copy
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

from .loaders import load_project
from .simulation import EvacuationModel


BUILTIN_ROUTING_PRESETS: dict[str, dict[str, Any]] = {
    "dijkstra_time": {
        "presetId": "dijkstra_time",
        "label": "Dijkstra / tiempo puro",
        "description": "Baseline de coste minimo sin riesgo ni congestion.",
        "routing": {
            "algorithm": "dijkstra",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": False,
            "useBeaconRisk": False,
            "useCongestion": False,
            "riskCostModel": "legacy_additive",
            "routeRecommendation": {"routeSelection": "lowest_cost"},
        },
    },
    "astar_time": {
        "presetId": "astar_time",
        "label": "A* / tiempo puro",
        "description": "Baseline equivalente a Dijkstra cuando la heuristica euclidea es admisible.",
        "routing": {
            "algorithm": "astar",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": False,
            "useBeaconRisk": False,
            "useCongestion": False,
            "riskCostModel": "legacy_additive",
            "routeRecommendation": {"routeSelection": "lowest_cost"},
        },
    },
    "astar_risk_multiplicative": {
        "presetId": "astar_risk_multiplicative",
        "label": "A* / tiempo x riesgo",
        "description": "Coste tipo animate_dynamic_route: base * (alpha + beta_h*h + beta_b*b).",
        "routing": {
            "algorithm": "astar",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": True,
            "useBeaconRisk": True,
            "useCongestion": False,
            "riskCostModel": "multiplicative_beta",
            "riskEndpointPolicy": "max",
            "riskAggregation": "sum",
            "riskAlpha": 1.0,
            "hazardBeta": 1.0,
            "beaconBeta": 1.0,
            "routeRecommendation": {"routeSelection": "lowest_cost"},
        },
    },
    "yen_risk_lowest": {
        "presetId": "yen_risk_lowest",
        "label": "Yen k-rutas / menor coste",
        "description": "Genera candidatas k-shortest y conserva la de menor coste ponderado.",
        "routing": {
            "algorithm": "yen_ksp",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": True,
            "useBeaconRisk": True,
            "useCongestion": False,
            "riskCostModel": "multiplicative_beta",
            "riskEndpointPolicy": "max",
            "riskAlpha": 1.0,
            "hazardBeta": 1.0,
            "beaconBeta": 1.0,
            "routeRecommendation": {
                "routeSelection": "lowest_cost",
                "kShortestPaths": 6,
                "candidateCostTolerance": 0.35,
            },
        },
    },
    "yen_highest_robustness": {
        "presetId": "yen_highest_robustness",
        "label": "Yen k-rutas / robustez",
        "description": "Selecciona la ruta con mayor robustez dentro de la tolerancia de coste.",
        "routing": {
            "algorithm": "yen_ksp",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": True,
            "useBeaconRisk": True,
            "useCongestion": False,
            "riskCostModel": "multiplicative_beta",
            "riskEndpointPolicy": "max",
            "riskAlpha": 1.0,
            "hazardBeta": 1.0,
            "beaconBeta": 1.0,
            "routeRecommendation": {
                "routeSelection": "highest_robustness",
                "kShortestPaths": 6,
                "candidateCostTolerance": 0.35,
                "robustnessTolerance": 0.2,
            },
        },
    },
    "yen_highest_agility": {
        "presetId": "yen_highest_agility",
        "label": "Yen k-rutas / agilidad",
        "description": "Selecciona la ruta que atraviesa nodos con mayor centralidad de evacuacion.",
        "routing": {
            "algorithm": "yen_ksp",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": True,
            "useBeaconRisk": True,
            "useCongestion": False,
            "riskCostModel": "multiplicative_beta",
            "riskEndpointPolicy": "max",
            "riskAlpha": 1.0,
            "hazardBeta": 1.0,
            "beaconBeta": 1.0,
            "routeRecommendation": {
                "routeSelection": "highest_agility",
                "kShortestPaths": 6,
                "candidateCostTolerance": 0.35,
                "centralityTolerance": 0.35,
                "centralityMaxPaths": 8,
                "centralityMaxOverlap": 0.8,
            },
        },
    },
    "robust_agility": {
        "presetId": "robust_agility",
        "label": "Robustez + agilidad",
        "description": "Combina coste, robustez y agilidad en una politica multicriterio.",
        "routing": {
            "algorithm": "robust_agility",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": True,
            "useBeaconRisk": True,
            "useCongestion": False,
            "riskCostModel": "multiplicative_beta",
            "riskEndpointPolicy": "max",
            "riskAlpha": 1.0,
            "hazardBeta": 1.0,
            "beaconBeta": 1.0,
            "routeRecommendation": {
                "routeSelection": "robust_agility",
                "kShortestPaths": 6,
                "candidateCostTolerance": 0.35,
                "robustnessTolerance": 0.2,
                "centralityTolerance": 0.35,
                "centralityMaxPaths": 8,
                "centralityMaxOverlap": 0.8,
                "costWeight": 1.0,
                "robustnessWeight": 0.35,
                "agilityWeight": 0.35,
                "agilityAggregation": "mean",
            },
        },
    },
    "astar_risk_congestion": {
        "presetId": "astar_risk_congestion",
        "label": "A* / riesgo + congestion",
        "description": "Coste ponderado por riesgo y ocupacion observada de celda destino.",
        "routing": {
            "algorithm": "astar",
            "costPolicy": "minimum_travel_time",
            "useHazardRisk": True,
            "useBeaconRisk": True,
            "useCongestion": True,
            "riskCostModel": "multiplicative_beta",
            "riskEndpointPolicy": "max",
            "riskAlpha": 1.0,
            "hazardBeta": 1.0,
            "beaconBeta": 1.0,
            "routeRecommendation": {"routeSelection": "lowest_cost"},
        },
    },
}


def available_routing_presets(scenario_raw: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    presets = copy.deepcopy(BUILTIN_ROUTING_PRESETS)
    for preset in (((scenario_raw or {}).get("experiments") or {}).get("routingPresets") or []):
        preset_id = str(preset.get("presetId") or preset.get("id") or "")
        if preset_id:
            presets[preset_id] = copy.deepcopy(preset)
    return presets


def compare_routing_presets(
    indoor_path: str | Path | None,
    scenario_path: str | Path,
    *,
    preset_ids: list[str] | None = None,
    output_dir: str | Path = "outputs/routing_comparison",
    runtime_overrides: dict[str, Any] | None = None,
    write_run_outputs: bool = True,
    write_plot: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    _, seed_scenario = load_project(indoor_path, scenario_path)
    presets = available_routing_presets(seed_scenario.raw)
    selected_ids = preset_ids or list(presets)
    unknown = [preset_id for preset_id in selected_ids if preset_id not in presets]
    if unknown:
        raise ValueError(f"Unknown routing preset(s): {', '.join(unknown)}")

    rows = []
    for preset_id in selected_ids:
        preset = copy.deepcopy(presets[preset_id])
        indoor, scenario = load_project(indoor_path, scenario_path)
        _apply_runtime_overrides(scenario, runtime_overrides or {})
        _apply_preset(scenario, preset)
        preset_output = output_root / preset_id
        if write_run_outputs:
            scenario.outputs["outputFolder"] = str(preset_output)
            scenario.raw.setdefault("outputs", {})["outputFolder"] = str(preset_output)
        else:
            scenario.outputs.pop("outputFolder", None)
            scenario.raw.setdefault("outputs", {}).pop("outputFolder", None)
        start = time.perf_counter()
        model = EvacuationModel(indoor, scenario)
        result = model.run(preset_output if write_run_outputs else None)
        runtime_ms = (time.perf_counter() - start) * 1000.0
        rows.append(_summarize_run(preset_id, preset, model, result, runtime_ms, preset_output if write_run_outputs else None))

    route_rows = []
    for row in rows:
        route_rows.extend(row.pop("_routeRows", []))

    summary = {
        "scenario": str(Path(scenario_path).resolve()),
        "indoor": str(Path(indoor_path).resolve()) if indoor_path else str(seed_scenario.indoor_model_ref.get("path")),
        "outputDir": str(output_root),
        "presetIds": selected_ids,
        "presets": {preset_id: presets[preset_id] for preset_id in selected_ids},
        "runs": rows,
    }
    _write_json(output_root / "comparison_summary.json", summary)
    _write_csv(output_root / "comparison_metrics.csv", rows)
    _write_csv(output_root / "comparison_routes.csv", route_rows)
    if write_plot:
        plot_path = _write_plot(output_root, rows)
        summary["plot"] = str(plot_path) if plot_path else None
        _write_json(output_root / "comparison_summary.json", summary)
    return summary


def apply_routing_preset(scenario: Any, preset: dict[str, Any]) -> None:
    """Apply a routing preset to an already loaded scenario."""

    _apply_preset(scenario, preset)


def summarize_routing_run(
    preset_id: str,
    preset: dict[str, Any],
    model: EvacuationModel,
    result: Any,
    runtime_ms: float,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Return comparison metrics for one completed routing run."""

    return _summarize_run(preset_id, preset, model, result, runtime_ms, output_dir)


def _apply_preset(scenario: Any, preset: dict[str, Any]) -> None:
    routing_patch = copy.deepcopy(preset.get("routing") or {})
    scenario.routing = _deep_merge(copy.deepcopy(scenario.routing), routing_patch)
    scenario.raw["routing"] = copy.deepcopy(scenario.routing)


def _apply_runtime_overrides(scenario: Any, overrides: dict[str, Any]) -> None:
    if "timeStepS" in overrides and overrides["timeStepS"] is not None:
        scenario.simulation_config["timeStepS"] = float(overrides["timeStepS"])
        scenario.raw.setdefault("simulationConfig", {})["timeStepS"] = float(overrides["timeStepS"])
    if "maxSteps" in overrides and overrides["maxSteps"] is not None:
        scenario.simulation_config["maxSteps"] = int(overrides["maxSteps"])
        scenario.raw.setdefault("simulationConfig", {})["maxSteps"] = int(overrides["maxSteps"])
    if "randomSeed" in overrides and overrides["randomSeed"] is not None:
        scenario.simulation_config["randomSeed"] = int(overrides["randomSeed"])
        scenario.raw.setdefault("simulationConfig", {})["randomSeed"] = int(overrides["randomSeed"])
    if "firstGroupCount" in overrides and overrides["firstGroupCount"] is not None and scenario.groups:
        scenario.groups[0]["count"] = int(overrides["firstGroupCount"])
        scenario.raw.setdefault("population", {}).setdefault("agentGroups", [])[0]["count"] = int(overrides["firstGroupCount"])


def _summarize_run(
    preset_id: str,
    preset: dict[str, Any],
    model: EvacuationModel,
    result: Any,
    runtime_ms: float,
    output_dir: Path | None,
) -> dict[str, Any]:
    topology = model.topology.to_summary()
    routes = _route_records(result)
    breakdowns = [route.get("weightBreakdown") or {} for route in routes]
    route_metrics = [(item.get("routeMetrics") or {}) for item in breakdowns]
    status_counts = result.metrics.get("statusCounts") or {}
    row = {
        "presetId": preset_id,
        "label": preset.get("label") or preset_id,
        "algorithm": model.scenario.routing.get("algorithm"),
        "costPolicy": model.scenario.routing.get("costPolicy"),
        "riskCostModel": model.scenario.routing.get("riskCostModel", "legacy_additive"),
        "riskEndpointPolicy": model.scenario.routing.get("riskEndpointPolicy", "target"),
        "useHazardRisk": bool(model.scenario.routing.get("useHazardRisk", True)),
        "useBeaconRisk": bool(model.scenario.routing.get("useBeaconRisk", True)),
        "useCongestion": bool(model.scenario.routing.get("useCongestion", False)),
        "riskAlpha": model.scenario.routing.get("riskAlpha"),
        "hazardBeta": model.scenario.routing.get("hazardBeta"),
        "beaconBeta": model.scenario.routing.get("beaconBeta"),
        "nodes": topology.get("nodes"),
        "arcs": topology.get("arcs"),
        "stepsExecuted": result.metrics.get("stepsExecuted"),
        "timeS": result.metrics.get("timeS"),
        "agentCount": result.metrics.get("agentCount"),
        "evacuated": result.metrics.get("evacuated"),
        "noRoute": result.metrics.get("noRoute"),
        "trapped": result.metrics.get("trapped"),
        "active": status_counts.get("active", 0),
        "meanEvacuationTimeS": result.metrics.get("meanEvacuationTimeS"),
        "maxEvacuationTimeS": result.metrics.get("maxEvacuationTimeS"),
        "runtimeMs": round(runtime_ms, 6),
        "routePlans": _event_count(result.events, "route_planned"),
        "routeRecoveries": _event_count(result.events, "agent_route_recovered"),
        "noRouteEvents": _event_count(result.events, "agent_no_route"),
        "meanRouteCost": _mean(route.get("totalCost") for route in routes),
        "meanBaseCost": _mean(item.get("base") for item in breakdowns),
        "meanBaseComponent": _mean(item.get("baseComponent") for item in breakdowns),
        "meanHazardPenalty": _mean(item.get("hazardPenalty") for item in breakdowns),
        "meanBeaconPenalty": _mean(item.get("beaconPenalty") for item in breakdowns),
        "meanCongestionPenalty": _mean(item.get("congestionPenalty") for item in breakdowns),
        "meanPlanningMs": _mean(item.get("planningMs") for item in breakdowns),
        "meanSnapshotCompileMs": _mean(item.get("snapshotCompileMs") for item in breakdowns),
        "meanRobustness": _mean(item.get("robustness") for item in route_metrics),
        "meanAgility": _mean(item.get("agility") for item in route_metrics),
        "meanSelectionScore": _mean(item.get("selectionScore") for item in route_metrics),
        "outputDir": str(output_dir) if output_dir else None,
    }
    row["_routeRows"] = _route_rows(preset_id, routes)
    return row


def _route_records(result: Any) -> list[dict[str, Any]]:
    records = []
    seen: set[str] = set()
    for event in result.events:
        route = event.get("route")
        if isinstance(route, dict):
            key = json.dumps(route, sort_keys=True)
            if key not in seen:
                seen.add(key)
                records.append(route)
    for route in result.routes:
        key = json.dumps(route, sort_keys=True)
        if key not in seen:
            seen.add(key)
            records.append(route)
    return records


def _route_rows(preset_id: str, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, route in enumerate(routes, start=1):
        breakdown = route.get("weightBreakdown") or {}
        metrics = breakdown.get("routeMetrics") or {}
        rows.append(
            {
                "presetId": preset_id,
                "routeIndex": index,
                "origin": route.get("origin"),
                "destination": route.get("destination"),
                "reachable": route.get("reachable"),
                "nodeCount": len(route.get("nodeSequence") or []),
                "arcCount": len(route.get("arcSequence") or []),
                "totalCost": route.get("totalCost"),
                "base": breakdown.get("base"),
                "baseComponent": breakdown.get("baseComponent"),
                "hazardPenalty": breakdown.get("hazardPenalty"),
                "beaconPenalty": breakdown.get("beaconPenalty"),
                "congestionPenalty": breakdown.get("congestionPenalty"),
                "planningMs": breakdown.get("planningMs"),
                "snapshotCompileMs": breakdown.get("snapshotCompileMs"),
                "robustness": metrics.get("robustness"),
                "agility": metrics.get("agility"),
                "selectionScore": metrics.get("selectionScore"),
                "costRatio": metrics.get("costRatio"),
                "nodeSequence": "->".join(route.get("nodeSequence") or []),
            }
        )
    return rows


def _event_count(events: list[dict[str, Any]], event_type: str) -> int:
    return sum(1 for event in events if event.get("eventType") == event_type)


def _mean(values: Any) -> float | None:
    parsed = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            parsed.append(number)
    if not parsed:
        return None
    return round(sum(parsed) / len(parsed), 6)


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=True, indent=2)
        file.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [key for key in rows[0] if not key.startswith("_")]
    for row in rows[1:]:
        for key in row:
            if key not in fieldnames and not key.startswith("_"):
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_plot(output_root: Path, rows: list[dict[str, Any]]) -> Path | None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return None
    if not rows:
        return None
    labels = [str(row["presetId"]) for row in rows]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    panels = [
        ("meanEvacuationTimeS", "Tiempo medio evacuacion (s)"),
        ("meanRouteCost", "Coste medio de ruta"),
        ("runtimeMs", "Runtime total (ms)"),
        ("meanPlanningMs", "Planificacion media (ms)"),
    ]
    for ax, (key, title) in zip(axes.flatten(), panels):
        values = [float(row[key]) if row.get(key) is not None else 0.0 for row in rows]
        ax.bar(labels, values, color="#5b8def")
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    plot_path = output_root / "comparison_plot.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)
    return plot_path

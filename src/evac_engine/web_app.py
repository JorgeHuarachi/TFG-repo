"""Local browser workbench for EvacEngine.

This is intentionally dependency-free: stdlib HTTP server plus the existing
Python runtime. It lets a user configure a scenario, run the simulation, and
inspect a smooth canvas playback without relying on Tk/Tcl.
"""

from __future__ import annotations

import json
import copy
import csv
import datetime as _dt
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.spatial_engine.project_workspace import related_scenarios_for_model

from .cer_export import default_cer_output_dir, export_cer_analysis
from .domain import ScenarioDefinition
from .experiments import apply_routing_preset, available_routing_presets, summarize_routing_run
from .loaders import load_project
from .model_workspace import ensure_baseline_for_indoor, ensure_model_baseline_scenario
from .simulation import EvacuationModel
from .topology import EvacTopology
from .visualization import build_visualization_payload, graph_edge_payload, save_result_gif, save_result_html, virtual_boundary_payload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO = "examples/indoor_data_model/scenario_single_floor.json"
MODEL_LIBRARY_ROOT = PROJECT_ROOT


def run_workbench(
    host: str = "127.0.0.1",
    port: int = 8765,
    scenario_path: str | None = None,
    indoor_path: str | Path | None = None,
    model_name: str | None = None,
    library_root: str | Path | None = None,
) -> None:
    resolved_indoor = _display_path(_workspace_path(indoor_path)) if indoor_path else ""
    if model_name:
        default_scenario = _display_path(ensure_model_baseline_scenario(model_name))
    elif scenario_path:
        default_scenario = scenario_path
    elif indoor_path:
        default_scenario = _display_path(ensure_baseline_for_indoor(indoor_path))
    else:
        default_scenario = DEFAULT_SCENARIO
    resolved_library_root = _workspace_path(library_root or MODEL_LIBRARY_ROOT)

    class Handler(WorkbenchHandler):
        scenario_default = default_scenario
        indoor_default = resolved_indoor
        library_root = resolved_library_root

    server = ThreadingHTTPServer((host, port), Handler)
    query = f"?scenario={default_scenario}"
    if resolved_indoor:
        query += f"&indoor={resolved_indoor}"
    _safe_print(f"EvacEngine workbench: http://{host}:{port}/{query}")
    _safe_print(f"Model library root: {resolved_library_root}")
    server.serve_forever()


class WorkbenchHandler(BaseHTTPRequestHandler):
    scenario_default = DEFAULT_SCENARIO
    indoor_default = ""
    library_root = MODEL_LIBRARY_ROOT

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = WORKBENCH_HTML.replace("__DEFAULT_SCENARIO__", self.scenario_default.replace("\\", "/"))
            html = html.replace("__DEFAULT_INDOOR__", self.indoor_default.replace("\\", "/"))
            html = html.replace("__DEFAULT_LIBRARY_ROOT__", _display_path(self.library_root))
            self._send_html(html)
            return
        if parsed.path == "/api/model":
            try:
                query = parse_qs(parsed.query)
                scenario = query.get("scenario", [self.scenario_default])[0]
                indoor_path = query.get("indoor", [None])[0]
                self._send_json(load_model_summary(indoor_path, scenario))
            except Exception as exc:
                self._send_json({"error": str(exc)})
            return
        if parsed.path == "/api/library":
            try:
                query = parse_qs(parsed.query)
                root = query.get("root", [None])[0] or self.library_root
                payload = discover_model_library(root)
                payload["root"] = _display_path(_workspace_path(root))
                self._send_json(payload)
            except Exception as exc:
                self._send_json({"error": str(exc), "scenarios": [], "indoorModels": []})
            return
        if parsed.path == "/api/baseline-scenario":
            try:
                query = parse_qs(parsed.query)
                indoor = query.get("indoor", [None])[0]
                if not indoor:
                    raise ValueError("indoor is required")
                scenario_path = ensure_baseline_for_indoor(_workspace_path(indoor))
                self._send_json(
                    {
                        "scenarioPath": _display_path(scenario_path),
                        "indoorPath": _display_path(_workspace_path(indoor)),
                    }
                )
            except Exception as exc:
                self._send_json({"error": str(exc)})
            return
        if parsed.path == "/api/routing-presets":
            try:
                query = parse_qs(parsed.query)
                scenario = query.get("scenario", [self.scenario_default])[0]
                indoor_path = query.get("indoor", [None])[0]
                _, scenario_definition = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario))
                self._send_json({"presets": available_routing_presets(scenario_definition.raw)})
            except Exception as exc:
                self._send_json({"error": str(exc), "presets": {}})
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/run", "/api/routing-compare", "/api/save-scenario", "/api/render", "/api/save-routing-comparison", "/api/cer-export"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            request = json.loads(body or "{}")
            if parsed.path == "/api/save-scenario":
                self._send_json(save_configured_scenario(request, self.scenario_default))
            elif parsed.path == "/api/render":
                self._send_json(render_configured_simulation(request, self.scenario_default))
            elif parsed.path == "/api/cer-export":
                self._send_json(save_configured_cer_analysis(request, self.scenario_default))
            elif parsed.path == "/api/save-routing-comparison":
                self._send_json(save_configured_routing_comparison(request, self.scenario_default))
            elif parsed.path == "/api/routing-compare":
                self._send_json(compare_configured_routing(request, self.scenario_default))
            else:
                self._send_json(run_configured_simulation(request, self.scenario_default))
        except Exception as exc:  # pragma: no cover - manual endpoint guard.
            self.send_response(500)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        _safe_print(f"{self.address_string()} - {format % args}")

    def _send_html(self, html: str) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self._send_no_cache_headers()
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, payload: dict[str, Any]) -> None:
        self.send_response(200)
        self.send_header("content-type", "application/json; charset=utf-8")
        self._send_no_cache_headers()
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))

    def _send_no_cache_headers(self) -> None:
        self.send_header("cache-control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("pragma", "no-cache")
        self.send_header("expires", "0")


def load_model_summary(indoor_path: str | None, scenario_path: str) -> dict[str, Any]:
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    topology = EvacTopology.from_indoor_model(indoor)
    cells = []
    spaces = []
    for cell in indoor.cells_by_id.values():
        if cell.geometry is not None and not cell.geometry.is_empty:
            rings = []
            polygons = [cell.geometry] if cell.geometry.geom_type == "Polygon" else list(cell.geometry.geoms) if cell.geometry.geom_type == "MultiPolygon" else []
            for polygon in polygons:
                rings.append([[float(x), float(y)] for x, y in polygon.exterior.coords])
            if rings:
                spaces.append(
                    {
                        "id": cell.id,
                        "level": cell.level,
                        "navigationType": cell.navigation_type,
                        "category": cell.category,
                        "function": cell.function,
                        "isNavigable": cell.is_navigable,
                        "rings": rings,
                    }
                )
        if cell.is_navigable and cell.representative_point:
            cells.append(
                {
                    "id": cell.id,
                    "level": cell.level,
                    "navigationType": cell.navigation_type,
                    "category": cell.category,
                    "function": cell.function,
                    "x": round(cell.representative_point[0], 3),
                    "y": round(cell.representative_point[1], 3),
                }
            )
    return {
        "scenarioPath": _display_path(scenario.path),
        "indoorPath": _display_path(indoor.path),
        "scenarioId": scenario.scenario_id,
        "relatedScenarios": related_scenarios_for_model(indoor.path, PROJECT_ROOT),
        "levels": sorted(indoor.levels_by_id),
        "graphView": topology.graph_view_name,
        "graphEdges": graph_edge_payload(topology),
        "virtualBoundaries": virtual_boundary_payload(topology),
        "transferNodes": _transfer_node_payload(topology),
        "graphSummary": topology.to_summary(),
        "cells": cells,
        "spaces": spaces,
        "exits": [cell for cell in cells if cell["category"] == "Exit" or cell["function"] == "AnchorSpace"],
        "profiles": list(scenario.mobility_profiles),
        "groups": scenario.groups,
        "spawns": scenario.spawns,
        "config": {
            "timeStepS": scenario.time_step_s,
            "maxSteps": scenario.max_steps,
            "randomSeed": scenario.random_seed,
            "algorithm": scenario.routing.get("algorithm", "dijkstra"),
            "costPolicy": scenario.routing.get("costPolicy", "minimum_travel_time"),
            "useHazardRisk": bool(scenario.routing.get("useHazardRisk", True)),
            "useBeaconRisk": bool(scenario.routing.get("useBeaconRisk", True)),
            "useCongestion": bool(scenario.routing.get("useCongestion", False)),
            "beaconBlockThreshold": scenario.routing.get("beaconBlockThreshold", 0.85),
            "stairCapacity": scenario.physics.get("stairCapacity", 1),
            "rampCapacity": scenario.physics.get("rampCapacity", 1),
            "linearTransferFlowMode": scenario.physics.get("linearTransferFlowMode", "single_file"),
            "riskCostModel": scenario.routing.get("riskCostModel", "legacy_additive"),
            "riskEndpointPolicy": scenario.routing.get("riskEndpointPolicy", "target"),
            "riskEdgePrecedence": bool(scenario.routing.get("riskEdgePrecedence", True)),
            "riskAggregation": scenario.routing.get("riskAggregation", "sum"),
            "riskAlpha": scenario.routing.get("riskAlpha", 1.0),
            "hazardBeta": scenario.routing.get("hazardBeta", 20.0),
            "beaconBeta": scenario.routing.get("beaconBeta", 5.0),
            "riskUnitCost": scenario.routing.get("riskUnitCost", 1.0),
            "routeRecommendation": scenario.routing.get("routeRecommendation") or {},
            "firstGroupCount": scenario.groups[0].get("count") if scenario.groups else 0,
            "firstSpawnCell": scenario.spawns[0].get("cellSpaceRef") if scenario.spawns else "",
            "firstSpawnPosition": (scenario.spawns[0].get("position") or {}).get("coordinates") if scenario.spawns else None,
            "firstGroupDistribution": scenario.groups[0].get("distribution", "random_within_space") if scenario.groups else "random_within_space",
            "destinationCells": (scenario.routing.get("destination") or {}).get("cellSpaceRefs") or [],
        },
        "routingPresets": available_routing_presets(scenario.raw),
        "manualAgents": scenario.agents,
        "beacons": scenario.beacons,
        "scheduledEvents": scenario.raw.get("scheduledEvents") or [],
    }


def discover_model_library(root: Path = MODEL_LIBRARY_ROOT) -> dict[str, list[dict[str, str]]]:
    scenarios: list[dict[str, str]] = []
    indoor_models: list[dict[str, str]] = []
    seen_scenarios: set[str] = set()
    seen_indoor_models: set[str] = set()
    root_path = _workspace_path(root)
    if root_path.resolve() == PROJECT_ROOT.resolve():
        roots = [PROJECT_ROOT / "models"]
    else:
        roots = [root_path]
    for current_root in roots:
        scanned = _scan_model_library_root(current_root)
        for item in scanned["scenarios"]:
            if item["path"] not in seen_scenarios:
                scenarios.append(item)
                seen_scenarios.add(item["path"])
        for item in scanned["indoorModels"]:
            if item["path"] not in seen_indoor_models:
                indoor_models.append(item)
                seen_indoor_models.add(item["path"])
    scenarios.sort(key=lambda item: item["path"])
    indoor_models.sort(key=lambda item: item["path"])
    return {"scenarios": scenarios, "indoorModels": indoor_models}


def _transfer_node_payload(topology: EvacTopology) -> list[dict[str, Any]]:
    """Expose runtime graph nodes for CER/debug selection in the workbench."""

    nodes: list[dict[str, Any]] = []
    for node_id, data in topology.graph.nodes(data=True):
        point = topology.node_position(str(node_id))
        if not point:
            continue
        category = str(data.get("category") or "")
        function = str(data.get("function") or "")
        navigation_type = str(data.get("navigationType") or "")
        transfer_kind = _transfer_kind(str(node_id), category, function, navigation_type)
        nodes.append(
            {
                "id": str(node_id),
                "level": topology.node_level(str(node_id)) or data.get("level") or "",
                "category": category,
                "function": function,
                "navigationType": navigation_type,
                "transferKind": transfer_kind,
                "isExit": bool(data.get("isExit") or category == "Exit" or function == "AnchorSpace"),
                "x": round(float(point[0]), 3),
                "y": round(float(point[1]), 3),
            }
        )
    return sorted(nodes, key=lambda item: (item["level"], item["transferKind"], item["id"]))


def _transfer_kind(node_id: str, category: str, function: str, navigation_type: str) -> str:
    if node_id.startswith("VTN_") or category == "VirtualTransferNode":
        return "virtual boundary"
    if category == "Exit" or function == "AnchorSpace":
        return "exit"
    if category in {"Door", "Window", "Stair", "Ramp", "Elevator"}:
        return category.lower()
    if navigation_type == "TransferSpace":
        return "transfer"
    return "graph node"


def _scan_model_library_root(root: Path) -> dict[str, list[dict[str, str]]]:
    scenarios: list[dict[str, str]] = []
    indoor_models: list[dict[str, str]] = []
    root_path = _workspace_path(root)
    if not root_path.exists():
        return {"scenarios": scenarios, "indoorModels": indoor_models}
    pattern = "*.json" if root_path == MODEL_LIBRARY_ROOT else "**/*.json"
    for path in sorted(root_path.glob(pattern)):
        if any(part in {"outputs", "__pycache__"} for part in path.relative_to(root_path).parts[:-1]):
            continue
        if _looks_like_indoor_model(path):
            indoor_models.append(_library_item(path, _read_light_metadata(path)))
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("scenarioId") or data.get("indoorModelRef"):
            scenarios.append(_library_item(path, data))
        elif data.get("indoorFeatures") or data.get("levels"):
            indoor_models.append(_library_item(path, data))
    return {"scenarios": scenarios, "indoorModels": indoor_models}


def _workspace_path(path: str | Path) -> Path:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved


def _display_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved).replace("\\", "/")


def _safe_print(message: str) -> None:
    try:
        print(message)
    except Exception:
        pass


def _looks_like_indoor_model(path: Path) -> bool:
    if "indoor_model" not in path.name:
        return False
    data = _read_light_metadata(path)
    return path.name.endswith("indoor_model.json") or bool(data.get("featureType") == "IndoorFeatures")


def _read_light_metadata(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            prefix = handle.read(200_000)
    except Exception:
        return {}
    metadata: dict[str, Any] = {}
    for key in ("scenarioId", "indoorModelId", "modelName", "scenarioName", "name"):
        match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', prefix)
        if match:
            metadata[key] = match.group(1)
    feature_match = re.search(r'"featureType"\s*:\s*"([^"]+)"', prefix)
    if feature_match:
        metadata["featureType"] = feature_match.group(1)
    name_match = re.search(r'"metadata"\s*:\s*\{.*?"name"\s*:\s*"([^"]+)"', prefix, flags=re.DOTALL)
    if name_match:
        metadata["metadata"] = {"name": name_match.group(1)}
    return metadata


def _library_item(path: Path, data: dict[str, Any]) -> dict[str, str]:
    return {
        "path": _display_path(path),
        "id": str(data.get("scenarioId") or data.get("indoorModelId") or data.get("modelName") or path.stem),
        "name": str((data.get("metadata") or {}).get("name") or data.get("scenarioName") or data.get("name") or path.stem),
    }


def _library_model_name(item: dict[str, Any]) -> str:
    label = str(item.get("label") or item.get("path") or "indoor_model")
    source = str(item.get("source") or "")
    project = str(item.get("project") or "")
    prefix = f"{project} - " if project else ""
    suffix = f" ({source})" if source else ""
    return f"{prefix}{label}{suffix}"


def run_configured_simulation(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    apply_request_to_scenario(scenario, request)
    run_beacons = copy.deepcopy(scenario.beacons)
    run_events = copy.deepcopy(scenario.raw.get("scheduledEvents") or [])
    run_routing = copy.deepcopy(scenario.routing)
    model = EvacuationModel(indoor, scenario)
    result = model.run()
    config = request.get("config") or {}
    include_geometry_qa = bool(config.get("includeGeometryQa"))
    payload = build_visualization_payload(model.topology, result, include_geometry_qa=include_geometry_qa)
    payload["scenarioConfig"] = {
        "scenarioPath": scenario_path,
        "timeStepS": scenario.time_step_s,
        "maxSteps": scenario.max_steps,
        "randomSeed": scenario.random_seed,
    }
    payload["beacons"] = run_beacons
    payload["scheduledEvents"] = run_events
    payload["routingConfig"] = run_routing
    return payload


def compare_configured_routing(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    _, seed_scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    presets = available_routing_presets(seed_scenario.raw)
    preset_ids = [str(item) for item in (request.get("presetIds") or []) if str(item) in presets]
    if not preset_ids:
        preset_ids = list(presets)[:4]
    rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    for preset_id in preset_ids:
        preset = copy.deepcopy(presets[preset_id])
        indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
        apply_request_to_scenario(scenario, request)
        apply_routing_preset(scenario, preset)
        started = time.perf_counter()
        model = EvacuationModel(indoor, scenario)
        result = model.run()
        row = summarize_routing_run(preset_id, preset, model, result, (time.perf_counter() - started) * 1000.0)
        route_rows.extend(row.pop("_routeRows", []))
        rows.append(row)
    return {
        "scenarioPath": scenario_path,
        "indoorPath": indoor_path,
        "presetIds": preset_ids,
        "presets": {preset_id: presets[preset_id] for preset_id in preset_ids},
        "runs": rows,
        "routeRows": route_rows,
    }


def save_configured_scenario(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    """Persist the current workbench configuration as a scenario JSON."""

    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    apply_request_to_scenario(scenario, request)
    save_name = str(request.get("saveName") or "").strip() or Path(scenario_path).stem
    scenario_slug = _slugify(save_name)
    model_dir = _model_workspace_for_paths(scenario.path, indoor.path)
    if model_dir is not None:
        target = model_dir / "evacuation" / "scenarios" / f"{scenario_slug}.json"
        model_name = model_dir.name
        indoor_ref = os_path_rel(model_dir / "spatial" / "indoor_model.json", target.parent)
        output_folder = f"models/{model_name}/outputs/{scenario_slug}"
        scenario_name = f"{model_name}_{scenario_slug}"
    else:
        target = PROJECT_ROOT / "outputs" / "workbench_scenarios" / f"{scenario_slug}.json"
        indoor_ref = os_path_rel(indoor.path, target.parent)
        output_folder = f"outputs/workbench_scenarios/{scenario_slug}"
        scenario_name = scenario_slug

    document = copy.deepcopy(scenario.raw)
    document["scenarioId"] = f"SCENARIO_{_slugify(scenario_name).upper()}"
    document["scenarioName"] = scenario_name
    metadata = dict(document.get("metadata") or {})
    now = _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metadata.setdefault("createdAt", now)
    metadata["modifiedAt"] = now
    metadata["name"] = scenario_name
    metadata["generator"] = "evac_engine.workbench.save_configured_scenario"
    document["metadata"] = metadata
    document["indoorModelRef"] = {
        **dict(document.get("indoorModelRef") or {}),
        "path": indoor_ref,
        "schemaRef": os_path_rel(PROJECT_ROOT / "schemas" / "indoor" / "indoor_model.schema.json", target.parent),
    }
    document.setdefault("outputs", {})["outputFolder"] = output_folder

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    load_project(None, tmp)
    tmp.replace(target)
    return {
        "scenarioPath": _display_path(target),
        "indoorPath": _display_path(indoor.path),
        "outputFolder": output_folder,
        "relatedScenarios": related_scenarios_for_model(indoor.path, PROJECT_ROOT),
    }


def render_configured_simulation(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    """Run the configured scenario and save reusable visual artifacts."""

    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    apply_request_to_scenario(scenario, request)
    render_config = request.get("render") or {}
    output_dir = _resolve_output_dir(render_config.get("outputDir") or _default_output_dir(scenario.path, indoor.path, suffix=""))
    result = EvacuationModel(indoor, scenario).run(output_dir)
    topology = EvacTopology.from_indoor_model(indoor)
    gif_path = None
    html_path = None
    if render_config.get("gif", True):
        gif_path = save_result_gif(
            topology,
            result,
            output_dir / "simulation.gif",
            level=render_config.get("level") or None,
            fps=int(render_config.get("fps") or 8),
            max_frames=int(render_config["maxFrames"]) if render_config.get("maxFrames") else None,
        )
    if render_config.get("html", True):
        html_path = save_result_html(topology, result, output_dir / "simulation.html", include_geometry_qa=bool((request.get("config") or {}).get("includeGeometryQa")))
    return {
        "outputDir": _display_path(output_dir),
        "gif": _display_path(gif_path) if gif_path else None,
        "html": _display_path(html_path) if html_path else None,
        "metrics": result.metrics,
        "qa": build_visualization_payload(topology, result, include_geometry_qa=bool((request.get("config") or {}).get("includeGeometryQa")))["qa"],
    }


def save_configured_routing_comparison(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    """Compare selected routing presets and persist a small comparison viewer."""

    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    indoor, _ = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    output_dir = _resolve_output_dir(request.get("comparisonOutputDir") or _default_output_dir(_workspace_path(scenario_path), indoor.path, suffix="routing_compare"))
    comparison = compare_configured_routing(request, default_scenario)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "comparison_summary.json"
    metrics_path = output_dir / "comparison_metrics.csv"
    routes_path = output_dir / "comparison_routes.csv"
    html_path = output_dir / "comparison_viewer.html"
    _write_json(summary_path, comparison)
    _write_csv(metrics_path, comparison.get("runs") or [])
    _write_csv(routes_path, comparison.get("routeRows") or [])
    _write_comparison_html(html_path, comparison)
    return {
        **comparison,
        "outputDir": _display_path(output_dir),
        "summary": _display_path(summary_path),
        "metricsCsv": _display_path(metrics_path),
        "routesCsv": _display_path(routes_path),
        "html": _display_path(html_path),
    }


def save_configured_cer_analysis(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    """Persist CER debug artifacts for the current workbench scenario."""

    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    apply_request_to_scenario(scenario, request)
    cer = request.get("cer") or {}
    origin = str(cer.get("origin") or _default_cer_origin(scenario, request) or "").strip()
    if not origin:
        raise ValueError("CER origin is required. Select a spawn/manual agent cell or fill CER origin.")
    target = str(cer.get("target") or _default_cer_target(scenario, request) or "").strip() or None
    profile = str(cer.get("profile") or _default_cer_profile(scenario, request) or "").strip() or None
    output_dir = _resolve_output_dir(
        cer.get("outputDir") or default_cer_output_dir(scenario.path, indoor.path, origin, target or "target")
    )
    formats = cer.get("formats") or ["json", "png", "html"]
    payload = export_cer_analysis(
        indoor,
        scenario,
        origin=origin,
        target=target,
        profile_id=profile,
        output_dir=output_dir,
        formats=formats,
        level=cer.get("level") or None,
        use_dynamic_snapshot=bool(cer.get("dynamic")),
        step=int(cer.get("step") or 0),
        time_s=float(cer.get("timeS") or 0.0),
        include_gif=bool(cer.get("gif")),
        fps=int(cer.get("fps") or 2),
        max_frames=int(cer["maxFrames"]) if cer.get("maxFrames") else 120,
    )
    outputs = {key: _display_path(value) for key, value in (payload.get("outputs") or {}).items()}
    return {
        "scenarioId": payload.get("scenarioId"),
        "origin": payload.get("origin"),
        "target": payload.get("target"),
        "profileId": payload.get("profileId"),
        "graphView": payload.get("graphView"),
        "snapshot": payload.get("snapshot"),
        "outputDir": _display_path(output_dir),
        "outputs": outputs,
        "metadata": payload.get("metadata"),
        "nodeSummary": payload.get("nodeSummary"),
    }


def apply_request_to_scenario(scenario: ScenarioDefinition, request: dict[str, Any]) -> None:
    config = request.get("config") or {}
    if config.get("timeStepS") is not None:
        scenario.simulation_config["timeStepS"] = float(config["timeStepS"])
    if config.get("maxSteps") is not None:
        scenario.simulation_config["maxSteps"] = int(config["maxSteps"])
    if config.get("randomSeed") is not None:
        scenario.simulation_config["randomSeed"] = int(config["randomSeed"])
    for key in ("stairCapacity", "rampCapacity"):
        if config.get(key) is not None:
            scenario.physics[key] = max(1, int(config[key]))
    if config.get("linearTransferFlowMode"):
        scenario.physics["linearTransferFlowMode"] = str(config["linearTransferFlowMode"])
    if config.get("algorithm"):
        scenario.routing["algorithm"] = config["algorithm"]
    if config.get("costPolicy"):
        scenario.routing["costPolicy"] = config["costPolicy"]
    for key in ("riskCostModel", "riskEndpointPolicy", "riskAggregation"):
        if config.get(key):
            scenario.routing[key] = str(config[key])
    for key in ("useHazardRisk", "useBeaconRisk", "useCongestion", "riskEdgePrecedence"):
        if config.get(key) is not None:
            scenario.routing[key] = bool(config[key])
    for key in ("riskAlpha", "hazardBeta", "beaconBeta", "riskUnitCost"):
        if config.get(key) is not None:
            scenario.routing[key] = float(config[key])
    if config.get("useBeaconRisk") is not None:
        scenario.routing["useBeaconRisk"] = bool(config["useBeaconRisk"])
    if config.get("beaconBlockThreshold") is not None:
        scenario.routing["beaconBlockThreshold"] = float(config["beaconBlockThreshold"])
    if config.get("routeRecommendation") is not None:
        scenario.routing["routeRecommendation"] = dict(config["routeRecommendation"] or {})
    if config.get("destinationCells"):
        scenario.routing.setdefault("destination", {})["cellSpaceRefs"] = list(config["destinationCells"])
    if scenario.groups and config.get("firstGroupCount") is not None:
        scenario.groups[0]["count"] = int(config["firstGroupCount"])
    if scenario.groups and config.get("firstGroupDistribution"):
        scenario.groups[0]["distribution"] = str(config["firstGroupDistribution"])
    if scenario.spawns and config.get("firstSpawnCell"):
        scenario.spawns[0]["cellSpaceRef"] = config["firstSpawnCell"]
        scenario.spawns[0].pop("nodeRef", None)
    if scenario.spawns and config.get("firstSpawnPosition"):
        coords = list(config["firstSpawnPosition"])
        if len(coords) >= 2:
            scenario.spawns[0]["position"] = {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]}
    if request.get("manualAgents"):
        scenario.agents = list(request["manualAgents"])
        scenario.raw.setdefault("population", {})["agents"] = list(request["manualAgents"])
        scenario.groups = []
        scenario.raw.setdefault("population", {})["agentGroups"] = []
    if request.get("beacons") is not None:
        scenario.beacons = list(request["beacons"])
        scenario.raw.setdefault("beaconSystem", {})["beacons"] = list(request["beacons"])
        scenario.raw.setdefault("beaconSystem", {})["enabled"] = True
    if request.get("scheduledEvents") is not None:
        scenario.raw["scheduledEvents"] = list(request["scheduledEvents"])
    _sync_scenario_raw(scenario)


def _sync_scenario_raw(scenario: ScenarioDefinition) -> None:
    scenario.raw["routing"] = copy.deepcopy(scenario.routing)
    scenario.raw["simulationConfig"] = copy.deepcopy(scenario.simulation_config)
    scenario.raw["outputs"] = copy.deepcopy(scenario.outputs)
    population = scenario.raw.setdefault("population", {})
    population["agentGroups"] = copy.deepcopy(scenario.groups)
    population["agentSpawns"] = copy.deepcopy(scenario.spawns)
    population["agents"] = copy.deepcopy(scenario.agents)
    beacon_system = scenario.raw.setdefault("beaconSystem", {})
    beacon_system["beacons"] = copy.deepcopy(scenario.beacons)
    if scenario.beacons:
        beacon_system["enabled"] = True


def _model_workspace_for_paths(scenario_path: Path, indoor_path: Path) -> Path | None:
    for path in (scenario_path, indoor_path):
        try:
            relative = path.resolve().relative_to((PROJECT_ROOT / "models").resolve())
        except ValueError:
            continue
        if relative.parts:
            model_dir = PROJECT_ROOT / "models" / relative.parts[0]
            if model_dir.exists():
                return model_dir
    return None


def _default_output_dir(scenario_path: Path, indoor_path: Path, suffix: str = "") -> Path:
    scenario_slug = _slugify(Path(scenario_path).stem)
    if suffix:
        scenario_slug = f"{scenario_slug}_{_slugify(suffix)}"
    model_dir = _model_workspace_for_paths(Path(scenario_path), Path(indoor_path))
    if model_dir is not None:
        return model_dir / "outputs" / scenario_slug
    return PROJECT_ROOT / "outputs" / "workbench" / scenario_slug


def _default_cer_origin(scenario: ScenarioDefinition, request: dict[str, Any]) -> str | None:
    manual_agents = request.get("manualAgents") or []
    if manual_agents:
        return manual_agents[0].get("initialCellSpaceRef")
    agents = scenario.agents or []
    if agents:
        return agents[0].get("initialCellSpaceRef")
    config = request.get("config") or {}
    if config.get("firstSpawnCell"):
        return str(config["firstSpawnCell"])
    if scenario.spawns:
        return scenario.spawns[0].get("cellSpaceRef")
    return None


def _default_cer_target(scenario: ScenarioDefinition, request: dict[str, Any]) -> str | None:
    config = request.get("config") or {}
    if config.get("destinationCells"):
        return list(config["destinationCells"])[0]
    destinations = list(((scenario.routing.get("destination") or {}).get("cellSpaceRefs") or []))
    return destinations[0] if destinations else None


def _default_cer_profile(scenario: ScenarioDefinition, request: dict[str, Any]) -> str | None:
    manual_agents = request.get("manualAgents") or []
    if manual_agents:
        return manual_agents[0].get("mobilityProfileRef")
    if scenario.agents:
        return scenario.agents[0].get("mobilityProfileRef")
    if scenario.groups:
        return scenario.groups[0].get("mobilityProfileRef")
    return next(iter(scenario.mobility_profiles), None)


def _resolve_output_dir(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"Output path is outside the repository: {value}") from exc
    return resolved


def os_path_rel(path: str | Path, start: str | Path) -> str:
    import os

    return os.path.relpath(Path(path), Path(start)).replace("\\", "/")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "scenario"


def _write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=True, indent=2)
        handle.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_comparison_html(path: Path, comparison: dict[str, Any]) -> None:
    rows = comparison.get("runs") or []
    labels = [str(row.get("presetId")) for row in rows]
    max_time = max([float(row.get("meanEvacuationTimeS") or 0) for row in rows] or [1.0])
    max_runtime = max([float(row.get("runtimeMs") or 0) for row in rows] or [1.0])
    table = "\n".join(
        "<tr>"
        f"<td>{_escape_html(row.get('presetId'))}</td>"
        f"<td>{_escape_html(row.get('algorithm'))}</td>"
        f"<td>{_escape_html(row.get('evacuated'))}</td>"
        f"<td>{_escape_html(row.get('noRoute'))}</td>"
        f"<td>{_escape_html(row.get('meanEvacuationTimeS'))}</td>"
        f"<td>{_escape_html(row.get('meanRouteCost'))}</td>"
        f"<td>{_escape_html(row.get('meanPlanningMs'))}</td>"
        f"<td>{_escape_html(row.get('runtimeMs'))}</td>"
        f"<td>{_escape_html(row.get('meanRobustness'))}</td>"
        f"<td>{_escape_html(row.get('meanAgility'))}</td>"
        "</tr>"
        for row in rows
    )
    bars = "\n".join(
        "<div class='bar-row'>"
        f"<span>{_escape_html(label)}</span>"
        f"<div class='bar time' style='width:{_bar_width(row.get('meanEvacuationTimeS'), max_time)}%'></div>"
        f"<div class='bar runtime' style='width:{_bar_width(row.get('runtimeMs'), max_runtime)}%'></div>"
        "</div>"
        for label, row in zip(labels, rows)
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Routing Comparison</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #111827; background: #f8fafc; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; font-size: 13px; text-align: left; }}
    th {{ background: #e2e8f0; }}
    .bar-row {{ display: grid; grid-template-columns: 220px 1fr 1fr; gap: 8px; align-items: center; margin: 8px 0; }}
    .bar {{ height: 16px; min-width: 2px; border-radius: 3px; }}
    .time {{ background: #2563eb; }}
    .runtime {{ background: #f97316; }}
    .legend {{ color: #475569; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>Routing Comparison</h1>
  <p class="legend">Blue = mean evacuation time. Orange = runtime. Shorter bars are usually better for both metrics.</p>
  {bars}
  <h2>Metrics</h2>
  <table>
    <thead><tr><th>preset</th><th>algorithm</th><th>evacuated</th><th>noRoute</th><th>meanEvacS</th><th>meanRouteCost</th><th>meanPlanMs</th><th>runtimeMs</th><th>robust</th><th>agility</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _bar_width(value: Any, maximum: float) -> int:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return max(2, min(100, round(number / max(maximum, 1e-9) * 100)))


def _escape_html(value: Any) -> str:
    return (
        str(value if value is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


WORKBENCH_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EvacEngine Workbench</title>
  <style>
    :root { font-family: Segoe UI, Arial, sans-serif; color: #111827; background: #f8fafc; }
    body { margin: 0; }
    .app { height: 100vh; display: grid; grid-template-columns: 390px 1fr; }
    aside { overflow: auto; background: white; border-right: 1px solid #cbd5e1; padding: 14px; }
    main { min-width: 0; display: grid; grid-template-rows: 1fr 240px; }
    canvas { width: 100%; height: 100%; display: block; background: #f8fafc; }
    h1 { font-size: 19px; margin: 0 0 8px; }
    h2 { font-size: 14px; margin: 18px 0 6px; color: #334155; }
    label { display: block; font-size: 12px; color: #475569; margin-top: 9px; }
    input, select, textarea, button { width: 100%; box-sizing: border-box; margin-top: 4px; padding: 7px; border-radius: 4px; border: 1px solid #94a3b8; background: #fff; }
    select { min-height: 36px; color: #0f172a; }
    select:disabled { color: #64748b; background: #f8fafc; }
    textarea { min-height: 96px; resize: vertical; font-family: Consolas, monospace; font-size: 12px; }
    button { border-color: #0f172a; background: #0f172a; color: white; cursor: pointer; }
    button:disabled { border-color: #cbd5e1; background: #e2e8f0; color: #64748b; cursor: not-allowed; }
    input:disabled, select:disabled, textarea:disabled { background: #eef2f7; color: #64748b; cursor: not-allowed; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .row.three { grid-template-columns: 1fr 1fr 1fr; }
    .tabs { display: flex; gap: 6px; margin-top: 8px; }
    .tabs button { width: auto; flex: 1; border-color: #cbd5e1; background: #e2e8f0; color: #0f172a; }
    .tabs button.active { border-color: #0f172a; background: #0f172a; color: #fff; }
    .tab-panel[hidden] { display: none; }
    details { margin-top: 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; padding: 8px; }
    summary { cursor: pointer; font-size: 12px; color: #334155; font-weight: 600; }
    details.section { background: #ffffff; }
    details.section > summary { font-size: 13px; color: #0f172a; }
    .section-description { display: block; margin-top: 2px; font-size: 11px; font-weight: 400; color: #64748b; line-height: 1.25; }
    .disabled-hint { color: #64748b; font-style: italic; }
    .check-list { max-height: 132px; overflow: auto; margin-top: 6px; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; }
    .check-list label { display: flex; align-items: flex-start; gap: 6px; margin: 4px 0; color: #0f172a; }
    .check-list input { width: auto; margin-top: 2px; }
    .mini-canvas { display: block; width: 100%; height: 116px; margin-top: 4px; border: 1px solid #94a3b8; border-radius: 4px; background: #fff; }
    .status-box { margin-top: 8px; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; font-family: Consolas, monospace; font-size: 12px; line-height: 1.35; color: #334155; white-space: pre-wrap; font-variant-numeric: tabular-nums; }
    .toolbar { display: flex; gap: 8px; align-items: center; padding: 10px; border-top: 1px solid #cbd5e1; background: #fff; }
    .toolbar button { width: auto; min-width: 80px; }
    .toolbar input, .toolbar select { width: auto; flex: 1; }
    .run-panel { min-height: 0; overflow: auto; background: #f8fafc; }
    .route-cost-wrap { display: grid; grid-template-columns: minmax(220px, 34%) 1fr; gap: 10px; padding: 8px 10px; border-top: 1px solid #cbd5e1; background: #fff; }
    .route-cost-chart { display: block; width: 100%; height: 74px; border: 1px solid #cbd5e1; border-radius: 4px; background: #fff; }
    pre { margin: 0; overflow: auto; background: #f1f5f9; padding: 10px; font-size: 12px; }
    .muted { color: #64748b; font-size: 12px; }
    .compact-note { margin: 4px 0 8px; color: #64748b; font-size: 11px; line-height: 1.35; }
  </style>
</head>
<body>
<div class="app">
  <aside>
    <h1>EvacEngine Workbench</h1>
    <div class="muted" id="summary">Loading model...</div>
    <div class="compact-note" id="sessionInfo">session pending</div>
    <pre id="help">1. Scenario = config editable de simulacion.
2. Indoor model = geometria; se toma del scenario si esta vacio.
3. Ajusta agentes, destino, balizas y routing.
4. Run simulation; Play revisa el resultado.</pre>
    <h2>Open</h2>
    <label>Scenario library</label>
    <select id="libraryScenario"></select>
    <label>Indoor model library</label>
    <select id="libraryIndoor"></select>
    <div class="row">
      <button id="openLibraryScenario" type="button">Open scenario</button>
      <button id="openLibraryIndoor" type="button">Open indoor</button>
    </div>
    <div class="compact-note">Open indoor crea o reutiliza `evacuation/scenarios/baseline.json` para ese modelo.</div>
    <label>Scenarios for loaded model</label>
    <select id="modelScenario"></select>
    <button id="openModelScenario" type="button">Open model scenario</button>
    <label>Scenario path</label>
    <input id="scenarioPath">
    <div class="compact-note">Run usa una copia en memoria; Save scenario escribe el JSON en disco.</div>
    <label>Indoor model path</label>
    <input id="indoorPath" placeholder="Leave empty to use scenario.indoorModelRef.path">
    <div class="compact-note">Vacio = usar indoorModelRef.path declarado dentro del scenario.</div>
    <label>Save scenario name</label>
    <input id="scenarioSaveName" placeholder="baseline, crowd_test, beacon_blocked...">
    <div class="row">
      <button id="reload" type="button">Reload scenario</button>
      <button id="saveScenario" type="button">Save scenario</button>
    </div>
    <h2>Simulation</h2>
    <div class="row">
      <div><label>Time step</label><input id="timeStep" type="number" step="0.05"></div>
      <div><label>Max steps</label><input id="maxSteps" type="number"></div>
    </div>
    <div class="compact-note" id="durationHint"></div>
    <label>Seed</label><input id="seed" type="number">
    <div class="compact-note">Seed fija la aleatoriedad reproducible: mismo seed, mismos spawns aleatorios.</div>
    <div class="row">
      <div><label>Destination mode</label><select id="destinationMode"><option value="scenario">All scenario exits</option><option value="selected">Selected only</option></select></div>
      <div><label>Destination exit/cell</label><select id="destinationCell"></select></div>
    </div>
    <div class="compact-note">All scenario exits usa las salidas del scenario; Selected only fuerza una celda concreta.</div>
    <div class="row">
      <div><label>Algorithm</label><select id="algorithm"><option>dijkstra</option><option>astar</option><option>floyd_warshall</option><option>yen_ksp</option><option>robust_agility</option></select></div>
      <div><label>Cost</label><select id="costPolicy"><option>minimum_travel_time</option></select></div>
    </div>
    <div class="compact-note">Algorithm se usa en la proxima simulacion salvo que apliques un preset. Cost base = tiempo de viaje.</div>
    <div class="row">
      <div><label title="Agentes que pueden estar a la vez dentro de una escalera o sus endpoints.">Stair capacity</label><input id="stairCapacity" type="number" min="1" step="1"></div>
      <div><label title="Agentes que pueden estar a la vez dentro de una rampa o sus endpoints.">Ramp capacity</label><input id="rampCapacity" type="number" min="1" step="1"></div>
    </div>
    <label title="single_file respeta capacidad fija; platoon permite estimar una fila interna segun la longitud de escalera/rampa.">Stair/ramp flow</label>
    <select id="linearTransferFlowMode"><option value="single_file">single_file</option><option value="platoon">platoon</option></select>
    <div class="compact-note">single_file = uno-a-uno; platoon = fila interna lenta en escaleras/rampas largas.</div>
    <label><input id="useBeaconRisk" type="checkbox" style="width:auto"> Beacon safety affects routing</label>
    <label><input id="includeGeometryQa" type="checkbox" style="width:auto"> Geometry QA</label>
    <h2>Agents</h2>
    <div class="tabs">
      <button id="autoTab" class="active" type="button">Automatic</button>
      <button id="manualTab" type="button">Manual</button>
    </div>
    <section id="autoPanel" class="tab-panel">
      <label>Agents</label><input id="agentCount" type="number">
      <label>Profile</label><select id="autoProfile"></select>
      <label>Spawn cell</label>
      <select id="spawnCell"></select>
      <div class="row">
        <div><label>Spawn X</label><input id="spawnX" type="number" step="0.05"></div>
        <div><label>Spawn Y</label><input id="spawnY" type="number" step="0.05"></div>
      </div>
      <label>Group distribution</label>
      <select id="distribution"><option>random_within_space</option><option>fixed</option></select>
      <div class="compact-note">Spawn X/Y solo fija el punto si eliges fixed; random_within_space reparte dentro de la celda.</div>
      <div class="row">
        <button id="setAutoBatch" type="button" title="Add this batch as visible manual agents. Repeat in several cells without deleting previous agents.">SET batch</button>
        <button id="deleteAutoBatch" type="button" title="Delete manual agents currently assigned to the selected spawn cell.">DELETE cell</button>
      </div>
      <div class="compact-note" id="agentHint">Click a room to select automatic spawn. Run uses the visible batch; SET batch stores it as manual agents.</div>
    </section>
    <section id="manualPanel" class="tab-panel" hidden>
      <div class="row">
        <div><label>Click profile</label><select id="placementProfile"></select></div>
        <div><label>Click placement</label><button id="placementMode" type="button">On</button></div>
      </div>
      <button id="clearManualAgents" type="button">Clear manual agents</button>
      <textarea id="manualAgents"></textarea>
    </section>
    <h2>Beacons</h2>
    <div class="row">
      <div><label>Beacon id</label><input id="beaconId" placeholder="auto"></div>
      <div><label>Selected</label><select id="beaconSelect"></select></div>
    </div>
    <div class="row">
      <div><label>Mount surface</label><select id="beaconSurface"><option value="ceiling">ceiling</option><option value="wall">wall</option><option value="floor">floor</option><option value="free">free</option></select></div>
      <div><label>Sensor</label><input id="beaconSensor" value="smoke"></div>
    </div>
    <div class="row">
      <div><label title="0 means safe; 1 means fully unsafe for routing. Saved internally as riskPenalty.">Safety loss</label><input id="beaconRisk" type="number" min="0" max="1" step="0.05" value="0.4"></div>
      <div><label>Radius m</label><input id="beaconRadius" type="number" min="0" step="0.1" value="3"></div>
    </div>
    <div class="row">
      <div><label>Inner radius m</label><input id="beaconInnerRadius" type="number" min="0" step="0.1" value="0"></div>
      <div><label title="Block the affected space when safety loss reaches this value.">Block at loss</label><input id="beaconBlockThreshold" type="number" min="0" max="1" step="0.05" value="0.85"></div>
    </div>
    <div class="row">
      <div><label>Click placement</label><button id="beaconPlacementMode" type="button">Off</button></div>
      <div><label>Curve edit</label><button id="clearBeaconCurvePoint" type="button">Delete point</button></div>
    </div>
    <div class="row">
      <button id="newBeacon" type="button">New beacon</button>
      <button id="saveBeacon" type="button">Save/update beacon</button>
    </div>
    <div class="row">
      <button id="deleteBeacon" type="button">Delete selected</button>
      <button id="refreshBeaconPreview" type="button">Refresh preview</button>
    </div>
    <div class="muted" id="beaconHint">Click placement lets you drop a beacon on the selected level, including wall or column geometry.</div>
    <label>Safety loss curve preview</label>
    <canvas id="beaconCurve" class="mini-canvas"></canvas>
    <label>timeS -> safety loss points</label>
    <textarea id="beaconCurvePoints" placeholder="0, 0.1&#10;30, 0.7&#10;90, 0.2"></textarea>
    <div class="row">
      <button id="seedBeaconCurve" type="button">Seed duration</button>
      <button id="applyBeaconCurve" type="button">Generate events</button>
    </div>
    <div id="beaconImpact" class="status-box">Beacon impact preview will appear after the model loads.</div>
    <textarea id="beacons"></textarea>
    <h2>Routing Experiments</h2>
    <div class="muted">Presets are complete routing strategies. Apply one, run it visually, or compare several with the same agents and beacons.</div>
    <div class="row">
      <div><label title="Predefined routing strategy. Apply copies its parameters into the controls.">Preset strategy</label><select id="routingPreset"></select></div>
      <div><label title="Copies the selected strategy into the editable routing controls.">Use this preset</label><button id="applyRoutingPreset" type="button">Apply preset</button></div>
    </div>
    <div class="row">
      <button id="runRoutingPreset" type="button" title="Apply the selected preset first, then run it in the canvas.">Apply preset + run</button>
      <button id="compareRoutingPresets" type="button" title="Run checked presets on the current agents, beacons and scenario.">Compare checked</button>
    </div>
    <div class="compact-note">Run simulation usa los selectores actuales. Apply preset + run cambia esos selectores al preset antes de simular.</div>
    <label>Presets to compare</label>
    <div id="routingPresetChecks" class="check-list"></div>
    <details id="cerDebugSection">
      <summary>Advanced safety/cost parameters</summary>
      <div class="compact-note" id="routingParameterStatus"></div>
      <div class="row">
        <div><label title="Formula used to convert travel time and safety loss into an edge weight.">Safety-cost model</label><select id="riskCostModel"><option>legacy_additive</option><option>multiplicative_beta</option><option>linear_time_risk</option></select></div>
        <div><label title="How space safety is mapped onto directed edges when there is no connection-specific value.">Safety source</label><select id="riskEndpointPolicy"><option>target</option><option>source</option><option>mean</option><option>min</option><option>max</option></select></div>
      </div>
      <div class="row">
        <label><input id="useHazardRisk" type="checkbox" style="width:auto"> Hazard safety affects routes</label>
        <label><input id="useCongestion" type="checkbox" style="width:auto"> Congestion affects routes</label>
      </div>
      <div class="row">
        <label><input id="riskEdgePrecedence" type="checkbox" style="width:auto"> Connection value first</label>
        <div><label title="Informative combined safety-loss value in route breakdowns.">Safety-loss aggregation</label><select id="riskAggregation"><option>sum</option><option>max</option><option>mean</option></select></div>
      </div>
      <div class="row three">
        <div><label title="Weight of the base time/distance component.">alpha</label><input id="riskAlpha" type="number" min="0" step="0.05" value="1"></div>
        <div><label title="Weight of hazard safety loss.">hazard beta</label><input id="hazardBeta" type="number" min="0" step="0.05" value="1"></div>
        <div><label title="Weight of beacon safety loss.">beacon beta</label><input id="beaconBeta" type="number" min="0" step="0.05" value="1"></div>
      </div>
      <div class="row">
        <div><label title="Safety-loss to cost conversion used by linear_time_risk.">safety unit cost</label><input id="riskUnitCost" type="number" min="0" step="0.05" value="1"></div>
        <div><label title="Policy that selects a candidate route after the search algorithm generates candidates.">Route selection</label><select id="routeSelection"><option>lowest_cost</option><option>highest_robustness</option><option>highest_agility</option><option>robust_agility</option><option>cer_weighted</option><option>cer_agility_yen</option></select></div>
      </div>
      <div class="row three">
        <div><label title="Number of candidate routes for Yen/advanced policies.">k routes</label><input id="kShortestPaths" type="number" min="1" step="1" value="6"></div>
        <div><label title="Allowed extra cost versus the cheapest candidate.">cost tolerance</label><input id="candidateCostTolerance" type="number" min="0" step="0.05" value="0.35"></div>
        <div><label title="Allowed detour when checking alternatives after an edge failure.">robust tolerance</label><input id="robustnessTolerance" type="number" min="0" step="0.05" value="0.2"></div>
      </div>
      <div class="row three">
        <div><label title="Allowed extra cost when counting efficient alternatives for evacuation centrality.">CE tolerance</label><input id="centralityTolerance" type="number" min="0" step="0.05" value="0.35"></div>
        <div><label title="Maximum paths considered when estimating evacuation centrality.">CE paths</label><input id="centralityMaxPaths" type="number" min="1" step="1" value="8"></div>
        <div><label title="Maximum overlap allowed between centrality paths.">CE overlap</label><input id="centralityMaxOverlap" type="number" min="0" max="1" step="0.05" value="0.8"></div>
      </div>
      <div><label title="How node centrality is summarized into route agility.">Agility aggregation</label><select id="agilityAggregation"><option>mean</option><option>geometric</option></select></div>
      <div class="row three">
        <div><label title="Cost weight for robust_agility selection.">cost weight</label><input id="costWeight" type="number" min="0" step="0.05" value="1"></div>
        <div><label title="Robustness weight for robust_agility selection.">robust weight</label><input id="robustnessWeight" type="number" min="0" step="0.05" value="0.35"></div>
        <div><label title="Agility weight for robust_agility selection.">agility weight</label><input id="agilityWeight" type="number" min="0" step="0.05" value="0.35"></div>
      </div>
      <div class="row">
        <div><label title="Centrality family used by agility policies.">centrality type</label><select id="centralityType"><option>legacy</option><option>rerouting</option></select></div>
        <label><input id="reroutingUseStructuralPrecompute" type="checkbox" style="width:auto" checked> structural CER precompute</label>
      </div>
      <div class="row three">
        <div><label title="Failure profiles separated by semicolon, e.g. 1;1,1;2.">CER profiles</label><input id="reroutingFailureProfiles" type="text" value="1;1,1"></div>
        <div><label title="CER tolerance: Cmax = (1 + tau) * C0.">CER tolerance</label><input id="reroutingCostTolerance" type="number" min="0" step="0.05" value="0.35"></div>
        <div><label title="Physical unit removed during CER failures.">failure unit</label><select id="reroutingFailureUnit"><option>resource</option><option>arc</option><option>undirected_pair</option><option>cell</option></select></div>
      </div>
      <div class="row three">
        <div><label title="Distinctness policy for alternative routes.">distinctness</label><select id="reroutingDistinctnessPolicy"><option>exact</option><option>overlap</option></select></div>
        <div><label title="Maximum CER failure combinations per computation.">CER max cases</label><input id="reroutingMaxCombinations" type="number" min="1" step="1" value="500"></div>
        <div><label title="Maximum CER computation time in milliseconds.">CER max ms</label><input id="reroutingMaxRuntimeMs" type="number" min="1" step="50" value="1000"></div>
      </div>
    </details>
    <details>
      <summary>Routing notes</summary>
      <pre class="status-box">Safety = 1 means usable. Safety = 0 means unsafe.
Safety loss = 1 - safety; internally this is stored as riskPenalty.
C(e) = alpha*time(e) + beta*safety_loss(e)
Dijkstra/A*/Floyd-Warshall: one best path under the current scalar cost
Yen: k candidate paths, then a policy chooses one
Robustness: path keeps alternatives if one connection fails
Agility: path crosses spaces with more evacuation alternatives
CER: rerouting centrality counts acceptable distinct alternatives after resource failures</pre>
    </details>
    <details>
      <summary>CER visual debug</summary>
      <div class="muted">Exports an auditable CER trace on the transfer-to-transfer backbone. Use transfer nodes as origin; the target is normally an exit transfer.</div>
      <div class="row">
        <div><label title="Transfer node where the CER explanation starts.">CER origin transfer</label><select id="cerOrigin"></select></div>
        <div><label title="Exit or target transfer evaluated by CER.">CER target exit</label><select id="cerTarget"></select></div>
      </div>
      <div class="row">
        <div><label>CER profile</label><select id="cerProfile"></select></div>
        <label><input id="cerGif" type="checkbox" style="width:auto" checked> GIF</label>
        <label><input id="cerDynamic" type="checkbox" style="width:auto"> dynamic snapshot</label>
      </div>
      <div class="row">
        <button id="pickCerOrigin" type="button" title="Click the canvas to choose the nearest transfer node as CER origin.">Pick origin</button>
        <button id="pickCerTarget" type="button" title="Click the canvas near an exit/transfer to choose the CER target.">Pick target</button>
      </div>
      <div id="cerPickStatus" class="compact-note">Open this panel to show transfer nodes on the canvas.</div>
      <button id="saveCerDebug" type="button">Save CER debug</button>
      <div id="cerResults" class="status-box">CER exports will appear here.</div>
    </details>
    <div id="routingResults" class="status-box">Choose a preset to see what it does, or compare checked presets.</div>
    <button id="saveRoutingComparison" type="button">Save comparison viewer</button>
    <h2>Dynamic Events</h2>
    <textarea id="events"></textarea>
    <h2>Run & Record</h2>
    <button id="run">Run simulation</button>
    <div class="compact-note">Este boton NO aplica presets: usa Algorithm, Cost y parametros tal como esten ahora.</div>
    <div class="row">
      <label><input id="recordGif" type="checkbox" style="width:auto" checked> GIF</label>
      <label><input id="recordHtml" type="checkbox" style="width:auto" checked> HTML viewer</label>
    </div>
    <div class="row">
      <div><label>GIF fps</label><input id="recordFps" type="number" min="1" max="30" step="1" value="8"></div>
      <div><label>Max frames</label><input id="recordMaxFrames" type="number" min="1" step="1" placeholder="optional"></div>
    </div>
    <button id="recordSimulation" type="button">Save GIF/HTML</button>
  </aside>
  <main>
    <canvas id="canvas"></canvas>
    <div>
      <div class="toolbar">
        <button id="play">Play</button>
        <button id="reset">Reset</button>
        <label>Level</label><select id="level"></select>
        <label>Playback ms/frame</label><input id="playbackMs" type="number" min="20" step="10" value="80">
        <label>Frame</label><input id="frame" type="range" min="0" max="0" value="0">
      </div>
      <div class="run-panel">
        <div class="route-cost-wrap">
          <div>
            <strong>Estimated total evacuation time</strong>
            <div id="routeCostStatus" class="compact-note">Run a simulation to inspect ETA over replans.</div>
          </div>
          <canvas id="routeCostChart" class="route-cost-chart"></canvas>
        </div>
        <pre id="metrics">Run a simulation to see metrics and QA.</pre>
      </div>
    </div>
  </main>
</div>
<script>
const qs = new URLSearchParams(location.search);
const defaultScenario = qs.get("scenario") || "__DEFAULT_SCENARIO__";
const defaultIndoor = qs.get("indoor") || "__DEFAULT_INDOOR__";
const defaultLibraryRoot = "__DEFAULT_LIBRARY_ROOT__";
const workbenchSession = qs.get("session") || "manual";
const $ = id => document.getElementById(id);
let model = null, payload = null, currentFrame = 0, timer = null, trajectoryByAgent = new Map();
let beaconDraftMode = true;
let draggedCurvePointIndex = null;
let selectedCurvePointIndex = null;
let routingPresets = {};
let cerPickMode = null;
$("scenarioPath").value = defaultScenario;
$("indoorPath").value = defaultIndoor;
const profileColors = { MP_WALKING: "#006dff", MP_WALKING_VERTICAL: "#006dff", MP_WALKING_ROLLING: "#0891b2", MP_ROLLING_ACCESSIBLE: "#c026d3", MP_ELDERLY: "#16a34a", MP_CHILD: "#f59e0b" };
const statusColors = { active: "#006dff", evacuated: "#1a9f52", no_route: "#c0392b", trapped: "#8e44ad" };
const canvas = $("canvas"), ctx = canvas.getContext("2d");
const routeCostChart = $("routeCostChart"), routeCostCtx = routeCostChart.getContext("2d");
const beaconCurve = $("beaconCurve"), beaconCurveCtx = beaconCurve.getContext("2d");

const sectionDescriptions = {
  "Open": "Carga un modelo/scenario y guarda configuraciones nuevas.",
  "Simulation": "Duracion, destino, algoritmo base y QA.",
  "Agents": "Colocacion automatica por sala o manual con clics.",
  "Beacons": "Balizas, curva temporal de seguridad y bloqueo.",
  "Routing Experiments": "Presets, comparativas y parametros de recomendacion.",
  "Dynamic Events": "Eventos JSON generados por balizas u otras fuentes.",
  "Run & Record": "Previsualiza, reproduce y exporta HTML/GIF."
};
const defaultOpenSections = new Set(["Open", "Simulation", "Agents", "Run & Record"]);

function setupSidebarSections() {
  const aside = document.querySelector("aside");
  if (!aside || aside.dataset.sectionsReady) return;
  aside.dataset.sectionsReady = "true";
  const headings = [...aside.querySelectorAll(":scope > h2")];
  for (const heading of headings) {
    const title = heading.textContent.trim();
    const details = document.createElement("details");
    details.className = "section";
    details.open = defaultOpenSections.has(title);
    const summary = document.createElement("summary");
    summary.innerHTML = `${escapeHtml(title)}<span class="section-description">${escapeHtml(sectionDescriptions[title] || "")}</span>`;
    details.appendChild(summary);
    let node = heading.nextSibling;
    heading.replaceWith(details);
    while (node && !(node.nodeType === Node.ELEMENT_NODE && node.tagName === "H2")) {
      const next = node.nextSibling;
      details.appendChild(node);
      node = next;
    }
  }
}

function setControlDisabled(id, disabled, reason = "") {
  const el = $(id);
  if (!el) return;
  el.disabled = Boolean(disabled);
  if (disabled && reason) el.title = reason;
  else if (el.dataset.originalTitle != null) el.title = el.dataset.originalTitle;
}

function rememberControlTitles() {
  document.querySelectorAll("input, select, textarea, button").forEach(el => {
    if (el.dataset.originalTitle == null) el.dataset.originalTitle = el.title || "";
  });
}

async function loadLibrary() {
  const res = await fetch(`/api/library?root=${encodeURIComponent(defaultLibraryRoot)}`);
  const library = await res.json();
  if (library.error) throw new Error(library.error);
  fillSelect($("libraryScenario"), library.scenarios || [], item => `${item.name} - ${item.path}`, item => item.path, "No scenarios found");
  fillSelect($("libraryIndoor"), library.indoorModels || [], item => `${item.name} - ${item.path}`, item => item.path, "No indoor models found");
  if ([...$("libraryScenario").options].some(option => option.value === $("scenarioPath").value)) $("libraryScenario").value = $("scenarioPath").value;
  if ([...$("libraryIndoor").options].some(option => option.value === $("indoorPath").value)) $("libraryIndoor").value = $("indoorPath").value;
}

async function openLibraryScenario() {
  const selected = $("libraryScenario").value;
  if (!selected) return;
  $("scenarioPath").value = selected;
  $("indoorPath").value = "";
  await loadModel();
}

async function openLibraryIndoor() {
  const selected = $("libraryIndoor").value;
  if (!selected) return;
  $("metrics").textContent = "Creating/opening baseline scenario...";
  const res = await fetch(`/api/baseline-scenario?indoor=${encodeURIComponent(selected)}`);
  const baseline = await res.json();
  if (baseline.error) throw new Error(baseline.error);
  $("scenarioPath").value = baseline.scenarioPath;
  $("indoorPath").value = "";
  await loadLibrary();
  await loadModel();
}

async function openModelScenario() {
  const selected = $("modelScenario").value;
  if (!selected) return;
  $("scenarioPath").value = selected;
  $("indoorPath").value = "";
  await loadModel();
}

async function saveScenario() {
  const request = buildSimulationRequest();
  request.saveName = $("scenarioSaveName").value.trim() || scenarioNameFromPath($("scenarioPath").value);
  $("metrics").textContent = "Saving scenario...";
  const res = await fetch("/api/save-scenario", { method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(request) });
  const saved = await res.json();
  if (saved.error) throw new Error(saved.error);
  $("scenarioPath").value = saved.scenarioPath;
  $("indoorPath").value = "";
  await loadLibrary();
  await loadModel();
  $("metrics").textContent = `Scenario saved: ${saved.scenarioPath}\\nOutputs: ${saved.outputFolder}`;
}

async function recordSimulation() {
  const request = buildSimulationRequest();
  request.render = {
    gif: $("recordGif").checked,
    html: $("recordHtml").checked,
    fps: Number($("recordFps").value || 8),
    maxFrames: $("recordMaxFrames").value ? Number($("recordMaxFrames").value) : null,
    level: $("level").value || null,
  };
  $("metrics").textContent = "Running and saving GIF/HTML...";
  const res = await fetch("/api/render", { method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(request) });
  const rendered = await res.json();
  if (rendered.error) throw new Error(rendered.error);
  $("metrics").textContent = JSON.stringify({
    outputDir: rendered.outputDir,
    gif: rendered.gif,
    html: rendered.html,
    metrics: rendered.metrics,
    qa: rendered.qa,
  }, null, 2);
}

async function saveRoutingComparison() {
  const presetIds = selectedRoutingPresetIds();
  if (!presetIds.length) {
    $("routingResults").textContent = "Select at least one preset.";
    return;
  }
  const request = buildSimulationRequest();
  request.presetIds = presetIds;
  $("routingResults").textContent = "Saving routing comparison...";
  const res = await fetch("/api/save-routing-comparison", { method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(request) });
  const comparison = await res.json();
  if (comparison.error) throw new Error(comparison.error);
  $("routingResults").textContent = `${formatRoutingComparison(comparison)}\\n\\nSaved:\\n${comparison.html}\\n${comparison.metricsCsv}\\n${comparison.routesCsv}`;
}

async function saveCerDebug() {
  const request = buildSimulationRequest();
  request.cer = {
    origin: $("cerOrigin").value,
    target: $("cerTarget").value,
    profile: $("cerProfile").value || $("autoProfile").value,
    formats: $("cerGif").checked ? ["json", "png", "html", "gif"] : ["json", "png", "html"],
    gif: $("cerGif").checked,
    dynamic: $("cerDynamic").checked,
    level: $("level").value || null,
    fps: 2,
    maxFrames: 120,
  };
  if (!request.cer.origin) {
    $("cerResults").textContent = "Select a CER origin transfer first.";
    return;
  }
  if (!request.cer.target) {
    $("cerResults").textContent = "Select a CER target exit/transfer first.";
    return;
  }
  $("cerResults").textContent = "Generating CER debug artifacts...";
  const res = await fetch("/api/cer-export", { method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(request) });
  const exported = await res.json();
  if (exported.error) throw new Error(exported.error);
  $("cerResults").textContent = JSON.stringify({
    outputDir: exported.outputDir,
    origin: exported.origin,
    target: exported.target,
    graphView: exported.graphView,
    snapshot: exported.snapshot,
    outputs: exported.outputs,
    nodeSummary: exported.nodeSummary,
  }, null, 2);
}

async function loadModel() {
  $("summary").textContent = "Loading model...";
  $("sessionInfo").textContent = `session ${workbenchSession} | loading`;
  const indoor = $("indoorPath").value.trim() ? `&indoor=${encodeURIComponent($("indoorPath").value.trim())}` : "";
  const res = await fetch(`/api/model?scenario=${encodeURIComponent($("scenarioPath").value)}${indoor}`);
  if (!res.ok) throw new Error(`Could not load model: HTTP ${res.status}`);
  model = await res.json();
  if (model.error) throw new Error(model.error);
  $("summary").textContent = `${model.scenarioId} | ${model.levels.join(", ")}`;
  $("sessionInfo").textContent = `session ${workbenchSession} | loaded ${new Date().toLocaleTimeString()}`;
  fillSelect($("modelScenario"), model.relatedScenarios || [], item => `${item.label || item.name || item.path} - ${item.path}`, item => item.path, "No scenarios for this model");
  if ([...$("modelScenario").options].some(option => option.value === model.scenarioPath)) $("modelScenario").value = model.scenarioPath;
  $("scenarioSaveName").value = scenarioNameFromPath(model.scenarioPath);
  const spawnable = model.cells.filter(isSpawnableCell);
  fillSelect($("spawnCell"), spawnable, c => `${c.level} ${c.id} [${c.x}, ${c.y}]`, c => c.id);
  fillSelect($("destinationCell"), model.exits.length ? model.exits : model.cells, c => `${c.level} ${c.id}`, c => c.id);
  fillSelect($("level"), model.levels.map(level => ({id: level, label: levelLabel(level, null)})), c => c.label, c => c.id);
  fillSelect($("placementProfile"), model.profiles.map(profile => ({id: profile})), c => c.id, c => c.id);
  fillSelect($("autoProfile"), model.profiles.map(profile => ({id: profile})), c => c.id, c => c.id);
  const cerOrigins = cerOriginOptions();
  const cerTargets = cerTargetOptions();
  fillSelect($("cerOrigin"), cerOrigins, cerNodeLabel, c => c.id, "No transfer nodes");
  fillSelect($("cerTarget"), cerTargets, cerNodeLabel, c => c.id, "No exit transfers");
  fillSelect($("cerProfile"), model.profiles.map(profile => ({id: profile})), c => c.id, c => c.id);
  $("timeStep").value = model.config.timeStepS;
  $("maxSteps").value = model.config.maxSteps;
  $("stairCapacity").value = model.config.stairCapacity ?? 1;
  $("rampCapacity").value = model.config.rampCapacity ?? 1;
  $("linearTransferFlowMode").value = model.config.linearTransferFlowMode || "single_file";
  $("seed").value = model.config.randomSeed;
  $("agentCount").value = model.config.firstGroupCount;
  $("spawnCell").value = spawnable.some(c => c.id === model.config.firstSpawnCell)
    ? model.config.firstSpawnCell
    : ((spawnable[0] && spawnable[0].id) || "");
  const spawn = model.config.firstSpawnPosition || selectedCellPoint($("spawnCell").value);
  $("spawnX").value = spawn ? spawn[0] : "";
  $("spawnY").value = spawn ? spawn[1] : "";
  $("distribution").value = model.config.firstGroupDistribution || "random_within_space";
  $("destinationMode").value = "scenario";
  $("destinationCell").value = model.config.destinationCells[0] || (model.exits[0] && model.exits[0].id) || "";
  const defaultCerOrigin = nearestTransferForCell($("spawnCell").value, node => !node.isExit);
  if (defaultCerOrigin) $("cerOrigin").value = defaultCerOrigin.id;
  const configuredTarget = cerTargets.find(node => node.id === $("destinationCell").value);
  if (configuredTarget) $("cerTarget").value = configuredTarget.id;
  $("cerProfile").value = $("autoProfile").value || $("cerProfile").value;
  $("algorithm").value = model.config.algorithm;
  $("costPolicy").value = model.config.costPolicy;
  routingPresets = model.routingPresets || {};
  populateRoutingPresets();
  applyRoutingConfigToControls(model.config || {});
  $("useBeaconRisk").checked = Boolean(model.config.useBeaconRisk);
  $("beaconBlockThreshold").value = String(model.config.beaconBlockThreshold ?? 0.85);
  $("manualAgents").value = JSON.stringify(model.manualAgents.length ? model.manualAgents : [], null, 2);
  $("beacons").value = JSON.stringify(model.beacons, null, 2);
  $("events").value = JSON.stringify(model.scheduledEvents, null, 2);
  refreshBeaconSelect();
  loadSelectedBeacon();
  payload = null;
  $("metrics").textContent = "Scenario loaded. Configure values on the left, then press Run simulation.";
  updateDurationHint();
  drawModelPreview();
  drawBeaconCurve();
  updateControlAvailability();
}
function fillSelect(select, rows, labelFn, valueFn, emptyLabel = "No options") {
  select.innerHTML = "";
  if (!rows.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyLabel;
    select.appendChild(option);
    return;
  }
  for (const row of rows) {
    const option = document.createElement("option");
    option.value = valueFn(row); option.textContent = labelFn(row);
    option.title = option.textContent;
    select.appendChild(option);
  }
}
function scenarioNameFromPath(path) {
  const clean = String(path || "").replace(/\\\\/g, "/").split("/").pop() || "";
  return clean.replace(/\\.json$/i, "") || "baseline";
}
function levelLabel(level, counts) {
  const count = counts && counts[level] ? counts[level] : 0;
  return count ? `${level} (${count} agents)` : level;
}
function updateLevelOptions(counts) {
  const current = $("level").value;
  fillSelect($("level"), model.levels.map(level => ({id: level, label: levelLabel(level, counts)})), c => c.label, c => c.id);
  if (current) $("level").value = current;
}
async function runSimulation() {
  const request = buildSimulationRequest();
  $("metrics").textContent = "Running...";
  const res = await fetch("/api/run", { method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(request) });
  payload = await res.json();
  if (payload.error) throw new Error(payload.error);
  buildTrajectoryIndex();
  currentFrame = 0;
  $("frame").max = String(Math.max(...payload.trajectories.map(r => r.step)) * 4);
  const firstRows = payload.trajectories.filter(r => r.step === 0);
  const levelCounts = {};
  for (const row of firstRows) levelCounts[row.levelRef] = (levelCounts[row.levelRef] || 0) + 1;
  updateLevelOptions(levelCounts);
  const bestLevel = Object.entries(levelCounts).sort((a,b) => b[1]-a[1])[0];
  if (bestLevel && bestLevel[0]) $("level").value = bestLevel[0];
  $("metrics").textContent = JSON.stringify({ metrics: payload.metrics, qa: payload.qa, routeDebug: routeDebugSummary(payload), routeCost: routeCostSummary() }, null, 2);
  updateBeaconImpactPreview();
  draw();
}
function routeDebugSummary(data) {
  const route = routeForDebug(null, 0);
  if (!route) return null;
  const breakdown = route.weightBreakdown || {};
  return {
    agentId: route.agentId || null,
    profileId: route.profileId || null,
    reachable: route.reachable,
    totalCost: route.totalCost,
    algorithm: route.algorithm,
    costPolicy: route.costPolicy,
    firstStep: breakdown.firstStep || null,
    originCandidates: breakdown.originCandidates || [],
    nodeSequence: route.nodeSequence || [],
  };
}
function routeCostSummary() {
  const route = routeForDebug($("level").value || null, currentFrame);
  if (!route) return null;
  const history = routeCostHistory(route.agentId);
  if (!history.length) return null;
  const current = latestRouteCostAt(history, currentPreviewTimeS()) || history[history.length - 1];
  const first = history[0];
  const etaValues = history.map(item => item.etaTotal);
  const increases = history.slice(1).filter((item, index) => item.etaTotal > history[index].etaTotal + 1e-6);
  return {
    agentId: route.agentId,
    algorithm: current.algorithm || route.algorithm,
    samples: history.length,
    currentTimeS: Number(currentPreviewTimeS().toFixed(3)),
    currentRouteStep: current.step,
    currentRouteTimeS: current.timeS,
    remainingRouteCostS: current.totalCost,
    estimatedTotalEvacuationS: current.etaTotal,
    etaDeltaFromFirstS: Number((current.etaTotal - first.etaTotal).toFixed(6)),
    minEstimatedTotalEvacuationS: Number(Math.min(...etaValues).toFixed(6)),
    maxEstimatedTotalEvacuationS: Number(Math.max(...etaValues).toFixed(6)),
    etaIncreases: increases.length,
  };
}
function buildSimulationRequest() {
  const routing = routingConfigFromControls();
  const request = {
    scenarioPath: $("scenarioPath").value,
    indoorPath: $("indoorPath").value.trim() || null,
    config: {
      timeStepS: Number($("timeStep").value),
      maxSteps: Number($("maxSteps").value),
      stairCapacity: Math.max(1, Math.round(numberFromInput("stairCapacity", 1))),
      rampCapacity: Math.max(1, Math.round(numberFromInput("rampCapacity", 1))),
      linearTransferFlowMode: $("linearTransferFlowMode").value,
      randomSeed: Number($("seed").value),
      firstGroupCount: Number($("agentCount").value),
      firstSpawnCell: $("spawnCell").value,
      firstSpawnPosition: [Number($("spawnX").value), Number($("spawnY").value)],
      firstGroupDistribution: $("distribution").value,
      destinationCells: destinationCellsForRun(),
      ...routing,
      beaconBlockThreshold: Number($("beaconBlockThreshold").value),
      includeGeometryQa: $("includeGeometryQa").checked
    },
    manualAgents: activeAgentMode() === "manual" ? readManualAgents() : automaticAgentsFromControls(),
    beacons: JSON.parse($("beacons").value || "[]"),
    scheduledEvents: JSON.parse($("events").value || "[]")
  };
  return request;
}
function routingConfigFromControls() {
  return {
    algorithm: $("algorithm").value,
    costPolicy: $("costPolicy").value,
    useHazardRisk: $("useHazardRisk").checked,
    useBeaconRisk: $("useBeaconRisk").checked,
    useCongestion: $("useCongestion").checked,
    riskCostModel: $("riskCostModel").value,
    riskEndpointPolicy: $("riskEndpointPolicy").value,
    riskEdgePrecedence: $("riskEdgePrecedence").checked,
    riskAggregation: $("riskAggregation").value,
    riskAlpha: numberFromInput("riskAlpha", 1),
    hazardBeta: numberFromInput("hazardBeta", 1),
    beaconBeta: numberFromInput("beaconBeta", 1),
    riskUnitCost: numberFromInput("riskUnitCost", 1),
    routeRecommendation: {
      routeSelection: $("routeSelection").value,
      kShortestPaths: Math.max(1, Math.round(numberFromInput("kShortestPaths", 6))),
      candidateCostTolerance: numberFromInput("candidateCostTolerance", 0.35),
      robustnessTolerance: numberFromInput("robustnessTolerance", 0.2),
      centralityTolerance: numberFromInput("centralityTolerance", 0.35),
      centralityMaxPaths: Math.max(1, Math.round(numberFromInput("centralityMaxPaths", 8))),
      centralityMaxOverlap: clamp(numberFromInput("centralityMaxOverlap", 0.8), 0, 1),
      costWeight: numberFromInput("costWeight", 1),
      robustnessWeight: numberFromInput("robustnessWeight", 0.35),
      agilityWeight: numberFromInput("agilityWeight", 0.35),
      agilityAggregation: $("agilityAggregation").value,
      centralityType: $("centralityType").value,
      reroutingEnabled: $("centralityType").value === "rerouting" || $("routeSelection").value.startsWith("cer_"),
      reroutingFailureProfiles: parseReroutingProfiles($("reroutingFailureProfiles").value),
      reroutingCostTolerance: numberFromInput("reroutingCostTolerance", 0.35),
      reroutingFailureUnit: $("reroutingFailureUnit").value,
      reroutingDistinctnessPolicy: $("reroutingDistinctnessPolicy").value,
      reroutingMaxCombinations: Math.max(1, Math.round(numberFromInput("reroutingMaxCombinations", 500))),
      reroutingMaxRuntimeMs: Math.max(1, Math.round(numberFromInput("reroutingMaxRuntimeMs", 1000))),
      reroutingUseStructuralPrecompute: $("reroutingUseStructuralPrecompute").checked,
    }
  };
}
function applyRoutingConfigToControls(config) {
  const routeRecommendation = config.routeRecommendation || {};
  setIfPresent("algorithm", config.algorithm);
  setIfPresent("costPolicy", config.costPolicy);
  setIfPresent("riskCostModel", config.riskCostModel);
  setIfPresent("riskEndpointPolicy", config.riskEndpointPolicy);
  setIfPresent("riskAggregation", config.riskAggregation);
  setIfPresent("routeSelection", routeRecommendation.routeSelection);
  $("useHazardRisk").checked = config.useHazardRisk !== false;
  $("useBeaconRisk").checked = config.useBeaconRisk !== false;
  $("useCongestion").checked = Boolean(config.useCongestion);
  $("riskEdgePrecedence").checked = config.riskEdgePrecedence !== false;
  setNumberIfPresent("riskAlpha", config.riskAlpha);
  setNumberIfPresent("hazardBeta", config.hazardBeta);
  setNumberIfPresent("beaconBeta", config.beaconBeta);
  setNumberIfPresent("riskUnitCost", config.riskUnitCost);
  setNumberIfPresent("kShortestPaths", routeRecommendation.kShortestPaths);
  setNumberIfPresent("candidateCostTolerance", routeRecommendation.candidateCostTolerance);
  setNumberIfPresent("robustnessTolerance", routeRecommendation.robustnessTolerance);
  setNumberIfPresent("centralityTolerance", routeRecommendation.centralityTolerance);
  setNumberIfPresent("centralityMaxPaths", routeRecommendation.centralityMaxPaths);
  setNumberIfPresent("centralityMaxOverlap", routeRecommendation.centralityMaxOverlap);
  setNumberIfPresent("costWeight", routeRecommendation.costWeight);
  setNumberIfPresent("robustnessWeight", routeRecommendation.robustnessWeight);
  setNumberIfPresent("agilityWeight", routeRecommendation.agilityWeight);
  setIfPresent("agilityAggregation", routeRecommendation.agilityAggregation);
  setIfPresent("centralityType", routeRecommendation.centralityType);
  if (routeRecommendation.reroutingFailureProfiles) $("reroutingFailureProfiles").value = formatReroutingProfiles(routeRecommendation.reroutingFailureProfiles);
  setNumberIfPresent("reroutingCostTolerance", routeRecommendation.reroutingCostTolerance);
  setIfPresent("reroutingFailureUnit", routeRecommendation.reroutingFailureUnit);
  setIfPresent("reroutingDistinctnessPolicy", routeRecommendation.reroutingDistinctnessPolicy);
  setNumberIfPresent("reroutingMaxCombinations", routeRecommendation.reroutingMaxCombinations);
  setNumberIfPresent("reroutingMaxRuntimeMs", routeRecommendation.reroutingMaxRuntimeMs);
  $("reroutingUseStructuralPrecompute").checked = routeRecommendation.reroutingUseStructuralPrecompute !== false;
  updateRoutingParameterStatus();
  updateBeaconImpactPreview();
  updateCerPickStatus();
}
function parseReroutingProfiles(text) {
  return String(text || "1").split(";").map(part =>
    part.split(",").map(value => Math.max(1, Math.round(Number(value.trim()) || 0))).filter(Boolean)
  ).filter(profile => profile.length);
}
function formatReroutingProfiles(profiles) {
  return (profiles || [[1]]).map(profile => (profile || []).join(",")).join(";");
}
function setIfPresent(id, value) {
  if (value == null || !$(`${id}`)) return;
  const select = $(id);
  if ([...select.options].some(option => option.value === String(value))) select.value = String(value);
}
function setNumberIfPresent(id, value) {
  if (value != null && Number.isFinite(Number(value))) $(id).value = String(value);
}
function populateRoutingPresets() {
  const rows = Object.values(routingPresets).sort((a, b) => String(a.presetId).localeCompare(String(b.presetId)));
  fillSelect($("routingPreset"), rows, preset => `${preset.presetId} - ${preset.label || preset.presetId}`, preset => preset.presetId, "No presets");
  const selectedDefaults = new Set(["dijkstra_time", "floyd_warshall_time", "astar_risk_multiplicative", "yen_highest_robustness", "robust_agility", "cer_weighted"]);
  $("routingPresetChecks").innerHTML = rows.map(preset => {
    const id = String(preset.presetId);
    const checked = selectedDefaults.has(id) ? "checked" : "";
    const label = `${id} - ${preset.label || id}`;
    return `<label title="${escapeHtml(preset.description || label)}"><input type="checkbox" class="routingPresetCheck" value="${escapeHtml(id)}" ${checked}> <span>${escapeHtml(label)}</span></label>`;
  }).join("") || "<span class='muted'>No presets loaded</span>";
  document.querySelectorAll(".routingPresetCheck").forEach(input => input.addEventListener("change", updateControlAvailability));
  updateRoutingPresetInfo();
}
function selectedRoutingPresetIds() {
  return [...document.querySelectorAll(".routingPresetCheck:checked")].map(input => input.value);
}
function selectedRoutingPreset() {
  return routingPresets[$("routingPreset").value] || null;
}
function applySelectedRoutingPreset() {
  const preset = selectedRoutingPreset();
  if (!preset) return;
  applyRoutingConfigToControls(deepMerge(routingConfigFromControls(), preset.routing || {}));
  updateRoutingPresetInfo();
}
async function runSelectedRoutingPreset() {
  applySelectedRoutingPreset();
  await runSimulation();
}
async function compareSelectedRoutingPresets() {
  const presetIds = selectedRoutingPresetIds();
  if (!presetIds.length) {
    $("routingResults").textContent = "Select at least one preset.";
    return;
  }
  const request = buildSimulationRequest();
  request.presetIds = presetIds;
  $("routingResults").textContent = "Comparing routing presets...";
  const res = await fetch("/api/routing-compare", { method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(request) });
  const comparison = await res.json();
  if (comparison.error) throw new Error(comparison.error);
  $("routingResults").textContent = formatRoutingComparison(comparison);
}
function formatRoutingComparison(comparison) {
  const lines = ["preset | alg | evacuated | active | noRoute | plans | routeCost | planMs | robust | agility"];
  for (const row of comparison.runs || []) {
    lines.push([
      row.presetId,
      row.algorithm,
      row.evacuated,
      row.active,
      row.noRoute,
      row.routePlans,
      formatMetric(row.meanRouteCost),
      formatMetric(row.meanPlanningMs),
      formatMetric(row.meanRobustness),
      formatMetric(row.meanAgility),
    ].join(" | "));
  }
  return lines.join("\\n");
}
function updateRoutingPresetInfo() {
  const preset = selectedRoutingPreset();
  if (!preset) return;
  const routing = preset.routing || {};
  const recommendation = routing.routeRecommendation || {};
  $("routingResults").textContent =
    `${preset.presetId}\\n` +
    `${preset.label || ""}\\n` +
    `${preset.description || ""}\\n\\n` +
    `Algorithm: ${routing.algorithm || "scenario default"}\\n` +
    `Cost: ${routing.costPolicy || "scenario default"}\\n` +
    `Safety model: ${routing.riskCostModel || "legacy_additive"}\\n` +
    `Safety source: ${routing.riskEndpointPolicy || "target"}\\n` +
    `Selection: ${recommendation.routeSelection || "lowest_cost"}\\n` +
    `Beacon safety: ${routing.useBeaconRisk === false ? "off" : "on"} | Hazard safety: ${routing.useHazardRisk === false ? "off" : "on"} | Congestion: ${routing.useCongestion ? "on" : "off"}\\n\\n` +
    presetUseHint(preset) +
    `\\n\\nactive/ignored parameters\\n` +
    routingParameterWarnings(routing).join("\\n") +
    `\\n\\ntechnical patch\\n` +
    JSON.stringify(routing, null, 2);
  updateRoutingParameterStatus(routing);
}
function presetUseHint(preset) {
  const id = String(preset.presetId || "");
  if (id.includes("dijkstra_time")) return "Use it as the simplest baseline: shortest evacuation time without safety penalties.";
  if (id.includes("astar_time")) return "Use it to compare A* latency against Dijkstra while keeping the same time-only objective.";
  if (id.includes("risk_multiplicative")) return "Use it when beacon/hazard safety should bend routes away from unsafe spaces.";
  if (id.includes("yen_risk_lowest")) return "Use it to generate several candidate routes but still choose the cheapest safe one.";
  if (id.includes("robustness")) return "Use it when you prefer routes that keep alternatives if a connection fails.";
  if (id.includes("agility")) return "Use it when you prefer routes through spaces with more evacuation alternatives.";
  if (id.includes("congestion")) return "Use it when current crowding should penalize route choices.";
  return "Use this preset as a complete routing strategy. Apply it, then run or compare.";
}
function routingParameterWarnings(config = null) {
  const routing = config || routingConfigFromControls();
  const recommendation = routing.routeRecommendation || {};
  const algorithm = routing.algorithm || "dijkstra";
  const selection = recommendation.routeSelection || "lowest_cost";
  const notes = [`base cost: minimum_travel_time is always active`];
  notes.push(routing.useBeaconRisk === false ? "beacon beta inactive: beacon safety is off" : "beacon beta active when beacons affect spaces");
  notes.push(routing.useHazardRisk === false ? "hazard beta inactive: hazard safety is off" : "hazard beta active when hazards affect spaces");
  notes.push(routing.useCongestion ? "congestion penalty active" : "congestion penalty inactive");
  notes.push(routing.riskCostModel === "linear_time_risk" ? "safety unit cost active" : "safety unit cost ignored unless linear_time_risk is selected");
  const usesCandidates = algorithm === "yen_ksp" || algorithm === "robust_agility" || selection !== "lowest_cost";
  notes.push(usesCandidates ? "k/tolerance parameters active: candidate routes are evaluated" : "k/tolerance parameters ignored: single best route only");
  const usesRobustness = selection === "highest_robustness" || selection === "robust_agility" || algorithm === "robust_agility";
  notes.push(usesRobustness ? "robustness active: alternatives after edge failure are scored" : "robustness ignored for this selection");
  const usesAgility = selection === "highest_agility" || selection === "robust_agility" || selection === "cer_agility_yen" || selection === "cer_weighted" || algorithm === "robust_agility";
  const usesCer = selection.startsWith("cer_") || recommendation.centralityType === "rerouting";
  notes.push(usesAgility ? "CE/agility active: intermediate spaces with more alternatives are scored" : "CE/agility ignored for this selection");
  notes.push(usesCer ? "CER active: rerouting centrality is used for agility" : "CER inactive: legacy CE/agility or no centrality");
  return notes;
}
function updateRoutingParameterStatus(config = null) {
  if (!$("routingParameterStatus")) return;
  $("routingParameterStatus").textContent = routingParameterWarnings(config).join("\\n");
  updateControlAvailability();
}

function updateControlAvailability() {
  const distributionFixed = $("distribution").value === "fixed";
  setControlDisabled("spawnX", !distributionFixed, "Solo se usa con distribucion fixed.");
  setControlDisabled("spawnY", !distributionFixed, "Solo se usa con distribucion fixed.");
  const selectedDestination = $("destinationMode").value === "selected";
  setControlDisabled("destinationCell", !selectedDestination, "Se usa solo con Destination mode = Selected only.");

  const beaconRiskOn = $("useBeaconRisk").checked;
  setControlDisabled("beaconBlockThreshold", !beaconRiskOn, "Solo afecta al routing si Beacon safety esta activo.");
  setControlDisabled("beaconBeta", !beaconRiskOn, "Solo se usa si Beacon safety esta activo.");
  setControlDisabled("hazardBeta", !$("useHazardRisk").checked, "Solo se usa si Hazard safety esta activo.");
  setControlDisabled("riskUnitCost", $("riskCostModel").value !== "linear_time_risk", "Solo se usa con linear_time_risk.");

  const routing = routingConfigFromControls();
  const recommendation = routing.routeRecommendation || {};
  const algorithm = routing.algorithm || "dijkstra";
  const selection = recommendation.routeSelection || "lowest_cost";
  const usesCandidates = algorithm === "yen_ksp" || algorithm === "robust_agility" || selection !== "lowest_cost";
  const usesRobustness = selection === "highest_robustness" || selection === "robust_agility" || algorithm === "robust_agility";
  const usesAgility = selection === "highest_agility" || selection === "robust_agility" || selection === "cer_agility_yen" || selection === "cer_weighted" || algorithm === "robust_agility";
  const usesCer = selection.startsWith("cer_") || recommendation.centralityType === "rerouting";
  const usesWeightedSelection = selection === "robust_agility" || algorithm === "robust_agility";

  ["kShortestPaths", "candidateCostTolerance"].forEach(id => setControlDisabled(id, !usesCandidates, "Solo se usa con Yen, robust_agility o seleccion multicriterio."));
  ["robustnessTolerance", "robustnessWeight"].forEach(id => setControlDisabled(id, !usesRobustness, "Solo se usa en estrategias con robustez."));
  ["centralityTolerance", "centralityMaxPaths", "centralityMaxOverlap", "agilityAggregation", "agilityWeight"].forEach(id => setControlDisabled(id, !usesAgility, "Solo se usa en estrategias con agilidad/CE."));
  ["centralityType", "reroutingFailureProfiles", "reroutingCostTolerance", "reroutingFailureUnit", "reroutingDistinctnessPolicy", "reroutingMaxCombinations", "reroutingMaxRuntimeMs", "reroutingUseStructuralPrecompute"].forEach(id => setControlDisabled(id, !usesCer, "Solo se usa con politicas CER/rerouting."));
  setControlDisabled("costWeight", !usesWeightedSelection, "Solo se usa en robust_agility.");

  const hasPresetSelection = selectedRoutingPresetIds().length > 0;
  setControlDisabled("compareRoutingPresets", !hasPresetSelection, "Selecciona al menos un preset.");
  setControlDisabled("saveRoutingComparison", !hasPresetSelection, "Selecciona al menos un preset.");
  setControlDisabled("recordSimulation", !$("recordGif").checked && !$("recordHtml").checked, "Activa GIF o HTML viewer.");

  const hasManualAgents = readManualAgents().length > 0;
  setControlDisabled("deleteAutoBatch", !hasManualAgents, "No hay agentes manuales para borrar.");
}
function formatMetric(value) {
  return value == null ? "-" : Number(value).toFixed(3);
}
function deepMerge(base, patch) {
  const output = {...base};
  for (const [key, value] of Object.entries(patch || {})) {
    if (value && typeof value === "object" && !Array.isArray(value) && output[key] && typeof output[key] === "object" && !Array.isArray(output[key])) {
      output[key] = deepMerge(output[key], value);
    } else {
      output[key] = value;
    }
  }
  return output;
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}
function activeAgentMode() {
  return $("manualTab").classList.contains("active") ? "manual" : "automatic";
}
function setAgentMode(mode) {
  const manual = mode === "manual";
  $("manualTab").classList.toggle("active", manual);
  $("autoTab").classList.toggle("active", !manual);
  $("manualPanel").hidden = !manual;
  $("autoPanel").hidden = manual;
  payload = null;
  drawModelPreview();
  updateControlAvailability();
}
function updateDurationHint() {
  if (!$("durationHint")) return;
  const seconds = Math.max(0, numberFromInput("timeStep", 0) * numberFromInput("maxSteps", 0));
  const minutes = seconds / 60;
  $("durationHint").textContent = `Simulation window: ${seconds.toFixed(1)} s (${minutes.toFixed(2)} min)`;
}
function writeManualAgents(agents) {
  $("manualAgents").value = JSON.stringify(agents, null, 2);
  payload = null;
  drawModelPreview();
  updateControlAvailability();
}
function nextManualAgentId(agents) {
  const used = new Set(agents.map(agent => agent.agentId));
  for (let index = 1; index < 10000; index++) {
    const id = `MANUAL_${String(index).padStart(3, "0")}`;
    if (!used.has(id)) return id;
  }
  return `MANUAL_${Date.now()}`;
}
function addAutomaticBatchToManualAgents() {
  const generated = automaticAgentsFromControls();
  if (!generated.length) {
    $("metrics").textContent = "SET ignored: agents must be greater than 0.";
    return;
  }
  const agents = readManualAgents();
  for (const agent of generated) {
    agents.push({ ...agent, agentId: nextManualAgentId(agents) });
  }
  writeManualAgents(agents);
  setAgentMode("manual");
  $("metrics").textContent = `Added ${generated.length} visible agents around ${$("spawnCell").value}. Manual mode will be used for the next run.`;
}
function deleteManualAgentsInSelectedCell() {
  const cellId = $("spawnCell").value;
  const regionIds = new Set(spawnRegionSpaces(cellId).map(space => space.id));
  if (!regionIds.size) regionIds.add(cellId);
  const before = readManualAgents();
  const after = before.filter(agent => !regionIds.has(agent.initialCellSpaceRef));
  writeManualAgents(after);
  $("metrics").textContent = `Deleted ${before.length - after.length} manual agents around ${cellId}.`;
}
function automaticAgentsFromControls() {
  if (!model) return [];
  const cellId = $("spawnCell").value;
  const selectedSpace = model.spaces.find(space => space.id === cellId);
  if (!selectedSpace || !spaceIsSpawnable(selectedSpace)) return [];
  const count = Math.max(0, Math.round(numberFromInput("agentCount", 0)));
  const distribution = $("distribution").value;
  const fixed = [numberFromInput("spawnX", NaN), numberFromInput("spawnY", NaN)];
  const regionSpaces = distribution === "fixed" ? [selectedSpace] : spawnRegionSpaces(cellId);
  const spaces = regionSpaces.length ? regionSpaces : [selectedSpace];
  const agents = [];
  for (let index = 0; index < count; index++) {
    const point = distribution === "fixed" && Number.isFinite(fixed[0]) && Number.isFinite(fixed[1])
      ? fixed
      : spreadPointInRegion(spaces, index, count);
    const pointSpace = spaceAt(selectedSpace.level, point, "spawn") || selectedSpace;
    agents.push({
      agentId: `AUTO_${String(index + 1).padStart(3, "0")}`,
      mobilityProfileRef: $("autoProfile").value || model.profiles[0],
      initialCellSpaceRef: pointSpace.id,
      initialPosition: { type: "Point", coordinates: [Number(point[0].toFixed(3)), Number(point[1].toFixed(3))] }
    });
  }
  return agents;
}
function spreadPointInSpace(space, index, count) {
  return spreadPointInRegion([space], index, count);
}
function spreadPointInRegion(spaces, index, count) {
  const rings = spaces.map(space => ({ space, ring: (space.rings && space.rings[0]) || [] })).filter(item => item.ring.length);
  if (!rings.length) return spaceRepresentative(spaces[0]) || [0, 0];
  const xs = rings.flatMap(item => item.ring.map(point => point[0]));
  const ys = rings.flatMap(item => item.ring.map(point => point[1]));
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = Math.max(maxX - minX, 0.01);
  const height = Math.max(maxY - minY, 0.01);
  const columns = Math.max(1, Math.ceil(Math.sqrt(count * (width / height))));
  const rows = Math.max(1, Math.ceil(count / columns));
  const totalSlots = Math.max(count, columns * rows);
  for (let attempt = 0; attempt < totalSlots * 3; attempt++) {
    const slot = (index + attempt) % totalSlots;
    const col = slot % columns;
    const row = Math.floor(slot / columns) % rows;
    const x = minX + (col + 0.5) * (width / columns);
    const y = minY + (row + 0.5) * (height / rows);
    if (rings.some(item => pointInRing([x, y], item.ring))) return [x, y];
  }
  const fallback = rings[index % rings.length].space;
  return spaceRepresentative(fallback) || rings[index % rings.length].ring[0] || [0, 0];
}
function spawnRegionSpaces(cellId) {
  if (!model) return [];
  const selected = model.spaces.find(space => space.id === cellId);
  if (!selected || !spaceIsSpawnable(selected)) return [];
  const sameLevel = model.spaces.filter(space => space.level === selected.level && spaceIsSpawnable(space));
  const byId = new Map(sameLevel.map(space => [space.id, space]));
  const visited = new Set([selected.id]);
  const queue = [selected.id];
  while (queue.length) {
    const current = byId.get(queue.shift());
    if (!current) continue;
    for (const candidate of sameLevel) {
      if (visited.has(candidate.id)) continue;
      if (!spacesTouch(current, candidate)) continue;
      visited.add(candidate.id);
      queue.push(candidate.id);
    }
  }
  return sameLevel.filter(space => visited.has(space.id));
}
function spacesTouch(left, right) {
  const leftRing = (left.rings && left.rings[0]) || [];
  const rightRing = (right.rings && right.rings[0]) || [];
  if (!leftRing.length || !rightRing.length) return false;
  const tolerance = 0.015;
  for (let i = 0; i < leftRing.length - 1; i++) {
    for (let j = 0; j < rightRing.length - 1; j++) {
      if (segmentsOverlap(leftRing[i], leftRing[i + 1], rightRing[j], rightRing[j + 1], tolerance)) return true;
    }
  }
  return false;
}
function segmentsOverlap(a, b, c, d, tolerance) {
  const ux = b[0] - a[0], uy = b[1] - a[1];
  const vx = d[0] - c[0], vy = d[1] - c[1];
  const lenU = Math.hypot(ux, uy), lenV = Math.hypot(vx, vy);
  if (lenU < 1e-9 || lenV < 1e-9) return false;
  const cross = Math.abs((ux / lenU) * (vy / lenV) - (uy / lenU) * (vx / lenV));
  if (cross > 0.08) return false;
  const distance = Math.min(pointSegmentDistance(a, c, d), pointSegmentDistance(b, c, d), pointSegmentDistance(c, a, b), pointSegmentDistance(d, a, b));
  if (distance > tolerance) return false;
  const axis = Math.abs(ux) >= Math.abs(uy) ? 0 : 1;
  const a0 = Math.min(a[axis], b[axis]), a1 = Math.max(a[axis], b[axis]);
  const b0 = Math.min(c[axis], d[axis]), b1 = Math.max(c[axis], d[axis]);
  return Math.min(a1, b1) - Math.max(a0, b0) > tolerance;
}
function pointSegmentDistance(point, a, b) {
  const vx = b[0] - a[0], vy = b[1] - a[1];
  const wx = point[0] - a[0], wy = point[1] - a[1];
  const denom = vx * vx + vy * vy;
  const t = denom <= 1e-12 ? 0 : Math.max(0, Math.min(1, (wx * vx + wy * vy) / denom));
  const px = a[0] + t * vx, py = a[1] + t * vy;
  return Math.hypot(point[0] - px, point[1] - py);
}
function isSpawnableCell(cell) {
  return cell && cell.navigationType === "GeneralSpace" && !["Door", "Window", "Exit", "Stair", "Ramp", "Elevator", "ConnectorSideCoverage"].includes(cell.category);
}
function spaceIsSpawnable(space) {
  return space && space.navigationType === "GeneralSpace" && space.isNavigable && !["Door", "Window", "Exit", "Stair", "Ramp", "Elevator", "ConnectorSideCoverage"].includes(space.category);
}
function readJsonArray(id) {
  try {
    const value = JSON.parse($(id).value || "[]");
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}
function readBeacons() {
  return readJsonArray("beacons");
}
function writeBeacons(beacons, selectedId = null) {
  payload = null;
  $("beacons").value = JSON.stringify(beacons, null, 2);
  refreshBeaconSelect(selectedId);
  updateBeaconImpactPreview();
  draw();
}
function readEvents() {
  return readJsonArray("events");
}
function writeEvents(events) {
  payload = null;
  $("events").value = JSON.stringify(events, null, 2);
  updateBeaconImpactPreview();
}
function playbackBeacons() {
  return payload && Array.isArray(payload.beacons) ? payload.beacons : readBeacons();
}
function playbackEvents() {
  return payload && Array.isArray(payload.scheduledEvents) ? payload.scheduledEvents : readEvents();
}
function playbackUsesBeaconRisk() {
  if (payload && payload.routingConfig) return Boolean(payload.routingConfig.useBeaconRisk);
  return $("useBeaconRisk").checked;
}
function refreshBeaconSelect(selectedId = null) {
  const current = selectedId || $("beaconSelect").value;
  const beacons = readBeacons();
  fillSelect(
    $("beaconSelect"),
    beacons.map(beacon => ({ id: beacon.beaconId || "", label: `${beacon.levelRef || "level"} ${beacon.beaconId || "beacon"}` })),
    row => row.label,
    row => row.id,
    "No beacons"
  );
  if (current && beacons.some(beacon => beacon.beaconId === current)) $("beaconSelect").value = current;
}
function selectedBeacon() {
  if (beaconDraftMode) return null;
  const id = $("beaconSelect").value || $("beaconId").value.trim();
  return readBeacons().find(beacon => beacon.beaconId === id) || null;
}
function resetBeaconForm() {
  beaconDraftMode = true;
  $("beaconId").value = "";
  $("beaconSurface").value = "ceiling";
  $("beaconSensor").value = "smoke";
  $("beaconRisk").value = "0.4";
  $("beaconRadius").value = "3";
  $("beaconInnerRadius").value = "0";
  $("beaconCurvePoints").value = "";
  $("beaconSelect").value = "";
  seedBeaconCurve(0.4);
  updateBeaconImpactPreview();
  draw();
}
function loadSelectedBeacon() {
  beaconDraftMode = false;
  const beacon = selectedBeacon();
  if (!beacon) {
    resetBeaconForm();
    return;
  }
  $("beaconId").value = beacon.beaconId || "";
  $("beaconSurface").value = (beacon.attributes && beacon.attributes.mountSurface) || "ceiling";
  $("beaconSensor").value = (beacon.sensorTypes || ["smoke"]).join(", ");
  $("beaconRisk").value = String(((beacon.effects || {}).riskPenalty ?? 0.4));
  $("beaconRadius").value = String(((beacon.influence || {}).radiusM ?? 3));
  $("beaconInnerRadius").value = String(((beacon.influence || {}).innerRadiusM ?? 0));
  loadBeaconCurveFromEvents(beacon.beaconId);
  updateBeaconImpactPreview();
  draw();
}
function nextBeaconId(level) {
  const existing = new Set(readBeacons().map(beacon => beacon.beaconId));
  const prefix = `BC_${String(level || "L").replace(/[^A-Za-z0-9_]/g, "_")}_`;
  for (let i = 1; i < 1000; i++) {
    const id = `${prefix}${String(i).padStart(3, "0")}`;
    if (!existing.has(id)) return id;
  }
  return `${prefix}${Date.now()}`;
}
function numberFromInput(id, fallback) {
  const value = Number($(id).value);
  return Number.isFinite(value) ? value : fallback;
}
function beaconFromForm(positionOverride = null, spaceOverride = null) {
  const existing = selectedBeacon() || {};
  const level = (spaceOverride && spaceOverride.level) || existing.levelRef || $("level").value || (model && model.levels[0]) || "L00";
  const id = $("beaconId").value.trim() || existing.beaconId || nextBeaconId(level);
  const existingCoordinates = existing.position && existing.position.coordinates;
  const fallbackCell = model && model.cells.find(cell => cell.level === level);
  const coordinates = positionOverride || existingCoordinates || (fallbackCell ? [fallbackCell.x, fallbackCell.y] : [0, 0]);
  const sensorTypes = $("beaconSensor").value.split(",").map(value => value.trim()).filter(Boolean);
  const attributes = {
    ...(existing.attributes || {}),
    mountSurface: $("beaconSurface").value,
  };
  if (spaceOverride && spaceOverride.id) attributes.attachedSpaceRef = spaceOverride.id;
  return {
    ...existing,
    beaconId: id,
    levelRef: level,
    position: { type: "Point", coordinates: [Number(coordinates[0].toFixed(3)), Number(coordinates[1].toFixed(3))] },
    sensorTypes: sensorTypes.length ? sensorTypes : ["smoke"],
    influence: {
      ...(existing.influence || {}),
      type: (existing.influence && existing.influence.type) || "radius",
      innerRadiusM: Math.max(0, numberFromInput("beaconInnerRadius", 0)),
      radiusM: Math.max(0, numberFromInput("beaconRadius", 3)),
    },
    effects: {
      ...(existing.effects || {}),
      riskPenalty: clamp(numberFromInput("beaconRisk", 0.4), 0, 1),
    },
    attributes,
  };
}
function saveBeacon(positionOverride = null, spaceOverride = null) {
  const beacon = beaconFromForm(positionOverride, spaceOverride);
  const beacons = readBeacons();
  const index = beacons.findIndex(row => row.beaconId === beacon.beaconId);
  if (index >= 0) beacons[index] = beacon;
  else beacons.push(beacon);
  if (beacons.length) $("useBeaconRisk").checked = true;
  $("beaconId").value = beacon.beaconId;
  beaconDraftMode = false;
  writeBeacons(beacons, beacon.beaconId);
  loadSelectedBeacon();
  $("metrics").textContent = `Beacon ${beacon.beaconId} saved on ${beacon.levelRef}. Press Run simulation.`;
}
function deleteSelectedBeacon() {
  const id = $("beaconSelect").value || $("beaconId").value.trim();
  if (!id) return;
  writeBeacons(readBeacons().filter(beacon => beacon.beaconId !== id));
  writeEvents(readEvents().filter(event => event.beaconRef !== id));
  resetBeaconForm();
  $("metrics").textContent = `Beacon ${id} deleted.`;
}
function placeBeaconFromClick(event) {
  const rect = canvas.getBoundingClientRect();
  const point = [event.clientX - rect.left, event.clientY - rect.top].map(v => v * devicePixelRatio);
  const level = $("level").value || model.levels[0];
  const world = unprojectFor(level)(point);
  const space = spaceAt(level, world, false);
  if (!space) {
    $("metrics").textContent = "Beacon click ignored: position is outside the loaded floor geometry.";
    return;
  }
  const typedId = $("beaconId").value.trim();
  const existingIds = new Set(readBeacons().map(beacon => beacon.beaconId));
  $("beaconId").value = typedId && !existingIds.has(typedId) ? typedId : nextBeaconId(level);
  beaconDraftMode = true;
  saveBeacon([world[0], world[1]], space);
}
function simulationDurationS() {
  return Math.max(0, numberFromInput("timeStep", 0) * numberFromInput("maxSteps", 0));
}
function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
function formatNumber(value) {
  return Number(value.toFixed(3)).toString();
}
function formatFixed(value, digits = 2) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "0".toFixed(digits);
}
function parseCurvePoints() {
  const text = $("beaconCurvePoints").value.trim();
  if (!text) return [];
  const duration = simulationDurationS();
  let raw = [];
  if (text.startsWith("[")) {
    try { raw = JSON.parse(text); } catch { raw = []; }
  } else {
    raw = text.split(/\\n+/).map(line => {
      const matches = line.match(/[-+]?(?:[0-9]*[.])?[0-9]+/g) || [];
      return matches.length >= 2 ? [Number(matches[0]), Number(matches[1])] : null;
    }).filter(Boolean);
  }
  return raw
    .map(point => Array.isArray(point) ? { timeS: Number(point[0]), riskPenalty: Number(point[1]) } : { timeS: Number(point.timeS), riskPenalty: Number(point.riskPenalty ?? point.safety ?? point.risk) })
    .filter(point => Number.isFinite(point.timeS) && Number.isFinite(point.riskPenalty))
    .map(point => ({ timeS: clamp(point.timeS, 0, duration || point.timeS), riskPenalty: clamp(point.riskPenalty, 0, 1) }))
    .sort((a, b) => a.timeS - b.timeS);
}
function writeCurvePoints(points) {
  $("beaconCurvePoints").value = points.map(point => `${formatNumber(point.timeS)}, ${formatNumber(point.riskPenalty)}`).join("\\n");
}
function loadBeaconCurveFromEvents(beaconId) {
  if (!beaconId) return;
  const timeStep = Math.max(numberFromInput("timeStep", 1), 1e-6);
  const points = readEvents()
    .filter(event => event.beaconRef === beaconId && event.eventType === "beacon_update" && event.patch && event.patch.effects && event.patch.effects.riskPenalty != null)
    .map(event => ({
      timeS: Number.isFinite(Number(event.timeS)) ? Number(event.timeS) : Number(event.step || 0) * timeStep,
      riskPenalty: Number(event.patch.effects.riskPenalty),
    }));
  if (points.length) {
    writeCurvePoints(points.sort((a, b) => a.timeS - b.timeS));
  } else {
    const beacon = selectedBeacon();
    const risk = beacon ? Number(((beacon.effects || {}).riskPenalty ?? 0.4)) : 0.4;
    seedBeaconCurve(risk);
  }
  drawBeaconCurve();
}
function seedBeaconCurve(riskOverride = null) {
  const risk = clamp(Number(riskOverride ?? numberFromInput("beaconRisk", 0.4)), 0, 1);
  const duration = simulationDurationS();
  const points = duration > 0 ? [{ timeS: 0, riskPenalty: risk }, { timeS: duration, riskPenalty: risk }] : [{ timeS: 0, riskPenalty: risk }];
  writeCurvePoints(points);
  drawBeaconCurve();
}
function drawBeaconCurve() {
  const ratio = devicePixelRatio || 1;
  beaconCurve.width = Math.max(240, beaconCurve.clientWidth) * ratio;
  beaconCurve.height = Math.max(100, beaconCurve.clientHeight) * ratio;
  const w = beaconCurve.width, h = beaconCurve.height;
  const left = 34 * ratio, right = 12 * ratio, top = 10 * ratio, bottom = 24 * ratio;
  const duration = Math.max(simulationDurationS(), 1);
  const points = parseCurvePoints();
  selectedCurvePointIndex = points.length ? Math.min(selectedCurvePointIndex ?? 0, points.length - 1) : null;
  beaconCurveCtx.clearRect(0, 0, w, h);
  beaconCurveCtx.fillStyle = "#ffffff";
  beaconCurveCtx.fillRect(0, 0, w, h);
  beaconCurveCtx.strokeStyle = "#cbd5e1";
  beaconCurveCtx.lineWidth = ratio;
  for (let i = 0; i <= 4; i++) {
    const y = top + ((h - top - bottom) * i / 4);
    beaconCurveCtx.beginPath();
    beaconCurveCtx.moveTo(left, y);
    beaconCurveCtx.lineTo(w - right, y);
    beaconCurveCtx.stroke();
  }
  beaconCurveCtx.strokeStyle = "#334155";
  beaconCurveCtx.beginPath();
  beaconCurveCtx.moveTo(left, top);
  beaconCurveCtx.lineTo(left, h - bottom);
  beaconCurveCtx.lineTo(w - right, h - bottom);
  beaconCurveCtx.stroke();
  beaconCurveCtx.fillStyle = "#64748b";
  beaconCurveCtx.font = `${10 * ratio}px Segoe UI, Arial`;
  beaconCurveCtx.textAlign = "left";
  beaconCurveCtx.fillText("1", 4 * ratio, top + 4 * ratio);
  beaconCurveCtx.fillText("0", 4 * ratio, h - bottom + 4 * ratio);
  beaconCurveCtx.textAlign = "right";
  beaconCurveCtx.fillText(`${formatNumber(duration)}s`, w - right, h - 6 * ratio);
  if (!points.length) {
    beaconCurveCtx.textAlign = "center";
    beaconCurveCtx.fillText("Add time and safety-loss points or click the graph", w / 2, h / 2);
    return;
  }
  const toPixel = point => [
    left + (clamp(point.timeS, 0, duration) / duration) * (w - left - right),
    top + (1 - clamp(point.riskPenalty, 0, 1)) * (h - top - bottom),
  ];
  beaconCurveCtx.strokeStyle = "#7c3aed";
  beaconCurveCtx.lineWidth = 2 * ratio;
  beaconCurveCtx.beginPath();
  points.forEach((point, index) => {
    const p = toPixel(point);
    if (index) beaconCurveCtx.lineTo(p[0], p[1]);
    else beaconCurveCtx.moveTo(p[0], p[1]);
  });
  beaconCurveCtx.stroke();
  beaconCurveCtx.fillStyle = "#7c3aed";
  points.forEach((point, index) => {
    const p = toPixel(point);
    beaconCurveCtx.beginPath();
    beaconCurveCtx.arc(p[0], p[1], (index === selectedCurvePointIndex ? 6 : 4) * ratio, 0, Math.PI * 2);
    beaconCurveCtx.fill();
    if (index === selectedCurvePointIndex) {
      beaconCurveCtx.strokeStyle = "#111827";
      beaconCurveCtx.lineWidth = ratio;
      beaconCurveCtx.stroke();
    }
  });
}
function curvePointFromEvent(event) {
  const rect = beaconCurve.getBoundingClientRect();
  const ratio = devicePixelRatio || 1;
  const x = (event.clientX - rect.left) * ratio;
  const y = (event.clientY - rect.top) * ratio;
  const w = beaconCurve.width, h = beaconCurve.height;
  const left = 34 * ratio, right = 12 * ratio, top = 10 * ratio, bottom = 24 * ratio;
  const duration = Math.max(simulationDurationS(), 1);
  const timeS = clamp((x - left) / Math.max(w - left - right, 1) * duration, 0, duration);
  const riskPenalty = clamp(1 - (y - top) / Math.max(h - top - bottom, 1), 0, 1);
  return { x, y, timeS, riskPenalty };
}
function curvePixelForPoint(point) {
  const ratio = devicePixelRatio || 1;
  const w = beaconCurve.width, h = beaconCurve.height;
  const left = 34 * ratio, right = 12 * ratio, top = 10 * ratio, bottom = 24 * ratio;
  const duration = Math.max(simulationDurationS(), 1);
  return [
    left + (clamp(point.timeS, 0, duration) / duration) * (w - left - right),
    top + (1 - clamp(point.riskPenalty, 0, 1)) * (h - top - bottom),
  ];
}
function nearestCurvePointIndex(event) {
  const pointer = curvePointFromEvent(event);
  const ratio = devicePixelRatio || 1;
  const points = parseCurvePoints();
  let bestIndex = null;
  let bestDistance = 12 * ratio;
  points.forEach((point, index) => {
    const pixel = curvePixelForPoint(point);
    const distance = Math.hypot(pixel[0] - pointer.x, pixel[1] - pointer.y);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });
  return bestIndex;
}
function setCurvePoint(index, point) {
  const points = parseCurvePoints();
  if (index == null || index < 0 || index >= points.length) return;
  points[index] = { timeS: point.timeS, riskPenalty: point.riskPenalty };
  const selectedPoint = points[index];
  const sorted = points.sort((a, b) => a.timeS - b.timeS);
  selectedCurvePointIndex = sorted.indexOf(selectedPoint);
  draggedCurvePointIndex = selectedCurvePointIndex;
  writeCurvePoints(sorted);
  drawBeaconCurve();
  updateBeaconImpactPreview();
  draw();
}
function addCurvePointFromEvent(event) {
  const point = curvePointFromEvent(event);
  const points = parseCurvePoints();
  points.push({ timeS: point.timeS, riskPenalty: point.riskPenalty });
  const sorted = points.sort((a, b) => a.timeS - b.timeS);
  selectedCurvePointIndex = sorted.findIndex(item => item.timeS === point.timeS && item.riskPenalty === point.riskPenalty);
  writeCurvePoints(sorted);
  drawBeaconCurve();
  updateBeaconImpactPreview();
  draw();
}
function startCurveDrag(event) {
  const index = nearestCurvePointIndex(event);
  if (index == null) {
    addCurvePointFromEvent(event);
    draggedCurvePointIndex = selectedCurvePointIndex;
    return;
  }
  selectedCurvePointIndex = index;
  draggedCurvePointIndex = index;
  drawBeaconCurve();
}
function dragCurvePoint(event) {
  if (draggedCurvePointIndex == null) return;
  setCurvePoint(draggedCurvePointIndex, curvePointFromEvent(event));
}
function stopCurveDrag() {
  draggedCurvePointIndex = null;
}
function deleteSelectedCurvePoint() {
  const points = parseCurvePoints();
  if (selectedCurvePointIndex == null || selectedCurvePointIndex < 0 || selectedCurvePointIndex >= points.length) return;
  points.splice(selectedCurvePointIndex, 1);
  selectedCurvePointIndex = points.length ? Math.min(selectedCurvePointIndex, points.length - 1) : null;
  writeCurvePoints(points);
  drawBeaconCurve();
  updateBeaconImpactPreview();
  draw();
}
function generateBeaconCurveEvents() {
  if (!$("beaconId").value.trim() && !$("beaconSelect").value) saveBeacon();
  const beaconId = $("beaconId").value.trim() || $("beaconSelect").value;
  if (!beaconId) return;
  const points = parseCurvePoints();
  if (!points.length) seedBeaconCurve();
  const safePoints = parseCurvePoints();
  const timeStep = Math.max(numberFromInput("timeStep", 1), 1e-6);
  const maxSteps = Math.max(1, Math.floor(numberFromInput("maxSteps", 1)));
  const duration = simulationDurationS();
  const keep = readEvents().filter(event => !(event.source === "workbench_beacon_curve" && event.beaconRef === beaconId));
  const generated = [];
  const seenSteps = new Set();
  const lastStep = Math.max(0, Math.min(maxSteps, Math.ceil(duration / timeStep)));
  for (let step = 0; step <= lastStep; step++) {
    const timeS = Math.min(duration, step * timeStep);
    const riskPenalty = sampleCurveRisk(safePoints, timeS);
    if (seenSteps.has(step)) continue;
    seenSteps.add(step);
    generated.push({
      eventId: `EV_${beaconId}_RISK_${String(step).padStart(4, "0")}`,
      step,
      timeS: Number(timeS.toFixed(3)),
      eventType: "beacon_update",
      beaconRef: beaconId,
      patch: { effects: { riskPenalty: Number(riskPenalty.toFixed(3)) } },
      source: "workbench_beacon_curve",
    });
  }
  writeEvents([...keep, ...generated].sort((a, b) => Number(a.step || 0) - Number(b.step || 0)));
  $("metrics").textContent = `Generated ${generated.length} safety events for ${beaconId}. Press Run simulation.`;
  updateBeaconImpactPreview();
}
function sampleCurveRisk(points, timeS) {
  if (!points.length) return 0;
  const ordered = [...points].sort((a, b) => a.timeS - b.timeS);
  if (timeS <= ordered[0].timeS) return ordered[0].riskPenalty;
  for (let i = 0; i < ordered.length - 1; i++) {
    const left = ordered[i], right = ordered[i + 1];
    if (timeS <= right.timeS) {
      const ratio = right.timeS === left.timeS ? 0 : (timeS - left.timeS) / (right.timeS - left.timeS);
      return clamp(left.riskPenalty + (right.riskPenalty - left.riskPenalty) * ratio, 0, 1);
    }
  }
  return ordered[ordered.length - 1].riskPenalty;
}
function currentPreviewTimeS() {
  if (payload) {
    const rows = rowsAt(currentFrame);
    const withTime = rows.find(row => row.timeS != null);
    if (withTime) return Math.max(0, Number(withTime.timeS));
  }
  return Math.max(0, (payload ? currentFrame / 4 : 0) * numberFromInput("timeStep", model && model.config ? model.config.timeStepS : 0.5));
}
function eventTimeS(event) {
  const timeStep = Math.max(numberFromInput("timeStep", 1), 1e-6);
  return Number.isFinite(Number(event.timeS)) ? Number(event.timeS) : Number(event.step || 0) * timeStep;
}
function beaconRuntimeState(beacon, timeS) {
  const id = beacon.beaconId;
  const baseEffects = beacon.effects || beacon.affects || {};
  const state = {
    enabled: beacon.enabled !== false,
    riskPenalty: clamp(Number(baseEffects.riskPenalty ?? 0), 0, 1),
  };
  const events = playbackEvents()
    .filter(event => event.beaconRef === id && eventTimeS(event) <= timeS)
    .sort((a, b) => eventTimeS(a) - eventTimeS(b));
  for (const event of events) {
    if (event.eventType === "beacon_disable") state.enabled = false;
    if (event.eventType === "beacon_enable") state.enabled = true;
    if (event.eventType === "beacon_update") {
      const patchEffects = (event.patch && event.patch.effects) || {};
      if (patchEffects.riskPenalty != null) state.riskPenalty = clamp(Number(patchEffects.riskPenalty), 0, 1);
      if (event.patch && event.patch.enabled != null) state.enabled = Boolean(event.patch.enabled);
    }
  }
  const curveEvents = playbackEvents()
    .filter(event => event.beaconRef === id && event.source === "workbench_beacon_curve" && event.eventType === "beacon_update" && event.patch && event.patch.effects && event.patch.effects.riskPenalty != null)
    .sort((a, b) => eventTimeS(a) - eventTimeS(b));
  if (curveEvents.length) {
    const points = curveEvents.map(event => ({ timeS: eventTimeS(event), riskPenalty: Number(event.patch.effects.riskPenalty) }));
    state.riskPenalty = sampleCurveRisk(points, timeS);
  }
  return state;
}
function distanceM(a, b) {
  const dx = Number(a[0]) - Number(b[0]);
  const dy = Number(a[1]) - Number(b[1]);
  return Math.sqrt(dx * dx + dy * dy);
}
function smoothstepSignal(distance, innerRadius, outerRadius) {
  if (outerRadius <= innerRadius) return distance <= outerRadius ? 1 : 0;
  if (distance <= innerRadius) return 1;
  if (distance >= outerRadius) return 0;
  const t = (distance - innerRadius) / (outerRadius - innerRadius);
  return 1 - (t * t * (3 - 2 * t));
}
function beaconRiskForPoint(beacon, point, level, timeS) {
  if (beacon.levelRef !== level) return 0;
  const coordinates = beacon.position && beacon.position.coordinates;
  if (!coordinates || coordinates.length < 2) return 0;
  const runtime = beaconRuntimeState(beacon, timeS);
  if (!runtime.enabled) return 0;
  const influence = beacon.influence || {};
  const radius = Math.max(0, Number(influence.radiusM ?? 8));
  const inner = Math.max(0, Number(influence.innerRadiusM ?? 0));
  const signal = smoothstepSignal(distanceM(coordinates, point), inner, radius);
  return clamp(signal * runtime.riskPenalty, 0, 1);
}
function combinedBeaconRiskForPoint(point, level, timeS) {
  let risk = 0;
  for (const beacon of playbackBeacons()) risk = Math.max(risk, beaconRiskForPoint(beacon, point, level, timeS));
  return risk;
}
function spaceRepresentative(space) {
  const cell = model && model.cells.find(row => row.id === space.id);
  if (cell) return [cell.x, cell.y];
  const ring = (space.rings && space.rings[0]) || [];
  if (!ring.length) return null;
  const total = ring.reduce((acc, p) => [acc[0] + Number(p[0]), acc[1] + Number(p[1])], [0, 0]);
  return [total[0] / ring.length, total[1] / ring.length];
}
function beaconImpactRows(level = null, timeS = currentPreviewTimeS()) {
  if (!model) return [];
  const selectedLevel = level || $("level").value || model.levels[0];
  return activeSpaces()
    .filter(space => space.level === selectedLevel && spaceIsNavigable(space))
    .map(space => {
      const point = spaceRepresentative(space);
      const risk = point ? combinedBeaconRiskForPoint(point, selectedLevel, timeS) : 0;
      return { id: space.id, category: space.category, risk };
    })
    .filter(row => row.risk > 0.001)
    .sort((a, b) => b.risk - a.risk);
}
function beaconBlockThreshold() {
  if (payload && payload.routingConfig && payload.routingConfig.beaconBlockThreshold != null) {
    return clamp(Number(payload.routingConfig.beaconBlockThreshold), 0, 1);
  }
  return clamp(numberFromInput("beaconBlockThreshold", 0.85), 0, 1);
}
function updateBeaconImpactPreview() {
  if (!$("beaconImpact")) return;
  if (!model) {
    $("beaconImpact").textContent = "Beacon impact preview will appear after the model loads.";
    return;
  }
  const timeS = currentPreviewTimeS();
  const selected = selectedBeacon();
  const beacons = playbackBeacons();
  const selectedRuntime = selected ? beaconRuntimeState(selected, timeS) : null;
  const rows = beaconImpactRows(null, timeS);
  const selectedEvents = selected ? playbackEvents().filter(event => event.beaconRef === selected.beaconId) : [];
  const mode = playbackUsesBeaconRisk() ? "routing ON" : "routing OFF";
  const blockThreshold = beaconBlockThreshold();
  const blockedRows = playbackUsesBeaconRisk() ? rows.filter(row => row.risk >= blockThreshold) : [];
  const selectedText = selected
    ? `${selected.beaconId}\nlevel ${selected.levelRef}\nspace ${((selected.attributes || {}).attachedSpaceRef || "no attachedSpaceRef")}\nsafety ${formatFixed(1 - selectedRuntime.riskPenalty, 2)} | safety loss ${formatFixed(selectedRuntime.riskPenalty, 2)}`
    : "none selected";
  const topRows = rows.slice(0, 8).map(row => {
    const safety = 1 - row.risk;
    const blocked = row.risk >= blockThreshold && playbackUsesBeaconRisk();
    return `${row.id}: safety ${formatFixed(safety, 2)} | loss ${formatFixed(row.risk, 2)}${blocked ? " BLOCKED" : ""}`;
  }).join("\\n") || "none at current time";
  $("beaconImpact").textContent =
    `Safety preview ${mode}\\n` +
    `time ${formatFixed(timeS, 1)}s | beacons ${beacons.length}\\n` +
    `block when safety loss >= ${formatFixed(blockThreshold, 2)} | safety <= ${formatFixed(1 - blockThreshold, 2)}\\n` +
    `selected\\n${selectedText}\\n` +
    `selected events ${selectedEvents.length}\\n` +
    `affected spaces ${rows.length} | blocked ${blockedRows.length}\\n` +
    topRows;
}
function destinationCellsForRun() {
  if ($("destinationMode").value === "selected") return [$("destinationCell").value].filter(Boolean);
  const configured = (model && model.config && model.config.destinationCells) || [];
  if (configured.length) return configured;
  return model ? model.exits.map(exit => exit.id) : [$("destinationCell").value].filter(Boolean);
}
function cerOriginOptions() {
  if (!model) return [];
  const nodes = model.transferNodes || [];
  return nodes.filter(node => !node.isExit);
}
function cerTargetOptions() {
  if (!model) return [];
  const nodes = model.transferNodes || [];
  const exits = nodes.filter(node => node.isExit);
  return exits.length ? exits : nodes;
}
function cerNodeLabel(node) {
  const kind = node.transferKind || node.category || "transfer";
  return `${node.level} ${kind} ${node.id} [${node.x}, ${node.y}]`;
}
function transferNodeById(id) {
  return model && (model.transferNodes || []).find(node => node.id === id);
}
function nearestTransferForCell(cellId, predicate = null) {
  const point = selectedCellPoint(cellId);
  const cell = model && model.cells.find(c => c.id === cellId);
  if (!point || !cell) return null;
  return nearestTransfer(cell.level, point, predicate);
}
function nearestTransfer(level, point, predicate = null) {
  if (!model) return null;
  let best = null;
  let bestDistance = Infinity;
  for (const node of model.transferNodes || []) {
    if (level && node.level !== level) continue;
    if (predicate && !predicate(node)) continue;
    const distance = Math.hypot(Number(node.x) - point[0], Number(node.y) - point[1]);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = node;
    }
  }
  return best;
}
function updateCerPickStatus() {
  if (!$("cerPickStatus")) return;
  const origin = transferNodeById($("cerOrigin").value);
  const target = transferNodeById($("cerTarget").value);
  const action = cerPickMode ? `Click the canvas to set CER ${cerPickMode}.` : "Open this panel to show transfer nodes on the canvas.";
  $("cerPickStatus").textContent =
    `${action}\n` +
    `origin: ${origin ? cerNodeLabel(origin) : "not selected"}\n` +
    `target: ${target ? cerNodeLabel(target) : "not selected"}`;
}
function selectedCellPoint(cellId) {
  const cell = model && model.cells.find(c => c.id === cellId);
  return cell ? [cell.x, cell.y] : null;
}
function bounds(level) {
  const pts = [];
  for (const s of activeSpaces()) if (s.level === level) for (const ring of s.rings) for (const p of ring) pts.push(p);
  if (!pts.length) return [0,0,1,1];
  return [Math.min(...pts.map(p=>p[0])), Math.min(...pts.map(p=>p[1])), Math.max(...pts.map(p=>p[0])), Math.max(...pts.map(p=>p[1]))];
}
function activeSpaces() {
  return payload ? payload.spaces : (model ? model.spaces : []);
}
function activeEdges() {
  return payload ? (payload.edges || []) : (model ? (model.graphEdges || []) : []);
}
function activeVirtualBoundaries() {
  return payload ? (payload.virtualBoundaries || []) : (model ? (model.virtualBoundaries || []) : []);
}
function spaceIsNavigable(space) {
  if (space.isNavigable != null) return Boolean(space.isNavigable);
  return space.navigationType === "GeneralSpace" || space.navigationType === "TransferSpace";
}
function projectFor(level) {
  const [minX,minY,maxX,maxY] = bounds(level), pad = 26 * devicePixelRatio;
  const scale = Math.min((canvas.width-pad*2)/Math.max(maxX-minX,1), (canvas.height-pad*2)/Math.max(maxY-minY,1));
  return ([x,y]) => [pad+(x-minX)*scale, canvas.height-pad-(y-minY)*scale];
}
function pixelsPerMeter(level) {
  const [minX,minY,maxX,maxY] = bounds(level), pad = 26 * devicePixelRatio;
  return Math.min((canvas.width-pad*2)/Math.max(maxX-minX,1), (canvas.height-pad*2)/Math.max(maxY-minY,1));
}
function unprojectFor(level) {
  const [minX,minY,maxX,maxY] = bounds(level), pad = 26 * devicePixelRatio;
  const scale = Math.min((canvas.width-pad*2)/Math.max(maxX-minX,1), (canvas.height-pad*2)/Math.max(maxY-minY,1));
  return ([x,y]) => [minX + (x-pad)/scale, minY + (canvas.height-pad-y)/scale];
}
function positiveNumberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : null;
}
function profileBodyRadiusM(profileId) {
  const defaults = {
    MP_WALKING: 0.24,
    MP_WALKING_VERTICAL: 0.24,
    MP_ELDERLY: 0.26,
    MP_CHILD: 0.18,
    MP_ROLLING_ACCESSIBLE: 0.3
  };
  return defaults[profileId] || 0.28;
}
function profilePersonalRadiusM(profileId) {
  const defaults = {
    MP_WALKING: 0.5,
    MP_WALKING_VERTICAL: 0.5,
    MP_ELDERLY: 0.6,
    MP_CHILD: 0.42,
    MP_ROLLING_ACCESSIBLE: 0.58
  };
  return defaults[profileId] || 0.55;
}
function agentBodyRadiusPx(level, profileId, bodyRadiusM, scale = 1) {
  const radiusM = positiveNumberOrNull(bodyRadiusM) || profileBodyRadiusM(profileId);
  return Math.max(radiusM * pixelsPerMeter(level) * scale, 4 * devicePixelRatio);
}
function agentPersonalRadiusPx(level, profileId, personalRadiusM) {
  const radiusM = positiveNumberOrNull(personalRadiusM) || profilePersonalRadiusM(profileId);
  return Math.max(radiusM * pixelsPerMeter(level), agentBodyRadiusPx(level, profileId, null) * 1.55);
}
function rowsAt(frame) {
  const step = frame / 4;
  const rows = [];
  for (const list of trajectoryByAgent.values()) {
    let a = null, b = null;
    for (const row of list) { if (row.step <= step) a = row; if (row.step >= step) { b = row; break; } }
    if (!a && b) rows.push({...b});
    else if (a && (!b || a === b)) rows.push({...a});
    else if (a && b) {
      const t = b.step === a.step ? 0 : (step-a.step)/(b.step-a.step);
      const timeS = Number(a.timeS || 0) + (Number(b.timeS || a.timeS || 0) - Number(a.timeS || 0)) * t;
      rows.push({...a, x: a.x+(b.x-a.x)*t, y: a.y+(b.y-a.y)*t, timeS, status: t > .85 ? b.status : a.status});
    }
  }
  return rows;
}
function buildTrajectoryIndex() {
  trajectoryByAgent = new Map();
  for (const row of payload.trajectories) {
    if (!trajectoryByAgent.has(row.agentId)) trajectoryByAgent.set(row.agentId, []);
    trajectoryByAgent.get(row.agentId).push(row);
  }
  for (const list of trajectoryByAgent.values()) list.sort((a,b)=>a.step-b.step);
}
function draw() {
  if (!payload) { drawModelPreview(); return; }
  canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio;
  const level = $("level").value || payload.levels[0], project = projectFor(level);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  drawSpaces(level, project);
  drawBeaconRiskOverlay(level, project);
  drawEdges(level, project);
  drawVirtualBoundaries(level, project);
  drawCerTransfers(level, project);
  drawBeaconRiskEdges(level, project);
  drawBeacons(level, project);
  drawRouteDebug(level, project);
  drawTraces(level, project);
  for (const r of rowsAt(currentFrame)) if (r.levelRef === level) {
    const p=project([r.x,r.y]), color = r.status === "active" ? (profileColors[r.profileId] || "#006dff") : (statusColors[r.status] || "#64748b");
    if (r.intentX != null && r.status === "active") { const q=project([r.intentX,r.intentY]); ctx.beginPath(); ctx.moveTo(p[0],p[1]); ctx.lineTo(q[0],q[1]); ctx.strokeStyle=color; ctx.setLineDash([4,3]); ctx.stroke(); ctx.setLineDash([]); }
    const bodyScale = r.status === "active" ? 1 : 0.65;
    if (r.status === "active") { ctx.beginPath(); ctx.arc(p[0],p[1],agentPersonalRadiusPx(level, r.profileId, r.personalRadiusM),0,Math.PI*2); ctx.fillStyle=color+"33"; ctx.fill(); }
    ctx.globalAlpha = r.status === "active" ? 1 : 0.72;
    ctx.beginPath(); ctx.arc(p[0],p[1],agentBodyRadiusPx(level, r.profileId, r.bodyRadiusM, bodyScale),0,Math.PI*2); ctx.fillStyle=color; ctx.strokeStyle="#111827"; ctx.fill(); ctx.stroke();
    ctx.globalAlpha = 1;
  }
  $("frame").value = String(currentFrame);
  updateBeaconImpactPreview();
  drawRouteCostChart();
}
function drawModelPreview() {
  if (!model) return drawEmpty("Loading model...");
  canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio;
  const level = $("level").value || model.levels[0], project = projectFor(level);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  drawSpaces(level, project);
  drawBeaconRiskOverlay(level, project);
  drawEdges(level, project);
  drawVirtualBoundaries(level, project);
  drawCerTransfers(level, project);
  drawBeacons(level, project);
  if (activeAgentMode() === "automatic") drawAutomaticAgents(level, project);
  else drawManualAgents(level, project);
  updateBeaconImpactPreview();
  drawRouteCostChart();
}
function drawSpaces(level, project) {
  for (const s of activeSpaces()) if (s.level === level) {
    ctx.beginPath();
    for (const ring of s.rings) ring.forEach((p,i)=>{ const q=project(p); if(i)ctx.lineTo(q[0],q[1]); else ctx.moveTo(q[0],q[1]); });
    ctx.closePath();
    const wall = s.navigationType === "NonNavigableSpace" || s.category === "WallSegment" || s.category === "WallJunction" || s.category === "Column";
    ctx.fillStyle = wall ? "#050505" : s.category === "Exit" ? "#75c878" : s.category === "Window" ? "#60a5fa" : s.category === "Stair" ? "#d8b4fe" : s.category === "Ramp" ? "#93c5fd" : s.category === "Elevator" ? "#67e8f9" : s.category === "Door" ? "#f4c25f" : s.navigationType === "TransferSpace" ? "#f8e7b7" : "#eef4fb";
    ctx.strokeStyle = wall ? "#000000" : "#94a3b8";
    ctx.lineWidth = wall ? 1.1 * devicePixelRatio : 0.8 * devicePixelRatio;
    ctx.fill(); ctx.stroke();
  }
  drawConnectorLabels(level, project);
}
function drawEdges(level, project) {
  ctx.save();
  for (const e of activeEdges()) if (edgeVisibleOnLevel(e, level)) {
    const a=project(e.points[0]), b=project(e.points[1]);
    ctx.beginPath();
    ctx.moveTo(a[0],a[1]);
    ctx.lineTo(b[0],b[1]);
    const connectorAccess = isConnectorAccessEdge(e);
    const virtualEdge = isVirtualEdge(e);
    ctx.globalAlpha = virtualEdge ? 0.32 : connectorAccess ? 0.34 : 0.28;
    ctx.strokeStyle = graphEdgeColor(e);
    ctx.lineWidth = (connectorAccess ? 0.95 : virtualEdge ? 0.9 : 0.75) * devicePixelRatio;
    ctx.stroke();
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}
function drawVirtualBoundaries(level, project) {
  ctx.save();
  ctx.globalAlpha = 0.5;
  ctx.strokeStyle = "#64748b";
  ctx.lineWidth = 1.05 * devicePixelRatio;
  ctx.setLineDash([4 * devicePixelRatio, 4 * devicePixelRatio]);
  for (const boundary of activeVirtualBoundaries()) {
    if (!boundaryVisibleOnLevel(boundary, level) || !boundary.points || boundary.points.length < 2) continue;
    ctx.beginPath();
    boundary.points.forEach((point, index) => {
      const p = project(point);
      if (index) ctx.lineTo(p[0], p[1]);
      else ctx.moveTo(p[0], p[1]);
    });
    ctx.stroke();
  }
  ctx.restore();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}
function drawCerTransfers(level, project) {
  if (!model || !shouldShowCerTransfers()) return;
  const originId = $("cerOrigin").value;
  const targetId = $("cerTarget").value;
  ctx.save();
  for (const node of model.transferNodes || []) {
    if (node.level !== level) continue;
    const p = project([Number(node.x), Number(node.y)]);
    const selectedOrigin = node.id === originId;
    const selectedTarget = node.id === targetId;
    const selected = selectedOrigin || selectedTarget;
    const radius = (selected ? 6.5 : node.isExit ? 4.8 : 3.4) * devicePixelRatio;
    ctx.beginPath();
    ctx.arc(p[0], p[1], radius, 0, Math.PI * 2);
    ctx.fillStyle = selectedOrigin ? "#f97316" : selectedTarget ? "#16a34a" : node.isExit ? "#22c55e" : "#ffffff";
    ctx.strokeStyle = selected ? "#111827" : "#334155";
    ctx.lineWidth = (selected ? 1.8 : 1.0) * devicePixelRatio;
    ctx.globalAlpha = selected ? 0.98 : 0.82;
    ctx.fill();
    ctx.stroke();
    if (selected) {
      ctx.globalAlpha = 1;
      ctx.font = `${10 * devicePixelRatio}px Segoe UI, Arial`;
      ctx.textAlign = "left";
      ctx.textBaseline = "middle";
      ctx.fillStyle = selectedOrigin ? "#9a3412" : "#166534";
      ctx.fillText(selectedOrigin ? "CER origin" : "CER target", p[0] + 8 * devicePixelRatio, p[1]);
    }
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}
function shouldShowCerTransfers() {
  return Boolean(cerPickMode || ($("cerDebugSection") && $("cerDebugSection").open));
}
function drawRouteCostChart() {
  if (!routeCostChart) return;
  routeCostChart.width = routeCostChart.clientWidth * devicePixelRatio;
  routeCostChart.height = routeCostChart.clientHeight * devicePixelRatio;
  const w = routeCostChart.width, h = routeCostChart.height;
  const padL = 38 * devicePixelRatio, padR = 10 * devicePixelRatio, padT = 10 * devicePixelRatio, padB = 18 * devicePixelRatio;
  routeCostCtx.clearRect(0, 0, w, h);
  routeCostCtx.fillStyle = "#ffffff";
  routeCostCtx.fillRect(0, 0, w, h);
  if (!payload) {
    $("routeCostStatus").textContent = "Run a simulation to inspect ETA over replans.";
    drawRouteCostEmpty("No simulation");
    return;
  }
  const route = routeForDebug($("level").value || null, currentFrame);
  const history = route ? routeCostHistory(route.agentId) : [];
  if (!route || !history.length) {
    $("routeCostStatus").textContent = "No route_planned events for the visible agent.";
    drawRouteCostEmpty("No ETA");
    return;
  }
  const currentTime = currentPreviewTimeS();
  const current = latestRouteCostAt(history, currentTime) || history[history.length - 1];
  const first = history[0];
  const maxTime = Math.max(...history.map(item => item.timeS), currentTime, 1);
  const minCost = Math.min(...history.map(item => item.etaTotal));
  const maxCost = Math.max(...history.map(item => item.etaTotal));
  const yLow = minCost === maxCost ? Math.max(0, minCost - 1) : minCost;
  const yHigh = minCost === maxCost ? maxCost + 1 : maxCost;
  const xOf = time => padL + (Math.max(0, time) / maxTime) * Math.max(1, w - padL - padR);
  const yOf = cost => h - padB - ((cost - yLow) / Math.max(yHigh - yLow, 1e-9)) * Math.max(1, h - padT - padB);

  routeCostCtx.strokeStyle = "#cbd5e1";
  routeCostCtx.lineWidth = 1 * devicePixelRatio;
  routeCostCtx.beginPath();
  routeCostCtx.moveTo(padL, padT);
  routeCostCtx.lineTo(padL, h - padB);
  routeCostCtx.lineTo(w - padR, h - padB);
  routeCostCtx.stroke();

  for (let i = 1; i < history.length; i++) {
    const prev = history[i - 1], item = history[i];
    routeCostCtx.beginPath();
    routeCostCtx.moveTo(xOf(prev.timeS), yOf(prev.etaTotal));
    routeCostCtx.lineTo(xOf(item.timeS), yOf(item.etaTotal));
    routeCostCtx.strokeStyle = item.etaTotal > prev.etaTotal + 1e-6 ? "#dc2626" : "#2563eb";
    routeCostCtx.lineWidth = 2 * devicePixelRatio;
    routeCostCtx.stroke();
  }
  for (const item of history) {
    routeCostCtx.beginPath();
    routeCostCtx.arc(xOf(item.timeS), yOf(item.etaTotal), 2.6 * devicePixelRatio, 0, Math.PI * 2);
    routeCostCtx.fillStyle = item === current ? "#f97316" : "#0f172a";
    routeCostCtx.fill();
  }

  routeCostCtx.beginPath();
  routeCostCtx.moveTo(xOf(currentTime), padT);
  routeCostCtx.lineTo(xOf(currentTime), h - padB);
  routeCostCtx.setLineDash([4 * devicePixelRatio, 3 * devicePixelRatio]);
  routeCostCtx.strokeStyle = "#f97316";
  routeCostCtx.lineWidth = 1.4 * devicePixelRatio;
  routeCostCtx.stroke();
  routeCostCtx.setLineDash([]);

  routeCostCtx.fillStyle = "#334155";
  routeCostCtx.font = `${10 * devicePixelRatio}px Segoe UI, Arial`;
  routeCostCtx.textAlign = "left";
  routeCostCtx.fillText(`${yHigh.toFixed(1)}s`, 4 * devicePixelRatio, padT + 4 * devicePixelRatio);
  routeCostCtx.fillText(`${yLow.toFixed(1)}s`, 4 * devicePixelRatio, h - padB);
  routeCostCtx.textAlign = "right";
  routeCostCtx.fillText(`${maxTime.toFixed(1)}s`, w - padR, h - 4 * devicePixelRatio);

  const delta = current.etaTotal - first.etaTotal;
  const sign = delta > 1e-6 ? "+" : "";
  $("routeCostStatus").textContent =
    `agent ${route.agentId || "?"} | alg ${current.algorithm || route.algorithm || "?"} | ETA ${current.etaTotal.toFixed(3)} s | remaining ${current.totalCost.toFixed(3)} s | delta ${sign}${delta.toFixed(3)} s | samples ${history.length}`;
}
function drawRouteCostEmpty(message) {
  const w = routeCostChart.width, h = routeCostChart.height;
  routeCostCtx.fillStyle = "#64748b";
  routeCostCtx.font = `${12 * devicePixelRatio}px Segoe UI, Arial`;
  routeCostCtx.textAlign = "center";
  routeCostCtx.textBaseline = "middle";
  routeCostCtx.fillText(message, w / 2, h / 2);
}
function routeCostHistory(agentId) {
  if (!agentId || !payload || !Array.isArray(payload.events)) return [];
  return payload.events
    .filter(event => event.agentId === agentId && ["route_planned", "agent_route_recovered"].includes(event.eventType) && event.route && Number.isFinite(Number(event.route.totalCost)))
    .map(event => ({
      step: Number(event.step || 0),
      timeS: Number(event.timeS || 0),
      totalCost: Number(event.route.totalCost),
      etaTotal: Number((Number(event.timeS || 0) + Number(event.route.totalCost)).toFixed(6)),
      algorithm: event.route.algorithm || "",
      nodeSequence: event.route.nodeSequence || [],
    }))
    .sort((a, b) => a.step - b.step || a.timeS - b.timeS);
}
function latestRouteCostAt(history, timeS) {
  let latest = null;
  for (const item of history) {
    if (item.timeS <= timeS + 1e-9) latest = item;
    else break;
  }
  return latest || history[0] || null;
}
function drawRouteDebug(level, project) {
  const route = routeForDebug(level, currentFrame);
  if (!route) return;
  const nodeSequence = route.nodeSequence || [];
  if (nodeSequence.length < 2) return;
  const nodePoints = routeNodePoints();
  const row = trajectoryRowForAgent(route.agentId, currentFrame, level);
  if (row && row.levelRef === level) nodePoints.set(nodeSequence[0], [row.x, row.y]);

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (let i = 0; i < nodeSequence.length - 1; i++) {
    const segment = routeSegmentPoints(nodeSequence[i], nodeSequence[i + 1], nodePoints);
    if (!segment || !segment.some(point => pointLevelVisible(point, level))) continue;
    const a = project(segment[0]);
    const b = project(segment[1]);
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.globalAlpha = i === 0 ? 0.92 : 0.72;
    ctx.strokeStyle = i === 0 ? "#f97316" : "#2563eb";
    ctx.lineWidth = (i === 0 ? 3.0 : 2.1) * devicePixelRatio;
    ctx.stroke();
  }

  const breakdown = route.weightBreakdown || {};
  const candidates = (breakdown.originCandidates || []).slice(0, 5);
  candidates.forEach((candidate, index) => {
    const point = nodePoints.get(candidate.to);
    if (!point || !pointLevelVisible(point, level)) return;
    const p = project(point);
    ctx.beginPath();
    ctx.globalAlpha = index === 0 ? 0.95 : 0.72;
    ctx.arc(p[0], p[1], (index === 0 ? 6 : 5) * devicePixelRatio, 0, Math.PI * 2);
    ctx.fillStyle = index === 0 ? "#f97316" : "#ffffff";
    ctx.strokeStyle = index === 0 ? "#9a3412" : "#2563eb";
    ctx.lineWidth = 1.6 * devicePixelRatio;
    ctx.fill();
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.fillStyle = index === 0 ? "#ffffff" : "#1e3a8a";
    ctx.font = `${8 * devicePixelRatio}px Segoe UI, Arial`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(index + 1), p[0], p[1]);
  });
  ctx.restore();
  ctx.globalAlpha = 1;
}
function routeNodePoints() {
  const nodes = new Map();
  for (const edge of activeEdges()) {
    if (edge.source && edge.points && edge.points[0]) nodes.set(edge.source, edge.points[0]);
    if (edge.target && edge.points && edge.points[1]) nodes.set(edge.target, edge.points[1]);
  }
  for (const space of activeSpaces()) {
    const point = spaceRepresentative(space);
    if (point) nodes.set(space.id, point);
  }
  return nodes;
}
function routeSegmentPoints(source, target, nodePoints) {
  const edge = activeEdges().find(item =>
    (item.source === source && item.target === target) || (item.source === target && item.target === source)
  );
  if (edge && edge.points && edge.points.length >= 2) {
    return edge.source === source ? [edge.points[0], edge.points[1]] : [edge.points[1], edge.points[0]];
  }
  const a = nodePoints.get(source), b = nodePoints.get(target);
  return a && b ? [a, b] : null;
}
function routeForDebug(level = null, frame = currentFrame) {
  if (!payload || !Array.isArray(payload.routes) || !payload.routes.length) return null;
  const visibleRows = rowsAt(frame).filter(row => !level || row.levelRef === level);
  for (const row of visibleRows) {
    const route = plannedRouteForAgent(row.agentId, frame) || payload.routes.find(item => item.agentId === row.agentId);
    if (route) return route;
  }
  if (level) {
    const routeIds = new Set(payload.routes.map(route => route.agentId));
    const row = (payload.trajectories || []).find(item => item.levelRef === level && routeIds.has(item.agentId));
    if (row) return plannedRouteForAgent(row.agentId, frame) || payload.routes.find(item => item.agentId === row.agentId) || null;
  }
  const firstRoute = payload.routes[0] || null;
  return firstRoute ? (plannedRouteForAgent(firstRoute.agentId, frame) || firstRoute) : null;
}
function plannedRouteForAgent(agentId, frame = currentFrame) {
  if (!agentId || !payload || !Array.isArray(payload.events)) return null;
  const step = frame / 4;
  const planned = payload.events
    .filter(event => event.agentId === agentId && ["route_planned", "agent_route_recovered"].includes(event.eventType) && Number(event.step) <= step && event.route)
    .sort((a, b) => Number(b.step) - Number(a.step) || Number(b.timeS || 0) - Number(a.timeS || 0))[0];
  if (!planned) return null;
  return {
    agentId: planned.agentId,
    eventStep: planned.step,
    eventTimeS: planned.timeS,
    ...(planned.route || {}),
  };
}
function trajectoryRowForAgent(agentId, frame, level = null) {
  if (!agentId || !trajectoryByAgent.has(agentId)) return null;
  const step = frame / 4;
  const rows = trajectoryByAgent.get(agentId);
  let previous = null;
  let following = null;
  for (const row of rows) {
    if (level && row.levelRef !== level) continue;
    if (row.step <= step) previous = row;
    if (row.step >= step) { following = row; break; }
  }
  return previous || following || null;
}
function pointLevelVisible(point, level) {
  const space = spaceAt(level, point, "any");
  return Boolean(space) || !level;
}
function drawBeaconRiskOverlay(level, project) {
  if (!model || !playbackBeacons().length) return;
  const timeS = currentPreviewTimeS();
  const blockThreshold = beaconBlockThreshold();
  ctx.save();
  for (const space of activeSpaces()) if (space.level === level && spaceIsNavigable(space)) {
    const point = spaceRepresentative(space);
    if (!point) continue;
    const risk = combinedBeaconRiskForPoint(point, level, timeS);
    if (risk <= 0.001) continue;
    const blocked = playbackUsesBeaconRisk() && risk >= blockThreshold;
    ctx.beginPath();
    for (const ring of space.rings) ring.forEach((p, i) => {
      const q = project(p);
      if (i) ctx.lineTo(q[0], q[1]);
      else ctx.moveTo(q[0], q[1]);
    });
    ctx.closePath();
    ctx.globalAlpha = blocked ? 0.62 : 0.08 + risk * 0.18;
    ctx.fillStyle = blocked ? "#b91c1c" : risk > 0.66 ? "#f97316" : risk > 0.33 ? "#facc15" : "#86efac";
    ctx.fill();
    const label = project(point);
    if (blocked) {
      drawCanvasBadge(label[0], label[1], [`BLOCKED`], "#7f1d1d", "#ffffff");
    }
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}
function drawBeaconRiskEdges(level, project) {
  return;
}
function drawCanvasBadge(x, y, lines, background, foreground) {
  const fontSize = 9 * devicePixelRatio;
  const paddingX = 5 * devicePixelRatio;
  const paddingY = 3 * devicePixelRatio;
  ctx.save();
  ctx.font = `${fontSize}px Segoe UI, Arial`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const widths = lines.map(line => ctx.measureText(line).width);
  const width = Math.max(...widths) + paddingX * 2;
  const lineHeight = fontSize + 2 * devicePixelRatio;
  const height = lines.length * lineHeight + paddingY * 2;
  const left = x - width / 2;
  const top = y - height / 2;
  ctx.globalAlpha = 0.92;
  ctx.fillStyle = background;
  ctx.fillRect(left, top, width, height);
  ctx.globalAlpha = 1;
  ctx.strokeStyle = background === "#ffffff" ? "#475569" : background;
  ctx.lineWidth = 0.8 * devicePixelRatio;
  ctx.strokeRect(left, top, width, height);
  ctx.fillStyle = foreground;
  lines.forEach((line, index) => {
    ctx.fillText(line, x, top + paddingY + lineHeight * index + lineHeight / 2);
  });
  ctx.restore();
}
function isVirtualEdge(edge) {
  return String(edge.viaBoundaryRef || "").includes("VIRTUAL") || String(edge.source || "").startsWith("VTN_") || String(edge.target || "").startsWith("VTN_");
}
function edgeVisibleOnLevel(edge, level) {
  if (edge.sourceLevel === level || edge.targetLevel === level) return true;
  return Array.isArray(edge.levels) && edge.levels.includes(level);
}
function boundaryVisibleOnLevel(boundary, level) {
  if (boundary.level === level) return true;
  return Array.isArray(boundary.levels) && boundary.levels.includes(level);
}
function isConnectorAccessEdge(edge) {
  return ["Stair","Ramp","Elevator"].includes(edge.sourceCategory) || ["Stair","Ramp","Elevator"].includes(edge.targetCategory);
}
function graphEdgeColor(edge) {
  return "#94a3b8";
}
function drawSpaceLabel(space, project) {
  const ring = (space.rings && space.rings[0]) || [];
  if (!ring.length) return;
  const avg = ring.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1]], [0, 0]).map(v => v / ring.length);
  const p = project(avg);
  ctx.save();
  ctx.font = `${9 * devicePixelRatio}px Segoe UI, Arial`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = "#111827";
  ctx.fillText(space.category === "Stair" ? "STAIR" : "RAMP", p[0], p[1]);
  ctx.restore();
}
function drawConnectorLabels(level, project) {
  const groups = new Map();
  for (const space of activeSpaces()) if (space.level === level && (space.category === "Stair" || space.category === "Ramp")) {
    const match = String(space.id).match(/VC_[0-9]+/);
    const key = `${space.category}:${match ? match[0] : space.id}`;
    if (!groups.has(key)) groups.set(key, { category: space.category, points: [] });
    const ring = (space.rings && space.rings[0]) || [];
    for (const point of ring) groups.get(key).points.push(point);
  }
  for (const group of groups.values()) {
    if (!group.points.length) continue;
    const avg = group.points.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1]], [0, 0]).map(v => v / group.points.length);
    const p = project(avg);
    ctx.save();
    ctx.font = `${10 * devicePixelRatio}px Segoe UI, Arial`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "#111827";
    ctx.fillText(group.category === "Stair" ? "STAIR" : "RAMP", p[0], p[1]);
    ctx.restore();
  }
}
function drawManualAgents(level, project) {
  const agents = readManualAgents();
  for (const agent of agents) {
    const cell = model.cells.find(c => c.id === agent.initialCellSpaceRef);
    if (cell && cell.level !== level) continue;
    const coords = agent.initialPosition && agent.initialPosition.coordinates;
    if (!coords || coords.length < 2) continue;
    const p = project(coords);
    const color = profileColors[agent.mobilityProfileRef] || "#006dff";
    ctx.beginPath();
    ctx.arc(p[0], p[1], agentBodyRadiusPx(level, agent.mobilityProfileRef, null), 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.strokeStyle = "#111827";
    ctx.fill();
    ctx.stroke();
  }
}
function drawAutomaticAgents(level, project) {
  if (!model) return;
  const agents = automaticAgentsFromControls();
  const color = profileColors[$("autoProfile").value] || "#006dff";
  ctx.save();
  ctx.globalAlpha = 0.74;
  for (const agent of agents) {
    const cell = model.cells.find(c => c.id === agent.initialCellSpaceRef);
    if (cell && cell.level !== level) continue;
    const coords = agent.initialPosition && agent.initialPosition.coordinates;
    if (!coords || coords.length < 2) continue;
    const p = project(coords);
    ctx.beginPath();
    ctx.arc(p[0], p[1], agentBodyRadiusPx(level, agent.mobilityProfileRef || $("autoProfile").value, null), 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.4 * devicePixelRatio;
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}
function drawBeacons(level, project) {
  const beacons = playbackBeacons();
  const selectedId = $("beaconSelect").value || $("beaconId").value.trim();
  for (const beacon of beacons) {
    if (beacon.levelRef !== level) continue;
    const coordinates = beacon.position && beacon.position.coordinates;
    if (!coordinates || coordinates.length < 2) continue;
    const p = project(coordinates);
    const radiusM = Number((beacon.influence || {}).radiusM || 0);
    const risk = clamp(Number((beacon.effects || {}).riskPenalty || 0), 0, 1);
    const selected = beacon.beaconId === selectedId;
    const color = selected ? "#7c3aed" : "#0f766e";
    if (radiusM > 0) {
      const edge = project([coordinates[0] + radiusM, coordinates[1]]);
      const pixelRadius = Math.abs(edge[0] - p[0]);
      ctx.save();
      ctx.globalAlpha = 0.08 + risk * 0.16;
      ctx.beginPath();
      ctx.arc(p[0], p[1], pixelRadius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.globalAlpha = 0.45;
      ctx.strokeStyle = color;
      ctx.setLineDash([4 * devicePixelRatio, 4 * devicePixelRatio]);
      ctx.stroke();
      ctx.restore();
    }
    if (selected) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(p[0], p[1], 14 * devicePixelRatio, 0, Math.PI * 2);
      ctx.strokeStyle = "#7c3aed";
      ctx.lineWidth = 2.5 * devicePixelRatio;
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(p[0] - 18 * devicePixelRatio, p[1]);
      ctx.lineTo(p[0] - 10 * devicePixelRatio, p[1]);
      ctx.moveTo(p[0] + 10 * devicePixelRatio, p[1]);
      ctx.lineTo(p[0] + 18 * devicePixelRatio, p[1]);
      ctx.moveTo(p[0], p[1] - 18 * devicePixelRatio);
      ctx.lineTo(p[0], p[1] - 10 * devicePixelRatio);
      ctx.moveTo(p[0], p[1] + 10 * devicePixelRatio);
      ctx.lineTo(p[0], p[1] + 18 * devicePixelRatio);
      ctx.stroke();
      ctx.restore();
    }
    ctx.save();
    ctx.translate(p[0], p[1]);
    ctx.rotate(Math.PI / 4);
    ctx.fillStyle = color;
    ctx.strokeStyle = "#111827";
    ctx.lineWidth = 1.2 * devicePixelRatio;
    ctx.fillRect(-5 * devicePixelRatio, -5 * devicePixelRatio, 10 * devicePixelRatio, 10 * devicePixelRatio);
    ctx.strokeRect(-5 * devicePixelRatio, -5 * devicePixelRatio, 10 * devicePixelRatio, 10 * devicePixelRatio);
    ctx.restore();
    ctx.save();
    ctx.font = `${9 * devicePixelRatio}px Segoe UI, Arial`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = "#111827";
    ctx.restore();
  }
}
function drawTraces(level, project) {
  const step = currentFrame / 4;
  ctx.lineWidth = 1.25 * devicePixelRatio;
  for (const sourceRows of trajectoryByAgent.values()) {
    const rows = [];
    for (const row of sourceRows) {
      if (row.step > step) break;
      if (row.levelRef === level) rows.push(row);
    }
    if (rows.length < 2) continue;
    ctx.beginPath();
    rows.forEach((row, index) => {
      const p = project([row.x,row.y]);
      if (index) ctx.lineTo(p[0],p[1]); else ctx.moveTo(p[0],p[1]);
    });
    const last = rows[rows.length - 1];
    ctx.strokeStyle = (profileColors[last.profileId] || "#2563eb") + "88";
    ctx.stroke();
  }
}
function drawEmpty(message) {
  canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle = "#f8fafc";
  ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle = "#334155";
  ctx.font = `${18 * devicePixelRatio}px Segoe UI, Arial`;
  ctx.textAlign = "center";
  ctx.fillText(message, canvas.width / 2, canvas.height / 2);
}
setupSidebarSections();
rememberControlTitles();
$("reload").onclick = loadModel;
$("openLibraryScenario").onclick = () => openLibraryScenario().catch(err => $("metrics").textContent = err.message);
$("openLibraryIndoor").onclick = () => openLibraryIndoor().catch(err => $("metrics").textContent = err.message);
$("openModelScenario").onclick = () => openModelScenario().catch(err => $("metrics").textContent = err.message);
$("saveScenario").onclick = () => saveScenario().catch(err => $("metrics").textContent = err.message);
$("autoTab").onclick = () => setAgentMode("automatic");
$("manualTab").onclick = () => setAgentMode("manual");
$("spawnCell").onchange = () => {
  const point = selectedCellPoint($("spawnCell").value);
  if (point) { $("spawnX").value = point[0]; $("spawnY").value = point[1]; }
  const transfer = nearestTransferForCell($("spawnCell").value, node => !node.isExit);
  if (transfer && $("cerOrigin")) $("cerOrigin").value = transfer.id;
  drawModelPreview();
  updateCerPickStatus();
  updateControlAvailability();
};
$("agentCount").oninput = () => { drawModelPreview(); updateControlAvailability(); };
$("autoProfile").onchange = drawModelPreview;
$("spawnX").oninput = drawModelPreview;
$("spawnY").oninput = drawModelPreview;
$("distribution").onchange = () => { drawModelPreview(); updateControlAvailability(); };
$("setAutoBatch").onclick = addAutomaticBatchToManualAgents;
$("deleteAutoBatch").onclick = deleteManualAgentsInSelectedCell;
$("placementMode").onclick = () => {
  $("placementMode").textContent = $("placementMode").textContent === "On" ? "Off" : "On";
};
$("clearManualAgents").onclick = () => {
  $("manualAgents").value = "[]";
  payload = null;
  drawModelPreview();
  updateControlAvailability();
};
$("beaconSelect").onchange = loadSelectedBeacon;
$("newBeacon").onclick = resetBeaconForm;
$("saveBeacon").onclick = () => saveBeacon();
$("deleteBeacon").onclick = deleteSelectedBeacon;
$("refreshBeaconPreview").onclick = () => { updateBeaconImpactPreview(); draw(); };
$("beaconPlacementMode").onclick = () => {
  $("beaconPlacementMode").textContent = $("beaconPlacementMode").textContent === "On" ? "Off" : "On";
};
$("beacons").onchange = () => {
  refreshBeaconSelect();
  loadSelectedBeacon();
};
$("events").onchange = () => loadSelectedBeacon();
$("seedBeaconCurve").onclick = () => seedBeaconCurve();
$("applyBeaconCurve").onclick = generateBeaconCurveEvents;
$("clearBeaconCurvePoint").onclick = deleteSelectedCurvePoint;
$("beaconCurvePoints").oninput = () => { drawBeaconCurve(); updateBeaconImpactPreview(); draw(); };
$("beaconCurve").onmousedown = startCurveDrag;
$("beaconCurve").onmousemove = dragCurvePoint;
$("beaconCurve").onmouseup = stopCurveDrag;
$("beaconCurve").onmouseleave = stopCurveDrag;
$("timeStep").oninput = () => { updateDurationHint(); drawBeaconCurve(); updateBeaconImpactPreview(); draw(); };
$("maxSteps").oninput = () => { updateDurationHint(); drawBeaconCurve(); updateBeaconImpactPreview(); draw(); };
$("useBeaconRisk").onchange = () => { updateRoutingParameterStatus(); updateBeaconImpactPreview(); draw(); };
$("beaconBlockThreshold").oninput = () => { updateBeaconImpactPreview(); draw(); };
$("destinationMode").onchange = updateControlAvailability;
$("destinationCell").onchange = () => {
  if ($("cerTarget")) {
    const target = transferNodeById($("destinationCell").value) || nearestTransferForCell($("destinationCell").value, node => node.isExit);
    if (target) $("cerTarget").value = target.id;
  }
  updateCerPickStatus();
  draw();
};
$("recordGif").onchange = updateControlAvailability;
$("recordHtml").onchange = updateControlAvailability;
$("manualAgents").oninput = updateControlAvailability;
$("routingPreset").onchange = updateRoutingPresetInfo;
$("applyRoutingPreset").onclick = applySelectedRoutingPreset;
$("runRoutingPreset").onclick = () => runSelectedRoutingPreset().catch(err => $("metrics").textContent = err.message);
$("compareRoutingPresets").onclick = () => compareSelectedRoutingPresets().catch(err => $("routingResults").textContent = err.message);
$("saveRoutingComparison").onclick = () => saveRoutingComparison().catch(err => $("routingResults").textContent = err.message);
$("saveCerDebug").onclick = () => saveCerDebug().catch(err => $("cerResults").textContent = err.message);
$("pickCerOrigin").onclick = () => setCerPickMode("origin");
$("pickCerTarget").onclick = () => setCerPickMode("target");
$("cerOrigin").onchange = () => { updateCerPickStatus(); draw(); };
$("cerTarget").onchange = () => { updateCerPickStatus(); draw(); };
$("cerDebugSection").ontoggle = () => { updateCerPickStatus(); draw(); };
$("run").onclick = () => runSimulation().catch(err => $("metrics").textContent = err.message);
$("recordSimulation").onclick = () => recordSimulation().catch(err => $("metrics").textContent = err.message);
$("play").onclick = () => {
  if (timer) {
    clearInterval(timer);
    timer = null;
    $("play").textContent = "Play";
    return;
  }
  const delayMs = Math.max(20, Number($("playbackMs").value || 80));
  timer = setInterval(() => {
    currentFrame = currentFrame >= Number($("frame").max) ? 0 : currentFrame + 1;
    draw();
  }, delayMs);
  $("play").textContent = "Pause";
};
$("reset").onclick = () => { currentFrame=0; draw(); };
$("frame").oninput = e => { currentFrame = Number(e.target.value); draw(); };
$("level").onchange = draw;
[
  "algorithm", "costPolicy", "riskCostModel", "riskEndpointPolicy", "useHazardRisk",
  "useCongestion", "riskEdgePrecedence", "riskAggregation", "riskAlpha", "hazardBeta",
  "beaconBeta", "riskUnitCost", "routeSelection", "kShortestPaths",
  "candidateCostTolerance", "robustnessTolerance", "centralityTolerance",
  "centralityMaxPaths", "centralityMaxOverlap", "costWeight", "robustnessWeight",
  "agilityWeight", "agilityAggregation", "centralityType", "reroutingFailureProfiles",
  "reroutingCostTolerance", "reroutingFailureUnit", "reroutingDistinctnessPolicy",
  "reroutingMaxCombinations", "reroutingMaxRuntimeMs", "reroutingUseStructuralPrecompute"
].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener("input", () => updateRoutingParameterStatus());
  if (el) el.addEventListener("change", () => updateRoutingParameterStatus());
});
canvas.onclick = event => {
  if (!model) return;
  if ($("beaconPlacementMode").textContent === "On") {
    placeBeaconFromClick(event);
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const point = [event.clientX - rect.left, event.clientY - rect.top].map(v => v * devicePixelRatio);
  const level = $("level").value || model.levels[0];
  const world = unprojectFor(level)(point);
  if (cerPickMode) {
    pickCerTransferFromClick(level, world);
    return;
  }
  if (activeAgentMode() === "automatic") {
    const cell = cellAt(level, world);
    if (!cell) {
      $("metrics").textContent = "Spawn selection ignored: click inside a GeneralSpace room.";
      return;
    }
    $("spawnCell").value = cell.id;
    $("spawnX").value = Number(world[0].toFixed(3));
    $("spawnY").value = Number(world[1].toFixed(3));
    payload = null;
    $("metrics").textContent = `Automatic spawn selected: ${cell.id}. Press Run simulation or SET batch.`;
    drawModelPreview();
    return;
  }
  if ($("placementMode").textContent !== "On") return;
  const cell = cellAt(level, world);
  if (!cell) {
    $("metrics").textContent = "Click ignored: position is not inside a navigable cell.";
    return;
  }
  const agents = readManualAgents();
  agents.push({
    agentId: nextManualAgentId(agents),
    mobilityProfileRef: $("placementProfile").value || model.profiles[0],
    initialCellSpaceRef: cell.id,
    initialPosition: { type: "Point", coordinates: [Number(world[0].toFixed(3)), Number(world[1].toFixed(3))] }
  });
  writeManualAgents(agents);
  $("metrics").textContent = `Added ${agents[agents.length - 1].agentId} in ${cell.id}. Press Run simulation.`;
};
function setCerPickMode(mode) {
  cerPickMode = cerPickMode === mode ? null : mode;
  if (mode) {
    $("cerDebugSection").open = true;
    $("beaconPlacementMode").textContent = "Off";
    $("placementMode").textContent = "Off";
  }
  updateCerPickStatus();
  draw();
}
function pickCerTransferFromClick(level, world) {
  const predicate = cerPickMode === "target" ? (node => node.isExit) : (node => !node.isExit);
  let node = nearestTransfer(level, world, predicate);
  if (!node && cerPickMode === "target") node = nearestTransfer(level, world);
  if (!node) {
    $("cerPickStatus").textContent = `No transfer node found on ${level}.`;
    return;
  }
  if (cerPickMode === "origin") $("cerOrigin").value = node.id;
  else $("cerTarget").value = node.id;
  $("cerResults").textContent = `Selected CER ${cerPickMode}: ${cerNodeLabel(node)}`;
  cerPickMode = null;
  updateCerPickStatus();
  draw();
}
function readManualAgents() {
  try { return JSON.parse($("manualAgents").value || "[]"); } catch { return []; }
}
function cellAt(level, point) {
  return spaceAt(level, point, "spawn");
}
function spaceAt(level, point, mode = "any") {
  const candidates = model.spaces.filter(s => {
    if (s.level !== level) return false;
    if (mode === "spawn") return spaceIsSpawnable(s);
    if (mode === "navigable") return s.isNavigable;
    return true;
  });
  for (let i = candidates.length - 1; i >= 0; i--) {
    const space = candidates[i];
    if (space.rings.some(ring => pointInRing(point, ring))) return space;
  }
  return null;
}
function pointInRing(point, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
    const intersect = ((yi > point[1]) !== (yj > point[1])) && (point[0] < (xj - xi) * (point[1] - yi) / ((yj - yi) || 1e-12) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}
addEventListener("resize", () => draw());
async function boot() {
  try {
    await loadLibrary();
    await loadModel();
  } catch (err) {
    $("summary").textContent = "Model load failed";
    $("metrics").textContent = err.message;
  }
}
boot();
</script>
</body>
</html>
"""

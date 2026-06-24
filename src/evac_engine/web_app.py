"""Local browser workbench for EvacEngine.

This is intentionally dependency-free: stdlib HTTP server plus the existing
Python runtime. It lets a user configure a scenario, run the simulation, and
inspect a smooth canvas playback without relying on Tk/Tcl.
"""

from __future__ import annotations

import json
import copy
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .domain import ScenarioDefinition
from .loaders import load_project
from .simulation import EvacuationModel
from .visualization import build_visualization_payload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCENARIO = "examples/indoor_data_model/scenario_single_floor.json"
MODEL_LIBRARY_ROOT = PROJECT_ROOT / "examples/indoor_data_model"


def run_workbench(
    host: str = "127.0.0.1",
    port: int = 8765,
    scenario_path: str | None = None,
    library_root: str | Path | None = None,
) -> None:
    default_scenario = scenario_path or DEFAULT_SCENARIO
    resolved_library_root = _workspace_path(library_root or MODEL_LIBRARY_ROOT)

    class Handler(WorkbenchHandler):
        scenario_default = default_scenario
        library_root = resolved_library_root

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"EvacEngine workbench: http://{host}:{port}/?scenario={default_scenario}")
    print(f"Model library root: {resolved_library_root}")
    server.serve_forever()


class WorkbenchHandler(BaseHTTPRequestHandler):
    scenario_default = DEFAULT_SCENARIO
    library_root = MODEL_LIBRARY_ROOT

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path == "/":
            html = WORKBENCH_HTML.replace("__DEFAULT_SCENARIO__", self.scenario_default.replace("\\", "/"))
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
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            request = json.loads(body or "{}")
            self._send_json(run_configured_simulation(request, self.scenario_default))
        except Exception as exc:  # pragma: no cover - manual endpoint guard.
            self.send_response(500)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_html(self, html: str) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, payload: dict[str, Any]) -> None:
        self.send_response(200)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=True).encode("utf-8"))


def load_model_summary(indoor_path: str | None, scenario_path: str) -> dict[str, Any]:
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
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
        "levels": sorted(indoor.levels_by_id),
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
            "costPolicy": scenario.routing.get("costPolicy", "shortest_distance"),
            "useBeaconRisk": bool(scenario.routing.get("useBeaconRisk", True)),
            "beaconBlockThreshold": scenario.routing.get("beaconBlockThreshold", 0.85),
            "firstGroupCount": scenario.groups[0].get("count") if scenario.groups else 0,
            "firstSpawnCell": scenario.spawns[0].get("cellSpaceRef") if scenario.spawns else "",
            "firstSpawnPosition": (scenario.spawns[0].get("position") or {}).get("coordinates") if scenario.spawns else None,
            "firstGroupDistribution": scenario.groups[0].get("distribution", "random_within_space") if scenario.groups else "random_within_space",
            "destinationCells": (scenario.routing.get("destination") or {}).get("cellSpaceRefs") or [],
        },
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
    roots = [MODEL_LIBRARY_ROOT]
    if root_path.resolve() != MODEL_LIBRARY_ROOT.resolve():
        roots.append(root_path)
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
    return {"scenarios": scenarios, "indoorModels": indoor_models}


def _scan_model_library_root(root: Path) -> dict[str, list[dict[str, str]]]:
    scenarios: list[dict[str, str]] = []
    indoor_models: list[dict[str, str]] = []
    root_path = _workspace_path(root)
    if not root_path.exists():
        return {"scenarios": scenarios, "indoorModels": indoor_models}
    for path in sorted(root_path.glob("*.json")):
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


def _looks_like_indoor_model(path: Path) -> bool:
    return path.name.endswith("indoor_model.json")


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


def run_configured_simulation(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    scenario_path = request.get("scenarioPath") or default_scenario
    indoor_path = request.get("indoorPath") or None
    indoor, scenario = load_project(_workspace_path(indoor_path) if indoor_path else None, _workspace_path(scenario_path))
    apply_request_to_scenario(scenario, request)
    run_beacons = copy.deepcopy(scenario.beacons)
    run_events = copy.deepcopy(scenario.raw.get("scheduledEvents") or [])
    run_routing = {
        "useBeaconRisk": bool(scenario.routing.get("useBeaconRisk", True)),
        "beaconBlockThreshold": scenario.routing.get("beaconBlockThreshold", 0.85),
    }
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


def apply_request_to_scenario(scenario: ScenarioDefinition, request: dict[str, Any]) -> None:
    config = request.get("config") or {}
    if config.get("timeStepS") is not None:
        scenario.simulation_config["timeStepS"] = float(config["timeStepS"])
    if config.get("maxSteps") is not None:
        scenario.simulation_config["maxSteps"] = int(config["maxSteps"])
    if config.get("randomSeed") is not None:
        scenario.simulation_config["randomSeed"] = int(config["randomSeed"])
    if config.get("algorithm"):
        scenario.routing["algorithm"] = config["algorithm"]
    if config.get("costPolicy"):
        scenario.routing["costPolicy"] = config["costPolicy"]
    if config.get("useBeaconRisk") is not None:
        scenario.routing["useBeaconRisk"] = bool(config["useBeaconRisk"])
    if config.get("beaconBlockThreshold") is not None:
        scenario.routing["beaconBlockThreshold"] = float(config["beaconBlockThreshold"])
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
    main { min-width: 0; display: grid; grid-template-rows: 1fr 150px; }
    canvas { width: 100%; height: 100%; display: block; background: #f8fafc; }
    h1 { font-size: 19px; margin: 0 0 8px; }
    h2 { font-size: 14px; margin: 18px 0 6px; color: #334155; }
    label { display: block; font-size: 12px; color: #475569; margin-top: 9px; }
    input, select, textarea, button { width: 100%; box-sizing: border-box; margin-top: 4px; padding: 7px; border-radius: 4px; border: 1px solid #94a3b8; background: #fff; }
    select { min-height: 36px; color: #0f172a; }
    select:disabled { color: #64748b; background: #f8fafc; }
    textarea { min-height: 96px; resize: vertical; font-family: Consolas, monospace; font-size: 12px; }
    button { border-color: #0f172a; background: #0f172a; color: white; cursor: pointer; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .tabs { display: flex; gap: 6px; margin-top: 8px; }
    .tabs button { width: auto; flex: 1; border-color: #cbd5e1; background: #e2e8f0; color: #0f172a; }
    .tabs button.active { border-color: #0f172a; background: #0f172a; color: #fff; }
    .tab-panel[hidden] { display: none; }
    .mini-canvas { display: block; width: 100%; height: 116px; margin-top: 4px; border: 1px solid #94a3b8; border-radius: 4px; background: #fff; }
    .status-box { margin-top: 8px; padding: 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; font-family: Consolas, monospace; font-size: 12px; line-height: 1.35; color: #334155; white-space: pre-wrap; font-variant-numeric: tabular-nums; }
    .toolbar { display: flex; gap: 8px; align-items: center; padding: 10px; border-top: 1px solid #cbd5e1; background: #fff; }
    .toolbar button { width: auto; min-width: 80px; }
    .toolbar input, .toolbar select { width: auto; flex: 1; }
    pre { margin: 0; overflow: auto; background: #f1f5f9; padding: 10px; font-size: 12px; }
    .muted { color: #64748b; font-size: 12px; }
  </style>
</head>
<body>
<div class="app">
  <aside>
    <h1>EvacEngine Workbench</h1>
    <div class="muted" id="summary">Loading model...</div>
    <pre id="help">1. Carga o revisa el scenario.
2. Ajusta agentes, spawn, destino, timestep o balizas.
3. Pulsa Run simulation.
4. Usa Play o el slider para revisar el movimiento.</pre>
    <label>Scenario path</label>
    <input id="scenarioPath">
    <label>Indoor model path</label>
    <input id="indoorPath" placeholder="Leave empty to use scenario.indoorModelRef.path">
    <button id="reload">Reload scenario</button>
    <h2>Simulation</h2>
    <div class="row">
      <div><label>Time step</label><input id="timeStep" type="number" step="0.05"></div>
      <div><label>Max steps</label><input id="maxSteps" type="number"></div>
    </div>
    <label>Seed</label><input id="seed" type="number">
    <div class="row">
      <div><label>Destination mode</label><select id="destinationMode"><option value="scenario">All scenario exits</option><option value="selected">Selected only</option></select></div>
      <div><label>Destination exit/cell</label><select id="destinationCell"></select></div>
    </div>
    <div class="row">
      <div><label>Algorithm</label><select id="algorithm"><option>dijkstra</option><option>astar</option><option>yen_ksp</option><option>robust_agility</option></select></div>
      <div><label>Cost</label><select id="costPolicy"><option>shortest_distance</option><option>minimum_travel_time</option></select></div>
    </div>
    <label><input id="useBeaconRisk" type="checkbox" style="width:auto"> Use beacon risk in routing</label>
    <label><input id="includeGeometryQa" type="checkbox" style="width:auto"> Geometry QA</label>
    <h2>Agents</h2>
    <div class="tabs">
      <button id="autoTab" class="active" type="button">Automatic</button>
      <button id="manualTab" type="button">Manual</button>
    </div>
    <section id="autoPanel" class="tab-panel">
      <label>Agents</label><input id="agentCount" type="number">
      <label>Spawn cell</label>
      <select id="spawnCell"></select>
      <div class="row">
        <div><label>Spawn X</label><input id="spawnX" type="number" step="0.05"></div>
        <div><label>Spawn Y</label><input id="spawnY" type="number" step="0.05"></div>
      </div>
      <label>Group distribution</label>
      <select id="distribution"><option>random_within_space</option><option>fixed</option></select>
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
      <div><label>Risk penalty</label><input id="beaconRisk" type="number" min="0" max="1" step="0.05" value="0.4"></div>
      <div><label>Radius m</label><input id="beaconRadius" type="number" min="0" step="0.1" value="3"></div>
    </div>
    <div class="row">
      <div><label>Inner radius m</label><input id="beaconInnerRadius" type="number" min="0" step="0.1" value="0"></div>
      <div><label>Block threshold</label><input id="beaconBlockThreshold" type="number" min="0" max="1" step="0.05" value="0.85"></div>
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
    <label>Risk curve preview</label>
    <canvas id="beaconCurve" class="mini-canvas"></canvas>
    <label>timeS -> riskPenalty points</label>
    <textarea id="beaconCurvePoints" placeholder="0, 0.1&#10;30, 0.7&#10;90, 0.2"></textarea>
    <div class="row">
      <button id="seedBeaconCurve" type="button">Seed duration</button>
      <button id="applyBeaconCurve" type="button">Generate events</button>
    </div>
    <div id="beaconImpact" class="status-box">Beacon impact preview will appear after the model loads.</div>
    <textarea id="beacons"></textarea>
    <h2>Dynamic Events</h2>
    <textarea id="events"></textarea>
    <button id="run">Run simulation</button>
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
      <pre id="metrics">Run a simulation to see metrics and QA.</pre>
    </div>
  </main>
</div>
<script>
const qs = new URLSearchParams(location.search);
const defaultScenario = qs.get("scenario") || "__DEFAULT_SCENARIO__";
const defaultIndoor = qs.get("indoor") || "";
const $ = id => document.getElementById(id);
let model = null, payload = null, currentFrame = 0, timer = null, trajectoryByAgent = new Map();
let beaconDraftMode = true;
let draggedCurvePointIndex = null;
let selectedCurvePointIndex = null;
$("scenarioPath").value = defaultScenario;
$("indoorPath").value = defaultIndoor;
const profileColors = { MP_WALKING: "#006dff", MP_WALKING_VERTICAL: "#006dff", MP_WALKING_ROLLING: "#0891b2", MP_ROLLING_ACCESSIBLE: "#c026d3", MP_ELDERLY: "#16a34a", MP_CHILD: "#f59e0b" };
const statusColors = { active: "#006dff", evacuated: "#1a9f52", no_route: "#c0392b", trapped: "#8e44ad" };
const canvas = $("canvas"), ctx = canvas.getContext("2d");
const beaconCurve = $("beaconCurve"), beaconCurveCtx = beaconCurve.getContext("2d");

async function loadModel() {
  $("summary").textContent = "Loading model...";
  const indoor = $("indoorPath").value.trim() ? `&indoor=${encodeURIComponent($("indoorPath").value.trim())}` : "";
  const res = await fetch(`/api/model?scenario=${encodeURIComponent($("scenarioPath").value)}${indoor}`);
  if (!res.ok) throw new Error(`Could not load model: HTTP ${res.status}`);
  model = await res.json();
  if (model.error) throw new Error(model.error);
  $("summary").textContent = `${model.scenarioId} | ${model.levels.join(", ")}`;
  fillSelect($("spawnCell"), model.cells.filter(c => c.category !== "Exit"), c => `${c.level} ${c.id} [${c.x}, ${c.y}]`, c => c.id);
  fillSelect($("destinationCell"), model.exits.length ? model.exits : model.cells, c => `${c.level} ${c.id}`, c => c.id);
  fillSelect($("level"), model.levels.map(level => ({id: level, label: levelLabel(level, null)})), c => c.label, c => c.id);
  fillSelect($("placementProfile"), model.profiles.map(profile => ({id: profile})), c => c.id, c => c.id);
  $("timeStep").value = model.config.timeStepS;
  $("maxSteps").value = model.config.maxSteps;
  $("seed").value = model.config.randomSeed;
  $("agentCount").value = model.config.firstGroupCount;
  $("spawnCell").value = model.config.firstSpawnCell;
  const spawn = model.config.firstSpawnPosition || selectedCellPoint($("spawnCell").value);
  $("spawnX").value = spawn ? spawn[0] : "";
  $("spawnY").value = spawn ? spawn[1] : "";
  $("distribution").value = model.config.firstGroupDistribution || "random_within_space";
  $("destinationMode").value = "scenario";
  $("destinationCell").value = model.config.destinationCells[0] || (model.exits[0] && model.exits[0].id) || "";
  $("algorithm").value = model.config.algorithm;
  $("costPolicy").value = model.config.costPolicy;
  $("useBeaconRisk").checked = Boolean(model.config.useBeaconRisk);
  $("beaconBlockThreshold").value = String(model.config.beaconBlockThreshold ?? 0.85);
  $("manualAgents").value = JSON.stringify(model.manualAgents.length ? model.manualAgents : [], null, 2);
  $("beacons").value = JSON.stringify(model.beacons, null, 2);
  $("events").value = JSON.stringify(model.scheduledEvents, null, 2);
  refreshBeaconSelect();
  loadSelectedBeacon();
  payload = null;
  $("metrics").textContent = "Scenario loaded. Configure values on the left, then press Run simulation.";
  drawModelPreview();
  drawBeaconCurve();
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
  const request = {
    scenarioPath: $("scenarioPath").value,
    indoorPath: $("indoorPath").value.trim() || null,
    config: {
      timeStepS: Number($("timeStep").value),
      maxSteps: Number($("maxSteps").value),
      randomSeed: Number($("seed").value),
      firstGroupCount: Number($("agentCount").value),
      firstSpawnCell: $("spawnCell").value,
      firstSpawnPosition: [Number($("spawnX").value), Number($("spawnY").value)],
      firstGroupDistribution: $("distribution").value,
      destinationCells: destinationCellsForRun(),
      algorithm: $("algorithm").value,
      costPolicy: $("costPolicy").value,
      useBeaconRisk: $("useBeaconRisk").checked,
      beaconBlockThreshold: Number($("beaconBlockThreshold").value),
      includeGeometryQa: $("includeGeometryQa").checked
    },
    manualAgents: activeAgentMode() === "manual" ? JSON.parse($("manualAgents").value || "[]") : [],
    beacons: JSON.parse($("beacons").value || "[]"),
    scheduledEvents: JSON.parse($("events").value || "[]")
  };
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
  $("metrics").textContent = JSON.stringify({ metrics: payload.metrics, qa: payload.qa }, null, 2);
  draw();
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
    beaconCurveCtx.fillText("Add time, risk points or click the graph", w / 2, h / 2);
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
  $("metrics").textContent = `Generated ${generated.length} scheduledEvents for ${beaconId}. Press Run simulation.`;
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
    ? `${selected.beaconId}\nlevel ${selected.levelRef}\nspace ${((selected.attributes || {}).attachedSpaceRef || "no attachedSpaceRef")}\nrisk ${formatFixed(selectedRuntime.riskPenalty, 2)} | safety ${formatFixed(1 - selectedRuntime.riskPenalty, 2)}`
    : "none selected";
  const topRows = rows.slice(0, 8).map(row => {
    const safety = 1 - row.risk;
    const blocked = row.risk >= blockThreshold && playbackUsesBeaconRisk();
    return `${row.id}: safety ${formatFixed(safety, 2)} | risk ${formatFixed(row.risk, 2)}${blocked ? " BLOCKED" : ""}`;
  }).join("\\n") || "none at current time";
  $("beaconImpact").textContent =
    `Safety preview ${mode}\\n` +
    `time ${formatFixed(timeS, 1)}s | beacons ${beacons.length}\\n` +
    `block risk >= ${formatFixed(blockThreshold, 2)} | block safety <= ${formatFixed(1 - blockThreshold, 2)}\\n` +
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
function spaceIsNavigable(space) {
  if (space.isNavigable != null) return Boolean(space.isNavigable);
  return space.navigationType === "GeneralSpace" || space.navigationType === "TransferSpace";
}
function projectFor(level) {
  const [minX,minY,maxX,maxY] = bounds(level), pad = 26 * devicePixelRatio;
  const scale = Math.min((canvas.width-pad*2)/Math.max(maxX-minX,1), (canvas.height-pad*2)/Math.max(maxY-minY,1));
  return ([x,y]) => [pad+(x-minX)*scale, canvas.height-pad-(y-minY)*scale];
}
function unprojectFor(level) {
  const [minX,minY,maxX,maxY] = bounds(level), pad = 26 * devicePixelRatio;
  const scale = Math.min((canvas.width-pad*2)/Math.max(maxX-minX,1), (canvas.height-pad*2)/Math.max(maxY-minY,1));
  return ([x,y]) => [minX + (x-pad)/scale, minY + (canvas.height-pad-y)/scale];
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
  drawBeaconRiskEdges(level, project);
  drawBeacons(level, project);
  drawTraces(level, project);
  for (const r of rowsAt(currentFrame)) if (r.levelRef === level) {
    const p=project([r.x,r.y]), color = r.status === "active" ? (profileColors[r.profileId] || "#006dff") : (statusColors[r.status] || "#64748b");
    if (r.intentX != null && r.status === "active") { const q=project([r.intentX,r.intentY]); ctx.beginPath(); ctx.moveTo(p[0],p[1]); ctx.lineTo(q[0],q[1]); ctx.strokeStyle=color; ctx.setLineDash([4,3]); ctx.stroke(); ctx.setLineDash([]); }
    const bodyScale = r.status === "active" ? 1 : 0.65;
    if (r.status === "active") { ctx.beginPath(); ctx.arc(p[0],p[1],Math.max(r.personalRadiusM*10,7)*devicePixelRatio,0,Math.PI*2); ctx.fillStyle=color+"33"; ctx.fill(); }
    ctx.globalAlpha = r.status === "active" ? 1 : 0.72;
    ctx.beginPath(); ctx.arc(p[0],p[1],Math.max(r.bodyRadiusM*10*bodyScale,3)*devicePixelRatio,0,Math.PI*2); ctx.fillStyle=color; ctx.strokeStyle="#111827"; ctx.fill(); ctx.stroke();
    ctx.globalAlpha = 1;
  }
  $("frame").value = String(currentFrame);
  updateBeaconImpactPreview();
}
function drawModelPreview() {
  if (!model) return drawEmpty("Loading model...");
  canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio;
  const level = $("level").value || model.levels[0], project = projectFor(level);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  drawSpaces(level, project);
  drawBeaconRiskOverlay(level, project);
  drawBeacons(level, project);
  drawManualAgents(level, project);
  updateBeaconImpactPreview();
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
  if (!payload) return;
  ctx.save();
  for (const e of payload.edges) if (e.sourceLevel === level || e.targetLevel === level) {
    if (isVirtualEdge(e)) continue;
    const a=project(e.points[0]), b=project(e.points[1]);
    ctx.beginPath();
    ctx.moveTo(a[0],a[1]);
    ctx.lineTo(b[0],b[1]);
    ctx.globalAlpha = 0.35;
    ctx.strokeStyle = ["Stair","Ramp","Elevator"].includes(e.connectorType) ? "#d97706" : "#64748b";
    ctx.lineWidth = 0.8 * devicePixelRatio;
    ctx.stroke();
  }
  ctx.restore();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
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
    ctx.arc(p[0], p[1], 7 * devicePixelRatio, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.strokeStyle = "#111827";
    ctx.fill();
    ctx.stroke();
  }
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
$("reload").onclick = loadModel;
$("autoTab").onclick = () => setAgentMode("automatic");
$("manualTab").onclick = () => setAgentMode("manual");
$("spawnCell").onchange = () => {
  const point = selectedCellPoint($("spawnCell").value);
  if (point) { $("spawnX").value = point[0]; $("spawnY").value = point[1]; }
};
$("placementMode").onclick = () => {
  $("placementMode").textContent = $("placementMode").textContent === "On" ? "Off" : "On";
};
$("clearManualAgents").onclick = () => {
  $("manualAgents").value = "[]";
  payload = null;
  drawModelPreview();
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
$("timeStep").oninput = () => { drawBeaconCurve(); updateBeaconImpactPreview(); draw(); };
$("maxSteps").oninput = () => { drawBeaconCurve(); updateBeaconImpactPreview(); draw(); };
$("useBeaconRisk").onchange = () => { updateBeaconImpactPreview(); draw(); };
$("beaconBlockThreshold").oninput = () => { updateBeaconImpactPreview(); draw(); };
$("run").onclick = () => runSimulation().catch(err => $("metrics").textContent = err.message);
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
canvas.onclick = event => {
  if (!model) return;
  if ($("beaconPlacementMode").textContent === "On") {
    placeBeaconFromClick(event);
    return;
  }
  if (activeAgentMode() !== "manual" || $("placementMode").textContent !== "On") return;
  const rect = canvas.getBoundingClientRect();
  const point = [event.clientX - rect.left, event.clientY - rect.top].map(v => v * devicePixelRatio);
  const level = $("level").value || model.levels[0];
  const world = unprojectFor(level)(point);
  const cell = cellAt(level, world);
  if (!cell) {
    $("metrics").textContent = "Click ignored: position is not inside a navigable cell.";
    return;
  }
  const agents = readManualAgents();
  const next = agents.length + 1;
  agents.push({
    agentId: `MANUAL_${String(next).padStart(3, "0")}`,
    mobilityProfileRef: $("placementProfile").value || model.profiles[0],
    initialCellSpaceRef: cell.id,
    initialPosition: { type: "Point", coordinates: [Number(world[0].toFixed(3)), Number(world[1].toFixed(3))] }
  });
  $("manualAgents").value = JSON.stringify(agents, null, 2);
  payload = null;
  $("metrics").textContent = `Added ${agents[agents.length - 1].agentId} in ${cell.id}. Press Run simulation.`;
  drawModelPreview();
};
function readManualAgents() {
  try { return JSON.parse($("manualAgents").value || "[]"); } catch { return []; }
}
function cellAt(level, point) {
  return spaceAt(level, point, true);
}
function spaceAt(level, point, navigableOnly) {
  const candidates = model.spaces.filter(s => s.level === level && (!navigableOnly || s.isNavigable));
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

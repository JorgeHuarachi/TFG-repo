"""Local browser workbench for EvacEngine.

This is intentionally dependency-free: stdlib HTTP server plus the existing
Python runtime. It lets a user configure a scenario, run the simulation, and
inspect a smooth canvas playback without relying on Tk/Tcl.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .domain import ScenarioDefinition
from .loaders import load_project
from .simulation import EvacuationModel
from .visualization import build_visualization_payload


DEFAULT_SCENARIO = "examples/indoor_data_model/scenario_single_floor.json"


def run_workbench(host: str = "127.0.0.1", port: int = 8765, scenario_path: str | None = None) -> None:
    default_scenario = scenario_path or DEFAULT_SCENARIO

    class Handler(WorkbenchHandler):
        scenario_default = default_scenario

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"EvacEngine workbench: http://{host}:{port}/?scenario={default_scenario}")
    server.serve_forever()


class WorkbenchHandler(BaseHTTPRequestHandler):
    scenario_default = DEFAULT_SCENARIO

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(WORKBENCH_HTML.replace("__DEFAULT_SCENARIO__", self.scenario_default.replace("\\", "/")))
            return
        if parsed.path == "/api/model":
            query = parse_qs(parsed.query)
            scenario = query.get("scenario", [self.scenario_default])[0]
            indoor_path = query.get("indoor", [None])[0]
            self._send_json(load_model_summary(indoor_path, scenario))
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
    indoor, scenario = load_project(indoor_path, scenario_path)
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
        "scenarioPath": str(Path(scenario_path)),
        "indoorPath": str(indoor.path),
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


def run_configured_simulation(request: dict[str, Any], default_scenario: str) -> dict[str, Any]:
    scenario_path = request.get("scenarioPath") or default_scenario
    indoor, scenario = load_project(request.get("indoorPath") or None, scenario_path)
    apply_request_to_scenario(scenario, request)
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
    textarea { min-height: 96px; resize: vertical; font-family: Consolas, monospace; font-size: 12px; }
    button { border-color: #0f172a; background: #0f172a; color: white; cursor: pointer; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
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
    <button id="reload">Reload scenario</button>
    <h2>Simulation</h2>
    <div class="row">
      <div><label>Time step</label><input id="timeStep" type="number" step="0.05"></div>
      <div><label>Max steps</label><input id="maxSteps" type="number"></div>
    </div>
    <div class="row">
      <div><label>Seed</label><input id="seed" type="number"></div>
      <div><label>Agents</label><input id="agentCount" type="number"></div>
    </div>
    <label>Spawn cell</label>
    <select id="spawnCell"></select>
    <div class="row">
      <div><label>Spawn X</label><input id="spawnX" type="number" step="0.05"></div>
      <div><label>Spawn Y</label><input id="spawnY" type="number" step="0.05"></div>
    </div>
    <label>Group distribution</label>
    <select id="distribution"><option>random_within_space</option><option>fixed</option></select>
    <div class="row">
      <div><label>Destination mode</label><select id="destinationMode"><option value="scenario">All scenario exits</option><option value="selected">Selected only</option></select></div>
      <div><label>Destination exit/cell</label><select id="destinationCell"></select></div>
    </div>
    <div class="row">
      <div><label>Algorithm</label><select id="algorithm"><option>dijkstra</option><option>astar</option></select></div>
      <div><label>Cost</label><select id="costPolicy"><option>shortest_distance</option><option>minimum_travel_time</option></select></div>
    </div>
    <label><input id="includeGeometryQa" type="checkbox" style="width:auto"> Geometry QA</label>
    <h2>Manual Agents</h2>
    <div class="row">
      <div><label>Click profile</label><select id="placementProfile"></select></div>
      <div><label>Click placement</label><button id="placementMode" type="button">On</button></div>
    </div>
    <button id="clearManualAgents" type="button">Clear manual agents</button>
    <textarea id="manualAgents"></textarea>
    <h2>Beacons</h2>
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
        <label>Frame</label><input id="frame" type="range" min="0" max="0" value="0">
      </div>
      <pre id="metrics">Run a simulation to see metrics and QA.</pre>
    </div>
  </main>
</div>
<script>
const qs = new URLSearchParams(location.search);
const defaultScenario = qs.get("scenario") || "__DEFAULT_SCENARIO__";
const $ = id => document.getElementById(id);
let model = null, payload = null, currentFrame = 0, timer = null, trajectoryByAgent = new Map();
$("scenarioPath").value = defaultScenario;
const profileColors = { MP_WALKING: "#006dff", MP_WALKING_VERTICAL: "#006dff", MP_WALKING_ROLLING: "#0891b2", MP_ROLLING_ACCESSIBLE: "#c026d3", MP_ELDERLY: "#16a34a", MP_CHILD: "#f59e0b" };
const statusColors = { active: "#006dff", evacuated: "#1a9f52", no_route: "#c0392b", trapped: "#8e44ad" };
const canvas = $("canvas"), ctx = canvas.getContext("2d");

async function loadModel() {
  const res = await fetch(`/api/model?scenario=${encodeURIComponent($("scenarioPath").value)}`);
  model = await res.json();
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
  $("manualAgents").value = JSON.stringify(model.manualAgents.length ? model.manualAgents : [], null, 2);
  $("beacons").value = JSON.stringify(model.beacons, null, 2);
  $("events").value = JSON.stringify(model.scheduledEvents, null, 2);
  payload = null;
  $("metrics").textContent = "Scenario loaded. Configure values on the left, then press Run simulation.";
  drawModelPreview();
}
function fillSelect(select, rows, labelFn, valueFn) {
  select.innerHTML = "";
  for (const row of rows) {
    const option = document.createElement("option");
    option.value = valueFn(row); option.textContent = labelFn(row);
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
      includeGeometryQa: $("includeGeometryQa").checked
    },
    manualAgents: JSON.parse($("manualAgents").value || "[]"),
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
      rows.push({...a, x: a.x+(b.x-a.x)*t, y: a.y+(b.y-a.y)*t, status: t > .85 ? b.status : a.status});
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
  drawEdges(level, project);
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
}
function drawModelPreview() {
  if (!model) return drawEmpty("Loading model...");
  canvas.width = canvas.clientWidth * devicePixelRatio; canvas.height = canvas.clientHeight * devicePixelRatio;
  const level = $("level").value || model.levels[0], project = projectFor(level);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  drawSpaces(level, project);
  drawManualAgents(level, project);
}
function drawSpaces(level, project) {
  for (const s of activeSpaces()) if (s.level === level) {
    ctx.beginPath();
    for (const ring of s.rings) ring.forEach((p,i)=>{ const q=project(p); if(i)ctx.lineTo(q[0],q[1]); else ctx.moveTo(q[0],q[1]); });
    ctx.closePath();
    const wall = s.navigationType === "NonNavigableSpace" || s.category === "WallSegment" || s.category === "WallJunction" || s.category === "Column";
    ctx.fillStyle = wall ? "#050505" : s.category === "Exit" ? "#75c878" : s.category === "Stair" ? "#d8b4fe" : s.category === "Ramp" ? "#93c5fd" : s.category === "Elevator" ? "#67e8f9" : s.category === "Door" ? "#f4c25f" : s.navigationType === "TransferSpace" ? "#f8e7b7" : "#eef4fb";
    ctx.strokeStyle = wall ? "#000000" : "#94a3b8";
    ctx.lineWidth = wall ? 1.1 * devicePixelRatio : 0.8 * devicePixelRatio;
    ctx.fill(); ctx.stroke();
    if (s.category === "Stair" || s.category === "Ramp") drawSpaceLabel(s, project);
  }
}
function drawEdges(level, project) {
  if (!payload) return;
  ctx.save();
  for (const e of payload.edges) if (e.sourceLevel === level || e.targetLevel === level) {
    const a=project(e.points[0]), b=project(e.points[1]), virtual = isVirtualEdge(e);
    ctx.beginPath();
    ctx.moveTo(a[0],a[1]);
    ctx.lineTo(b[0],b[1]);
    ctx.globalAlpha = virtual ? 0.75 : 0.35;
    ctx.strokeStyle = virtual ? "#dc2626" : ["Stair","Ramp","Elevator"].includes(e.connectorType) ? "#d97706" : "#64748b";
    ctx.lineWidth = virtual ? 1.3 * devicePixelRatio : 0.8 * devicePixelRatio;
    ctx.setLineDash(virtual ? [6 * devicePixelRatio, 4 * devicePixelRatio] : []);
    ctx.stroke();
  }
  ctx.restore();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
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
$("run").onclick = () => runSimulation().catch(err => $("metrics").textContent = err.message);
$("play").onclick = () => { if (timer) { clearInterval(timer); timer=null; $("play").textContent="Play"; } else { timer=setInterval(()=>{ currentFrame = currentFrame >= Number($("frame").max) ? 0 : currentFrame+1; draw(); }, 50); $("play").textContent="Pause"; } };
$("reset").onclick = () => { currentFrame=0; draw(); };
$("frame").oninput = e => { currentFrame = Number(e.target.value); draw(); };
$("level").onchange = draw;
canvas.onclick = event => {
  if (!model || $("placementMode").textContent !== "On") return;
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
  const candidates = model.spaces.filter(s => s.level === level && s.isNavigable);
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
loadModel();
</script>
</body>
</html>
"""

"""Browser workbench for inspecting SpatialEngine IndoorModel exports."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from indoor_data_model.graph_views import derive_graph_views
from src.spatial_engine.project_workspace import (
    discover_indoor_models,
    load_json,
    related_scenarios_for_model,
    repo_relative,
    resolve_repo_path,
)


DEFAULT_PORT = 8770
DEFAULT_HOST = "127.0.0.1"


def build_model_payload(model_path: Path | str) -> dict[str, Any]:
    path = resolve_repo_path(model_path, REPO_ROOT)
    model = load_json(path)
    return {
        "path": repo_relative(path, REPO_ROOT),
        "model": model,
        "graphViews": derive_graph_views(model),
        "scenarios": related_scenarios_for_model(path, REPO_ROOT),
    }


def run_workbench(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, model: str | None = None) -> None:
    default_model = repo_relative(resolve_repo_path(model, REPO_ROOT), REPO_ROOT) if model else ""

    class Handler(SpatialWorkbenchHandler):
        default_model_path = default_model

    server = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"SpatialEngine workbench: http://{host}:{port}/?model={urllib.parse.quote(default_model)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSpatialEngine workbench stopped.")
    finally:
        server.server_close()


class SpatialWorkbenchHandler(BaseHTTPRequestHandler):
    default_model_path = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        try:
            if parsed.path == "/":
                self._send_html(HTML)
                return
            if parsed.path == "/api/models":
                self._send_json({"models": discover_indoor_models(REPO_ROOT), "defaultModel": self.default_model_path})
                return
            if parsed.path == "/api/model":
                query = urllib.parse.parse_qs(parsed.query)
                model_path = query.get("path", [self.default_model_path])[0]
                if not model_path:
                    models = discover_indoor_models(REPO_ROOT)
                    model_path = models[0]["path"] if models else ""
                if not model_path:
                    raise FileNotFoundError("No IndoorModel files were found.")
                self._send_json(build_model_payload(model_path))
                return
            if parsed.path == "/health":
                self._send_json({"ok": True})
                return
            self.send_error(404, "Not found")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, status=400)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start a browser-based SpatialEngine IndoorModel workbench.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model", help="IndoorModel JSON to load initially.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_workbench(args.host, args.port, args.model)
    return 0


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SpatialEngine Workbench</title>
<style>
:root {
  color-scheme: light;
  --bg: #eef2f5;
  --panel: #ffffff;
  --line: #c8d0d7;
  --text: #17202a;
  --muted: #5b6773;
  --accent: #0f766e;
  --accent-2: #b45309;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: var(--text); background: var(--bg); }
body { display: grid; grid-template-columns: 360px 1fr; overflow: hidden; }
aside { min-width: 0; overflow-y: auto; border-right: 1px solid var(--line); background: var(--panel); padding: 14px; }
main { position: relative; min-width: 0; }
h1 { margin: 0 0 12px; font-size: 18px; line-height: 1.2; }
h2 { margin: 18px 0 8px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
label { display: block; margin: 8px 0 4px; font-size: 12px; color: var(--muted); }
select, input[type="text"] { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px; font-size: 13px; background: #fff; color: var(--text); }
button { border: 1px solid #aab5bf; border-radius: 6px; padding: 8px 9px; background: #f8fafc; color: var(--text); cursor: pointer; font-size: 13px; }
button:hover { background: #edf6f4; border-color: var(--accent); }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.toolbar { display: flex; gap: 7px; flex-wrap: wrap; margin-top: 8px; }
.check { display: flex; align-items: center; gap: 8px; margin: 7px 0; font-size: 13px; color: var(--text); }
.check input { width: 16px; height: 16px; accent-color: var(--accent); }
.hint { color: var(--muted); font-size: 12px; line-height: 1.35; margin: 8px 0 0; }
.status { border-top: 1px solid var(--line); margin-top: 12px; padding-top: 10px; font-size: 12px; color: var(--muted); line-height: 1.45; }
.feature { background: #f7f9fb; border: 1px solid var(--line); border-radius: 8px; padding: 9px; font-size: 12px; line-height: 1.4; word-break: break-word; }
.feature strong { display: block; color: var(--text); margin-bottom: 4px; }
.scenario-list { padding-left: 18px; margin: 6px 0 0; font-size: 12px; line-height: 1.4; }
canvas { width: 100%; height: 100%; display: block; background: #f8fafc; }
.badge { position: absolute; left: 14px; bottom: 14px; background: rgba(255,255,255,.92); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font-size: 12px; color: var(--muted); pointer-events: none; }
.legend { display: grid; grid-template-columns: 14px 1fr; gap: 5px 8px; align-items: center; font-size: 12px; color: var(--muted); margin-top: 8px; }
.swatch { width: 14px; height: 10px; border: 1px solid #59636f; }
@media (max-width: 850px) {
  body { grid-template-columns: 1fr; grid-template-rows: 44vh 56vh; }
  aside { order: 2; border-right: 0; border-top: 1px solid var(--line); }
  main { order: 1; }
}
</style>
</head>
<body>
<aside>
  <h1>SpatialEngine Workbench</h1>
  <label for="modelSelect">IndoorModel</label>
  <select id="modelSelect"></select>
  <label for="modelPath">Path</label>
  <input id="modelPath" type="text" spellcheck="false" placeholder="examples/indoor_data_model/...">
  <div class="toolbar">
    <button id="loadPath" title="Load the path written above.">Load</button>
    <button id="refreshModels" title="Refresh model list.">Refresh</button>
  </div>

  <h2>View</h2>
  <div class="row">
    <div>
      <label for="levelSelect">Level</label>
      <select id="levelSelect"></select>
    </div>
    <div>
      <label for="presetSelect">Preset</label>
      <select id="presetSelect">
        <option value="spaces">Spaces</option>
        <option value="authoring">Source</option>
        <option value="graph">Base graph</option>
        <option value="connectivity">Connectivity</option>
        <option value="vertical">Vertical</option>
      </select>
    </div>
  </div>
  <label for="graphSelect">Graph view</label>
  <select id="graphSelect"></select>
  <div class="toolbar">
    <button id="resetView" title="Fit the model to the canvas.">Reset view</button>
    <button id="zoomIn" title="Zoom in.">+</button>
    <button id="zoomOut" title="Zoom out.">-</button>
  </div>

  <h2>Layers</h2>
  <div id="layerChecks"></div>
  <label class="check"><input id="labelsToggle" type="checkbox"> Labels</label>
  <label class="check"><input id="gridToggle" type="checkbox" checked> Grid</label>

  <h2>Selection</h2>
  <div id="selection" class="feature">Click a cell, boundary, node or edge.</div>

  <h2>Scenarios</h2>
  <div id="scenarios" class="hint">No scenario loaded yet.</div>

  <div class="status" id="status"></div>
  <div class="legend">
    <span class="swatch" style="background:#8ecae6"></span><span>GeneralSpace</span>
    <span class="swatch" style="background:#56c2a3"></span><span>TransferSpace</span>
    <span class="swatch" style="background:#111827"></span><span>Blocked/Object/NonNavigable</span>
    <span class="swatch" style="background:#22d3ee"></span><span>VirtualBoundary</span>
    <span class="swatch" style="background:#f97316"></span><span>Graph edge</span>
  </div>
</aside>
<main>
  <canvas id="canvas"></canvas>
  <div class="badge">Wheel: zoom · middle/right drag: pan · click: inspect</div>
</main>
<script>
const $ = id => document.getElementById(id);
const canvas = $("canvas");
const ctx = canvas.getContext("2d");
const layerDefs = [
  ["source", "Source geometry"],
  ["general", "General spaces"],
  ["transfer", "Transfer spaces"],
  ["blocked", "Blocked/object spaces"],
  ["boundaries", "Boundaries"],
  ["nodes", "Nodes"],
  ["edges", "Base edges"],
  ["graph", "Derived graph"],
];
const presets = {
  authoring: {source: true, general: false, transfer: false, blocked: false, boundaries: false, nodes: false, edges: false, graph: false, graphView: ""},
  spaces: {source: false, general: true, transfer: true, blocked: true, boundaries: true, nodes: false, edges: false, graph: false, graphView: ""},
  graph: {source: false, general: true, transfer: true, blocked: false, boundaries: true, nodes: true, edges: true, graph: false, graphView: ""},
  connectivity: {source: false, general: true, transfer: true, blocked: false, boundaries: true, nodes: false, edges: false, graph: true, graphView: "space_connectivity"},
  vertical: {source: false, general: true, transfer: true, blocked: false, boundaries: false, nodes: false, edges: false, graph: true, graphView: "vertical_connectivity", level: "__STACK__"},
};
const state = {
  models: [],
  payload: null,
  model: null,
  records: null,
  layers: {...presets.spaces},
  level: "",
  graphView: "",
  labels: false,
  grid: true,
  zoom: 1,
  pan: {x: 0, y: 0},
  transform: null,
  drawn: [],
  drag: null,
};

function arr(value) { return Array.isArray(value) ? value : []; }
function tail(value) { return String(value ?? "").split(":").pop(); }
function coordXY(value) {
  if (!Array.isArray(value) || value.length < 2) return null;
  const x = Number(value[0]), y = Number(value[1]);
  return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
}
function geometryPoints(geometry) {
  const out = [];
  if (!geometry || typeof geometry !== "object") return out;
  const t = geometry.type, c = geometry.coordinates;
  const add = p => { const xy = coordXY(p); if (xy) out.push(xy); };
  if (t === "Point") add(c);
  else if (t === "MultiPoint" || t === "LineString") arr(c).forEach(add);
  else if (t === "MultiLineString" || t === "Polygon") arr(c).flat(1).forEach(add);
  else if (t === "MultiPolygon") arr(c).flat(2).forEach(add);
  else if (t === "GeometryCollection") arr(geometry.geometries).forEach(g => geometryPoints(g).forEach(p => out.push(p)));
  return out;
}
function lineStrings(geometry) {
  if (!geometry || typeof geometry !== "object") return [];
  const t = geometry.type, c = geometry.coordinates;
  if (t === "LineString") {
    const line = arr(c).map(coordXY).filter(Boolean);
    return line.length >= 2 ? [line] : [];
  }
  if (t === "MultiLineString") return arr(c).map(line => arr(line).map(coordXY).filter(Boolean)).filter(line => line.length >= 2);
  if (t === "Polygon") return arr(c).map(line => arr(line).map(coordXY).filter(Boolean)).filter(line => line.length >= 2);
  if (t === "GeometryCollection") return arr(geometry.geometries).flatMap(lineStrings);
  return [];
}
function polygons(geometry) {
  if (!geometry || typeof geometry !== "object") return [];
  const t = geometry.type, c = geometry.coordinates;
  const normalize = poly => arr(poly).map(ring => arr(ring).map(coordXY).filter(Boolean)).filter(ring => ring.length >= 3);
  if (t === "Polygon") {
    const rings = normalize(c);
    return rings.length ? [rings] : [];
  }
  if (t === "MultiPolygon") return arr(c).map(normalize).filter(rings => rings.length);
  if (t === "GeometryCollection") return arr(geometry.geometries).flatMap(polygons);
  return [];
}
function cellGeom(cell) { return cell?.cellSpaceGeom?.geometry2D; }
function boundaryGeom(boundary) { return boundary?.cellBoundaryGeom?.geometry2D; }
function centroidFromPoints(points) {
  if (!points.length) return null;
  const sum = points.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1]], [0, 0]);
  return [sum[0] / points.length, sum[1] / points.length];
}
function featurePoint(geometry) { return centroidFromPoints(geometryPoints(geometry)); }
function collectRecords(model) {
  const records = {cells: [], boundaries: [], nodes: [], edges: []};
  for (const layer of arr(model.layers)) {
    const primal = layer.primalSpace || {};
    const dual = layer.dualSpace || {};
    arr(primal.cellSpaceMember).forEach(feature => records.cells.push({layer, feature}));
    arr(primal.cellBoundaryMember).forEach(feature => records.boundaries.push({layer, feature}));
    arr(dual.nodeMember).forEach(feature => records.nodes.push({layer, feature}));
    arr(dual.edgeMember).forEach(feature => records.edges.push({layer, feature}));
  }
  return records;
}
function levelsFor(model) {
  const ids = arr(model.levels).map(l => l.id).filter(Boolean);
  if (ids.length) return ids;
  return [...new Set(arr(model.layers).map(l => l.level).filter(Boolean))];
}
function stackOffsets(model, records) {
  const levels = levelsFor(model);
  let maxHeight = 1;
  const boundsByLevel = {};
  for (const level of levels) {
    const b = boundsForRecords(records, level, {});
    if (b) {
      boundsByLevel[level] = b;
      maxHeight = Math.max(maxHeight, b.maxY - b.minY);
    }
  }
  const step = Math.max(maxHeight * 1.35, maxHeight + 4, 4);
  const offsets = {};
  levels.forEach((level, index) => offsets[level] = index * step);
  return offsets;
}
function featureLevel(record) { return record.layer?.level || ""; }
function visibleRecord(record) { return state.level === "__STACK__" || !state.level || featureLevel(record) === state.level; }
function yOffsetFor(record) {
  if (state.level !== "__STACK__") return 0;
  return stackOffsets(state.model, state.records)[featureLevel(record)] || 0;
}
function withOffset(point, offset) { return [point[0], point[1] + offset]; }
function boundsAdd(bounds, point) {
  if (!point) return bounds;
  bounds.minX = Math.min(bounds.minX, point[0]);
  bounds.minY = Math.min(bounds.minY, point[1]);
  bounds.maxX = Math.max(bounds.maxX, point[0]);
  bounds.maxY = Math.max(bounds.maxY, point[1]);
  return bounds;
}
function boundsForRecords(records, level, offsets) {
  const bounds = {minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity};
  const addGeom = (geometry, offset = 0) => geometryPoints(geometry).forEach(p => boundsAdd(bounds, withOffset(p, offset)));
  const ok = record => level === "__STACK__" || !level || featureLevel(record) === level;
  records.cells.filter(ok).forEach(r => addGeom(cellGeom(r.feature), offsets[featureLevel(r)] || 0));
  records.boundaries.filter(ok).forEach(r => addGeom(boundaryGeom(r.feature), offsets[featureLevel(r)] || 0));
  records.nodes.filter(ok).forEach(r => addGeom(r.feature.geometry, offsets[featureLevel(r)] || 0));
  records.edges.filter(ok).forEach(r => addGeom(r.feature.geometry, offsets[featureLevel(r)] || 0));
  arr(state.model?.sourceFeatures).filter(sf => level === "__STACK__" || !level || (sf.level || level) === level)
    .forEach(sf => addGeom(sf.geometry, offsets[sf.level] || 0));
  return Number.isFinite(bounds.minX) ? bounds : null;
}
function fitTransform() {
  if (!state.model || !state.records) return null;
  const offsets = state.level === "__STACK__" ? stackOffsets(state.model, state.records) : {};
  const b = boundsForRecords(state.records, state.level, offsets) || {minX: 0, minY: 0, maxX: 10, maxY: 10};
  const pad = 36;
  const width = Math.max(b.maxX - b.minX, 1);
  const height = Math.max(b.maxY - b.minY, 1);
  const scale = Math.min((canvas.width - pad * 2) / width, (canvas.height - pad * 2) / height);
  state.transform = {bounds: b, scale, pad};
}
function toScreen(point) {
  const t = state.transform;
  const x = t.pad + (point[0] - t.bounds.minX) * t.scale;
  const y = t.pad + (point[1] - t.bounds.minY) * t.scale;
  return [x * state.zoom + state.pan.x, y * state.zoom + state.pan.y];
}
function screenToWorld(point) {
  const t = state.transform;
  return [
    ((point[0] - state.pan.x) / state.zoom - t.pad) / t.scale + t.bounds.minX,
    ((point[1] - state.pan.y) / state.zoom - t.pad) / t.scale + t.bounds.minY,
  ];
}
function resize() {
  canvas.width = Math.max(1, Math.floor(canvas.clientWidth * devicePixelRatio));
  canvas.height = Math.max(1, Math.floor(canvas.clientHeight * devicePixelRatio));
  fitTransform();
  draw();
}
function drawGrid() {
  if (!state.grid || !state.transform) return;
  const b = state.transform.bounds;
  ctx.save();
  ctx.strokeStyle = "#dbe2e8";
  ctx.lineWidth = 1;
  const step = chooseGridStep((b.maxX - b.minX) / Math.max(canvas.clientWidth / 80, 1));
  for (let x = Math.floor(b.minX / step) * step; x <= b.maxX; x += step) {
    const a = toScreen([x, b.minY]), c = toScreen([x, b.maxY]);
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]); ctx.stroke();
  }
  for (let y = Math.floor(b.minY / step) * step; y <= b.maxY; y += step) {
    const a = toScreen([b.minX, y]), c = toScreen([b.maxX, y]);
    ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(c[0], c[1]); ctx.stroke();
  }
  ctx.restore();
}
function chooseGridStep(raw) {
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 0.1))));
  const n = raw / pow;
  return (n < 2 ? 1 : n < 5 ? 2 : 5) * pow;
}
function pathForPolygon(poly, offset) {
  const path = new Path2D();
  for (const ring of poly) {
    ring.forEach((p, index) => {
      const s = toScreen(withOffset(p, offset));
      if (index === 0) path.moveTo(s[0], s[1]); else path.lineTo(s[0], s[1]);
    });
    path.closePath();
  }
  return path;
}
function drawLine(line, offset, stroke, width = 2, dash = []) {
  if (line.length < 2) return;
  ctx.save();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = width * devicePixelRatio;
  ctx.setLineDash(dash.map(v => v * devicePixelRatio));
  ctx.beginPath();
  line.forEach((p, index) => {
    const s = toScreen(withOffset(p, offset));
    if (index === 0) ctx.moveTo(s[0], s[1]); else ctx.lineTo(s[0], s[1]);
  });
  ctx.stroke();
  ctx.restore();
}
function cellStyle(cell) {
  const nav = String(cell.navigationType || "");
  if (nav === "GeneralSpace") return {fill: "rgba(142,202,230,.55)", stroke: "#1d6f9b"};
  if (nav === "TransferSpace") return {fill: "rgba(86,194,163,.68)", stroke: "#08785e"};
  if (nav === "NonNavigableSpace" || nav === "ObjectSpace") return {fill: "rgba(17,24,39,.70)", stroke: "#020617"};
  return {fill: "rgba(199,185,226,.45)", stroke: "#6d5195"};
}
function drawCells() {
  for (const record of state.records.cells) {
    if (!visibleRecord(record)) continue;
    const cell = record.feature;
    const nav = String(cell.navigationType || "");
    const show = (nav === "GeneralSpace" && state.layers.general)
      || (nav === "TransferSpace" && state.layers.transfer)
      || ((nav === "NonNavigableSpace" || nav === "ObjectSpace") && state.layers.blocked);
    if (!show) continue;
    const style = cellStyle(cell);
    const offset = yOffsetFor(record);
    for (const poly of polygons(cellGeom(cell))) {
      const path = pathForPolygon(poly, offset);
      ctx.fillStyle = style.fill;
      ctx.strokeStyle = selectedId() === cell.id ? "#e11d48" : style.stroke;
      ctx.lineWidth = (selectedId() === cell.id ? 3 : 1.4) * devicePixelRatio;
      ctx.fill(path, "evenodd");
      ctx.stroke(path);
      state.drawn.push({kind: "CellSpace", id: cell.id, record, poly: poly[0].map(p => withOffset(p, offset))});
    }
    if (state.labels) labelFeature(cell.id, featurePoint(cellGeom(cell)), offset, "#123");
  }
}
function drawBoundaries() {
  if (!state.layers.boundaries) return;
  for (const record of state.records.boundaries) {
    if (!visibleRecord(record)) continue;
    const b = record.feature;
    const offset = yOffsetFor(record);
    const isVirtual = Boolean(b.isVirtual || b.attributes?.virtualBoundaryRef);
    const color = isVirtual ? "#0891b2" : (b.navigationBoundaryType === "NavigableBoundary" ? "#0f766e" : "#0f172a");
    const dash = isVirtual ? [5, 4] : [];
    lineStrings(boundaryGeom(b)).forEach(line => drawLine(line, offset, selectedId() === b.id ? "#e11d48" : color, isVirtual ? 2.5 : 2, dash));
    state.drawn.push({kind: "CellBoundary", id: b.id, record, line: lineStrings(boundaryGeom(b))[0]?.map(p => withOffset(p, offset)) || []});
    if (state.labels) labelFeature(b.id, featurePoint(boundaryGeom(b)), offset, color);
  }
}
function drawDual() {
  if (state.layers.edges) {
    for (const record of state.records.edges) {
      if (!visibleRecord(record)) continue;
      const offset = yOffsetFor(record);
      lineStrings(record.feature.geometry).forEach(line => drawLine(line, offset, selectedId() === record.feature.id ? "#e11d48" : "#f97316", 1.8));
      state.drawn.push({kind: "Edge", id: record.feature.id, record, line: lineStrings(record.feature.geometry)[0]?.map(p => withOffset(p, offset)) || []});
      if (state.labels) labelFeature(record.feature.id, featurePoint(record.feature.geometry), offset, "#9a3412");
    }
  }
  if (state.layers.nodes) {
    for (const record of state.records.nodes) {
      if (!visibleRecord(record)) continue;
      const offset = yOffsetFor(record);
      for (const p of geometryPoints(record.feature.geometry)) {
        const s = toScreen(withOffset(p, offset));
        ctx.beginPath();
        ctx.arc(s[0], s[1], (selectedId() === record.feature.id ? 6 : 4.5) * devicePixelRatio, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.strokeStyle = selectedId() === record.feature.id ? "#e11d48" : "#c2410c";
        ctx.lineWidth = 1.5 * devicePixelRatio;
        ctx.fill(); ctx.stroke();
        state.drawn.push({kind: "Node", id: record.feature.id, record, point: withOffset(p, offset)});
      }
      if (state.labels) labelFeature(record.feature.id, featurePoint(record.feature.geometry), offset, "#9a3412");
    }
  }
}
function drawSource() {
  if (!state.layers.source) return;
  for (const sf of arr(state.model.sourceFeatures)) {
    if (state.level !== "__STACK__" && state.level && sf.level && sf.level !== state.level) continue;
    const offset = state.level === "__STACK__" ? (stackOffsets(state.model, state.records)[sf.level] || 0) : 0;
    const typ = String(sf.attributes?.originalType || sf.sourceType || "");
    const color = typ.includes("ventana") ? "#2563eb" : typ.includes("puerta") || typ.includes("salida") ? "#b45309" : "#64748b";
    lineStrings(sf.geometry).forEach(line => drawLine(line, offset, color, 1.6, typ.includes("ventana") ? [4, 3] : []));
    for (const poly of polygons(sf.geometry)) {
      const path = pathForPolygon(poly, offset);
      ctx.strokeStyle = color; ctx.lineWidth = 1.3 * devicePixelRatio; ctx.stroke(path);
    }
  }
}
function nodePositions() {
  const positions = {};
  const put = (id, point) => {
    if (!id || !point) return;
    positions[String(id)] = point;
    positions[tail(id)] = point;
  };
  for (const record of state.records.cells) {
    if (!visibleRecord(record)) continue;
    const point = featurePoint(cellGeom(record.feature));
    put(record.feature.id, point ? withOffset(point, yOffsetFor(record)) : null);
    put(record.feature.duality, point ? withOffset(point, yOffsetFor(record)) : null);
  }
  for (const record of state.records.nodes) {
    if (!visibleRecord(record)) continue;
    const point = featurePoint(record.feature.geometry);
    put(record.feature.id, point ? withOffset(point, yOffsetFor(record)) : null);
    put(record.feature.duality, point ? withOffset(point, yOffsetFor(record)) : null);
  }
  for (const node of arr(state.payload.graphViews?.[state.graphView]?.nodes)) {
    const point = featurePoint(node.geometry);
    put(node.id, point);
  }
  return positions;
}
function drawGraphView() {
  if (!state.layers.graph || !state.graphView) return;
  const view = state.payload.graphViews?.[state.graphView];
  if (!view) return;
  const positions = nodePositions();
  for (const edge of arr(view.edges)) {
    const connects = arr(edge.connects);
    if (connects.length < 2) continue;
    const p1 = positions[String(connects[0])] || positions[tail(connects[0])];
    const p2 = positions[String(connects[1])] || positions[tail(connects[1])];
    if (!p1 || !p2) continue;
    drawLine([p1, p2], 0, "#7c3aed", 2.4, state.graphView.includes("vertical") ? [7, 4] : []);
    if (state.labels) labelFeature(edge.id || state.graphView, [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2], 0, "#5b21b6");
  }
}
function drawStackLabels() {
  if (state.level !== "__STACK__") return;
  const offsets = stackOffsets(state.model, state.records);
  ctx.save();
  ctx.fillStyle = "#1f2937";
  ctx.font = `${12 * devicePixelRatio}px Segoe UI`;
  for (const [level, offset] of Object.entries(offsets)) {
    const b = boundsForRecords(state.records, level, {});
    if (!b) continue;
    const s = toScreen([b.minX, b.minY + offset]);
    ctx.fillText(level, s[0], Math.max(18 * devicePixelRatio, s[1] - 8 * devicePixelRatio));
  }
  ctx.restore();
}
function labelFeature(text, point, offset, color) {
  if (!point) return;
  const s = toScreen(withOffset(point, offset));
  ctx.save();
  ctx.font = `${10 * devicePixelRatio}px Segoe UI`;
  ctx.fillStyle = "rgba(255,255,255,.82)";
  const label = tail(text);
  const w = ctx.measureText(label).width + 8 * devicePixelRatio;
  ctx.fillRect(s[0] - w / 2, s[1] - 8 * devicePixelRatio, w, 14 * devicePixelRatio);
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, s[0], s[1]);
  ctx.restore();
}
function selectedId() { return state.selected?.id || ""; }
function draw() {
  if (!state.model || !state.records) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  state.drawn = [];
  if (!state.transform) fitTransform();
  drawGrid();
  drawSource();
  drawCells();
  drawBoundaries();
  drawDual();
  drawGraphView();
  drawStackLabels();
  updateStatus();
}
function updateStatus() {
  const r = state.records;
  $("status").innerHTML = [
    `<strong>${state.payload?.path || ""}</strong>`,
    `${r.cells.length} CellSpaces · ${r.boundaries.length} Boundaries`,
    `${r.nodes.length} Nodes · ${r.edges.length} Edges`,
    `Zoom ${(state.zoom * 100).toFixed(0)}%`,
  ].join("<br>");
}
function pointInPoly(point, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
    const intersect = ((yi > point[1]) !== (yj > point[1])) && (point[0] < (xj - xi) * (point[1] - yi) / ((yj - yi) || 1e-9) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}
function distToSegment(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy || 1e-9;
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  const x = a[0] + t * dx, y = a[1] + t * dy;
  return Math.hypot(p[0] - x, p[1] - y);
}
function pick(screenPoint) {
  const world = screenToWorld(screenPoint);
  let best = null, bestD = Infinity;
  for (const item of state.drawn.slice().reverse()) {
    if (item.poly && pointInPoly(world, item.poly)) return item;
    if (item.point) {
      const d = Math.hypot(world[0] - item.point[0], world[1] - item.point[1]);
      if (d < bestD) { best = item; bestD = d; }
    }
    if (item.line?.length >= 2) {
      for (let i = 0; i < item.line.length - 1; i++) {
        const d = distToSegment(world, item.line[i], item.line[i + 1]);
        if (d < bestD) { best = item; bestD = d; }
      }
    }
  }
  const tolerance = 12 / (state.transform.scale * state.zoom);
  return bestD <= tolerance ? best : null;
}
function showSelection(item) {
  state.selected = item;
  if (!item) {
    $("selection").textContent = "Click a cell, boundary, node or edge.";
    draw();
    return;
  }
  const f = item.record?.feature || {};
  const level = featureLevel(item.record || {});
  const lines = [
    `<strong>${item.kind}: ${f.id || item.id}</strong>`,
    `level: ${level || "-"}`,
    `type: ${f.navigationType || f.navigationBoundaryType || f.category || "-"}`,
    `duality: ${f.duality || "-"}`,
  ];
  if (f.isVirtual) lines.push("virtual boundary: yes");
  $("selection").innerHTML = lines.join("<br>");
  draw();
}
async function loadModels() {
  const res = await fetch("/api/models");
  const data = await res.json();
  state.models = data.models || [];
  $("modelSelect").innerHTML = state.models.map(m => `<option value="${escapeAttr(m.path)}">${escapeHtml(m.label)} · ${m.source}</option>`).join("");
  const query = new URLSearchParams(location.search);
  const wanted = query.get("model") || data.defaultModel || state.models[0]?.path || "";
  if (wanted) {
    $("modelSelect").value = wanted;
    $("modelPath").value = wanted;
    await loadModel(wanted);
  }
}
async function loadModel(path) {
  const res = await fetch(`/api/model?path=${encodeURIComponent(path)}`);
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  state.payload = data;
  state.model = data.model;
  state.records = collectRecords(data.model);
  state.selected = null;
  state.zoom = 1; state.pan = {x: 0, y: 0};
  populateLevels();
  populateGraphs();
  renderScenarios();
  fitTransform();
  draw();
}
function populateLevels() {
  const levels = levelsFor(state.model);
  $("levelSelect").innerHTML = [`<option value="__STACK__">All levels stacked</option>`, ...levels.map(l => `<option value="${escapeAttr(l)}">${escapeHtml(l)}</option>`)].join("");
  state.level = levels[0] || "__STACK__";
  $("levelSelect").value = state.level;
}
function populateGraphs() {
  const names = Object.keys(state.payload.graphViews || {}).sort();
  $("graphSelect").innerHTML = [`<option value="">None</option>`, ...names.map(n => `<option value="${escapeAttr(n)}">${escapeHtml(n)}</option>`)].join("");
  if (names.includes(state.graphView)) $("graphSelect").value = state.graphView;
}
function renderScenarios() {
  const scenarios = state.payload.scenarios || [];
  if (!scenarios.length) {
    $("scenarios").textContent = "No scenario found for this IndoorModel.";
    return;
  }
  $("scenarios").innerHTML = `<ul class="scenario-list">${scenarios.map(s => `<li><code>${escapeHtml(s.path)}</code></li>`).join("")}</ul>`;
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function escapeAttr(value) { return escapeHtml(value); }
function applyPreset(name) {
  const preset = presets[name] || presets.spaces;
  for (const [key] of layerDefs) state.layers[key] = Boolean(preset[key]);
  if (preset.graphView !== undefined) {
    state.graphView = preset.graphView;
    $("graphSelect").value = state.graphView;
  }
  if (preset.level && $("levelSelect").querySelector(`option[value="${preset.level}"]`)) {
    state.level = preset.level;
    $("levelSelect").value = state.level;
  }
  updateLayerChecks();
  state.zoom = 1; state.pan = {x: 0, y: 0};
  fitTransform();
  draw();
}
function updateLayerChecks() {
  $("layerChecks").innerHTML = layerDefs.map(([key, label]) =>
    `<label class="check"><input data-layer="${key}" type="checkbox" ${state.layers[key] ? "checked" : ""}> ${label}</label>`
  ).join("");
  $("layerChecks").querySelectorAll("input[data-layer]").forEach(input => {
    input.onchange = () => { state.layers[input.dataset.layer] = input.checked; draw(); };
  });
}
$("modelSelect").onchange = event => { $("modelPath").value = event.target.value; loadModel(event.target.value).catch(alert); };
$("loadPath").onclick = () => loadModel($("modelPath").value).catch(alert);
$("refreshModels").onclick = () => loadModels().catch(alert);
$("levelSelect").onchange = event => { state.level = event.target.value; state.zoom = 1; state.pan = {x: 0, y: 0}; fitTransform(); draw(); };
$("presetSelect").onchange = event => applyPreset(event.target.value);
$("graphSelect").onchange = event => { state.graphView = event.target.value; state.layers.graph = Boolean(state.graphView); updateLayerChecks(); draw(); };
$("labelsToggle").onchange = event => { state.labels = event.target.checked; draw(); };
$("gridToggle").onchange = event => { state.grid = event.target.checked; draw(); };
$("resetView").onclick = () => { state.zoom = 1; state.pan = {x: 0, y: 0}; fitTransform(); draw(); };
$("zoomIn").onclick = () => { state.zoom *= 1.18; draw(); };
$("zoomOut").onclick = () => { state.zoom /= 1.18; draw(); };
canvas.oncontextmenu = event => event.preventDefault();
canvas.addEventListener("wheel", event => {
  event.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const mouse = [(event.clientX - rect.left) * devicePixelRatio, (event.clientY - rect.top) * devicePixelRatio];
  const old = state.zoom;
  const next = Math.max(0.2, Math.min(12, old * (event.deltaY < 0 ? 1.12 : 0.89)));
  state.pan.x = mouse[0] - (mouse[0] - state.pan.x) * next / old;
  state.pan.y = mouse[1] - (mouse[1] - state.pan.y) * next / old;
  state.zoom = next;
  draw();
}, {passive: false});
canvas.addEventListener("mousedown", event => {
  const rect = canvas.getBoundingClientRect();
  const point = [(event.clientX - rect.left) * devicePixelRatio, (event.clientY - rect.top) * devicePixelRatio];
  if (event.button === 1 || event.button === 2) {
    state.drag = {point, pan: {...state.pan}};
  } else {
    const picked = pick(point);
    showSelection(picked);
  }
});
window.addEventListener("mousemove", event => {
  if (!state.drag) return;
  const rect = canvas.getBoundingClientRect();
  const point = [(event.clientX - rect.left) * devicePixelRatio, (event.clientY - rect.top) * devicePixelRatio];
  state.pan.x = state.drag.pan.x + point[0] - state.drag.point[0];
  state.pan.y = state.drag.pan.y + point[1] - state.drag.point[1];
  draw();
});
window.addEventListener("mouseup", () => state.drag = null);
window.addEventListener("resize", resize);
updateLayerChecks();
loadModels().then(resize).catch(error => {
  $("status").textContent = error.message || String(error);
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())


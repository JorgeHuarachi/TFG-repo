"""Matplotlib visualization and GIF export for EvacEngine."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from .domain import SimulationResult
from .simulation import EvacuationModel
from .topology import EvacTopology


SPACE_COLORS = {
    "GeneralSpace": "#eef4fb",
    "TransferSpace": "#f8e7b7",
    "VirtualTransferNode": "#f6f2d8",
    "NonNavigableSpace": "#050505",
}

CATEGORY_COLORS = {
    "Door": "#f4c25f",
    "Exit": "#75c878",
    "Stair": "#d8b4fe",
    "Ramp": "#93c5fd",
    "Elevator": "#67e8f9",
    "Column": "#050505",
    "WallSegment": "#050505",
    "WallJunction": "#000000",
    "Window": "#a7d8ff",
}

STATUS_COLORS = {
    "active": "#006dff",
    "evacuated": "#1a9f52",
    "no_route": "#c0392b",
    "trapped": "#8e44ad",
}

PROFILE_COLORS = {
    "Walking": "#006dff",
    "Rolling": "#c026d3",
    "Elderly": "#16a34a",
    "MP_WALKING": "#006dff",
    "MP_WALKING_VERTICAL": "#006dff",
    "MP_WALKING_ROLLING": "#0891b2",
    "MP_ROLLING_ACCESSIBLE": "#c026d3",
}


class EvacuationRenderer:
    def __init__(self, topology: EvacTopology) -> None:
        self.topology = topology

    def draw_model_frame(self, ax: Axes, model: EvacuationModel, level: str | None = None) -> None:
        self.draw_base(ax, level)
        rows = [
            {
                "agentId": agent.agent_id,
                "levelRef": agent.level,
                "x": agent.position[0],
                "y": agent.position[1],
                "status": agent.status,
            }
            for agent in model.agents
        ]
        self.draw_agents(ax, rows, level)
        ax.set_title(f"{model.scenario.scenario_id} | step {model.step_count} | t={model.time_s:.1f}s")

    def draw_result_frame(self, ax: Axes, result: SimulationResult, step: float, level: str | None = None) -> None:
        self.draw_base(ax, level)
        rows = _rows_for_step(result.trajectories, step)
        self.draw_traces(ax, result.trajectories, step, level)
        self.draw_agents(ax, rows, level)
        time_s = rows[0].get("timeS") if rows else step
        ax.set_title(f"{result.scenario_id} | step {step} | t={time_s}s")

    def draw_base(self, ax: Axes, level: str | None = None) -> None:
        ax.clear()
        ax.set_aspect("equal", adjustable="box")
        ax.set_facecolor("#f8fafc")
        for cell in self.topology.indoor.cells_by_id.values():
            if level and cell.level != level:
                continue
            geom = cell.geometry
            if geom is None or geom.is_empty:
                continue
            color = CATEGORY_COLORS.get(cell.category or "", SPACE_COLORS.get(cell.navigation_type or "", "#e5e7eb"))
            edge = "#9aa6b2" if cell.navigation_type != "NonNavigableSpace" else "#000000"
            alpha = 0.9 if cell.navigation_type != "NonNavigableSpace" else 0.95
            for polygon in _polygons(geom):
                coords = list(polygon.exterior.coords)
                patch = MplPolygon(coords, closed=True, facecolor=color, edgecolor=edge, linewidth=0.6, alpha=alpha, zorder=1)
                ax.add_patch(patch)
        self._draw_graph(ax, level)
        self._fit_bounds(ax, level)
        ax.grid(True, color="#d4dce5", linewidth=0.4, alpha=0.5)

    def draw_agents(self, ax: Axes, rows: list[dict[str, Any]], level: str | None = None) -> None:
        for row in rows:
            if level and row.get("levelRef") != level:
                continue
            x, y = float(row["x"]), float(row["y"])
            body_radius = float(row.get("bodyRadiusM") or 0.25)
            personal_radius = float(row.get("personalRadiusM") or 0.5)
            color = _agent_color(row)
            if row.get("status") != "active":
                body_radius *= 0.65
                personal_radius = 0.0
            if personal_radius > 0:
                ax.add_patch(Circle((x, y), personal_radius, facecolor=color, edgecolor="none", alpha=0.14, zorder=18))
            ax.add_patch(Circle((x, y), body_radius, facecolor=color, edgecolor="#111827", linewidth=0.6, alpha=0.72 if row.get("status") != "active" else 0.92, zorder=22))
            if row.get("intentX") is not None and row.get("status") == "active":
                ax.plot([x, float(row["intentX"])], [y, float(row["intentY"])], color=color, linestyle=":", alpha=0.55, linewidth=0.8, zorder=19)

    def draw_traces(self, ax: Axes, trajectories: list[dict[str, Any]], step: float, level: str | None = None) -> None:
        by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in trajectories:
            if float(row.get("step", -1)) > step:
                continue
            if level and row.get("levelRef") != level:
                continue
            by_agent[str(row.get("agentId"))].append(row)
        for rows in by_agent.values():
            if len(rows) < 2:
                continue
            rows = sorted(rows, key=lambda item: int(item["step"]))
            ax.plot([float(row["x"]) for row in rows], [float(row["y"]) for row in rows], color="#2563eb", alpha=0.35, linewidth=1, zorder=15)

    def _draw_graph(self, ax: Axes, level: str | None) -> None:
        drawn = set()
        for source, target, data in self.topology.graph.edges(data=True):
            key = tuple(sorted((source, target)))
            if key in drawn:
                continue
            drawn.add(key)
            source_level = self.topology.node_level(source)
            target_level = self.topology.node_level(target)
            if level and source_level != level and target_level != level:
                continue
            p1 = self.topology.node_position(source)
            p2 = self.topology.node_position(target)
            if not p1 or not p2:
                continue
            is_virtual = str(data.get("viaBoundaryRef") or "").upper().find("VIRTUAL") >= 0 or source.startswith("VTN_") or target.startswith("VTN_")
            if is_virtual:
                continue
            elif data.get("connectorType") in {"Stair", "Ramp", "Elevator"}:
                color, linestyle, alpha = "#d97706", "-", 0.35
            else:
                color, linestyle, alpha = "#64748b", "-", 0.35
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linestyle=linestyle, alpha=alpha, linewidth=0.8, zorder=5)

    def _fit_bounds(self, ax: Axes, level: str | None) -> None:
        bounds = []
        for cell in self.topology.indoor.cells_by_id.values():
            if level and cell.level != level:
                continue
            if cell.geometry is not None and not cell.geometry.is_empty:
                bounds.append(cell.geometry.bounds)
        if not bounds:
            ax.autoscale()
            return
        minx = min(item[0] for item in bounds)
        miny = min(item[1] for item in bounds)
        maxx = max(item[2] for item in bounds)
        maxy = max(item[3] for item in bounds)
        pad_x = max((maxx - minx) * 0.05, 0.5)
        pad_y = max((maxy - miny) * 0.05, 0.5)
        ax.set_xlim(minx - pad_x, maxx + pad_x)
        ax.set_ylim(miny - pad_y, maxy + pad_y)


def save_result_gif(
    topology: EvacTopology,
    result: SimulationResult,
    output_path: str | Path,
    level: str | None = None,
    fps: int = 8,
    max_frames: int | None = None,
    subframes_per_step: int = 4,
) -> Path:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    renderer = EvacuationRenderer(topology)
    integer_steps = sorted({int(row["step"]) for row in result.trajectories})
    if not integer_steps:
        frame_steps = [0.0]
    else:
        frame_steps = []
        for left, right in zip(integer_steps, integer_steps[1:]):
            for sub in range(subframes_per_step):
                frame_steps.append(left + sub / subframes_per_step)
        frame_steps.append(float(integer_steps[-1]))
    if max_frames and len(frame_steps) > max_frames:
        stride = max(len(frame_steps) // max_frames, 1)
        frame_steps = frame_steps[::stride]

    fig = Figure(figsize=(8, 6), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)

    def update(frame_step: float):
        renderer.draw_result_frame(ax, result, frame_step, level)
        return ax.patches + ax.lines + ax.collections

    animation = FuncAnimation(fig, update, frames=frame_steps, blit=False, repeat=False)
    animation.save(output, writer=PillowWriter(fps=fps))
    return output


def save_result_html(topology: EvacTopology, result: SimulationResult, output_path: str | Path, include_geometry_qa: bool = True) -> Path:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_visualization_payload(topology, result, include_geometry_qa=include_geometry_qa)
    html = HTML_TEMPLATE.replace("__EVACENGINE_PAYLOAD__", json.dumps(payload, ensure_ascii=True))
    output.write_text(html, encoding="utf-8")
    return output


def build_visualization_payload(topology: EvacTopology, result: SimulationResult, include_geometry_qa: bool = True) -> dict[str, Any]:
    qa = trajectory_quality_metrics(result.trajectories)
    if include_geometry_qa:
        qa.update(trajectory_geometry_metrics(topology, result.trajectories))
    else:
        qa.update({"geometryQaSkipped": True})
    return {
        "scenarioId": result.scenario_id,
        "metrics": result.metrics,
        "levels": sorted(topology.indoor.levels_by_id),
        "spaces": _space_payload(topology),
        "edges": _edge_payload(topology),
        "trajectories": result.trajectories,
        "qa": qa,
    }


def _rows_for_step(trajectories: list[dict[str, Any]], step: float) -> list[dict[str, Any]]:
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trajectories:
        by_agent[str(row.get("agentId"))].append(row)
    rows = []
    for agent_rows in by_agent.values():
        ordered = sorted(agent_rows, key=lambda item: float(item["step"]))
        previous = None
        following = None
        for row in ordered:
            row_step = float(row.get("step", -1))
            if row_step <= step:
                previous = row
            if row_step >= step:
                following = row
                break
        if previous is None and following is not None:
            rows.append(dict(following))
            continue
        if previous is not None and (following is None or previous is following):
            rows.append(dict(previous))
            continue
        if previous is None or following is None:
            continue
        left_step = float(previous["step"])
        right_step = float(following["step"])
        ratio = 0.0 if right_step == left_step else (step - left_step) / (right_step - left_step)
        interpolated = dict(previous)
        for key in ("x", "y"):
            interpolated[key] = float(previous[key]) + (float(following[key]) - float(previous[key])) * ratio
        if previous.get("levelRef") != following.get("levelRef") and ratio >= 1.0:
            interpolated["levelRef"] = following.get("levelRef")
        if ratio > 0.85:
            interpolated["status"] = following.get("status", previous.get("status"))
        rows.append(interpolated)
    return rows


def _polygons(geom: Any) -> list[Any]:
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    return []


def _agent_color(row: dict[str, Any]) -> str:
    if row.get("status") != "active":
        return STATUS_COLORS.get(str(row.get("status")), "#64748b")
    profile = str(row.get("profileId") or "")
    return PROFILE_COLORS.get(profile, "#006dff")


def trajectory_quality_metrics(trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trajectories:
        by_agent[str(row.get("agentId"))].append(row)
    max_step_distance = 0.0
    large_jumps = 0
    for rows in by_agent.values():
        ordered = sorted(rows, key=lambda item: int(item["step"]))
        for left, right in zip(ordered, ordered[1:]):
            if left.get("levelRef") != right.get("levelRef"):
                continue
            dx = float(right["x"]) - float(left["x"])
            dy = float(right["y"]) - float(left["y"])
            distance = (dx * dx + dy * dy) ** 0.5
            max_step_distance = max(max_step_distance, distance)
            if distance > 1.5:
                large_jumps += 1
    overlaps = 0
    by_step_level: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in trajectories:
        if row.get("status") != "active":
            continue
        by_step_level[(int(row["step"]), str(row.get("levelRef")))].append(row)
    for rows in by_step_level.values():
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                dx = float(right["x"]) - float(left["x"])
                dy = float(right["y"]) - float(left["y"])
                distance = (dx * dx + dy * dy) ** 0.5
                min_distance = float(left.get("bodyRadiusM") or 0.25) + float(right.get("bodyRadiusM") or 0.25)
                if distance < min_distance * 0.85:
                    overlaps += 1
    return {
        "agentCount": len(by_agent),
        "sampleCount": len(trajectories),
        "maxStepDistanceM": round(max_step_distance, 6),
        "largeJumps": large_jumps,
        "bodyOverlapSamples": overlaps,
    }


def trajectory_geometry_metrics(topology: EvacTopology, trajectories: list[dict[str, Any]]) -> dict[str, Any]:
    navigable_by_level: dict[str, Any] = {}
    for cell in topology.indoor.cells_by_id.values():
        if not cell.is_navigable or cell.geometry is None or cell.geometry.is_empty or not cell.level:
            continue
        navigable_by_level.setdefault(cell.level, []).append(cell.geometry)
    navigable_by_level = {level: unary_union(geoms) for level, geoms in navigable_by_level.items()}

    outside_samples = 0
    for row in trajectories:
        if row.get("status") != "active":
            continue
        level = str(row.get("levelRef"))
        area = navigable_by_level.get(level)
        if area is None:
            continue
        if not area.buffer(1e-6).covers(Point(float(row["x"]), float(row["y"]))):
            outside_samples += 1

    segment_crossings = 0
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trajectories:
        by_agent[str(row.get("agentId"))].append(row)
    for rows in by_agent.values():
        ordered = sorted(rows, key=lambda item: int(item["step"]))
        for left, right in zip(ordered, ordered[1:]):
            if left.get("levelRef") != right.get("levelRef"):
                continue
            area = navigable_by_level.get(str(left.get("levelRef")))
            if area is None:
                continue
            segment = LineString([(float(left["x"]), float(left["y"])), (float(right["x"]), float(right["y"]))])
            if not area.buffer(1e-6).covers(segment):
                segment_crossings += 1
    return {
        "outsideNavigableSamples": outside_samples,
        "segmentOutsideNavigable": segment_crossings,
    }


def _space_payload(topology: EvacTopology) -> list[dict[str, Any]]:
    spaces = []
    for cell in topology.indoor.cells_by_id.values():
        if cell.geometry is None or cell.geometry.is_empty:
            continue
        rings = []
        for polygon in _polygons(cell.geometry):
            rings.append([[float(x), float(y)] for x, y in polygon.exterior.coords])
        if not rings:
            continue
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
    return spaces


def _edge_payload(topology: EvacTopology) -> list[dict[str, Any]]:
    edges = []
    seen = set()
    for source, target, data in topology.graph.edges(data=True):
        key = tuple(sorted((source, target)))
        if key in seen:
            continue
        seen.add(key)
        p1 = topology.node_position(source)
        p2 = topology.node_position(target)
        if not p1 or not p2:
            continue
        edges.append(
            {
                "source": source,
                "target": target,
                "sourceLevel": topology.node_level(source),
                "targetLevel": topology.node_level(target),
                "connectorType": data.get("connectorType"),
                "viaBoundaryRef": data.get("viaBoundaryRef"),
                "sourceRef": data.get("sourceRef"),
                "relationshipType": (data.get("raw") or {}).get("relationshipType"),
                "points": [[float(p1[0]), float(p1[1])], [float(p2[0]), float(p2[1])]],
            }
        )
    return edges


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EvacEngine Viewer</title>
  <style>
    :root { color-scheme: light; font-family: Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #f8fafc; color: #111827; }
    .app { display: grid; grid-template-columns: 320px 1fr; height: 100vh; }
    aside { border-right: 1px solid #cbd5e1; background: #ffffff; padding: 14px; overflow: auto; }
    main { position: relative; min-width: 0; }
    canvas { display: block; width: 100%; height: 100%; background: #f8fafc; }
    label { display: block; font-size: 12px; color: #475569; margin-top: 10px; }
    select, input, button { width: 100%; box-sizing: border-box; margin-top: 4px; padding: 7px; border: 1px solid #94a3b8; border-radius: 4px; background: #fff; }
    button { cursor: pointer; background: #0f172a; color: white; border-color: #0f172a; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    pre { white-space: pre-wrap; font-size: 12px; background: #f1f5f9; padding: 10px; border-radius: 4px; }
    h1 { font-size: 18px; margin: 0 0 8px; }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>EvacEngine Viewer</h1>
      <div id="scenario"></div>
      <label>Level</label>
      <select id="level"></select>
      <label>Step <span id="stepLabel"></span></label>
      <input id="step" type="range" min="0" max="0" value="0">
      <div class="row">
        <button id="play">Play</button>
        <button id="reset">Reset</button>
      </div>
      <label>Speed</label>
      <input id="speed" type="range" min="40" max="500" value="120">
      <label>Metrics</label>
      <pre id="metrics"></pre>
    </aside>
    <main><canvas id="canvas"></canvas></main>
  </div>
  <script>
    const payload = __EVACENGINE_PAYLOAD__;
    const colors = { GeneralSpace: "#eef4fb", TransferSpace: "#f8e7b7", NonNavigableSpace: "#050505" };
    const category = { Door: "#f4c25f", Exit: "#75c878", Stair: "#d8b4fe", Ramp: "#93c5fd", Elevator: "#67e8f9", Column: "#050505", WallSegment: "#050505", WallJunction: "#000000" };
    const statusColors = { active: "#006dff", evacuated: "#1a9f52", no_route: "#c0392b", trapped: "#8e44ad" };
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const levelSelect = document.getElementById("level");
    const stepSlider = document.getElementById("step");
    const stepLabel = document.getElementById("stepLabel");
    const playButton = document.getElementById("play");
    const speed = document.getElementById("speed");
    let timer = null;
    let currentStep = 0;
    const steps = [...new Set(payload.trajectories.map(row => row.step))].sort((a, b) => a - b);
    const maxStep = steps.length ? steps[steps.length - 1] : 0;
    document.getElementById("scenario").textContent = payload.scenarioId;
    document.getElementById("metrics").textContent = JSON.stringify({ metrics: payload.metrics, qa: payload.qa }, null, 2);
    for (const level of payload.levels) {
      const option = document.createElement("option");
      option.value = level;
      option.textContent = level;
      levelSelect.appendChild(option);
    }
    const initialCounts = {};
    for (const row of payload.trajectories) {
      if (row.step === 0 && row.levelRef) initialCounts[row.levelRef] = (initialCounts[row.levelRef] || 0) + 1;
    }
    const initialLevel = Object.entries(initialCounts).sort((a, b) => b[1] - a[1])[0];
    if (initialLevel) levelSelect.value = initialLevel[0];
    stepSlider.max = String(maxStep);
    function resize() {
      canvas.width = canvas.clientWidth * devicePixelRatio;
      canvas.height = canvas.clientHeight * devicePixelRatio;
      draw();
    }
    function bounds(level) {
      const pts = [];
      for (const space of payload.spaces) if (space.level === level) {
        for (const ring of space.rings) for (const p of ring) pts.push(p);
      }
      if (!pts.length) return [0, 0, 1, 1];
      return [Math.min(...pts.map(p => p[0])), Math.min(...pts.map(p => p[1])), Math.max(...pts.map(p => p[0])), Math.max(...pts.map(p => p[1]))];
    }
    function projector(level) {
      const [minX, minY, maxX, maxY] = bounds(level);
      const pad = 24 * devicePixelRatio;
      const sx = (canvas.width - pad * 2) / Math.max(maxX - minX, 1);
      const sy = (canvas.height - pad * 2) / Math.max(maxY - minY, 1);
      const scale = Math.min(sx, sy);
      return ([x, y]) => [pad + (x - minX) * scale, canvas.height - pad - (y - minY) * scale];
    }
    function rowsForStep(step) {
      const latest = new Map();
      for (const row of payload.trajectories) if (row.step <= step) latest.set(row.agentId, row);
      return [...latest.values()];
    }
    function draw() {
      const level = levelSelect.value || payload.levels[0];
      const project = projector(level);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const space of payload.spaces) if (space.level === level) {
        ctx.beginPath();
        for (const ring of space.rings) {
          ring.forEach((p, i) => {
            const [x, y] = project(p);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
          });
        }
        ctx.closePath();
        ctx.fillStyle = category[space.category] || colors[space.navigationType] || "#e5e7eb";
        const blocked = space.navigationType === "NonNavigableSpace" || space.category === "Column";
        ctx.strokeStyle = blocked ? "#000000" : "#94a3b8";
        ctx.lineWidth = 0.8 * devicePixelRatio;
        ctx.fill();
        ctx.stroke();
        if (space.category === "Stair" || space.category === "Ramp") drawSpaceLabel(space, project);
      }
      ctx.globalAlpha = 1;
      for (const edge of payload.edges) if (edge.sourceLevel === level || edge.targetLevel === level) {
        if (isVirtualEdge(edge)) continue;
        const a = project(edge.points[0]), b = project(edge.points[1]);
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]);
        ctx.globalAlpha = 0.35;
        ctx.strokeStyle = ["Stair", "Ramp", "Elevator"].includes(edge.connectorType) ? "#d97706" : "#64748b";
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      drawTraces(level, project);
      for (const row of rowsForStep(currentStep)) if (row.levelRef === level) {
        const [x, y] = project([row.x, row.y]);
        ctx.beginPath();
        ctx.arc(x, y, 6 * devicePixelRatio, 0, Math.PI * 2);
        ctx.fillStyle = statusColors[row.status] || "#006dff";
        ctx.strokeStyle = "#111827";
        ctx.lineWidth = 1 * devicePixelRatio;
        ctx.fill();
        ctx.stroke();
      }
      stepSlider.value = String(currentStep);
      stepLabel.textContent = `${currentStep}/${maxStep}`;
    }
    function isVirtualEdge(edge) {
      return String(edge.viaBoundaryRef || "").includes("VIRTUAL") || String(edge.source || "").startsWith("VTN_") || String(edge.target || "").startsWith("VTN_");
    }
    function drawSpaceLabel(space, project) {
      const ring = space.rings[0] || [];
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
    function drawTraces(level, project) {
      const byAgent = new Map();
      for (const row of payload.trajectories) {
        if (row.step > currentStep || row.levelRef !== level) continue;
        if (!byAgent.has(row.agentId)) byAgent.set(row.agentId, []);
        byAgent.get(row.agentId).push(row);
      }
      ctx.lineWidth = 1.1 * devicePixelRatio;
      for (const rows of byAgent.values()) {
        if (rows.length < 2) continue;
        rows.sort((a, b) => a.step - b.step);
        ctx.beginPath();
        rows.forEach((row, index) => {
          const p = project([row.x, row.y]);
          if (index === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
        });
        ctx.strokeStyle = "#2563eb88";
        ctx.stroke();
      }
    }
    function tick() {
      currentStep = currentStep >= maxStep ? 0 : currentStep + 1;
      draw();
    }
    playButton.onclick = () => {
      if (timer) { clearInterval(timer); timer = null; playButton.textContent = "Play"; return; }
      timer = setInterval(tick, Number(speed.value));
      playButton.textContent = "Pause";
    };
    document.getElementById("reset").onclick = () => { currentStep = 0; draw(); };
    stepSlider.oninput = event => { currentStep = Number(event.target.value); draw(); };
    levelSelect.onchange = draw;
    addEventListener("resize", resize);
    resize();
  </script>
</body>
</html>
"""

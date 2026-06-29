"""CER debug visualization utilities.

These functions consume CER debug traces. They do not compute or alter the
centrality metric; they only render the reasoning steps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .rerouting_centrality import CERDebugStep, CERResult
from .topology import EvacTopology
from .visualization import EvacuationRenderer, _edge_levels


def save_cer_debug_json(result: CERResult | dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict() if isinstance(result, CERResult) else result
    output.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return output


def save_cer_summary_png(
    topology: EvacTopology,
    result: CERResult | dict[str, Any],
    output_path: str | Path,
    *,
    level: str | None = None,
) -> Path:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict() if isinstance(result, CERResult) else result
    fig = Figure(figsize=(10, 7), dpi=140)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    renderer = EvacuationRenderer(topology)
    renderer.draw_base(ax, level)
    _draw_cer_node_scores(ax, topology, payload, level)
    ax.set_title("CER summary | Centralidad de Evacuacion por Reencaminamiento")
    fig.tight_layout()
    fig.savefig(output)
    return output


def save_cer_debug_gif(
    topology: EvacTopology,
    result: CERResult | dict[str, Any],
    output_path: str | Path,
    *,
    level: str | None = None,
    fps: int = 2,
    max_frames: int | None = 120,
) -> Path:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict() if isinstance(result, CERResult) else result
    steps = payload.get("debugSteps") or []
    if max_frames and len(steps) > max_frames:
        stride = max(len(steps) // max_frames, 1)
        steps = steps[::stride]
    if not steps:
        steps = [{"reason": "no_debug_steps", "basePath": [], "candidatePath": []}]
    fig = Figure(figsize=(10, 7), dpi=120)
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    renderer = EvacuationRenderer(topology)

    def update(step: dict[str, Any]):
        renderer.draw_base(ax, level)
        _draw_cer_step(ax, topology, step, level)
        return ax.patches + ax.lines + ax.collections

    animation = FuncAnimation(fig, update, frames=steps, blit=False, repeat=False)
    animation.save(output, writer=PillowWriter(fps=max(1, int(fps))))
    return output


def save_cer_debug_html(
    topology: EvacTopology,
    result: CERResult | dict[str, Any],
    output_path: str | Path,
    *,
    level: str | None = None,
) -> Path:
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict() if isinstance(result, CERResult) else result
    html = CER_HTML_TEMPLATE.replace("__CER_PAYLOAD__", json.dumps(payload, ensure_ascii=True))
    html = html.replace("__CER_GRAPH__", json.dumps(_cer_graph_payload(topology), ensure_ascii=True))
    html = html.replace("__CER_LEVEL__", json.dumps(level, ensure_ascii=True))
    output.write_text(html, encoding="utf-8")
    return output


def _cer_graph_payload(topology: EvacTopology) -> dict[str, Any]:
    nodes: dict[str, Any] = {}
    for node_id, data in topology.graph.nodes(data=True):
        point = topology.node_position(str(node_id))
        if not point:
            continue
        nodes[str(node_id)] = {
            "id": str(node_id),
            "level": topology.node_level(str(node_id)),
            "category": data.get("category"),
            "isExit": bool(data.get("isExit")),
            "x": float(point[0]),
            "y": float(point[1]),
        }
    edges = []
    seen: set[tuple[str, str, str]] = set()
    for source, target, data in topology.graph.edges(data=True):
        if source not in nodes or target not in nodes:
            continue
        resource = str(data.get("resourceRef") or data.get("arcId") or "")
        key = tuple(sorted((str(source), str(target))) + [resource])
        if key in seen:
            continue
        seen.add(key)
        levels = _edge_levels(topology, str(source), str(target), data)
        edges.append(
            {
                "source": str(source),
                "target": str(target),
                "resource": resource,
                "levels": levels,
                "connectorType": data.get("connectorType"),
            }
        )
    levels = sorted({str(node.get("level")) for node in nodes.values() if node.get("level")})
    return {"nodes": list(nodes.values()), "edges": edges, "levels": levels}


def _draw_cer_step(ax: Axes, topology: EvacTopology, step: dict[str, Any], level: str | None) -> None:
    origin = step.get("origin")
    target = step.get("target")
    _draw_path(ax, topology, step.get("basePath") or [], level, color="#2563eb", linewidth=3.0, alpha=0.75, label="P0")
    source_path = step.get("failureSourcePath") or []
    if source_path and source_path != (step.get("basePath") or []):
        _draw_path(ax, topology, source_path, level, color="#f59e0b", linewidth=2.7, alpha=0.8, label="ruta fuente")
    accepted = bool(step.get("accepted"))
    reason = str(step.get("reason") or "")
    candidate_color = "#16a34a" if accepted else "#dc2626"
    _draw_path(ax, topology, step.get("candidatePath") or [], level, color=candidate_color, linewidth=3.0, alpha=0.82, label="candidate")
    _draw_failed_units(ax, topology, step.get("failedResources") or [], level, color="#ef4444", linewidth=3.0, alpha=0.45)
    _draw_failed_units(ax, topology, step.get("newlyFailedResources") or [], level, color="#991b1b", linewidth=4.4, alpha=0.95)
    _draw_node_marker(ax, topology, origin, level, "#2563eb", "origen")
    _draw_node_marker(ax, topology, target, level, "#16a34a", "salida")
    title = "CER rerouting"
    if origin and target:
        title += f" | {origin} -> {target}"
    ax.set_title(title)
    status = "ACEPTADA" if accepted else "RECHAZADA"
    info = (
        f"perfil: {step.get('failureProfile')} | fallo depth: {step.get('failureDepth')}\n"
        f"C0 inicial: {_fmt(step.get('baseCost'))} | Cmax tolerado: {_fmt(step.get('costLimit'))} | Calt candidata: {_fmt(step.get('candidateCost'))}\n"
        f"estado: {status} ({reason})\n"
        f"distintas acumuladas en este perfil: {step.get('distinctRouteCount')} | casos del perfil: {step.get('evaluatedFailureCases')}"
    )
    ax.text(
        0.02,
        0.02,
        info,
        transform=ax.transAxes,
        verticalalignment="bottom",
        bbox={"facecolor": "#ffffff", "edgecolor": "#cbd5e1", "alpha": 0.88, "boxstyle": "round,pad=0.45"},
        fontsize=8,
        zorder=80,
    )


def _draw_path(
    ax: Axes,
    topology: EvacTopology,
    path: list[str],
    level: str | None,
    *,
    color: str,
    linewidth: float,
    alpha: float,
    label: str,
) -> None:
    for source, target in zip(path, path[1:]):
        source_level = topology.node_level(source)
        target_level = topology.node_level(target)
        if level and source_level != level and target_level != level:
            continue
        p1 = topology.node_position(source)
        p2 = topology.node_position(target)
        if not p1 or not p2:
            continue
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linewidth=linewidth, alpha=alpha, zorder=45, label=label)


def _draw_failed_units(
    ax: Axes,
    topology: EvacTopology,
    failed_resources: list[str],
    level: str | None,
    *,
    color: str = "#dc2626",
    linewidth: float = 4.2,
    alpha: float = 0.9,
) -> None:
    failed = set(str(item) for item in failed_resources)
    if not failed:
        return
    drawn = set()
    for source, target, data in topology.graph.edges(data=True):
        resource = str(data.get("resourceRef") or data.get("arcId") or "")
        if resource not in failed:
            continue
        key = tuple(sorted((source, target, resource)))
        if key in drawn:
            continue
        drawn.add(key)
        source_level = topology.node_level(source)
        target_level = topology.node_level(target)
        if level and source_level != level and target_level != level:
            continue
        p1 = topology.node_position(source)
        p2 = topology.node_position(target)
        if not p1 or not p2:
            continue
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linestyle="--", linewidth=linewidth, alpha=alpha, zorder=55)
        mid = ((p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5)
        ax.scatter([mid[0]], [mid[1]], marker="x", s=90, color=color, alpha=min(alpha + 0.1, 1.0), zorder=60)


def _draw_node_marker(ax: Axes, topology: EvacTopology, node_id: str | None, level: str | None, color: str, label: str) -> None:
    if not node_id:
        return
    if level and topology.node_level(node_id) != level:
        return
    point = topology.node_position(node_id)
    if not point:
        return
    ax.scatter([point[0]], [point[1]], s=130, facecolor=color, edgecolor="#ffffff", linewidth=1.8, zorder=70)
    ax.text(point[0], point[1], label, fontsize=7, color="#111827", zorder=75)


def _draw_cer_node_scores(ax: Axes, topology: EvacTopology, payload: dict[str, Any], level: str | None) -> None:
    values = {
        node_id: float((node_payload.get("summary") or {}).get("nodeScore") or 0.0)
        for node_id, node_payload in (payload.get("nodes") or {}).items()
    }
    max_value = max(values.values(), default=0.0)
    for node_id, value in values.items():
        if level and topology.node_level(node_id) != level:
            continue
        point = topology.node_position(node_id)
        if not point:
            continue
        ratio = value / max_value if max_value > 0 else 0.0
        size = 35 + 180 * ratio
        ax.scatter([point[0]], [point[1]], s=size, facecolor="#f97316", edgecolor="#7c2d12", alpha=0.25 + 0.55 * ratio, zorder=65)
        if value > 0:
            ax.text(point[0], point[1], f"{value:.0f}", fontsize=7, color="#7c2d12", ha="center", va="center", zorder=75)


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return str(value)


CER_HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<meta charset="utf-8">
<title>CER debug</title>
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f8fafc; color: #111827; }
main { display: grid; grid-template-columns: 340px 1fr; min-height: 100vh; }
aside { background: #ffffff; border-right: 1px solid #d7dee8; padding: 16px; overflow: auto; }
section { padding: 20px; overflow: auto; }
button { display: block; width: 100%; margin: 4px 0; padding: 8px; border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; text-align: left; cursor: pointer; }
button.active { border-color: #2563eb; background: #eff6ff; }
select { width: 100%; padding: 7px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; }
svg { width: 100%; height: 62vh; background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; }
pre { background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow: auto; }
.ok { color: #15803d; font-weight: 700; }
.bad { color: #b91c1c; font-weight: 700; }
.muted { color: #64748b; font-size: 12px; }
.metric { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 12px 0; font-size: 13px; }
.metric span { background: #f1f5f9; padding: 6px; border-radius: 6px; }
.edge-base { stroke: #94a3b8; stroke-width: 1.2; opacity: .38; }
.edge-p0 { stroke: #2563eb; stroke-width: 4; opacity: .82; stroke-linecap: round; }
.edge-source { stroke: #f59e0b; stroke-width: 3.6; opacity: .8; stroke-linecap: round; }
.edge-candidate-ok { stroke: #16a34a; stroke-width: 4; opacity: .86; stroke-linecap: round; }
.edge-candidate-bad { stroke: #dc2626; stroke-width: 4; opacity: .76; stroke-linecap: round; stroke-dasharray: 7 4; }
.edge-failed-old { stroke: #ef4444; stroke-width: 4; opacity: .42; stroke-dasharray: 8 4; stroke-linecap: round; }
.edge-failed-new { stroke: #991b1b; stroke-width: 6; opacity: .95; stroke-dasharray: 8 4; stroke-linecap: round; }
.node { fill: #fff; stroke: #334155; stroke-width: 1.2; opacity: .86; }
.node-exit { fill: #dcfce7; stroke: #15803d; }
.node-origin { fill: #f97316; stroke: #111827; stroke-width: 2; }
.node-target { fill: #22c55e; stroke: #111827; stroke-width: 2; }
.legend { display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap:8px; margin:10px 0; font-size:12px; }
.legend span { padding:7px 9px; border-radius:6px; background:#eef2f7; border-left: 5px solid #94a3b8; }
.legend .p0 { border-left-color:#2563eb; }
.legend .source { border-left-color:#f59e0b; }
.legend .ok { border-left-color:#16a34a; color:#111827; font-weight:400; }
.legend .bad { border-left-color:#dc2626; color:#111827; font-weight:400; }
.legend .fail { border-left-color:#991b1b; }
.help { background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:10px; font-size:12px; line-height:1.45; }
</style>
<main>
<aside>
<h1>CER debug</h1>
<p id="meta"></p>
<label>Nivel</label>
<select id="level"></select>
<div id="steps"></div>
</aside>
<section>
<h2 id="title">Paso</h2>
<p id="status"></p>
<div class="metric" id="metrics"></div>
<div class="help">
  C0 = coste de la ruta minima inicial P0. Cmax = C0 x (1 + tolerancia). Calt = coste de la ruta recalculada despues del fallo actual. Los casos evaluados se cuentan dentro de cada perfil: al cambiar de (1) a (1,1) empiezan otra vez.
</div>
<div class="legend">
  <span>gris: grafo base completo usado por CER</span>
  <span class="p0">azul: P0, ruta minima inicial</span>
  <span class="source">ambar: ruta fuente a la que se le aplica el fallo actual</span>
  <span class="ok">verde: ruta alternativa aceptada dentro de Cmax</span>
  <span class="bad">rojo fino/discontinuo: candidata rechazada o fuera de tolerancia</span>
  <span class="fail">rojo grueso: recurso/arista eliminada en este paso</span>
</div>
<svg id="graph" role="img" aria-label="CER graph visualization"></svg>
<pre id="detail"></pre>
</section>
</main>
<script>
const payload = __CER_PAYLOAD__;
const graph = __CER_GRAPH__;
const preferredLevel = __CER_LEVEL__;
const steps = payload.debugSteps || [];
document.getElementById("meta").textContent = `${payload.metadata?.graphView || "graph"} | ${steps.length} pasos`;
const list = document.getElementById("steps");
const detail = document.getElementById("detail");
const title = document.getElementById("title");
const status = document.getElementById("status");
const metrics = document.getElementById("metrics");
const svg = document.getElementById("graph");
const levelSelect = document.getElementById("level");
let activeIndex = 0;
const ns = "http://www.w3.org/2000/svg";
const levels = graph.levels || [];
levels.forEach(level => {
  const option = document.createElement("option");
  option.value = level;
  option.textContent = level;
  levelSelect.appendChild(option);
});
if (preferredLevel && levels.includes(preferredLevel)) levelSelect.value = preferredLevel;
else if (levels.length) levelSelect.value = levels[0];
levelSelect.onchange = () => show(activeIndex);
function show(index) {
  activeIndex = index;
  const step = steps[index] || {};
  document.querySelectorAll("button").forEach((b, i) => b.classList.toggle("active", i === index));
  title.textContent = `${step.origin || "?"} -> ${step.target || "?"} | ${step.failureProfile || ""}`;
  status.innerHTML = step.accepted ? '<span class="ok">ACEPTADA</span>' : '<span class="bad">RECHAZADA</span>';
  metrics.innerHTML = [
    ["C0 ruta inicial", fmt(step.baseCost)],
    ["Cmax tolerado", fmt(step.costLimit)],
    ["Calt candidata", fmt(step.candidateCost)],
    ["rutas distintas", step.distinctRouteCount ?? "-"],
    ["casos del perfil", step.evaluatedFailureCases ?? "-"],
    ["decision", step.reason || "-"],
  ].map(([k, v]) => `<span><b>${k}</b><br>${v}</span>`).join("");
  drawGraph(step);
  detail.textContent = JSON.stringify(step, null, 2);
}
function fmt(value) {
  return value == null ? "-" : Number(value).toFixed(3);
}
function visibleNodes(level) {
  return (graph.nodes || []).filter(node => !level || node.level === level);
}
function visibleEdges(level) {
  return (graph.edges || []).filter(edge => !level || (edge.levels || []).includes(level));
}
function bounds(nodes) {
  if (!nodes.length) return [0, 0, 1, 1];
  return [
    Math.min(...nodes.map(node => node.x)),
    Math.min(...nodes.map(node => node.y)),
    Math.max(...nodes.map(node => node.x)),
    Math.max(...nodes.map(node => node.y)),
  ];
}
function projector(nodes) {
  const [minX, minY, maxX, maxY] = bounds(nodes);
  const width = 1000, height = 650, pad = 40;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const scale = Math.min((width - pad * 2) / Math.max(maxX - minX, 1), (height - pad * 2) / Math.max(maxY - minY, 1));
  return node => [pad + (node.x - minX) * scale, height - pad - (node.y - minY) * scale];
}
function nodeMap() {
  return new Map((graph.nodes || []).map(node => [node.id, node]));
}
function edgeFor(source, target) {
  return (graph.edges || []).find(edge =>
    (edge.source === source && edge.target === target) || (edge.source === target && edge.target === source)
  );
}
function appendLine(a, b, className) {
  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1", a[0]);
  line.setAttribute("y1", a[1]);
  line.setAttribute("x2", b[0]);
  line.setAttribute("y2", b[1]);
  line.setAttribute("class", className);
  svg.appendChild(line);
}
function drawPath(path, className, nodes, project) {
  const byId = nodeMap();
  for (let i = 0; i < (path || []).length - 1; i++) {
    const a = byId.get(path[i]);
    const b = byId.get(path[i + 1]);
    if (!a || !b) continue;
    if (!nodes.includes(a) && !nodes.includes(b)) continue;
    appendLine(project(a), project(b), className);
  }
}
function failedValues(units) {
  return new Set((units || []).map(unit => unit.value));
}
function drawFailedValues(values, nodes, project, className) {
  const byId = nodeMap();
  for (const edge of graph.edges || []) {
    if (!values.has(edge.resource) && !values.has(edge.source + "->" + edge.target)) continue;
    const a = byId.get(edge.source);
    const b = byId.get(edge.target);
    if (!a || !b || (!nodes.includes(a) && !nodes.includes(b))) continue;
    appendLine(project(a), project(b), className);
  }
}
function drawFailed(step, nodes, project) {
  const allFailed = failedValues(step.failedUnits);
  const newFailed = failedValues(step.newlyFailedUnits);
  const previousFailed = new Set([...allFailed].filter(value => !newFailed.has(value)));
  drawFailedValues(previousFailed, nodes, project, "edge-failed-old");
  drawFailedValues(newFailed, nodes, project, "edge-failed-new");
}
function samePath(left, right) {
  left = left || [];
  right = right || [];
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
function drawNode(node, project, className = "node") {
  const [x, y] = project(node);
  const circle = document.createElementNS(ns, "circle");
  circle.setAttribute("cx", x);
  circle.setAttribute("cy", y);
  circle.setAttribute("r", className.includes("origin") || className.includes("target") ? 8 : node.isExit ? 5 : 3.5);
  circle.setAttribute("class", className);
  svg.appendChild(circle);
}
function drawLabel(node, project, text) {
  const [x, y] = project(node);
  const label = document.createElementNS(ns, "text");
  label.setAttribute("x", x + 10);
  label.setAttribute("y", y + 4);
  label.setAttribute("font-size", "13");
  label.setAttribute("fill", "#111827");
  label.textContent = text;
  svg.appendChild(label);
}
function drawGraph(step) {
  svg.textContent = "";
  const level = levelSelect.value || "";
  const nodes = visibleNodes(level);
  const edges = visibleEdges(level);
  const byId = nodeMap();
  const project = projector(nodes);
  for (const edge of edges) {
    const a = byId.get(edge.source);
    const b = byId.get(edge.target);
    if (a && b) appendLine(project(a), project(b), "edge-base");
  }
  drawPath(step.basePath || [], "edge-p0", nodes, project);
  if ((step.failureSourcePath || []).length && !samePath(step.failureSourcePath, step.basePath || [])) {
    drawPath(step.failureSourcePath || [], "edge-source", nodes, project);
  }
  drawPath(step.candidatePath || [], step.accepted ? "edge-candidate-ok" : "edge-candidate-bad", nodes, project);
  drawFailed(step, nodes, project);
  for (const node of nodes) drawNode(node, project, node.isExit ? "node node-exit" : "node");
  const origin = byId.get(step.origin);
  const target = byId.get(step.target);
  if (origin && (!level || origin.level === level)) { drawNode(origin, project, "node-origin"); drawLabel(origin, project, "origen"); }
  if (target && (!level || target.level === level)) { drawNode(target, project, "node-target"); drawLabel(target, project, "salida"); }
}
if (!steps.length) {
  detail.textContent = JSON.stringify(payload, null, 2);
  drawGraph({});
} else {
  steps.forEach((step, index) => {
    const button = document.createElement("button");
    button.textContent = `${index + 1}. ${step.failureProfile} d${step.failureDepth} caso ${step.evaluatedFailureCases} | ${step.reason} | distintas=${step.distinctRouteCount}`;
    button.onclick = () => show(index);
    list.appendChild(button);
  });
  show(0);
}
</script>
</html>
"""

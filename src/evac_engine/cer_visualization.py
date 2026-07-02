"""CER debug visualization utilities.

These functions consume CER debug traces. They do not compute or alter the
centrality metric; they only render the reasoning steps.
"""

from __future__ import annotations

from collections import Counter
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
    payload = _annotated_payload(result)
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
    payload = _annotated_payload(result)
    steps = payload.get("debugSteps") or []
    if max_frames and max_frames > 0 and len(steps) > max_frames:
        stride = max(len(steps) // max_frames, 1)
        steps = steps[::stride]
        payload.setdefault("metadata", {})["gifFrameSampling"] = {"maxFrames": max_frames, "stride": stride}
    if not steps:
        steps = [{"reason": "no_debug_steps", "basePath": [], "candidatePath": []}]
    fig = Figure(figsize=(13, 7), dpi=120)
    FigureCanvasAgg(fig)
    grid = fig.add_gridspec(1, 2, width_ratios=[3.3, 1.25], wspace=0.08)
    ax = fig.add_subplot(grid[0, 0])
    panel_ax = fig.add_subplot(grid[0, 1])
    renderer = EvacuationRenderer(topology)

    def update(step: dict[str, Any]):
        ax.clear()
        panel_ax.clear()
        renderer.draw_base(ax, level)
        _draw_cer_step(ax, topology, step, level, panel_ax=panel_ax, metadata=payload.get("metadata") or {})
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
    payload = _annotated_payload(result)
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


def _annotated_payload(result: CERResult | dict[str, Any]) -> dict[str, Any]:
    payload = result.to_dict() if isinstance(result, CERResult) else result
    payload = json.loads(json.dumps(payload, ensure_ascii=True))
    steps = payload.get("debugSteps") or []
    profile_counts = Counter(str(step.get("failureProfile") or "") for step in steps)
    profile_seen: Counter[str] = Counter()
    total = len(steps)
    for index, step in enumerate(steps, start=1):
        profile = str(step.get("failureProfile") or "")
        profile_seen[profile] += 1
        step["globalStepIndex"] = index
        step["globalStepCount"] = total
        step["profileStepIndex"] = profile_seen[profile]
        step["profileStepCount"] = profile_counts[profile]
    return payload


def _draw_cer_step(
    ax: Axes,
    topology: EvacTopology,
    step: dict[str, Any],
    level: str | None,
    *,
    panel_ax: Axes | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
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
    newly_failed = [str(item) for item in (step.get("newlyFailedResources") or [])]
    previous_failed = [str(item) for item in (step.get("failedResources") or []) if str(item) not in set(newly_failed)]
    _draw_failed_units(ax, topology, previous_failed, level, color="#ef4444", linewidth=3.8, alpha=0.82)
    _draw_failed_units(ax, topology, newly_failed, level, color="#7f1d1d", linewidth=4.8, alpha=0.98)
    _draw_node_marker(ax, topology, origin, level, "#2563eb", "origen")
    _draw_node_marker(ax, topology, target, level, "#16a34a", "salida")
    title = "CER rerouting"
    if origin and target:
        title += f" | {origin} -> {target}"
    ax.set_title(title)
    if panel_ax is not None:
        _draw_cer_panel(panel_ax, step, metadata or {})
    else:
        status = "ACEPTADA" if accepted else "RECHAZADA"
        info = (
            f"perfil: {step.get('failureProfile')} | fallo depth: {step.get('failureDepth')}\n"
            f"C0: {_fmt(step.get('baseCost'))} | Cmax: {_fmt(step.get('costLimit'))} | Calt: {_fmt(step.get('candidateCost'))}\n"
            f"estado: {status} ({reason})"
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


def _draw_cer_panel(ax: Axes, step: dict[str, Any], metadata: dict[str, Any]) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    accepted = bool(step.get("accepted"))
    status = "ACEPTADA" if accepted else "RECHAZADA"
    status_color = "#166534" if accepted else "#991b1b"
    tau = metadata.get("costTolerance")
    reason = str(step.get("reason") or "-")
    header = (
        f"Paso {step.get('globalStepIndex', '-')}/{step.get('globalStepCount', '-')}\n"
        f"Perfil {step.get('failureProfile', '-')} | paso perfil {step.get('profileStepIndex', '-')}/{step.get('profileStepCount', '-')}\n"
        f"Nivel secuencial {step.get('failureDepth', '-')}/{len(step.get('failureProfileRaw') or []) or '-'}"
    )
    ax.text(0.02, 0.98, header, ha="left", va="top", fontsize=9.2, fontweight="bold", color="#111827")
    ax.text(0.02, 0.83, f"{status} | {reason}", ha="left", va="top", fontsize=11, fontweight="bold", color=status_color)
    values = [
        ("tau tolerancia", _fmt(tau)),
        ("C0 ruta inicial", _fmt(step.get("baseCost"))),
        ("Cmax = C0*(1+tau)", _fmt(step.get("costLimit"))),
        ("Calt candidata", _fmt(step.get("candidateCost"))),
        ("casos evaluados", str(step.get("evaluatedFailureCases") or "-")),
    ]
    y = 0.76
    for label, value in values:
        ax.text(0.02, y, label, ha="left", va="top", fontsize=8.2, color="#475569")
        ax.text(0.98, y, value, ha="right", va="top", fontsize=8.2, color="#111827", fontweight="bold")
        y -= 0.055
    routes_value = str(step.get("distinctRouteCount") or 0)
    ax.text(0.02, y - 0.005, "RUTAS DISTINTAS", ha="left", va="top", fontsize=9.4, color="#7c2d12", fontweight="bold")
    ax.text(0.98, y - 0.005, routes_value, ha="right", va="top", fontsize=15, color="#7c2d12", fontweight="bold")
    y -= 0.075
    failed = _format_failure_units(step)
    ax.text(0.02, y - 0.01, "recurso eliminado ahora", ha="left", va="top", fontsize=8.2, color="#475569")
    ax.text(0.02, y - 0.048, failed, ha="left", va="top", fontsize=7.0, color="#111827", fontweight="bold", wrap=True)
    ax.text(0.02, y - 0.092, "cambia porque cada frame prueba un fallo distinto", ha="left", va="top", fontsize=6.7, color="#64748b")
    legend_y = 0.235
    ax.text(0.02, legend_y + 0.05, "Leyenda", ha="left", va="top", fontsize=9, fontweight="bold", color="#111827")
    _panel_legend_line(ax, legend_y, "#94a3b8", "grafo base", linestyle="-")
    _panel_legend_line(ax, legend_y - 0.045, "#2563eb", "P0 inicial", linestyle="-")
    _panel_legend_line(ax, legend_y - 0.09, "#f59e0b", "ruta fuente", linestyle="-")
    _panel_legend_line(ax, legend_y - 0.135, "#16a34a", "candidata aceptada", linestyle="-")
    _panel_legend_line(ax, legend_y - 0.18, "#dc2626", "candidata rechazada", linestyle="-")
    _panel_legend_line(ax, legend_y - 0.225, "#7f1d1d", "recurso fallado", linestyle="--")


def _panel_legend_line(ax: Axes, y: float, color: str, label: str, *, linestyle: str = "-") -> None:
    ax.plot([0.03, 0.17], [y, y], color=color, linewidth=4, linestyle=linestyle)
    ax.text(0.21, y, label, ha="left", va="center", fontsize=7.0, color="#111827")


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


def _format_failure_units(step: dict[str, Any]) -> str:
    units = step.get("newlyFailedUnits") or []
    if not units:
        values = step.get("newlyFailedResources") or step.get("newlyFailedArcs") or []
        return ", ".join(_short_failure_value("recurso", str(value)) for value in values) or "-"
    labels: list[str] = []
    for unit in units:
        if isinstance(unit, dict):
            kind = str(unit.get("kind") or "fallo")
            value = str(unit.get("value") or "")
        else:
            kind = "fallo"
            value = str(unit)
        labels.append(_short_failure_value(kind, value))
    return ", ".join(labels) or "-"


def _short_failure_value(kind: str, value: str) -> str:
    label = "recurso" if kind == "resource" else kind
    if len(value) > 38:
        value = f"{value[:20]}...{value[-14:]}"
    return f"{label}: {value}"


CER_HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<meta charset="utf-8">
<title>CER debug</title>
<style>
body { font-family: Segoe UI, Arial, sans-serif; margin: 0; background: #f8fafc; color: #111827; }
main { display: grid; grid-template-columns: 340px 1fr; min-height: 100vh; }
aside { background: #ffffff; border-right: 1px solid #d7dee8; padding: 16px; overflow: auto; }
section { padding: 20px; overflow: auto; }
body.layout-wide { overflow-y: auto; }
body.layout-wide main { grid-template-columns: 1fr; grid-template-rows: 100vh 112px; height: auto; min-height: calc(100vh + 112px); overflow: visible; }
body.layout-wide aside { grid-row: 2; border-right: 0; border-top: 1px solid #d7dee8; padding: 6px 9px; display: grid; grid-template-columns: 190px 1fr; gap: 8px; min-height: 0; overflow: hidden; }
body.layout-wide aside h1, body.layout-wide aside p, body.layout-wide aside label, body.layout-wide aside select { grid-column: 1; }
body.layout-wide aside h1 { margin: 0; font-size: 15px; line-height: 18px; }
body.layout-wide aside p { margin: 0; font-size: 11px; line-height: 14px; }
body.layout-wide aside label { margin-top: 2px; font-size: 11px; line-height: 13px; }
body.layout-wide aside select { padding: 3px 6px; font-size: 11px; min-height: 24px; }
body.layout-wide #steps { grid-column: 2; grid-row: 1 / span 5; display: flex; gap: 6px; overflow-x: auto; overflow-y: hidden; padding: 1px 0 4px; align-items: flex-start; height: 88px; max-height: 88px; min-height: 0; }
body.layout-wide aside button { flex: 0 0 156px; white-space: normal; font-size: 9.5px; line-height: 1.15; padding: 4px 5px; margin: 0; min-height: 52px; max-height: 72px; overflow: hidden; }
body.layout-wide section { grid-row: 1; position: relative; display: block; overflow: hidden; padding: 12px; height: 100vh; min-height: 0; box-sizing: border-box; }
body.layout-wide #title, body.layout-wide #status, body.layout-wide .controls, body.layout-wide #metrics, body.layout-wide .help, body.layout-wide .legend { width: 304px; box-sizing: border-box; }
body.layout-wide #title { margin: 0 0 9px; font-size: 18px; line-height: 22px; max-height: 48px; overflow: hidden; }
body.layout-wide #status { margin: 0 0 8px; font-size: 12px; line-height: 15px; max-height: 45px; overflow: hidden; }
body.layout-wide .controls { margin: 6px 0 8px; gap: 5px; height: 32px; overflow: hidden; }
body.layout-wide .controls button { min-width: 73px; min-height: 28px; padding: 4px 7px; font-size: 11px; }
body.layout-wide .controls .muted { display: none; }
body.layout-wide #routeTools { width: 304px; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px; margin: 0 0 8px; }
body.layout-wide #routeTools button { min-width: 0; min-height: 26px; padding: 4px 5px; font-size: 10px; }
body.layout-wide #distinctRouteGroup { grid-column: 1 / -1; padding: 3px 5px; font-size: 10px; min-height: 23px; }
body.layout-wide #distinctRouteStatus { grid-column: 1 / -1; font-size: 10px; line-height: 1.15; max-height: 34px; overflow: hidden; }
body.layout-wide #metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; margin: 0 0 8px; font-size: 10.2px; line-height: 1.12; max-height: 230px; overflow: hidden; }
body.layout-wide #metrics span { padding: 5px 6px; min-width: 0; overflow-wrap: anywhere; }
body.layout-wide .help { display: none; }
body.layout-wide .legend { grid-template-columns: 1fr; gap: 4px; margin: 0; font-size: 10px; line-height: 1.15; max-height: 138px; overflow: hidden; }
body.layout-wide .legend span { padding: 4px 6px; border-left-width: 4px; }
body.layout-wide #graph { position: absolute; left: 328px; right: 12px; top: 12px; bottom: 12px; width: auto; height: auto; min-height: 0; }
body.layout-wide #detail { display: none; }
#results { padding: 18px 22px 28px; border-top: 1px solid #d7dee8; background: #f8fafc; }
#results h2 { margin: 0 0 6px; }
#results .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 12px 0 16px; }
#results .summary-card { background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; padding: 10px 12px; }
#results .summary-card b { display: block; font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .02em; }
#results .summary-card span { display: block; margin-top: 4px; font-size: 20px; font-weight: 800; color: #111827; overflow-wrap: anywhere; }
#results .table-wrap { max-height: 420px; overflow: auto; border: 1px solid #d7dee8; border-radius: 8px; background: #ffffff; }
#results table { width: 100%; border-collapse: collapse; font-size: 12px; }
#results th, #results td { border-bottom: 1px solid #e2e8f0; padding: 7px 8px; text-align: left; white-space: nowrap; }
#results th { position: sticky; top: 0; background: #e2e8f0; z-index: 1; }
#results tr:nth-child(even) td { background: #f8fafc; }
#globalRoutesTable tbody tr { cursor: pointer; }
#globalRoutesTable tbody tr:hover td { background: #eff6ff; }
#diversityTable tbody tr { cursor: pointer; }
#diversityTable tbody tr:hover td { background: #f0fdf4; }
#distinctRoutesTable tbody tr { cursor: pointer; }
#distinctRoutesTable tbody tr:hover td { background: #ecfeff; }
button { display: block; width: 100%; margin: 4px 0; padding: 8px; border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; text-align: left; cursor: pointer; }
button.active { border-color: #2563eb; background: #eff6ff; }
.controls { display: flex; gap: 8px; align-items: center; margin: 10px 0; }
.controls button { display: inline-flex; width: auto; min-width: 92px; justify-content: center; text-align: center; }
select { width: 100%; padding: 7px; border: 1px solid #cbd5e1; border-radius: 6px; background: #fff; }
svg { width: 100%; height: 62vh; background: #ffffff; border: 1px solid #d7dee8; border-radius: 8px; }
pre { background: #0f172a; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow: auto; }
.ok { color: #15803d; font-weight: 700; }
.bad { color: #b91c1c; font-weight: 700; }
.warn { color: #b45309; font-weight: 700; }
.visited { color: #6d28d9; font-weight: 700; }
.muted { color: #64748b; font-size: 12px; }
.metric { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin: 12px 0; font-size: 13px; }
.metric span { background: #f1f5f9; padding: 6px; border-radius: 6px; }
.edge-base { stroke: #94a3b8; stroke-width: 1.2; opacity: .38; }
.edge-p0 { stroke: #2563eb; stroke-width: 4; opacity: .82; stroke-linecap: round; }
.edge-source { stroke: #f59e0b; stroke-width: 3.6; opacity: .8; stroke-linecap: round; }
.edge-candidate-ok { stroke: #16a34a; stroke-width: 4; opacity: .86; stroke-linecap: round; }
.edge-candidate-bad { stroke: #dc2626; stroke-width: 4; opacity: .78; stroke-linecap: round; }
.edge-candidate-duplicate { stroke: #9333ea; stroke-width: 4; opacity: .86; stroke-linecap: round; stroke-dasharray: 10 4; }
.edge-candidate-visited { stroke: #7c3aed; stroke-width: 4; opacity: .82; stroke-linecap: round; stroke-dasharray: 4 4; }
.edge-distinct-route { stroke: #0891b2; stroke-width: 5.2; opacity: .94; stroke-linecap: round; stroke-dasharray: 12 3; }
.edge-failed-old { stroke: #ef4444; stroke-width: 5; opacity: .78; stroke-dasharray: 8 4; stroke-linecap: round; }
.edge-failed-new { stroke: #7f1d1d; stroke-width: 7; opacity: .98; stroke-dasharray: 8 4; stroke-linecap: round; }
.node { fill: #fff; stroke: #334155; stroke-width: 1.2; opacity: .86; }
.node-exit { fill: #dcfce7; stroke: #15803d; }
.node-origin { fill: #f97316; stroke: #111827; stroke-width: 2; }
.node-target { fill: #22c55e; stroke: #111827; stroke-width: 2; }
.node-score-box { fill: #111827; opacity: .88; rx: 4; ry: 4; }
.node-score-text { fill: #ffffff; font-size: 12px; font-weight: 800; text-anchor: middle; dominant-baseline: central; pointer-events: none; }
.node-score-zero .node-score-box { fill: #64748b; opacity: .72; }
.legend { display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap:8px; margin:10px 0; font-size:12px; }
.legend span { padding:7px 9px; border-radius:6px; background:#eef2f7; border-left: 5px solid #94a3b8; }
.legend .p0 { border-left-color:#2563eb; }
.legend .source { border-left-color:#f59e0b; }
.legend .ok { border-left-color:#16a34a; color:#111827; font-weight:400; }
.legend .bad { border-left-color:#dc2626; color:#111827; font-weight:400; }
.legend .fail { border-left-color:#991b1b; }
.legend .duplicate { border-left-color:#9333ea; }
.legend .distinct { border-left-color:#0891b2; }
.help { background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:10px; font-size:12px; line-height:1.45; }
.route-tools { display: grid; grid-template-columns: repeat(4, minmax(0, auto)); gap: 8px; align-items: center; margin: 8px 0 10px; }
.route-tools select { grid-column: 1 / -1; }
.route-tools button { display: inline-flex; width: auto; min-width: 98px; justify-content: center; text-align: center; }
.path-cell { white-space: normal; min-width: 360px; max-width: 760px; overflow-wrap: anywhere; }
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
<div class="controls">
  <button id="prevStep" type="button">Anterior</button>
  <button id="playStep" type="button">Play</button>
  <button id="nextStep" type="button">Siguiente</button>
  <span class="muted">Tambien puedes usar las flechas izquierda/derecha.</span>
</div>
<div class="route-tools" id="routeTools">
  <select id="distinctRouteGroup" aria-label="Grupo de rutas distintas"></select>
  <button id="prevDistinctRoute" type="button">Ruta -</button>
  <button id="toggleDistinctRoute" type="button">Ver ruta</button>
  <button id="nextDistinctRoute" type="button">Ruta +</button>
  <button id="toggleRouteOnly" type="button">Solo rutas</button>
  <span class="muted" id="distinctRouteStatus"></span>
</div>
<div class="metric" id="metrics"></div>
<div class="help">
  C0 = coste de la ruta minima inicial P0. tau = tolerancia. Cmax = C0 x (1 + tau). Calt = coste de la ruta recalculada despues del fallo actual. "Recurso eliminado ahora" cambia porque cada paso prueba un fallo distinto. "Paso perfil" indica la posicion visual dentro del perfil; "casos evaluados" es el contador CER acumulado.
</div>
<div class="legend">
  <span>gris: grafo base completo usado por CER</span>
  <span class="p0">azul: P0, ruta minima inicial</span>
  <span class="source">ambar: ruta fuente a la que se le aplica el fallo actual</span>
  <span class="ok">verde: ruta alternativa aceptada dentro de Cmax</span>
  <span class="duplicate">morado discontinuo: ruta valida pero duplicada</span>
  <span class="bad">rojo continuo: candidata rechazada o fuera de tolerancia</span>
  <span class="fail">rojo discontinuo grueso: recurso/arista eliminada en este paso</span>
  <span class="distinct">cian discontinuo: ruta distinta seleccionada</span>
  <span>numero negro en nodo: rutas unicas globales para la salida activa</span>
</div>
<svg id="graph" role="img" aria-label="CER graph visualization"></svg>
<pre id="detail"></pre>
</section>
</main>
<section id="results">
  <h2>Resultado final CER</h2>
  <p class="muted">Resumen calculado a partir de todos los pasos y perfiles incluidos en este HTML.</p>
  <div class="summary-grid" id="resultCards"></div>
  <h3>Rutas unicas por nodo y salida</h3>
  <p class="muted">Deduplica por secuencia exacta de nodos entre todos los perfiles. Esta es la lectura estricta para no contar dos veces la misma ruta en perfiles distintos.</p>
  <div class="table-wrap">
    <table id="globalRoutesTable">
      <thead>
        <tr>
          <th>origin</th>
          <th>target</th>
          <th>uniqueDistinctRoutes</th>
          <th>sumProfileDistinctRoutes</th>
          <th>repeatedAcrossProfiles</th>
          <th>profiles</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
  <h3>Tabla por nodo, salida y perfil</h3>
  <div class="table-wrap">
    <table id="resultTable">
      <thead>
        <tr>
          <th>origin</th>
          <th>target</th>
          <th>profile</th>
          <th>profileDistinctRoutes</th>
          <th>targetUnique</th>
          <th>accepted</th>
          <th>total</th>
          <th>coverage</th>
          <th>noPath</th>
          <th>overTol.</th>
          <th>duplicate</th>
          <th>visited</th>
          <th>runtimeMs</th>
          <th>trunc.</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
  <h3>Diagnostico de diversidad de rutas</h3>
  <p class="muted">Solape Jaccard de aristas: 0 significa rutas sin aristas comunes, 1 significa rutas casi iguales en aristas. Esta tabla no cambia CER; ayuda a juzgar si las rutas exactas distintas son alternativas espaciales relevantes.</p>
  <div class="table-wrap">
    <table id="diversityTable">
      <thead>
        <tr>
          <th>origin</th>
          <th>target</th>
          <th>profile</th>
          <th>routes</th>
          <th>uniqueEdges</th>
          <th>meanEdges</th>
          <th>mean vs P0</th>
          <th>mean pairwise</th>
          <th>max pairwise</th>
          <th>pairs >= 90%</th>
          <th>lectura</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
  <h3>Rutas distintas guardadas</h3>
  <p class="muted">Cada fila es una ruta aceptada y distinta por secuencia exacta de nodos. El solape se calcula contra P0 cuando hay una ruta base disponible en el payload.</p>
  <div class="table-wrap">
    <table id="distinctRoutesTable">
      <thead>
        <tr>
          <th>origin</th>
          <th>target</th>
          <th>scope</th>
          <th>profile</th>
          <th>#</th>
          <th>nodes</th>
          <th>overlap P0</th>
          <th>path</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
</section>
<script>
const payload = __CER_PAYLOAD__;
const graph = __CER_GRAPH__;
const preferredLevel = __CER_LEVEL__;
const steps = payload.debugSteps || [];
document.body.classList.add(`layout-${payload.metadata?.visualLayout || "standard"}`);
const runInfo = runStatus(payload);
document.getElementById("meta").textContent = `${payload.metadata?.graphView || "graph"} | ${steps.length} pasos | ${runInfo.short}`;
const list = document.getElementById("steps");
const detail = document.getElementById("detail");
const title = document.getElementById("title");
const status = document.getElementById("status");
const metrics = document.getElementById("metrics");
const svg = document.getElementById("graph");
const levelSelect = document.getElementById("level");
const resultCards = document.getElementById("resultCards");
const globalRoutesTable = document.querySelector("#globalRoutesTable tbody");
const resultTable = document.querySelector("#resultTable tbody");
const diversityTable = document.querySelector("#diversityTable tbody");
const distinctRoutesTable = document.querySelector("#distinctRoutesTable tbody");
const prevStep = document.getElementById("prevStep");
const playStep = document.getElementById("playStep");
const nextStep = document.getElementById("nextStep");
const distinctRouteGroup = document.getElementById("distinctRouteGroup");
const prevDistinctRoute = document.getElementById("prevDistinctRoute");
const toggleDistinctRoute = document.getElementById("toggleDistinctRoute");
const nextDistinctRoute = document.getElementById("nextDistinctRoute");
const toggleRouteOnly = document.getElementById("toggleRouteOnly");
const distinctRouteStatus = document.getElementById("distinctRouteStatus");
let activeIndex = 0;
let distinctRouteIndex = 0;
let selectedRouteGroupIndex = 0;
let showDistinctRoute = false;
let routeOnlyMode = false;
let playTimer = null;
const ns = "http://www.w3.org/2000/svg";
const resultRows = collectResultRows(payload);
const globalRouteGroups = collectGlobalRouteRows(resultRows);
const profileRouteGroups = resultRows.filter(row => (row.routeSignatures || []).length > 0);
const routeGroups = [...globalRouteGroups, ...profileRouteGroups];
renderResults(resultRows);
renderRouteGroups();
renderDiversity(routeGroups);
renderDistinctRoutes(routeGroups);
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
prevStep.onclick = () => show(Math.max(0, activeIndex - 1));
nextStep.onclick = () => show(Math.min(steps.length - 1, activeIndex + 1));
playStep.onclick = () => togglePlay();
distinctRouteGroup.onchange = () => selectRouteGroup(Number(distinctRouteGroup.value || 0), 0, true, false);
prevDistinctRoute.onclick = () => moveDistinctRoute(-1);
nextDistinctRoute.onclick = () => moveDistinctRoute(1);
toggleDistinctRoute.onclick = () => toggleDistinctRouteView();
toggleRouteOnly.onclick = () => toggleRouteOnlyView();
document.addEventListener("keydown", event => {
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    show(Math.max(0, activeIndex - 1));
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    show(Math.min(steps.length - 1, activeIndex + 1));
  } else if (event.key === " ") {
    event.preventDefault();
    togglePlay();
  }
});
function show(index) {
  if (!steps.length) return;
  activeIndex = index;
  const step = steps[index] || {};
  list.querySelectorAll("button").forEach((b, i) => b.classList.toggle("active", i === index));
  const decision = decisionInfo(step);
  const group = activeRouteGroup();
  if (routeOnlyMode && group) {
    title.textContent = `Rutas distintas | ${group.origin} -> ${group.target} | ${group.profile}`;
    status.innerHTML = `<span class="ok">EXPLORADOR DE RESULTADOS</span><br><span class="muted">Grafo limpio con una ruta aceptada y distinta superpuesta. El paso CER activo queda solo como referencia temporal.</span>`;
  } else {
    title.textContent = `${step.origin || "?"} -> ${step.target || "?"} | ${step.failureProfile || ""}`;
    status.innerHTML = `<span class="${decision.className}">${decision.label}</span><br><span class="muted">${decision.description}</span>`;
  }
  metrics.innerHTML = [
    ["cálculo", runInfo.short],
    ["límites", runInfo.limits],
    ["orden visual", payload.metadata?.visualOrder || "calculation"],
    ["paso global", `${step.globalStepIndex ?? "-"} / ${step.globalStepCount ?? "-"}`],
    ["paso cálculo", step.calculationStepIndex ?? "-"],
    ["paso perfil", `${step.profileStepIndex ?? "-"} / ${step.profileStepCount ?? "-"}`],
    ["rama", `${step.branchStatus || "-"} ${step.branchDeathReason ? "(" + step.branchDeathReason + ")" : ""}`],
    ["tau", fmt(payload.metadata?.costTolerance)],
    ["C0 ruta inicial", fmt(step.baseCost)],
    ["Cmax tolerado", fmt(step.costLimit)],
    ["Calt candidata", fmt(step.candidateCost)],
    ["casos evaluados", step.evaluatedFailureCases ?? "-"],
    ["RUTAS DISTINTAS", step.distinctRouteCount ?? "-"],
    ["ruta inspeccionada", distinctRouteMetric()],
    ["recurso eliminado ahora", formatFailureUnits(step)],
  ].map(([k, v]) => `<span><b>${k}</b><br>${v}</span>`).join("");
  drawGraph(step);
  syncDistinctRouteControls();
  detail.textContent = JSON.stringify(step, null, 2);
  prevStep.disabled = index <= 0;
  nextStep.disabled = index >= steps.length - 1;
  if (index >= steps.length - 1 && playTimer) stopPlay();
}
function togglePlay() {
  if (playTimer) stopPlay();
  else startPlay();
}
function startPlay() {
  if (!steps.length) return;
  playStep.textContent = "Pausa";
  playTimer = setInterval(() => {
    if (activeIndex >= steps.length - 1) {
      stopPlay();
      return;
    }
    show(activeIndex + 1);
  }, 850);
}
function stopPlay() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null;
  playStep.textContent = "Play";
}
function fmt(value) {
  return value == null ? "-" : Number(value).toFixed(3);
}
function runStatus(payload) {
  const metadata = payload.metadata || {};
  const profileStats = [];
  const limitHits = {};
  for (const origin of Object.values(payload.nodes || {})) {
    for (const target of Object.values(origin.targets || {})) {
      Object.assign(limitHits, target.summary?.limitHits || {});
      for (const profile of Object.values(target.failureProfiles || {})) profileStats.push(profile);
    }
  }
  const runtime = fmt(metadata.runtimeMs);
  const started = metadata.startedPairs ?? "-";
  const completed = metadata.completedPairs ?? "-";
  const runtimeCut = !!metadata.truncatedByRuntime || profileStats.some(profile => profile.truncatedByRuntime);
  const comboCut = profileStats.some(profile => profile.truncatedByCombinations) || Number(limitHits.maxCombinations || 0) > 0;
  const comboCases = profileStats.reduce((total, profile) => total + Number(profile.combinationsTruncatedCases || 0), 0);
  const status = runtimeCut ? "cortado por runtime" : comboCut ? "cortado por combinaciones" : "completado";
  const limits = [
    runtimeCut ? `runtime alcanzado` : "",
    comboCut ? `maxCombinations ${comboCases || limitHits.maxCombinations || ""}` : "",
    limitHits.maxDepth ? `maxDepth ${limitHits.maxDepth}` : "",
    limitHits.maxTotalFailures ? `maxTotalFailures ${limitHits.maxTotalFailures}` : "",
  ].filter(Boolean).join(" | ") || "sin cortes";
  return {
    short: `${status} | ${runtime} ms | pares ${completed}/${started}`,
    limits,
  };
}
function collectResultRows(payload) {
  const rows = [];
  for (const [originId, origin] of Object.entries(payload.nodes || {})) {
    for (const [targetId, target] of Object.entries(origin.targets || {})) {
      const targetSummary = target.summary || {};
      for (const [profileLabel, profile] of Object.entries(target.failureProfiles || {})) {
        rows.push({
          origin: originId,
          target: targetId,
          profile: profileLabel,
          distinctRoutes: Number(profile.distinctRoutes || 0),
          routeSignatures: Array.isArray(profile.distinctRouteSignatures) ? profile.distinctRouteSignatures : [],
          targetUniqueDistinctRoutes: Number(targetSummary.uniqueDistinctRoutes ?? targetSummary.distinctRoutes ?? 0),
          targetProfileDistinctRoutes: Number(targetSummary.profileDistinctRoutes ?? 0),
          targetRepeatedRoutesAcrossProfiles: Number(targetSummary.repeatedRoutesAcrossProfiles ?? 0),
          acceptedCases: Number(profile.acceptedCases || 0),
          totalCases: Number(profile.totalCases || 0),
          coverage: Number(profile.coverage || 0),
          noPathCases: Number(profile.noPathCases || 0),
          overToleranceCases: Number(profile.overToleranceCases || 0),
          duplicateRouteCases: Number(profile.duplicateRouteCases || 0),
          visitedStateCases: Number(profile.visitedStateCases || 0),
          runtimeMs: Number(profile.runtimeMs || 0),
          truncated: !!profile.truncatedByRuntime || !!profile.truncatedByCombinations,
        });
      }
    }
  }
  rows.sort((a, b) =>
    b.distinctRoutes - a.distinctRoutes ||
    b.coverage - a.coverage ||
    a.origin.localeCompare(b.origin) ||
    a.profile.localeCompare(b.profile)
  );
  return rows;
}
function renderResults(rows) {
  if (!resultCards || !resultTable) return;
  const origins = new Set(rows.map(row => row.origin));
  const targets = new Set(rows.map(row => row.target));
  const profiles = new Set(rows.map(row => row.profile));
  const totalDistinct = rows.reduce((total, row) => total + row.distinctRoutes, 0);
  const totalAccepted = rows.reduce((total, row) => total + row.acceptedCases, 0);
  const totalCases = rows.reduce((total, row) => total + row.totalCases, 0);
  const globalRouteStats = globalDistinctRouteStats(rows);
  const best = rows[0] || {};
  const bestGlobal = globalRouteGroups[0] || {};
  resultCards.innerHTML = [
    ["suma por perfil", totalDistinct],
    ["rutas unicas globales", globalRouteStats.uniqueRoutes],
    ["repetidas entre perfiles", globalRouteStats.repeatedAcrossProfiles],
    ["mejor nodo global", bestGlobal.origin ? `${bestGlobal.origin} -> ${bestGlobal.target} = ${bestGlobal.uniqueDistinctRoutes}` : "-"],
    ["mejor fila", best.origin ? `${best.origin} -> ${best.target} | ${best.profile} = ${best.distinctRoutes}` : "-"],
    ["origenes", origins.size],
    ["salidas", targets.size],
    ["perfiles", [...profiles].join(", ") || "-"],
    ["coverage global", totalCases ? (totalAccepted / totalCases).toFixed(3) : "-"],
  ].map(([label, value]) => `<div class="summary-card"><b>${label}</b><span>${value}</span></div>`).join("");
  resultTable.innerHTML = rows.map(row => `
    <tr>
      <td>${escapeHtml(row.origin)}</td>
      <td>${escapeHtml(row.target)}</td>
      <td>${escapeHtml(row.profile)}</td>
      <td><b>${row.distinctRoutes}</b></td>
      <td><b>${row.targetUniqueDistinctRoutes || "-"}</b></td>
      <td>${row.acceptedCases}</td>
      <td>${row.totalCases}</td>
      <td>${row.coverage.toFixed(3)}</td>
      <td>${row.noPathCases}</td>
      <td>${row.overToleranceCases}</td>
      <td>${row.duplicateRouteCases}</td>
      <td>${row.visitedStateCases}</td>
      <td>${row.runtimeMs.toFixed(1)}</td>
      <td>${row.truncated ? "si" : "no"}</td>
    </tr>
  `).join("") || `<tr><td colspan="14">Sin metricas de perfiles en este payload.</td></tr>`;
  renderGlobalRoutes(globalRouteGroups);
}
function globalDistinctRouteStats(rows) {
  const allRoutes = [];
  for (const row of rows) {
    for (const route of row.routeSignatures || []) allRoutes.push(`${row.origin}||${row.target}||${routeKey(route)}`);
  }
  const uniqueRoutes = new Set(allRoutes).size;
  return {
    uniqueRoutes,
    repeatedAcrossProfiles: Math.max(0, allRoutes.length - uniqueRoutes),
  };
}
function routeKey(route) {
  return (route || []).map(value => String(value)).join("||");
}
function collectGlobalRouteRows(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = `${row.origin}||${row.target}`;
    if (!groups.has(key)) {
      groups.set(key, {
        origin: row.origin,
        target: row.target,
        profile: "GLOBAL",
        scope: "global",
        isGlobal: true,
        distinctRoutes: 0,
        routeSignatures: [],
        profileDistinctRoutes: 0,
        repeatedRoutesAcrossProfiles: 0,
        profiles: new Set(),
        _routeMap: new Map(),
      });
    }
    const group = groups.get(key);
    group.profiles.add(row.profile);
    group.profileDistinctRoutes += row.distinctRoutes;
    for (const route of row.routeSignatures || []) {
      const routeId = routeKey(route);
      if (!group._routeMap.has(routeId)) group._routeMap.set(routeId, route);
    }
  }
  const result = [...groups.values()].map(group => {
    group.routeSignatures = [...group._routeMap.values()];
    group.distinctRoutes = group.routeSignatures.length;
    group.uniqueDistinctRoutes = group.distinctRoutes;
    group.repeatedRoutesAcrossProfiles = Math.max(0, group.profileDistinctRoutes - group.distinctRoutes);
    group.profileList = [...group.profiles].sort();
    delete group._routeMap;
    delete group.profiles;
    return group;
  });
  result.sort((a, b) =>
    b.uniqueDistinctRoutes - a.uniqueDistinctRoutes ||
    a.origin.localeCompare(b.origin) ||
    a.target.localeCompare(b.target)
  );
  return result;
}
function renderGlobalRoutes(groups) {
  if (!globalRoutesTable) return;
  globalRoutesTable.innerHTML = groups.map((group, index) => `
    <tr data-global-group="${index}">
      <td>${escapeHtml(group.origin)}</td>
      <td>${escapeHtml(group.target)}</td>
      <td><b>${group.uniqueDistinctRoutes}</b></td>
      <td>${group.profileDistinctRoutes}</td>
      <td>${group.repeatedRoutesAcrossProfiles}</td>
      <td>${escapeHtml((group.profileList || []).join(", "))}</td>
    </tr>
  `).join("") || `<tr><td colspan="6">Sin rutas distintas globales.</td></tr>`;
  globalRoutesTable.querySelectorAll("tr[data-global-group]").forEach(row => {
    row.onclick = () => {
      selectRouteGroup(Number(row.dataset.globalGroup || 0), 0, true, true);
      document.getElementById("graph")?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
  });
}
function renderRouteGroups() {
  if (!distinctRouteGroup) return;
  distinctRouteGroup.innerHTML = "";
  if (!routeGroups.length) {
    const option = document.createElement("option");
    option.value = "0";
    option.textContent = "Sin rutas distintas guardadas";
    distinctRouteGroup.appendChild(option);
    distinctRouteGroup.disabled = true;
    return;
  }
  routeGroups.forEach((row, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = routeGroupLabel(row);
    distinctRouteGroup.appendChild(option);
  });
  distinctRouteGroup.disabled = false;
}
function routeGroupLabel(row) {
  if (row.isGlobal) return `GLOBAL | ${row.origin} -> ${row.target} | ${row.routeSignatures.length} rutas unicas`;
  return `${row.origin} -> ${row.target} | ${row.profile} | ${row.routeSignatures.length} rutas`;
}
function renderDiversity(groups) {
  if (!diversityTable) return;
  const stats = groups.map((row, groupIndex) => ({ row, groupIndex, stats: routeDiversityStats(row) }));
  stats.sort((a, b) =>
    b.stats.routeCount - a.stats.routeCount ||
    (b.stats.meanPairwiseJaccard ?? -1) - (a.stats.meanPairwiseJaccard ?? -1) ||
    a.row.profile.localeCompare(b.row.profile)
  );
  diversityTable.innerHTML = stats.map(item => `
    <tr data-diversity-group="${item.groupIndex}">
      <td>${escapeHtml(item.row.origin)}</td>
      <td>${escapeHtml(item.row.target)}</td>
      <td>${escapeHtml(item.row.profile)}</td>
      <td><b>${item.stats.routeCount}</b></td>
      <td>${item.stats.uniqueEdges}</td>
      <td>${item.stats.meanEdges.toFixed(1)}</td>
      <td>${formatRatio(item.stats.meanP0Jaccard)}</td>
      <td>${formatRatio(item.stats.meanPairwiseJaccard)}</td>
      <td>${formatRatio(item.stats.maxPairwiseJaccard)}</td>
      <td>${item.stats.nearDuplicatePairs90}/${item.stats.pairCount}</td>
      <td>${escapeHtml(item.stats.reading)}</td>
    </tr>
  `).join("") || `<tr><td colspan="11">Este payload no incluye rutas distintas guardadas.</td></tr>`;
  diversityTable.querySelectorAll("tr[data-diversity-group]").forEach(row => {
    row.onclick = () => {
      selectRouteGroup(Number(row.dataset.diversityGroup || 0), 0, true, true);
      document.getElementById("graph")?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
  });
}
function renderDistinctRoutes(groups) {
  if (!distinctRoutesTable) return;
  const flattened = [];
  for (const [groupIndex, row] of groups.entries()) {
    const base = basePathForRow(row);
    (row.routeSignatures || []).forEach((route, index) => {
      flattened.push({ groupIndex, row, route, index, overlap: routeOverlap(route, base) });
    });
  }
  flattened.sort((a, b) =>
    a.row.origin.localeCompare(b.row.origin) ||
    a.row.target.localeCompare(b.row.target) ||
    a.row.profile.localeCompare(b.row.profile) ||
    a.index - b.index
  );
  distinctRoutesTable.innerHTML = flattened.map(item => `
    <tr data-route-group="${item.groupIndex}" data-route-index="${item.index}">
      <td>${escapeHtml(item.row.origin)}</td>
      <td>${escapeHtml(item.row.target)}</td>
      <td>${item.row.isGlobal ? "global" : "perfil"}</td>
      <td>${escapeHtml(item.row.profile)}</td>
      <td>${item.index + 1}</td>
      <td>${item.route.length}</td>
      <td>${formatOverlap(item.overlap)}</td>
      <td class="path-cell">${escapeHtml(item.route.join(" -> "))}</td>
    </tr>
  `).join("") || `<tr><td colspan="8">Este payload no incluye distinctRouteSignatures.</td></tr>`;
  distinctRoutesTable.querySelectorAll("tr[data-route-group]").forEach(row => {
    row.onclick = () => {
      selectRouteGroup(Number(row.dataset.routeGroup || 0), Number(row.dataset.routeIndex || 0), true, true);
      document.getElementById("graph")?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
  });
}
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}
function decisionInfo(step) {
  const reason = String(step.reason || "");
  if (reason === "accepted") return { label: "ACEPTADA", className: "ok", description: "Ruta alternativa nueva dentro de Cmax." };
  if (reason === "duplicate_route") return { label: "DUPLICADA", className: "warn", description: "Ruta valida dentro de Cmax, pero su secuencia de nodos ya estaba contada." };
  if (reason === "visited_state") return { label: "ESTADO VISITADO", className: "visited", description: "Ese conjunto de fallos ya se habia evaluado; se reutiliza el resultado." };
  if (reason === "over_tolerance") return { label: "RECHAZADA POR TOLERANCIA", className: "bad", description: "Hay ruta, pero Calt supera Cmax." };
  if (reason === "no_path") return { label: "SIN RUTA", className: "bad", description: "El fallo deja al origen sin ruta hacia la salida." };
  return { label: step.accepted ? "ACEPTADA" : "RECHAZADA", className: step.accepted ? "ok" : "bad", description: reason || "-" };
}
function candidateClass(step) {
  const reason = String(step.reason || "");
  if (reason === "duplicate_route") return "edge-candidate-duplicate";
  if (reason === "visited_state") return "edge-candidate-visited";
  return step.accepted ? "edge-candidate-ok" : "edge-candidate-bad";
}
function activeRouteGroup() {
  return routeGroups[selectedRouteGroupIndex] || routeGroups[0] || null;
}
function activeDistinctRoutes() {
  const row = activeRouteGroup();
  return (row && Array.isArray(row.routeSignatures)) ? row.routeSignatures : [];
}
function selectedDistinctRoute() {
  const routes = activeDistinctRoutes();
  if (!routes.length || !showDistinctRoute) return null;
  distinctRouteIndex = Math.max(0, Math.min(distinctRouteIndex, routes.length - 1));
  return routes[distinctRouteIndex] || null;
}
function moveDistinctRoute(delta) {
  const routes = activeDistinctRoutes();
  if (!routes.length) return;
  showDistinctRoute = true;
  distinctRouteIndex = (distinctRouteIndex + delta + routes.length) % routes.length;
  show(activeIndex);
}
function toggleDistinctRouteView() {
  const routes = activeDistinctRoutes();
  if (!routes.length) return;
  showDistinctRoute = !showDistinctRoute;
  if (!showDistinctRoute) routeOnlyMode = false;
  show(activeIndex);
}
function toggleRouteOnlyView() {
  const routes = activeDistinctRoutes();
  if (!routes.length) return;
  routeOnlyMode = !routeOnlyMode;
  showDistinctRoute = true;
  show(activeIndex);
}
function selectRouteGroup(groupIndex, routeIndex = 0, visible = true, onlyRoutes = routeOnlyMode) {
  selectedRouteGroupIndex = Math.max(0, Math.min(groupIndex, routeGroups.length - 1));
  distinctRouteIndex = Math.max(0, routeIndex);
  showDistinctRoute = visible;
  routeOnlyMode = !!onlyRoutes;
  if (distinctRouteGroup) distinctRouteGroup.value = String(selectedRouteGroupIndex);
  if (steps.length) show(activeIndex);
  else drawGraph({});
}
function syncDistinctRouteControls() {
  const routes = activeDistinctRoutes();
  const hasRoutes = routes.length > 0;
  prevDistinctRoute.disabled = !hasRoutes;
  nextDistinctRoute.disabled = !hasRoutes;
  toggleDistinctRoute.disabled = !hasRoutes;
  toggleRouteOnly.disabled = !hasRoutes;
  toggleDistinctRoute.textContent = showDistinctRoute ? "Ocultar ruta" : "Ver ruta";
  toggleRouteOnly.textContent = routeOnlyMode ? "Ver calculo" : "Solo rutas";
  distinctRouteStatus.textContent = distinctRouteMetric();
}
function distinctRouteMetric() {
  const group = activeRouteGroup();
  const routes = activeDistinctRoutes();
  if (!routes.length) return "sin rutas guardadas";
  distinctRouteIndex = Math.max(0, Math.min(distinctRouteIndex, routes.length - 1));
  const route = routes[distinctRouteIndex] || [];
  const basePath = basePathForRow(group);
  const overlap = routeOverlap(route, basePath);
  const diversity = routeDiversityStats(group);
  return `${group.origin} -> ${group.target} | ${group.profile} | ruta ${distinctRouteIndex + 1}/${routes.length} | nodos ${route.length} | solape P0 ${formatOverlap(overlap)} | media entre rutas ${formatRatio(diversity.meanPairwiseJaccard)}`;
}
function basePathForRow(row) {
  if (!row) return [];
  const step = steps.find(item => item.origin === row.origin && item.target === row.target && item.failureProfile === row.profile)
      || steps.find(item => item.origin === row.origin && item.target === row.target);
  return step?.basePath || [];
}
function pathEdges(path) {
  const edges = [];
  for (let i = 0; i < (path || []).length - 1; i++) {
    const a = String(path[i]);
    const b = String(path[i + 1]);
    edges.push(a < b ? `${a}|${b}` : `${b}|${a}`);
  }
  return edges;
}
function pathEdgeSet(path) {
  return new Set(pathEdges(path));
}
function edgeJaccard(left, right) {
  if (!left || !right || (!left.size && !right.size)) return null;
  let shared = 0;
  for (const edge of left) if (right.has(edge)) shared += 1;
  const union = new Set([...left, ...right]).size;
  return union ? shared / union : null;
}
function routeDiversityStats(row) {
  const routes = (row?.routeSignatures || []).filter(route => Array.isArray(route) && route.length);
  const edgeSets = routes.map(pathEdgeSet);
  const routeEdgeCounts = edgeSets.map(edges => edges.size);
  const uniqueEdges = new Set(edgeSets.flatMap(edges => [...edges]));
  const baseEdges = pathEdgeSet(basePathForRow(row));
  const p0Scores = baseEdges.size ? edgeSets.map(edges => edgeJaccard(edges, baseEdges)).filter(value => value != null) : [];
  const pairwise = [];
  for (let i = 0; i < edgeSets.length; i++) {
    for (let j = i + 1; j < edgeSets.length; j++) {
      const score = edgeJaccard(edgeSets[i], edgeSets[j]);
      if (score != null) pairwise.push(score);
    }
  }
  const meanPairwise = mean(pairwise);
  const near90 = pairwise.filter(value => value >= 0.9).length;
  const near75 = pairwise.filter(value => value >= 0.75).length;
  return {
    routeCount: routes.length,
    uniqueEdges: uniqueEdges.size,
    meanEdges: mean(routeEdgeCounts) ?? 0,
    meanP0Jaccard: mean(p0Scores),
    maxP0Jaccard: p0Scores.length ? Math.max(...p0Scores) : null,
    meanPairwiseJaccard: meanPairwise,
    maxPairwiseJaccard: pairwise.length ? Math.max(...pairwise) : null,
    nearDuplicatePairs90: near90,
    nearDuplicatePairs75: near75,
    pairCount: pairwise.length,
    reading: diversityReading(routes.length, meanPairwise, near90, pairwise.length, uniqueEdges.size, mean(routeEdgeCounts) ?? 0),
  };
}
function mean(values) {
  const filtered = (values || []).filter(value => Number.isFinite(value));
  if (!filtered.length) return null;
  return filtered.reduce((total, value) => total + value, 0) / filtered.length;
}
function formatRatio(value) {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${Math.round(value * 100)}%`;
}
function diversityReading(routeCount, meanPairwise, near90, pairCount, uniqueEdges, meanEdges) {
  if (routeCount <= 1) return "sin comparacion";
  const nearRatio = pairCount ? near90 / pairCount : 0;
  const spread = meanEdges ? uniqueEdges / meanEdges : 0;
  if (meanPairwise >= 0.75 || nearRatio >= 0.4) return "muchas variantes muy parecidas";
  if (meanPairwise >= 0.45) return spread >= 2.5 ? "diversidad media con varios corredores" : "diversidad media";
  return spread >= 2.5 ? "alta diversidad espacial" : "bajo solape, revisar visualmente";
}
function routeOverlap(route, basePath) {
  const routeEdges = pathEdges(route);
  const baseEdges = new Set(pathEdges(basePath));
  if (!routeEdges.length || !baseEdges.size) return null;
  const shared = routeEdges.filter(edge => baseEdges.has(edge)).length;
  return { shared, total: Math.max(routeEdges.length, baseEdges.size), routeEdges: routeEdges.length, baseEdges: baseEdges.size };
}
function formatOverlap(overlap) {
  if (!overlap) return "-";
  return `${Math.round((overlap.shared / Math.max(overlap.total, 1)) * 100)}% (${overlap.shared}/${overlap.total})`;
}
function formatFailureUnits(step) {
  const units = step.newlyFailedUnits || [];
  if (!units.length) return "-";
  return units.map(unit => shortFailureValue(unit.kind || "fallo", unit.value || "")).join(", ");
}
function shortFailureValue(kind, value) {
  const label = kind === "resource" ? "recurso" : kind;
  value = String(value || "");
  if (value.length > 38) value = `${value.slice(0, 20)}...${value.slice(-14)}`;
  return `${label}: ${value}`;
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
function drawNodeScore(node, project, value) {
  const [x, y] = project(node);
  const text = String(value ?? 0);
  const group = document.createElementNS(ns, "g");
  if (Number(value || 0) === 0) group.setAttribute("class", "node-score-zero");
  const width = Math.max(20, 12 + text.length * 7);
  const box = document.createElementNS(ns, "rect");
  box.setAttribute("x", x - width / 2);
  box.setAttribute("y", y - 25);
  box.setAttribute("width", width);
  box.setAttribute("height", 18);
  box.setAttribute("class", "node-score-box");
  const label = document.createElementNS(ns, "text");
  label.setAttribute("x", x);
  label.setAttribute("y", y - 16);
  label.setAttribute("class", "node-score-text");
  label.textContent = text;
  group.appendChild(box);
  group.appendChild(label);
  svg.appendChild(group);
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
function nodeScoresForContext(step) {
  const group = routeOnlyMode ? activeRouteGroup() : null;
  const target = group?.target || step.target || resultRows[0]?.target;
  const scores = new Map();
  const routeKeysByOrigin = new Map();
  for (const row of resultRows) {
    if (row.target !== target) continue;
    if (!routeKeysByOrigin.has(row.origin)) routeKeysByOrigin.set(row.origin, new Set());
    const keys = routeKeysByOrigin.get(row.origin);
    for (const route of row.routeSignatures || []) keys.add(routeKey(route));
    if (!(row.routeSignatures || []).length && row.targetUniqueDistinctRoutes) {
      scores.set(row.origin, row.targetUniqueDistinctRoutes);
    }
  }
  for (const [origin, keys] of routeKeysByOrigin.entries()) {
    if (keys.size) scores.set(origin, keys.size);
  }
  return scores;
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
  if (!routeOnlyMode) {
    drawPath(step.basePath || [], "edge-p0", nodes, project);
    if ((step.failureSourcePath || []).length && !samePath(step.failureSourcePath, step.basePath || [])) {
      drawPath(step.failureSourcePath || [], "edge-source", nodes, project);
    }
    drawPath(step.candidatePath || [], candidateClass(step), nodes, project);
    drawFailed(step, nodes, project);
  }
  const selectedRoute = selectedDistinctRoute();
  if (selectedRoute) drawPath(selectedRoute, "edge-distinct-route", nodes, project);
  for (const node of nodes) drawNode(node, project, node.isExit ? "node node-exit" : "node");
  const scores = nodeScoresForContext(step);
  if (scores.size) {
    for (const node of nodes) {
      if (scores.has(node.id)) drawNodeScore(node, project, scores.get(node.id));
    }
  }
  const routeGroup = routeOnlyMode ? activeRouteGroup() : null;
  const origin = byId.get(routeGroup?.origin || step.origin);
  const target = byId.get(routeGroup?.target || step.target);
  if (origin && (!level || origin.level === level)) { drawNode(origin, project, "node-origin"); drawLabel(origin, project, "origen"); }
  if (target && (!level || target.level === level)) { drawNode(target, project, "node-target"); drawLabel(target, project, "salida"); }
}
if (!steps.length) {
  detail.textContent = JSON.stringify(payload, null, 2);
  drawGraph({});
} else {
  steps.forEach((step, index) => {
    const button = document.createElement("button");
    button.textContent = `${index + 1}. ${step.failureProfile} d${step.failureDepth} | ${step.reason} | rama=${step.branchStatus || "-"} | distintas=${step.distinctRouteCount}`;
    button.onclick = () => show(index);
    list.appendChild(button);
  });
  show(0);
}
</script>
</html>
"""

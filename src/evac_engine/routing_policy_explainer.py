"""Explain how CER is applied by routing policies.

This module does not run the physical evacuation simulation. It builds a static
routing snapshot and exports an auditable HTML/JSON explanation of two policies:
CER-Cost and CER-Agility.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .cer_visualization import _cer_graph_payload
from .domain import IndoorModelBundle, MobilityProfile, ScenarioDefinition
from .overlays import BeaconState, HazardState
from .rerouting_centrality import cer_node_scores, normalize_failure_profiles, rerouting_evacuation_centrality
from .route_recommendation import EvacuationRouteRecommendationService, RouteCandidate, RouteRecommendationConfig
from .routing import RoutingEngine
from .topology import EvacTopology


DEFAULT_POLICY_FAILURE_PROFILES = ((1,), (1, 1), (1, 1, 1))
DEFAULT_CER_PROFILE_WEIGHTS = {
    "(1)": 1.0,
    "(1,1)": 0.6,
    "(1,1,1)": 0.3,
}
POLICY_COLORS = {
    "lowest_cost": "#2563eb",
    "cer_weighted": "#dc2626",
    "cer_agility_yen": "#16a34a",
}


def export_routing_policy_explainer(
    indoor: IndoorModelBundle,
    scenario: ScenarioDefinition,
    *,
    origin: str,
    target: str | None = None,
    profile_id: str | None = None,
    output_dir: str | Path,
    formats: Iterable[str] = ("json", "html"),
    level: str | None = None,
    failure_profiles: Iterable[Iterable[int]] | None = None,
    cost_tolerance: float = 0.2,
    profile_weights: dict[str, float] | None = None,
    k_shortest_paths: int = 6,
    candidate_cost_tolerance: float = 0.35,
    agility_weight: float = 0.35,
    agility_aggregation: str = "mean",
    max_combinations: int = 500,
    max_runtime_ms: int = 30000,
) -> dict[str, Any]:
    topology = EvacTopology.from_indoor_model(indoor)
    engine = RoutingEngine(topology)
    recommender = EvacuationRouteRecommendationService()
    origin_id = indoor.resolve_cell_ref(origin) or origin
    target_id = _resolve_target(indoor, topology, scenario, target)
    profile = _resolve_profile(scenario, profile_id)
    routing_config = _structural_routing_config(scenario)
    cost_policy = str(routing_config.get("costPolicy", "minimum_travel_time"))
    snapshot = engine.compiler.compile(
        mobility_profile=profile,
        cost_policy=cost_policy,
        hazard_state=HazardState(),
        beacon_state=BeaconState(),
        routing_config=routing_config,
    )
    engine._attach_cell_endpoint(
        snapshot.graph,
        origin_id,
        None,
        None,
        profile,
        cost_policy,
        HazardState(),
        BeaconState(),
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
            HazardState(),
            BeaconState(),
            {},
            routing_config,
            direction="in",
        )
    profiles = normalize_failure_profiles(
        failure_profiles or DEFAULT_POLICY_FAILURE_PROFILES,
        max_depth=3,
        max_k=3,
    )
    weights = _normal_profile_weights(profile_weights or _configured_profile_weights(scenario) or DEFAULT_CER_PROFILE_WEIGHTS)
    cer_result = rerouting_evacuation_centrality(
        snapshot.graph,
        [target_id],
        failure_profiles=profiles,
        failure_unit="resource",
        cost_tolerance=cost_tolerance,
        distinctness_policy="exact",
        max_depth=3,
        max_k=3,
        max_combinations=max_combinations,
        max_runtime_ms=max_runtime_ms,
        graph_view=topology.graph_view_name,
        store_routes=False,
    )
    cer_payload = cer_result.to_dict()
    cer_scores = cer_node_scores(cer_result, profile_weights=weights)
    profile_breakdown = _cer_profile_breakdown(cer_payload, weights)
    all_nodes_cer = _all_nodes_cer_payload(cer_scores, profile_breakdown, topology)
    policy_payload = _policy_payload(
        snapshot.graph,
        origin_id,
        target_id,
        profile,
        recommender,
        cer_scores,
        cer_result.metadata,
        k_shortest_paths=k_shortest_paths,
        candidate_cost_tolerance=candidate_cost_tolerance,
        agility_weight=agility_weight,
        agility_aggregation=agility_aggregation,
    )
    payload = {
        "scenarioId": scenario.scenario_id,
        "origin": origin_id,
        "target": target_id,
        "profileId": profile.id if profile else None,
        "graphView": topology.graph_view_name,
        "level": level,
        "cer": {
            "name": "CER",
            "expandedName": "Centralidad de Evacuacion por Reencaminamiento",
            "note": "La R de CER significa Reencaminamiento; la metrica expresa resiliencia de reencaminamiento.",
            "costTolerance": cost_tolerance,
            "failureProfiles": ["(" + ",".join(str(item) for item in profile) + ")" for profile in profiles],
            "profileWeights": weights,
            "metadata": cer_result.metadata,
            "scores": _score_payload(cer_scores),
            "profileBreakdown": profile_breakdown,
            "allNodes": all_nodes_cer,
        },
        "policies": policy_payload,
        "graph": _cer_graph_payload(topology),
    }
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    requested = {str(item).lower() for item in formats}
    paths: dict[str, str] = {}
    if "json" in requested:
        path = output / "policy_comparison.json"
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        paths["json"] = str(path)
        all_nodes_path = output / "cer_all_nodes.json"
        all_nodes_path.write_text(json.dumps(all_nodes_cer, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        paths["cerAllNodesJson"] = str(all_nodes_path)
    if "html" in requested:
        path = output / "policy_comparison.html"
        path.write_text(_POLICY_HTML.replace("__POLICY_PAYLOAD__", json.dumps(payload, ensure_ascii=True)), encoding="utf-8")
        paths["html"] = str(path)
        cost_path = output / "cer_cost_explainer.html"
        cost_path.write_text(_policy_animation_html(payload, "cer_cost"), encoding="utf-8")
        paths["cerCostHtml"] = str(cost_path)
        agility_path = output / "cer_agility_explainer.html"
        agility_path.write_text(_policy_animation_html(payload, "cer_agility"), encoding="utf-8")
        paths["cerAgilityHtml"] = str(agility_path)
    manifest = {
        "scenarioId": scenario.scenario_id,
        "origin": origin_id,
        "target": target_id,
        "profileId": profile.id if profile else None,
        "outputs": paths,
        "outputDir": str(output),
    }
    manifest_path = output / "policy_comparison_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    paths["manifest"] = str(manifest_path)
    return {**manifest, "outputs": paths, "result": payload}


def default_policy_output_dir(scenario_path: str | Path, indoor_path: str | Path, origin: str, target: str) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    scenario = Path(scenario_path).resolve()
    indoor = Path(indoor_path).resolve()
    slug = f"{_slug(scenario.stem)}__{_slug(origin)}__{_slug(target)}"
    try:
        relative = indoor.relative_to((project_root / "models").resolve())
        model_name = relative.parts[0]
        return project_root / "models" / model_name / "outputs" / "routing_policies" / slug
    except ValueError:
        return project_root / "outputs" / "routing_policies" / slug


def _policy_payload(
    graph: Any,
    origin: str,
    target: str,
    profile: MobilityProfile | None,
    recommender: EvacuationRouteRecommendationService,
    cer_scores: dict[str, float],
    cer_metadata: dict[str, Any],
    *,
    k_shortest_paths: int,
    candidate_cost_tolerance: float,
    agility_weight: float,
    agility_aggregation: str,
) -> dict[str, Any]:
    targets = [target]
    base_config = RouteRecommendationConfig(algorithm="dijkstra", route_selection="lowest_cost")
    base = recommender.recommend(graph, origin, targets, config=base_config)
    cer_config = RouteRecommendationConfig(
        algorithm="dijkstra",
        route_selection="cer_weighted",
        centrality_type="rerouting",
        rerouting_enabled=True,
        rerouting_centrality_by_node=cer_scores,
        rerouting_metadata=cer_metadata,
        agility_weight=agility_weight,
        agility_aggregation=agility_aggregation,
    )
    cer_cost = recommender.recommend(graph, origin, targets, config=cer_config)
    adjusted = recommender._cer_adjusted_graph(graph, cer_config, "weight")
    yen_config = RouteRecommendationConfig(
        algorithm="yen_ksp",
        route_selection="cer_agility_yen",
        centrality_type="rerouting",
        rerouting_enabled=True,
        rerouting_centrality_by_node=cer_scores,
        rerouting_metadata=cer_metadata,
        k_shortest_paths=max(1, int(k_shortest_paths)),
        candidate_cost_tolerance=max(0.0, float(candidate_cost_tolerance)),
        agility_weight=agility_weight,
        agility_aggregation=agility_aggregation,
    )
    candidates = recommender._k_shortest_candidates(graph, origin, targets, yen_config.k_shortest_paths, "weight")
    eligible = recommender._within_cost_tolerance(candidates, yen_config.candidate_cost_tolerance) if candidates else []
    if eligible:
        recommender._annotate_candidates(graph, eligible, yen_config, targets, "weight")
    selected_yen = recommender._select_advanced_candidate(eligible, yen_config) if eligible else None
    candidate_rows = [_candidate_payload(candidate, f"P{index + 1}", index) for index, candidate in enumerate(candidates)]
    eligible_keys = {tuple(candidate.node_sequence) for candidate in eligible}
    selected_yen_key = tuple(selected_yen.node_sequence) if selected_yen else None
    for row in candidate_rows:
        key = tuple(row["path"])
        row["eligible"] = key in eligible_keys
        row["selected"] = key == selected_yen_key
    return {
        "inputs": {
            "origin": origin,
            "target": target,
            "mobilityProfile": profile.id if profile else None,
            "kShortestPaths": yen_config.k_shortest_paths,
            "candidateCostTolerance": yen_config.candidate_cost_tolerance,
            "agilityWeight": agility_weight,
            "agilityAggregation": agility_aggregation,
        },
        "policyLabels": {
            "lowest_cost": "Minimum Time",
            "cer_weighted": "CER-Cost",
            "cer_agility_yen": "CER-Agility",
        },
        "results": [
            _route_payload(base, "lowest_cost", "Minimum Time", POLICY_COLORS["lowest_cost"]),
            _route_payload(cer_cost, "cer_weighted", "CER-Cost", POLICY_COLORS["cer_weighted"]),
            _route_payload(selected_yen, "cer_agility_yen", "CER-Agility", POLICY_COLORS["cer_agility_yen"]),
        ],
        "cerCostAdjustedEdges": _adjusted_edge_payload(graph, adjusted),
        "yenCandidates": candidate_rows,
    }


def _route_payload(candidate: RouteCandidate | None, policy_id: str, label: str, color: str) -> dict[str, Any]:
    if candidate is None:
        return {"policyId": policy_id, "label": label, "color": color, "path": [], "reachable": False}
    metrics = dict(candidate.metrics or {})
    return {
        "policyId": policy_id,
        "label": label,
        "color": color,
        "path": list(candidate.node_sequence),
        "destination": candidate.destination,
        "reachable": True,
        "cost": round(float(candidate.total_cost), 6),
        "metrics": metrics,
    }


def _candidate_payload(candidate: RouteCandidate, label: str, index: int) -> dict[str, Any]:
    palette = ["#2563eb", "#f59e0b", "#16a34a", "#9333ea", "#0f766e", "#ef4444", "#64748b", "#84cc16"]
    return {
        "id": label,
        "color": palette[index % len(palette)],
        "path": list(candidate.node_sequence),
        "destination": candidate.destination,
        "cost": round(float(candidate.total_cost), 6),
        "metrics": dict(candidate.metrics or {}),
        "eligible": False,
        "selected": False,
    }


def _adjusted_edge_payload(base_graph: Any, adjusted_graph: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, target, data in adjusted_graph.edges(data=True):
        base_data = base_graph.get_edge_data(source, target) or {}
        base_weight = float(base_data.get("weight", data.get("weight", 1.0)))
        adjusted_weight = float(data.get("weight", base_weight))
        penalty = float(data.get("cerPenalty", max(0.0, adjusted_weight - base_weight)))
        rows.append(
            {
                "source": str(source),
                "target": str(target),
                "baseCost": round(base_weight, 6),
                "cerPenalty": round(penalty, 6),
                "adjustedCost": round(adjusted_weight, 6),
                "cerNodeScore": round(float(data.get("cerNodeScore", 0.0)), 6),
            }
        )
    rows.sort(key=lambda item: (-item["cerPenalty"], item["source"], item["target"]))
    return rows


def _cer_profile_breakdown(payload: dict[str, Any], weights: dict[str, float]) -> dict[str, Any]:
    breakdown: dict[str, Any] = {}
    for node, node_payload in (payload.get("nodes") or {}).items():
        total = 0.0
        profiles: dict[str, Any] = {}
        for target_payload in (node_payload.get("targets") or {}).values():
            if target_payload.get("skippedSelf") or target_payload.get("unreachable"):
                continue
            for label, stats in (target_payload.get("profiles") or {}).items():
                distinct = float((stats or {}).get("distinctRoutes") or 0.0)
                weight = float(weights.get(str(label), 1.0))
                profiles[str(label)] = {
                    "distinctRoutes": distinct,
                    "weight": weight,
                    "weightedContribution": round(distinct * weight, 6),
                }
                total += distinct * weight
        breakdown[str(node)] = {"score": round(total, 6), "profiles": profiles}
    return breakdown


def _all_nodes_cer_payload(cer_scores: dict[str, float], profile_breakdown: dict[str, Any], topology: EvacTopology) -> list[dict[str, Any]]:
    score_payload = _score_payload(cer_scores)
    rows = []
    for node_id in sorted(score_payload):
        score_info = score_payload[node_id]
        node_data = topology.graph.nodes[node_id] if node_id in topology.graph else {}
        rows.append(
            {
                "node": node_id,
                "level": topology.node_level(node_id),
                "category": node_data.get("category"),
                "isExit": bool(node_data.get("isExit")),
                "score": score_info["score"],
                "normalized": score_info["normalized"],
                "profiles": (profile_breakdown.get(node_id) or {}).get("profiles", {}),
            }
        )
    rows.sort(key=lambda item: (-float(item["score"]), str(item["node"])))
    return rows


def _score_payload(scores: dict[str, float]) -> dict[str, Any]:
    max_score = max(scores.values(), default=0.0)
    return {
        node: {
            "score": round(float(score), 6),
            "normalized": round(float(score) / max_score, 6) if max_score > 0 else 0.0,
        }
        for node, score in scores.items()
    }


def _resolve_profile(scenario: ScenarioDefinition, profile_id: str | None) -> MobilityProfile | None:
    if profile_id and profile_id in scenario.mobility_profiles:
        return scenario.mobility_profiles[profile_id]
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
    raise ValueError("Policy explainer target is required because the scenario has no exit candidate.")


def _structural_routing_config(scenario: ScenarioDefinition) -> dict[str, Any]:
    routing_config = dict(scenario.physics)
    routing_config.update(scenario.routing)
    routing_config.update({"useHazardRisk": False, "useBeaconRisk": False, "useCongestion": False})
    return routing_config


def _configured_profile_weights(scenario: ScenarioDefinition) -> dict[str, float]:
    recommendation = (scenario.routing.get("routeRecommendation") or {})
    return _normal_profile_weights(recommendation.get("reroutingProfileWeights") or {})


def _normal_profile_weights(raw: dict[str, Any]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for key, value in dict(raw or {}).items():
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed < 0.0:
            continue
        label = str(key).strip()
        if not label:
            continue
        if not label.startswith("("):
            label = f"({label})"
        weights[label] = parsed
    return weights


def _slug(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    return re.sub(r"_+", "_", cleaned).strip("._-") or "item"


def _policy_animation_html(payload: dict[str, Any], mode: str) -> str:
    return (
        _POLICY_ANIMATION_HTML.replace("__POLICY_PAYLOAD__", json.dumps(payload, ensure_ascii=True))
        .replace("__POLICY_MODE__", json.dumps(mode, ensure_ascii=True))
    )


_POLICY_ANIMATION_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>CER policy animation</title>
<style>
:root { color-scheme: light; font-family: Inter, Segoe UI, system-ui, sans-serif; }
body { margin:0; background:#f6f8fb; color:#111827; }
main { display:grid; grid-template-columns: 330px 1fr; min-height:100vh; }
aside { background:#fff; border-right:1px solid #d7dee8; padding:16px; overflow:auto; }
section { padding:18px; display:grid; grid-template-rows:auto minmax(540px, 1fr) auto; gap:12px; }
h1 { margin:0 0 8px; font-size:22px; }
h2 { margin:0 0 6px; font-size:22px; }
p { margin:6px 0; line-height:1.45; }
button { border:1px solid #cbd5e1; background:#fff; padding:8px 10px; border-radius:7px; cursor:pointer; text-align:left; }
button.active { background:#e0f2fe; border-color:#0284c7; }
.timeline { display:grid; gap:8px; margin:12px 0; }
.note { background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:10px; font-size:13px; }
.metric { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr)); gap:8px; }
.metric span, .card { background:#fff; border:1px solid #d7dee8; border-radius:8px; padding:9px; }
.metric b { color:#475569; font-size:12px; font-weight:600; }
.layout { display:grid; grid-template-columns:minmax(560px, 1fr) 350px; gap:12px; min-height:540px; }
svg { width:100%; height:100%; min-height:540px; background:#fff; border:1px solid #d7dee8; border-radius:8px; }
.side { display:grid; gap:10px; align-content:start; }
.formula { background:#eef2ff; border:1px solid #c7d2fe; border-radius:8px; padding:12px; font-family:Consolas, monospace; font-size:16px; }
.edge-base { stroke:#cbd5e1; stroke-width:2; opacity:.85; }
.edge-penalty { stroke:#ef4444; stroke-width:5; opacity:.6; stroke-linecap:round; }
.route { fill:none; stroke-width:6; stroke-linecap:round; stroke-linejoin:round; opacity:.9; }
.node { stroke:#fff; stroke-width:1.5; }
.node-label { font-size:11px; fill:#0f172a; paint-order:stroke; stroke:#fff; stroke-width:3; }
.route-label { font-size:12px; font-weight:700; fill:#111827; paint-order:stroke; stroke:#fff; stroke-width:4; }
table { width:100%; border-collapse:collapse; background:#fff; border:1px solid #d7dee8; border-radius:8px; overflow:hidden; }
th, td { padding:7px; border-bottom:1px solid #e5e7eb; font-size:12px; text-align:left; }
th { background:#f1f5f9; color:#334155; }
tr.selected { outline:3px solid #16a34a; outline-offset:-3px; }
tr.dim { opacity:.45; }
.swatch { display:inline-block; width:12px; height:12px; border-radius:999px; margin-right:6px; vertical-align:-1px; }
</style>
</head>
<body>
<main>
<aside>
<h1 id="pageTitle"></h1>
<p id="meta"></p>
<div class="note" id="modeNote"></div>
<div class="timeline" id="timeline"></div>
<button id="play">Play</button>
<div class="card">
  <b>Perfiles CER usados</b>
  <pre id="profiles"></pre>
</div>
</aside>
<section>
<div>
<h2 id="frameTitle"></h2>
<p id="frameText"></p>
<div class="metric" id="metrics"></div>
</div>
<div class="layout">
  <svg id="graph"></svg>
  <div class="side" id="side"></div>
</div>
<div id="bottom"></div>
</section>
</main>
<script>
const payload = __POLICY_PAYLOAD__;
const mode = __POLICY_MODE__;
const graph = payload.graph || {};
const nodes = graph.nodes || [];
const edges = graph.edges || [];
const cerScores = payload.cer?.scores || {};
const allNodes = payload.cer?.allNodes || [];
const policies = payload.policies || {};
const routeById = new Map((policies.results || []).map(route => [route.policyId, route]));
const svg = document.getElementById("graph");
const timeline = document.getElementById("timeline");
const frameTitle = document.getElementById("frameTitle");
const frameText = document.getElementById("frameText");
const metrics = document.getElementById("metrics");
const side = document.getElementById("side");
const bottom = document.getElementById("bottom");
const ns = "http://www.w3.org/2000/svg";
let active = 0;
const frames = mode === "cer_cost" ? costFrames() : agilityFrames();
document.getElementById("pageTitle").textContent = mode === "cer_cost" ? "CER-Cost" : "CER-Agility";
document.getElementById("meta").textContent = `${payload.scenarioId} | ${payload.origin} -> ${payload.target}`;
document.getElementById("profiles").textContent = `${payload.cer.failureProfiles.join(", ")}\\n${JSON.stringify(payload.cer.profileWeights, null, 2)}`;
document.getElementById("modeNote").textContent = mode === "cer_cost"
  ? "CER-Cost modifica los pesos del grafo antes de resolver la ruta minima."
  : "CER-Agility genera candidatas con Yen y usa CER como medida de agilidad para elegir.";
frames.forEach((frame, index) => {
  const button = document.createElement("button");
  button.textContent = `${index + 1}. ${frame.short}`;
  button.onclick = () => show(index);
  timeline.appendChild(button);
});
document.getElementById("play").onclick = async () => {
  for (let index = 0; index < frames.length; index++) {
    show(index);
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
};
function costFrames() {
  return [
    {short:"grafo base", title:"1. Grafo operativo", text:"Se parte del grafo multilevel_transfer_to_transfer ponderado por tiempo base.", routes:[], showCer:false},
    {short:"CER nodos", title:"2. CER de todos los nodos", text:"Cada nodo muestra su CER agregada con perfiles basicos (1), (1,1), (1,1,1).", routes:[], showCer:true, table:"nodes"},
    {short:"formula", title:"3. Penalizacion inversa", text:"Los nodos con baja CER encarecen la entrada a ese nodo.", routes:[], showCer:true, formula:true},
    {short:"pesos ajustados", title:"4. Pesos ajustados por CER", text:"Las aristas rojas son las que reciben mas penalizacion por conducir a nodos con menor CER.", routes:[], showCer:true, penalties:true, table:"penalties"},
    {short:"ruta minima", title:"5. Ruta minima temporal", text:"Referencia de menor coste sin penalizacion CER.", routes:[routeById.get("lowest_cost")], showCer:true, table:"policies"},
    {short:"ruta CER-Cost", title:"6. Ruta seleccionada por CER-Cost", text:"Dijkstra minimiza el coste ajustado: tiempo + penalizacion inversa CER.", routes:[routeById.get("cer_weighted")], showCer:true, formula:true, table:"policies"},
  ];
}
function agilityFrames() {
  const candidates = policies.yenCandidates || [];
  const frames = [
    {short:"grafo base", title:"1. Grafo operativo", text:"Se parte del mismo grafo y de la misma CER.", routes:[], showCer:false},
    {short:"CER nodos", title:"2. CER de todos los nodos", text:"CER no modifica todavia el grafo; solo mide capacidad de reencaminamiento.", routes:[], showCer:true, table:"nodes"},
  ];
  candidates.forEach((candidate, index) => {
    frames.push({short:`candidata ${candidate.id}`, title:`${3 + index}. Yen genera ${candidate.id}`, text:`Ruta candidata ${candidate.id}. Coste=${fmt(candidate.cost)}.`, candidateRoutes:[candidate], showCer:true, table:"candidates", activeCandidate:candidate.id});
  });
  frames.push({short:"filtrado", title:"Filtrado por tolerancia", text:"Se descartan candidatas cuyo coste excede el margen frente a la mas barata.", candidateRoutes:candidates, showCer:true, table:"candidates", filter:true});
  frames.push({short:"agilidad CER", title:"Evaluacion de agilidad CER", text:"Para cada candidata valida se resume la CER de sus nodos intermedios.", candidateRoutes:candidates, showCer:true, table:"candidates"});
  frames.push({short:"ruta elegida", title:"Ruta seleccionada por CER-Agility", text:"La politica elige la candidata con mayor agilidad CER, usando robustez y coste como desempate.", candidateRoutes:candidates.filter(item => item.selected), showCer:true, table:"candidates"});
  return frames;
}
function show(index) {
  active = index;
  const frame = frames[index];
  [...timeline.children].forEach((button, i) => button.classList.toggle("active", i === index));
  frameTitle.textContent = frame.title;
  frameText.textContent = frame.text;
  metrics.innerHTML = metric("origen", payload.origin) + metric("salida", payload.target) + metric("perfil", payload.profileId || "-");
  draw(frame);
  side.innerHTML = sidePanel(frame);
  bottom.innerHTML = tableFor(frame);
}
function draw(frame) {
  svg.textContent = "";
  const visible = nodes.filter(node => !payload.level || node.level === payload.level);
  const byId = new Map(nodes.map(node => [node.id, node]));
  const project = projector(visible);
  for (const edge of edges) {
    const a = byId.get(edge.source), b = byId.get(edge.target);
    if (!a || !b || !visible.includes(a) || !visible.includes(b)) continue;
    line(project(a), project(b), "edge-base");
  }
  if (frame.penalties) drawPenaltyEdges(byId, project, visible);
  for (const route of frame.candidateRoutes || []) drawRoute(route.path, route.color, byId, project, route.id);
  for (const route of frame.routes || []) if (route) drawRoute(route.path, route.color, byId, project, route.label);
  for (const node of visible) drawNode(node, project, !!frame.showCer);
}
function drawPenaltyEdges(byId, project, visible) {
  const top = [...(policies.cerCostAdjustedEdges || [])].filter(edge => edge.cerPenalty > 0).slice(0, 14);
  for (const edge of top) {
    const a = byId.get(edge.source), b = byId.get(edge.target);
    if (!a || !b || !visible.includes(a) || !visible.includes(b)) continue;
    line(project(a), project(b), "edge-penalty");
  }
}
function sidePanel(frame) {
  let html = "";
  if (frame.formula) {
    html += `<div class="formula">coste'(u,v)<br>= tiempo(u,v)<br>+ lambda * (1 - CERnorm(v))</div>`;
  }
  html += `<div class="card"><b>Escala CER</b><p>Claro = CER baja. Intenso = CER alta. El numero junto al nodo es la CER ponderada.</p></div>`;
  if (mode === "cer_agility") {
    html += `<div class="card"><b>Yen</b><p>Genera k rutas simples. CER se aplica despues, como criterio de seleccion.</p></div>`;
  }
  return html;
}
function tableFor(frame) {
  if (frame.table === "nodes") return nodeTable();
  if (frame.table === "penalties") return penaltyTable();
  if (frame.table === "candidates") return candidateTable(frame);
  if (frame.table === "policies") return policyTable();
  return "";
}
function metric(label, value) {
  return `<span><b>${label}</b><br>${fmt(value)}</span>`;
}
function fmt(value) {
  if (value == null) return "-";
  if (typeof value === "number") return value.toFixed(3);
  return String(value);
}
function projector(items) {
  const xs = items.map(n => n.x), ys = items.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const box = svg.getBoundingClientRect();
  const w = box.width || 900, h = box.height || 560, pad = 35;
  const scale = Math.min((w - 2 * pad) / Math.max(maxX - minX, 1), (h - 2 * pad) / Math.max(maxY - minY, 1));
  return node => [pad + (node.x - minX) * scale, h - pad - (node.y - minY) * scale];
}
function line(a, b, cls) {
  const el = document.createElementNS(ns, "line");
  el.setAttribute("x1", a[0]); el.setAttribute("y1", a[1]);
  el.setAttribute("x2", b[0]); el.setAttribute("y2", b[1]);
  el.setAttribute("class", cls);
  svg.appendChild(el);
}
function drawRoute(path, color, byId, project, label) {
  if (!path || path.length < 2) return;
  const pts = path.map(id => byId.get(id)).filter(Boolean).map(project);
  if (pts.length < 2) return;
  const poly = document.createElementNS(ns, "polyline");
  poly.setAttribute("points", pts.map(p => p.join(",")).join(" "));
  poly.setAttribute("class", "route");
  poly.setAttribute("stroke", color || "#111827");
  svg.appendChild(poly);
  const mid = pts[Math.floor(pts.length / 2)];
  const text = document.createElementNS(ns, "text");
  text.setAttribute("x", mid[0] + 8); text.setAttribute("y", mid[1] - 8);
  text.setAttribute("class", "route-label");
  text.textContent = label || "";
  svg.appendChild(text);
}
function drawNode(node, project, showCer) {
  const [x, y] = project(node);
  const score = cerScores[node.id]?.score || 0;
  const normalized = cerScores[node.id]?.normalized || 0;
  const circle = document.createElementNS(ns, "circle");
  circle.setAttribute("cx", x); circle.setAttribute("cy", y);
  circle.setAttribute("r", node.id === payload.origin || node.id === payload.target ? 8 : 5);
  circle.setAttribute("class", "node");
  circle.setAttribute("fill", showCer ? cerColor(normalized) : "#94a3b8");
  svg.appendChild(circle);
  if (showCer) {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", x + 8); text.setAttribute("y", y - 8);
    text.setAttribute("class", "node-label");
    text.textContent = Number(score).toFixed(1);
    svg.appendChild(text);
  }
}
function cerColor(t) {
  t = Math.max(0, Math.min(1, t));
  const hue = 210 - 90 * t;
  const light = 91 - 45 * t;
  return `hsl(${hue} 85% ${light}%)`;
}
function nodeTable() {
  return `<table><thead><tr><th>Nodo</th><th>Nivel</th><th>CER</th><th>Norm</th><th>(1)</th><th>(1,1)</th><th>(1,1,1)</th></tr></thead><tbody>` +
    allNodes.map(row => `<tr><td>${row.node}</td><td>${row.level || "-"}</td><td>${fmt(row.score)}</td><td>${fmt(row.normalized)}</td><td>${profileValue(row, "(1)")}</td><td>${profileValue(row, "(1,1)")}</td><td>${profileValue(row, "(1,1,1)")}</td></tr>`).join("") +
    `</tbody></table>`;
}
function profileValue(row, label) {
  return fmt(row.profiles?.[label]?.distinctRoutes ?? 0);
}
function penaltyTable() {
  const rows = (policies.cerCostAdjustedEdges || []).filter(row => row.cerPenalty > 0).slice(0, 16);
  return `<table><thead><tr><th>Arista</th><th>Base</th><th>Penalizacion CER</th><th>Ajustado</th><th>CER nodo destino</th></tr></thead><tbody>` +
    rows.map(row => `<tr><td>${row.source} -> ${row.target}</td><td>${fmt(row.baseCost)}</td><td>${fmt(row.cerPenalty)}</td><td>${fmt(row.adjustedCost)}</td><td>${fmt(row.cerNodeScore)}</td></tr>`).join("") +
    `</tbody></table>`;
}
function policyTable() {
  return `<table><thead><tr><th>Politica</th><th>Ruta</th><th>Coste</th><th>Agilidad CER</th></tr></thead><tbody>` +
    (policies.results || []).map(route => `<tr><td><span class="swatch" style="background:${route.color}"></span>${route.label}</td><td>${(route.path || []).join(" -> ")}</td><td>${fmt(route.cost)}</td><td>${fmt(route.metrics?.reroutingAgility ?? route.metrics?.agility)}</td></tr>`).join("") +
    `</tbody></table>`;
}
function candidateTable(frame) {
  const rows = policies.yenCandidates || [];
  return `<table><thead><tr><th>Ruta</th><th>Coste</th><th>Agilidad CER</th><th>Robustez</th><th>Estado</th><th>Secuencia</th></tr></thead><tbody>` +
    rows.map(row => {
      const dim = frame.filter && !row.eligible ? "dim" : "";
      const active = frame.activeCandidate === row.id || row.selected ? "selected" : "";
      return `<tr class="${dim} ${active}"><td><span class="swatch" style="background:${row.color}"></span>${row.id}</td><td>${fmt(row.cost)}</td><td>${fmt(row.metrics?.agility)}</td><td>${fmt(row.metrics?.robustness)}</td><td>${row.selected ? "elegida" : row.eligible ? "valida" : "filtrada"}</td><td>${row.path.join(" -> ")}</td></tr>`;
    }).join("") +
    `</tbody></table>`;
}
show(0);
</script>
</body>
</html>
"""


_POLICY_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>CER routing policy explainer</title>
<style>
:root { color-scheme: light; font-family: Inter, Segoe UI, system-ui, sans-serif; }
body { margin:0; background:#f6f8fb; color:#111827; }
main { display:grid; grid-template-columns: 340px 1fr; min-height:100vh; }
aside { background:#fff; border-right:1px solid #d7dee8; padding:16px; overflow:auto; }
section { padding:18px; display:grid; grid-template-rows:auto minmax(520px, 1fr) auto; gap:12px; }
h1 { margin:0 0 8px; font-size:22px; }
h2 { margin:0 0 6px; font-size:20px; }
p { line-height:1.45; }
button { border:1px solid #cbd5e1; background:#fff; padding:8px 10px; border-radius:7px; cursor:pointer; text-align:left; }
button.active { background:#e0f2fe; border-color:#0284c7; }
.steps { display:grid; gap:8px; margin:12px 0; }
.note { background:#fff7ed; border:1px solid #fed7aa; border-radius:8px; padding:10px; font-size:13px; }
.metric { display:grid; grid-template-columns:repeat(auto-fit, minmax(145px, 1fr)); gap:8px; }
.metric span, .card { background:#fff; border:1px solid #d7dee8; border-radius:8px; padding:9px; }
.metric b { color:#475569; font-size:12px; font-weight:600; }
svg { width:100%; height:100%; min-height:520px; background:#fff; border:1px solid #d7dee8; border-radius:8px; }
.edge-base { stroke:#cbd5e1; stroke-width:2; opacity:.9; }
.route { fill:none; stroke-width:6; stroke-linecap:round; stroke-linejoin:round; opacity:.9; }
.node { stroke:#fff; stroke-width:1.5; }
.node-label { font-size:11px; fill:#0f172a; paint-order:stroke; stroke:#fff; stroke-width:3; }
.route-label { font-size:12px; font-weight:700; fill:#111827; paint-order:stroke; stroke:#fff; stroke-width:4; }
table { width:100%; border-collapse:collapse; background:#fff; border:1px solid #d7dee8; border-radius:8px; overflow:hidden; }
th, td { padding:8px; border-bottom:1px solid #e5e7eb; font-size:13px; text-align:left; }
th { background:#f1f5f9; color:#334155; }
tr.selected { outline:3px solid #16a34a; outline-offset:-3px; }
.swatch { display:inline-block; width:12px; height:12px; border-radius:999px; margin-right:6px; vertical-align:-1px; }
.hidden { display:none; }
</style>
</head>
<body>
<main>
<aside>
<h1>CER policies</h1>
<p id="meta"></p>
<div class="note">
CER = Centralidad de Evacuacion por Reencaminamiento. La R es reencaminamiento; la escala muestra capacidad de recuperacion ante fallos.
</div>
<div class="steps">
  <button data-step="cer" class="active">1. CER calculada</button>
  <button data-step="cost">2. CER-Cost</button>
  <button data-step="agility">3. CER-Agility</button>
  <button data-step="compare">4. Comparacion</button>
</div>
<button id="play">Play</button>
<div class="card">
  <b>Pesos por perfil</b>
  <pre id="profileWeights"></pre>
</div>
</aside>
<section>
<div>
<h2 id="title"></h2>
<p id="description"></p>
<div class="metric" id="metrics"></div>
</div>
<svg id="graph"></svg>
<div id="tables"></div>
</section>
</main>
<script>
const payload = __POLICY_PAYLOAD__;
const graph = payload.graph || {};
const nodes = graph.nodes || [];
const edges = graph.edges || [];
const cerScores = payload.cer?.scores || {};
const policies = payload.policies || {};
const svg = document.getElementById("graph");
const title = document.getElementById("title");
const description = document.getElementById("description");
const metrics = document.getElementById("metrics");
const tables = document.getElementById("tables");
const ns = "http://www.w3.org/2000/svg";
const routeById = new Map((policies.results || []).map(route => [route.policyId, route]));
document.getElementById("meta").textContent = `${payload.scenarioId} | ${payload.origin} -> ${payload.target}`;
document.getElementById("profileWeights").textContent = JSON.stringify(payload.cer?.profileWeights || {}, null, 2);
document.querySelectorAll("button[data-step]").forEach(button => button.onclick = () => show(button.dataset.step));
document.getElementById("play").onclick = async () => {
  for (const id of ["cer", "cost", "agility", "compare"]) {
    show(id);
    await new Promise(resolve => setTimeout(resolve, 1600));
  }
};
function show(step) {
  document.querySelectorAll("button[data-step]").forEach(button => button.classList.toggle("active", button.dataset.step === step));
  if (step === "cer") return renderCer();
  if (step === "cost") return renderCost();
  if (step === "agility") return renderAgility();
  return renderCompare();
}
function renderCer() {
  title.textContent = "CER ya calculada";
  description.textContent = "Los nodos se colorean por CER normalizada. El numero muestra el score agregado con pesos por perfil.";
  metrics.innerHTML = [
    metric("tau CER", payload.cer.costTolerance),
    metric("perfiles", payload.cer.failureProfiles.join(", ")),
    metric("grafo", payload.graphView),
  ].join("");
  drawGraph({showCer:true, routes:[]});
  tables.innerHTML = nodeTable();
}
function renderCost() {
  const route = routeById.get("cer_weighted") || {};
  title.textContent = "CER-Cost";
  description.textContent = "CER modifica el coste de las aristas mediante penalizacion inversa: coste' = tiempo + lambda * (1 - CERnorm(destino)).";
  metrics.innerHTML = [
    metric("lambda agility", policies.inputs.agilityWeight),
    metric("coste ajustado", route.cost),
    metric("CER medio ruta", route.metrics?.reroutingAgility ?? route.metrics?.agility),
  ].join("");
  drawGraph({showCer:true, routes:[route]});
  tables.innerHTML = policyTable(["lowest_cost", "cer_weighted"]);
}
function renderAgility() {
  title.textContent = "CER-Agility";
  description.textContent = "Yen genera k rutas candidatas. Despues CER se usa como medida de agilidad para elegir entre rutas razonables.";
  metrics.innerHTML = [
    metric("k rutas", policies.inputs.kShortestPaths),
    metric("tolerancia candidatas", policies.inputs.candidateCostTolerance),
    metric("agregacion", policies.inputs.agilityAggregation),
  ].join("");
  drawGraph({showCer:true, candidateRoutes: policies.yenCandidates || []});
  tables.innerHTML = candidateTable();
}
function renderCompare() {
  title.textContent = "Comparacion de politicas";
  description.textContent = "Mismo grafo y misma CER; cambia la politica de integracion: coste ajustado frente a seleccion posterior sobre candidatas.";
  metrics.innerHTML = [
    metric("origen", payload.origin),
    metric("salida", payload.target),
    metric("perfil", payload.profileId || "-"),
  ].join("");
  drawGraph({showCer:true, routes: policies.results || []});
  tables.innerHTML = policyTable(["lowest_cost", "cer_weighted", "cer_agility_yen"]);
}
function metric(label, value) {
  return `<span><b>${label}</b><br>${format(value)}</span>`;
}
function format(value) {
  if (value == null) return "-";
  if (typeof value === "number") return value.toFixed(3);
  return String(value);
}
function drawGraph(options) {
  svg.textContent = "";
  const visible = nodes.filter(node => !payload.level || node.level === payload.level);
  const byId = new Map(nodes.map(node => [node.id, node]));
  const project = projector(visible);
  for (const edge of edges) {
    const a = byId.get(edge.source), b = byId.get(edge.target);
    if (!a || !b || !visible.includes(a) || !visible.includes(b)) continue;
    line(project(a), project(b), "edge-base");
  }
  for (const route of options.candidateRoutes || []) drawRoute(route.path, route.color, byId, project, route.id);
  for (const route of options.routes || []) drawRoute(route.path, route.color, byId, project, route.label);
  for (const node of visible) drawNode(node, project, options.showCer);
}
function projector(items) {
  const xs = items.map(n => n.x), ys = items.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const box = svg.getBoundingClientRect();
  const w = box.width || 900, h = box.height || 560, pad = 35;
  const sx = (w - 2 * pad) / Math.max(maxX - minX, 1);
  const sy = (h - 2 * pad) / Math.max(maxY - minY, 1);
  const scale = Math.min(sx, sy);
  return node => [pad + (node.x - minX) * scale, h - pad - (node.y - minY) * scale];
}
function line(a, b, cls, color) {
  const el = document.createElementNS(ns, "line");
  el.setAttribute("x1", a[0]); el.setAttribute("y1", a[1]);
  el.setAttribute("x2", b[0]); el.setAttribute("y2", b[1]);
  el.setAttribute("class", cls);
  if (color) el.setAttribute("stroke", color);
  svg.appendChild(el);
}
function drawRoute(path, color, byId, project, label) {
  if (!path || path.length < 2) return;
  const pts = path.map(id => byId.get(id)).filter(Boolean).map(project);
  if (pts.length < 2) return;
  const poly = document.createElementNS(ns, "polyline");
  poly.setAttribute("points", pts.map(p => p.join(",")).join(" "));
  poly.setAttribute("class", "route");
  poly.setAttribute("stroke", color || "#111827");
  svg.appendChild(poly);
  const mid = pts[Math.floor(pts.length / 2)];
  const text = document.createElementNS(ns, "text");
  text.setAttribute("x", mid[0] + 8); text.setAttribute("y", mid[1] - 8);
  text.setAttribute("class", "route-label"); text.textContent = label || "";
  svg.appendChild(text);
}
function drawNode(node, project, showCer) {
  const [x, y] = project(node);
  const score = cerScores[node.id]?.score || 0;
  const normalized = cerScores[node.id]?.normalized || 0;
  const circle = document.createElementNS(ns, "circle");
  circle.setAttribute("cx", x); circle.setAttribute("cy", y);
  circle.setAttribute("r", node.id === payload.origin || node.id === payload.target ? 8 : 5);
  circle.setAttribute("class", "node");
  circle.setAttribute("fill", showCer ? cerColor(normalized) : "#94a3b8");
  svg.appendChild(circle);
  if (showCer && score > 0) {
    const text = document.createElementNS(ns, "text");
    text.setAttribute("x", x + 8); text.setAttribute("y", y - 8);
    text.setAttribute("class", "node-label"); text.textContent = score.toFixed(1);
    svg.appendChild(text);
  }
}
function cerColor(t) {
  t = Math.max(0, Math.min(1, t));
  const hue = 210 - 90 * t;
  const light = 88 - 42 * t;
  return `hsl(${hue} 85% ${light}%)`;
}
function policyTable(ids) {
  const rows = ids.map(id => routeById.get(id)).filter(Boolean);
  return `<table><thead><tr><th>Politica</th><th>Ruta</th><th>Coste</th><th>Agilidad CER</th><th>Detalle</th></tr></thead><tbody>` +
    rows.map(route => `<tr><td><span class="swatch" style="background:${route.color}"></span>${route.label}</td><td>${route.path.join(" -> ")}</td><td>${format(route.cost)}</td><td>${format(route.metrics?.reroutingAgility ?? route.metrics?.agility)}</td><td>${route.reachable ? "alcanzable" : "sin ruta"}</td></tr>`).join("") +
    `</tbody></table>`;
}
function candidateTable() {
  const rows = policies.yenCandidates || [];
  return `<table><thead><tr><th>Ruta</th><th>Coste</th><th>Agilidad CER</th><th>Robustez</th><th>Estado</th><th>Secuencia</th></tr></thead><tbody>` +
    rows.map(row => `<tr class="${row.selected ? "selected" : ""}"><td><span class="swatch" style="background:${row.color}"></span>${row.id}</td><td>${format(row.cost)}</td><td>${format(row.metrics?.agility)}</td><td>${format(row.metrics?.robustness)}</td><td>${row.selected ? "elegida" : row.eligible ? "valida" : "filtrada"}</td><td>${row.path.join(" -> ")}</td></tr>`).join("") +
    `</tbody></table>`;
}
function nodeTable() {
  const entries = Object.entries(cerScores).filter(([, value]) => value.score > 0).sort((a, b) => b[1].score - a[1].score).slice(0, 12);
  return `<table><thead><tr><th>Nodo</th><th>CER ponderada</th><th>Normalizada</th></tr></thead><tbody>` +
    entries.map(([node, value]) => `<tr><td>${node}</td><td>${format(value.score)}</td><td>${format(value.normalized)}</td></tr>`).join("") +
    `</tbody></table>`;
}
show("cer");
</script>
</body>
</html>
"""

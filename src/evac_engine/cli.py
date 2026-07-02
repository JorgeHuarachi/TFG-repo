"""Command line interface for EvacEngine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .application import ApplicationService
from .cer_export import default_cer_output_dir, export_cer_analysis
from .cer_tree import CERTreeConfig, default_cer_tree_output_dir, export_cer_tree_for_scenario
from .experiments import available_routing_presets, compare_routing_presets
from .loaders import load_project
from .overlays import BeaconSimulator
from .routing_policy_explainer import default_policy_output_dir, export_routing_policy_explainer
from .simulation import EvacuationModel
from .topology import EvacTopology
from .visualization import build_visualization_payload, save_result_gif, save_result_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.evac_engine", description="EvacEngine for Indoor Data Model scenarios")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate indoor/scenario inputs and derived topology")
    _add_project_args(validate)

    route = sub.add_parser("route", help="Plan one route")
    _add_project_args(route)
    route.add_argument("--origin", required=True)
    route.add_argument("--target", action="append", default=[])
    route.add_argument("--profile")
    route.add_argument("--origin-x", type=float)
    route.add_argument("--origin-y", type=float)
    route.add_argument("--origin-level")

    run = sub.add_parser("run", help="Run the simulation and write outputs")
    _add_project_args(run)
    _add_runtime_override_args(run)
    run.add_argument("--output-dir")
    run.add_argument("--gif", help="Optional GIF path to render after the run")
    run.add_argument("--html", help="Optional standalone HTML viewer path")
    run.add_argument("--level", help="Level to render in the optional GIF")
    run.add_argument("--fps", type=int, default=8)
    run.add_argument("--skip-geometry-qa", action="store_true", help="Skip expensive Shapely trajectory geometry checks")

    beacons = sub.add_parser("beacons", help="Evaluate beacon observations at one tick")
    _add_project_args(beacons)
    beacons.add_argument("--step", type=int, default=0)
    beacons.add_argument("--time-s", type=float, default=0.0)

    cer = sub.add_parser("cer", help="Export CER rerouting centrality debug visualizations")
    _add_project_args(cer)
    cer.add_argument("--origin", required=True, help="Origin CellSpace id/ref to explain")
    cer.add_argument("--target", help="Target exit CellSpace id/ref; defaults to first scenario destination")
    cer.add_argument("--profile", help="Mobility profile id; defaults to first group/agent profile")
    cer.add_argument("--output-dir", help="Output folder for cer_debug.json, PNG, GIF and HTML")
    cer.add_argument("--formats", default="json,png,html", help="Comma-separated: json,png,html,gif")
    cer.add_argument("--gif", action="store_true", help="Also export cer_explanation.gif")
    cer.add_argument("--level", help="Level to render in PNG/GIF")
    cer.add_argument("--fps", type=int, default=2)
    cer.add_argument("--max-frames", type=int, default=120, help="Maximum CER GIF frames; 0 means export every debug step")
    cer.add_argument("--failure-profiles", help='Failure profiles separated by semicolon, e.g. "1;1,1;1,2"')
    cer.add_argument("--cost-tolerance", type=float, help="CER tau tolerance; Cmax = C0 * (1 + tau)")
    cer.add_argument("--dynamic", action="store_true", help="Use dynamic snapshot with beacons/hazards at --step/--time-s")
    cer.add_argument("--step", type=int, default=0)
    cer.add_argument("--time-s", type=float, default=0.0)

    cer_tree = sub.add_parser("cer-tree", help="Audit CER as a bounded rerouting failure tree on weighted snapshots")
    _add_project_args(cer_tree)
    cer_tree.add_argument("--origin", action="append", default=[], help="Origin CellSpace id/ref. Repeat for several origins")
    cer_tree.add_argument("--all-origins", action="store_true", help="Evaluate every node in the weighted snapshot as origin")
    cer_tree.add_argument("--target", action="append", default=[], help="Target exit CellSpace id/ref. Defaults to scenario destination/exits")
    cer_tree.add_argument("--profile", action="append", default=[], help="Mobility profile id. Repeat for walking/rolling comparisons; defaults to all profiles")
    cer_tree.add_argument("--output-dir", help="Output folder for cer_tree JSON/CSV/HTML")
    cer_tree.add_argument("--formats", default="json,csv,html,visual-html", help="Comma-separated: json,csv,html,visual-html")
    cer_tree.add_argument("--tau", type=float, default=0.3, help="Fixed CER tolerance; Cmax = C0 * (1 + tau)")
    cer_tree.add_argument("--max-depth", type=int, default=2)
    cer_tree.add_argument("--max-k", type=int, default=2)
    cer_tree.add_argument("--max-total-failures", type=int, default=4)
    cer_tree.add_argument("--max-combinations", type=int, default=1000, help="Maximum combinations evaluated per state and k")
    cer_tree.add_argument("--max-runtime-ms", type=int, default=1000, help="Maximum runtime per mobility-profile run")
    cer_tree.add_argument("--max-distinct-routes", type=int)
    cer_tree.add_argument("--failure-profiles", help='Failure profiles separated by semicolon, e.g. "1;1,1;2;2,1"')
    cer_tree.add_argument("--failure-unit", choices=["resource", "arc", "undirected_pair", "undirected_connection", "cell"], default="resource")
    cer_tree.add_argument("--dynamic", action="store_true", help="Use dynamic hazards/beacons at --step/--time-s instead of structural snapshot")
    cer_tree.add_argument("--level", help="Level to render in visual-html output")
    cer_tree.add_argument("--visual-order", choices=["tree", "calculation"], default="tree", help="Order visual steps by CER branch tree or raw calculation order")
    cer_tree.add_argument("--visual-layout", choices=["wide", "standard"], default="wide", help="Use wide graph-first layout or the original compact layout")
    cer_tree.add_argument("--step", type=int, default=0)
    cer_tree.add_argument("--time-s", type=float, default=0.0)

    policy = sub.add_parser("explain-routing-policies", help="Export HTML/JSON explaining CER-Cost and CER-Agility policies")
    _add_project_args(policy)
    policy.add_argument("--origin", required=True, help="Origin CellSpace id/ref to explain")
    policy.add_argument("--target", help="Target exit CellSpace id/ref; defaults to first scenario destination")
    policy.add_argument("--profile", help="Mobility profile id; defaults to first group/agent profile")
    policy.add_argument("--output-dir", help="Output folder for policy comparison and per-policy HTML explainers")
    policy.add_argument("--formats", default="json,html", help="Comma-separated: json,html")
    policy.add_argument("--level", help="Level to render in the HTML")
    policy.add_argument("--failure-profiles", default="1;1,1;1,1,1", help='CER profiles separated by semicolon, e.g. "1;1,1;1,2"')
    policy.add_argument("--cost-tolerance", type=float, default=0.2, help="CER tau tolerance; Cmax = C0 * (1 + tau)")
    policy.add_argument("--profile-weights", default="(1)=1;(1,1)=0.6;(1,1,1)=0.3", help='Profile weights, e.g. "(1)=1;(1,1)=0.6"')
    policy.add_argument("--k-routes", type=int, default=6)
    policy.add_argument("--candidate-cost-tolerance", type=float, default=0.35)
    policy.add_argument("--agility-weight", type=float, default=0.35)
    policy.add_argument("--agility-aggregation", choices=["mean", "geometric"], default="mean")
    policy.add_argument("--max-combinations", type=int, default=500)
    policy.add_argument("--max-runtime-ms", type=int, default=30000)

    ui = sub.add_parser("ui", help="Open the desktop UI")
    ui.add_argument("--indoor")
    ui.add_argument("--scenario")

    workbench = sub.add_parser("workbench", help="Start the browser-based local workbench")
    workbench.add_argument("--host", default="127.0.0.1")
    workbench.add_argument("--port", type=int, default=8765)
    workbench.add_argument("--scenario")
    workbench.add_argument("--indoor", help="IndoorModel path; creates/uses a baseline scenario when --scenario is omitted")
    workbench.add_argument("--model", help="Model workspace name or path under models/; creates/uses evacuation/scenarios/baseline.json")
    workbench.add_argument("--library-root", help="Root scanned by the workbench library selectors")

    render = sub.add_parser("render", help="Run the simulation and render a GIF")
    _add_project_args(render)
    _add_runtime_override_args(render)
    render.add_argument("--gif", help="Output GIF path")
    render.add_argument("--html", help="Output standalone HTML viewer path")
    render.add_argument("--level", help="Level to render")
    render.add_argument("--fps", type=int, default=8)
    render.add_argument("--max-frames", type=int)
    render.add_argument("--skip-geometry-qa", action="store_true", help="Skip expensive Shapely trajectory geometry checks")

    compare = sub.add_parser("compare-routing", help="Run one scenario with multiple routing presets and compare metrics")
    _add_project_args(compare, scenario_required=False)
    _add_simulation_runtime_args(compare)
    compare.add_argument("--preset", action="append", default=[], help="Preset id to run; repeat for several presets")
    compare.add_argument("--presets", help="Comma-separated preset ids; appended after --preset values")
    compare.add_argument("--output-dir", default="outputs/routing_comparison")
    compare.add_argument("--list-presets", action="store_true", help="List built-in preset ids and exit")
    compare.add_argument("--no-run-outputs", action="store_true", help="Only write comparison files, not per-preset run manifests")
    compare.add_argument("--skip-plot", action="store_true", help="Skip comparison_plot.png generation")
    return parser


def _add_project_args(parser: argparse.ArgumentParser, *, scenario_required: bool = True) -> None:
    parser.add_argument("--scenario", required=scenario_required, help="Path to scenario_model.json")
    parser.add_argument("--indoor", help="Path to indoor_model.json; defaults to scenario.indoorModelRef.path")


def _add_simulation_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--time-step", type=float, help="Override simulationConfig.timeStepS")
    parser.add_argument("--max-steps", type=int, help="Override simulationConfig.maxSteps")
    parser.add_argument("--seed", type=int, help="Override simulationConfig.randomSeed")
    parser.add_argument("--first-group-count", type=int, help="Override the first population group count")


def _add_runtime_override_args(parser: argparse.ArgumentParser) -> None:
    _add_simulation_runtime_args(parser)
    parser.add_argument("--algorithm", choices=["dijkstra", "astar", "floyd_warshall", "yen_ksp", "robust_agility"], help="Override routing.algorithm")
    parser.add_argument("--cost-policy", choices=["minimum_travel_time"], help="Override routing.costPolicy")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ui":
        from .ui.desktop_app import run_desktop_app

        run_desktop_app(args.indoor, args.scenario)
        return 0
    if args.command == "workbench":
        if args.model and args.scenario:
            parser.error("workbench accepts --model or --scenario, not both")
        if args.model and args.indoor:
            parser.error("workbench accepts --model or --indoor, not both")
        from .web_app import run_workbench

        run_workbench(args.host, args.port, args.scenario, indoor_path=args.indoor, model_name=args.model, library_root=args.library_root)
        return 0
    if args.command == "validate":
        service = ApplicationService()
        print_json(service.validate(args.indoor, args.scenario))
        return 0
    if args.command == "route":
        service = ApplicationService()
        service.load(args.indoor, args.scenario)
        origin_position = None
        if args.origin_x is not None and args.origin_y is not None:
            origin_position = (args.origin_x, args.origin_y)
        print_json(service.plan_route(args.origin, args.target or None, args.profile, origin_position, args.origin_level))
        return 0
    if args.command == "run":
        service = ApplicationService()
        service.load(args.indoor, args.scenario)
        _apply_service_overrides(service, args)
        result = service.run(args.output_dir)
        gif_path = None
        html_path = None
        if args.gif:
            assert service.model is not None
            gif_path = save_result_gif(service.model.topology, result, args.gif, level=args.level, fps=args.fps)
        if args.html:
            assert service.model is not None
            html_path = save_result_html(service.model.topology, result, args.html, include_geometry_qa=not args.skip_geometry_qa)
        print_json(
            {
                "metrics": result.metrics,
                "qa": build_visualization_payload(service.model.topology, result, include_geometry_qa=not args.skip_geometry_qa)["qa"] if service.model else {},
                "outputDir": str(result.output_dir) if result.output_dir else None,
                "gif": str(gif_path) if gif_path else None,
                "html": str(html_path) if html_path else None,
            }
        )
        return 0
    if args.command == "render":
        indoor, scenario = load_project(args.indoor, args.scenario)
        _apply_scenario_overrides(scenario, args)
        model = EvacuationModel(indoor, scenario)
        result = model.run()
        gif_path = save_result_gif(model.topology, result, args.gif, level=args.level, fps=args.fps, max_frames=args.max_frames) if args.gif else None
        html_path = save_result_html(model.topology, result, args.html, include_geometry_qa=not args.skip_geometry_qa) if args.html else None
        print_json(
            {
                "metrics": result.metrics,
                "qa": build_visualization_payload(model.topology, result, include_geometry_qa=not args.skip_geometry_qa)["qa"],
                "gif": str(gif_path) if gif_path else None,
                "html": str(html_path) if html_path else None,
            }
        )
        return 0
    if args.command == "compare-routing":
        if args.list_presets:
            scenario_raw = None
            if args.scenario:
                _, scenario = load_project(args.indoor, args.scenario)
                scenario_raw = scenario.raw
            print_json({"presets": available_routing_presets(scenario_raw)})
            return 0
        if not args.scenario:
            parser.error("compare-routing requires --scenario unless --list-presets is used")
        presets = list(args.preset or [])
        if args.presets:
            presets.extend(item.strip() for item in args.presets.split(",") if item.strip())
        summary = compare_routing_presets(
            args.indoor,
            args.scenario,
            preset_ids=presets or None,
            output_dir=args.output_dir,
            runtime_overrides={
                "timeStepS": args.time_step,
                "maxSteps": args.max_steps,
                "randomSeed": args.seed,
                "firstGroupCount": args.first_group_count,
            },
            write_run_outputs=not args.no_run_outputs,
            write_plot=not args.skip_plot,
        )
        print_json(
            {
                "outputDir": summary["outputDir"],
                "presetIds": summary["presetIds"],
                "runs": summary["runs"],
                "plot": summary.get("plot"),
            }
        )
        return 0
    if args.command == "cer":
        indoor, scenario = load_project(args.indoor, args.scenario)
        target = args.target or _first_destination(scenario)
        output_dir = args.output_dir or default_cer_output_dir(scenario.path, indoor.path, args.origin, target or "target")
        formats = [item.strip() for item in str(args.formats).split(",") if item.strip()]
        payload = export_cer_analysis(
            indoor,
            scenario,
            origin=args.origin,
            target=target,
            profile_id=args.profile,
            output_dir=output_dir,
            formats=formats,
            level=args.level,
            use_dynamic_snapshot=bool(args.dynamic),
            step=args.step,
            time_s=args.time_s,
            include_gif=bool(args.gif),
            fps=args.fps,
            max_frames=None if args.max_frames == 0 else args.max_frames,
            failure_profiles=_parse_failure_profiles_arg(args.failure_profiles),
            cost_tolerance=args.cost_tolerance,
        )
        print_json({key: value for key, value in payload.items() if key != "result"})
        return 0
    if args.command == "cer-tree":
        if not args.origin and not args.all_origins:
            parser.error("cer-tree requires at least one --origin or --all-origins")
        indoor, scenario = load_project(args.indoor, args.scenario)
        output_dir = args.output_dir or default_cer_tree_output_dir(scenario.path, indoor.path)
        formats = [item.strip() for item in str(args.formats).split(",") if item.strip()]
        config = CERTreeConfig(
            tau=args.tau,
            max_depth=args.max_depth,
            max_k=args.max_k,
            max_total_failures=args.max_total_failures,
            max_combinations=args.max_combinations,
            max_runtime_ms=args.max_runtime_ms,
            max_distinct_routes=args.max_distinct_routes,
            failure_profiles=_parse_failure_profiles_arg(args.failure_profiles),
            failure_unit=args.failure_unit,
        )
        payload = export_cer_tree_for_scenario(
            indoor,
            scenario,
            profile_ids=args.profile or None,
            origins=None if args.all_origins else args.origin,
            targets=args.target or None,
            output_dir=output_dir,
            formats=formats,
            config=config,
            structural=not bool(args.dynamic),
            step=args.step,
            time_s=args.time_s,
            visual_level=args.level,
            visual_order=args.visual_order,
            visual_layout=args.visual_layout,
        )
        print_json({key: value for key, value in payload.items() if key != "runs"})
        return 0
    if args.command == "explain-routing-policies":
        indoor, scenario = load_project(args.indoor, args.scenario)
        target = args.target or _first_destination(scenario)
        output_dir = args.output_dir or default_policy_output_dir(scenario.path, indoor.path, args.origin, target or "target")
        formats = [item.strip() for item in str(args.formats).split(",") if item.strip()]
        payload = export_routing_policy_explainer(
            indoor,
            scenario,
            origin=args.origin,
            target=target,
            profile_id=args.profile,
            output_dir=output_dir,
            formats=formats,
            level=args.level,
            failure_profiles=_parse_failure_profiles_arg(args.failure_profiles),
            cost_tolerance=args.cost_tolerance,
            profile_weights=_parse_profile_weights_arg(args.profile_weights),
            k_shortest_paths=args.k_routes,
            candidate_cost_tolerance=args.candidate_cost_tolerance,
            agility_weight=args.agility_weight,
            agility_aggregation=args.agility_aggregation,
            max_combinations=args.max_combinations,
            max_runtime_ms=args.max_runtime_ms,
        )
        print_json({key: value for key, value in payload.items() if key != "result"})
        return 0
    if args.command == "beacons":
        indoor, scenario = load_project(args.indoor, args.scenario)
        topology = EvacTopology.from_indoor_model(indoor)
        simulator = BeaconSimulator(topology, scenario.beacons, (scenario.raw.get("beaconSystem") or {}).get("fusion"))
        state = simulator.state_at(args.step, args.time_s)
        print_json({"observations": state.observations, "cellRisk": state.cell_risk})
        return 0
    parser.error(f"Unhandled command {args.command}")
    return 2


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))


def _parse_failure_profiles_arg(value: str | None) -> list[list[int]] | None:
    if not value:
        return None
    profiles: list[list[int]] = []
    for raw_profile in str(value).split(";"):
        items = [int(item.strip()) for item in raw_profile.split(",") if item.strip()]
        if items:
            profiles.append(items)
    return profiles or None


def _parse_profile_weights_arg(value: str | None) -> dict[str, float] | None:
    if not value:
        return None
    weights: dict[str, float] = {}
    for raw_item in str(value).split(";"):
        if not raw_item.strip() or "=" not in raw_item:
            continue
        key, raw_weight = raw_item.split("=", 1)
        key = key.strip()
        if not key:
            continue
        try:
            weight = float(raw_weight.strip())
        except ValueError:
            continue
        if weight < 0.0:
            continue
        if not key.startswith("("):
            key = f"({key})"
        weights[key] = weight
    return weights or None


def _apply_service_overrides(service: ApplicationService, args: argparse.Namespace) -> None:
    if not any(
        value is not None
        for value in (
            args.time_step,
            args.max_steps,
            args.seed,
            args.first_group_count,
            args.algorithm,
            args.cost_policy,
        )
    ):
        return
    service.apply_runtime_settings(
        time_step_s=args.time_step,
        max_steps=args.max_steps,
        random_seed=args.seed,
        routing_algorithm=args.algorithm,
        cost_policy=args.cost_policy,
        first_group_count=args.first_group_count,
    )


def _apply_scenario_overrides(scenario: Any, args: argparse.Namespace) -> None:
    if args.time_step is not None:
        scenario.simulation_config["timeStepS"] = float(args.time_step)
    if args.max_steps is not None:
        scenario.simulation_config["maxSteps"] = int(args.max_steps)
    if args.seed is not None:
        scenario.simulation_config["randomSeed"] = int(args.seed)
    if args.first_group_count is not None and scenario.groups:
        scenario.groups[0]["count"] = int(args.first_group_count)
    if args.algorithm is not None:
        scenario.routing["algorithm"] = args.algorithm
    if args.cost_policy is not None:
        scenario.routing["costPolicy"] = args.cost_policy


def _first_destination(scenario: Any) -> str | None:
    destinations = list(((scenario.routing.get("destination") or {}).get("cellSpaceRefs") or []))
    return destinations[0] if destinations else None


if __name__ == "__main__":
    raise SystemExit(main())

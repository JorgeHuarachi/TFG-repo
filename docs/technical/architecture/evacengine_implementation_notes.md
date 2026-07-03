# EvacEngine Implementation Notes

## Scope

This implementation introduces `src/evac_engine/` as the runtime package for evacuation simulations driven by:

- `indoor_model.json` as spatial truth.
- `scenario_model.json` as dynamic overlay and simulation configuration.

The legacy `src/MLSM_EvacEngine.py` remains available as a manual demo launcher, but it no longer runs Matplotlib animation or CSV export at import time.

## Package Map

- `domain.py`: dataclasses shared across loaders, topology, routing and simulation.
- `loaders.py`: JSON loading, JSON Schema validation, cross-reference checks and Indoor Data Model indexing.
- `topology.py`: canonical `networkx.MultiDiGraph` built preferably from `derive_graph_views(...)[multilevel_transfer_to_transfer]`.
- `routing.py`: route planning with Dijkstra/A*, mobility filters and immutable weight snapshot compilation.
- `overlays.py`: beacon observations and scheduled hazard state.
- `simulation.py`: synchronous tick model, population materialization, route replanning, movement physics and output writers.
- `experiments.py`: route policy preset catalog and same-scenario policy comparison runner.
- `visualization.py`: visual payloads, trajectory QA metrics, HTML viewer and GIF rendering.
- `web_app.py`: local browser workbench for scenario editing, click placement, simulation and playback.
- `application.py`: headless service boundary for CLI/UI/tests.
- `cli.py`: `validate`, `route`, `run`, `render`, `compare-routing`, `workbench`, `beacons`, `cer-tree`, `explain-routing-policies` and `ui` commands.
- `__main__.py`: module entrypoint for `python -m src.evac_engine`.
- `ui/desktop_app.py`: import-safe Tk desktop shell connected to `ApplicationService`.

## Canonical IDs

Runtime nodes are canonical `CellSpace.id` values. Node IDs from the dual graph are accepted as input references only where the loader can resolve them through `Node.duality`.

Vertical connectivity follows the fixed `graph_views` contract: `vertical_connectivity.edges[*].connects`, `multilevel_transfer_to_transfer.edges[*].connects` and `multilevel_space_connectivity.edges[*].connects` are `CellSpace` endpoint IDs, not dual `Node` IDs.

## Runtime Graph

`EvacTopology` builds a directed `networkx.MultiDiGraph` from multilevel graph views. The active evacuation backbone is `multilevel_transfer_to_transfer`: rooms/general spaces are not persistent routing nodes unless they are needed as synthetic origin/destination endpoints for a specific route request. Each undirected Indoor Data Model connection becomes two runtime arcs that share a `ConnectionResource`.

The topology preserves:

- source graph edge refs;
- boundary refs;
- via-space refs for transfer-to-transfer corridors;
- transfer-space refs;
- connector IDs/types;
- locomotion types;
- base length and traversal time.

Vertical inter-level arcs use the difference between level `floorZ` values when both endpoints share the same XY footprint.

## Routing

`WeightSnapshotCompiler` creates a fresh weighted directed graph per tick. It recomputes weights from immutable base data plus current hazard, beacon and congestion overlays. It does not mutate or increment stored edge weights.

Supported internal solvers:

- `dijkstra`
- `astar`
- `floyd_warshall`
- `yen_ksp`
- `robust_agility`

Supported cost policy:

- `minimum_travel_time`

The routing base weight is always traversal time in seconds. `WeightSnapshotCompiler` estimates each edge as `lengthM / (profile base speed * connector speed factor)`, so stairs, ramps and elevators cost more than flat movement even when their 2D length looks similar. Mobility filters prevent profiles from using stairs, ramps or elevators when profile flags disallow them.

Dynamic routing weights support the legacy additive model and cost models for route recommendation policies. The current research focus is CER and policy design, not algorithm comparison. The policy contract, symbols and commands are documented in `docs/technical/research/evacengine_routing_experiment_framework.md`.

Route planning uses the agent's exact continuous XY position for the first graph step. If `agent.current_cell` is a GeneralSpace that is not present in `multilevel_transfer_to_transfer`, the planner adds a temporary endpoint node for that route request and connects it to reachable transfers inside the same cell. The same mechanism supports GeneralSpace destinations in legacy/minimal scenarios. Run metrics expose `routePlans`, `routeRecoveries` and `noRouteEvents` so routing churn can be measured directly.

## Simulation

The simulation uses synchronous phases:

1. update hazard state;
2. update beacon state;
3. compute congestion;
4. plan or replan routes;
5. decide movements;
6. commit movements;
7. record events and trajectories.

Agents keep a topological route and continuous XY position. Movement advances toward transfer waypoints, using each route arc's `viaSpaceRefs` as the geometric corridor when the route jumps from one transfer to another through a GeneralSpace.

Current movement includes:

- velocity inertia and acceleration limiting;
- basic social repulsion;
- wall repulsion against non-navigable geometry;
- geometric step constraints to avoid crossing non-navigable spaces;
- transfer handling for doors, exits, virtual boundaries and vertical connector endpoints;
- relaxed virtual-boundary wall handling to avoid stalls in narrow valid corridors;
- transfer capacity limiting for queue-like behavior.

## Workbench

The browser workbench is launched with:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine workbench --model UnaPlanta_ConConexionesVerticales --host 127.0.0.1 --port 8765
```

It supports:

- scenario reload by path;
- timestep, max steps, seed, route policy and cost policy edits;
- automatic group count/spawn edits;
- click placement of manual agents;
- profile selection for clicked agents;
- policy presets, editable safety/cost/CER parameters and same-scenario policy comparison;
- CER visual debug over `multilevel_transfer_to_transfer`, with transfer-node selectors and click picking for origin/target;
- JSON editing of manual agents, beacons and scheduled events;
- optional geometry QA;
- level switching and trajectory playback;
- multilevel destination mode:
  - `All scenario exits`
  - `Selected only`

The left panel is intentionally ordered as:

1. scenario and simulation controls;
2. agents;
3. beacons and their temporal safety curve;
4. CER and route recommendation policies;
5. raw dynamic events.

This order keeps the workflow explicit: first define the scenario state, then evaluate route recommendation policies over that same state.

The workbench labels beacon/routing safety in user-facing terms:

- `Safety loss` is shown instead of `riskPenalty`;
- `Safety-cost model` is shown instead of `riskCostModel`;
- `Safety source` is shown instead of `riskEndpointPolicy`;
- `Block at loss` is shown instead of a risk block threshold.

The underlying JSON fields are unchanged for compatibility. In runtime data:

```text
safety_loss = 1 - safety
riskPenalty = safety_loss
```

`CER & Route Recommendation` is split into two levels:

- the normal level exposes policy selection, `Apply policy`, `Apply policy + run`, `Compare policies` and the policy checklist;
- the advanced level is collapsed under `Advanced safety/cost parameters` and contains alpha/beta weights, candidate-route parameters and CER controls.

The comparison table includes `plans`, which is the count of route recalculation events for active agents under that policy. The visible policy decides the internal solver: minimum time, safety-time and CER-Cost use Dijkstra; CER-Agility uses Yen to generate candidates and then selects by CER.

## Outputs

Runs write:

- `run_manifest.json`
- `events.ndjson`
- `routes.json`
- `trajectories.ndjson`
- `metrics.json`
- `metrics.csv`

## Non-Goals In This Pass

- No changes to `src/MLSM_SpatialEngine.py`.
- No changes to `schemas/indoor/indoor_model.schema.json`.
- No re-export of `indoor_model.json`.
- No external GUI dependency beyond the Python standard-library Tk stack.

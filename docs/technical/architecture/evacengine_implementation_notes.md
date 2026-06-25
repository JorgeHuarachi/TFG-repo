# EvacEngine Implementation Notes

## Scope

This implementation introduces `src/evac_engine/` as the runtime package for evacuation simulations driven by:

- `indoor_model.json` as spatial truth.
- `scenario_model.json` as dynamic overlay and simulation configuration.

The legacy `src/MLSM_EvacEngine.py` remains available as a manual demo launcher, but it no longer runs Matplotlib animation or CSV export at import time.

## Package Map

- `domain.py`: dataclasses shared across loaders, topology, routing and simulation.
- `loaders.py`: JSON loading, JSON Schema validation, cross-reference checks and Indoor Data Model indexing.
- `topology.py`: canonical `networkx.MultiDiGraph` built from `derive_graph_views(...)[multilevel_space_connectivity]`.
- `routing.py`: route planning with Dijkstra/A*, mobility filters and immutable weight snapshot compilation.
- `overlays.py`: beacon observations and scheduled hazard state.
- `simulation.py`: synchronous tick model, population materialization, route replanning, movement physics and output writers.
- `experiments.py`: routing preset catalog and same-scenario comparison runner.
- `visualization.py`: visual payloads, trajectory QA metrics, HTML viewer and GIF rendering.
- `web_app.py`: local browser workbench for scenario editing, click placement, simulation and playback.
- `application.py`: headless service boundary for CLI/UI/tests.
- `cli.py`: `validate`, `route`, `run`, `render`, `compare-routing`, `workbench`, `beacons` and `ui` commands.
- `__main__.py`: module entrypoint for `python -m src.evac_engine`.
- `ui/desktop_app.py`: import-safe Tk desktop shell connected to `ApplicationService`.

## Canonical IDs

Runtime nodes are canonical `CellSpace.id` values. Node IDs from the dual graph are accepted as input references only where the loader can resolve them through `Node.duality`.

Vertical connectivity follows the fixed `graph_views` contract: `vertical_connectivity.edges[*].connects` and `multilevel_space_connectivity.edges[*].connects` are `CellSpace` endpoint IDs, not dual `Node` IDs.

## Runtime Graph

`EvacTopology` builds a directed `networkx.MultiDiGraph` from multilevel graph views. Each undirected Indoor Data Model connection becomes two runtime arcs that share a `ConnectionResource`.

The topology preserves:

- source graph edge refs;
- boundary refs;
- transfer-space refs;
- connector IDs/types;
- locomotion types;
- base length and traversal time.

Vertical inter-level arcs use the difference between level `floorZ` values when both endpoints share the same XY footprint.

## Routing

`WeightSnapshotCompiler` creates a fresh weighted directed graph per tick. It recomputes weights from immutable base data plus current hazard, beacon and congestion overlays. It does not mutate or increment stored edge weights.

Supported algorithms:

- `dijkstra`
- `astar`
- `yen_ksp`
- `robust_agility`

Supported cost policies:

- `shortest_distance`
- `minimum_travel_time`

Mobility filters prevent profiles from using stairs, ramps or elevators when profile flags disallow them.

Dynamic routing weights support the legacy additive model and experimental cost models for route recommendation studies. The full experiment contract, symbols, presets and commands are documented in `docs/technical/research/evacengine_routing_experiment_framework.md`.

## Simulation

The simulation uses synchronous phases:

1. update hazard state;
2. update beacon state;
3. compute congestion;
4. plan or replan routes;
5. decide movements;
6. commit movements;
7. record events and trajectories.

Agents keep a topological route and continuous XY position. Movement advances toward the representative point of the next `CellSpace` waypoint.

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
.\.venv\Scripts\python.exe -B -m src.evac_engine workbench --scenario examples\indoor_data_model\scenario_single_floor.json --host 127.0.0.1 --port 8765
```

It supports:

- scenario reload by path;
- timestep, max steps, seed, algorithm and cost policy edits;
- automatic group count/spawn edits;
- click placement of manual agents;
- profile selection for clicked agents;
- routing experiment presets, editable risk/cost parameters and same-scenario preset comparison;
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
4. routing experiments;
5. raw dynamic events.

This order keeps the workflow explicit: first define the scenario state, then compare route recommendation policies over that same state.

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

`Routing Experiments` is split into two levels:

- the normal level exposes preset selection, `Apply preset`, `Run visually`, `Compare checked` and the preset checklist;
- the advanced level is collapsed under `Advanced safety/cost parameters` and contains alpha/beta weights, candidate-route parameters, robustness/agility controls and the combined-policy weights.

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

# EvacEngine Refactor Verification

## Baseline

Initial repository checks were run before implementation:

- `git status --short`
- `git branch --show-current`
- `git log -5 --oneline`

The pre-existing working tree contained untracked technical docs under `docs/technical/`.

The existing suite was executed with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Baseline result before EvacEngine edits: 49 tests, OK.

## Added Automated Coverage

`tests/test_evac_engine_refactor.py` covers:

- new scenario examples validate against `schemas/indoor/scenario_model.schema.json`;
- legacy `dynamic_weighted` routing selection is rejected;
- minimal routing uses canonical `CellSpace` IDs and preserves route arcs;
- vertical endpoint routing works through `multilevel_space_connectivity`;
- Rolling profiles do not receive the direct stair edge in the weighted snapshot;
- the simulation writes the required output files.

Final result after implementation:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Result: 54 tests, OK.

## Manual/CLI Checks

Representative checks used during implementation:

```powershell
.\.venv\Scripts\python.exe -B -m src.evac_engine validate --scenario examples\indoor_data_model\minimal_scenario_model.json
.\.venv\Scripts\python.exe -B -m src.evac_engine route --scenario examples\indoor_data_model\minimal_scenario_model.json --origin CS_L00_ROOM_A
.\.venv\Scripts\python.exe -B -m src.evac_engine run --scenario examples\indoor_data_model\minimal_scenario_model.json --output-dir .tmp\evacengine_minimal_run
.\.venv\Scripts\python.exe -B -m src.evac_engine validate --scenario examples\indoor_data_model\scenario_single_floor.json
.\.venv\Scripts\python.exe -B -m src.evac_engine validate --scenario examples\indoor_data_model\scenario_multilevel.json
.\.venv\Scripts\python.exe -B -m src.evac_engine beacons --scenario examples\indoor_data_model\scenario_beacons_demo.json --step 0 --time-s 0
```

Manual route checks confirmed:

- minimal route: `CS_L00_ROOM_A -> CS_L00_DOOR_1 -> CS_L00_ROOM_B`;
- single-floor example reaches `CS_L00_EXIT_001`;
- multilevel endpoint route works from `CS_L02_EP_VC_004_LEVEL_02` to `CS_L01_EP_VC_004_LEVEL_01`.

Manual run checks confirmed:

- minimal scenario: 5/5 evacuated in 6 steps;
- single-floor scenario: 8/8 evacuated in 66 steps;
- multilevel scenario: 6/6 evacuated in 96 steps;
- beacons demo: beacon risk observations generated for Room A, Door 1 and Room B.

## Remaining Verification Risks

- The desktop UI is intentionally lightweight and import-safe; its service boundary is covered indirectly through CLI/application tests, not screenshot tests.
- Physical movement is a deterministic waypoint model. It is functional, but it is not yet a calibrated crowd-dynamics validation model.
- Hazard propagation is scheduled/static in this pass. Growth by radius exists, but no smoke/fire propagation model is calibrated.

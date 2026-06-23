# Evacuation Routing Research Backlog

## Calibration

- Validate walking, rolling and elderly speed distributions against evacuation literature and local building assumptions.
- Calibrate personal-space and body-radius parameters for dense door/connector flows.
- Compare waypoint travel times against observed or synthetic evacuation benchmarks.

## Routing And Behavior

- Add route-choice models beyond shortest distance and minimum travel time.
- Investigate bounded rationality, familiarity with exits and herd-following behavior.
- Add explicit queueing/capacity models for doors, ramps, stairs and elevators.

## Hazards

- Replace static risk overlays with calibrated smoke/fire propagation fields.
- Model visibility reduction separately from route risk.
- Add time-varying blocked-boundary and degraded-capacity effects.

## Beacons And Sensing

- Define beacon measurement uncertainty and latency.
- Support conflicting beacon observations and confidence-based fusion.
- Evaluate guidance policies that reduce risk without causing congestion.

## Validation

- Build scenario fixtures with expected evacuation times and route choices.
- Add regression tests for disconnected graphs, blocked exits and wheelchair-accessible rerouting.
- Add visual QA for the desktop UI and route overlays.


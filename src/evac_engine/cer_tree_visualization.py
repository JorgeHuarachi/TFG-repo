"""Interactive visualization adapter for CER-tree debug payloads."""

from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from .cer_visualization import save_cer_debug_html
from .topology import EvacTopology


def save_cer_tree_debug_html(
    topology: EvacTopology,
    tree_payload: dict[str, Any],
    output_path: str | Path,
    *,
    level: str | None = None,
    visual_order: str = "tree",
    visual_layout: str = "wide",
) -> Path:
    """Render CER-tree debug steps with the existing CER visual grammar.

    The tree calculator keeps richer audit fields than the first CER
    visualizer. This adapter maps those fields to the visual payload expected by
    ``cer_visualization`` without changing the CER-tree calculation itself.
    """

    visual_payload = _to_visual_payload(tree_payload, visual_order=visual_order, visual_layout=visual_layout)
    return save_cer_debug_html(topology, visual_payload, output_path, level=level)


def _to_visual_payload(tree_payload: dict[str, Any], *, visual_order: str, visual_layout: str) -> dict[str, Any]:
    payload = json.loads(json.dumps(tree_payload, ensure_ascii=True))
    metadata = payload.setdefault("metadata", {})
    config = metadata.get("config") or {}
    metadata.setdefault("costTolerance", config.get("tau"))
    metadata.setdefault("visualSource", "cer_tree")
    metadata["visualOrder"] = visual_order
    metadata["visualLayout"] = visual_layout
    visual_steps = []
    for step in _ordered_steps(payload.get("debugSteps") or [], visual_order):
        visual_steps.append(_to_visual_step(step))
    payload["debugSteps"] = visual_steps
    return payload


def _ordered_steps(steps: list[dict[str, Any]], visual_order: str) -> list[dict[str, Any]]:
    if visual_order != "tree":
        return [{**step, "calculationStepIndex": index} for index, step in enumerate(steps, start=1)]
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    indexed_steps = [{**step, "calculationStepIndex": index} for index, step in enumerate(steps, start=1)]
    for step in indexed_steps:
        children[str(step.get("parentBranchId") or "root")].append(step)
    ordered: list[dict[str, Any]] = []
    seen_indexes: set[int] = set()

    def visit(parent_id: str) -> None:
        for child in children.get(parent_id, []):
            index = int(child.get("calculationStepIndex") or 0)
            if index in seen_indexes:
                continue
            seen_indexes.add(index)
            ordered.append(child)
            child_id = str(child.get("branchId") or "")
            if child_id:
                visit(child_id)

    visit("root")
    for step in indexed_steps:
        index = int(step.get("calculationStepIndex") or 0)
        if index not in seen_indexes:
            ordered.append(step)
    return ordered


def _to_visual_step(step: dict[str, Any]) -> dict[str, Any]:
    candidate_cost = step.get("recalculatedCost")
    cost_limit = step.get("Cmax")
    decision = str(step.get("decision") or "")
    accepted = _is_visual_acceptance(decision, candidate_cost, cost_limit)
    failure_profile = step.get("failureProfileRaw") or []
    removed = _normalize_units(step.get("removedCombination") or [])
    failed = _normalize_units(step.get("failedUnits") or [])
    visual = {
        **step,
        "accepted": accepted,
        "reason": decision,
        "costLimit": cost_limit,
        "candidatePath": list(step.get("recalculatedPath") or []),
        "candidateCost": candidate_cost,
        "failureSourcePath": list(step.get("sourcePath") or []),
        "failureDepth": len(failure_profile),
        "evaluatedFailureCases": step.get("totalCases"),
        "distinctRouteCount": step.get("distinctRoutes"),
        "failedUnits": failed,
        "newlyFailedUnits": removed,
        "failedResources": _resource_values(failed),
        "newlyFailedResources": _resource_values(removed),
    }
    return visual


def _is_visual_acceptance(decision: str, candidate_cost: Any, cost_limit: Any) -> bool:
    if decision in {"accepted", "duplicate_route"}:
        return True
    if candidate_cost is None or cost_limit is None:
        return False
    try:
        return float(candidate_cost) <= float(cost_limit)
    except (TypeError, ValueError):
        return False


def _normalize_units(units: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized = []
    for item in units:
        kind = str(item.get("kind") or item.get("type") or "resource")
        value = str(item.get("value") or item.get("id") or "")
        if value:
            normalized.append({"kind": kind, "value": value})
    return normalized


def _resource_values(units: list[dict[str, str]]) -> list[str]:
    return [str(item["value"]) for item in units if item.get("kind") == "resource"]

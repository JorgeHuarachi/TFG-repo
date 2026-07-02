#!/usr/bin/env python3
"""Interactive launcher for CER-tree experiments."""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evac_engine.loaders import load_project
from src.evac_engine.topology import EvacTopology
from src.spatial_engine.project_workspace import discover_indoor_models, related_scenarios_for_model


PYTHON = sys.executable

FAILURE_PRESETS = [
    {
        "name": "1-chain depth 2",
        "profiles": "1;1,1",
        "max_depth": 2,
        "max_k": 1,
        "max_total_failures": 2,
        "description": "Fallo simple y un segundo fallo secuencial.",
    },
    {
        "name": "1-chain depth 4",
        "profiles": "1;1,1;1,1,1;1,1,1,1",
        "max_depth": 4,
        "max_k": 1,
        "max_total_failures": 4,
        "description": "Rama secuencial larga hasta 4 fallos simples.",
    },
    {
        "name": "2-chain",
        "profiles": "2;2,1;2,1,1",
        "max_depth": 3,
        "max_k": 2,
        "max_total_failures": 4,
        "description": "Empieza con fallo simultaneo doble y continua con fallos simples.",
    },
    {
        "name": "mixed depth 2",
        "profiles": "1;2;1,1;1,2;2,1;2,2",
        "max_depth": 2,
        "max_k": 2,
        "max_total_failures": 4,
        "description": "Comparacion rapida de fallos simples, dobles y secuenciales.",
    },
]


def main() -> int:
    print("\n=== CER-tree playground ===")
    print("Configura experimentos sin editar una linea de comando enorme.\n")
    model = choose_model()
    if not model:
        return 1
    scenario_path = choose_scenario(model)
    if not scenario_path:
        return 1
    indoor, scenario = load_project(None, scenario_path)
    topology = EvacTopology.from_indoor_model(indoor)

    profile_id = choose_mobility_profile(scenario)
    all_origins = choose_origin_scope()
    origin = "" if all_origins else choose_node(topology, "origen", exclude=set(exit_candidates(topology, scenario)))
    all_targets = choose_target_scope()
    target = "" if all_targets else choose_target(topology, scenario)
    preset = choose_failure_preset()

    tau = prompt_float("Tau tolerancia", 0.3)
    max_depth = prompt_int("maxDepth", preset["max_depth"])
    max_k = prompt_int("maxK", preset["max_k"])
    max_total_failures = prompt_int("maxTotalFailures", preset["max_total_failures"])
    max_combinations = prompt_int("maxCombinations", 1000)
    max_runtime_ms = prompt_int("maxRuntimeMs", 30000)
    default_visual = not all_origins
    visual_enabled = prompt_yes_no("Generar HTML visual paso a paso", default_visual)
    visual_order = prompt_choice("Orden visual", ["tree", "calculation", "both"], "tree") if visual_enabled else "tree"
    visual_layout = prompt_choice("Layout visual", ["wide", "standard"], "wide") if visual_enabled else "wide"
    level = choose_level(topology) if visual_enabled else ""
    output_name = prompt_text("Nombre carpeta output", default_output_name(preset, visual_order))
    open_after = prompt_yes_no("Abrir HTML al terminar", True)

    orders = ["tree", "calculation"] if visual_enabled and visual_order == "both" else [visual_order]
    for order in orders:
        output_dir = output_dir_for_scenario(scenario_path, output_name, order if visual_order == "both" else "")
        formats = "json,csv,html,visual-html" if visual_enabled else "json,csv,html"
        cmd = [
            PYTHON,
            "-m",
            "src.evac_engine",
            "cer-tree",
            "--scenario",
            str(scenario_path),
            "--profile",
            profile_id,
            "--formats",
            formats,
            "--failure-profiles",
            preset["profiles"],
            "--tau",
            str(tau),
            "--max-depth",
            str(max_depth),
            "--max-k",
            str(max_k),
            "--max-total-failures",
            str(max_total_failures),
            "--max-combinations",
            str(max_combinations),
            "--max-runtime-ms",
            str(max_runtime_ms),
            "--visual-order",
            order,
            "--visual-layout",
            visual_layout,
            "--output-dir",
            str(output_dir),
        ]
        if all_origins:
            cmd.append("--all-origins")
        else:
            cmd.extend(["--origin", origin])
        if not all_targets:
            cmd.extend(["--target", target])
        if level:
            cmd.extend(["--level", level])
        print("\nEjecutando:")
        print(" ".join(quote_arg(item) for item in cmd))
        subprocess.run(cmd, cwd=REPO_ROOT, check=False)
        visual = output_dir / f"cer_tree_{safe_slug(profile_id)}_visual.html"
        summary = output_dir / f"cer_tree_{safe_slug(profile_id)}.html"
        if visual.exists():
            print(f"\nHTML visual: {visual}")
            if open_after and visual_enabled:
                webbrowser.open_new_tab(visual.resolve().as_uri())
        if summary.exists():
            print(f"HTML tabla: {summary}")
            if open_after and not visual_enabled:
                webbrowser.open_new_tab(summary.resolve().as_uri())
    return 0


def choose_model() -> dict[str, Any] | None:
    models = [item for item in discover_indoor_models(REPO_ROOT) if item.get("source") == "models"]
    if not models:
        print("No hay modelos en models/.")
        return None
    return choose_from_list(models, "modelo", model_label, default_index=1)


def choose_scenario(model: dict[str, Any]) -> Path | None:
    scenarios = related_scenarios_for_model(REPO_ROOT / model["path"], REPO_ROOT)
    if not scenarios:
        print("Ese modelo no tiene scenarios asociados.")
        return None
    baseline_index = next((index for index, item in enumerate(scenarios, start=1) if Path(item["path"]).stem == "baseline"), 1)
    scenario = choose_from_list(scenarios, "scenario", lambda item: item["path"], default_index=baseline_index)
    return (REPO_ROOT / scenario["path"]).resolve() if scenario else None


def choose_mobility_profile(scenario: Any) -> str:
    profiles = sorted(scenario.mobility_profiles)
    if not profiles:
        return "MP_WALKING"
    default = profiles.index("MP_WALKING") + 1 if "MP_WALKING" in profiles else 1
    return choose_from_list([{"id": item} for item in profiles], "perfil de movilidad", lambda item: item["id"], default_index=default)["id"]


def choose_origin_scope() -> bool:
    selected = choose_from_list(
        [
            {"id": "one", "label": "un nodo origen"},
            {"id": "all", "label": "todos los nodos del snapshot"},
        ],
        "alcance de origen",
        lambda item: item["label"],
        default_index=1,
    )
    return selected["id"] == "all"


def choose_target_scope() -> bool:
    selected = choose_from_list(
        [
            {"id": "one", "label": "una salida concreta"},
            {"id": "all", "label": "todas las salidas configuradas"},
        ],
        "alcance de salida",
        lambda item: item["label"],
        default_index=1,
    )
    return selected["id"] == "all"


def choose_target(topology: EvacTopology, scenario: Any) -> str:
    targets = exit_candidates(topology, scenario)
    return choose_node(topology, "salida target", only=set(targets)) if targets else choose_node(topology, "salida target")


def choose_node(topology: EvacTopology, label: str, *, only: set[str] | None = None, exclude: set[str] | None = None) -> str:
    rows = []
    for node_id, data in topology.graph.nodes(data=True):
        node_id = str(node_id)
        if only is not None and node_id not in only:
            continue
        if exclude and node_id in exclude:
            continue
        rows.append(
            {
                "id": node_id,
                "category": str(data.get("category") or ""),
                "level": topology.node_level(node_id) or "",
            }
        )
    rows.sort(key=lambda item: (item["level"], item["category"], item["id"]))
    selected = choose_from_list(rows, label, lambda item: f"{item['id']} | {item['category']} | {item['level']}", default_index=1, allow_custom=True)
    return selected["id"]


def choose_failure_preset() -> dict[str, Any]:
    rows = []
    for item in FAILURE_PRESETS:
        rows.append({"label": f"{item['name']} -> {item['profiles']} | {item['description']}", **item})
    rows.append({"label": "custom", "name": "custom", "profiles": "", "max_depth": 2, "max_k": 1, "max_total_failures": 2})
    selected = choose_from_list(rows, "preset de perfiles de fallo", lambda item: item["label"], default_index=1)
    if selected["name"] == "custom":
        profiles = prompt_text("Perfiles de fallo", "1;1,1")
        max_depth = max(len(part.split(",")) for part in profiles.split(";") if part.strip())
        max_k = max(int(value) for part in profiles.split(";") for value in part.split(",") if value.strip())
        max_total = max(sum(int(value) for value in part.split(",") if value.strip()) for part in profiles.split(";") if part.strip())
        selected = {
            "name": "custom",
            "profiles": profiles,
            "max_depth": max_depth,
            "max_k": max_k,
            "max_total_failures": max_total,
        }
    print(
        f"\nPreset: {selected['profiles']} "
        f"(maxDepth={selected['max_depth']}, maxK={selected['max_k']}, maxTotalFailures={selected['max_total_failures']})"
    )
    return selected


def choose_level(topology: EvacTopology) -> str:
    levels = sorted({str(data.get("level")) for _, data in topology.graph.nodes(data=True) if data.get("level")})
    if not levels:
        return ""
    return choose_from_list([{"id": ""}, *({"id": item} for item in levels)], "nivel visual", lambda item: item["id"] or "auto/todos", default_index=2)["id"]


def exit_candidates(topology: EvacTopology, scenario: Any) -> list[str]:
    configured = [
        str(item)
        for item in ((scenario.routing.get("destination") or {}).get("cellSpaceRefs") or [])
        if str(item) in topology.graph
    ]
    return configured or topology.exit_candidates()


def output_dir_for_scenario(scenario_path: Path, output_name: str, order_suffix: str) -> Path:
    parts = scenario_path.resolve().parts
    if "models" in parts:
        index = parts.index("models")
        if index + 1 < len(parts):
            model = parts[index + 1]
            suffix = f"{output_name}_{order_suffix}" if order_suffix else output_name
            return REPO_ROOT / "models" / model / "outputs" / "cer_tree" / safe_slug(suffix)
    suffix = f"{output_name}_{order_suffix}" if order_suffix else output_name
    return REPO_ROOT / "outputs" / "cer_tree" / safe_slug(suffix)


def default_output_name(preset: dict[str, Any], visual_order: str) -> str:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return safe_slug(f"{preset['name']}_{visual_order}_{timestamp}")


def choose_from_list(rows: list[dict[str, Any]], label: str, format_row, *, default_index: int = 1, allow_custom: bool = False) -> dict[str, Any]:
    print(f"\n{label}:")
    for index, row in enumerate(rows, start=1):
        marker = " [default]" if index == default_index else ""
        print(f"  {index}) {format_row(row)}{marker}")
    while True:
        raw = input(f"Selecciona {label} [Enter={default_index}]: ").strip()
        if not raw:
            return rows[default_index - 1]
        if allow_custom and not raw.isdigit():
            return {"id": raw}
        try:
            index = int(raw)
        except ValueError:
            print("Introduce un numero valido.")
            continue
        if 1 <= index <= len(rows):
            return rows[index - 1]
        print("Indice fuera de rango.")


def prompt_text(label: str, default: str) -> str:
    raw = input(f"{label} [Enter={default}]: ").strip()
    return raw or default


def prompt_int(label: str, default: int) -> int:
    while True:
        raw = input(f"{label} [Enter={default}]: ").strip()
        if not raw:
            return int(default)
        try:
            return int(raw)
        except ValueError:
            print("Introduce un entero.")


def prompt_float(label: str, default: float) -> float:
    while True:
        raw = input(f"{label} [Enter={default}]: ").strip()
        if not raw:
            return float(default)
        try:
            return float(raw)
        except ValueError:
            print("Introduce un numero.")


def prompt_choice(label: str, choices: list[str], default: str) -> str:
    rows = [{"id": item} for item in choices]
    default_index = choices.index(default) + 1 if default in choices else 1
    return choose_from_list(rows, label, lambda item: item["id"], default_index=default_index)["id"]


def prompt_yes_no(label: str, default: bool) -> bool:
    suffix = "S/n" if default else "s/N"
    raw = input(f"{label} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"s", "si", "sí", "y", "yes"}


def model_label(item: dict[str, Any]) -> str:
    parts = [str(item.get("project") or item.get("label") or item.get("path"))]
    if item.get("levelCount"):
        parts.append(f"{item['levelCount']} niveles")
    if item.get("cellCount"):
        parts.append(f"{item['cellCount']} celdas")
    if item.get("scenarioCount"):
        parts.append(f"{item['scenarioCount']} scenarios")
    return " | ".join(parts)


def safe_slug(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "._-" else "_" for char in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("._-") or "cer_tree_run"


def quote_arg(value: str) -> str:
    value = str(value)
    return f'"{value}"' if any(char.isspace() for char in value) else value


if __name__ == "__main__":
    raise SystemExit(main())

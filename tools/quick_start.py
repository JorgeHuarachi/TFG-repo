#!/usr/bin/env python3
"""Interactive quick launcher for SpatialEngine and EvacEngine workflows."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.spatial_engine.project_workspace import discover_indoor_models, related_scenarios_for_model


PYTHON = sys.executable
DECOMPOSITIONS = ("triangulation", "rectilinear", "none")
RENDER_DETAILS = ("fast", "full")


def main() -> int:
    print_header()
    while True:
        print(
            "\nElige una opcion:\n"
            "  1) Crear/dibujar IndoorModel nuevo en SpatialEngine\n"
            "  2) Ver IndoorModel en visor SpatialEngine\n"
            "  3) Abrir EvacEngine Workbench por modelo\n"
            "  4) Listar mis modelos de trabajo\n"
            "  5) Listar todo lo detectable\n"
            "  6) CER-tree playground\n"
            "  7) Salir\n"
        )
        choice = input("Opcion [1-7]: ").strip()
        if choice == "1":
            launch_spatial_authoring()
        elif choice == "2":
            launch_spatial_viewer()
        elif choice == "3":
            launch_evac_workbench()
        elif choice == "4":
            list_models(source="models")
        elif choice == "5":
            list_models(source=None)
        elif choice == "6":
            launch_cer_tree_playground()
        elif choice in {"7", "q", "Q", "salir"}:
            return 0
        else:
            print("Opcion no reconocida.")


def print_header() -> None:
    print("\n=== TFG Quick Start ===")
    print("Flujo: SpatialEngine -> models/<modelo>/spatial -> EvacEngine scenarios/outputs")
    print(f"Repo: {REPO_ROOT}")


def launch_spatial_authoring() -> None:
    name = prompt_text("Nombre del modelo", "Mi_Edificio_01")
    width = prompt_number("Ancho del lienzo en metros", 45)
    height = prompt_number("Alto del lienzo en metros", 28)
    decomposition = prompt_choice("Division GeneralSpace", DECOMPOSITIONS, "triangulation")
    render_detail = prompt_choice("Render durante autoria", RENDER_DETAILS, "fast")
    cmd = [
        PYTHON,
        "src/MLSM_SpatialEngine.py",
        "--name",
        name,
        "--width",
        str(width),
        "--height",
        str(height),
        "--decomposition",
        decomposition,
        "--render-detail",
        render_detail,
    ]
    print("\nEjecutando SpatialEngine. Dibuja y pulsa 'e' para exportar.")
    print_command(cmd)
    subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    print(
        "\nSi exportaste con 'e', deberias tener:\n"
        f"  models/{safe_slug(name)}/spatial/indoor_model.json\n"
        f"  models/{safe_slug(name)}/evacuation/scenarios/baseline.json\n"
    )


def launch_spatial_viewer() -> None:
    model = choose_indoor_model(prefer_user_models=True)
    if not model:
        return
    port = next_free_port(8770)
    print(f"Puerto SpatialEngine visor: {port} (automatico)")
    url = f"http://127.0.0.1:{port}/?model={quote_url(model['path'])}&session={session_token()}"
    cmd = [PYTHON, "-m", "src.spatial_engine.web_app", "--model", model["path"], "--port", str(port)]
    start_background(cmd)
    if not wait_for_port("127.0.0.1", port):
        print("Aviso: el visor aun no responde; si la pestaña falla, recarga en unos segundos.")
    print(f"Visor SpatialEngine: {url}")
    webbrowser.open_new_tab(url)


def launch_evac_workbench() -> None:
    models = [item for item in discover_indoor_models(REPO_ROOT) if item.get("source") == "models"]
    if not models:
        print("No hay modelos en models/. Crea uno primero con la opcion 1.")
        return
    model = choose_from_list(models, "modelo para EvacEngine", lambda item: model_label(item))
    if not model:
        return
    model_name = model.get("project") or model_name_from_path(model["path"])
    port = next_free_port(8900)
    print(f"Puerto EvacEngine nuevo: {port} (automatico)")
    scenario_path = default_scenario_for_model(Path(model["path"]))
    session = session_token()
    query_parts = []
    if scenario_path:
        query_parts.append(f"scenario={quote_url(scenario_path)}")
    query_parts.append(f"session={session}")
    query = "?" + "&".join(query_parts)
    url = f"http://127.0.0.1:{port}/{query}"
    cmd = [PYTHON, "-m", "src.evac_engine", "workbench", "--model", model_name, "--port", str(port)]
    start_background(cmd)
    if not wait_for_port("127.0.0.1", port):
        print("Aviso: EvacEngine aun no responde; si la pestaña falla, recarga en unos segundos.")
    print(f"EvacEngine Workbench nuevo: {url}")
    print(f"Sesion: {session}")
    print("En la UI: Save scenario guarda JSON; Save GIF/HTML graba la simulacion.")
    webbrowser.open_new_tab(url)


def launch_cer_tree_playground() -> None:
    cmd = [PYTHON, "tools/cer_tree_playground.py"]
    print("\nAbriendo CER-tree playground interactivo.")
    print_command(cmd)
    subprocess.run(cmd, cwd=REPO_ROOT, check=False)


def list_models(source: str | None = "models") -> None:
    models = discover_indoor_models(REPO_ROOT)
    if source:
        models = [model for model in models if model.get("source") == source]
    if not models:
        scope = " en models/" if source == "models" else ""
        print(f"No se encontraron IndoorModels{scope}.")
        return
    if source == "models":
        print("\nModelos de trabajo en models/:")
    else:
        print("\nTodo lo detectable: models/, examples/ y backups de outputs/indoor_models/")
    for index, model in enumerate(models, start=1):
        print(f"\n{index}. {model_label(model)}")
        model_path = REPO_ROOT / model["path"]
        scenarios = related_scenarios_for_model(model_path, REPO_ROOT)
        if scenarios:
            for scenario in scenarios:
                print(f"   scenario: {scenario['path']}")
        else:
            print("   scenario: ninguno")


def choose_indoor_model(prefer_user_models: bool = False) -> dict[str, str] | None:
    models = discover_indoor_models(REPO_ROOT)
    if prefer_user_models:
        user_models = [item for item in models if item.get("source") == "models"]
        if user_models:
            models = user_models
    if not models:
        print("No se encontraron IndoorModels.")
        return None
    return choose_from_list(models, "IndoorModel", lambda item: model_label(item))


def choose_from_list(rows: list[dict[str, str]], label: str, format_row) -> dict[str, str] | None:
    for index, row in enumerate(rows, start=1):
        print(f"  {index}) {format_row(row)}")
        if row.get("path"):
            print(f"     {row['path']}")
    while True:
        raw = input(f"Selecciona {label} [1-{len(rows)}] o Enter para cancelar: ").strip()
        if not raw:
            return None
        try:
            index = int(raw)
        except ValueError:
            print("Introduce un numero.")
            continue
        if 1 <= index <= len(rows):
            return rows[index - 1]
        print("Indice fuera de rango.")


def model_label(item: dict[str, str]) -> str:
    name = item.get("project") or item.get("label") or item.get("path") or "IndoorModel"
    parts = [str(name)]
    if item.get("levelCount"):
        parts.append(f"{item['levelCount']} levels")
    if item.get("cellCount"):
        parts.append(f"{item['cellCount']} cells")
    if item.get("generalSpaceCount"):
        parts.append(f"{item['generalSpaceCount']} rooms")
    if item.get("extentM"):
        parts.append(str(item["extentM"]))
    parts.append(f"scenarios={item.get('scenarioCount', 0)}")
    if item.get("source") and item.get("source") != "models":
        parts.append(str(item["source"]))
    return " | ".join(parts)


def default_scenario_for_model(model_path: Path) -> str:
    scenarios = related_scenarios_for_model(REPO_ROOT / model_path, REPO_ROOT)
    baseline = next((item for item in scenarios if Path(item["path"]).stem == "baseline"), None)
    selected = baseline or (scenarios[0] if scenarios else None)
    return selected["path"] if selected else ""


def model_name_from_path(path: str) -> str:
    parts = Path(path).parts
    if len(parts) >= 2 and parts[0] == "models":
        return parts[1]
    return Path(path).stem


def prompt_text(label: str, default: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def prompt_number(label: str, default: int) -> int:
    while True:
        value = input(f"{label} [{default}]: ").strip()
        if not value:
            return default
        try:
            parsed = int(value)
        except ValueError:
            print("Introduce un numero entero.")
            continue
        if parsed > 0:
            return parsed
        print("Debe ser mayor que 0.")


def prompt_choice(label: str, choices: tuple[str, ...], default: str) -> str:
    options = "/".join(choices)
    while True:
        value = input(f"{label} ({options}) [{default}]: ").strip()
        if not value:
            return default
        if value in choices:
            return value
        print(f"Opciones validas: {options}")


def prompt_port(label: str, default: int) -> int:
    port = prompt_number(label, default)
    if port_is_open(port):
        replacement = next_free_port(port + 1)
        print(f"El puerto {port} ya esta en uso; usare {replacement} para abrir una sesion nueva.")
        return replacement
    return port


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def next_free_port(start: int, search_limit: int = 200) -> int:
    for candidate in range(int(start), int(start) + search_limit):
        if not port_is_open(candidate):
            return candidate
    raise RuntimeError(f"No se encontro un puerto libre desde {start} hasta {int(start) + search_limit - 1}.")


def start_background(cmd: list[str]) -> None:
    print_command(cmd)
    kwargs = {"cwd": REPO_ROOT}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(cmd, **kwargs)


def wait_for_port(host: str, port: int, timeout_s: float = 6.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def print_command(cmd: list[str]) -> None:
    print("Comando:")
    print("  " + " ".join(str(part) for part in cmd))


def quote_url(value: str) -> str:
    from urllib.parse import quote

    return quote(str(value).replace("\\", "/"))


def session_token() -> str:
    return str(int(time.time() * 1000))


def safe_slug(value: str) -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "SpatialEngine_Model"


if __name__ == "__main__":
    raise SystemExit(main())

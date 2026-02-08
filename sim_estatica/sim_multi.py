# sim_multi.py (con force_sources + diagnóstico)
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import time
import networkx as nx

from graph_utils import (
    get_conn, build_filtered_graph, find_exit_nodes, shortest_to_any_target,
    explain_filtering
)

DUAL = "DU-01"
LEVEL = "P01"
SCORE_UMBRAL_LOCAL = 0.6
ALLOWED_LOCOMOTIONS_LOCAL = ("WALK","RAMP")
V_MPS = 1.2

TICK = 1.0
REFRESH_S = 2.0
MAX_T = 600.0

CAPACITY = 3
ALPHA = 0.6

OUT_DIR = Path("out"); OUT_DIR.mkdir(exist_ok=True, parents=True)
OUT_CSV = OUT_DIR / "run_multi.csv"

@dataclass
class Agent:
    aid: int
    cur: str
    path: List[str]
    idx: int
    status: str
    dist_m: float
    replans: int

def build_scene(conn, force_sources: List[str]):
    G_full, G_masked, meta = build_filtered_graph(
        conn, DUAL, LEVEL,
        score_umbral=SCORE_UMBRAL_LOCAL,
        allowed_locomotions=ALLOWED_LOCOMOTIONS_LOCAL,
        undirected=True,
        force_sources=force_sources  # <-- fuerza orígenes
    )
    exits = find_exit_nodes(conn, DUAL, LEVEL, include_windows=False)
    return G_full, G_masked, meta, exits

def edge_key(a, b): return tuple(sorted((a, b)))

def effective_time(G: nx.Graph, u: str, v: str, on_edge_count: int) -> float:
    base = G[u][v]["length"] / V_MPS
    overload = max(0, on_edge_count - CAPACITY)
    return base * (1.0 + ALPHA * (overload / max(1, CAPACITY)))

def simulate(starts: List[str]):
    conn = get_conn()
    G_full, G, meta, exits = build_scene(conn, force_sources=starts)

    # Diagnóstico: por qué se filtrarían
    diag = explain_filtering(meta, starts)
    for s in starts:
        if s not in G_full:
            print(f"[WARN] {s} no existe en DUAL/LEVEL actuales.")
        elif s not in G:
            print(f"[INFO] {s} fue forzado dentro del grafo (sin vecinos no permitidos). Motivo filtro: {diag[s]}")

    agents: List[Agent] = []
    aid = 0
    for src in starts:
        if src not in G:
            print(f"[WARN] {src} no está ni siquiera tras forzar; se ignora.")
            continue
        aid += 1
        p = shortest_to_any_target(G, src, exits)
        if p is None:
            # probar ventanas
            exits2 = find_exit_nodes(conn, DUAL, LEVEL, include_windows=True)
            p = shortest_to_any_target(G, src, exits2)
            if p is not None:
                exits = exits2
        if p is None:
            print(f"[WARN] {src} sin ruta; agente queda 'stuck'.")
            agents.append(Agent(aid, src, [src], 0, "stuck", 0.0, 0))
        else:
            agents.append(Agent(aid, src, p, 0, "moving", 0.0, 0))

    t, last_refresh = 0.0, 0.0
    on_edge: Dict[tuple, int] = {}

    print(f"[SIM] {len(agents)} agentes. TICK={TICK}s; MAX_T={MAX_T}s")
    while t < MAX_T:
        if t - last_refresh >= REFRESH_S:
            last_refresh = t
            G_full, G, meta, exits = build_scene(conn, force_sources=[a.cur for a in agents])
            # replan
            for ag in agents:
                if ag.status != "moving": continue
                newp = shortest_to_any_target(G, ag.cur, exits)
                if newp is None:
                    exits2 = find_exit_nodes(conn, DUAL, LEVEL, include_windows=True)
                    newp = shortest_to_any_target(G, ag.cur, exits2)
                    if newp is not None: exits = exits2
                if newp is not None:
                    ag.path, ag.idx, ag.replans = newp, 0, ag.replans + 1

        on_edge.clear()
        # ocupación por tramo
        for ag in agents:
            if ag.status != "moving": continue
            if ag.idx >= len(ag.path)-1:
                ag.status = "done"; continue
            u, v = ag.path[ag.idx], ag.path[ag.idx+1]
            if u not in G or v not in G:
                ag.status = "stuck"; continue
            on_edge[edge_key(u, v)] = on_edge.get(edge_key(u, v), 0) + 1

        # avanzar
        for ag in agents:
            if ag.status != "moving": continue
            u, v = ag.path[ag.idx], ag.path[ag.idx+1]
            occ = on_edge.get(edge_key(u, v), 1)
            et = effective_time(G, u, v, occ)
            if TICK >= et:
                ag.cur = v
                ag.dist_m += G[u][v]["length"]
                ag.idx += 1
                if ag.idx >= len(ag.path)-1:
                    ag.status = "done"

        if int(t) % 5 == 0:
            mv = sum(a.status=='moving' for a in agents)
            dn = sum(a.status=='done' for a in agents)
            print(f"[t={t:5.1f}s] moving={mv} done={dn}")

        if all(a.status!='moving' for a in agents):
            print("[OK] todos terminaron o están bloqueados."); break

        t += TICK

    with OUT_CSV.open("w", encoding="utf-8") as f:
        f.write("agent_id,travel_s,dist_m,status,replans\n")
        for ag in agents:
            f.write(f"{ag.aid},{t:.1f},{ag.dist_m:.2f},{ag.status},{ag.replans}\n")

    conn.close()
    print(f"[OK] guardado resumen → {OUT_CSV}")

if __name__ == "__main__":
    # pon aquí tus starts reales:
    simulate(starts=["ND-020","ND-006","ND-007","ND-002"])

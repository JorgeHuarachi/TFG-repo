# sim_multi.py
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import time
import psycopg2
import networkx as nx
from graph_utils import (
    get_conn, build_filtered_graph, find_exit_nodes, shortest_to_any_target
)

DUAL = "DU-01"
LEVEL = "P00"
SCORE_UMBRAL_LOCAL = 0.6
ALLOWED_LOCOMOTIONS_LOCAL = ("WALK","RAMP")
V_MPS = 1.2

TICK = 1.0   # s
REFRESH_S = 2.0
MAX_T = 600.0

# congestión
CAPACITY = 3      # capacidad deseada por tramo
ALPHA = 0.6       # penalización por sobrecarga relativa

OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True, parents=True)
OUT_CSV = OUT_DIR / "run_multi.csv"

@dataclass
class Agent:
    aid: int
    cur: str
    path: List[str]
    idx: int
    status: str  # moving|done|stuck
    dist_m: float
    replans: int

def build_scene(conn):
    G_full, G_masked, meta = build_filtered_graph(
        conn, DUAL, LEVEL,
        score_umbral=SCORE_UMBRAL_LOCAL,
        allowed_locomotions=ALLOWED_LOCOMOTIONS_LOCAL,
        undirected=True
    )
    exits = find_exit_nodes(conn, DUAL, LEVEL, include_windows=False)
    return G_full, G_masked, meta, exits

def effective_time(G: nx.Graph, u: str, v: str, on_edge_count: int) -> float:
    base = G[u][v]["length"] / V_MPS
    overload = max(0, on_edge_count - CAPACITY)
    return base * (1.0 + ALPHA * (overload / max(1, CAPACITY)))

def simulate(starts: List[str]):
    conn = get_conn()
    G_full, G, meta, exits = build_scene(conn)

    agents: List[Agent] = []
    for i, src in enumerate(starts, 1):
        if src not in G:
            print(f"[WARN] {src} no está en el grafo filtrado; se ignora.")
            continue
        p = shortest_to_any_target(G, src, exits)
        if p is None:
            # probar ventanas
            exits2 = find_exit_nodes(conn, DUAL, LEVEL, include_windows=True)
            p = shortest_to_any_target(G, src, exits2)
            if p is not None:
                exits = exits2
        if p is None:
            agents.append(Agent(i, src, [src], 0, "stuck", 0.0, 0))
        else:
            agents.append(Agent(i, src, p, 0, "moving", 0.0, 0))

    t = 0.0
    last_refresh = 0.0

    # mapa “quién está en cada tramo”
    def edge_key(a, b): return tuple(sorted((a, b)))
    on_edge: Dict[tuple, int] = {}

    print(f"[SIM] {len(agents)} agentes. TICK={TICK}s; MAX_T={MAX_T}s")
    while t < MAX_T:
        # replan global (cada REFRESH_S)
        if t - last_refresh >= REFRESH_S:
            last_refresh = t
            G_full, G, meta, exits = build_scene(conn)
            for ag in agents:
                if ag.status != "moving":
                    continue
                newp = shortest_to_any_target(G, ag.cur, exits)
                if newp is None:
                    exits2 = find_exit_nodes(conn, DUAL, LEVEL, include_windows=True)
                    newp = shortest_to_any_target(G, ag.cur, exits2)
                    if newp is not None:
                        exits = exits2
                if newp is not None:
                    ag.path = newp
                    ag.idx = 0
                    ag.replans += 1

        # limpia ocupación
        on_edge.clear()

        # contar ocupación de edge actual de cada agente (simplificado)
        for ag in agents:
            if ag.status != "moving":
                continue
            if ag.idx >= len(ag.path) - 1:
                ag.status = "done"
                continue
            u, v = ag.path[ag.idx], ag.path[ag.idx + 1]
            if u not in G or v not in G:
                ag.status = "stuck"
                continue
            on_edge[edge_key(u, v)] = on_edge.get(edge_key(u, v), 0) + 1

        # avanzar
        alive = 0
        for ag in agents:
            if ag.status != "moving":
                continue
            alive += 1
            u, v = ag.path[ag.idx], ag.path[ag.idx + 1]
            occ = on_edge.get(edge_key(u, v), 1)
            et = effective_time(G, u, v, occ)
            # si en este tick puede terminar el tramo, lo cruza
            if TICK >= et:
                ag.cur = v
                ag.dist_m += G[u][v]["length"]
                ag.idx += 1
                if ag.idx >= len(ag.path) - 1:
                    ag.status = "done"
            # si no, acumular "progreso" parcial (nos quedamos en u en este modelo por simplicidad)

        if int(t) % 5 == 0:
            print(f"[t={t:5.1f}s] moving={sum(a.status=='moving' for a in agents)} done={sum(a.status=='done' for a in agents)}")

        if all(a.status != "moving" for a in agents):
            print("[OK] todos terminaron o están bloqueados.")
            break

        t += TICK

    # resumen → CSV
    with OUT_CSV.open("w", encoding="utf-8") as f:
        f.write("agent_id,travel_s,dist_m,status,replans\n")
        for ag in agents:
            # travel_s = tiempo simulado total hasta estado final
            f.write(f"{ag.aid},{t:.1f},{ag.dist_m:.2f},{ag.status},{ag.replans}\n")

    conn.close()
    print(f"[OK] guardado resumen → {OUT_CSV}")

if __name__ == "__main__":
    # Cambia los orígenes aquí
    simulate(starts=["ND-020","ND-006","ND-007","ND-002"])

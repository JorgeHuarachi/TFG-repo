# sim_agent.py
import time
from pathlib import Path
import psycopg2
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from graph_utils import (
    get_conn, build_filtered_graph, find_exit_nodes, shortest_to_any_target,
    SCORE_UMBRAL, ALLOWED_LOCOMOTIONS
)

DUAL = "DU-01"
LEVEL = "P01"
SRC_NODE = "ND-020"
SCORE_UMBRAL_LOCAL = 0.6
ALLOWED_LOCOMOTIONS_LOCAL = ("WALK","RAMP")
V_MPS = 1.2
REFRESH_S = 1.0

OUT_DIR = Path("out")
OUT_DIR.mkdir(exist_ok=True, parents=True)
OUT_CSV = OUT_DIR / "run_agent.csv"
OUT_GIF = OUT_DIR / "run_agent.gif"

def build_scene(conn):
    G_full, G_masked, meta = build_filtered_graph(
        conn, DUAL, LEVEL,
        score_umbral=SCORE_UMBRAL_LOCAL,
        allowed_locomotions=ALLOWED_LOCOMOTIONS_LOCAL,
        undirected=True
    )
    exits = find_exit_nodes(conn, DUAL, LEVEL, include_windows=False)
    return G_full, G_masked, meta, exits

def run_and_animate():
    conn = get_conn()
    G_full, G, meta, exits = build_scene(conn)

    node_ids = meta["node_ids"]
    pos = meta["positions"]
    if SRC_NODE not in G:
        raise RuntimeError(f"Origen {SRC_NODE} no está en el grafo filtrado (revisa SCORE_UMBRAL o SRC_NODE).")

    # Ruta inicial a salidas normales
    path = shortest_to_any_target(G, SRC_NODE, exits)

    # Si no hay, prueba modo emergencia (ventanas)
    if path is None:
        print("[WARN] Sin ruta a salidas normales; probando ventanas…")
        exits2 = find_exit_nodes(conn, DUAL, LEVEL, include_windows=True)
        path = shortest_to_any_target(G, SRC_NODE, exits2)
        if path is None:
            raise RuntimeError("No hay ruta ni con ventanas (baja umbral o revisa datos).")
        else:
            exits = exits2

    # Prepara animación
    fig, ax = plt.subplots(figsize=(8, 6))
    # dibuja grafo base
    xy = np.array([pos[n] for n in G.nodes if n in pos])
    ax.scatter(xy[:,0], xy[:,1], s=20, alpha=0.8)
    for u, v in G.edges():
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], lw=0.8, alpha=0.5)

    # artista ruta (línea roja)
    line_path, = ax.plot([], [], lw=2.5, color="red")
    # agente (punto)
    agent_dot, = ax.plot([], [], marker="o", ms=8, color="red")

    ax.set_title("Agente y ruta dinámica")
    ax.axis("equal"); ax.set_xticks([]); ax.set_yticks([])

    # Estado de simulación
    t = 0.0
    cur = SRC_NODE
    cur_i = 0
    def route_xy(path_nodes):
        xs = [pos[n][0] for n in path_nodes if n in pos]
        ys = [pos[n][1] for n in path_nodes if n in pos]
        return xs, ys

    xs, ys = route_xy(path)
    line_path.set_data(xs, ys)
    x0, y0 = pos[cur]
    agent_dot.set_data([x0], [y0])   # <-- listas, no escalares

    # CSV log
    f = OUT_CSV.open("w", encoding="utf-8")
    f.write("t,cur_node,path_len\n")

    # variables para avance
    next_node = path[1] if len(path) > 1 else path[0]
    seg_len = G[cur][next_node]["length"]
    seg_time = seg_len / V_MPS
    seg_elapsed = 0.0
    last_replan = 0.0

    def step(dt):
        nonlocal t, cur, cur_i, next_node, seg_len, seg_time, seg_elapsed, last_replan, G, exits, path
        t += dt
        seg_elapsed += dt

        # replan periódica
        if t - last_replan >= REFRESH_S:
            last_replan = t
            # reconstruir grafo por si cambió score
            G_full2, G2, meta2, exits2 = build_scene(conn)
            G = G2
            exits = exits2
            # replan desde nodo actual
            new_path = shortest_to_any_target(G, cur, exits)
            if new_path is None:
                # probar ventanas
                exits3 = find_exit_nodes(conn, DUAL, LEVEL, include_windows=True)
                new_path = shortest_to_any_target(G, cur, exits3)
                if new_path is not None:
                    exits = exits3
            if new_path is not None:
                path[:] = new_path  # sustituye
                cur_i = 0
                if len(path) > 1:
                    next_node = path[1]
                    seg_len = G[cur][next_node]["length"]
                    seg_time = seg_len / V_MPS
                    seg_elapsed = 0.0
                xs, ys = route_xy(path)
                line_path.set_data(xs, ys)

        # si ya en destino
        if cur == path[-1]:
            return

        # avanza por el segmento actual (interpolación simple)
        if seg_time <= 1e-6:
            alpha = 1.0
        else:
            alpha = min(1.0, seg_elapsed / seg_time)

        xA, yA = pos[cur]
        xB, yB = pos[next_node]
        x = xA + alpha * (xB - xA)
        y = yA + alpha * (yB - yA)
        agent_dot.set_data([x], [y])  # listas

        if alpha >= 1.0:
            # llegó a next_node
            cur = next_node
            cur_i += 1
            f.write(f"{t:.2f},{cur},{len(path)}\n")
            if cur == path[-1]:
                return
            next_node = path[cur_i + 1]
            seg_len = G[cur][next_node]["length"]
            seg_time = seg_len / V_MPS
            seg_elapsed = 0.0

    def update(frame):
        step(0.1)  # 0.1 s por frame
        return line_path, agent_dot

    anim = FuncAnimation(fig, update, frames=600, interval=50, blit=False)
    try:
        anim.save(OUT_GIF, writer=PillowWriter(fps=20))
        print(f"[OK] GIF guardado → {OUT_GIF}")
    except Exception as e:
        print(f"[WARN] No se pudo guardar GIF: {e}. Abriendo ventana…")
        plt.show()

    f.close()
    conn.close()

if __name__ == "__main__":
    run_and_animate()

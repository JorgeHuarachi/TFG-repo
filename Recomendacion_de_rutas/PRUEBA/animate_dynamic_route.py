# animate_dynamic_route.py
# Recalcula dinámicamente la ruta desde un origen fijo a la mejor salida,
# coloreando nodos por "score" (0..1) que varía con el tiempo.
# Usa build_score_fn(node_ids, scenario, default, ema_alpha, combine).

from __future__ import annotations
from typing import Optional, Dict, Iterable, Set, Tuple, List
import numpy as np
import psycopg2
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.animation import FuncAnimation

from sim_scores import build_score_fn  # <-- API estable

# --------------------- Config BD ---------------------
DB_CFG = dict(
    host="localhost",
    dbname="SIMULAR",      # <--- cámbialo si procede
    user="postgres",
    password="DB032122"
)

DUAL_ID = "DU-01"
LEVEL   = "P01"           # o None para todos los niveles
UNDIRECTED = True

# (Opcional) movilidad
APPLY_MOBILITY_FILTER = False
ALLOWED_LOCOMOTIONS   = ("WALK", "RAMP")
TREAT_GENERAL_AS_WALK = False

# Simulación/visualización
SOURCE_NODE = "ND-020"        # si None, usa el primer nodo ordenado
TAU = 0.60                # umbral de seguridad (0..1)
DT  = 0.50                # segundos simulados por frame
N_FRAMES = 400
EMA_ALPHA = 0.30          # suavizado; None para desactivar
SAVE_GIF = False
OUT_GIF  = "route_dynamics.gif"

# (Opcional) salidas manuales (si la BD no las tiene marcadas)
EMERGENCY_EXIT_NODE_IDS: Set[str] = set()  # e.g., {"ND-021","ND-030"}

# --------------------- Carga del grafo desde PostGIS ---------------------
def fetch_graph_from_db(
    conn,
    dual_id: str,
    level: Optional[str] = None,
    undirected: bool = True,
    apply_mobility: bool = False,
    allowed_locomotions: Iterable[str] = ("WALK","RAMP"),
    treat_general_as_walk: bool = False
) -> Dict:
    with conn.cursor() as cur:
        # Nodos con coord XY
        cur.execute(
            """
            SELECT
              n.id_node, n.id_cell_space,
              ST_X(n.geom) AS x, ST_Y(n.geom) AS y
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            WHERE n.id_dual = %s
              AND (%s::text IS NULL OR cs.level = %s)
            ORDER BY n.id_node
            """,
            (dual_id, level, level)
        )
        rows_nodes = cur.fetchall()
        if not rows_nodes:
            raise RuntimeError("No hay nodos para esa dual/level.")

        node_ids = [r[0] for r in rows_nodes]
        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        positions = {r[0]: (r[2], r[3]) for r in rows_nodes if r[2] is not None and r[3] is not None}

        # Aristas
        cur.execute(
            """
            SELECT e.from_node, e.to_node, e.weight_m
            FROM indoorgml_core.edge e
            JOIN indoorgml_core.node na ON na.id_node = e.from_node
            JOIN indoorgml_core.node nb ON nb.id_node = e.to_node
            JOIN indoorgml_core.cell_space csa ON csa.id_cell_space = na.id_cell_space
            JOIN indoorgml_core.cell_space csb ON csb.id_cell_space = nb.id_cell_space
            WHERE e.id_dual = %s
              AND (%s::text IS NULL OR (csa.level = %s AND csb.level = %s))
            """,
            (dual_id, level, level, level)
        )
        rows_edges = cur.fetchall()

        # Nodos marcados como salidas de emergencia (si existen)
        cur.execute(
            """
            SELECT n.id_node
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            JOIN indoorgml_navigation.navigable_space ns ON ns.id_cell_space = cs.id_cell_space
            WHERE n.id_dual = %s
              AND (%s::text IS NULL OR cs.level = %s)
              AND ns.is_emergency_exit = TRUE
            """,
            (dual_id, level, level)
        )
        ex_rows = cur.fetchall()
        emergency_nodes_from_db = {r[0] for r in ex_rows}

        # (Opcional) movilidad: máscara booleana por nodo_id
        mobility_mask = None
        if apply_mobility:
            cur.execute(
                """
                SELECT
                  n.id_node,
                  CASE
                    WHEN ns.locomotion::text = ANY(%s::text[]) THEN TRUE
                    WHEN %s::boolean IS TRUE AND ns.locomotion IS NULL AND ns.kind = 'GENERAL' THEN TRUE
                    ELSE FALSE
                  END AS allowed
                FROM indoorgml_core.node n
                JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
                LEFT JOIN indoorgml_navigation.navigable_space ns ON ns.id_cell_space = cs.id_cell_space
                WHERE n.id_dual = %s
                  AND (%s::text IS NULL OR cs.level = %s)
                ORDER BY n.id_node
                """,
                (list(allowed_locomotions), treat_general_as_walk, dual_id, level, level)
            )
            rows_mob = cur.fetchall()
            allowed_vec = np.array([bool(r[1]) for r in rows_mob], dtype=bool)
            mobility_mask = {nid: ok for (nid, _), ok in zip(rows_mob, allowed_vec)}

    # Grafo
    G = nx.Graph() if undirected else nx.DiGraph()
    G.add_nodes_from(node_ids)
    for u, v, w in rows_edges:
        if w is not None and w > 0 and u in node_to_idx and v in node_to_idx:
            G.add_edge(u, v, weight=float(w))

    return {
        "node_ids": node_ids,
        "node_to_idx": node_to_idx,
        "positions": positions,
        "edges": rows_edges,
        "G": G,
        "mobility_mask": mobility_mask,
        "emergency_nodes_db": emergency_nodes_from_db
    }

# --------------------- MAIN ---------------------
def main():
    # Conexión BD
    conn = psycopg2.connect(**DB_CFG)
    data = fetch_graph_from_db(
        conn,
        dual_id=DUAL_ID,
        level=LEVEL,
        undirected=UNDIRECTED,
        apply_mobility=APPLY_MOBILITY_FILTER,
        allowed_locomotions=ALLOWED_LOCOMOTIONS,
        treat_general_as_walk=TREAT_GENERAL_AS_WALK
    )
    conn.close()

    node_ids = data["node_ids"]
    positions = data["positions"]
    G = data["G"]

    # Origen fijo
    source = SOURCE_NODE or node_ids[0]

    # Salidas de emergencia (BD o fallback manual)
    emergency_nodes = set(EMERGENCY_EXIT_NODE_IDS) or set(data["emergency_nodes_db"])
    if not emergency_nodes:
        print("[AVISO] No hay salidas en BD ni definidas. Usa EMERGENCY_EXIT_NODE_IDS para fijarlas.")
        emergency_nodes = {source}

    # -------------- Escenario de scores dinámicos --------------
    # Edita aquí: por cada nodo, lista de ventanas (ramp/triangle/hold)
    # ("ramp", t0, dur, v_from, v_to) — baja/sube lineal
    # ("triangle", t0, dur, v_min, v_max) — baja y sube simétrico
    # ("hold", t0, dur, v) — valor constante un intervalo
    SCENARIO = {
    # ND-011: baja primero (temprano)
    # 10..35 s: 1.0 -> 0.50 (rampa descendente)
    "ND-011": [
        ("ramp", 10.0, 25.0, 1.00, 0.50)
    ],

    # ND-010: baja después de ND-011
    # 40..60 s: 1.0 -> 0.40 (rampa descendente)
    "ND-010": [
        ("ramp", 40.0, 20.0, 1.00, 0.40)
    ],
    # ND-018: baja y luego sube
    # Arranca DESPUÉS de que ND-010 termina (ND-010 acaba en t=60 s); añadimos margen de 5 s.
    # 65..80 s: 1.0 -> 0.50 (rampa descendente)
    # 85..100 s: 0.50 -> 1.0 (rampa ascendente)
    "ND-018": [
        ("ramp", 65.0, 15.0, 1.00, 0.50),
        ("ramp", 85.0, 15.0, 0.50, 1.00)
        # Si quieres dejar explícito que se mantiene arriba, podrías añadir:
        # ("hold", 100.0, 999.0, 1.0)  # ya fuera de horizonte, sólo documental
    ],
}
 

    # Construye la función de scores (vector) y el reset (todo a 1.0)
    score_fn, reset_scores = build_score_fn(
        node_ids=node_ids,
        scenario=SCENARIO,
        default=1.0,
        ema_alpha=EMA_ALPHA,
        combine="min"
    )

    # ------------------ Figura (una sola colorbar) ------------------
    fig, ax = plt.subplots(figsize=(12, 8))

    # Si no hay XY en BD para algún nodo, usa layout de NetworkX
    if not positions:
        positions = nx.spring_layout(G, seed=42)

    # Dibuja edges una vez
    nx.draw_networkx_edges(G, positions, ax=ax, width=1.2, edge_color="#B0B0B0", alpha=0.9)

    # Dibuja nodos (guardamos el artista para actualizar colores)
    nodes_artist = nx.draw_networkx_nodes(
        G, positions, nodelist=node_ids, ax=ax,
        node_size=420, node_color="#dddddd", edgecolors="#333333", linewidths=1.0
    )
    # Etiquetas
    nx.draw_networkx_labels(G, positions, ax=ax, font_size=9)

    # Colorbar única
    norm = mpl.colors.Normalize(vmin=0.0, vmax=1.0)
    cmap = mpl.cm.get_cmap("RdYlGn")
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("score de seguridad (0–1)")

    # Línea para la ruta
    path_line, = ax.plot([], [], lw=4, color="#ff6b6b")
    title_text = ax.text(0.02, 0.98, "", transform=ax.transAxes,
                         va="top", ha="left",
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    ax.set_title("Ruta dinámica (origen fijo → mejor salida) con score(t)")
    ax.axis("equal")
    ax.set_xticks([]); ax.set_yticks([])

    # Helper para colorear nodos por score (score es vector alineado con node_ids)
    def set_node_facecolors(score_vec: np.ndarray):
        colors = [cmap(norm(float(score_vec[i]))) for i in range(len(node_ids))]
        nodes_artist.set_facecolor(colors)

    mobility_mask = data["mobility_mask"]  # dict nid -> bool, o None
    prev_scores: Optional[np.ndarray] = None  # para EMA

    # init: reset total de scores
    def init():
        nonlocal prev_scores
        prev_scores = reset_scores()            # todo a 1.0
        s0 = score_fn(0.0, prev_scores=prev_scores)  # inicial (aplica EMA si procede)
        prev_scores = s0
        set_node_facecolors(s0)
        path_line.set_data([], [])
        title_text.set_text("t=0.0s | coste=–")
        return nodes_artist, path_line, title_text

    def best_exit_path(H: nx.Graph, src: str, exits: Set[str]) -> Tuple[Optional[List[str]], float]:
        best_path, best_cost = None, float("inf")
        for ex in exits:
            if src in H and ex in H:
                try:
                    p = nx.shortest_path(H, src, ex, weight="weight")
                    c = nx.path_weight(H, p, weight="weight")
                    if c < best_cost:
                        best_cost, best_path = c, p
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
        return best_path, best_cost

    def animate(frame):
        nonlocal prev_scores
        t = frame * DT
        scores = score_fn(t, prev_scores=prev_scores)  # vector
        prev_scores = scores
        set_node_facecolors(scores)

        # Filtrado por seguridad (y movilidad si aplica)
        safe_nodes = [node_ids[i] for i in range(len(node_ids)) if float(scores[i]) >= TAU]
        if mobility_mask is not None:
            safe_nodes = [n for n in safe_nodes if mobility_mask.get(n, False)]

        H = G.subgraph(safe_nodes).copy()

        # Ruta al mejor exit
        path, cost = best_exit_path(H, source, emergency_nodes)
        if path:
            xs = [positions[n][0] for n in path]
            ys = [positions[n][1] for n in path]
            path_line.set_data(xs, ys)
            title_text.set_text(f"t={t:.1f}s | coste={cost:.2f} | nodos={len(path)}")
        else:
            path_line.set_data([], [])
            title_text.set_text(f"t={t:.1f}s | sin ruta")

        return nodes_artist, path_line, title_text

    anim = FuncAnimation(
        fig, animate, init_func=init, frames=N_FRAMES,
        interval=80, blit=False, repeat=False
    )

    if SAVE_GIF:
        try:
            fps = max(1, int(round(1.0 / max(DT, 0.1))))
            anim.save(OUT_GIF, writer="pillow", fps=fps)
            print(f"[OK] Guardado GIF: {OUT_GIF}")
        except Exception as e:
            print(f"[AVISO] No se pudo guardar GIF: {e}")

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()

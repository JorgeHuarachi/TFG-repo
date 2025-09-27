# -*- coding: utf-8 -*-
"""
Agente: start -> goal con:
 - filtro de movilidad (WALK/RAMP, opcional GENERAL como WALK)
 - filtro de seguridad por score (>= S_MIN)
 - ruta mínima Dijkstra (recalcula al llegar a nodo y si cambian condiciones)
 - animación con recoloreo dinámico, HUD y colorbar

Requisitos:
  pip install psycopg2-binary networkx numpy matplotlib pillow pandas
"""

import os
from datetime import datetime

import numpy as np
import psycopg2
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import colormaps as cmaps  # <- evita deprecación get_cmap()

# ------------------- CONFIG -------------------

DSN = dict(host="localhost", dbname="SIMULACION", user="postgres", password="DB032122", port=5432)

DUAL_ID    = "DU-01"
LEVEL      = "P00"
START_NODE = "ND-020"
GOAL_NODE  = "ND-019"

# Filtro movilidad
ALLOWED_LOCOMOTIONS   = ("WALK", "RAMP")
TREAT_GENERAL_AS_WALK = False   # si True, ns.kind='GENERAL' cuenta como permitido

# Filtro seguridad
S_MIN                 = 0.30     # umbral de seguridad por celda
POLL_SCORES_EVERY     = 1.0      # s entre lecturas de score (y recoloreo)
RELAX_ON_BLOCK        = True     # si no hay ruta con S_MIN, intenta con 0.0

# Replanificación
RECOMPUTE_ON_NODE_ONLY      = True    # recalcular sólo al llegar a un nodo
RECOMPUTE_MIN_INTERVAL_S    = 2.0     # no recalcular más a menudo que esto
RECOMPUTE_ON_ALLOWED_CHANGE = True    # dispara replan si cambia el conjunto permitido
ALLOWED_CHANGE_EPS          = 0.05    # cambio mínimo de score para considerar “cambio relevante”

# Animación
FRAMES_PER_EDGE     = 25       # frames para cruzar una arista
FPS                 = 10
SHOW_NODE_LABELS    = False    # dibuja IDs de nodos
SHOW_NUMERIC_SCORES = False    # dibuja el score numérico sobre cada nodo (puede saturar)
DRAW_VISITED_EDGES  = True

# Salidas
OUT_DIR  = "out"
GIF_PATH = os.path.join(OUT_DIR, "agent.gif")
CSV_PATH = os.path.join(OUT_DIR, "run_agent.csv")

# ------------------------------------------------


def connect():
    return psycopg2.connect(**DSN)


def fetch_graph_with_mobility(conn, dual_id, level, allowed_locomotions, treat_general_as_walk):
    """
    Carga nodos/edges y marca si cada nodo pasa el filtro de movilidad.
    """
    with conn.cursor() as cur:
        # NODOS + flag movilidad
        cur.execute(
            """
            SELECT
              n.id_node,
              cs.id_cell_space,
              ST_X(n.geom) AS x,
              ST_Y(n.geom) AS y,
              CASE
                WHEN ns.locomotion::text = ANY(%s) THEN TRUE
                WHEN %s::boolean IS TRUE AND ns.locomotion IS NULL AND ns.kind = 'GENERAL' THEN TRUE
                ELSE FALSE
              END AS mob_ok
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            LEFT JOIN indoorgml_navigation.navigable_space ns ON ns.id_cell_space = cs.id_cell_space
            WHERE n.id_dual = %s
              AND (%s::text IS NULL OR cs.level = %s)
            ORDER BY n.id_node
            """,
            (list(allowed_locomotions), treat_general_as_walk, dual_id, level, level)
        )
        rn = cur.fetchall()
        if not rn:
            raise RuntimeError("No hay nodos para esa dual/level.")
        node_ids   = [r[0] for r in rn]
        node2cell  = {r[0]: r[1] for r in rn}
        pos        = {r[0]: (float(r[2]), float(r[3])) for r in rn if r[2] is not None and r[3] is not None}
        mob_ok_set = {r[0] for r in rn if r[4]}

        # EDGES
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
        re = cur.fetchall()

    G = nx.Graph()
    G.add_nodes_from(node_ids)
    for u, v, w in re:
        if u in pos and v in pos and w and w > 0:
            G.add_edge(u, v, weight=float(w))

    return G, pos, node2cell, mob_ok_set


def fetch_scores(conn):
    """cell_space -> score (si falta, tratamos como 1.0)"""
    with conn.cursor() as cur:
        cur.execute("SELECT id_cell_space, score FROM iot.v_cell_score_latest;")
        rows = cur.fetchall()
    return {cs: float(s) for cs, s in rows}


def allowed_by_security(G, node2cell, scores, s_min):
    ok = set()
    for n in G.nodes():
        s = scores.get(node2cell.get(n), 1.0)
        if s >= s_min:
            ok.add(n)
    return ok


def color_nodes(nodelist, node2cell, scores, s_min, mob_ok_set):
    """Colores por score; gris si movilidad no permitida o score < s_min."""
    cmap = cmaps["RdYlGn"]
    colors = []
    for n in nodelist:
        s = scores.get(node2cell.get(n), 1.0)
        if (n not in mob_ok_set) or (s < s_min):
            colors.append((0.7, 0.7, 0.7, 0.35))
        else:
            s_clamped = max(0.0, min(1.0, s))
            r, g, b, _ = cmap(s_clamped)
            colors.append((r, g, b, 0.95))
    return colors


def changed_cells(prev, curr, s_min, eps=0.2, max_items=6):
    """
    Lista corta de celdas cuyo estado SAFE/DANGER ha cambiado o variación >= eps.
    Devuelve texto para HUD.
    """
    out = []
    keys = set(prev.keys()) | set(curr.keys())
    for cs in keys:
        p = prev.get(cs, 1.0)
        c = curr.get(cs, 1.0)
        flip = (p >= s_min) != (c >= s_min)
        big  = abs(c - p) >= eps
        if flip or big:
            out.append((cs, c, p))
    out.sort(key=lambda t: abs(t[1]-t[2]), reverse=True)
    out = out[:max_items]
    if not out:
        return "Δcells: —"
    return "Δcells: " + ", ".join(f"{cs}({v:.2f})" for cs, v, _ in out)


def sim():
    os.makedirs(OUT_DIR, exist_ok=True)

    # --- GRAFO BASE + MOVILIDAD ---
    with connect() as conn:
        G, pos, node2cell, mob_ok = fetch_graph_with_mobility(
            conn, DUAL_ID, LEVEL, ALLOWED_LOCOMOTIONS, TREAT_GENERAL_AS_WALK
        )
        scores = fetch_scores(conn)

    if START_NODE not in G or GOAL_NODE not in G:
        raise RuntimeError("START/GOAL no están en el grafo.")

    nodelist = list(pos.keys())
    xs = np.array([pos[n][0] for n in nodelist])
    ys = np.array([pos[n][1] for n in nodelist])

    # helper para construir grafo permitido por movilidad+seguridad
    def build_allowed_graph(scores_now, s_min):
        allowed_sec = allowed_by_security(G, node2cell, scores_now, s_min)
        allowed = (mob_ok & allowed_sec)
        return G.subgraph(allowed).copy(), allowed

    # primer grafo y ruta (relaja si hace falta)
    s_min = S_MIN
    for attempt in (1, 2):
        G_ok, allowed = build_allowed_graph(scores, s_min)
        try:
            path = nx.shortest_path(G_ok, START_NODE, GOAL_NODE, weight="weight")
            break
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            if RELAX_ON_BLOCK and attempt == 1:
                print("[WARN] sin ruta con s_min -> relajo a 0.0")
                s_min = 0.0
            else:
                raise

    # --------------- DIBUJO BASE ---------------
    fig, ax = plt.subplots(figsize=(9, 7))
    # edges
    for u, v in G.edges():
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], lw=1.2, color="#B0B0B0", alpha=0.6, zorder=0)
    # nodes coloreados por score actual
    scat = ax.scatter(xs, ys, s=420, edgecolors="#243447",
                      c=color_nodes(nodelist, node2cell, scores, s_min, mob_ok))
    # colorbar para scores
    sm = plt.cm.ScalarMappable(cmap=cmaps["RdYlGn"], norm=plt.Normalize(vmin=0, vmax=1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax, fraction=0.046, pad=0.02)
    cbar.set_label("score de seguridad (0–1)")

    # path restante (rojo) y visitado (granate)
    rem_lines = []
    vis_lines = []

    def draw_remaining(pnodes):
        for l in rem_lines: l.remove()
        rem_lines.clear()
        for a, b in zip(pnodes[:-1], pnodes[1:]):
            if a in pos and b in pos:
                ln, = ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]],
                              lw=3.0, color="#ff5252", alpha=0.95, zorder=2)
                rem_lines.append(ln)

    draw_remaining(path)
    # agente
    agent_dot, = ax.plot([], [], "o", ms=10, color="#1b9e77", zorder=3)
    # labels opcionales
    id_labels = {}
    if SHOW_NODE_LABELS:
        for n in nodelist:
            id_labels[n] = ax.text(pos[n][0], pos[n][1], n, fontsize=7, ha="center", va="center")

    score_labels = {}
    if SHOW_NUMERIC_SCORES:
        # textos con score numérico (se actualizan al poll)
        for n in nodelist:
            s = scores.get(node2cell.get(n), 1.0)
            score_labels[n] = ax.text(pos[n][0], pos[n][1]-0.6, f"{s:.2f}", fontsize=7,
                                      ha="center", va="center", color="black")

    hud = ax.text(0.02, 0.98, "", transform=ax.transAxes, va="top", ha="left",
                  bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Agente con recalculo controlado (movilidad + seguridad)")
    plt.tight_layout()

    # --------------- ESTADO SIM ---------------
    cur_i = 0                   # índice de nodo del path
    step_in_edge = 0            # frame dentro de la arista
    frames = 0
    recomputes = 0
    prev_scores = scores.copy()
    poll_each_frames = max(1, int(POLL_SCORES_EVERY * FPS))
    min_frames_between_recompute = max(1, int(RECOMPUTE_MIN_INTERVAL_S * FPS))
    last_recompute_frame = -min_frames_between_recompute
    last_allowed_set = allowed.copy()

    # posición inicial
    x0, y0 = pos[path[0]]
    agent_dot.set_data([x0], [y0])

    # Para este script, blit=False simplifica cuando hay muchos artistas
    def update(_):
        nonlocal frames, step_in_edge, cur_i, path, scores, prev_scores, recomputes
        nonlocal G_ok, allowed, last_recompute_frame, last_allowed_set

        # 1) refresca scores periódicamente + recolor (y etiquetas numéricas si toca)
        if frames % poll_each_frames == 0:
            prev_scores = scores
            with connect() as c2:
                scores = fetch_scores(c2)
            scat.set_color(color_nodes(nodelist, node2cell, scores, s_min, mob_ok))
            if SHOW_NUMERIC_SCORES:
                for n in nodelist:
                    s = scores.get(node2cell.get(n), 1.0)
                    score_labels[n].set_text(f"{s:.2f}")

            # si queremos disparar replan por cambio de permitido, calculamos allowed_now
            if RECOMPUTE_ON_ALLOWED_CHANGE and RECOMPUTE_ON_NODE_ONLY and step_in_edge == 0:
                # allowed con el umbral actual
                G_tmp, allowed_now = build_allowed_graph(scores, s_min)
                # detecta cambios relevantes (no miramos sólo dif. de conjuntos, también “margen” por eps)
                # aquí hacemos diff puro; si quieres eps real por celda, compáralo con prev_scores en otro paso
                changed = (allowed_now != last_allowed_set)
                allowed = allowed_now
                G_ok = G_tmp
                if changed and (frames - last_recompute_frame >= min_frames_between_recompute):
                    # recomputa ruta desde el nodo actual
                    anchor = path[cur_i]
                    try:
                        path = path[:cur_i] + nx.shortest_path(G_ok, anchor, GOAL_NODE, weight="weight")
                        draw_remaining(path[cur_i:])
                        recomputes += 1
                        last_recompute_frame = frames
                        last_allowed_set = allowed_now
                    except (nx.NetworkXNoPath, nx.NodeNotFound):
                        # no hay ruta ahora mismo: se muestra en HUD y el agente espera en nodo
                        hud.set_text(f"t={frames/FPS:.1f}s  s_min={s_min:.2f}  recomputes={recomputes}\n"
                                     f"ruta bloqueada; esperando cambios…\n"
                                     f"{changed_cells(prev_scores, scores, s_min)}")
                        frames += 1
                        return

        # 2) replan periódico (sólo al llegar a nodo)
        if RECOMPUTE_ON_NODE_ONLY and step_in_edge == 0:
            if frames - last_recompute_frame >= min_frames_between_recompute:
                # recalcula desde el nodo actual con allowed/scores que tenemos ahora
                G_ok, allowed = build_allowed_graph(scores, s_min)
                anchor = path[cur_i]
                try:
                    path = path[:cur_i] + nx.shortest_path(G_ok, anchor, GOAL_NODE, weight="weight")
                    draw_remaining(path[cur_i:])
                    recomputes += 1
                    last_recompute_frame = frames
                    last_allowed_set = allowed.copy()
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    hud.set_text(f"t={frames/FPS:.1f}s  s_min={s_min:.2f}  recomputes={recomputes}\n"
                                 f"ruta bloqueada; esperando cambios…\n"
                                 f"{changed_cells(prev_scores, scores, s_min)}")
                    frames += 1
                    return

        # 3) avanzar por la arista actual si existe
        if cur_i >= len(path) - 1:
            # llegó
            x, y = pos[path[-1]]
            agent_dot.set_data([x], [y])
            hud.set_text(f"t={frames/FPS:.1f}s  s_min={s_min:.2f}  recomputes={recomputes}\n"
                         f"FIN @ {path[-1]}\n{changed_cells(prev_scores, scores, s_min)}")
            frames += 1
            return

        a = path[cur_i]
        b = path[cur_i + 1]
        x0, y0 = pos[a]; x1, y1 = pos[b]
        t = step_in_edge / float(FRAMES_PER_EDGE)
        x = x0 + t * (x1 - x0)
        y = y0 + t * (y1 - y0)
        agent_dot.set_data([x], [y])

        # HUD
        hud.set_text(
            f"t={frames/FPS:.1f}s  s_min={s_min:.2f}  recomputes={recomputes}\n"
            f"{a}→{b} | score({node2cell[a]})={scores.get(node2cell[a],1.0):.2f}\n"
            f"{changed_cells(prev_scores, scores, s_min)}"
        )

        # avanza “frame”
        step_in_edge += 1
        if step_in_edge >= FRAMES_PER_EDGE:
            # llega a b
            step_in_edge = 0
            # pinta como visitado
            if DRAW_VISITED_EDGES:
                ln, = ax.plot([x0, x1], [y0, y1], lw=3.0, color="#8b1b1b", alpha=0.9, zorder=1)
                vis_lines.append(ln)
            cur_i += 1

        frames += 1

    # OJO: con muchos artistas, mejor blit=False
    anim = FuncAnimation(fig, update, frames=100000, interval=1000.0/FPS, blit=False)
    try:
        anim.save(GIF_PATH, writer="pillow", dpi=120, fps=FPS)
    except Exception as ex:
        print(f"[WARN] error guardando GIF: {ex}; guardo PNG")
        fig.savefig(GIF_PATH.replace(".gif", ".png"), dpi=120)
    plt.close(fig)

    # CSV resumen (ruta final y stats)
    try:
        dist = nx.path_weight(G, path, weight="weight")
    except Exception:
        dist = 0.0
    row = {
        "ts": datetime.utcnow().isoformat(),
        "level": LEVEL,
        "start": START_NODE,
        "goal": GOAL_NODE,
        "s_min": s_min,
        "recomputes": recomputes,
        "nodes_in_path_final": len(path),
        "dist_m": round(dist, 3),
        "path": "->".join(path)
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", encoding="utf-8") as f:
        if new:
            f.write(",".join(row.keys()) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")

    print(f"[DONE] GIF: {GIF_PATH}")
    print(f"[DONE] CSV: {CSV_PATH}")


if __name__ == "__main__":
    sim()

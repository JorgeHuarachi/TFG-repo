# graph_utils.py
from typing import Dict, Tuple, List, Optional, Iterable
import psycopg2
import numpy as np
import networkx as nx

DB = dict(host="localhost", dbname="SIMULAR", user="postgres", password="DB032122")

# Parámetros por defecto (puedes sobreescribir desde los otros scripts)
SCORE_UMBRAL: float = 0.6
ALLOWED_LOCOMOTIONS: Tuple[str, ...] = ("WALK", "RAMP")
WINDOW_FUNCS: Tuple[str, ...] = ("WINDOW", "VENTANA")
TREAT_GENERAL_AS_WALK: bool = True  # GENERAL (sin locomotion) cuenta como permitido

def get_conn():
    return psycopg2.connect(**DB)

def fetch_nodes_positions_and_flags(
    conn,
    dual_id: str,
    level: Optional[str],
    score_umbral: float,
    allowed_locomotions: Iterable[str],
    treat_general_as_walk: bool
):
    """Obtiene nodos (id, pos), su cell_space y flags de permitidos por movilidad + score."""
    with conn.cursor() as cur:
        # Nodos con su CellSpace, locomoción y último score
        cur.execute(
            """
            SELECT
              n.id_node,
              n.id_cell_space,
              cs.level,
              ST_X(n.geom) AS x,
              ST_Y(n.geom) AS y,
              ns.kind,
              ns.locomotion,
              ns.function_code,
              sl.score
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            LEFT JOIN indoorgml_navigation.navigable_space ns ON ns.id_cell_space = cs.id_cell_space
            LEFT JOIN iot.v_cell_score_latest sl ON sl.id_cell_space = cs.id_cell_space
            WHERE n.id_dual = %s
              AND (%s::text IS NULL OR cs.level = %s)
            ORDER BY n.id_node
            """,
            (dual_id, level, level)
        )
        rows = cur.fetchall()

    node_ids = []
    positions = {}
    node_to_cell = {}
    cell_to_func = {}
    cell_to_score = {}

    allowed_locomotions = tuple(allowed_locomotions)
    allowed_mask = []

    for (nid, csid, lvl, x, y, kind, locomotion, function_code, score) in rows:
        node_ids.append(nid)
        if x is not None and y is not None:
            positions[nid] = (float(x), float(y))
        node_to_cell[nid] = csid
        cell_to_func[csid] = (function_code or "").upper()
        cell_to_score[csid] = float(score) if score is not None else 1.0

        # movilidad
        if kind == 'GENERAL' and treat_general_as_walk:
            mob_ok = True
        else:
            mob_ok = (locomotion is not None and locomotion in allowed_locomotions)

        # score
        sc_ok = (cell_to_score[csid] >= score_umbral)
        allowed_mask.append(bool(mob_ok and sc_ok))

    node_to_idx = {nid: i for i, nid in enumerate(node_ids)}
    idx_to_node = np.array(node_ids)

    return {
        "node_ids": node_ids,
        "positions": positions,
        "node_to_cell": node_to_cell,
        "cell_to_func": cell_to_func,
        "cell_to_score": cell_to_score,
        "allowed_mask": np.array(allowed_mask, dtype=bool),
        "node_to_idx": node_to_idx,
        "idx_to_node": idx_to_node
    }

def fetch_edges(conn, dual_id: str, level: Optional[str], undirected: bool=True):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.from_node, e.to_node, e.weight_m AS w
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
        rows = cur.fetchall()

    G = nx.Graph() if undirected else nx.DiGraph()
    for u, v, w in rows:
        if w is not None and w > 0:
            G.add_edge(u, v, weight=float(w), length=float(w))
    return G

def build_filtered_graph(
    conn,
    dual_id: str,
    level: Optional[str],
    score_umbral: float = SCORE_UMBRAL,
    allowed_locomotions: Iterable[str] = ALLOWED_LOCOMOTIONS,
    treat_general_as_walk: bool = TREAT_GENERAL_AS_WALK,
    undirected: bool = True
):
    """Construye grafo y anula aristas incidentes a nodos NO permitidos."""
    meta = fetch_nodes_positions_and_flags(
        conn, dual_id, level, score_umbral, allowed_locomotions, treat_general_as_walk
    )
    G_full = fetch_edges(conn, dual_id, level, undirected=undirected)

    # restringe a nodos conocidos
    G_full = G_full.subgraph(meta["node_ids"]).copy()

    # quita conexiones de nodos disallow
    allowed = meta["allowed_mask"]
    node_ids = meta["node_ids"]
    disallowed_nodes = {nid for nid, ok in zip(node_ids, allowed) if not ok}
    G_masked = G_full.copy()
    G_masked.remove_nodes_from(disallowed_nodes)

    return G_full, G_masked, meta

def find_exit_nodes(conn, dual_id: str, level: Optional[str], include_windows: bool=False) -> List[str]:
    """Devuelve los id_node que pertenecen a celdas de salida (o ventanas si include_windows)."""
    funcs = WINDOW_FUNCS if include_windows else tuple()
    params = [dual_id]
    where_win = ""
    if include_windows:
        where_win = "OR UPPER(ns.function_code) = ANY(%s)"
        params.append(list(funcs))

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT n.id_node
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            JOIN indoorgml_navigation.navigable_space ns ON ns.id_cell_space = cs.id_cell_space
            WHERE n.id_dual = %s
              AND (ns.is_emergency_exit = TRUE {where_win})
              AND (%s::text IS NULL OR cs.level = %s)
            ORDER BY n.id_node
            """,
            params + [level, level]
        )
        rows = cur.fetchall()
    return [r[0] for r in rows]

def shortest_to_any_target(G: nx.Graph, src: str, targets: List[str]) -> Optional[List[str]]:
    """Camino más corto a cualquiera de los targets. Devuelve lista de nodos o None."""
    best_path = None
    best_cost = float("inf")
    for t in targets:
        if t not in G:
            continue
        try:
            p = nx.shortest_path(G, src, t, weight="weight")
            c = nx.path_weight(G, p, weight="weight")
            if c < best_cost:
                best_cost, best_path = c, p
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue
    return best_path

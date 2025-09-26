# graph_utils.py
from typing import Optional, Iterable, Dict, Tuple, Set
import psycopg2, networkx as nx

ALLOWED_LOCOMOTIONS = ("WALK","RAMP")
WINDOW_FUNCS = ("WINDOW","VENTANA")   # para “último recurso”
SCORE_UMBRAL = 0.6

def _fetch_nodes_edges_scores(conn, dual_id, level):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT n.id_node, n.id_cell_space, cs.level,
                   ST_X(n.geom) AS x, ST_Y(n.geom) AS y,
                   ns.locomotion, ns.kind, ns.function_code, COALESCE(ns.is_emergency_exit,false) AS is_exit
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            LEFT JOIN indoorgml_navigation.navigable_space ns ON ns.id_cell_space = cs.id_cell_space
            WHERE n.id_dual = %s
              AND (%s::text IS NULL OR cs.level = %s)
            ORDER BY n.id_node;
        """, (dual_id, level, level))
        nodes = cur.fetchall()

        cur.execute("""
            SELECT e.from_node, e.to_node, e.weight_m
            FROM indoorgml_core.edge e
            JOIN indoorgml_core.node na ON na.id_node = e.from_node
            JOIN indoorgml_core.node nb ON nb.id_node = e.to_node
            JOIN indoorgml_core.cell_space ca ON ca.id_cell_space = na.id_cell_space
            JOIN indoorgml_core.cell_space cb ON cb.id_cell_space = nb.id_cell_space
            WHERE e.id_dual = %s
              AND (%s::text IS NULL OR (ca.level = %s AND cb.level = %s));
        """, (dual_id, level, level, level))
        edges = cur.fetchall()

        # v_cell_score_latest devuelve TODAS las celdas (sin score => 1.0)
        cur.execute("SELECT id_cell_space, score FROM iot.v_cell_score_latest;")
        score_by_cell = dict(cur.fetchall())

    return nodes, edges, score_by_cell

def build_graph_with_filters(
    conn,
    dual_id: str,
    level: Optional[str],
    allowed_locomotions: Iterable[str] = ALLOWED_LOCOMOTIONS,
    score_threshold: float = SCORE_UMBRAL,
    window_function_codes: Iterable[str] = WINDOW_FUNCS
):
    nodes, edges, score_by_cell = _fetch_nodes_edges_scores(conn, dual_id, level)

    G = nx.Graph()
    positions: Dict[str, Tuple[float,float]] = {}
    meta: Dict[str, dict] = {}
    exits: Set[str] = set()
    windows: Set[str] = set()

    # crear nodos
    for nid, csid, lvl, x, y, locom, kind, fcode, is_exit in nodes:
        G.add_node(nid)
        if x is not None and y is not None:
            positions[nid] = (float(x), float(y))
        score = float(score_by_cell.get(csid, 1.0))
        meta[nid] = dict(cell=csid, locom=locom, kind=kind, fcode=fcode, is_exit=bool(is_exit), score=score)
        if is_exit or (fcode and fcode.upper() in ("EXIT","EMERGENCY_EXIT")):
            exits.add(nid)
        if fcode and fcode.upper() in set(fc.upper() for fc in window_function_codes):
            windows.add(nid)

    # aristas
    for u, v, w in edges:
        if w and w > 0:
            G.add_edge(u, v, weight=float(w))

    # filtro movilidad + score
    allowed_loco = set(allowed_locomotions)
    keep = []
    for n in G.nodes:
        m = meta[n]
        ok_mob = (m["locom"] in allowed_loco) or (m["locom"] is None and m["kind"] == "GENERAL")
        ok_score = (m["score"] >= score_threshold)
        if ok_mob and ok_score:
            keep.append(n)

    G_masked = G.subgraph(keep).copy()
    return dict(G_full=G, G=G_masked, positions=positions, meta=meta,
                exits=exits, windows=windows, score_by_cell=score_by_cell)

def shortest_to_any(G: nx.Graph, src: str, targets: Iterable[str]):
    best, best_cost = None, float("inf")
    for t in targets:
        if src in G and t in G:
            try:
                p = nx.shortest_path(G, src, t, weight="weight")
                c = nx.path_weight(G, p, weight="weight")
                if c < best_cost:
                    best, best_cost = p, c
            except nx.NetworkXNoPath:
                pass
    return best, best_cost

def emergency_exits_if_needed(G: nx.Graph, src: str, exits: Set[str], windows: Set[str]):
    p, _ = shortest_to_any(G, src, exits)
    if p:  # hay ruta normal
        return exits, False
    # no hay ruta → activa ventanas como última opción
    return exits.union(windows), True

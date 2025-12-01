from typing import Optional, Dict, Iterable
import numpy as np
import psycopg2
import networkx as nx
import matplotlib.pyplot as plt

def fetch_graph_from_db(
    conn,
    dual_id: str,
    level: Optional[str] = None,
    undirected: bool = True,
    allowed_locomotions: Iterable[str] = ("WALK", "RAMP"),
    filter_mode: str = "mask",  # "mask" (por defecto) o "subgraph"
    treat_general_as_walk: bool = False
) -> Dict:
    """
    Carga grafo desde BD y aplica filtro de movilidad.
    - filter_mode="mask": mantiene todos los nodos pero pone a 0 toda arista incidente
      a nodos NO permitidos (WALK/RAMP). -> matriz del mismo tamaño que el total.
    - filter_mode="subgraph": devuelve el subgrafo solo con nodos permitidos (WALK/RAMP).
    """
    allowed_locomotions = tuple(allowed_locomotions)

    with conn.cursor() as cur:
        # --- NODOS + FLAG allowed ---
        # *** ARREGLO ENUM *** -> ns.locomotion::text = ANY(%s::text[])
        sql_nodes = """
            SELECT
              n.id_node,
              n.id_cell_space,
              cs.level,
              ST_X(n.geom) AS x,
              ST_Y(n.geom) AS y,
              CASE
                WHEN ns.locomotion::text = ANY(%s::text[]) THEN TRUE
                WHEN %s::boolean IS TRUE AND ns.locomotion IS NULL AND ns.kind = 'GENERAL' THEN TRUE
                ELSE FALSE
              END AS allowed
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs
              ON cs.id_cell_space = n.id_cell_space
            LEFT JOIN indoorgml_navigation.navigable_space ns
              ON ns.id_cell_space = cs.id_cell_space
            WHERE n.id_dual = %s
              AND (%s::text IS NULL OR cs.level = %s)
            ORDER BY n.id_node
        """
        cur.execute(
            sql_nodes,
            (list(allowed_locomotions), treat_general_as_walk, dual_id, level, level)
        )
        rows_nodes = cur.fetchall()
        if not rows_nodes:
            raise RuntimeError("No se encontraron nodos para esa dual/level.")

        node_ids = [r[0] for r in rows_nodes]
        positions = {r[0]: (r[3], r[4]) for r in rows_nodes if r[3] is not None and r[4] is not None}
        allowed_vec = np.array([bool(r[5]) for r in rows_nodes], dtype=bool)

        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        idx_to_node = np.array(node_ids)

        # --- ARISTAS (todas) ---
        sql_edges = """
            SELECT e.from_node, e.to_node, e.weight_m AS w
            FROM indoorgml_core.edge e
            JOIN indoorgml_core.node na ON na.id_node = e.from_node
            JOIN indoorgml_core.node nb ON nb.id_node = e.to_node
            JOIN indoorgml_core.cell_space csa ON csa.id_cell_space = na.id_cell_space
            JOIN indoorgml_core.cell_space csb ON csb.id_cell_space = nb.id_cell_space
            WHERE e.id_dual = %s
              AND (%s::text IS NULL OR (csa.level = %s AND csb.level = %s))
        """
        cur.execute(sql_edges, (dual_id, level, level, level))
        rows_edges = cur.fetchall()

    # --- Construye el grafo completo ---
    G_full = nx.Graph() if undirected else nx.DiGraph()
    G_full.add_nodes_from(node_ids)
    for u, v, w in rows_edges:
        if w is not None and w > 0 and u in node_to_idx and v in node_to_idx:
            G_full.add_edge(u, v, weight=float(w))

    # Matriz base (tamaño total)
    A_full = nx.to_numpy_array(G_full, nodelist=node_ids, weight='weight', dtype=float)
    if undirected:
        A_full = np.maximum(A_full, A_full.T)

    # --- Opción 1: MÁSCARA (mantener nodos, anular conexiones no permitidas) ---
    A_masked = A_full.copy()
    disallowed = ~allowed_vec
    if disallowed.any():
        A_masked[disallowed, :] = 0.0
        A_masked[:, disallowed] = 0.0
        if undirected:
            A_masked = np.maximum(A_masked, A_masked.T)

    # --- Opción 2: SUBGRAFO (quitar nodos no permitidos) ---
    allowed_nodes = [nid for nid, ok in zip(node_ids, allowed_vec) if ok]
    G_allowed = G_full.subgraph(allowed_nodes).copy()
    A_allowed = nx.to_numpy_array(G_allowed, nodelist=allowed_nodes, weight='weight', dtype=float) \
        if allowed_nodes else np.zeros((0, 0), dtype=float)
    if undirected and A_allowed.size:
        A_allowed = np.maximum(A_allowed, A_allowed.T)

    out = {
        "node_ids": node_ids,
        "positions": positions,
        "node_to_idx": node_to_idx,
        "idx_to_node": idx_to_node,
        "allowed_mask": allowed_vec,
        "G_full": G_full,
        "A_full": A_full,
        "A_masked": A_masked,
        "allowed_node_ids": allowed_nodes,
        "G_allowed": G_allowed,
        "A_allowed": A_allowed
    }
    if filter_mode == "subgraph":
        out["G"] = out["G_allowed"]
        out["A"] = out["A_allowed"]
    else:
        out["G"] = out["G_full"]
        out["A"] = out["A_masked"]
    return out


def draw_graph(
    G: nx.Graph,
    positions: Dict[str, tuple],
    node_ids: list,
    allowed_mask: np.ndarray
):
    """
    Dibuja el grafo. Resalta nodos permitidos (WALK/RAMP) y
    dibuja únicamente aristas cuyo par de nodos esté permitido.
    """
    # Si no hay posiciones en BD, usa un layout de NetworkX
    if not positions:
        positions = nx.spring_layout(G, seed=42)

    allowed_nodes = [nid for nid, ok in zip(node_ids, allowed_mask) if ok]
    disallowed_nodes = [nid for nid, ok in zip(node_ids, allowed_mask) if not ok]

    # Edges solo entre nodos permitidos (coherente con la matriz enmascarada)
    edgelist_allowed = [(u, v) for u, v in G.edges() if u in allowed_nodes and v in allowed_nodes]

    plt.figure(figsize=(10, 7))

    # Nodos no permitidos
    if disallowed_nodes:
        nx.draw_networkx_nodes(
            G, positions, nodelist=disallowed_nodes,
            node_size=380, node_color="#d9d9d9", edgecolors="#7a7a7a", linewidths=1.0
        )

    # Nodos permitidos
    if allowed_nodes:
        nx.draw_networkx_nodes(
            G, positions, nodelist=allowed_nodes,
            node_size=420, node_color="#9dd6ff", edgecolors="#2c5178", linewidths=1.2
        )

    # Aristas entre nodos permitidos
    nx.draw_networkx_edges(G, positions, edgelist=edgelist_allowed, width=1.6, edge_color="#8fa3b6", alpha=0.95)

    # Etiquetas de nodos
    nx.draw_networkx_labels(G, positions, font_size=9)

    plt.title("Grafo (WALK/RAMP permitidos — aristas solo entre nodos permitidos)")
    plt.axis("equal")
    plt.xticks([]); plt.yticks([])
    plt.tight_layout()
    plt.show()


# --------------------- USO ---------------------
if __name__ == "__main__":
    conn = psycopg2.connect(
        host="localhost",
        dbname="BASE",          # <-- cambia si tu DB se llama distinto
        user="postgres",
        password="DB032122"
    )

    # a) Mantener todos los nodos, con filas/columnas a 0 para no permitidos
    data = fetch_graph_from_db(
        conn,
        dual_id="DU-01",
        level="P02",
        undirected=True,
        allowed_locomotions=("WALK", "RAMP"),
        filter_mode="mask",            # por defecto
        treat_general_as_walk=False    # estricto: GENERAL (NULL) queda fuera
    )
    A = data["A"]  # matriz enmascarada

    # Resumen rápido por consola
    nnz = int(np.count_nonzero(A))
    print(f"A.shape = {A.shape} | nnz = {nnz} | densidad = {nnz / A.size:.4f}" if A.size else "A vacía")

    # Dibujo (coherente con WALK/RAMP)
    draw_graph(
        G=data["G"],  # en modo 'mask' es G_full (pintamos sólo edges entre permitidos)
        positions=data["positions"],
        node_ids=data["node_ids"],
        allowed_mask=data["allowed_mask"]
    )

    # b) (Opcional) Subgrafo solo con WALK/RAMP
    data2 = fetch_graph_from_db(
        conn,
        dual_id="DU-01",
        level="P02",
        undirected=True,
        allowed_locomotions=("WALK", "RAMP"),
        filter_mode="subgraph"
    )
    print(f"Subgrafo: nodos={data2['G'].number_of_nodes()} | aristas={data2['G'].number_of_edges()}")

    conn.close()

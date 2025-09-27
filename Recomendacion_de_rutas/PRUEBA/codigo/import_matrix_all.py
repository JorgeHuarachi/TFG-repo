
from typing import Optional, Dict, List, Tuple
import numpy as np
import psycopg2
import networkx as nx
import matplotlib.pyplot as plt

## FUNCIOANA MUY BIEN DE MOMENTO, USARLA PARA CARGAR GRAFO DESDE BD

# 1) funcion para cargar grafo desde BD

def fetch_graph_from_db(
    conn,
    dual_id: str,
    level: Optional[str] = None,
    undirected: bool = True
):
    """
    Objetivo: cargar grafo desde BD (nodos + aristas con peso)
    Devuelve:
      - node_ids: lista ordenada de IDs ND-#### (para fijar el orden)
      - node_to_idx / idx_to_node: mappings consistentes
      - positions: dict id_node -> (x,y)
      - edges: lista de (from_id, to_id, w)
      - G: Graph de NetworkX con 'weight'
      - A: matriz NumPy (densa) de costes (simétrica si undirected=True)
    """
    with conn.cursor() as cur:
        # 1) Nodos
        cur.execute(
            """
            SELECT n.id_node, n.id_cell_space, cs.level, ST_X(n.geom) AS x, ST_Y(n.geom) AS y
            FROM indoorgml_core.node n
            JOIN indoorgml_core.cell_space cs ON cs.id_cell_space = n.id_cell_space
            WHERE n.id_dual = 'DU-01'
              AND ('P01'::text IS NULL OR cs.level = 'P01')
            ORDER BY n.id_node
            """,
            (dual_id, level, level)
        )
        rows_nodes = cur.fetchall()

        if not rows_nodes:
            raise RuntimeError("No se encontraron nodos para esa dual/level.")

        node_ids = [r[0] for r in rows_nodes]  # ['ND-0001', ...]
        positions = {r[0]: (r[3], r[4]) for r in rows_nodes}  # id_node -> (x,y)

        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        idx_to_node = np.array(node_ids)

        # 2) Aristas
        cur.execute(
            """
            SELECT
              e.from_node, e.to_node, e.weight_m AS w
            FROM indoorgml_core.edge e
            JOIN indoorgml_core.node na ON na.id_node = e.from_node
            JOIN indoorgml_core.node nb ON nb.id_node = e.to_node
            JOIN indoorgml_core.cell_space csa ON csa.id_cell_space = na.id_cell_space
            JOIN indoorgml_core.cell_space csb ON csb.id_cell_space = nb.id_cell_space
            WHERE e.id_dual = 'DU-01'
              AND ('P01'::text IS NULL OR (csa.level = 'P01' AND csb.level = 'P01'))
            """,
            (dual_id, level, level, level)
        )
        rows_edges = cur.fetchall()

    # 3) NetworkX
    G = nx.Graph() if undirected else nx.DiGraph()
    G.add_nodes_from(node_ids)
    for u, v, w in rows_edges:
        if u in node_to_idx and v in node_to_idx and w is not None and w > 0:
            G.add_edge(u, v, weight=float(w))

    # 4) Matriz densa NumPy con orden controlado
    A = nx.to_numpy_array(G, nodelist=node_ids, weight='weight', dtype=float)
    if undirected:
        # Garantiza simetría exacta si hubiera alguna pequeña deriva numérica
        A = np.maximum(A, A.T)

    return {
        "node_ids": node_ids,
        "node_to_idx": node_to_idx,
        "idx_to_node": idx_to_node,
        "positions": positions,
        "edges": rows_edges,  # lista [(u,v,w), ...]
        "G": G,
        "A": A
    }

# 2) usar la funcion para cargar grafo desde BD

# conn es una variable global de conexion a la BD
conn = psycopg2.connect(
    host="localhost", 
    dbname="edges", 
    user="postgres", 
    password="DB032122"
)

# data es un diccionario con toda la info del grafo
data = fetch_graph_from_db(conn, dual_id="DU-01", level="P00", undirected=True)

# Extraer componentes del diccionario data
A = data["A"]                       # matriz de costes (NumPy)
node_to_idx = data["node_to_idx"]   # mapea ND-#### -> índice
idx_to_node = data["idx_to_node"]   # índice -> ND-####
G = data["G"]                       # por si quieres usar Dijkstra en NetworkX
pos = data["positions"]             # coordenadas para dibujar

# Ejemplo: convertir un camino en índices -> IDs para devolver a la BD
path_nodes = nx.shortest_path(G, source="ND-022", target="ND-018", weight="weight")
# Imprimir por terminarl de forma visible
print("Ruta (nodos):", " -> ".join(path_nodes))
# path_nodes ya está en IDs ND-####, listo para registrar en la BD o mostrar

# PRINTS PARA INSPECCIONAR EL GRAFO CARGADO

# Suponiendo que ya hiciste:
# data = fetch_graph_from_db(conn, dual_id="DU-01", level="P00", undirected=True)

# ya tienes:
G            = data["G"]
A            = data["A"]                # matriz de costes (NumPy)
node_ids     = data["node_ids"]         # lista de IDs ND-####
node_to_idx  = data["node_to_idx"]      # dict ND-#### -> idx
idx_to_node  = data["idx_to_node"]      # np.array de ND-####
positions    = data["positions"]        # dict ND-#### -> (x,y)
edges        = data["edges"]            # lista (from_node, to_node, weight)

print(f"--- RESUMEN DEL GRAFO ---")
print(f"Tipo de G: {type(G).__name__}")
print(f"Nodos (|V|): {G.number_of_nodes()}  |  Aristas (|E|): {G.number_of_edges()}")

print(f"\n--- NODOS ---")
print(f"type(node_ids): {type(node_ids).__name__}  |  len: {len(node_ids)}")
print(f"Primeros 10 node_ids: {node_ids[:10]}")
print(f"type(node_to_idx): {type(node_to_idx).__name__}  |  ejemplo: {list(node_to_idx.items())[:3]}")
print(f"type(idx_to_node): {type(idx_to_node).__name__}  |  shape: {idx_to_node.shape}")
print(f"type(positions): {type(positions).__name__}  |  muestras: {list(positions.items())[:3]}")

print(f"\n--- MATRIZ DE COSTES A ---")
print(f"type(A): {type(A).__name__}  |  shape: {A.shape}  |  dtype: {A.dtype}")
nnz = np.count_nonzero(A)
density = nnz / A.size
print(f"Elementos no nulos (nnz): {nnz}  |  Densidad: {density:.4f}")
is_symmetric = np.allclose(A, A.T, equal_nan=True)
print(f"¿Simétrica?: {is_symmetric}")
diag_zero = np.allclose(np.diag(A), 0)
print(f"¿Diagonal cero?: {diag_zero}")
if nnz > 0:
    nz_vals = A[A > 0]
    print(f"Coste > 0  ->  min: {nz_vals.min():.3f}  |  max: {nz_vals.max():.3f}  |  mean: {nz_vals.mean():.3f}")

print(f"\n--- ARISTAS (muestras) ---")
print(f"type(edges): {type(edges).__name__}  |  len: {len(edges)}")
print("Muestras:")
for row in edges[:10]:
    u, v, w = row
    print(f"  ({u}) --{w:.3f}--> ({v})")

print(f"\n--- GRADOS (muestras) ---")
deg = dict(G.degree())
print(f"Grado medio: {np.mean(list(deg.values())):.2f}")
print(f"Ejemplos: {list(deg.items())[:10]}")

# Si esperas 23x23, compruébalo:
expected_n = 23
print(f"\nEsperaba 23x23? {A.shape == (expected_n, expected_n)}  |  A.shape: {A.shape}")

## 
# Asume que ya tienes:
# - G: grafo NetworkX
# - positions: dict {"ND-####": (x, y)}

# Filtramos por si hay nodos sin coordenadas
nodos_con_pos = [n for n in G.nodes if n in positions]
nodos_sin_pos = [n for n in G.nodes if n not in positions]
if nodos_sin_pos:
    print(f"[AVISO] {len(nodos_sin_pos)} nodos no tienen posición y no se dibujarán:", nodos_sin_pos)

fig, ax = plt.subplots(figsize=(10, 7))

# Aristas donde ambos extremos tienen posición
edgelist_con_pos = [(u, v) for u, v in G.edges() if u in positions and v in positions]

fig, ax = plt.subplots(figsize=(10, 7))

# Nodos
nx.draw_networkx_nodes(
    G, positions, nodelist=nodos_con_pos, ax=ax,
    node_size=420, node_color="#9dd6ff", edgecolors="#2c5178", linewidths=1.2
)

# Aristas (finas y grises)
nx.draw_networkx_edges(
    G, positions, edgelist=edgelist_con_pos, ax=ax,
    width=1.2, edge_color="#B0B0B0", alpha=0.9
)

# Etiquetas de nodos
nx.draw_networkx_labels(
    G, positions, labels={n: n for n in nodos_con_pos}, ax=ax,
    font_size=9, font_color="#0d1b2a"
)

ax.set_title("Geometría del grafo (nodos + aristas base)", fontsize=12)
ax.axis("equal")
ax.set_xticks([]); ax.set_yticks([])
plt.tight_layout()
plt.show()

## PARA DIBUJAR GRAFO CON PESOS Y RUTA DESTACADA

# --- Asume que ya tienes ---
# G: grafo de NetworkX (no dirigido) con atributo 'weight' en las aristas
# positions: dict { "ND-####": (x, y) }
# Opcional: en cada arista puedes tener 'id_edge' para depurar

# Configura origen/destino si quieres resaltar ruta
source_id = "ND-022"
target_id = "ND-018"

# Calcula ruta (opcional). Si no existen en G, comenta este bloque.
try:
    path_nodes = nx.shortest_path(G, source=source_id, target=target_id, weight="weight")
    path_edges = list(zip(path_nodes[:-1], path_nodes[1:]))
    path_cost  = nx.path_weight(G, path_nodes, weight="weight")
except nx.NodeNotFound:
    path_nodes, path_edges, path_cost = [], [], None

# Anchura de aristas basada en peso (más corto -> más grueso)
weights = np.array([data.get("weight", 1.0) for _, _, data in G.edges(data=True)], dtype=float)
if weights.size > 0:
    # Normalizamos invertido para que menor distancia => mayor grosor
    w_min, w_max = weights.min(), weights.max()
    inv = (w_max - weights) / (w_max - w_min + 1e-9)
    widths = 1.0 + 4.0 * inv  # entre 1 y 5
else:
    widths = 1.0

# Etiquetas de aristas: el peso con 1 decimal
edge_labels = {(u, v): f"{attr.get('weight', 0):.1f}" for u, v, attr in G.edges(data=True)}

fig, ax = plt.subplots(figsize=(10, 7))

# Nodos (base)
nx.draw_networkx_nodes(
    G, positions, ax=ax,
    node_size=420, node_color="#9dd6ff", edgecolors="#2c5178", linewidths=1.2
)

# Aristas (base)
nx.draw_networkx_edges(
    G, positions, ax=ax,
    width=widths, edge_color="#9a9a9a", alpha=0.9
)

# Etiquetas de nodos
nx.draw_networkx_labels(
    G, positions, ax=ax,
    font_size=9, font_color="#0d1b2a"
)

# Etiquetas de aristas (pesos)
nx.draw_networkx_edge_labels(
    G, positions, edge_labels=edge_labels, ax=ax,
    font_size=8, rotate=False, label_pos=0.5
)

# Resalta ruta (si existe)
if path_nodes:
    # Nodos de la ruta
    nx.draw_networkx_nodes(
        G, positions, nodelist=path_nodes, ax=ax,
        node_size=520, node_color="#ff6b6b", edgecolors="#8b1b1b", linewidths=1.5
    )
    # Aristas de la ruta
    nx.draw_networkx_edges(
        G, positions, edgelist=path_edges, ax=ax,
        width=4.5, edge_color="#ff6b6b"
    )
    # Texto con coste
    ax.text(
        0.02, 0.98,
        f"Ruta {source_id} → {target_id} | coste = {path_cost:.2f}\n" +
        " → ".join(path_nodes),
        transform=ax.transAxes, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        fontsize=9
    )

ax.set_title("Grafo IndoorGML (Dual) — nodos=CellSpace, aristas con peso=distancia", fontsize=12)
ax.axis("equal")
ax.set_xticks([]); ax.set_yticks([])
plt.tight_layout()
plt.show()

for u, v, d in G.edges(data=True):
    if "id_edge" in d:
        print(f"{u} -- {v} | w={d['weight']:.2f} | edge={d['id_edge']}")

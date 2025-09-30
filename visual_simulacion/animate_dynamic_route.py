# -----------------------------------------------------------------------------
# Recalcula dinámicamente la ruta desde un origen fijo a la mejor salida,
# coloreando nodos por "score" (0..1) que varía con el tiempo.
# Usa build_score_fn(node_ids, scenario, default, ema_alpha, combine).
# -----------------------------------------------------------------------------

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
    dbname="simulacion",      # <--- Nombre de la base de datos
    user="postgres",
    password="DB032122"
)

DUAL_ID = "DU-01"         # Identificador de grafo dual IndoorGML en BD
LEVEL   = "P00"           # Planta/nivel (None si quieres traer todo)
UNDIRECTED = True         # True: grafo no dirigido; False: dirigido (puertas sentido único, etc.)

# (Opcional) movilidad
APPLY_MOBILITY_FILTER = True                 # Si True, filtra por locomociones permitidas
ALLOWED_LOCOMOTIONS   = ("WALK", "RAMP")     # Locomociones permitidas
TREAT_GENERAL_AS_WALK = True                 # Si un nodo carece de locomotion y kind=="GENERAL", trátalo como WALK

# Simulación/visualización
SOURCE_NODE = "ND-009"              # Origen fijo (si None, usa el primer nodo)
TAU = 0.60                          # Umbral de seguridad: nodos con score >= TAU son transitables
INTERVAL_MS = 80                    # Milisegundos por frame en la animación (GIF)
DT  = 0.50                          # Segundos simulados por frame (t = frame * DT)
N_FRAMES = 200                      # Número total de frames (duración de la sim)
EMA_ALPHA = 0.30                    # Suavizado EMA de scores; None para desactivar
SAVE_GIF = False                    # Guardar GIF al final (requiere pillow)
OUT_GIF  = "route_dynamics.gif"     # Nombre de archivo GIF

# (Opcional) salidas manuales (si la BD no las tiene marcadas)
EMERGENCY_EXIT_NODE_IDS: Set[str] = set()  # e.g., {"ND-021","ND-030"}

# --------------------- Carga del grafo desde PostGIS ---------------------
def fetch_graph_from_db(
    conn,                                                   # Conexión psycopg2 ya abierta
    dual_id: str,                                           # Id del grafo dual
    level: Optional[str] = None,                            # Filtro de planta
    undirected: bool = True,                                # Grafo no dirigido o dirigido
    apply_mobility: bool = False,                           # ¿Aplicar filtro de movilidad en BD?
    allowed_locomotions: Iterable[str] = ("WALK","RAMP"),   # Locomociones admitidas
    treat_general_as_walk: bool = False                     # ¿Contar GENERAL sin locomotion como WALK?
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
            (dual_id, level, level) # Parámetros de la query
        )
        rows_nodes = cur.fetchall() # Lista de filas con (id_node, id_cell, x, y)
        if not rows_nodes:
            # Si no hay nodos, abortamos con un error explícito
            raise RuntimeError("No hay nodos para esa dual/level.")
        
        # Extrae ids de nodos en orden y mapea id -> índice (posición en vector score)  
        node_ids = [r[0] for r in rows_nodes]
        node_to_idx = {nid: i for i, nid in enumerate(node_ids)}
        
        # Diccionario de posiciones para dibujar (solo si x,y no son None)
        positions = {r[0]: (r[2], r[3]) for r in rows_nodes if r[2] is not None and r[3] is not None}

        #---------------- Aristas con peso (metros) ----------------
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
            (dual_id, level, level, level) # Parametrización segura
        )
        rows_edges = cur.fetchall()  # Lista de (from_node, to_node, weight_m)

        # ---------------- Nodos marcados como salidas de emergencia ----------------
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
        emergency_nodes_from_db = {r[0] for r in ex_rows}  # Conjunto de ids de salida

        # ---------------- (Opcional) máscara de movilidad desde BD ----------------
        mobility_mask = None # Si no se solicita, queda en None
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
                (list(allowed_locomotions), treat_general_as_walk, dual_id, level, level)  # Lista de locomociones permitidas # Flag GENERAL->WALK
            )
            rows_mob = cur.fetchall() # [(id_node, allowed_bool), ...]
            
            # Vector booleano y luego diccionario id->allowed (más cómodo en Python)
            allowed_vec = np.array([bool(r[1]) for r in rows_mob], dtype=bool)
            mobility_mask = {nid: ok for (nid, _), ok in zip(rows_mob, allowed_vec)}

    # ---------------- Construcción del grafo NetworkX ----------------
    G = nx.Graph() if undirected else nx.DiGraph() # Tipo de grafo según flag
    G.add_nodes_from(node_ids) # Añade todos los nodos
    for u, v, w in rows_edges:
        # Valida peso positivo y existencia de nodos antes de añadir la arista

        if w is not None and w > 0 and u in node_to_idx and v in node_to_idx:
            G.add_edge(u, v, weight=float(w)) # Peso "weight" = metros (por ahora)
    
    # Devuelve un diccionario con todo lo necesario para sim/visual y uso en main()
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
    # -------------------- Conexión a BD --------------------
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
    # -------------------- Unpack datos del grafo --------------------
    node_ids =  data["node_ids"]       # lista de ids de nodos (ordenado)
    positions = data["positions"]      # posiciones XY conocidas (puede estar incompleto)
    G =         data["G"]              # grafo NX (con aristas y pesos)

    # -------------------- Origen fijo --------------------
    source = SOURCE_NODE or node_ids[0]  # si no se definió SOURCE_NODE, usa el primero

    # -------------------- Salidas de emergencia --------------------
    emergency_nodes = set(EMERGENCY_EXIT_NODE_IDS) or set(data["emergency_nodes_db"])
    if not emergency_nodes:
        # Si BD no tiene salidas y no se definieron manualmente,
        # avisamos y, para no romper la demo, usamos el propio origen como "salida".
        print("[AVISO] No hay salidas en BD ni definidas. Usa EMERGENCY_EXIT_NODE_IDS para fijarlas.")
        emergency_nodes = {source}

    # -------------- Escenario de scores dinámicos --------------
    SCENARIO = {
    "ND-001": [("triangle", 16.38, 23.78, 0.78, 1.00)],
    "ND-002": [("triangle", 16.10, 16.88, 0.84, 1.00)],
    "ND-003": [("triangle", 18.05, 30.72, 0.41, 1.00)],
    "ND-004": [("triangle", 14.02, 22.42, 0.81, 1.00)],
    "ND-005": [("triangle", 18.05, 31.46, 0.57, 1.00)],
    "ND-006": [("triangle", 12.33, 24.16, 0.38, 1.00)],
    "ND-007": [("triangle", 22.87, 27.63, 0.73, 1.00)],
    "ND-008": [("triangle", 16.24, 31.83, 0.80, 1.00)],
    "ND-009": [("triangle", 23.96, 18.89, 0.58, 1.00)],
    "ND-010": [("triangle", 13.15, 18.09, 0.69, 1.00)],
    "ND-011": [("triangle", 25.30, 34.35, 0.51, 1.00)],
    "ND-012": [("triangle", 20.25, 24.39, 0.44, 1.00)],
    "ND-013": [("triangle", 17.34, 24.51, 0.46, 1.00)],
    "ND-014": [("triangle", 26.91, 23.74, 0.77, 1.00)],
    "ND-015": [("triangle", 28.34, 21.25, 0.77, 1.00)],
    "ND-016": [("triangle", 29.63, 20.14, 0.48, 1.00)],
    "ND-017": [("triangle", 22.54, 24.46, 0.84, 1.00)],
    "ND-018": [("triangle", 31.29, 20.42, 0.64, 1.00)],
    "ND-019": [("triangle", 28.24, 31.87, 0.81, 1.00)],
    "ND-020": [("triangle", 32.66, 24.27, 0.80, 1.00)],
    "ND-021": [("triangle", 34.91, 18.91, 0.57, 1.00)],
    "ND-022": [("triangle", 38.66, 23.13, 0.73, 1.00)],
    "ND-023": [("triangle", 36.82, 34.09, 0.50, 1.00)],
    "ND-024": [("triangle", 41.21, 18.13, 0.53, 1.00)],
    "ND-025": [("triangle", 39.32, 16.33, 0.57, 1.00)],
    "ND-026": [("triangle", 39.90, 21.26, 0.65, 1.00)],
    "ND-027": [("triangle", 44.33, 21.68, 0.49, 1.00)],
    "ND-028": [("triangle", 39.98, 27.63, 0.47, 1.00)],
    "ND-029": [("triangle", 42.87, 24.39, 0.79, 1.00)],
    "ND-030": [("triangle", 44.53, 27.31, 0.84, 1.00)],
    "ND-031": [("triangle", 43.29, 34.51, 0.62, 1.00)],
    "ND-032": [("triangle", 49.28, 28.06, 0.48, 1.00)],
    "ND-033": [("triangle", 48.23, 31.36, 0.44, 1.00)],
    "ND-034": [("triangle", 51.16, 21.28, 0.71, 1.00)],
    "ND-035": [("triangle", 49.97, 26.74, 0.64, 1.00)],
    "ND-036": [("triangle", 51.42, 20.76, 0.79, 1.00)],
    "ND-037": [("triangle", 50.34, 23.61, 0.54, 1.00)],
    "ND-038": [("triangle", 55.23, 30.53, 0.63, 1.00)],
    "ND-039": [("triangle", 58.14, 15.64, 0.67, 1.00)],
    "ND-040": [("triangle", 58.66, 27.92, 0.80, 1.00)],
    "ND-041": [("triangle", 55.20, 18.71, 0.49, 1.00)],
    "ND-042": [("triangle", 60.61, 22.67, 0.39, 1.00)],
    "ND-043": [("triangle", 56.85, 29.24, 0.76, 1.00)],
    "ND-044": [("triangle", 62.11, 22.99, 0.58, 1.00)],
    "ND-045": [("triangle", 61.85, 23.67, 0.52, 1.00)],
    "ND-046": [("triangle", 62.43, 20.12, 0.63, 1.00)],
    "ND-047": [("triangle", 67.96, 28.28, 0.54, 1.00)],
    "ND-048": [("triangle", 62.35, 23.67, 0.40, 1.00)],
    "ND-049": [("triangle", 68.32, 27.75, 0.70, 1.00)],
    "ND-050": [("triangle", 66.49, 25.34, 0.61, 1.00)],
    "ND-051": [("triangle", 66.35, 22.52, 0.69, 1.00)],
    "ND-052": [("triangle", 67.33, 23.91, 0.79, 1.00)],
    "ND-053": [("triangle", 66.23, 25.65, 0.78, 1.00)],
    "ND-054": [("triangle", 70.83, 17.68, 0.39, 1.00)],
    "ND-055": [("triangle", 72.06, 34.57, 0.47, 1.00)],
    "ND-056": [("triangle", 70.90, 19.75, 0.48, 1.00)],
    "ND-057": [("triangle", 72.26, 25.31, 0.67, 1.00)],
    "ND-058": [("triangle", 71.50, 23.31, 0.72, 1.00)],
    "ND-059": [("triangle", 75.64, 18.45, 0.39, 1.00)],
    "ND-060": [("triangle", 74.32, 22.93, 0.59, 1.00)],
    "ND-061": [("triangle", 74.68, 30.83, 0.48, 1.00)],
    "ND-062": [("triangle", 74.84, 29.40, 0.83, 1.00)],
    "ND-063": [("triangle", 78.21, 23.22, 0.52, 1.00)],
    "ND-064": [("triangle", 77.36, 19.26, 0.68, 1.00)],
    "ND-065": [("triangle", 77.43, 23.83, 0.47, 1.00)],
    "ND-066": [("triangle", 80.95, 28.19, 0.83, 1.00)],
    "ND-067": [("triangle", 78.49, 26.87, 0.80, 1.00)],
    "ND-068": [("triangle", 83.35, 19.46, 0.71, 1.00)],
    "ND-069": [("triangle", 68.03, 19.59, 0.42, 1.00)],
    "ND-070": [("triangle", 79.58, 17.44, 0.60, 1.00)],
    "ND-071": [("triangle", 80.79, 26.62, 0.45, 1.00)],
    "ND-072": [("triangle", 83.48, 29.31, 0.72, 1.00)],
    "ND-073": [("triangle", 73.65, 17.48, 0.81, 1.00)],
    "ND-074": [("triangle", 78.86, 21.02, 0.59, 1.00)],
    "ND-075": [("triangle", 84.04, 31.29, 0.49, 1.00)],
    "ND-076": [("triangle", 89.17, 15.50, 0.63, 1.00)],
    "ND-077": [("triangle", 85.45, 17.12, 0.42, 1.00)],
    "ND-078": [("triangle", 82.95, 33.41, 0.65, 1.00)],
    "ND-079": [("triangle", 92.00, 15.68, 0.58, 1.00)],
    "ND-080": [("triangle", 90.68, 15.36, 0.40, 1.00)],
    "ND-081": [("triangle", 92.00, 15.68, 0.47, 1.00)],
    "ND-082": [("triangle", 88.49, 22.56, 0.78, 1.00)],
}
 
    # Construye la función de scores (vector) y el reset (todo a 1.0)
    score_fn, reset_scores = build_score_fn(
        node_ids=node_ids,        # orden de nodos al que se alinea el vector de salida
        scenario=SCENARIO,        # diccionario node_id -> ventanas
        default=1.0,              # valor por defecto cuando no aplica ninguna ventana
        ema_alpha=EMA_ALPHA,      # suavizado EMA (None para desactivar)
        combine="min"             # combinación de ventanas: conservador (peor caso)
    )
    # ------------------ Figura (una sola colorbar) ------------------
    fig, ax = plt.subplots(figsize=(12, 8))

    # Si no hay XY en BD para algún nodo, usa layout de NetworkX (distribución automática)
    if not positions:
        positions = nx.spring_layout(G, seed=42)

    # Dibuja aristas una vez (no cambian)
    nx.draw_networkx_edges(G, positions, ax=ax, width=1.2, edge_color="#B0B0B0", alpha=0.9)

    # Dibuja nodos: guardamos el "artist" para actualizar colores en cada frame
    nodes_artist = nx.draw_networkx_nodes(
        G, positions, nodelist=node_ids, ax=ax,
        node_size=420, node_color="#dddddd", edgecolors="#333333", linewidths=1.0
    )
    # Etiquetas de nodos (Fijas)
    nx.draw_networkx_labels(G, positions, ax=ax, font_size=9)

    # Colorbar única para el score (0..1) con colormap rojo→amarillo→verde
    norm = mpl.colors.Normalize(vmin=0.0, vmax=1.0)
    cmap = mpl.cm.get_cmap("RdYlGn")
    sm = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)
    cbar = fig.colorbar(sm, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("score de seguridad (0–1)")

    # Línea para la ruta dinámica (se actualizará en cada frame)
    path_line, = ax.plot([], [], lw=4, color="#ff6b6b")
    
    # Caja de texto (título vivo) arriba a la izquierda
    title_text = ax.text(0.02, 0.98, "", transform=ax.transAxes,
                         va="top", ha="left",
                         bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    # Titulo estático del gráfico
    ax.set_title("Ruta dinámica (origen fijo → mejor salida) con score(t)")
    ax.axis("equal")
    ax.set_xticks([]); ax.set_yticks([])

    # Helper para colorear nodos por score (score es vector alineado con node_ids)
    def set_node_facecolors(score_vec: np.ndarray):
        # Conviertes cada score en un color usando el colormap
        colors = [cmap(norm(float(score_vec[i]))) for i in range(len(node_ids))]
        nodes_artist.set_facecolor(colors)   # actualiza colores del "artist" de nodos

    mobility_mask = data["mobility_mask"]  # dict nid->bool (o None si no se pidió)
    prev_scores: Optional[np.ndarray] = None  # último vector de scores (para EMA)

    # ------------------ Función de inicialización de la animación ------------------
    def init():
        nonlocal prev_scores
        prev_scores = reset_scores()                 # inicia todo a 1.0 (default)
        s0 = score_fn(0.0, prev_scores=prev_scores)  # primer cálculo (aplica EMA si procede)
        prev_scores = s0                             # almacena para siguiente frame
        set_node_facecolors(s0)                      # pinta nodos
        path_line.set_data([], [])                   # limpio la línea de ruta
        title_text.set_text("t=0.0s | coste=–")      # título inicial
        return nodes_artist, path_line, title_text   # devuelve artistas a blitear

    # ------------------ Ruta a la "mejor" salida ------------------
    def best_exit_path(H: nx.Graph, src: str, exits: Set[str]) -> Tuple[Optional[List[str]], float]:
        # Recorre todas las salidas y elige la ruta con menor coste (weight)
        best_path, best_cost = None, float("inf")
        for ex in exits:
            if src in H and ex in H: # ambos nodos deben existir en el subgrafo seguro
                try:
                    p = nx.shortest_path(H, src, ex, weight="weight") # Dijkstra (weight)
                    c = nx.path_weight(H, p, weight="weight")         # suma de pesos
                    if c < best_cost:
                        best_cost, best_path = c, p
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue # ignora salidas no alcanzables
        return best_path, best_cost
    
    # ------------------ Función por frame ------------------
    def animate(frame):
        nonlocal prev_scores
        t = frame * DT                                 # tiempo simulado actual
        scores = score_fn(t, prev_scores=prev_scores)  # vector de scores para t
        prev_scores = scores                           # guarda para EMA del próximo frame
        set_node_facecolors(scores)                    # repinta nodos según score(t)


        # --- Filtrado por seguridad (y movilidad si hay máscara) ---
        safe_nodes = [node_ids[i] for i in range(len(node_ids)) if float(scores[i]) >= TAU]
        if mobility_mask is not None:
            # Aplica filtro de movilidad (solo nodos permitidos por locomotion/kind)
            safe_nodes = [n for n in safe_nodes if mobility_mask.get(n, False)]
            
        # Construye subgrafo seguro (copia materializada para operar sin vistas)
        H = G.subgraph(safe_nodes).copy()

        # --- Ruta al "mejor" exit en el subgrafo H ---
        path, cost = best_exit_path(H, source, emergency_nodes)
        if path:
            # Si hay ruta, dibuja la polilínea y actualiza el título con coste y longitud
            xs = [positions[n][0] for n in path]
            ys = [positions[n][1] for n in path]
            path_line.set_data(xs, ys)
            title_text.set_text(f"t={t:.1f}s | coste={cost:.2f} | nodos={len(path)}")
        else:
            # Si no hay ruta, limpia y muestra aviso
            path_line.set_data([], [])
            title_text.set_text(f"t={t:.1f}s | sin ruta")

        return nodes_artist, path_line, title_text  # artistas que se redibujan
    
    # ------------------ Lanza la animación ------------------
    anim = FuncAnimation(
        fig, animate, init_func=init, frames=N_FRAMES,
        interval=INTERVAL_MS, blit=False, repeat=False
    )
    
    # ------------------ Guardar GIF (opcional) ------------------
    if SAVE_GIF:
        try:
            fps = max(1, int(round(1000.0 / INTERVAL_MS)))  # frames por segundo según INTERVAL_MS
            anim.save(OUT_GIF, writer="pillow", fps=fps)    # requiere pillow instalado
            print(f"[OK] Guardado GIF: {OUT_GIF} (fps={fps})")
        except Exception as e:
            print(f"[AVISO] No se pudo guardar GIF: {e}")

    plt.tight_layout()  # ajusta márgenes
    plt.show()          # muestra la ventana de la animación

# Punto de entrada si ejecutas el script directamente (python animate_dynamic_route.py)
if __name__ == "__main__":
    main()

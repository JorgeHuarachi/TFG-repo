# -----------------------------------------------------------------------------
# MÓDULO: utilidades para construir un grafo IndoorGML filtrado por
#         (i) movilidad permitida y (ii) umbral de seguridad (score),
#         junto con funciones auxiliares para buscar rutas a múltiples destinos.
#
# DEPENDENCIAS:
#   - psycopg2: conexión/PostgreSQL (PostGIS).
#   - networkx: manipulación de grafos y rutas.
#
# ESQUEMA DE DATOS ESPERADO (BD):
#   - indoorgml_core.node          (id_node, id_cell_space, id_dual, geom)
#   - indoorgml_core.edge          (from_node, to_node, id_dual, weight_m)
#   - indoorgml_core.cell_space    (id_cell_space, level)
#   - indoorgml_navigation.navigable_space (id_cell_space, locomotion, kind,
#                                            function_code, is_emergency_exit)
#   - iot.v_cell_score_latest      (id_cell_space, score)   # score ∈ [0,1]?¿
#
# IDEA FUERZA:
#   1) Leer nodos/aristas + metadatos + score por celda.
#   2) Construir G (grafo completo) y G_masked (subgrafo transitable).
#   3) Ofrecer utilidades: ruta más corta a cualquier destino, y fallback a
#      ventanas/respiraderos si no hay ruta a salidas.
#
# NOTAS:
#   - Este módulo trabaja con grafos NO dirigidos (nx.Graph()).
#     Si tu red tiene direccionalidad (puertas unidireccionales, escaleras),
#     considera migrar a nx.DiGraph() (ver comentarios “Mejora:” más abajo).
# -----------------------------------------------------------------------------
from typing import Optional, Iterable, Dict, Tuple, Set
import psycopg2, networkx as nx




ALLOWED_LOCOMOTIONS = ("WALK","RAMP")
WINDOW_FUNCS = ("WINDOW","VENTANA")   # para “último recurso”
SCORE_UMBRAL = 0.6

def _fetch_nodes_edges_scores(conn, dual_id, level):
    """
    Lee de la BD:
      - nodos con posición (x,y) y metadatos (locomotion/kind/function_code/is_exit),
      - aristas y su peso (metros),
      - score por celda (vista iot.v_cell_score_latest).?¿

    Params
    ------
    conn : psycopg2 connection
        Conexión abierta a Postgres/PostGIS.
    dual_id : str
        Identificador del grafo dual (IndoorGML).
    level : Optional[str]
        Planta/level a filtrar; si es None, trae todos los niveles del dual.

    Returns
    -------
    nodes : list[tuple]
        Filas con campos (id_node, id_cell_space, level, x, y, locomotion, kind,
                          function_code, is_emergency_exit).
    edges : list[tuple]
        Filas (from_node, to_node, weight_m).
    score_by_cell : dict[str, float]
        Mapa id_cell_space → score más reciente (si no hay, se usará 1.0).
    """
    with conn.cursor() as cur:
        # ------------------------------
        # 1) NODOS + METADATOS + POS
        # ------------------------------
        # Nota: el filtro por 'level' es opcional: si level es None, se ignora.
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
        
        # ------------------------------
        # 2) ARISTAS + PESO (metros)
        # ------------------------------
        # Se unen cell_spaces de ambos extremos para filtrar por level si aplica.
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

        # ------------------------------
        # 3) SCORES por celda
        # ------------------------------
        # La vista devuelve todas las celdas con su último score; si no hay
        # registro para una celda, más tarde asumimos score=1.0 (seguro).
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
    """
    Construye el grafo IndoorGML y aplica un filtro de transitabilidad basado en:
      (i) movilidad permitida y (ii) score de seguridad mínimo.

    Devuelve ambas vistas: G_full (completo) y G (filtrado), además de posiciones,
    metadatos por nodo, conjuntos de salidas y ventanas, y los scores por celda.

    Params
    ------
    conn : psycopg2 connection
        Conexión a Postgres/PostGIS.
    dual_id : str
        Id del grafo dual (IndoorGML).
    level : Optional[str]
        Planta a cargar (None = todas).
    allowed_locomotions : Iterable[str]
        Modalidades de locomoción aceptadas (p. ej., WALK, RAMP).
    score_threshold : float
        Umbral de seguridad ∈ [0,1]. Nodos con score < umbral se excluyen.
    window_function_codes : Iterable[str]
        Códigos de función considerados “ventanas/respiraderos” (último recurso).

    Returns
    -------
    dict con:
      - G_full: nx.Graph       (grafo completo sin filtrar)
      - G: nx.Graph            (subgrafo filtrado/transitable)
      - positions: dict[nid] -> (x,y)  (coordenadas para visualización)
      - meta: dict[nid] -> {...}       (cell, locom, kind, fcode, is_exit, score)
      - exits: set[nid]                (nodos marcados como salida)
      - windows: set[nid]              (nodos marcados como ventana/respiradero)
      - score_by_cell: dict[cell_id] -> score
    """
    
    # 1) Descargar datos de la BD
    nodes, edges, score_by_cell = _fetch_nodes_edges_scores(conn, dual_id, level)
    
    # 2) Construir grafo NO dirigido (nx.Graph).
    #    Mejora: usar nx.DiGraph() si existen restricciones de dirección
    #            (p. ej., puertas de sentido único, escaleras “subida/descenso”).
    G = nx.Graph()

    # Diccionarios auxiliares para posiciones y metadatos.
    positions: Dict[str, Tuple[float,float]] = {}
    meta: Dict[str, dict] = {}
    # Conjuntos de destinos “oficiales” (salidas) y “último recurso” (ventanas).
    exits: Set[str] = set()
    windows: Set[str] = set()

    # 3) Crear nodos en G con atributos
    for nid, csid, lvl, x, y, locom, kind, fcode, is_exit in nodes:
        G.add_node(nid)
        if x is not None and y is not None:
            # Guardamos la posición para dibujar o heurísticas (A*).
            positions[nid] = (float(x), float(y))
        # Si esa celda no tiene score en la vista, asumimos 1.0 (seguro).
        score = float(score_by_cell.get(csid, 1.0))
        
        # Metadatos útiles para filtros y auditoría.
        meta[nid] = dict(
            cell=csid, 
            locom=locom, 
            kind=kind, 
            fcode=fcode, 
            is_exit=bool(is_exit), 
            score=score
            )
        
        # Detectar salidas (dos criterios: flag is_exit o function_code tipo EXIT)
        if is_exit or (fcode and fcode.upper() in ("EXIT","EMERGENCY_EXIT")):
            exits.add(nid)
            
        # Detectar “ventanas/respiraderos” para último recurso
        if fcode and fcode.upper() in set(fc.upper() for fc in window_function_codes):
            windows.add(nid)

    # 4) Crear aristas (sólo si el peso existe y es positivo)
    for u, v, w in edges:
        if w and w > 0:
            # Guardar peso en metros. Mejora: convertir a tiempo (m/velocidad_perfil)
            #        o penalizar por riesgo dinámico (ver animate_dynamic_route).
            G.add_edge(u, v, weight=float(w))

    # 5) Filtro por movilidad y score
    #    - ok_mob: locomotion en lista permitida, o GENERAL sin locom definido.
    #    - ok_score: score >= umbral.
    allowed_loco = set(allowed_locomotions)
    keep = []  # nodos que sobrevivirán al filtro
    for n in G.nodes:
        m = meta[n] # metadatos del nodo n
        
        # Regla de movilidad:
        #  - Si m["locom"] ∈ allowed_loco => permitido.
        #  - Si m["locom"] es None y kind == "GENERAL" => tratamos como WALK (opcional).
        ok_mob = (m["locom"] in allowed_loco) or (m["locom"] is None and m["kind"] == "GENERAL")
        
        # Regla de seguridad: el score debe ser ≥ score_threshold.
        ok_score = (m["score"] >= score_threshold)
        
        # Incluir el nodo sólo si pasa ambas reglas
        if ok_mob and ok_score:
            keep.append(n) 
    # 6) Subgrafo filtrado (copia independiente del original para no "arrastrar" vistas)
    G_masked = G.subgraph(keep).copy()
    
    # 7) Devolver todo lo necesario para ruteo y visualización
    return dict(
        G_full=G, 
        G=G_masked, 
        positions=positions, 
        meta=meta,
        exits=exits, 
        windows=windows, 
        score_by_cell=score_by_cell)

def shortest_to_any(G: nx.Graph, src: str, targets: Iterable[str]):
    """
    Devuelve la mejor ruta (y su coste) desde 'src' hasta cualquiera de los 'targets'.

    Estrategia:
      - Itera sobre todos los destinos y calcula la ruta más corta con el 'weight' del grafo.
      - Conserva la ruta con coste mínimo.
      - Ignora destinos sin ruta (NetworkXNoPath).

    Parámetros:
      G       : grafo (filtrado o completo).
      src     : id de nodo origen.
      targets : iterable de ids de nodos destino.

    Devuelve:
      (best_path, best_cost) donde:
        best_path : lista de nodos de la mejor ruta o None si no hay ruta a ninguno.
        best_cost : float con el coste (peso) de esa ruta; inf si no existe ruta.
    """
    best, best_cost = None, float("inf")
    for t in targets:
        
        # Validación: origen y destino deben existir en el grafo
        if src in G and t in G:
            try:
                # Ruta más corta ponderada por atributo "weight" en aristas
                p = nx.shortest_path(G, src, t, weight="weight")
                # Coste total de la ruta (suma de pesos "weight")
                c = nx.path_weight(G, p, weight="weight")
                # Si mejora el mejor coste conocido, actualizamos
                if c < best_cost:
                    best, best_cost = p, c
            except nx.NetworkXNoPath:
                pass
    return best, best_cost

def emergency_exits_if_needed(G: nx.Graph, src: str, exits: Set[str], windows: Set[str]):
    """
    Si existe ruta desde 'src' a alguna salida en 'exits', devolvemos (exits, False).
    Si NO existe ruta, activamos nodos 'windows' como "último recurso" y devolvemos
    (exits U windows, True).

    Parámetros:
      G       : grafo (normalmente filtrado).
      src     : id de nodo origen.
      exits   : conjunto de ids de salidas certificadas.
      windows : conjunto de ids de nodos "ventana/respiradero".

    Devuelve:
      (targets, used_windows) donde:
        targets       : destinos efectivos (exits o exits U windows).
        used_windows  : bool indicando si se recurrió a "último recurso".
    """
    
        # ¿Hay ruta a alguna salida "normal"?

    p, _ = shortest_to_any(G, src, exits)
    if p:  # Sí hay ruta: mantenemos sólo exits
        return exits, False
    # No hay ruta → habilitamos "ventanas" como destinos alternativos (último recurso)
    return exits.union(windows), True

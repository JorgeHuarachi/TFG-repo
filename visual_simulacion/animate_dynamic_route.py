# -----------------------------------------------------------------------------
# Recalcula dinámicamente la ruta desde un origen fijo a la mejor salida,
# coloreando nodos por "score" (0..1) que varía con el tiempo.
# Usa build_score_fn(node_ids, scenario, default, ema_alpha, combine).
# -----------------------------------------------------------------------------

from __future__ import annotations
from typing import Optional, Dict, Iterable, Set, Tuple, List, Union
import numpy as np
import psycopg2
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.animation import FuncAnimation
from dataclasses import dataclass
import math 
import csv, time
from networkx.algorithms.centrality import betweenness_centrality_subset
from sim_scores import build_score_fn, make_fire_scenario_radial, make_linear_front_scenario
from sim_scores import build_score_fn, make_manual_sequence_scenario

# =============================================================================
# GUÍA RÁPIDA — EVENTOS (plantillas copiables)
# =============================================================================
# EVENT_KIND: "none" | "fire_radial" | "linear_front" | "manual_sequence"
#
# 1) fire_radial  — incendio desde un nodo centro, propagación por distancia
# EVENT_PARAMS = {
#   "center_node": "ND-021",  # foco
#   "t0": 10.0,               # inicio (s)
#   "spread_speed": 0.8,      # s/metro (menor = más rápido)
#   "dip": 0.45,              # score mínimo [0..1]
#   "recover": 30.0           # duración total del triangle (baja+sube)
# }
#
# 2) linear_front — frente que avanza en dirección p0->p1 (pasillo)
# EVENT_PARAMS = {
#   "p0_node": "ND-001",      # origen del frente
#   "p1_node": "ND-020",      # marca dirección
#   "t0": 10.0,               # inicio
#   "speed": 1.0,             # s/metro
#   "dip": 0.50,
#   "recover": 25.0
# }
#
# 3) manual_sequence — fases explícitas (con grupos en paralelo)
#    shape="triangle"   -> ("triangle", start, recover, dip, 1.0)
#    shape="ramp_hold"  -> ("ramp" down) + ("hold") + ("ramp" up)
# EVENT_PARAMS = {
#   "groups": ["050","007",["029","045","030"], ...],  # fases; listas = paralelo
#   "t0": 10.0, "phase_step": 8.0,
#   "dip": 0.45,
#   "recover": 30.0,          # se ignora si shape="ramp_hold"
#   "id_prefix": "ND-",
#   "shape": "ramp_hold",     # "triangle" | "ramp_hold"
#   "ramp_down": 6.0, "hold_dur": 80.0, "ramp_up": 8.0
# }
#
# CONSEJOS:
# - Si dip < τ del perfil activo, esos nodos serán intransitables durante la ventana.
# - Asegúrate de que N_FRAMES*DT cubre hasta el fin del evento (t0 + ...).
# - COMBINE="min" es conservador si hay solapes; "last" prioriza la última ventana.
# =============================================================================


# =============================================================================
# MINI-GUÍA DE VARIABLES 
# =============================================================================
# TAU               (umbral seguridad, del perfil): ↑τ => subgrafo seguro más pequeño (más bloqueos), ↓τ abre alternativas.
# EMA_ALPHA         (suavizado):                    0.2–0.4 reduce “parpadeo”; None = sin suavizado (respuesta instantánea).
# BETA_RISK         (bi-criterio):                  0.0 = tiempo puro; ↑β penaliza más aristas “rojas” y empuja rutas seguras.
# ROBUST_TAU        (tolerancia robusta):           ↑ tolera más sobrecoste para mejorar R (redundancia).
# ROBUST_K          (k-rutas):                      ↑ explora más alternativas (más CPU); 6–10 suele bastar en grafos medianos.
# ALGORITHM:
#   - dijkstra: costo mínimo (sin heurística).
#   - astar(heur=euclidean): como Dijkstra pero acelera si la heurística es admisible.
#   - yen_ksp(k): enumera k rutas simples en orden de costo (top-1 = Dijkstra).
# =============================================================================


# =============================================================================
# MINI ROADMAP: añadir un algoritmo
# =============================================================================
# 1) En el helper shortest_path_with_algo(G, src, dst, positions, algo_cfg, weight):
#    - elif algo_cfg.name == "mi_algo": ...  # implementa y devuelve (path, cost)
# 2) En CONFIG: ALGORITHM = AlgoCfg("mi_algo", {"param1":..., ...})
# 3) Si tu algoritmo necesita pre-cálculo o parámetros especiales, documéntalo aquí.
# =============================================================================


"""# ===GUÍA RÁPIDA — SIMULACIÓN, GRÁFICOS Y MÉTRICAS (cómo usar y cómo extender)====
 =============================================================================
 1) CÓMO EJECUTAR (MODO OFFLINE CON GRÁFICOS FINALES)
 -----------------------------------------------------------------------------
 - En CONFIG: 
     SHOW_ANIMATION = False
     SHOW_SUMMARY_PLOTS = True
 - Elige EVENT_KIND y rellena EVENT_PARAMS (p.ej., "manual_sequence" con shape="triangle" o "ramp_hold").
 - Ejecuta el script. Al finalizar verás 3 paneles (configurables) y un recuadro con las condiciones del run.

 2) QUÉ SIGNIFICA LO QUE VES
 -----------------------------------------------------------------------------
 - cost_total   : coste con bi-criterio (tiempo base + penalización por riesgo).
 - time_base    : suma de pesos base (tiempo puro).
 - risk_penal   : cost_total - time_base (lo que añade β por transitar zonas con score bajo).
 - R            : robustez de la ruta (nº de aristas que puedes “romper” manteniendo coste ≤ (1+τ)·C0).
                  NOTA: por defecto se calcula en replan (y en frame 0 si así se implementa); 
                        si no se recalcula, verás NaN (serie vacía). 
                        Puedes forzarlo con compute_R_each_frame=True (más caro).
 - safe_nodes   : nº de nodos transitables (score ≥ τ y movilidad) en el subgrafo H.
 - path_min_score / path_mean_score : mínimo y media del score en la ruta (seguridad de la ruta).
 - overlap_prev : similitud (Jaccard 0..1) entre la ruta actual y la anterior (estabilidad).
 - agility      : señal de “agilidad” (requiere pasar una función agility_fn; si no, verás vacío).

 3) CÓMO AÑADIR UNA MÉTRICA NUEVA AL PIPELINE (4 PASOS)
 -----------------------------------------------------------------------------
 Supón que quieres graficar "my_metric" (una magnitud escalar por frame).

 PASO A) Calcula la serie en run_offline_simulation(...) y devuélvela en results:

   # dentro del bucle for frame in range(n_frames):
   my_metric_series = []   # (defínelo fuera del for, como otras series)
   ...
   my_metric = ...         # calcula usando H, path, scores_by_id, etc.
   my_metric_series.append(my_metric)
   ...
   return dict(..., my_metric=np.array(my_metric_series))

 PASO B) Declara la serie para el plotting en plot_summary(...):

   series_map = {
       "cost_total": results.get("cost_total"),
       ...,
       "my_metric": results.get("my_metric"),
   }

 PASO C) Elige en qué panel se dibuja ajustando PLOT_OPTS["panels"] en CONFIG:

   PLOT_OPTS["panels"] = {
       "p1": ["cost_total"],
       "p2": ["my_metric", "risk_penal"],   # <- añade tu métrica al panel 2, por ejemplo
       "p3": ["R"],
   }

 PASO D) (Opcional) Si es pesada de calcular, hazlo cada N frames o activa un flag:
        - ejemplo: compute_R_each_frame=False para R.

 4) RECETAS DE CONFIGURACIÓN DE PANELES (pega una de estas en CONFIG → PLOT_OPTS["panels"])
 -----------------------------------------------------------------------------
 A) Seguridad + Robustez:
   PLOT_OPTS["panels"] = {
       "p1": ["cost_total"],
       "p2": ["path_min_score", "path_mean_score"],
       "p3": ["R"],
   }

 B) Estabilidad de la ruta:
   PLOT_OPTS["panels"] = {
       "p1": ["cost_total"],
       "p2": ["overlap_prev", "path_len"],
       "p3": ["safe_nodes"],
   }

 C) Agilidad (cuando tengas tu función conectada):
   # En la llamada a run_offline_simulation(...): agility_fn=lambda H,p: sum(C_ev.get(n,0) for n in p[1:-1]) ...
   PLOT_OPTS["panels"] = {
       "p1": ["cost_total"],
       "p2": ["agility"],
       "p3": ["R"],
   }

 D) Rendimiento:
   # Asegúrate de exponer plan_ms y robust_ms en series_map si no están.
   PLOT_OPTS["panels"] = {
       "p1": ["cost_total"],
       "p2": ["plan_ms", "robust_ms"],
       "p3": ["safe_nodes"],
   }

 E) “Modo paper” minimal:
   PLOT_OPTS["panels"] = {
       "p1": ["cost_total"],
       "p2": ["R"],
       "p3": [],
   }

 5) CÓMO VER AGILIDAD (por qué sale vacío y cómo activarlo)
 -----------------------------------------------------------------------------
 - Si la serie 'agility' aparece vacía es porque no has pasado agility_fn a run_offline_simulation(...).
 - Conecta tu métrica propia (p. ej. centralidad de evacuación) así:

   # Ejemplo básico con un diccionario de centralidades por nodo:
   agility_fn = lambda H, path: sum(C_ev.get(n, 0.0) for n in path[1:-1]) if path and len(path) > 2 else 0.0

   results = run_offline_simulation(..., agility_fn=agility_fn, ...)

 - Proxy rápido (mientras no integres tu módulo): usa betweenness S→T con networkx y guarda C_ev por nodo
   para luego sumar en la ruta. (Precómputo recomendado.)

 6) POR QUÉ R SE VE “VACÍO” Y CÓMO LLENARLO
 -----------------------------------------------------------------------------
 - R se calcula por defecto en replan (y opcionalmente en frame 0); 
   si no hay replan o no lo fuerzas, verás NaN.
 - Para verlo SIEMPRE (más caro): compute_R_each_frame=True en run_offline_simulation(...).
 - Para provocar replan (si buscas contraste): baja τ, sube BETA_RISK o suaviza/ritma el evento para abrir alternativas.

 7) TÍTULOS, LEYENDA Y CONTEXTO DEL EXPERIMENTO
 -----------------------------------------------------------------------------
 - El título se arma con PLOT_OPTS["title_template"] y los campos de run_cfg:
     {tag}, {algo}, {profile}, {tau}, {beta}, {robust}
 - Además se muestra un recuadro con: algoritmo, perfil, τ, β, robustez y resumen del EVENT_KIND/params.
 - Puedes sombrear la ventana del evento con PLOT_OPTS["show_event_span"]=True (se calcula t0..t1).

 8) NOTAS DE RENDIMIENTO / CUIDADOS
 -----------------------------------------------------------------------------
 - A* necesita heurística con firma heuristic(u, v). Usa la euclídea si positions están completos; si no, heurística 0. 
 - Métricas de conectividad/centralidad pueden ser costosas si las recalculas cada frame → precomputar o muestrear.
 - Penalización por riesgo: w' = base*(1 + β*r_edge) con r_edge∈[0,1]. Mantén w' ≥ base y > 0.
 - τ alto + eventos agresivos estrechan H ⇒ menos alternativas ⇒ menos diferencias entre algoritmos.
 - EMA_ALPHA suaviza los scores (0.2–0.4 típico). None = respuesta “seca” (útil para depurar perfiles temporales).

 9) COMPARAR ALGORITMOS EN LA MISMA SITUACIÓN
 -----------------------------------------------------------------------------
 - Ejecuta varios runs cambiando sólo ALGORITHM (o β/τ) y usa plot_compare_cost(...) para superponer cost_total.
 - También puedes extender ese comparador para dibujar otras series (misma mecánica: pasar listas de results/cfgs).

 10) DÓNDE TOCAR PARA CAMBIAR QUÉ SE DIBUJA
 -----------------------------------------------------------------------------
 - CONFIG → PLOT_OPTS["panels"]  (elige series por panel)
 - plot_summary(...) → series_map (declara nuevas series)
 - run_offline_simulation(...) → calcular las series (y añadir al dict results)

 =============================================================================
"""

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

# --------------------- Movididad (OPCIONAL) ---------------------
APPLY_MOBILITY_FILTER = True                 # Si True, filtra por locomociones permitidas
ALLOWED_LOCOMOTIONS   = ("WALK", "RAMP")     # Locomociones permitidas
TREAT_GENERAL_AS_WALK = True                 # Si un nodo carece de locomotion y kind=="GENERAL", trátalo como WALK

# Simulación/visualización
SOURCE_NODE = "ND-009"              # Origen fijo (si None, usa el primer nodo)
TAU = 0.60                          # Umbral de seguridad: nodos con score >= TAU son transitables
INTERVAL_MS = 80                    # Milisegundos por frame en la animación (GIF)
DT  = 0.50                          # Segundos simulados por frame (t = frame * DT)
N_FRAMES = 350                      # Número total de frames (duración de la sim)
EMA_ALPHA = 0.30                    # Suavizado EMA de scores; None para desactivar
SAVE_GIF = True                    # Guardar GIF al final (requiere pillow)
OUT_GIF  = "route_dynamics.gif"     # Nombre de archivo GIF

# (Opcional) salidas manuales (si la BD no las tiene marcadas)
EMERGENCY_EXIT_NODE_IDS: Set[str] = set()  # e.g., {"ND-021","ND-030"}

# ================== COSTE BI-CRITERIO (MODO 2) ============
# BETA_RISK = 0.0 -> tiempo puro (Modo 1)
# BETA_RISK > 0   -> tiempo + penalización por riesgo (Modo 2/3)
BETA_RISK = 0.00

# ============== SELECCIÓN ROBUSTA (MODO 3) ================
""" Nota:
Valores guía
    ROBUST_SELECT=True
    ROBUST_TAU ∈ [0.15, 0.30] (0.20 es buen inicio)
    ROBUST_K ∈ [6, 10] (subirlo aumenta CPU; en grafos pequeños 6 basta)
"""
# Si activas robustez, el selector elige entre las k-rutas la de mayor R
ROBUST_SELECT = False        # FALSE: Planificación normal (Dikstra/A*/Yen top-1) TRUE: Selección robusta, explora varias rutas y elige la que maximice R
ROBUST_TAU    = 0.20         # Tolerancia de sobrecoste permitido a la ruta más barata [τ (aceptamos coste ≤ (1+τ)·C0)] NOTA: NO ES EL MISMO "TAU" QUE EL UMBRAL DE SEGURIDAD, ESTE ROBUST_TAU ES SOLO DE SELECCIÓN DE RUTA
ROBUST_K      = 6            # nº de rutas candidatas que se consideran (via Yen = nx.shortest_simple_paths)

# Cálculo de R en offline: por defecto sólo en replan (y frame 0); si True, en todos los frames (más caro)
COMPUTE_R_EACH_FRAME = False

# ================== AGILIDAD (opcional) ===================
RECALC_CENTRALITY_ON_CHANGE = False   # True para habilitar
SHOW_AGILITY_IN_TITLE = False         # True para mostrar suma de centralidad en el título

# ============== CATALOGO PERFILES DE MOVILIDAD ========
@dataclass
class ProfileCfg:
    name: str
    tau: float
    allowed_locomotions: tuple
    treat_general_as_walk: bool
    
PROFILES = {
    "GENERAL": ProfileCfg("GENERAL", tau=0.60, allowed_locomotions=("WALK","RAMP"), treat_general_as_walk=True),
    "PMR":     ProfileCfg("PMR",     tau=0.75, allowed_locomotions=("RAMP",),      treat_general_as_walk=False),
}
# ===================== PERFIL / MOVILIDAD =================
# Perfil activo (umbral τ y reglas de movilidad). Debes tenerlos definidos como dataclasses/tuplas.
# Ejemplo:
#   ProfileCfg(name="GENERAL", tau=0.60)
#   ProfileCfg(name="PMR",     tau=0.75)

ACTIVE_PROFILE = PROFILES["GENERAL"]  # cambia a "PMR" cuando quiera un Perfil de Movilidad Reducida
# (Opcional) Flags de movilidad si los usas en graph_utils:
# TREAT_GENERAL_AS_WALK = True

# ============== ALGORITMOS CATALOGO ========

@dataclass
class AlgoCfg:
    name: str                 # "dijkstra" | "astar" | "yen_ksp"
    params: dict

# ================ ALGORITMO DE RUTA (SELECCIÓN) ===========
# Objeto AlgoCfg(name, params). Soportados:
#   - "dijkstra"
#   - "astar"      -> params={"heuristic": "euclidean"}
#   - "yen_ksp"    -> params={"k": 3}
ALGORITHM = AlgoCfg(name="astar", params={"heuristic": "euclidean"})

# ===================== ESCENARIO / SCORES =================
# Tipo de evento que genera las "ventanas" de score dinámico:
#   "none" | "fire_radial" | "linear_front" | "manual_sequence"
EVENT_KIND = "manual_sequence"

EVENT_PARAMS = {
    
    "groups": [
        
        "050",                    # Fase 0: cae ND-050
        "007",                    # Fase 1: cae ND-007
        ["029", "045", "030"],    # Fase 2: caen EN PARALELO ND-029, ND-045, ND-030
        {"006","030"},             # Fase 3
        ["028", "044", "049","032", "054", "033"],    # Fase 4 (paralelo)
        "012",                    # Fase 5
        "033",                    # Fase 8
        ["055", "034", "056"]     # Fase 9 (paralelo)        
    ],
    
    "t0": 10.0,             # Inicio de la primer fase
    "phase_step": 8.0,      # separacion temporal entre fases
    "dip": 0.45,            # Score minimo durante cada fase IMPORTANTE: si dip < τ (tau del perfil activo), el nodo se vuelve INTRANSITABLE
    "recover": 30.0,        # Duración total de triangle   (SE IGNORA CON SI USAS ramp_holde)
    "id_prefix": "ND-",     # p.ej. "ND-" si tus nodos reales son "ND-050"
    
    # ---- NUEVO: forma de la ventana ----
    "shape": "ramp_hold",  # "triangle" (default) o "ramp_hold"
    "ramp_down": 6.0,      # rampam de bajada en segnundos
    "hold_dur": 80.0,      # Meseta (hold)
    "ramp_up": 8.0         # Subida de la rapma en segundos
}

# ===================== PLOTS / RESUMEN ====================
SHOW_ANIMATION = True          # False => no animación, solo cómputo + gráficos finales
SHOW_SUMMARY_PLOTS = False       # mostrar gráficos estáticos al finalizar

PLOT_OPTS = {
    # Plantilla del título (se rellenan las llaves con datos del run)
    "title_template": "{tag} | algo={algo} | perfil={profile} (τ={tau:.2f}) | β={beta:.2f} | robust={robust}",

    # Qué métricas se dibujan en cada panel (elige entre: cost_total, time_base, risk_penal, path_len, safe_nodes, R)
    "panels": {
        "p1": ["cost_total"],                           # panel superior    "p1": ["cost_total"],           
        "p2": ["path_min_score", "path_mean_score"],    # panel medio       "p2": ["time_base", "risk_penal"],  
        "p3": ["agility", "R"],                         # panel inferior    "p3": ["R"],                    
    },

    "annotate_replans": True,      # marcar replan (puntos) en el panel donde haya coste
    "show_event_span":  True,       # sombrear ventana del evento si se puede deducir t0 y duración
    "show_legend_box":  True,       # recuadro con condiciones del experimento
    "legend_loc": "upper right",   # esquina del panel superior

    "save_path": None,             # p.ej. "summary_plot.png"
    "dpi": 150
}


# ===========================================================================
# ====================== FIN CONFIGURACION ==================================
# ===========================================================================

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
        allowed_locomotions=ACTIVE_PROFILE.allowed_locomotions,
        treat_general_as_walk=ACTIVE_PROFILE.treat_general_as_walk
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
    
    # === Construcción de SCENARIO según configuración ===
    if EVENT_KIND == "fire_radial":
        SCENARIO = make_fire_scenario_radial(
            node_ids=node_ids,
            positions=positions,
            **EVENT_PARAMS
        )
    elif EVENT_KIND == "linear_front":
        SCENARIO = make_linear_front_scenario(
            node_ids=node_ids,
            positions=positions,
            **EVENT_PARAMS
        )
    elif EVENT_KIND == "manual_sequence":
        SCENARIO = make_manual_sequence_scenario(
            node_ids=node_ids,
            **EVENT_PARAMS
        )
    else:
        SCENARIO = {}  # sin evento -> todos los nodos quedan en DEFAULT_SCORE

 
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
    
    
    def _euclidean_h_uv(positions):
        """Heurística admisible: distancia euclídea entre u y v usando positions."""
        def h(u, v):
            pu = positions.get(u)
            pv = positions.get(v)
            if not pu or not pv:
                return 0.0  # sin posiciones => heurística nula (A* degenera a Dijkstra)
            (x1, y1), (x2, y2) = pu, pv
            return math.hypot(x1 - x2, y1 - y2)
        return h

    def shortest_path_with_algo(G, src, dst, positions, algo_cfg: AlgoCfg, weight="weight"):
        name, p = algo_cfg.name, algo_cfg.params
        if name == "dijkstra":
            path = nx.shortest_path(G, src, dst, weight=weight)
            cost = nx.path_weight(G, path, weight=weight)
            return path, cost
        elif name == "astar":
            heur = p.get("heuristic", "euclidean")
            if heur == "euclidean":
                h = _euclidean_h_uv(positions)    # ← ESTA
            else:
                h = lambda u, v: 0.0              # ← firma de 2 args
            path = nx.astar_path(G, src, dst, heuristic=h, weight=weight)
            cost = nx.path_weight(G, path, weight=weight)
            return path, cost

        elif name == "yen_ksp":
            k = int(p.get("k", 3))
            best_path, best_cost = None, float("inf")
            for i, pth in enumerate(nx.shortest_simple_paths(G, src, dst, weight=weight)):
                c = nx.path_weight(G, pth, weight=weight)
                if c < best_cost:
                    best_path, best_cost = pth, c
                if i + 1 >= k:
                    break
            if best_path is None:
                raise nx.NetworkXNoPath
            return best_path, best_cost
        else:
            raise ValueError(f"Algoritmo no soportado: {name}")


    def robustness_index(H: nx.Graph, path: list, tau: float, algo_cfg, positions, weight="weight") -> int:
        """
        Índice R: nº de aristas del path que se pueden 'romper' sin que el coste supere (1+tau)*C0.
        No modifica H de forma permanente.
        """
        if not path or len(path) < 2:
            return 0
        try:
            C0 = nx.path_weight(H, path, weight=weight)
        except Exception:
            return 0

        R = 0
        for a, b in zip(path, path[1:]):
            if not H.has_edge(a, b):
                continue
            # guardamos el peso y 'rompemos' la arista
            w_backup = H[a][b].get(weight, None)
            H[a][b][weight] = float("inf")
            try:
                alt_path, alt_cost = shortest_path_with_algo(H, path[0], path[-1], positions, algo_cfg, weight=weight)
                if alt_cost <= (1.0 + tau) * C0:
                    R += 1
            except Exception:
                pass
            # restauramos
            if w_backup is None:
                del H[a][b][weight]
            else:
                H[a][b][weight] = w_backup
        return R

    def run_offline_simulation(
        G, positions, node_ids, mobility_mask,
        source, emergency_nodes,
        score_fn, reset_scores,
        tau,                      # p.ej. PROFILE.tau
        beta_risk,                # p.ej. BETA_RISK
        algo_cfg,                 # p.ej. ALGORITHM
        dt, n_frames,             # p.ej. DT, N_FRAMES
        robust_select=False,      # p.ej. ROBUST_SELECT
        robust_tau=0.20,          # p.ej. ROBUST_TAU
        robust_k=6,                # p.ej. ROBUST_K
        # --- NUEVO ---
        agility_fn=None,                 # callable(H, path) -> float, opcional
        compute_R_each_frame=False       # si True, calcula R en todos los frames (más caro)

    ):
        """Simula frame a frame sin animación y devuelve series para graficar al final."""
        # series nuevas
        agility_series = []
        path_min_score_series = []
        path_mean_score_series = []
        overlap_series = []
    
        prev_scores = reset_scores()
        prev_path = None
        replans = 0

        # series
        t_series, time_base_series, risk_penal_series, cost_total_series = [], [], [], []
        path_len_series, safe_nodes_series, R_series = [], [], []
        replan_flags, plan_ms_series, robust_ms_series = [], [], []

        for frame in range(n_frames):
            t = frame * dt
            scores = score_fn(t, prev_scores=prev_scores)
            prev_scores = scores

            # Mapeo ID -> score SIEMPRE (lo usaremos en riesgo y métricas de ruta)
            scores_by_id = {node_ids[i]: float(scores[i]) for i in range(len(node_ids))}
            
            # Filtrado de nodos seguros y movilidad (si aplica)
            safe_nodes = [node_ids[i] for i in range(len(node_ids)) if float(scores[i]) >= tau]
            if mobility_mask is not None:
                safe_nodes = [n for n in safe_nodes if mobility_mask.get(n, False)]
            H = G.subgraph(safe_nodes).copy()

            # Penalización de riesgo en aristas (bi-criterio)
            if beta_risk > 0.0:
                scores_by_id = {node_ids[i]: float(scores[i]) for i in range(len(node_ids))}
                for u, v, d in H.edges(data=True):
                    su = scores_by_id.get(u, 1.0); sv = scores_by_id.get(v, 1.0)
                    ru, rv = (1.0 - su), (1.0 - sv)
                    r_edge = max(ru, rv)
                    base = float(d.get("weight", 1.0))
                    d["weight"] = base * (1.0 + beta_risk * r_edge)

            # Búsqueda de ruta
            t0_plan = time.perf_counter()
            path, cost, R_opt = None, float("inf"), np.nan

            if not robust_select:
                # Mejor salida por coste
                for ex in emergency_nodes:
                    if source in H and ex in H:
                        try:
                            p, c = shortest_path_with_algo(H, source, ex, positions, algo_cfg, weight="weight")
                            if c < cost:
                                path, cost = p, c
                        except (nx.NetworkXNoPath, nx.NodeNotFound):
                            pass
            else:
                # Selección robusta: k rutas y elige max R dentro de (1+τ)*C0
                for ex in emergency_nodes:
                    if source in H and ex in H:
                        try:
                            candidates = []
                            for i, pth in enumerate(nx.shortest_simple_paths(H, source, ex, weight="weight")):
                                cst = nx.path_weight(H, pth, weight="weight")
                                candidates.append((pth, cst))
                                if i+1 >= robust_k: break
                            if not candidates:
                                continue
                            C0 = min(c for _, c in candidates)
                            best_p, best_c, best_r = None, float("inf"), -1
                            for pth, cst in candidates:
                                if cst <= (1.0 + robust_tau) * C0:
                                    R_here = robustness_index(H, pth, robust_tau, algo_cfg, positions, weight="weight")
                                    if (R_here > best_r) or (R_here == best_r and cst < best_c):
                                        best_p, best_c, best_r = pth, cst, R_here
                            if best_p is None:
                                best_p, best_c = min(candidates, key=lambda pc: pc[1])
                                best_r = robustness_index(H, best_p, robust_tau, algo_cfg, positions, weight="weight")
                            if best_c < cost:
                                path, cost, R_opt = best_p, best_c, best_r
                        except (nx.NetworkXNoPath, nx.NodeNotFound):
                            pass

            plan_ms = (time.perf_counter() - t0_plan) * 1000.0

            # Descomposición de coste (base + penalización)
            if path:
                time_base = 0.0
                risk_penal = 0.0
                for a, b in zip(path, path[1:]):
                    w_full = float(H[a][b]["weight"])
                    if beta_risk > 0.0:
                        su = scores_by_id.get(a, 1.0); sv = scores_by_id.get(b, 1.0)
                        ru, rv = (1.0 - su), (1.0 - sv)
                        r_edge = max(ru, rv)
                        denom = (1.0 + beta_risk * r_edge)
                        base_here = w_full / denom if denom > 0 else w_full
                    else:
                        base_here = w_full
                    time_base += base_here
                    risk_penal += (w_full - base_here)
                cost_total = time_base + risk_penal
            else:
                time_base, risk_penal, cost_total = 0.0, 0.0, float("inf")

            # Replan (cambio de ruta)
            replan = 1 if (prev_path is None or path != prev_path) else 0
            robust_ms = np.nan
            
            if replan and path and np.isnan(R_opt):
                t0_r = time.perf_counter()
                R_opt = robustness_index(H, path, robust_tau, algo_cfg, positions, weight="weight")
                robust_ms = (time.perf_counter() - t0_r) * 1000.0
            prev_path = list(path) if path else None

            # --- NUEVO: calcular R al inicio y/o cada frame si se pide ---
            if path:
                if compute_R_each_frame or frame == 0:
                    R_opt = robustness_index(H, path, robust_tau, algo_cfg, positions, weight="weight")
                elif replan and np.isnan(R_opt):
                    t0_r = time.perf_counter()
                    R_opt = robustness_index(H, path, robust_tau, algo_cfg, positions, weight="weight")
                    robust_ms = (time.perf_counter() - t0_r) * 1000.0

            # --- NUEVO: métricas de seguridad de la ruta ---
            if path:
                p_scores = [scores_by_id.get(n, 1.0) for n in path]
                path_min = float(min(p_scores)) if p_scores else np.nan
                path_mean = float(sum(p_scores) / len(p_scores)) if p_scores else np.nan
            
            else:
                path_min, path_mean = np.nan, np.nan

            # --- NUEVO: agilidad (si nos pasan función) ---
            if path and callable(agility_fn):
                try:
                    agility_val = float(agility_fn(H, path))
                except Exception:
                    agility_val = np.nan
            else:
                agility_val = np.nan

            # --- NUEVO: solapamiento con ruta anterior (0..1) ---
            if path and prev_path:
                a = set(path); b = set(prev_path)
                overlap = len(a & b) / float(len(a | b)) if (a or b) else np.nan
            else:
                overlap = np.nan

            prev_path = list(path) if path else None
            if replan: replans += 1

            # Acumular series
            t_series.append(t)
            time_base_series.append(time_base)
            risk_penal_series.append(risk_penal)
            cost_total_series.append(cost_total)
            path_len_series.append(len(path) if path else 0)
            safe_nodes_series.append(len(safe_nodes))
            R_series.append(R_opt if not np.isnan(R_opt) else np.nan)
            replan_flags.append(replan)
            plan_ms_series.append(plan_ms)
            robust_ms_series.append(robust_ms)
            agility_series.append(agility_val)
            path_min_score_series.append(path_min)
            path_mean_score_series.append(path_mean)
            overlap_series.append(overlap)

        return dict(
            t=np.array(t_series),
            time_base=np.array(time_base_series),
            risk_penal=np.array(risk_penal_series),
            cost_total=np.array(cost_total_series),
            path_len=np.array(path_len_series),
            safe_nodes=np.array(safe_nodes_series),
            R=np.array(R_series),
            replan=np.array(replan_flags),
            plan_ms=np.array(plan_ms_series),
            robust_ms=np.array(robust_ms_series),
            replans_total=replans,
            # --- NUEVO ---
            agility=np.array(agility_series),
            path_min_score=np.array(path_min_score_series),
            path_mean_score=np.array(path_mean_score_series),
            overlap_prev=np.array(overlap_series),
        )

    def _brief_event(event_kind: str, params: dict):
        """Construye un string corto con los parámetros más relevantes del evento."""
        if not event_kind or not params:
            return "evento: none"
        try:
            if event_kind == "fire_radial":
                return (f"evento: fire_radial | center={params.get('center_node')} | "
                        f"t0={params.get('t0')}s | spread={params.get('spread_speed')} s/m | "
                        f"dip={params.get('dip')} | rec={params.get('recover')}s")
            if event_kind == "linear_front":
                return (f"evento: linear_front | p0={params.get('p0_node')} -> p1={params.get('p1_node')} | "
                        f"t0={params.get('t0')}s | speed={params.get('speed')} s/m | "
                        f"dip={params.get('dip')} | rec={params.get('recover')}s")
            if event_kind == "manual_sequence":
                groups = params.get("groups", [])
                nf = len(groups)
                shape = params.get("shape", "triangle")
                t0 = params.get("t0"); step = params.get("phase_step")
                dip = params.get("dip"); rp = params.get("recover")
                rd = params.get("ramp_down"); hd = params.get("hold_dur"); ru = params.get("ramp_up")
                core = f"evento: manual_sequence | fases={nf} | t0={t0}s | step={step}s | dip={dip} | shape={shape}"
                if shape == "triangle":
                    core += f" | rec={rp}s"
                else:
                    core += f" | ramp={rd}/{hd}/{ru}s"
                return core
        except Exception:
            pass
        return f"evento: {event_kind}"

    def _event_span(event_kind: str, params: dict):
        """Devuelve (t_ini, t_fin) aprox para sombrear el evento, o None si no se puede calcular."""
        if not event_kind or not params:
            return None
        try:
            if event_kind in ("fire_radial", "linear_front"):
                t0 = float(params.get("t0", 0.0))
                rec = float(params.get("recover", 0.0))
                return (t0, t0 + rec) if rec > 0 else None
            if event_kind == "manual_sequence":
                t0 = float(params.get("t0", 0.0))
                step = float(params.get("phase_step", 0.0))
                nf = len(params.get("groups", []))
                shape = params.get("shape", "triangle")
                if shape == "triangle":
                    dur = float(params.get("recover", 0.0))
                else:
                    dur = float(params.get("ramp_down", 0.0)) + float(params.get("hold_dur", 0.0)) + float(params.get("ramp_up", 0.0))
                if nf == 0:
                    return None
                t_last_start = t0 + (nf - 1) * step
                return (t0, t_last_start + dur)
        except Exception:
            return None
        return None

    def plot_summary(results: dict, run_cfg: dict, plot_opts: dict, event_kind: str = None, event_params: dict = None):
        """
        Dibuja 3 paneles configurables y un recuadro con condiciones del experimento.
        results: dict devuelto por run_offline_simulation(...)
        run_cfg: dict con las llaves: tag, algo, profile, tau, beta, robust (str)
        plot_opts: diccionario PLOT_OPTS de CONFIG (ver arriba)
        event_kind/event_params: para sombrear y describir el evento
        """
        # --- Datos base ---
        t = results["t"]

        # --- Construcción de figura ---
        fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
        ax0, ax1, ax2 = axes

        # --- Título principal ---
        title = plot_opts.get("title_template", "{tag}").format(**run_cfg)
        ax0.set_title(title)

        # --- Paneles y qué series dibujar ---
        panels = plot_opts.get("panels", {"p1": ["cost_total"], "p2": ["time_base", "risk_penal"], "p3": ["R"]})
        # Mapeo: nombre -> serie
        series_map = {
            "cost_total":   results.get("cost_total"),
            "time_base":    results.get("time_base"),
            "risk_penal":   results.get("risk_penal"),
            "path_len":     results.get("path_len"),
            "safe_nodes":   results.get("safe_nodes"),
            "R":            results.get("R"),
            # NUEVAS
            "agility":          results.get("agility"),
            "path_min_score":   results.get("path_min_score"),
            "path_mean_score":  results.get("path_mean_score"),
            "overlap_prev":     results.get("overlap_prev"),
        }

        axes_map = {"p1": ax0, "p2": ax1, "p3": ax2}
        ylabel_map = {"p1": "Panel 1", "p2": "Panel 2", "p3": "Panel 3"}

        # Dibuja cada panel según la selección
        for key, ax in axes_map.items():
            wanted = panels.get(key, [])
            labels_for_leg = []
            for metric in wanted:
                y = series_map.get(metric)
                if y is None:
                    continue
                ax.plot(t, y, label=metric, lw=2)
                labels_for_leg.append(metric)
            # Replan markers (si procede y si hay coste en este panel)
            if plot_opts.get("annotate_replans", True) and any(m in wanted for m in ("cost_total", "time_base", "risk_penal")):
                idx = np.where(results.get("replan", np.zeros_like(t)) == 1)[0]
                if idx.size > 0 and "cost_total" in wanted and series_map["cost_total"] is not None:
                    ax.scatter(t[idx], series_map["cost_total"][idx], marker='o')  # marcadores en coste
            ax.grid(True, linestyle="--", alpha=0.3)
            # Etiquetas de eje Y amigables
            if key == "p1":
                ax.set_ylabel("Coste / métricas seleccionadas")
            elif key == "p2":
                ax.set_ylabel("Desglose / métricas seleccionadas")
            elif key == "p3":
                ax.set_ylabel("Robustez / métricas seleccionadas")

            # Leyenda por panel, sólo si hay algo que mostrar
            if plot_opts.get("show_legend_box", True) and labels_for_leg:
                ax.legend(loc="best")

        # Eje X común
        ax2.set_xlabel("t (s)")

        # --- Sombreado del evento (si está habilitado y se puede calcular) ---
        if plot_opts.get("show_event_span", True):
            span = _event_span(event_kind, event_params or {})
            if span:
                t0, t1 = span
                for ax in axes:
                    ax.axvspan(t0, t1, alpha=0.15)

        # --- Recuadro con condiciones del experimento (leyenda descriptiva) ---
        if plot_opts.get("show_legend_box", True):
            ev_text = _brief_event(event_kind, event_params or {})
            # Texto de condiciones:
            cond = (
                f"algo={run_cfg['algo']} | perfil={run_cfg['profile']} (τ={run_cfg['tau']:.2f})\n"
                f"β={run_cfg['beta']:.2f} | robust={run_cfg['robust']}\n"
                f"{ev_text}"
            )
            # Caja en la esquina superior derecha del panel superior
            ax0.text(
                0.99, 0.98, cond,
                transform=ax0.transAxes,
                ha="right", va="top",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.7", alpha=0.9)
            )

        plt.tight_layout()

        # Guardado opcional
        save_path = plot_opts.get("save_path")
        if save_path:
            try:
                dpi = int(plot_opts.get("dpi", 150))
                plt.savefig(save_path, dpi=dpi, bbox_inches="tight")
                print(f"[OK] Figura guardada en: {save_path}")
            except Exception as e:
                print(f"[AVISO] No se pudo guardar la figura: {e}")


    
    # ------------------ Ruta a la "mejor" salida ------------------
    def best_exit_path(H: nx.Graph, src: str, exits: Set[str]) -> Tuple[Optional[List[str]], float]:
        # Recorre todas las salidas y elige la ruta con menor coste (weight)
        best_path, best_cost = None, float("inf")
        for ex in exits:
            if src in H and ex in H: # ambos nodos deben existir en el subgrafo seguro
                try:
                    p, c = shortest_path_with_algo(H, src, ex, positions, ALGORITHM, weight="weight")
                    if c < best_cost:
                        best_cost, best_path = c, p
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue # ignora salidas no alcanzables
        return best_path, best_cost
    # ----------
    C_ev = {}                      # cache centralidad actual
    prev_safe_set = set()          # safe_nodes del frame anterior

    def recalc_centrality_if_needed(H: nx.Graph, safe_nodes: List[str], source: str, exits: set):
        global C_ev, prev_safe_set
        if not RECALC_CENTRALITY_ON_CHANGE:
            return
        safe_set = set(safe_nodes)
        if safe_set != prev_safe_set:
            try:
                C_ev = betweenness_centrality_subset(H, sources={source}, targets=exits, normalized=True)
            except Exception:
                C_ev = {}
            prev_safe_set = safe_set

    # ------------------ Función por frame ------------------
    def animate(frame):
        nonlocal prev_scores
        t = frame * DT                                 # tiempo simulado actual
        scores = score_fn(t, prev_scores=prev_scores)  # vector de scores para t
        prev_scores = scores                           # guarda para EMA del próximo frame
        set_node_facecolors(scores)                    # repinta nodos según score(t)


        # --- Filtrado por seguridad (y movilidad si hay máscara) ---
        safe_nodes = [node_ids[i] for i in range(len(node_ids)) if float(scores[i]) >= ACTIVE_PROFILE.tau]
        if mobility_mask is not None:
            # Aplica filtro de movilidad (solo nodos permitidos por locomotion/kind)
            safe_nodes = [n for n in safe_nodes if mobility_mask.get(n, False)]
            
        # Construye subgrafo seguro (copia materializada para operar sin vistas)
        H = G.subgraph(safe_nodes).copy()
        # --- Penalización de riesgo en aristas (bi-criterio) ---
        if BETA_RISK > 0.0:
            scores_by_id = {node_ids[i]: float(scores[i]) for i in range(len(node_ids))}
            for u, v, d in H.edges(data=True):
                su = scores_by_id.get(u, 1.0)
                sv = scores_by_id.get(v, 1.0)
                ru, rv = (1.0 - su), (1.0 - sv)
                r_edge = max(ru, rv)  # conservador; alternativa: 0.5*(ru+rv) o 1 - min(su,sv)
                base = float(d.get("weight", 1.0))  # hoy: metros (interpretable como tiempo base)
                d["weight"] = base * (1.0 + BETA_RISK * r_edge)
                
        recalc_centrality_if_needed(H, safe_nodes, source, emergency_nodes)
        
        if SHOW_AGILITY_IN_TITLE:
            agility = sum(float(C_ev.get(n, 0.0)) for n in path[1:-1])
            title_text.set_text(f"t={t:.1f}s | coste={cost:.2f} | nodos={len(path)} | A={agility:.3f}")

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
            
        # --- logging CSV ---
        epoch_ms = int(time.time() * 1000)
        path_len = len(path) if path else 0
        note = "no_path" if not path else ""
        csv_w.writerow([epoch_ms, frame, f"{t:.2f}", ALGORITHM.name, ACTIVE_PROFILE.name,
                        len(safe_nodes), path_len, f"{cost:.3f}", len(emergency_nodes), note])
        csv_f.flush()
        return nodes_artist, path_line, title_text  # artistas que se redibujan
    
    LOG_CSV_PATH = "run_metrics.csv"
    csv_f = open(LOG_CSV_PATH, "w", newline="", encoding="utf-8")
    csv_w = csv.writer(csv_f)
    csv_w.writerow(["epoch_ms","frame","t","algo","profile","safe_nodes","path_len","cost","exit_count","note"])

    
    # ===================== ANIMACIÓN vs MODO OFFLINE ===================== #
    if SHOW_ANIMATION:
        # --- ANIMACIÓN (tu flujo de siempre) ---
        anim = FuncAnimation(
            fig, animate, init_func=init, frames=N_FRAMES,
            interval=INTERVAL_MS, blit=False, repeat=False
        )
        if SAVE_GIF:
            try:
                fps = max(1, int(round(1000.0 / INTERVAL_MS)))
                anim.save(OUT_GIF, writer="pillow", fps=fps)
                print(f"[OK] Guardado GIF: {OUT_GIF} (fps={fps})")
            except Exception as e:
                print(f"[AVISO] No se pudo guardar GIF: {e}")
        plt.tight_layout()
        plt.show()
        # cerramos el CSV usado por la animación
        try:
            csv_f.close()
        except Exception:
            pass

    else:
        # --- MODO OFFLINE (SIN animación): simulamos y mostramos gráficos finales ---
        # El CSV por-frame de la animación no se usa en este modo. Cerramos si está abierto:
        try:
            csv_f.close()
        except Exception:
            pass

        results = run_offline_simulation(
            G=G,
            positions=positions,
            node_ids=node_ids,
            mobility_mask=data["mobility_mask"],
            source=source,
            emergency_nodes=emergency_nodes,
            score_fn=score_fn,
            reset_scores=reset_scores,
            tau=ACTIVE_PROFILE.tau,   # o PROFILE.tau si usas ese alias
            beta_risk=BETA_RISK,
            algo_cfg=ALGORITHM,
            dt=DT,
            n_frames=N_FRAMES,
            robust_select=ROBUST_SELECT,
            robust_tau=ROBUST_TAU,
            robust_k=ROBUST_K,
            # --- NUEVO: si quieres R en todos los frames y/o agilidad ---
            compute_R_each_frame=False,       # pon True si quieres puntos de R en toda la serie
            
            # PARA IMPLEMENTAR MI C_EV -> agility_fn=lambda H, path: sum(C_ev.get(n, 0.0) for n in path[1:-1]) if path and len(path)>2 else 0.0
            agility_fn=None                   # reemplaza por tu función, p.ej.: lambda H,p: sum(C_ev.get(n,0) for n in p[1:-1])

        )

        if SHOW_SUMMARY_PLOTS:
            tag = globals().get("RUN_TAG", "RUN")
            run_cfg = {
                "tag": tag,
                "algo": ALGORITHM.name,
                "profile": ACTIVE_PROFILE.name,
                "tau": ACTIVE_PROFILE.tau,
                "beta": BETA_RISK,
                "robust": f"on (τ={ROBUST_TAU}, k={ROBUST_K})" if ROBUST_SELECT else "off",
            }
            plot_summary(
                results=results,
                run_cfg=run_cfg,
                plot_opts=PLOT_OPTS,
                event_kind=EVENT_KIND,
                event_params=EVENT_PARAMS
            )
            plt.show()

    # ===================================================================== #


# Punto de entrada si ejecutas el script directamente (python animate_dynamic_route.py)
if __name__ == "__main__":
    main()

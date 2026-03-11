# -----------------------------------------------------------------------------
# Propósito del módulo
# --------------------
# - Definir primitivas sencillas para generar "scores" (valores en [0,1])
#   por nodo en función del tiempo: clamp, interpolación lineal, rampas, triángulos, EMA.
# - Construir una función de evaluación "score_at(t)" que devuelve el vector de
#   scores alineado con la lista de node_ids, a partir de un "escenario" de ventanas
#   por nodo (hold/ramp/triangle).
# - Opcionalmente aplicar suavizado exponencial (EMA) para reducir parpadeo.
#
# Este módulo no conoce gráfos ni rutas: sólo produce señales de "seguridad" por nodo
# que luego pueden usarse para colorear, filtrar o penalizar rutas.
# -----------------------------------------------------------------------------
from __future__ import annotations # permite anotaciones de tipos como strings (futuras)
from typing import Dict, List, Tuple, Callable, Optional, Union
import numpy as np # trabajamos con vectores/arrays numéricos
import math

ScoreArray = np.ndarray  # vector float32/float64 con orden de node_ids

# ---------- primitivas simples ----------
def clamp01(x: float) -> float:
    """Satura x al rango [0,1]. Útil para garantizar que el score no sale del rango."""
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def lerp(a: float, b: float, u: float) -> float:
    """Interpolación lineal: devuelve a + (b - a) * u. Se asume u ∈ [0,1]."""
    # u in [0,1]
    return a + (b - a) * u

def ramp(t: float, t0: float, dur: float, v_from: float, v_to: float) -> float:
    """
    Rampa lineal: a partir de t0, en duración 'dur', va de v_from a v_to.
    Antes de t0 devuelve v_from; si dur<=0 pasa directamente a v_to.
    """
    if t < t0:
        return v_from
    if dur <= 0:
        return v_to
    u = (t - t0) / dur # progreso normalizado [0,1]
    if u >= 1.0:
        return v_to
    return lerp(v_from, v_to, u)

def triangle(t: float, t0: float, dur: float, v_min: float, v_max: float) -> float:
    """
    Onda triangular simétrica:
      - desciende linealmente de v_max a v_min en la primera mitad,
      - asciende linealmente de v_min a v_max en la segunda mitad.
    Antes de t0 y después de t0+dur devuelve v_max.
    """
    
    # descenso lineal hasta v_min y ascenso de vuelta hasta v_max (simétrico)
    if dur <= 0:
        return v_max
    half = 0.5 * dur
    if t < t0:
        return v_max
    u = t - t0
    if u <= half:
        # bajando: v_max -> v_min
        return lerp(v_max, v_min, u / half)
    if u >= dur:
        return v_max
    # subiendo: v_min -> v_max
    return lerp(v_min, v_max, (u - half) / half)

def ema(prev: float, new: float, alpha: float) -> float:
    """
    Exponential Moving Average (EMA):
      out = alpha * new + (1 - alpha) * prev
    alpha en (0,1]: cuanto más grande, más responde (menos suavizado).
    """
    # alpha in (0,1]; más grande = responde más rápido (menos suave)
    return alpha * new + (1.0 - alpha) * prev

# Formatos admitidos por ventana (por nodo), como tuplas:
#  - ("hold", t0, dur, v)                 -> valor constante v durante [t0, t0+dur]
#  - ("ramp", t0, dur, v_from, v_to)      -> rampa lineal de v_from a v_to
#  - ("triangle", t0, dur, v_min, v_max)  -> baja a v_min y sube a v_max (simétrica)

Window = Tuple # alias genérico; cada "ventana" es una tupla con el formato anterior

def build_score_fn(
    node_ids: List[str],                
    scenario: Dict[str, List[Window]],
    default: float = 1.0,                # cuando no hay ninguna ventana activa lo normal será 1
    ema_alpha: Optional[float] = None,   # p.ej. 0.3 para suavizar, None = sin suavizado
    combine: str = "min"                 # si un nodo tiene ventanas solapadas: "min" o "last"
) -> Tuple[Callable[[float, Optional[ScoreArray]], ScoreArray], Callable[[], ScoreArray]]:
    """
    Construye las funciones:
      - score_at(t, prev_scores) -> vector de scores (float) alineado con node_ids.
        * prev_scores se usa sólo si ema_alpha no es None (suavizado EMA).
      - reset() -> vector lleno de 'default' (por defecto 1.0).

    Notas:
      - El "scenario" se normaliza a índices (no a ids) para evaluar rápido cada frame.
      - combine="min" es conservador: ante varias ventanas activas, se toma el valor mínimo.
      - combine="last" toma el valor de la última ventana que "pase el filtro temporal".
    """
    # Mapa node_id -> índice en el vector de salida
    idx = {nid: i for i, nid in enumerate(node_ids)}
    n = len(node_ids)

    # Normaliza el escenario: pasa de node_ids a índices (int) y copia las ventanas
    norm_scenario: Dict[int, List[Window]] = {}
    for nid, windows in (scenario or {}).items():
        if nid in idx:
            norm_scenario[idx[nid]] = list(windows)

    # Evalúa una sola ventana en el instante t. Devuelve:
    # - un float en [0,1] si la ventana "aplica" en t
    # - None si la ventana no afecta en t (fuera de su intervalo)
    def eval_window(w, t: float):
        kind = w[0]

        if kind == "hold":
            # ("hold", start, dur, val)
            _, start, dur, val = w
            if t < start or t > start + dur:
                return None
            return float(val)

        elif kind == "ramp":
            # ("ramp", start, dur, target)
            # Interpola 1.0 -> target SOLO durante [start, start+dur].
            _, start, dur, target = w
            if t < start or t > start + dur:
                return None            # <<--- CAMBIO CLAVE: fuera del intervalo, no "pinta"
            if dur <= 0.0:
                return float(target)
            alpha = (t - start) / float(dur)  # 0..1
            start_val = 1.0
            return (1.0 - alpha) * start_val + alpha * float(target)
    
        elif kind == "triangle":
            # ("triangle", start, dur, low, high)  -> baja de high a low y vuelve a high
            _, start, dur, low, high = w
            if t < start or dur <= 0.0 or t > start + dur:
                return None
            mid = start + dur / 2.0
            if t <= mid:
                # tramo de bajada: high -> low
                a = (t - start) / (dur / 2.0)  # 0..1
                return float(high) + a * (float(low) - float(high))
            else:
                # tramo de subida: low -> high
                a = (t - mid) / (dur / 2.0)    # 0..1
                return float(low) + a * (float(high) - float(low))

        else:
            # ventana desconocida -> ignora
            return None


    def reset() -> ScoreArray:
        """Crea un vector de longitud n lleno con el valor 'default'."""
        return np.full((n,), float(default), dtype=float)

    def score_at(t: float, prev_scores: Optional[ScoreArray] = None) -> ScoreArray:
        """
        Calcula el vector de scores en el instante t.
        Si ema_alpha no es None y se provee prev_scores, aplica EMA por componente.
        """
        # Inicialmente todo al valor por defecto (normalmente 1.0)
        out = np.full((n,), float(default), dtype=float)
        
        # Recorremos los nodos por índice (0..n-1)
        for i_node in range(n):
            wins = norm_scenario.get(i_node) # ventanas de este nodo (si hay)
            if not wins:
                continue  # sin ventanas -> se mantiene default (1.0)
            if combine == "last":
            
                # Toma el último valor válido (no None) entre las ventanas
                val = None
                for w in wins:
                    v = eval_window(w, t)
                    if v is not None:
                        val = v # nos quedamos con el último que "aplica"
                if val is not None:
                    out[i_node] = clamp01(val) # saturamos a [0,1]
            else: 
                # Estrategia por defecto: "min" (conservador)
                # - Evalúa todas las ventanas activas en t
                # - Si hay valores, toma el mínimo (peor caso = menor seguridad)
                vals = [v for w in wins if (v := eval_window(w, t)) is not None]
                if vals:
                    out[i_node] = clamp01(min(vals))

        # Suavizado opcional por EMA (si se especifica alpha y tenemos vector previo)
        if ema_alpha is not None and prev_scores is not None:
            # Aplicamos EMA componente a componente para evitar "parpadeo"
            out = np.array([ema(prev_scores[k], out[k], ema_alpha) for k in range(n)], dtype=float)
            
        # vector final de scores ∈ [0,1], alineado con node_ids    
        return out  
    # Devolvemos la pareja (función de evaluación, función de reseteo)
    return score_at, reset

# ---------------------------------------------------------------------
# Generadores de escenarios (opcional): incendio radial y frente lineal
# ---------------------------------------------------------------------

def make_fire_scenario_radial(
    node_ids,
    positions,
    center_node: str,
    t0: float = 10.0,          # inicio del evento
    spread_speed: float = 0.8, # s por metro (tiempo que tarda el frente en llegar)
    dip: float = 0.5,          # score mínimo durante el impacto (0..1)
    recover: float = 30.0      # duración total del "triangle" (baja y sube)
) -> Dict[str, List[Window]]:
    """
    Incendio radial: para cada nodo calcula su distancia al centro, y
    programa una ventana 'triangle' que baja de 1.0 a 'dip' y regresa a 1.0.
    El inicio se retrasa según la distancia (t0 + dist * spread_speed).

    Requisitos:
      - 'positions' debe contener posiciones (x,y) para los nodos.
      - Si un nodo no tiene posición, se ignora (quedará con DEFAULT_SCORE).

    Retorna: scenario dict {node_id -> [("triangle", start, recover, dip, 1.0)]}
    """
    if center_node not in positions:
        raise ValueError("center_node no está en 'positions'")

    cx, cy = positions[center_node]
    scenario: Dict[str, List[Window]] = {}
    for nid in node_ids:
        pos = positions.get(nid)
        if not pos:
            continue
        x, y = pos
        dist = math.hypot(x - cx, y - cy)
        start = t0 + dist * spread_speed
        scenario.setdefault(nid, []).append(("triangle", float(start), float(recover), float(dip), 1.0))
    return scenario

def make_linear_front_scenario(
    node_ids,
    positions,
    p0_node: str,              # nodo que marca el origen de la línea
    p1_node: str,              # nodo que marca la dirección de avance
    t0: float = 10.0,          # comienzo
    speed: float = 0.8,        # s por metro de avance proyectado
    dip: float = 0.5,          # mínimo de score
    recover: float = 25.0      # duración del triangle
) -> Dict[str, List[Window]]:
    """
    Frente lineal: proyecta cada nodo sobre la recta p0->p1, y
    programa un 'triangle' cuyo inicio es t0 + proyección*speed.
    Nodos "detrás" de p0 reciben inicio ~ t0 (clamp a 0).

    Retorna: scenario dict {node_id -> [("triangle", start, recover, dip, 1.0)]}
    """
    if p0_node not in positions or p1_node not in positions:
        raise ValueError("p0_node/p1_node no están en 'positions'")

    x0, y0 = positions[p0_node]
    x1, y1 = positions[p1_node]
    vx, vy = (x1 - x0), (y1 - y0)
    denom = vx*vx + vy*vy
    if denom <= 0:
        raise ValueError("p0_node y p1_node no definen una dirección válida")

    scenario: Dict[str, List[Window]] = {}
    for nid in node_ids:
        pos = positions.get(nid)
        if not pos:
            continue
        x, y = pos
        # proyección escalar del vector p0->nodo sobre p0->p1
        px, py = (x - x0), (y - y0)
        s = (px*vx + py*vy) / denom  # s<0: detrás de p0; s>1: más allá de p1
        # solo permitimos avance hacia "delante"
        s_clamped = max(0.0, s)
        start = t0 + s_clamped * speed * math.sqrt(denom)  # escala con la longitud de p0->p1
        scenario.setdefault(nid, []).append(("triangle", float(start), float(recover), float(dip), 1.0))
    return scenario

# ---------------------------------------------------------------------
# Generador de escenario por SECUENCIA MANUAL (fases con grupos en paralelo)
# con soporte de formas: "triangle" (por defecto) o "ramp_hold"
# ---------------------------------------------------------------------
from typing import Dict, List, Union, Tuple

def make_manual_sequence_scenario(
    node_ids,
    groups: List[Union[str, List[str]]],
    t0: float = 5.0,            # arranque Fase 0
    phase_step: float = 6.0,    # separación entre fases (s)
    dip: float = 0.5,           # score mínimo [0..1]
    recover: float = 25.0,      # (solo triangle) duración total baja+sube
    id_prefix: str = "",        # si en BD tienes prefijo, ej. "ND-"
    # --- NUEVO ---
    shape: str = "triangle",    # "triangle" | "ramp_hold"
    ramp_down: float = 6.0,     # (ramp_hold) duración de bajada a dip
    hold_dur: float = 12.0,     # (ramp_hold) duración de meseta en dip
    ramp_up: float = 8.0        # (ramp_hold) duración de subida a 1.0
) -> Dict[str, List[Window]]:
    """
    groups: lista de fases; cada fase es un str (nodo) o list[str] (paralelo).
    Ejemplo:
      ["050","007",["029","045","030"],"006",["028","044","049"],"012",["032","054","033"]]

    shape:
      - "triangle": crea una sola ventana Triangle (start, recover, dip -> 1.0).
      - "ramp_hold": crea 3 ventanas: ramp down -> hold -> ramp up.

    Notas:
      - Si un ID no existe en node_ids, se ignora silenciosamente.
      - Con "ramp_hold", el 'recover' no se usa; la duración total es ramp_down+hold_dur+ramp_up.
    """
    scenario: Dict[str, List[Window]] = {}
    node_set = set(map(str, node_ids))

    use_triangle = (shape == "triangle")
    use_ramp_hold = (shape == "ramp_hold")

    for k, g in enumerate(groups):
        start = float(t0 + k * phase_step)
        ids = g if isinstance(g, list) else [g]
        for nid in ids:
            nid = f"{id_prefix}{nid}" if id_prefix else str(nid)
            if nid not in node_set:
                # ID no presente en node_ids -> lo ignoramos
                continue
            if use_triangle:
                # baja a dip y sube a 1.0 en 'recover' segundos
                scenario.setdefault(nid, []).append(("triangle", start, float(recover), float(dip), 1.0))
            elif use_ramp_hold:
                # ramp down: 1.0 -> dip
                scenario.setdefault(nid, []).append(("ramp",  start,            float(ramp_down), float(dip)))
                # hold en dip
                scenario[nid].append(("hold",  start + float(ramp_down),        float(hold_dur),  float(dip)))
                # ramp up: dip -> 1.0
                scenario[nid].append(("ramp",  start + float(ramp_down) + float(hold_dur), float(ramp_up), 1.0))
            else:
                raise ValueError(f"shape no soportado: {shape}")

    return scenario

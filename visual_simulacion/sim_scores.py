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
from typing import Dict, List, Tuple, Callable, Optional
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

    def eval_window(w: Window, t: float) -> Optional[float]:
        """
        Evalúa una única ventana 'w' en el tiempo 't'.
        Devuelve un float si la ventana aplica en ese instante o None si no aplica.
        """
        kind = w[0].lower() # tipo: hold/ramp/triangle
        
        if kind == "hold":
            # ("hold", t0, dur, v): constante v dentro del intervalo [t0, t0+dur]
            _, t0, dur, v = w
            if t < t0 or t > (t0 + dur):
                return None
            return float(v)
        elif kind == "ramp":
            # ("ramp", t0, dur, v_from, v_to): rampa de v_from a v_to entre t0 y t0+dur
            _, t0, dur, v_from, v_to = w
            if t < t0:
                return None   # aún no empezó la rampa
            if t >= t0 + dur:
                return float(v_to) # rampa terminada: valor final
            return ramp(t, t0, dur, float(v_from), float(v_to))
        elif kind == "triangle":
             # ("triangle", t0, dur, vmin, vmax): baja a vmin y sube a vmax en 'dur'
            _, t0, dur, vmin, vmax = w
            if t < t0:
                return None # aún no empezó el triángulo
            if t >= t0 + dur:
                return float(vmax) # triángulo terminado: valor final (tope)
            return triangle(t, t0, dur, float(vmin), float(vmax))
        else:
            # Tipo de ventana no reconocido -> ignorar
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


# ---------- Ejemplo rápido ----------
# El bloque siguiente muestra cómo probar el módulo de forma aislada desde CLI:
# - Define una lista de node_ids y un escenario con ventanas de tipo ramp/triangle.
# - Genera score_at y reset via build_score_fn.
# - Simula tiempos t=0..60 con paso 10 y aplica EMA encadenando prev_scores.
#
#if __name__ == "__main__":
#    node_ids = ["ND-001","ND-002","ND-003","ND-004"]
#    scenario = {
#        "ND-002": [("ramp", 10, 20, 1.0, 0.3), ("hold", 30, 10, 0.3), ("ramp", 40, 20, 0.3, 0.9)],
#        "ND-003": [("triangle", 35, 30, 0.5, 1.0)]
#    }
#    score_at, reset = build_score_fn(node_ids, scenario, default=1.0, ema_alpha=0.25, combine="min")
#    s = reset()
#    for t in range(0, 70, 10):
#        s = score_at(t, prev_scores=s)
#        print(t, dict(zip(node_ids, [round(float(x),3) for x in s.tolist()])))

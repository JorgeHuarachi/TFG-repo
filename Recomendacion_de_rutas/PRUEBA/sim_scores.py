# sim_scores.py
from __future__ import annotations
from typing import Dict, List, Tuple, Callable, Optional
import numpy as np

ScoreArray = np.ndarray  # vector float32/float64 con orden de node_ids

# ---------- primitivas simples ----------
def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def lerp(a: float, b: float, u: float) -> float:
    # u in [0,1]
    return a + (b - a) * u

def ramp(t: float, t0: float, dur: float, v_from: float, v_to: float) -> float:
    if t < t0:
        return v_from
    if dur <= 0:
        return v_to
    u = (t - t0) / dur
    if u >= 1.0:
        return v_to
    return lerp(v_from, v_to, u)

def triangle(t: float, t0: float, dur: float, v_min: float, v_max: float) -> float:
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
    # alpha in (0,1]; más grande = responde más rápido (menos suave)
    return alpha * new + (1.0 - alpha) * prev

# ---------- API principal ----------
# Formatos admitidos por ventana (por nodo):
#  - ("hold", t0, dur, v)
#  - ("ramp", t0, dur, v_from, v_to)
#  - ("triangle", t0, dur, v_min, v_max)
Window = Tuple

def build_score_fn(
    node_ids: List[str],
    scenario: Dict[str, List[Window]],
    default: float = 1.0,
    ema_alpha: Optional[float] = None,   # p.ej. 0.3 para suavizar, None = sin suavizado
    combine: str = "min"                 # si un nodo tiene ventanas solapadas: "min" o "last"
) -> Tuple[Callable[[float, Optional[ScoreArray]], ScoreArray], Callable[[], ScoreArray]]:
    """
    Devuelve:
      - score_at(t, prev_scores) -> vector de scores ∈ [0,1] alineado con node_ids.
      - reset() -> vector lleno de 'default' (por defecto 1.0).
    """
    idx = {nid: i for i, nid in enumerate(node_ids)}
    n = len(node_ids)

    # Normaliza el escenario a índices
    norm_scenario: Dict[int, List[Window]] = {}
    for nid, windows in (scenario or {}).items():
        if nid in idx:
            norm_scenario[idx[nid]] = list(windows)

    def eval_window(w: Window, t: float) -> Optional[float]:
        kind = w[0].lower()
        if kind == "hold":
            _, t0, dur, v = w
            if t < t0 or t > (t0 + dur):
                return None
            return float(v)
        elif kind == "ramp":
            _, t0, dur, v_from, v_to = w
            if t < t0:
                return None
            if t >= t0 + dur:
                return float(v_to)
            return ramp(t, t0, dur, float(v_from), float(v_to))
        elif kind == "triangle":
            _, t0, dur, vmin, vmax = w
            if t < t0:
                return None
            if t >= t0 + dur:
                return float(vmax)
            return triangle(t, t0, dur, float(vmin), float(vmax))
        else:
            return None

    def reset() -> ScoreArray:
        return np.full((n,), float(default), dtype=float)

    def score_at(t: float, prev_scores: Optional[ScoreArray] = None) -> ScoreArray:
        out = np.full((n,), float(default), dtype=float)
        for i_node in range(n):
            wins = norm_scenario.get(i_node)
            if not wins:
                continue  # se queda default (1.0)
            if combine == "last":
                val = None
                for w in wins:
                    v = eval_window(w, t)
                    if v is not None:
                        val = v
                if val is not None:
                    out[i_node] = clamp01(val)
            else:  # "min" (conservador)
                vals = [v for w in wins if (v := eval_window(w, t)) is not None]
                if vals:
                    out[i_node] = clamp01(min(vals))

        # suavizado opcional EMA
        if ema_alpha is not None and prev_scores is not None:
            out = np.array([ema(prev_scores[k], out[k], ema_alpha) for k in range(n)], dtype=float)
        return out

    return score_at, reset

# ---------- Ejemplo rápido ----------
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
#        print(t, dict(zip(node_ids, [round(float(x),3) for x in s.tolist()])))#

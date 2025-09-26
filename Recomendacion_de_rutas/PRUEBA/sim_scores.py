# sim_scores.py
import time
from datetime import datetime, timezone
import math
import random
import psycopg2
from graph_utils import get_conn

# Escenario: degrada CS-001 entre t0 y t1, luego recupera
DT = 1.0  # segundos entre “ticks”
TARGET_CELLS = {
    "CS-001": dict(t0=5, t1=90, min_score=0.10, rec_score=0.85),
    # añade más celdas si quieres
}
OTHER_NOISE = 0.0  # ruido para resto (0 = desactivado)

def upsert_score(conn, csid: str, score: float, source: str = "sim"):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO iot.cell_score(ts,id_cell_space,score,source) VALUES (NOW(),%s,%s,%s)",
            (csid, float(score), source)
        )
    conn.commit()

def main():
    print("[SIM] Scores dinámicos → iot.cell_score (Ctrl+C para parar)")
    conn = get_conn()
    t = 0.0
    try:
        while True:
            for csid, p in TARGET_CELLS.items():
                t0, t1 = p["t0"], p["t1"]
                smin, srec = p["min_score"], p["rec_score"]
                if t < t0:
                    s = 0.95
                elif t <= t1:
                    # caída lineal
                    frac = (t - t0) / max(1e-9, (t1 - t0))
                    s = 0.95 + frac * (smin - 0.95)
                else:
                    # recuperación exponencial hacia srec
                    s = smin + (srec - smin) * (1 - math.exp(-(t - t1) / 40.0))
                s = max(0.0, min(1.0, s))
                upsert_score(conn, csid, s, "sim")
            if OTHER_NOISE > 0:
                # ejemplo: inyecta ruido a otra celda
                pass
            time.sleep(DT)
            t += DT
    except KeyboardInterrupt:
        print("\n[SIM] stop")
    finally:
        conn.close()

if __name__ == "__main__":
    main()

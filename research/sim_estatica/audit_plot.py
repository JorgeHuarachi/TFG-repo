# audit_plot.py
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

def main():
    p = Path("out/run_multi.csv")
    if not p.exists() or p.stat().st_size == 0:
        print("[WARN] no hay out/run_multi.csv. Ejecuta primero sim_multi.py.")
        return

    df = pd.read_csv(p)
    if df.empty:
        print("[WARN] CSV vacío.")
        return

    # columnas esperadas: agent_id,travel_s,dist_m,status,replans
    cols = set(df.columns.str.lower())
    if "travel_s" not in cols or "dist_m" not in cols:
        print("[WARN] faltan columnas esperadas. Columnas:", list(df.columns))
        return

    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    df["travel_s"].plot(kind="hist", bins=10, ax=ax[0], title="Tiempo (s)")
    df["dist_m"].plot(kind="hist", bins=10, ax=ax[1], title="Distancia (m)")
    fig.tight_layout()
    fig.savefig("out/summary_hist.png", dpi=150)
    print("[OK] guardado → out/summary_hist.png")

if __name__ == "__main__":
    main()

"""Summarize P1's building/road/settlement impact."""
import os, sys, json
import geopandas as gpd
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import OUTPUT_DIR as OUTPUTS_DIR


def main():
    b = gpd.read_file(os.path.join(OUTPUTS_DIR, "affected_buildings.gpkg"))
    r = gpd.read_file(os.path.join(OUTPUTS_DIR, "affected_roads.geojson"))
    with open(os.path.join(OUTPUTS_DIR, "cutoff_settlements.json")) as f:
        s = json.load(f)

    n_b_total   = len(b)
    n_b_flooded = int(b["flooded"].sum())
    n_r_flooded = len(r)
    n_settle    = len(s)
    n_cutoff    = sum(1 for x in s if x["cut_off"])

    metrics = {
        "Buildings flooded":      f"{n_b_flooded:,} / {n_b_total:,}",
        "Flooded road segments":  f"{n_r_flooded:,}",
        "Cut-off settlements":    f"{n_cutoff:,} / {n_settle:,}",
    }

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axis("off")
    rows = list(metrics.items())
    table = ax.table(
        cellText=[[k, v] for k, v in rows],
        colLabels=["Metric", "Value"],
        cellLoc="left", loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(14)
    table.scale(1, 2)
    plt.title("Impact Summary — Trishuli Flood 2026",
              fontsize=15, pad=20)
    out = os.path.join(OUTPUTS_DIR, "impact_summary.png")
    plt.savefig(out, dpi=120, bbox_inches="tight")
    print(f"✅ {out}")

    with open(os.path.join(OUTPUTS_DIR, "impact_summary.txt"), "w") as f:
        for k, v in rows:
            f.write(f"{k}: {v}\n")
    print(f"✅ outputs/impact_summary.txt")


if __name__ == "__main__":
    main()

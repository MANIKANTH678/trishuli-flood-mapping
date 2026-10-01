"""P4: aggregate P1's impact outputs into stats + maps."""
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT  = ROOT / "outputs"

b = gpd.read_file(OUT / "affected_buildings.gpkg")
r = gpd.read_file(OUT / "affected_roads.geojson")
s = json.load(open(OUT / "cutoff_settlements.json"))
summary = json.load(open(OUT / "impact_summary.json"))

stats = {
    **summary,
    "total_settlements": len(s),
    "cutoff_settlements": sum(x["cut_off"] for x in s),
    "pct_buildings_flooded": round(100 * summary["flooded_buildings"] / summary["total_buildings"], 3),
    "pct_roads_flooded":     round(100 * summary["flooded_roads"] / summary["total_roads"], 3),
}
json.dump(stats, open(OUT / "impact_stats.json", "w"), indent=2)
print("impact_stats:", stats)

# Per-district buildings
if "addr:city" in b.columns:
    by = b.groupby("addr:city").size().sort_values(ascending=False).head(20)
    by.to_csv(OUT / "impact_by_district.csv")
    print("top districts:", by.head(5).to_dict())

# Map helper
def save_map(gdf, title, fname, color="#c0392b"):
    fig, ax = plt.subplots(figsize=(10, 8), dpi=110)
    gdf.plot(ax=ax, color=color, markersize=1, linewidth=0.3)
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT / fname, bbox_inches="tight")
    plt.close(fig)
    print("saved", fname)

save_map(b, f"Flooded buildings ({len(b):,})", "affected_buildings_map.png")
save_map(r, f"Flooded roads ({len(r):,})", "affected_roads_map.png", color="#2980b9")

"""P4: aggregate P1's impact outputs into stats + maps."""
import json
from pathlib import Path
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

# --- Load GeoDataFrames safely ---
b_path = OUT / "affected_buildings.gpkg"
r_path = OUT / "affected_roads.geojson"
b = gpd.read_file(b_path) if b_path.exists() else gpd.GeoDataFrame()
r = gpd.read_file(r_path) if r_path.exists() else gpd.GeoDataFrame()

# --- Load JSON outputs safely ---
s = []
s_path = OUT / "cutoff_settlements.json"
if s_path.exists():
    with open(s_path, "r", encoding="utf-8") as f:
        s = json.load(f)
    if isinstance(s, dict):  # new format: {"summary": ..., "settlements": [...]}
        s = s.get("settlements", [])

summary = {}
summary_path = OUT / "impact_summary.json"
if summary_path.exists():
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

# --- Compute fallbacks from actual data (no more branch conflict) ---
fallback = {
    "total_buildings":   len(b),
    "flooded_buildings": int(b["flooded"].sum()) if "flooded" in b.columns else 0,
    "total_roads":       len(r),
    # affected_roads.geojson is already the flooded subset, so default = total
    "flooded_roads":     int(r["flooded"].sum()) if "flooded" in r.columns else len(r),
}

# Prefer whatever the summary already has; fill the gaps from the fallback.
for k, v in fallback.items():
    summary.setdefault(k, v)

# Guard against None / missing values before division
total_b   = summary.get("total_buildings", 0) or 0
flooded_b = summary.get("flooded_buildings", 0) or 0
total_r   = summary.get("total_roads", 0) or 0
flooded_r = summary.get("flooded_roads", 0) or 0

stats = {
    **summary,
    "total_settlements":  len(s),
    "cutoff_settlements": sum(1 for x in s if (x.get("hospital") or {}).get("status") == "cut_off" or x.get("cut_off", False)),
    "pct_buildings_flooded": round(100 * flooded_b / total_b, 3) if total_b > 0 else 0.0,
    "pct_roads_flooded":     round(100 * flooded_r / total_r, 3) if total_r > 0 else 0.0,
}

with open(OUT / "impact_stats.json", "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)
print("impact_stats:", stats)

# --- Per-district buildings ---
if not b.empty and "addr:city" in b.columns:
    by = b.groupby("addr:city").size().sort_values(ascending=False).head(20)
    by.to_csv(OUT / "impact_by_district.csv")
    print("top districts:", by.head(5).to_dict())

# --- Map helper ---
def save_map(gdf, title, fname, color="#c0392b"):
    fig, ax = plt.subplots(figsize=(10, 8), dpi=110)
    if not gdf.empty:
        gdf.plot(ax=ax, color=color, markersize=1, linewidth=0.3)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(OUT / fname, bbox_inches="tight")
    plt.close(fig)
    print("saved", fname)

save_map(b, f"Buildings in mask ({len(b):,})", "affected_buildings_map.png")
save_map(r, f"Road segments in mask ({len(r):,})", "affected_roads_map.png", color="#2980b9")
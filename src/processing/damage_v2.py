"""damage_v2.py - buildings, roads, bridges, and debris-affected buildings."""
import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
FLOOD  = ROOT / "data/processed/flood_mask.tif"
DEBRIS = ROOT / "data/processed/debris_mask.tif"
BLD    = ROOT / "data/raw/osm/buildings.geojson"
RDS    = ROOT / "data/raw/osm/roads.geojson"
OUT    = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def sampler(path):
    with rasterio.open(path) as src:
        arr = src.read(1)
        crs = src.crs
        tr = src.transform
    h, w = arr.shape

    def fn(xs, ys):
        cols, rows = ~tr * (xs, ys)
        cols = np.floor(cols).astype(int)
        rows = np.floor(rows).astype(int)
        valid = (cols >= 0) & (cols < w) & (rows >= 0) & (rows < h)
        out = np.zeros(len(xs), dtype=bool)
        out[valid] = arr[rows[valid], cols[valid]] == 1
        return out
    return fn, crs


print("Opening flood + debris masks ...")
flood_hit, mask_crs = sampler(FLOOD)
debris_hit, _ = sampler(DEBRIS)

# --- Buildings ---
print("Loading buildings ...")
b = gpd.read_file(BLD).to_crs(mask_crs)
cent = b.geometry.centroid
b["flooded"] = flood_hit(cent.x.values, cent.y.values)
b["debris"]  = debris_hit(cent.x.values, cent.y.values)

n_flood  = int(b["flooded"].sum())
n_debris = int((b["debris"] & ~b["flooded"]).sum())
print(f"Flooded buildings: {n_flood}")
print(f"Debris-affected buildings (not flooded): {n_debris}")

b_out = b[b["flooded"] | b["debris"]].copy()
b_out.to_file(OUT / "affected_buildings.gpkg", driver="GPKG")
print(f"✅ affected_buildings.gpkg ({len(b_out)} features)")

# --- Roads ---
print("Loading roads ...")
r = gpd.read_file(RDS).to_crs(mask_crs)
mid = r.geometry.interpolate(0.5, normalized=True)
r["flooded"] = flood_hit(mid.x.values, mid.y.values)

# --- Bridges ---
is_bridge = r["bridge"].astype(str).str.lower().isin(["yes", "viaduct", "boardwalk"])
bridges = r[is_bridge].copy()
bridges["flooded"] = flood_hit(mid[is_bridge].x.values, mid[is_bridge].y.values)
n_bridges = int(bridges["flooded"].sum())
print(f"Bridges total: {len(bridges)} | flooded: {n_bridges}")

bridges[bridges["flooded"]].to_file(OUT / "affected_bridges.geojson", driver="GeoJSON")
print(f"✅ affected_bridges.geojson ({n_bridges} features)")

# --- Roads (non-bridge only, avoids double-count) ---
r_nb = r[~is_bridge]
n_roads = int(r_nb["flooded"].sum())
r_nb[r_nb["flooded"]].to_file(OUT / "affected_roads.geojson", driver="GeoJSON")
print(f"✅ affected_roads.geojson ({n_roads} features, bridges excluded)")

# --- Summary ---
summary = {
    "total_buildings": int(len(b)),
    "flooded_buildings": n_flood,
    "debris_buildings": n_debris,
    "total_roads": int(len(r_nb)),
    "flooded_roads": n_roads,
    "total_bridges": int(len(bridges)),
    "flooded_bridges": n_bridges,
}
with open(OUT / "impact_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSummary written to impact_summary.json:")
print(json.dumps(summary, indent=2))

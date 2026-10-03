"""P1: intersect OSM buildings & roads with the flood mask."""
import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
FLOOD = ROOT / "data/processed/flood_mask.tif"
BLD   = ROOT / "data/raw/osm/buildings.geojson"
RDS   = ROOT / "data/raw/osm/roads.geojson"
OUT   = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

print("Opening flood mask ...")
with rasterio.open(FLOOD) as src:
    arr = src.read(1)
    mask_crs = src.crs
    transform = src.transform
h, w = arr.shape

def is_flooded(xs, ys):
    cols, rows = ~transform * (xs, ys)
    cols = np.floor(cols).astype(int)
    rows = np.floor(rows).astype(int)
    valid = (cols >= 0) & (cols < w) & (rows >= 0) & (rows < h)
    out = np.zeros(len(xs), dtype=bool)
    out[valid] = arr[rows[valid], cols[valid]] == 1
    return out

# --- Buildings ---
print("Loading buildings ...")
b = gpd.read_file(BLD)
print(f"  {len(b)} features | CRS={b.crs}")
b = b.to_crs(mask_crs)
cent = b.geometry.centroid
b["flooded"] = is_flooded(cent.x.values, cent.y.values)
n_b = int(b["flooded"].sum())
print(f"Flooded buildings: {n_b} / {len(b)}")

b_affected = b[b["flooded"]].copy()
out_b = OUT / "affected_buildings.gpkg"
b_affected.to_file(out_b, driver="GPKG")
print(f"✅ {out_b} ({len(b_affected)} features)")

# --- Roads ---
print("\nLoading roads ...")
r = gpd.read_file(RDS)
print(f"  {len(r)} features | CRS={r.crs}")
r = r.to_crs(mask_crs)
mid = r.geometry.interpolate(0.5, normalized=True)
r["flooded"] = is_flooded(mid.x.values, mid.y.values)
n_r = int(r["flooded"].sum())
print(f"Flooded road segments: {n_r} / {len(r)}")

r_affected = r[r["flooded"]].copy()
out_r = OUT / "affected_roads.geojson"
r_affected.to_file(out_r, driver="GeoJSON")
print(f"✅ {out_r} ({len(r_affected)} features)")

# --- Summary ---
summary = {
    "total_buildings": int(len(b)),
    "flooded_buildings": n_b,
    "total_roads": int(len(r)),
    "flooded_roads": n_r,
}
with open(OUT / "impact_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print(f"\nSummary: {summary}")

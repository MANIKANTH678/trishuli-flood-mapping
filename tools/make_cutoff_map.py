#!/usr/bin/env python3
"""Full-bleed cut-off map for the deck (Step 6 outputs). Run from the repo root:
    python tools/make_cutoff_map.py
Writes outputs/figures/cutoff_map.png (3200x1800, no margins).
Layers, bottom to top: faded DEM hillshade, motorable roads (light grey), flooded/affected
road segments (red, thickest), settlements by hospital-access status, hospitals (black cross),
labels for cut-off settlements plus Bidur and Syapru Besi.
"""
import argparse, json
from pathlib import Path
import numpy as np, rasterio, geopandas as gpd
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe

ap = argparse.ArgumentParser()
ap.add_argument("--cutoff", default="outputs/cutoff_settlements.json")
ap.add_argument("--osm", default="data/raw/osm")
ap.add_argument("--flooded", default="outputs/affected_roads.geojson")
ap.add_argument("--dem", default="data/processed/dem_30m.tif")
ap.add_argument("--out", default="outputs/figures/cutoff_map.png")
ap.add_argument("--w", type=int, default=3200); ap.add_argument("--h", type=int, default=1800)
ap.add_argument("--crs", default="EPSG:32645")
ap.add_argument("--legend", action="store_true", help="draw a small legend in the corner")
a = ap.parse_args()

STY = {  # status: (face, edge, size, zorder)
    "no_pre_flood_path": ("none", "#9CA3AF", 70, 4),
    "reachable":         ("#2563EB", "white", 55, 5),
    "degraded":          ("#F59E0B", "white", 110, 6),
    "cut_off":           ("#7F1D1D", "white", 520, 8),
}
ORIENT = {"Bidur": ((85.1465, 27.8953), (-14, -6)), "Syapru Besi": ((85.3368, 28.1602), (14, -8))}

d = json.load(open(a.cutoff))
S = gpd.GeoDataFrame(d["settlements"], geometry=gpd.points_from_xy(
    [s["lon"] for s in d["settlements"]], [s["lat"] for s in d["settlements"]]), crs="EPSG:4326")
S["status"] = [s["hospital"]["status"] for s in d["settlements"]]
S = S.to_crs(a.crs)

# English names for labels, from the pre-event OSM settlements (nearest point, 300 m)
osm_s = gpd.read_file(Path(a.osm) / "settlements.geojson").to_crs(a.crs)
osm_s["geometry"] = osm_s.geometry.centroid
en = osm_s.get("name:en", osm_s.get("name")).fillna(osm_s.get("name"))
osm_s = osm_s.assign(label=en)[["label", "geometry"]]
S = gpd.sjoin_nearest(S, osm_s, how="left", max_distance=300).drop_duplicates(subset=["lat", "lon"])

roads = gpd.read_file(Path(a.osm) / "roads.geojson")
if "motorable" in roads: roads = roads[roads["motorable"].astype(bool)]
else: roads = roads[~roads["highway"].isin(["path", "footway", "steps", "track", "cycleway", "bridleway", "pedestrian"])]
roads = roads.to_crs(a.crs)
flooded = gpd.read_file(a.flooded).to_crs(a.crs)
hos = gpd.read_file(Path(a.osm) / "hospitals.geojson").to_crs(a.crs)
hos["geometry"] = hos.geometry.centroid

# extent: all settlements, padded, stretched to the output aspect
x0, y0, x1, y1 = S.total_bounds; pad = 0.04 * max(x1 - x0, y1 - y0)
x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
asp = a.w / a.h; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
wd, ht = x1 - x0, y1 - y0
if wd / ht < asp: wd = ht * asp
else: ht = wd / asp
x0, x1, y0, y1 = cx - wd / 2, cx + wd / 2, cy - ht / 2, cy + ht / 2

dpi = 200
fig = plt.figure(figsize=(a.w / dpi, a.h / dpi), dpi=dpi)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); fig.patch.set_facecolor("white")

# hillshade, faded
with rasterio.open(a.dem) as s:
    if str(s.crs) != a.crs:
        from rasterio.vrt import WarpedVRT
        src = WarpedVRT(s, crs=a.crs)
    else: src = s
    win = from_bounds(x0, y0, x1, y1, src.transform)
    z = src.read(1, window=win, boundless=True, masked=True, out_shape=(a.h // 2, a.w // 2)).astype("float32").filled(np.nan)
bad = ~np.isfinite(z); z = np.where(bad, np.nanmedian(z), z)
cs = wd / z.shape[1]
gy, gx = np.gradient(z, cs)
slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
az, alt = np.radians(315), np.radians(45)
hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
hs = np.ma.masked_array(np.clip(hs, 0, 1), mask=bad)
cm = plt.get_cmap("gray").copy(); cm.set_bad("white")
ax.imshow(hs, cmap=cm, vmin=-0.4, vmax=1.15, alpha=0.55,
          extent=(x0, x1, y0, y1), interpolation="bilinear", zorder=0)

roads.plot(ax=ax, color="#A9B1BA", linewidth=1.1, zorder=1)
flooded.plot(ax=ax, color="#DC2626", linewidth=3.6, zorder=3, capstyle="round")

for st, (fc, ec, sz, zo) in STY.items():
    g = S[S.status == st]
    if g.empty: continue
    lw = 1.6 if st == "no_pre_flood_path" else (2.2 if st == "cut_off" else 0.6)
    ax.scatter(g.geometry.x, g.geometry.y, s=sz, facecolors=fc, edgecolors=ec, linewidths=lw, zorder=zo)

ax.scatter(hos.geometry.x, hos.geometry.y, marker="P", s=420, c="black", edgecolors="white", linewidths=1.2, zorder=9)

halo = [pe.withStroke(linewidth=5, foreground="white")]
for _, r in S[S.status == "cut_off"].iterrows():
    nm = r.get("label") if isinstance(r.get("label"), str) else r["name"]
    ax.annotate(nm, (r.geometry.x, r.geometry.y), xytext=(14, 10), textcoords="offset points",
                fontsize=17, fontweight="bold", color="#7F1D1D", path_effects=halo, zorder=10)
ow = gpd.GeoSeries(gpd.points_from_xy([v[0][0] for v in ORIENT.values()], [v[0][1] for v in ORIENT.values()]),
                   crs="EPSG:4326").to_crs(a.crs)
for (nm, (_, off)), p in zip(ORIENT.items(), ow):
    ax.scatter([p.x], [p.y], s=60, c="#111827", marker="s", zorder=10)
    ax.annotate(nm, (p.x, p.y), xytext=off, textcoords="offset points", fontsize=17, ha="right" if off[0] < 0 else "left",
                color="#111827", path_effects=halo, zorder=10)

if a.legend:
    h = [Line2D([], [], color="#DC2626", lw=3.6, label="Flooded road segment"),
         Line2D([], [], marker="o", ls="", ms=14, mfc="#7F1D1D", mec="white", label="Cut off"),
         Line2D([], [], marker="o", ls="", ms=8, mfc="#F59E0B", mec="white", label="Degraded"),
         Line2D([], [], marker="o", ls="", ms=7, mfc="#2563EB", mec="white", label="Reachable"),
         Line2D([], [], marker="o", ls="", ms=7, mfc="none", mec="#9CA3AF", mew=1.6, label="No pre-event path"),
         Line2D([], [], marker="P", ls="", ms=13, mfc="black", mec="white", label="Hospital")]
    ax.legend(handles=h, loc="lower right", frameon=True, fontsize=13, framealpha=0.9)

ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
fig.savefig(a.out, dpi=dpi, pad_inches=0); plt.close(fig)
print({k: int((S.status == k).sum()) for k in STY}, "->", a.out)

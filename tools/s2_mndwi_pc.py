#!/usr/bin/env python3
"""Sentinel-2 L2A MNDWI + clear-sky fraction on THIS repo's 30 m grid, from Microsoft Planetary Computer (no login),
for the dates tools/ai_vs_s2.py needs when data/interim/s2/<date>/mndwi_30m.tif is missing.
python tools/s2_mndwi_pc.py --dates 20260812 20260827
clear = SCL in {4 vegetation, 5 bare, 6 water, 11 snow}; mndwi = (B03 - B11) / (B03 + B11), both resampled to 30 m."""
import argparse, json
from pathlib import Path
import numpy as np, rasterio, pystac_client, planetary_computer
from rasterio.warp import reproject, Resampling, transform_bounds

ap = argparse.ArgumentParser(); ap.add_argument("--dates", nargs="+", default=["20260812", "20260827"])
ap.add_argument("--grid", default="data/processed/dem_30m.tif"); ap.add_argument("--out", default="data/interim/s2"); a = ap.parse_args()
with rasterio.open(a.grid) as g: prof, T, crs, shp = g.profile, g.transform, g.crs, g.shape
bbox = transform_bounds(crs, "EPSG:4326", *rasterio.transform.array_bounds(*shp, T))
cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
prof.update(dtype="float32", nodata=np.nan, count=1, compress="deflate")
def warp(href, rs):
    dst = np.full(shp, np.nan, "float32")
    with rasterio.open(href) as s: reproject(rasterio.band(s, 1), dst, dst_transform=T, dst_crs=crs, dst_nodata=np.nan, src_nodata=0, resampling=rs)
    return dst
for day in a.dates:
    iso = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{iso}/{iso}").items())
    g3 = np.full(shp, np.nan, "float32"); s11 = g3.copy(); clear = np.zeros(shp, "float32")
    for it in items:
        scl = warp(it.assets["SCL"].href, Resampling.nearest); b3 = warp(it.assets["B03"].href, Resampling.average); b11 = warp(it.assets["B11"].href, Resampling.average)
        ok = np.isin(scl, (4, 5, 6, 11)) & np.isfinite(b3) & np.isfinite(b11) & (clear == 0)
        g3[ok], s11[ok], clear[ok] = b3[ok], b11[ok], 1.0
    with np.errstate(divide="ignore", invalid="ignore"): mndwi = (g3 - s11) / (g3 + s11)
    d = Path(a.out) / day; d.mkdir(parents=True, exist_ok=True)
    for n, arr in (("mndwi_30m.tif", mndwi), ("clear_30m.tif", clear)):
        with rasterio.open(d / n, "w", **prof) as o: o.write(arr.astype("float32"), 1)
    (d / "mndwi_source.json").write_text(json.dumps({"source": "Microsoft Planetary Computer sentinel-2-l2a", "items": [i.id for i in items]}, indent=1))
    print(day, len(items), "tiles, clear fraction of grid", round(float(clear.mean()), 3))

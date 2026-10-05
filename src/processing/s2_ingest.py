#!/usr/bin/env python3
import argparse, json
from collections import defaultdict
from pathlib import Path
import numpy as np, rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from scipy import ndimage as ndi
from src.processing.grid import make_grids
from src.processing.s1_to_grid import write

ap = argparse.ArgumentParser()
ap.add_argument("--bbox", required=True); ap.add_argument("--epsg", required=True)
ap.add_argument("--manifest", default="data/raw/s2/scenes.json"); ap.add_argument("--out", default="data/interim/s2")
ap.add_argument("--dates", help="comma list YYYY-MM-DD (default: all in manifest)")
a = ap.parse_args()
g = make_grids(tuple(map(float, a.bbox.split(","))), a.epsg); T10, W10, H10 = g[10]; T30 = g[30][0]

def read(href, resamp):
    with rasterio.open(href) as src, WarpedVRT(src, crs=f"EPSG:{a.epsg}", transform=T10, width=W10, height=H10,
                                               resampling=resamp, src_nodata=0, nodata=0) as v:
        return v.read(1)

def nd(x, y):
    with np.errstate(divide="ignore", invalid="ignore"): o = (x - y) / (x + y)
    o[~np.isfinite(o) | (np.abs(o) > 1.5)] = np.nan; return o.astype("float32")

def block(x, f=3, min_valid=5):
    h, w = x.shape; ok = np.isfinite(x)
    s = np.where(ok, x, 0).reshape(h // f, f, w // f, f).sum((1, 3)); c = ok.reshape(h // f, f, w // f, f).sum((1, 3))
    o = (s / np.maximum(c, 1)).astype("float32"); o[c < min_valid] = np.nan; return o, c / (f * f)

items = json.load(open(a.manifest)); by = defaultdict(list)
for s in items: by[s["date"]].append(s)
want = set(a.dates.split(",")) if a.dates else set(by)
with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="3"):
    for d in sorted(want & set(by)):
        out = Path(a.out) / d.replace("-", "")
        if (out / "clear_30m.tif").exists(): print(d, "done"); continue
        raw = {b: np.zeros((H10, W10), np.uint16) for b in ("B02", "B03", "B04", "B08", "B11")}
        scl = np.zeros((H10, W10), np.uint8)
        for s in by[d]:                                   # merge adjacent tiles of the same date
            for b, arr in raw.items():
                x = read(s["assets"][b], Resampling.bilinear); m = (arr == 0) & (x != 0); arr[m] = x[m]
            x = read(s["assets"]["SCL"], Resampling.nearest); m = (scl == 0) & (x != 0); scl[m] = x[m]
        sc, off = by[d][0]["scale"], by[d][0]["offset"]
        refl = {b: np.where(arr > 0, arr * sc + off, np.nan).astype("float32") for b, arr in raw.items()}; del raw
        ndvi = nd(refl["B08"], refl["B04"]); mndwi = nd(refl["B03"], refl["B11"])
        bsi = nd(refl["B11"] + refl["B04"], refl["B08"] + refl["B02"])
        bad = np.isin(scl, [0, 1, 2, 3, 8, 9, 10, 11]) | ndi.binary_dilation(np.isin(scl, [3, 8, 9, 10]), iterations=3)
        near_cloud = ndi.binary_dilation(np.isin(scl, [8, 9, 10]), iterations=3)
        bad &= ~(np.isin(scl, [2, 3]) & (mndwi > 0.1) & ~near_cloud)   # Sen2Cor often flags turbid flood water as shadow
        bad |= ~np.isfinite(ndvi) | ~np.isfinite(bsi) | ~np.isfinite(mndwi)
        out.mkdir(parents=True, exist_ok=True)
        for name, idx in (("ndvi", ndvi), ("mndwi", mndwi), ("bsi", bsi)):
            idx[bad] = np.nan; o, frac = block(idx); write(out / f"{name}_30m.tif", o, T30, a.epsg)
        write(out / "clear_30m.tif", frac, T30, a.epsg)
        (out / "meta.json").write_text(json.dumps([{k: s[k] for k in ("id", "tile", "cloud")} for s in by[d]]))
        print(d, f"tiles={len(by[d])} clear@10m={1 - bad.mean():.0%}")
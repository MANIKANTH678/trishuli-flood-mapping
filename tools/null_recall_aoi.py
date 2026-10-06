"""EMSR927 check: hit rate of the fused flagged mask (classes 1-3) on damage points vs a random-mask null.

Null: 200 random masks of the same pixel count as the flagged mask in the AOI, placed on ASSESSED floor pixels
(classes 0-3 of the fused raster) inside that AOI. AOI03 is the hold-out (not used to tune the detector).
Check only: EMS data is never an input to the mask.
"""
import json, os, glob, sys
from pathlib import Path
import numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.analysis.impact_lib import ASSESSED

P = "data/processed/"
HOLDOUT = {"AOI03"}
with rasterio.open(P + "fused_class_30m.tif") as s:
    cls = s.read(1); T, crs = s.transform, s.crs
m = np.isin(cls, (1, 2, 3))                       # flagged: flood-like + dark + bright
floor = np.isin(cls, ASSESSED)                    # pixels the detector actually looked at
rng = np.random.default_rng(0)
res = {}
for a in ("AOI01", "AOI02", "AOI03", "AOI05"):
    aoi = gpd.read_file(glob.glob(f"data/external/EMSR927/{a}/*areaOfInterestA*.shp")[0]).to_crs(crs)
    am = rasterize(aoi.geometry, out_shape=m.shape, transform=T).astype(bool)
    pts = gpd.read_file(glob.glob(f"data/external/EMSR927/{a}/*builtUpP*.shp")[0]).to_crs(crs)
    pts = pts.geometry.representative_point()
    r, c = rasterio.transform.rowcol(T, pts.x.values, pts.y.values)
    r, c = np.array(r), np.array(c)
    ok = (r >= 0) & (r < m.shape[0]) & (c >= 0) & (c < m.shape[1]); r, c = r[ok], c[ok]
    k = int((m & am).sum()); cr, cc = np.nonzero(floor & am)
    obs = float(m[r, c].mean()) if len(r) else None
    sims = []
    if cr.size and len(r):
        for _ in range(200):
            i = rng.choice(cr.size, min(k, cr.size), replace=False)
            rm = np.zeros_like(m); rm[cr[i], cc[i]] = True; sims.append(rm[r, c].mean())
    res[a] = dict(points=int(len(r)), assessed_points=int(floor[r, c].sum()), mask_px=k, assessed_px=int(cr.size),
                  observed=obs, null_mean=float(np.mean(sims)) if sims else None,
                  null_sd=float(np.std(sims)) if sims else None, holdout=a in HOLDOUT)
    print(a, res[a])
os.makedirs("outputs/validation", exist_ok=True)
json.dump(res, open("outputs/validation/null_recall_aoi.json", "w"), indent=2)
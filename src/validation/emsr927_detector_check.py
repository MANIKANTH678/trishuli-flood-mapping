"""emsr927_detector_check.py - proxy check of the frozen detector (tag detector-frozen) against EMSR927.

Run only after the detector-frozen tag. EMS polygons are landslides, not flood extent, so
precision/recall/IoU are PROXIES. Report them with that caveat and report the hold-out AOI separately.
"""
import argparse, json
from pathlib import Path
import numpy as np, geopandas as gpd, pyogrio, rasterio
from rasterio.features import rasterize
from scipy import ndimage as ndi
from shapely.ops import unary_union

ap = argparse.ArgumentParser()
ap.add_argument("--cls", default="data/processed/detect_class_30m.tif")
ap.add_argument("--emsr-dir", default="data/external/EMSR927"); ap.add_argument("--holdout", default="AOI03")
ap.add_argument("--out", default="outputs/validation/detector_vs_emsr927.json")
a = ap.parse_args()
with rasterio.open(a.cls) as s: cls, T, crs, res = s.read(1), s.transform, s.crs, s.res[0]
det = np.isin(cls, (1, 2, 3)); assessed = np.isin(cls, (0, 1, 2, 3))
dist = ndi.distance_transform_edt(~det) * res
def lyr(names, p): return next((n for n in names if n.startswith(p)), None)
def ras(geoms):
    g = [x for x in geoms if x is not None and not x.is_empty]
    return rasterize([(x, 1) for x in g], out_shape=cls.shape, transform=T).astype(bool) if g else np.zeros(cls.shape, bool)
out = {}
for aoi in sorted(Path(a.emsr_dir).glob("AOI*")):
    gp = sorted(aoi.glob("*.gpkg"))
    if not gp: continue
    f = gp[0]; names = pyogrio.list_layers(f)[:, 0].tolist()
    rd_ = lambda p: gpd.read_file(f, layer=lyr(names, p), engine="pyogrio").to_crs(crs)
    g = unary_union(rd_("areaOfInterestA").geometry.tolist())
    if lyr(names, "notAnalysedA"): g = g.difference(unary_union(rd_("notAnalysedA").geometry.tolist()))
    vm = ras([g]); pts = rd_("builtUpP"); pts = pts[pts.geometry.within(g)]
    r, c = (np.array(v) for v in rasterio.transform.rowcol(T, pts.geometry.x.values, pts.geometry.y.values))
    inb = (r >= 0) & (r < cls.shape[0]) & (c >= 0) & (c < cls.shape[1]); r, c = r[inb], c[inb]
    ls = ras(rd_("observedEventA").geometry.intersection(g).tolist())
    tp = int((det & ls & vm & assessed).sum()); fp = int((det & ~ls & vm).sum()); fn = int((ls & ~det & vm & assessed).sum())
    out[aoi.name] = {"holdout": aoi.name.startswith(a.holdout), "damage_points": int(len(r)),
        "points_in_assessed_domain": float(assessed[r, c].mean()) if len(r) else None,
        "damage_point_recall_within_m": {str(t): float((dist[r, c] <= t).mean()) for t in (0, 30, 60, 100)} if len(r) else None,
        "landslide_in_assessed_fraction": float((ls & vm & assessed).sum() / max((ls & vm).sum(), 1)),
        "landslide_precision": tp / max(tp + fp, 1), "landslide_recall": tp / max(tp + fn, 1), "landslide_iou": tp / max(tp + fp + fn, 1)}
Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(out, indent=2)); print(json.dumps(out, indent=2))
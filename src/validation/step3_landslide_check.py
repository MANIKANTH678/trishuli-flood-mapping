#!/usr/bin/env python3
"""Do step-3 main-floor exceedances sit on EMSR927 mapped landslides? Validation only."""
import argparse, json
from pathlib import Path
import numpy as np, geopandas as gpd, pyogrio
from affine import Affine
from rasterio.features import rasterize
from shapely.ops import unary_union

ap = argparse.ArgumentParser()
ap.add_argument("--masks", default="data/processed/step3_masks_event_masks.npz")
ap.add_argument("--emsr-dir", default="data/external/EMSR927")
ap.add_argument("--holdout", default="Bidur")
ap.add_argument("--final", action="store_true", help="include the held-out AOI; run once, last")
ap.add_argument("--out", default="outputs/validation/step3_landslide_check.json")
a = ap.parse_args()

m = np.load(a.masks, allow_pickle=False)
T = Affine(*[float(v) for v in m["transform"]]); crs = str(m["crs"]); shape = m["valid"].shape
mf = m["main_floor"]
EX = {"neg_VV": m["neg_VV"], "neg_VH": m["neg_VH"]}

def layer(layers, prefix): return next((l for l in layers if l.startswith(prefix)), None)
def raster(g):
    if g is None or g.is_empty: return np.zeros(shape, bool)
    return rasterize([(g, 1)], out_shape=shape, transform=T, fill=0, dtype="uint8").astype(bool)
def stat(sel):
    n = int(sel.sum())
    return {"n_px": n, **{k: {"n_exceed": int(v[sel].sum()), "frac": (float(v[sel].mean()) if n else None)}
                           for k, v in EX.items()}}

per, all_valid, all_land = {}, np.zeros(shape, bool), np.zeros(shape, bool)
for d in sorted(Path(a.emsr_dir).glob("AOI*")):
    gp = sorted(d.glob("*.gpkg"))
    if not gp: continue
    L = pyogrio.list_layers(gp[0])[:, 0].tolist()
    aoi = gpd.read_file(gp[0], layer=layer(L, "areaOfInterestA"), engine="pyogrio")
    name = str(aoi["locality"].iloc[0])
    if a.holdout.lower() in name.lower() and not a.final:
        print(f"{d.name} {name}: held out (add --final for the last run)"); continue
    vg = unary_union(aoi.to_crs(crs).geometry.tolist())
    nl = layer(L, "notAnalysedA")
    if nl:
        na = gpd.read_file(gp[0], layer=nl, engine="pyogrio").to_crs(crs)
        if len(na): vg = vg.difference(unary_union(na.geometry.tolist()))
    obs = gpd.read_file(gp[0], layer=layer(L, "observedEventA"), engine="pyogrio").to_crs(crs)
    for c in ("event_type", "obj_desc"):
        if c in obs: print(d.name, name, c, obs[c].value_counts().to_dict())
    obs = obs[obs.geometry.notna() & obs.geometry.intersects(vg)]
    lg = unary_union(obs.geometry.intersection(vg).tolist()) if len(obs) else None
    v, ls = raster(vg), raster(lg)
    all_valid |= v; all_land |= ls
    per[f"{d.name} {name}"] = {"main_floor_on_landslide": stat(mf & v & ls),
                               "main_floor_off_landslide": stat(mf & v & ~ls)}

res = {"holdout_included": bool(a.final), "per_aoi": per,
       "pooled_on_landslide": stat(mf & all_valid & all_land),
       "pooled_off_landslide": stat(mf & all_valid & ~all_land),
       "main_floor_outside_these_aois": stat(mf & ~all_valid)}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))
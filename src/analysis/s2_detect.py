#!/usr/bin/env python3
import argparse, json, warnings
from datetime import date, datetime, timedelta
from pathlib import Path
import numpy as np, rasterio
from src.analysis.changelib import rd, domain, control, robust_z, patch_filter, hysteresis
from src.processing.s1_to_grid import write

ap = argparse.ArgumentParser()
ap.add_argument("--event", required=True)
ap.add_argument("--s2-dir", default="data/interim/s2"); ap.add_argument("--proc-dir", default="data/processed")
ap.add_argument("--out-dir", default="data/processed")
ap.add_argument("--floor-m", type=float, default=30); ap.add_argument("--ctrl-m", type=float, default=100)
ap.add_argument("--t-hi", type=float); ap.add_argument("--t-lo", type=float, default=2.5)
ap.add_argument("--min-patch", type=int, default=8); ap.add_argument("--alpha", type=float, default=1e-3)
ap.add_argument("--post-window", type=int, default=30); ap.add_argument("--min-ref", type=int, default=2)
ap.add_argument("--mndwi-post", type=float, default=0.1); ap.add_argument("--mndwi-ref", type=float, default=-0.05)
a = ap.parse_args(); ev = date.fromisoformat(a.event); S2, MINPX = Path(a.s2_dir), a.min_patch

hand, mask, dem = domain(a.proc_dir, 30)
_, prof = rd(Path(a.proc_dir) / "hand_30m.tif"); T, EPSG = prof["transform"], prof["crs"].to_epsg()
floor = np.isfinite(hand) & np.isfinite(dem) & (hand <= a.floor_m)
K = ("ndvi", "mndwi", "bsi"); dates = {}
for p in sorted(S2.glob("*")):
    if p.is_dir() and (p / "clear_30m.tif").exists():
        x = {k: rd(p / f"{k}_30m.tif")[0] for k in K}
        dates[datetime.strptime(p.name, "%Y%m%d").date()] = (x, float(np.isfinite(x["ndvi"])[floor].mean()))
for d, (_, fc) in dates.items(): print(d, "PRE " if d < ev else "POST", f"floor clear {fc:.0%}")

def put_u8(name, arr):
    pr = dict(prof, dtype="uint8", nodata=255, count=1, compress="deflate")
    with rasterio.open(Path(a.out_dir) / name, "w", **pr) as dst: dst.write(arr.astype("uint8"), 1)
def finish(status, extra, cls):
    put_u8("s2_class_30m.tif", cls); Path("outputs/diagnostics").mkdir(parents=True, exist_ok=True)
    Path("outputs/diagnostics/s2_detect.json").write_text(json.dumps({"status": status, **extra}, indent=2)); print(status, extra)

pre = [d for d in dates if d < ev and dates[d][1] > 0.02]
post = [d for d in dates if ev < d <= ev + timedelta(days=a.post_window) and dates[d][1] > 0.0]
blank = np.full(dem.shape, 255, np.uint8); blank[np.isfinite(dem)] = 254
if not pre or not post:
    finish("no_clear_post_observation" if not post else "no_pre_reference", {"pre": len(pre), "post": len(post)}, blank); raise SystemExit
min_ref = a.min_ref if len(pre) >= 2 else 1

def nanmed(s):
    with warnings.catch_warnings(): warnings.simplefilter("ignore"); return np.nanmedian(s, axis=0), np.isfinite(s).sum(0)
def deltas(px, ref_ds, mr):
    ref, nref = {}, None
    for k in K:
        ref[k], n = nanmed(np.stack([dates[d][0][k] for d in ref_ds])); nref = n if nref is None else np.minimum(nref, n)
    d = {k: px[k] - ref[k] for k in K}
    valid = np.isfinite(hand) & np.isfinite(dem) & (nref >= mr) & np.all([np.isfinite(d[k]) for k in K], axis=0)
    return ref, d, valid
def zs(d, valid):
    ctrl = control(valid, hand, a.ctrl_m); return {k: robust_z(d[k], dem, ctrl) for k in K}
def seeds(z, t): return ((z["ndvi"] < -t) & (z["bsi"] > t)) | (z["mndwi"] > t)

GRID, cal = [3.0, 3.5, 4.0, 4.5, 5.0, 6.0], None
if len(pre) >= 3:                                              # leave-one-out nulls on the pre-event dates
    far = {t: [] for t in GRID}
    for j in pre:
        _, d, valid = deltas(dates[j][0], [x for x in pre if x != j], min(a.min_ref, len(pre) - 1))
        if valid.sum() < 20000: continue
        z = zs(d, valid)
        for t in GRID: far[t].append(float(patch_filter(seeds(z, t) & valid, MINPX)[valid].mean()))
    if far[GRID[0]]:
        worst = {t: max(v) for t, v in far.items()}; ok = [t for t in GRID if worst[t] <= a.alpha]; th = ok[0] if ok else GRID[-1]
        cal = {"t_hi": th, "far_max": {str(t): v for t, v in worst.items()}, "null_far_max_at_t_hi": worst[th]}
t_hi = a.t_hi or (cal["t_hi"] if cal else 4.0)

px = {k: np.full(dem.shape, np.nan, "float32") for k in K}; age = np.full(dem.shape, np.nan, "float32")
for d in sorted(post):                                         # earliest clear post-event observation per pixel
    x = dates[d][0]; m = np.isnan(px["ndvi"]) & np.all([np.isfinite(x[k]) for k in K], axis=0)
    for k in K: px[k][m] = x[k][m]
    age[m] = (d - ev).days
ref, dlt, valid = deltas(px, pre, min_ref); z = zs(dlt, valid)

water_like = (px["mndwi"] > a.mndwi_post) & (ref["mndwi"] < a.mndwi_ref)
water = hysteresis(valid & water_like & (z["mndwi"] > t_hi), valid & water_like & (z["mndwi"] > a.t_lo), MINPX)
rest = valid & ~water
scar = hysteresis(rest & (z["ndvi"] < -t_hi) & (z["bsi"] > t_hi), rest & (z["ndvi"] < -a.t_lo) & (z["bsi"] > a.t_lo), MINPX) & ~water
seed_frac = float(patch_filter(seeds(z, t_hi) & valid, MINPX)[valid].mean()) if valid.any() else 0.0
gate_thr = max(3 * cal["null_far_max_at_t_hi"], 5e-4) if cal else None
status = "change_detected" if ((gate_thr is None or seed_frac >= gate_thr) and (water | scar).any()) else "no_significant_change"
null_ok = cal is None or cal["null_far_max_at_t_hi"] <= a.alpha
if not null_ok: status = "null_not_calibrated"   # no grid threshold met alpha: S2 is uninformative either way

cls = blank.copy()
if null_ok: cls[valid] = 0
if status == "change_detected": cls[scar] = 2; cls[water] = 1
write(Path(a.out_dir) / "s2_post_age_days_30m.tif", age, T, EPSG)
pk = 900 / 1e6
finish(status, {"pre_dates": [str(d) for d in pre], "post_dates": [str(d) for d in post], "min_ref": min_ref,
    "t_hi": t_hi, "t_lo": a.t_lo, "calibrated": cal is not None, "null": cal, "seed_fraction": seed_frac, "gate_threshold": gate_thr,
    "floor_clear_post_fraction": float(valid[floor].mean()) if floor.any() else None,
    "valid_post_fraction_all": float(valid[np.isfinite(dem)].mean()),
    "area_km2": {"water": float((cls == 1).sum() * pk), "scar_total": float((cls == 2).sum() * pk),
                 "scar_on_floor": float(((cls == 2) & floor).sum() * pk)}}, cls)
#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np, rasterio
from src.analysis.changelib import *

ap = argparse.ArgumentParser()
ap.add_argument("--ref", default="pre,placebo,pre3,pre4"); ap.add_argument("--post", default="post")
ap.add_argument("--proc-dir", default="data/processed"); ap.add_argument("--out-dir", default="data/processed")
ap.add_argument("--calib", default="outputs/diagnostics/step4_null_calibration.json")
ap.add_argument("--res", type=int, default=30); ap.add_argument("--smooth", type=int, default=1)
ap.add_argument("--floor-m", type=float, default=30); ap.add_argument("--ctrl-m", type=float, default=100)
ap.add_argument("--t-hi", type=float); ap.add_argument("--t-lo", type=float, default=2.5)
ap.add_argument("--min-patch", type=int, default=8)
ap.add_argument("--vv-water", type=float, default=-16.0); ap.add_argument("--vh-water", type=float, default=-22.0)
ap.add_argument("--auto-water", action="store_true"); ap.add_argument("--no-gate", action="store_true")
ap.add_argument("--track-id", default="asc85")
a = ap.parse_args(); R, refs = a.res, a.ref.split(",")
MINPX = a.min_patch * (9 if R == 10 else 1)
cal = json.load(open(a.calib)) if Path(a.calib).exists() else {}
t_hi = a.t_hi or cal.get("t_hi", 3.5); null_far = cal.get("null_far_max_at_t_hi")

hand, mask, dem = domain(a.proc_dir, R)
db = {p: [load_db(a.proc_dir, m, p, R, a.smooth) for m in refs] for p in ("VV", "VH")}
post = {p: load_db(a.proc_dir, a.post, p, R, a.smooth) for p in ("VV", "VH")}
ref = {p: ref_db(db[p]) for p in db}; lr = {p: post[p] - ref[p] for p in db}
fin = np.isfinite(hand) & np.isfinite(dem) & np.isfinite(lr["VV"]) & np.isfinite(lr["VH"])
valid = fin & (mask == 0); floor = valid & (hand <= a.floor_m)
ctrl = control(valid, hand, a.ctrl_m)
z = {p: robust_z(lr[p], dem, ctrl) for p in lr}
zc = zcomb(z["VV"], z["VH"], ctrl); zw = np.maximum(z["VV"], z["VH"])   # zw < -t: BOTH pols dropped

tvv, tvh, wsrc = a.vv_water, a.vh_water, "fixed"
if a.auto_water:                                    # water level from permanent water in the reference
    perm = floor & (hand <= 15) & (ref["VV"] < -17) & (ref["VH"] < -23)
    if perm.sum() >= 500:
        tvv = float(np.clip(np.percentile(ref["VV"][perm], 95), -20, -14))
        tvh = float(np.clip(np.percentile(ref["VH"][perm], 95), -26, -19)); wsrc = f"auto({int(perm.sum())} px)"
water_post = (post["VV"] < tvv) & (post["VH"] < tvh); water_ref = (ref["VV"] < tvv) & (ref["VH"] < tvh)

new_water = floor & water_post & ~water_ref                                # permanent water excluded
flood  = hysteresis(new_water & (zw < -t_hi), new_water & (zw < -a.t_lo), MINPX)
nw = floor & ~water_post
dark   = hysteresis(nw & (z["VH"] < -t_hi), nw & (z["VH"] < -a.t_lo), MINPX) & ~flood
bright = hysteresis(floor & (zc > t_hi), floor & (zc > a.t_lo), MINPX) & ~flood & ~dark

seed_frac = float(patch_filter(floor & any_seed(z["VH"], zc, t_hi), MINPX)[floor].mean()) if floor.any() else 0.0
gate_thr = max(3 * null_far, 5e-4) if null_far is not None else None   # event must clearly exceed the null
gate_pass = a.no_gate or gate_thr is None or seed_frac >= gate_thr
status = "change_detected" if (gate_pass and (flood | dark | bright).any()) else "no_significant_change"

cls = np.full(mask.shape, 255, np.uint8)
cls[valid & ~floor] = 253; cls[floor] = 0
if status == "change_detected": cls[bright] = 3; cls[dark] = 2; cls[flood] = 1
cls[np.isfinite(mask) & (mask != 0) & np.isfinite(hand)] = 254

_, prof = rd(Path(a.proc_dir) / f"s1_{a.post}_VV_{R}m.tif")
prof.update(dtype="uint8", nodata=255, count=1, compress="deflate")
def put(name, arr):
    with rasterio.open(Path(a.out_dir) / name, "w", **prof) as d: d.write(arr.astype("uint8"), 1)
put(f"detect_class_{R}m.tif", cls)
if R == 30:                                         # names the downstream scripts already read
    put("flood_mask.tif", cls == 1); put("debris_mask.tif", (cls == 2) | (cls == 3)); put("observable_mask.tif", mask == 0)

pk = abs(prof["transform"].a * prof["transform"].e) / 1e6; fa = np.isfinite(hand) & np.isfinite(dem) & (hand <= a.floor_m)
summary = {"track": a.track_id, "status": status, "refs": refs, "post": a.post, "t_hi": t_hi, "t_lo": a.t_lo,
           "calibrated": bool(cal), "alpha_met": bool(cal) and bool(cal.get("alpha_met", True)) if isinstance(cal, dict) else bool(cal),
           "null_far_max": null_far, "gate_threshold": gate_thr, "seed_fraction_floor": seed_frac,
           "water_thresholds_db": {"VV": tvv, "VH": tvh, "source": wsrc}, "floor_km2": float(floor.sum() * pk),
           "usable_fraction_of_floor": float((fa & valid).sum() / max(fa.sum(), 1)),
           "area_km2": {n: float((cls == c).sum() * pk) for n, c in
                        (("flood_water", 1), ("surface_dark", 2), ("surface_bright", 3))}}
Path("outputs/diagnostics").mkdir(parents=True, exist_ok=True)
Path(f"outputs/diagnostics/detect_{a.track_id}.json").write_text(json.dumps(summary, indent=2)); print(json.dumps(summary, indent=2))
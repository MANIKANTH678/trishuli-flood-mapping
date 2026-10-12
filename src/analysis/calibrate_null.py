import argparse, json
from pathlib import Path
import numpy as np
from src.analysis.changelib import *

ap = argparse.ArgumentParser()
ap.add_argument("--ref", default="pre,placebo,pre3,pre4")
ap.add_argument("--proc-dir", default="data/processed"); ap.add_argument("--res", type=int, default=30)
ap.add_argument("--smooth", type=int, default=1); ap.add_argument("--floor-m", type=float, default=30)
ap.add_argument("--ctrl-m", type=float, default=100); ap.add_argument("--min-patch", type=int, default=8)
ap.add_argument("--alpha", type=float, default=1e-3)
ap.add_argument("--out", default="outputs/diagnostics/step4_null_calibration.json")
a = ap.parse_args(); members, R = a.ref.split(","), a.res
if len(members) < 3: raise SystemExit("need >= 3 reference scenes for leave-one-out nulls")
MINPX = a.min_patch * (9 if R == 10 else 1)

hand, mask, dem = domain(a.proc_dir, R)
db = {p: {m: load_db(a.proc_dir, m, p, R, a.smooth) for m in members} for p in ("VV", "VH")}
GRID = [3.0, 3.5, 4.0, 4.5, 5.0, 6.0]; far = {t: [] for t in GRID}
for j in members:
    others = [m for m in members if m != j]
    lr = {p: db[p][j] - ref_db([db[p][m] for m in others]) for p in db}
    valid = (np.isfinite(hand) & np.isfinite(dem) & np.isfinite(lr["VV"]) & np.isfinite(lr["VH"]) & (mask == 0))
    ctrl = control(valid, hand, a.ctrl_m); floor = valid & (hand <= a.floor_m)
    z = {p: robust_z(lr[p], dem, ctrl) for p in lr}; zc = zcomb(z["VV"], z["VH"], ctrl)
    for t in GRID:
        far[t].append(float(patch_filter(floor & any_seed(z["VH"], zc, t), MINPX)[floor].mean()))
worst = {t: max(v) for t, v in far.items()}
ok = [t for t in GRID if worst[t] <= a.alpha]; t_hi = ok[0] if ok else GRID[-1]
out = {"members": members, "alpha": a.alpha, "alpha_met": bool(ok), "t_hi": t_hi, "null_far_max_at_t_hi": worst[t_hi],
       "far_max_by_threshold": {str(t): v for t, v in worst.items()},
       "far_mean_by_threshold": {str(t): float(np.mean(v)) for t, v in far.items()},
       "floor_m": a.floor_m, "res": R, "min_patch_px": MINPX}
Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
if not ok: print("WARNING: no threshold met alpha; using the largest")
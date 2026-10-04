"""Co-registration check using DEM-predicted radar shadow.

Radar shadow is dark in the SAR. The DEM-based radar mask (radar_mask_30m.tif,
codes 2 = shadow, 3 = cast shadow) predicts where it should be. We shift the
mask over the pre-event VV image and find the shift with the lowest mean VV.
A sharp minimum at (0, 0) means the SAR and DEM are aligned. A minimum
elsewhere, consistent across tiles, is an offset. A flat or scattered result
means this check cannot detect an offset.

A positive dx / dy means the SAR feature lies east / south of the DEM prediction.

Run from the repo root:
    python -m src.analysis.coreg_shadow
"""
import numpy as np
import rasterio
from pathlib import Path

P = Path(__file__).resolve().parents[2] / "data" / "processed"
MAX_SHIFT, STEP, MIN_PX = 40, 2, 200      # pixels (30 m each)


def rd(name):
    with rasterio.open(P / name) as s:
        return s.read(1, masked=True).astype("float32").filled(np.nan), s.res[0]


vv, res = rd("s1_pre_VV_30m.tif")
mask, _ = rd("radar_mask_30m.tif")
H, W = vv.shape
ys, xs = np.nonzero(np.isin(mask, (2, 3)))      # shadow, cast shadow
shifts = list(range(-MAX_SHIFT, MAX_SHIFT + 1, STEP))
i0 = shifts.index(0)


def mean_at(dx, dy, sel):
    yy, xx = ys[sel] + dy, xs[sel] + dx
    ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
    v = vv[yy[ok], xx[ok]]
    v = v[np.isfinite(v)]
    return float(v.mean()) if v.size >= MIN_PX else np.nan


def search(sel):
    grid = np.array([[mean_at(dx, dy, sel) for dx in shifts] for dy in shifts])
    if not np.isfinite(grid).any():
        return None
    iy, ix = np.unravel_index(np.nanargmin(grid), grid.shape)
    return grid, shifts[ix], shifts[iy], grid[iy, ix], grid[i0, i0], float(np.nanmean(grid))


print(f"pixel size {res:.0f} m; grid {W} x {H}; shadow + cast shadow px: {len(ys)}")
full = search(np.ones(len(ys), bool))
grid, bx, by, rbest, r0, rmean = full
print(f"whole scene: best shift dx {bx} px ({bx * res:.0f} m), dy {by} px ({by * res:.0f} m)")
print(f"  mean VV at best {rbest:.2f} dB; at (0, 0) {r0:.2f} dB; average over all shifts {rmean:.2f} dB")
print("\nmean VV (dB) along x at the best dy, and along y at the best dx")
print("shift_px   x-profile   y-profile")
for k, s in enumerate(shifts):
    print(f"{s:8d}   {grid[shifts.index(by), k]:9.2f}   {grid[k, shifts.index(bx)]:9.2f}")

print("\n3 x 3 tiles (row, col): n px | best dx, dy px | mean at best | mean at (0, 0)")
bxs, bys = [], []
for i in range(3):
    for j in range(3):
        sel = ((ys * 3 // H) == i) & ((xs * 3 // W) == j)
        res_t = search(sel) if sel.sum() >= 1000 else None
        if res_t is None:
            print(f"  ({i},{j}): {int(sel.sum())} px, too few")
            continue
        _, tx, ty, tb, t0, _ = res_t
        bxs.append(tx); bys.append(ty)
        print(f"  ({i},{j}): {int(sel.sum()):6d} | {tx:4d}, {ty:4d} | {tb:6.2f} | {t0:6.2f}")
if bxs:
    print(f"\nbest dx across tiles: median {np.median(bxs):.0f} px, range {min(bxs)} to {max(bxs)}")
    print(f"best dy across tiles: median {np.median(bys):.0f} px, range {min(bys)} to {max(bys)}")
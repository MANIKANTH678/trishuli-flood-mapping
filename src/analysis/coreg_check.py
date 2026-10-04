"""Co-registration check: apparent shift of the SAR relative to the DEM grid.

Correlates high-passed pre-event VV (dB) with the high-passed DEM slope along the
image x axis for a range of pixel shifts, over the whole scene and over a 3 x 3
grid of tiles. A positive shift means SAR features lie east / south of the same
DEM features. The y shift is a control. If the best shift is consistent across
tiles and its correlation is clearly above the correlation at 0, there is a real
offset. If the best shift scatters between tiles or the peak is weak and broad,
there is no reliable scene-wide offset.

Run from the repo root:
    python -m src.analysis.coreg_check
"""
import numpy as np
import rasterio
from pathlib import Path
from scipy import ndimage as ndi

P = Path(__file__).resolve().parents[2] / "data" / "processed"
MAX_SHIFT, STEP, HP = 40, 2, 31      # pixels; HP = high-pass window in pixels


def rd(name):
    with rasterio.open(P / name) as s:
        return s.read(1, masked=True).astype("float32").filled(np.nan), s.res[0]


def highpass(a, n):
    ok = np.isfinite(a)
    num = ndi.uniform_filter(np.where(ok, a, 0).astype("float32"), n)
    den = ndi.uniform_filter(ok.astype("float32"), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = a - num / den
    out[den < 0.5] = np.nan
    return out


dem, res = rd("dem_30m.tif")
vv, _ = rd("s1_pre_VV_30m.tif")
H, W = dem.shape
A = highpass(np.gradient(dem, res, axis=1), HP)
B = highpass(vv, HP)
shifts = list(range(-MAX_SHIFT, MAX_SHIFT + 1, STEP))


def corr(dx, dy, ys, xs):
    """Correlate DEM slope at (y, x) with SAR at (y + dy, x + dx) inside a region."""
    y0, y1 = max(ys[0], -dy), min(ys[1], H - dy)
    x0, x1 = max(xs[0], -dx), min(xs[1], W - dx)
    if y1 <= y0 or x1 <= x0:
        return np.nan
    a = A[y0:y1, x0:x1]
    b = B[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 5000:
        return np.nan
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def curve(axis, ys, xs):
    return {s: (corr(s, 0, ys, xs) if axis == "x" else corr(0, s, ys, xs)) for s in shifts}


def best(r):
    ok = {s: v for s, v in r.items() if np.isfinite(v)}
    if not ok:
        return None, np.nan, np.nan
    b = max(ok, key=lambda s: abs(ok[s]))
    return b, ok[b], r.get(0, np.nan)


full = ((0, H), (0, W))
rx, ry = curve("x", *full), curve("y", *full)
print(f"pixel size {res:.0f} m; grid {W} x {H}; high-pass window {HP} px")
print("shift_px  shift_m   r(x shift)   r(y shift)")
for s in shifts:
    print(f"{s:8d} {s * res:8.0f}   {rx[s]:+.4f}      {ry[s]:+.4f}")
for name, r in (("x", rx), ("y", ry)):
    b, rb, r0 = best(r)
    print(f"whole scene, {name}: best shift {b} px ({b * res:.0f} m), r = {rb:+.4f}; at 0: {r0:+.4f}")

print("\n3 x 3 tiles (row, col): best x shift px (r, r at 0) | best y shift px (r, r at 0)")
xs_best = []
for i in range(3):
    for j in range(3):
        ys = (i * H // 3, (i + 1) * H // 3)
        xs = (j * W // 3, (j + 1) * W // 3)
        bx, rbx, r0x = best(curve("x", ys, xs))
        by, rby, r0y = best(curve("y", ys, xs))
        if bx is not None:
            xs_best.append(bx)
        print(f"  ({i},{j}):  x {bx} ({rbx:+.3f}, {r0x:+.3f})  |  y {by} ({rby:+.3f}, {r0y:+.3f})")
if xs_best:
    print(f"\nx best shifts across tiles: median {np.median(xs_best):.0f} px, range {min(xs_best)} to {max(xs_best)} px")
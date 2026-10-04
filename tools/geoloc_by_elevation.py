"""Shift of v0 vs new product by elevation band (FFT normalized cross-correlation).
(dr, dc) = displacement of v0 content relative to new: rows +south, cols +east.
Expected: toward the sensor (ascending ~261 deg az, descending ~99 deg)."""
import argparse, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve

ap = argparse.ArgumentParser()
ap.add_argument("--new", default="data/processed/s1_pre_VV_30m.tif")
ap.add_argument("--old", default="data/processed/_v0/s1_pre_VV_30m.tif")
ap.add_argument("--dem", default="data/processed/dem_30m.tif")
ap.add_argument("--maxpx", type=int, default=200)               # +-6 km
ap.add_argument("--bands", default="400,900,1400,2000,2800,4000")
a = ap.parse_args()

def load(p):
    with rasterio.open(p) as s:
        return s.read(1, masked=True).filled(np.nan).astype("float32"), s.transform, s.crs, s.res[0]
R, T, crs, res = load(a.new); H = load(a.dem)[0]
V = np.full(R.shape, np.nan, np.float32)
with rasterio.open(a.old) as s:
    reproject(rasterio.band(s, 1), V, src_nodata=-9999, dst_nodata=np.nan,
              dst_transform=T, dst_crs=crs, resampling=Resampling.bilinear)

def hp(x, sg=8):                                   # remove smooth background, NaN-aware
    ok = np.isfinite(x); f = np.where(ok, x, 0.0)
    lo = gaussian_filter(f, sg) / np.maximum(gaussian_filter(ok.astype("float32"), sg), 1e-3)
    return np.where(ok, f - lo, 0.0).astype("float32"), ok
Rh, okR = hp(R); Vh, okV = hp(V)

K, (n0, n1) = a.maxpx, R.shape
sl = (slice(n0 - 1 - K, n0 + K), slice(n1 - 1 - K, n1 + K))   # zero shift at index n-1 of 'full'
rev = lambda x: x[::-1, ::-1]
edges = [float(x) for x in a.bands.split(",")]; rows = []
for lo, hi in zip(edges[:-1], edges[1:]):
    M = (okR & (H >= lo) & (H < hi)).astype("float32")
    if M.sum() < 20000:
        print(f"{lo:.0f}-{hi:.0f} m: too few pixels"); continue
    B = M * Rh
    num = fftconvolve(Vh, rev(B), "full")[sl]
    den = fftconvolve(Vh * Vh, rev(M), "full")[sl]
    cnt = fftconvolve(okV.astype("float32"), rev(M), "full")[sl]
    ncc = np.where(cnt > 0.5 * M.sum(), num / np.sqrt(np.maximum(den, 1e-9) * (B * B).sum()), np.nan)
    i = np.unravel_index(np.nanargmax(ncc), ncc.shape); dr, dc = i[0] - K, i[1] - K
    yy, xx = np.ogrid[:ncc.shape[0], :ncc.shape[1]]
    side = np.nanmax(np.where((abs(yy - i[0]) > 5) | (abs(xx - i[1]) > 5), ncc, np.nan))
    az = np.degrees(np.arctan2(dc, -dr)) % 360
    print(f"{lo:5.0f}-{hi:5.0f} m  d=({dr*res:+6.0f} S, {dc*res:+6.0f} E) m  az={az:5.1f}  "
          f"ncc={ncc[i]:.3f}  peak/side={ncc[i]/side:.2f}  at_edge={max(abs(dr), abs(dc)) == K}")
    rows.append(((lo + hi) / 2, dr * res, dc * res))
if len(rows) >= 3:
    h, s_, e_ = np.array(rows).T
    kE, bE = np.polyfit(h, e_, 1); kS, bS = np.polyfit(h, s_, 1)
    k = np.hypot(kE, kS)
    print(f"relief term: {k:.2f} m per m of height, toward az {np.degrees(np.arctan2(kE, -kS)) % 360:.0f} deg "
          f"-> implied incidence ~{np.degrees(np.arctan(1 / k)):.0f} deg (rough)")
    print(f"rigid offset at h=0: {bS:+.0f} m S, {bE:+.0f} m E")
else:
    print("fewer than 3 usable bands; no fit")
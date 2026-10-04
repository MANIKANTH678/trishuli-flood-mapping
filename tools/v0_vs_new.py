import numpy as np, rasterio
from scipy.ndimage import gaussian_filter

def load(p):
    with rasterio.open(p) as s:
        return s.read(1, masked=True).filled(np.nan), s.res[0]

v0, res = load(r"data\processed\_v0\s1_pre_VV_30m.tif")
new, _ = load(r"data\processed\s1_pre_VV_30m.tif")

h = min(v0.shape[0], new.shape[0]); w = min(v0.shape[1], new.shape[1])
v0, new = v0[:h, :w], new[:h, :w]

def prep(a):
    ok = np.isfinite(a)
    a = np.where(ok, a, np.nanmean(a))
    a = a - gaussian_filter(a, 20)      # remove the slow range/incidence trend
    a[~ok] = 0
    return a - a.mean()

A, B = prep(v0), prep(new)
c = np.fft.ifft2(np.fft.fft2(A) * np.conj(np.fft.fft2(B))).real
py, px = np.unravel_index(np.argmax(c), c.shape)
if py > h // 2: py -= h
if px > w // 2: px -= w
z = (c.max() - c.mean()) / c.std()
print(f"v0 content is shifted {py} rows (south+), {px} cols (east+) relative to new")
print(f"= {py * res:.0f} m south, {px * res:.0f} m east; peak is {z:.1f} sigma above the correlation floor")
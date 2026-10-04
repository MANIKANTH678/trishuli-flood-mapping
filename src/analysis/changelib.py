"""changelib.py - shared change-detection helpers (linear-power reference, robust z, patches)."""
import warnings
from pathlib import Path
import numpy as np, rasterio
from scipy import ndimage as ndi

def rd(path):
    with rasterio.open(path) as s:
        return s.read(1, masked=True).astype("float32").filled(np.nan), s.profile

def up(x, res): return x if res == 30 else np.repeat(np.repeat(x, 3, 0), 3, 1)

def smooth_db(db, n):
    if n <= 1: return db
    ok = np.isfinite(db); lin = np.where(ok, 10 ** (db / 10), 0).astype("float32")
    num, den = ndi.uniform_filter(lin, n), ndi.uniform_filter(ok.astype("float32"), n)
    with np.errstate(divide="ignore", invalid="ignore"): out = 10 * np.log10(num / den)
    out[(den < 0.5) | ~np.isfinite(out)] = np.nan; return out.astype("float32")

def load_db(proc, split, pol, res, smooth):
    return smooth_db(rd(Path(proc) / f"s1_{split}_{pol}_{res}m.tif")[0], smooth)

def ref_db(members):
    """Per-pixel median in LINEAR power across same-track scenes, returned in dB."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return (10 * np.log10(np.nanmedian(10 ** (np.stack(members) / 10), axis=0))).astype("float32")

def domain(proc, res):
    hand = up(rd(Path(proc) / "hand_30m.tif")[0], res)
    mask = up(rd(Path(proc) / "radar_mask_30m.tif")[0], res)
    return hand, mask, rd(Path(proc) / f"dem_{res}m.tif")[0]

def control(valid, hand, ctrl_m):
    c = valid & (hand >= ctrl_m)
    return c if c.sum() >= 50000 else valid       # flat terrain: robust stats over everything

def robust_z(lr, dem, ctrl):
    band = np.digitize(dem, np.arange(0, 6001, 250))
    gm = np.median(lr[ctrl]); gs = 1.4826 * np.median(np.abs(lr[ctrl] - gm))
    med = np.full(lr.shape, gm, "float32"); sig = np.full(lr.shape, max(gs, 1e-3), "float32")
    for b in np.unique(band[ctrl]):
        m = ctrl & (band == b)
        if m.sum() >= 5000:
            mb = np.median(lr[m]); sb = 1.4826 * np.median(np.abs(lr[m] - mb))
            sel = band == b; med[sel], sig[sel] = mb, max(sb, 1e-3)
    return (lr - med) / sig

def zcomb(zvv, zvh, ctrl):
    zc = (zvv + zvh) / 2; m = np.median(zc[ctrl])
    return (zc - m) / (1.4826 * np.median(np.abs(zc[ctrl] - m)))

def any_seed(zvh, zc, t): return (zvh < -t) | (zc > t)

def patch_filter(m, minpx):
    lab, n = ndi.label(m)
    if n == 0: return m
    keep = np.zeros(n + 1, bool); keep[1:] = ndi.sum(m, lab, np.arange(1, n + 1)) >= minpx
    return keep[lab]

def hysteresis(seed, low, minpx):
    """Keep connected 'low' regions that contain a (patch-filtered) seed."""
    seed = patch_filter(seed, minpx)
    lab, n = ndi.label(low | seed)
    if n == 0: return seed
    keep = np.zeros(n + 1, bool); keep[np.unique(lab[seed])] = True; keep[0] = False
    return patch_filter(keep[lab], minpx)
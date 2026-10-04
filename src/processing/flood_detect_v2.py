# DEPRECATED: replaced by src/analysis/detect.py
"""flood_detect_v2.py - rubric-grade flood + debris detection."""
import os, sys
import numpy as np
import rioxarray
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR

SLOPE_MAX_DEG = 12.0
PERMANENT_WATER_VV_DB = -18.0
PERMANENT_WATER_VH_DB = -22.0
FLOOD_PCTL = 5.0
FLOOD_THRESHOLD_MIN = -3.5
FLOOD_THRESHOLD_MAX = -1.5
DEBRIS_LOW_DB = -0.5
MIN_FLOOD_PATCH = 20
MIN_DEBRIS_PATCH = 50
SPECKLE_SIZE = 5


def load(path):
    da = rioxarray.open_rasterio(path, masked=True).squeeze()
    return da.where(np.isfinite(da))


def lee_filter(img, size=SPECKLE_SIZE):
    img = np.asarray(img, dtype="float32")
    valid = np.isfinite(img)
    filled = np.where(valid, img, np.nanmean(img))
    mean = ndimage.uniform_filter(filled, size=size)
    sq   = ndimage.uniform_filter(filled * filled, size=size)
    var  = np.maximum(sq - mean * mean, 0.0)
    nv = np.nanmedian(var)
    if nv <= 0:
        nv = 1e-3
    out = mean + (var / (var + nv)) * (filled - mean)
    out[~valid] = np.nan
    return out


def slope_deg(dem, cell=30.0):
    dy, dx = np.gradient(dem, cell, cell)
    return np.degrees(np.arctan(np.hypot(dx, dy)))


def drop_small(mask, min_px):
    lab, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    small = np.isin(lab, np.where(sizes < min_px)[0] + 1)
    m = mask.copy()
    m[small] = 0
    return m


def detect(pre_vv_p, post_vv_p, pre_vh_p, post_vh_p, dem_p, out_dir):
    print("Loading rasters ...")
    pre_vv  = load(pre_vv_p)
    post_vv = load(post_vv_p)
    pre_vh  = load(pre_vh_p)
    post_vh = load(post_vh_p)
    dem     = load(dem_p)

    print("Lee speckle filtering ...")
    pre_vv_f  = lee_filter(pre_vv.values)
    post_vv_f = lee_filter(post_vv.values)
    pre_vh_f  = lee_filter(pre_vh.values)
    post_vh_f = lee_filter(post_vh.values)

    print("Dual-pol change ...")
    d_vv = post_vv_f - pre_vv_f
    d_vh = post_vh_f - pre_vh_f
    combined = 0.5 * d_vv + 0.5 * d_vh

    v = combined[np.isfinite(combined)]
    p_low = float(np.percentile(v, FLOOD_PCTL))
    t_used = float(np.clip(p_low, FLOOD_THRESHOLD_MIN, FLOOD_THRESHOLD_MAX))
    print("Adaptive threshold = %.2f dB (p%.1f = %.2f, clipped to [%.1f, %.1f])"
          % (t_used, FLOOD_PCTL, p_low, FLOOD_THRESHOLD_MIN, FLOOD_THRESHOLD_MAX))

    print("Masks: slope, permanent water, valid data ...")
    slope = slope_deg(dem.values, 30.0)
    valid = np.isfinite(combined)
    permanent_water = ((pre_vv_f < PERMANENT_WATER_VV_DB) |
                       (pre_vh_f < PERMANENT_WATER_VH_DB))

    n_valid = int(valid.sum())
    n_flat  = int((valid & (slope < SLOPE_MAX_DEG)).sum())
    n_land  = int((valid & (slope < SLOPE_MAX_DEG) & ~permanent_water).sum())
    n_under = int((valid & (combined < t_used)).sum())
    print("  valid px:       %d" % n_valid)
    print("  flat (slope<%.0f): %d" % (SLOPE_MAX_DEG, n_flat))
    print("  not water:      %d" % n_land)
    print("  combined<thr:   %d" % n_under)

    flood = (combined < t_used) & valid & (slope < SLOPE_MAX_DEG) & ~permanent_water
    print("  flood pre-morph: %d" % int(flood.sum()))

    flood = drop_small(flood.astype(np.uint8), MIN_FLOOD_PATCH)
    print("  flood post-morph+patch: %d" % int(flood.sum()))

    debris = ((combined >= t_used) & (combined < DEBRIS_LOW_DB) & valid
              & (slope < SLOPE_MAX_DEG) & ~permanent_water).astype(np.uint8)
    print("  debris pre-morph: %d" % int(debris.sum()))
    debris = ndimage.binary_opening(debris, iterations=1).astype(np.uint8)
    debris = drop_small(debris, MIN_DEBRIS_PATCH)
    print("  debris post-morph+patch: %d" % int(debris.sum()))

    for arr, name in [(flood, "flood_mask.tif"), (debris, "debris_mask.tif")]:
        out = pre_vv.copy()
        out.values = arr.astype(np.uint8)
        out.rio.write_nodata(0, inplace=True)
        out.rio.to_raster(os.path.join(out_dir, name))
        print("wrote %s: %d px (%.2f km2)" % (name, int(arr.sum()), arr.sum()*900/1e6))



# ---- public helpers (importable, tested) --------------------------------

def lee_filter_db(img_db, size=SPECKLE_SIZE, enl=4.0):
    """dB-in/dB-out wrapper around lee_filter. Stable public name."""
    return lee_filter(img_db, size=size)


def otsu_or_fallback(diff, fallback, nbins=256):
    """Return (threshold, source). Prefer skimage Otsu; fall back to constant."""
    d = np.asarray(diff, dtype=np.float32)
    v = d[np.isfinite(d)]
    if v.size < 100:
        return float(fallback), "fallback(insufficient-pixels)"
    try:
        from skimage.filters import threshold_otsu
        return float(threshold_otsu(v, nbins=nbins)), "otsu"
    except Exception as e:
        return float(fallback), f"fallback({type(e).__name__})"


if __name__ == "__main__":
    d = PROCESSED_DIR
    detect(
        pre_vv_p  = os.path.join(d, "s1_pre_VV_30m.tif"),
        post_vv_p = os.path.join(d, "s1_post_VV_30m.tif"),
        pre_vh_p  = os.path.join(d, "s1_pre_VH_30m.tif"),
        post_vh_p = os.path.join(d, "s1_post_VH_30m.tif"),
        dem_p     = os.path.join(d, "dem_30m.tif"),
        out_dir   = d,
    )

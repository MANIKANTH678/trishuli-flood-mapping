"""Detect flood extent from Sentinel-1 backscatter change."""
import os
import sys
import numpy as np
import rioxarray
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR

NODATA = -9999.0


def load(path):
    da = rioxarray.open_rasterio(path, masked=True).squeeze()
    return da.where(da != NODATA)


def otsu_threshold(values, nbins=256):
    vals = values[np.isfinite(values)]
    hist, edges = np.histogram(vals, bins=nbins)
    centers = (edges[:-1] + edges[1:]) / 2
    total = hist.sum()
    sum_all = (hist * centers).sum()
    sum_b, w_b = 0.0, 0.0
    best_t, best_var = centers[0], 0.0
    for i in range(nbins):
        w_b += hist[i]
        if w_b == 0: continue
        w_f = total - w_b
        if w_f == 0: break
        sum_b += hist[i] * centers[i]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        v = w_b * w_f * (m_b - m_f) ** 2
        if v > best_var:
            best_var, best_t = v, centers[i]
    return best_t


def detect_flood(pre_vv_path, post_vv_path, dem_path, out_path,
                 min_patch_pixels=100):
    print("📥 Loading rasters...")
    pre_vv  = load(pre_vv_path)
    post_vv = load(post_vv_path)
    dem     = load(dem_path)
    print(f"   shapes: {pre_vv.shape}  {post_vv.shape}  {dem.shape}")

    print("📊 Computing backscatter difference (post - pre) in dB...")
    diff = post_vv.values - pre_vv.values

    print("🎯 Finding Otsu threshold...")
    t = otsu_threshold(diff)
    print(f"   threshold = {t:.2f} dB")

    print("🌊 Classifying pixels...")
    flood = (diff < t).astype(np.uint8)

    print("🚫 Masking steep slopes (>15°) and permanent water (<-18 dB)...")
    dy, dx = np.gradient(dem.values, 30, 30)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    flood[slope > 15] = 0
    flood[pre_vv.values < -18] = 0

    print("🧹 Morphological cleanup...")
    flood = ndimage.binary_opening(flood, iterations=1).astype(np.uint8)
    labeled, n = ndimage.label(flood)
    sizes = ndimage.sum(flood, labeled, range(1, n + 1))
    small = np.isin(labeled, np.where(sizes < min_patch_pixels)[0] + 1)
    flood[small] = 0

    print("💾 Writing flood_mask.tif...")
    out_da = pre_vv.copy()
    out_da.values = flood.astype(np.uint8)
    out_da.rio.write_nodata(0, inplace=True)
    out_da.rio.to_raster(out_path)

    area_km2 = flood.sum() * 900 / 1e6
    print(f"✅ {out_path}")
    print(f"   flooded pixels: {flood.sum():,}")
    print(f"   flooded area:   {area_km2:.2f} km²")


if __name__ == "__main__":
    d = PROCESSED_DIR
    detect_flood(
        pre_vv_path  = os.path.join(d, "s1_pre_VV_30m.tif"),
        post_vv_path = os.path.join(d, "s1_post_VV_30m.tif"),
        dem_path     = os.path.join(d, "dem_30m.tif"),
        out_path     = os.path.join(d, "flood_mask.tif"),
    )

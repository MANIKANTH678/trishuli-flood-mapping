"""Derive terrain and hydro features from DEM. No flood mask needed."""
import os, sys
import numpy as np
import rioxarray
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR


def load(path):
    return rioxarray.open_rasterio(path, masked=True).squeeze()


def slope_aspect(dem, cell=30):
    dy, dx = np.gradient(dem.values, cell, cell)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    aspect = np.degrees(np.arctan2(-dy, dx)) % 360
    return slope, aspect


def tpi(dem, radius_pixels=5):
    """Topographic Position Index — positive = ridge, negative = valley."""
    kernel = np.ones((2*radius_pixels+1, 2*radius_pixels+1))
    kernel /= kernel.sum()
    mean = ndimage.convolve(np.nan_to_num(dem.values, nan=0), kernel, mode="constant")
    return dem.values - mean


def distance_to_low_elevation(dem, threshold_percentile=5):
    """Distance (in pixels) from each cell to the nearest 'lowland' cell."""
    low = dem.values < np.nanpercentile(dem.values, threshold_percentile)
    return ndimage.distance_transform_edt(~low)


def main():
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    dem = load(os.path.join(PROCESSED_DIR, "dem_30m.tif"))
    print(f"DEM shape: {dem.shape}")

    print("Computing slope + aspect...")
    slope, aspect = slope_aspect(dem)

    print("Computing TPI...")
    t = tpi(dem, radius_pixels=5)

    print("Computing distance-to-lowland...")
    dist = distance_to_low_elevation(dem)

    out = os.path.join(OUTPUTS_DIR, "features")
    os.makedirs(out, exist_ok=True)

    np.save(os.path.join(out, "elevation.npy"), dem.values)
    np.save(os.path.join(out, "slope.npy"), slope)
    np.save(os.path.join(out, "aspect.npy"), aspect)
    np.save(os.path.join(out, "tpi.npy"), t)
    np.save(os.path.join(out, "dist_lowland.npy"), dist)

    pre_vv  = load(os.path.join(PROCESSED_DIR, "s1_pre_VV_30m.tif"))
    post_vv = load(os.path.join(PROCESSED_DIR, "s1_post_VV_30m.tif"))
    pre_vh  = load(os.path.join(PROCESSED_DIR, "s1_pre_VH_30m.tif"))
    post_vh = load(os.path.join(PROCESSED_DIR, "s1_post_VH_30m.tif"))

    np.save(os.path.join(out, "vv_diff.npy"), post_vv.values - pre_vv.values)
    np.save(os.path.join(out, "vh_diff.npy"), post_vh.values - pre_vh.values)
    np.save(os.path.join(out, "vv_pre.npy"), pre_vv.values)
    np.save(os.path.join(out, "vh_pre.npy"), pre_vh.values)

    print(f"✅ Saved {len(os.listdir(out))} feature files to {out}/")


if __name__ == "__main__":
    main()

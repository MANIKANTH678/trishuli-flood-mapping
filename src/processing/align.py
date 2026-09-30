"""
Align all rasters (DEM, S1, S2) to a common 30 m grid in EPSG:32645.

Outputs go to data/processed/. Every downstream consumer (P2, P4) reads
from that folder and can assume:
  - all rasters share the same shape, transform, CRS
  - NaN = nodata
  - S1 values are in dB (already log-scaled)
"""
import os
import glob
import numpy as np
import rioxarray
import rioxarray.merge
from rasterio.enums import Resampling

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import (
    BBOX, CRS, PIXEL_SIZE,
    DEM_DIR, S1_DIR, S2_PRE_DIR, S2_POST_DIR,
    PROCESSED_DIR,
)

NODATA = -9999.0


def build_reference_grid():
    """Return transform, width, height for the target grid covering BBOX."""
    from rasterio.transform import from_origin
    from pyproj import Transformer

    west, south, east, north = BBOX
    transformer = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)

    xs, ys = [], []
    for lon, lat in [(west, south), (east, south),
                     (east, north), (west, north)]:
        x, y = transformer.transform(lon, lat)
        xs.append(x); ys.append(y)

    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    width  = int(np.ceil((maxx - minx) / PIXEL_SIZE))
    height = int(np.ceil((maxy - miny) / PIXEL_SIZE))
    transform = from_origin(minx, maxy, PIXEL_SIZE, PIXEL_SIZE)

    print(f"📐 Reference grid: {width} × {height} pixels "
          f"({width * height * 4 / 1e6:.1f} MB per float32 band)")
    return transform, width, height


def build_dem(output_name="dem_30m.tif"):
    tiles = sorted(glob.glob(os.path.join(DEM_DIR, "*.tif")))
    if not tiles:
        print("❌ No DEM tiles found.")
        return None

    print(f"🗺  Mosaicking {len(tiles)} DEM tiles...")
    arrays = [rioxarray.open_rasterio(t, masked=True).squeeze() for t in tiles]
    dem = rioxarray.merge.merge_arrays(arrays)

    west, south, east, north = BBOX
    print(f"✂️  Clipping to bbox {BBOX}...")
    dem = dem.rio.clip_box(minx=west, miny=south, maxx=east, maxy=north,
                           crs="EPSG:4326")

    print(f"🔄 Reprojecting DEM to {CRS} @ {PIXEL_SIZE} m...")
    dem = dem.rio.reproject(CRS, resolution=PIXEL_SIZE,
                            resampling=Resampling.bilinear)

    dem = dem.astype(np.float32).fillna(NODATA)
    dem.rio.write_nodata(NODATA, inplace=True)

    out = os.path.join(PROCESSED_DIR, output_name)
    dem.rio.to_raster(out)
    print(f"✅ {out}  shape={dem.shape}")
    return out


def to_db(arr):
    """Convert Sentinel-1 GRD amplitude DN to dB."""
    finite = arr[np.isfinite(arr)]
    if len(finite) == 0:
        return arr
    if np.median(finite) > 10:      # linear amplitude DN
    # Copernicus SAFE export is missing the ~60 dB calibration constant.
    return 20.0 * np.log10(np.maximum(arr, 1e-6)) - 60.0 
    return arr


def align_s1(pre_dir, post_dir, out_prefix="s1"):
    dem_path = os.path.join(PROCESSED_DIR, "dem_30m.tif")
    if not os.path.exists(dem_path):
        print("❌ Run build_dem() first.")
        return
    ref = rioxarray.open_rasterio(dem_path, masked=True).squeeze()

    for label, folder in [("pre", pre_dir), ("post", post_dir)]:
        files = sorted(
            glob.glob(os.path.join(folder, "**", "*.tif"),  recursive=True) +
            glob.glob(os.path.join(folder, "**", "*.tiff"), recursive=True)
        )
        if not files:
            print(f"⚠️  No S1 files in {folder}")
            continue

        by_pol = {"VV": [], "VH": []}
        for f in files:
            name = os.path.basename(f).upper()
            if "VV" in name:
                by_pol["VV"].append(f)
            elif "VH" in name:
                by_pol["VH"].append(f)

        for pol, pol_files in by_pol.items():
            if not pol_files:
                continue
            out_name = f"{out_prefix}_{label}_{pol}_30m.tif"
            print(f"\n🔄 {label.upper()} {pol}: {len(pol_files)} frame(s)")

            arrays = []
            for f in pol_files:
                print(f"   loading {os.path.basename(f)[:65]}")
                da = rioxarray.open_rasterio(f, masked=True).squeeze()
                arr = da.values.astype(np.float32)
                arr = to_db(arr)
                da.values = arr
                arrays.append(da)

            if len(arrays) == 1:
                merged = arrays[0]
            else:
                print(f"   merging {len(arrays)} frames...")
                merged = rioxarray.merge.merge_arrays(arrays, nodata=np.nan)

            print(f"   reprojecting to reference grid...")
            aligned = merged.rio.reproject_match(ref,
                                                 resampling=Resampling.bilinear)

            aligned = aligned.astype(np.float32).fillna(NODATA)
            aligned.rio.write_nodata(NODATA, inplace=True)

            out = os.path.join(PROCESSED_DIR, out_name)
            aligned.rio.to_raster(out)
            print(f"  ✅ {out}  shape={aligned.shape}")


def align_s2(pre_dir, post_dir):
    dem_path = os.path.join(PROCESSED_DIR, "dem_30m.tif")
    if not os.path.exists(dem_path):
        return
    ref = rioxarray.open_rasterio(dem_path, masked=True).squeeze()

    for label, folder in [("pre", pre_dir), ("post", post_dir)]:
        files = sorted(glob.glob(os.path.join(folder, "*.tif")) +
                       glob.glob(os.path.join(folder, "*.jp2")))
        for f in files:
            name = os.path.basename(f).upper()
            band = None
            for b in ["B02", "B03", "B04", "B08", "B11", "B12"]:
                if b in name:
                    band = b
                    break
            if band is None:
                continue
            out_name = f"s2_{label}_{band}_30m.tif"
            print(f"🔄 Aligning {name} → {out_name}")
            da = rioxarray.open_rasterio(f, masked=True).squeeze()
            aligned = da.rio.reproject_match(ref, resampling=Resampling.bilinear)
            aligned = aligned.astype(np.float32).fillna(NODATA)
            aligned.rio.write_nodata(NODATA, inplace=True)
            out = os.path.join(PROCESSED_DIR, out_name)
            aligned.rio.to_raster(out)


if __name__ == "__main__":
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    print("=" * 60); print("STEP 1 — Reference grid"); print("=" * 60)
    build_reference_grid()

    print("\n" + "=" * 60); print("STEP 2 — DEM"); print("=" * 60)
    build_dem()

    print("\n" + "=" * 60); print("STEP 3 — Sentinel-1"); print("=" * 60)
    pre_dir  = os.path.join(S1_DIR, "pre")
    post_dir = os.path.join(S1_DIR, "post")
    if os.path.isdir(pre_dir) and os.path.isdir(post_dir):
        align_s1(pre_dir, post_dir)
    else:
        print(f"⚠️  S1 dirs missing: {pre_dir} / {post_dir}")

    print("\n" + "=" * 60); print("STEP 4 — Sentinel-2 (optional)"); print("=" * 60)
    if os.path.isdir(S2_PRE_DIR) and os.path.isdir(S2_POST_DIR):
        align_s2(S2_PRE_DIR, S2_POST_DIR)

    print("\n🎉 Alignment complete. Check data/processed/")

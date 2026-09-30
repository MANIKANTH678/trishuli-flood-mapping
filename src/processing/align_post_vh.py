"""One-off: align only POST VH with memory-friendlier processing."""
import os, sys, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import glob, numpy as np, rioxarray
from rasterio.enums import Resampling
from src.config import PROCESSED_DIR
from src.processing.align import to_db, NODATA

dem_path = os.path.join(PROCESSED_DIR, "dem_30m.tif")
ref = rioxarray.open_rasterio(dem_path, masked=True).squeeze()

# Find POST VH
files = glob.glob("data/raw/s1/post/**/*vh*.tiff", recursive=True) + \
        glob.glob("data/raw/s1/post/**/*vh*.tif",  recursive=True)
assert files, "No POST VH file found"
f = files[0]
print(f"Loading {f}")

# Open the big file, keep as float32 in memory
da = rioxarray.open_rasterio(f, masked=True).squeeze()
print(f"   loaded shape={da.shape}  dtype={da.dtype}")

# Convert to dB in-place
arr = da.values.astype(np.float32)
da.values = to_db(arr)
del arr
gc.collect()

print("Reprojecting to reference grid...")
aligned = da.rio.reproject_match(ref, resampling=Resampling.bilinear)
print(f"   reprojected shape={aligned.shape}")

# Free memory
del da
gc.collect()

# Cast + fill
aligned = aligned.astype(np.float32).fillna(NODATA)
aligned.rio.write_nodata(NODATA, inplace=True)

out = os.path.join(PROCESSED_DIR, "s1_post_VH_30m.tif")
aligned.rio.to_raster(out)
print(f"✅ {out}")

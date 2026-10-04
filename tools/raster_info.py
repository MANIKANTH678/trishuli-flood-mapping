import sys
import rasterio

paths = sys.argv[1:] or [
    r"data\processed\_v0\s1_pre_VV_30m.tif",
    r"data\processed\s1_pre_VV_10m.tif",
    r"data\processed\dem_30m.tif",
    r"data\processed\s1_pre_VV_30m.tif",
]
for p in paths:
    try:
        with rasterio.open(p) as s:
            print(p)
            print("  crs   :", s.crs)
            print("  shape :", s.height, "x", s.width)
            print("  res   :", s.res)
            print("  bounds:", s.bounds)
    except Exception as e:
        print(p, "-> could not open:", e)
import numpy as np, rasterio, geopandas as gpd, pyogrio
from pathlib import Path
from rasterio.transform import rowcol

src = rasterio.open("data/processed/detect_class_30m.tif"); cls, T, crs = src.read(1), src.transform, src.crs
hand = rasterio.open("data/processed/hand_30m.tif").read(1, masked=True).filled(np.nan)
names = {0: "floor_no_change", 1: "flood", 2: "dark", 3: "bright", 253: "above_floor", 254: "unobservable", 255: "no_data"}
for aoi in sorted(Path("data/external/EMSR927").glob("AOI*")):
    f = sorted(aoi.glob("*.gpkg"))[0]; lyr = next(l for l in pyogrio.list_layers(f)[:, 0] if l.startswith("builtUpP"))
    p = gpd.read_file(f, layer=lyr, engine="pyogrio").to_crs(crs)
    r, c = (np.array(v) for v in rowcol(T, p.geometry.x.values, p.geometry.y.values))
    ok = (r >= 0) & (r < cls.shape[0]) & (c >= 0) & (c < cls.shape[1]); r, c = r[ok], c[ok]
    v, n = np.unique(cls[r, c], return_counts=True)
    print(aoi.name, {names.get(int(a), int(a)): f"{b / len(r):.0%}" for a, b in zip(v, n)},
          "HAND p25/50/75 (m):", np.nanpercentile(hand[r, c], [25, 50, 75]).round(0))
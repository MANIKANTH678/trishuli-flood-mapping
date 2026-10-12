# tools/chip_windows.py 20260827 -> points_20260827.csv (name,lon,lat,stratum)
"""Step 11, Himalayan chips path 1 (reviewer's code). Picks chip windows by Sentinel-2 clear fraction and stratum ONLY,
never by predictions: no model output is read here.

Fixes to the reviewer's snippet (real bugs only):
  1. repo root on sys.path, so `python tools/chip_windows.py` can import src.analysis.changelib (it runs from tools/ otherwise);
  2. a header line `name,lon,lat,stratum` (tools/make_himalaya_chips.py skips the first line of a points file, so without
     a header the first window would be silently dropped), plus the stratum column it expects;
  3. name columns cast to str before joining (a non-string OSM tag would raise in str.join);
  4. a clear message instead of a rasterio error when no Trishuli / Bhote Koshi river line is in rivers.geojson.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, geopandas as gpd
from pyproj import Transformer
from rasterio.features import rasterize
from scipy import ndimage as ndi
from src.analysis.changelib import rd

date, W = sys.argv[1], 85                                          # 85 px x 30 m = 2.55 km, like the 256-px chips
clr, prof = rd(f"data/interim/s2/{date}/clear_30m.tif"); hand = rd("data/processed/hand_30m.tif")[0]; mask = rd("data/processed/radar_mask_30m.tif")[0]
T, crs = prof["transform"], prof["crs"]; mean = lambda a: ndi.uniform_filter(a.astype("float32"), W, mode="constant")
clear, floor, hill = mean(np.nan_to_num(clr)), mean((hand <= 30) & (mask == 0)), mean(hand >= 100)
rv = gpd.read_file("data/raw/osm/rivers.geojson").to_crs(crs); nm = rv.filter(like="name").fillna("").astype(str).agg(" ".join, axis=1)
stem = rv[nm.str.contains(r"trishuli|trisuli|bhote\s*koshi|bhotekoshi", case=False, regex=True)]
if stem.empty: sys.exit("chip_windows: no Trishuli / Bhote Koshi line in data/raw/osm/rivers.geojson")
dist = ndi.distance_transform_edt(rasterize(stem.geometry, out_shape=hand.shape, transform=T, all_touched=True) == 0) * 30
strata = {"main": (floor >= 0.3) & (dist <= 1500), "trib": (floor >= 0.3) & (dist >= 2500), "hill": hill >= 0.8}
rows, taken, tf = [], np.zeros(hand.shape, bool), Transformer.from_crs(crs, 4326, always_xy=True)
for k, n in {"main": 8, "trib": 8, "hill": 4}.items():
    score, got = np.where(strata[k] & (clear >= 0.7), clear, 0), 0
    for i in np.argsort(score, axis=None)[::-1]:
        r, c = np.unravel_index(i, score.shape)
        if score[r, c] <= 0 or got >= n: break
        if taken[max(r - W, 0):r + W, max(c - W, 0):c + W].any(): continue
        taken[r, c] = True; got += 1; lon, lat = tf.transform(*(T * (c + .5, r + .5))); rows.append(f"{k}_{got - 1:02d},{lon:.5f},{lat:.5f},{k}")
    print(k, f"{got}/{n} windows with clear >= 0.7")
open(f"points_{date}.csv", "w").write("\n".join(["name,lon,lat,stratum"] + rows) + "\n")

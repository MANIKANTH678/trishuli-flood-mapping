import json, os
import numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize

P = "data/processed/"
def rd(n):
    with rasterio.open(P + n) as s:
        return s.read(1, masked=True).astype("float32").filled(np.nan), s

pre, s = rd("s1_pre_VV_30m.tif"); post, _ = rd("s1_post_VV_30m.tif")
flood, _ = rd("flood_mask.tif")
d = post - pre
riv = gpd.read_file("data/raw/osm/rivers.geojson").to_crs(s.crs)
rm = rasterize(riv.geometry.buffer(60), out_shape=d.shape, transform=s.transform).astype(bool)

res = {}
def st(name, m):
    v = d[m & np.isfinite(d)]
    res[name] = dict(n=int(v.size), median=float(np.median(v)),
                     p5=float(np.percentile(v, 5)), p1=float(np.percentile(v, 1)))
    print(f"{name:22s}", res[name])

st("all", np.ones(d.shape, bool))
st("river_60m", rm)
st("flood_mask", np.nan_to_num(flood) > 0)
for sh in (50, -50):
    st(f"river_shifted_{sh*30}m", np.roll(rm, sh, axis=1))
rows = np.arange(d.shape[0])[:, None] * np.ones((1, d.shape[1]))
mid = d.shape[0] // 2
st("river_north_half", rm & (rows < mid))
st("river_south_half", rm & (rows >= mid))

os.makedirs("outputs/validation", exist_ok=True)
json.dump(res, open("outputs/validation/signal_check.json", "w"), indent=2)
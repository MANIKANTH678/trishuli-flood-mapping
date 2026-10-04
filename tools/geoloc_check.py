import argparse, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize

ap = argparse.ArgumentParser()
ap.add_argument("raster"); ap.add_argument("--rng", type=int, default=40)
ap.add_argument("--ll", help="W,S,E,N of a WIDE river reach (e.g. near Bidur)")
ap.add_argument("--rivers", default="data/raw/osm/rivers.geojson")
a = ap.parse_args()

with rasterio.open(a.raster) as src:
    vv = src.read(1, masked=True).filled(np.nan)
    T, crs, res = src.transform, src.crs, src.res[0]
riv = gpd.read_file(a.rivers)
if a.ll:
    w, s, e, n = map(float, a.ll.split(",")); riv = riv.cx[w:e, s:n]
rr, cc = np.nonzero(rasterize(riv.to_crs(crs).geometry.buffer(2 * res),
                              vv.shape, transform=T))
best = (np.inf, 0, 0)
for dy in range(-a.rng, a.rng + 1):
    for dx in range(-a.rng, a.rng + 1):
        r, c = rr - dy, cc - dx
        ok = (r >= 0) & (r < vv.shape[0]) & (c >= 0) & (c < vv.shape[1])
        v = vv[r[ok], c[ok]]; v = v[np.isfinite(v)]
        if v.size > 0.5 * rr.size and v.mean() < best[0]:
            best = (v.mean(), dy, dx)
print(f"best mean {best[0]:.2f} dB at ({best[1] * res:.0f} m, {best[2] * res:.0f} m)")

def mean_at(dy, dx):
    r, c = rr - dy, cc - dx
    ok = (r >= 0) & (r < vv.shape[0]) & (c >= 0) & (c < vv.shape[1])
    v = vv[r[ok], c[ok]]; v = v[np.isfinite(v)]
    return v.mean() if v.size else np.nan

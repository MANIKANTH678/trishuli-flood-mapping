import argparse, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize
from pysheds.grid import Grid

if not hasattr(np, "in1d"):
    np.in1d = lambda a, b, **k: np.isin(np.asarray(a).ravel(), b, **k)

ap = argparse.ArgumentParser()
ap.add_argument("--dem", default="data/processed/dem_30m.tif")
ap.add_argument("--rivers", default="data/raw/osm/rivers.geojson")
ap.add_argument("--chan-km2", type=float, default=2.0)
ap.add_argument("--out", default="data/processed/hand_30m.tif")
a = ap.parse_args()

grid = Grid.from_raster(a.dem); dem = grid.read_raster(a.dem)
dem = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
fdir = grid.flowdir(dem); acc = grid.accumulation(fdir)
with rasterio.open(a.dem) as src:
    prof, T, crs = src.profile, src.transform, src.crs
rv = gpd.read_file(a.rivers).to_crs(crs)
river = rasterize(rv.geometry, out_shape=acc.shape, transform=T, all_touched=True).astype(bool)
hand = grid.compute_hand(fdir, dem, (acc > a.chan_km2 * 1e6 / 900) | river)
h = np.asarray(hand, dtype="float32"); h = np.where(np.isfinite(h) & (h >= 0), h, -9999.0)
prof.update(dtype="float32", nodata=-9999.0, count=1, compress="deflate")
with rasterio.open(a.out, "w", **prof) as d: d.write(h.astype("float32"), 1)
ok = h > -9999
print(f"HAND<=15 m: {(h[ok] <= 15).mean():.1%}   <=30 m: {(h[ok] <= 30).mean():.1%}   <=60 m: {(h[ok] <= 60).mean():.1%}")
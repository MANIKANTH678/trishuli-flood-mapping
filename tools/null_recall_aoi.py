import json, os, glob, numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize

P = "data/processed/"
with rasterio.open(P + "flood_mask.tif") as s:
    m = s.read(1) > 0; T, crs = s.transform, s.crs
with rasterio.open(P + "dem_30m.tif") as s:
    dem = s.read(1, masked=True).filled(np.nan)
gy, gx = np.gradient(dem, 30, 30)
flat = np.degrees(np.arctan(np.hypot(gx, gy))) < 12
rng = np.random.default_rng(0)
res = {}
for a in ("AOI01", "AOI02", "AOI03", "AOI05"):
    aoi = gpd.read_file(glob.glob(f"data/external/EMSR927/{a}/*areaOfInterestA*.shp")[0]).to_crs(crs)
    am = rasterize(aoi.geometry, out_shape=m.shape, transform=T).astype(bool)
    pts = gpd.read_file(glob.glob(f"data/external/EMSR927/{a}/*builtUpP*.shp")[0]).to_crs(crs)
    pts = pts.geometry.representative_point()
    r, c = rasterio.transform.rowcol(T, pts.x.values, pts.y.values)
    r, c = np.array(r), np.array(c)
    ok = (r >= 0) & (r < m.shape[0]) & (c >= 0) & (c < m.shape[1]); r, c = r[ok], c[ok]
    k = int((m & am).sum()); cr, cc = np.nonzero(flat & am)
    obs = m[r, c].mean(); sims = []
    for _ in range(200):
        i = rng.choice(cr.size, min(k, cr.size), replace=False)
        rm = np.zeros_like(m); rm[cr[i], cc[i]] = True; sims.append(rm[r, c].mean())
    res[a] = dict(points=int(len(r)), mask_px=k, flat_px=int(cr.size),
                  observed=float(obs), null_mean=float(np.mean(sims)), null_sd=float(np.std(sims)))
    print(a, res[a])
os.makedirs("outputs/validation", exist_ok=True)
json.dump(res, open("outputs/validation/null_recall_aoi.json", "w"), indent=2)
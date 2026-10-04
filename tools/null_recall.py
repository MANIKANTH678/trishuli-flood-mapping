import numpy as np, rasterio, geopandas as gpd, glob
P = "data/processed/"
with rasterio.open(P + "flood_mask.tif") as s:
    m = s.read(1) > 0; T, crs = s.transform, s.crs
with rasterio.open(P + "dem_30m.tif") as s:
    dem = s.read(1, masked=True).filled(np.nan)
gy, gx = np.gradient(dem, 30, 30)
flat = np.degrees(np.arctan(np.hypot(gx, gy))) < 12
print("mask px", int(m.sum()), "| flat px", int(flat.sum()))

files = glob.glob("data/external/EMSR927/AOI*/*builtUpP*.shp")
print("damage files found:", len(files)); print("\n".join(files[:10]))
pts = []
for f in files:
    g = gpd.read_file(f).to_crs(crs)
    g = g[g.geometry.geom_type.isin(["Point", "Polygon", "MultiPolygon"])]
    pts.append(g.geometry.representative_point())
if pts:
    pts = gpd.GeoSeries(np.concatenate([p.values for p in pts]), crs=crs)
    r, c = rasterio.transform.rowcol(T, pts.x.values, pts.y.values)
    r, c = np.array(r), np.array(c)
    ok = (r >= 0) & (r < m.shape[0]) & (c >= 0) & (c < m.shape[1])
    r, c = r[ok], c[ok]
    obs = m[r, c].mean()
    rng = np.random.default_rng(0); fr, fc = np.nonzero(flat)
    sims = []
    for _ in range(200):
        idx = rng.choice(fr.size, m.sum(), replace=False)
        rm = np.zeros_like(m); rm[fr[idx], fc[idx]] = True
        sims.append(rm[r, c].mean())
    print(f"points {len(r)} | observed hit {obs:.3f} | random flat mask {np.mean(sims):.3f} +/- {np.std(sims):.3f}")
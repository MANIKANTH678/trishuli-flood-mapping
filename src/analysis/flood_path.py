#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np, rasterio, geopandas as gpd, pandas as pd, shapely
from pyproj import Transformer
from pysheds.grid import Grid
from rasterio.features import shapes
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from shapely.geometry import shape

if not hasattr(np, "in1d"): np.in1d = np.isin            # pysheds <= 0.4 calls np.in1d, removed in NumPy 2
D8 = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}   # pysheds default N,NE,E,SE,S,SW,W,NW

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="lon,lat of the upstream point")
    ap.add_argument("--dem", default="data/processed/dem_30m.tif"); ap.add_argument("--hand", default="data/processed/hand_30m.tif")
    ap.add_argument("--floor-m", type=float, default=30); ap.add_argument("--corridor-m", type=float, default=1500)
    ap.add_argument("--snap-m", type=float, default=600); ap.add_argument("--chan-km2", type=float, default=2.0); ap.add_argument("--out", default="outputs/flood_path")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    grid = Grid.from_raster(a.dem); dem = grid.read_raster(a.dem)
    fd = grid.flowdir(grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))); fdir, acc = np.asarray(fd), np.asarray(grid.accumulation(fd))
    with rasterio.open(a.dem) as s: T, crs, res = s.transform, s.crs, s.res[0]
    with rasterio.open(a.hand) as s: hand = s.read(1, masked=True).astype("float32").filled(np.nan)
    x, y = Transformer.from_crs(4326, crs, always_xy=True).transform(*map(float, a.start.split(",")))
    col0, row0 = (int(v) for v in np.floor(~T * (x, y))); k = int(a.snap_m / res)
    rr, cc = np.mgrid[max(row0 - k, 0):row0 + k + 1, max(col0 - k, 0):col0 + k + 1]
    rr, cc = np.clip(rr, 0, fdir.shape[0] - 1), np.clip(cc, 0, fdir.shape[1] - 1)
    chan = acc[rr, cc] >= a.chan_km2 * 1e6 / res ** 2
    if not chan.any(): raise SystemExit("no channel cell within the snap distance: move the point onto the river or raise --snap-m")
    i = np.argmin(np.where(chan, (rr - row0) ** 2 + (cc - col0) ** 2, np.inf)); r, c = int(rr.flat[i]), int(cc.flat[i])
    path, seen = [], set()
    while (r, c) not in seen and 0 <= r < fdir.shape[0] and 0 <= c < fdir.shape[1]:
        seen.add((r, c)); path.append((r, c)); d = D8.get(int(fdir[r, c]))
        if d is None: break
        r, c = r + d[0], c + d[1]
    P = np.array(path); chain = np.r_[0.0, np.cumsum(np.hypot(*np.diff(P, axis=0).T) * res)]
    on = np.zeros(fdir.shape, bool); on[P[:, 0], P[:, 1]] = True
    near_path = (hand <= a.floor_m) & (ndi.distance_transform_edt(~on) * res <= a.corridor_m)
    lab, _ = ndi.label(near_path); keep = np.isin(lab, np.unique(lab[on & near_path])) & (lab > 0)       # connected to the path only
    st = gpd.read_file("data/raw/osm/settlements.geojson").to_crs(crs); st = st[st.geometry.notna() & ~st.geometry.is_empty].reset_index(drop=True)
    xy = shapely.get_coordinates(shapely.centroid(st.geometry.to_numpy())); cl, rw = (np.floor(v).astype(int) for v in ~T * (xy[:, 0], xy[:, 1]))
    inb = (rw >= 0) & (rw < fdir.shape[0]) & (cl >= 0) & (cl < fdir.shape[1]); near = ndi.binary_dilation(keep, iterations=3)       # 90 m tolerance
    hit = np.zeros(len(st), bool); hit[inb] = near[rw[inb], cl[inb]]
    dpx, j = cKDTree(P).query(np.c_[rw, cl][hit])
    rows = pd.DataFrame({"name": st["name"].to_numpy()[hit] if "name" in st else "", "name_en": st["name:en"].to_numpy()[hit] if "name:en" in st else "", "km_downstream": (chain[j] / 1000).round(2),
                         "height_above_channel_m": np.round(hand[rw[hit], cl[hit]], 1), "distance_to_path_m": (dpx * res).round(0)}).sort_values("km_downstream")
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(*(T * (P[0, 1] + .5, P[0, 0] + .5)))
    line = gpd.GeoSeries([shapely.LineString([T * (c_ + .5, r_ + .5) for r_, c_ in path])], crs=crs).to_crs(4326)
    poly = gpd.GeoSeries([shapely.union_all([shape(g) for g, _ in shapes(keep.astype("uint8"), mask=keep, transform=T)])], crs=crs).to_crs(4326)
    line.to_file(out / "path.geojson", driver="GeoJSON"); poly.to_file(out / "corridor.geojson", driver="GeoJSON"); rows.to_csv(out / "settlements.csv", index=False)
    (out / "summary.json").write_text(json.dumps({"start_snapped_lonlat": [lon, lat], "path_km": round(float(chain[-1]) / 1000, 1), "n_settlements": int(len(rows)),
        "note": "D8 path on Copernicus GLO-30 + HAND floor; geometry only, no hydraulics or arrival times"}, indent=2)); print(rows.to_string(index=False))

if __name__ == "__main__":
    main()
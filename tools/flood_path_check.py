"""CHECK-ONLY sanity test for src/analysis/flood_path.py (never feeds back into the path).
1. How far the D8 path sits from the OSM river lines (median / 90th percentile, in pixels).
2. Distance along the path and offset of each EMSR927 AOI centroid (Syapru Besi, Timure, Bidur, Phosretar), so the
   downstream order can be read off. EMS is read here only to check geometry, never as an input.
python tools/flood_path_check.py --path-dir outputs/flood_path"""
import argparse, json
from pathlib import Path
import numpy as np, geopandas as gpd, pyogrio, shapely

NAMES = {"AOI01": "Syapru Besi", "AOI02": "Timure", "AOI03": "Bidur", "AOI05": "Phosretar"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path-dir", default="outputs/flood_path"); ap.add_argument("--rivers", default="data/raw/osm/rivers.geojson")
    ap.add_argument("--emsr-dir", default="data/external/EMSR927"); ap.add_argument("--crs", default="EPSG:32645"); ap.add_argument("--res", type=float, default=30)
    a = ap.parse_args(); d = Path(a.path_dir)
    path = gpd.read_file(d / "path.geojson").to_crs(a.crs).geometry.iloc[0]
    riv = shapely.union_all(gpd.read_file(a.rivers).to_crs(a.crs).geometry.to_numpy())
    pts = [path.interpolate(t) for t in np.arange(0, path.length, a.res)]
    dist = np.array([p.distance(riv) for p in pts]) / a.res
    res = {"path_vs_osm_river_px": {"median": round(float(np.median(dist)), 2), "p90": round(float(np.percentile(dist, 90)), 2),
                                    "share_within_2px": round(float((dist <= 2).mean()), 3)}, "ems_localities": []}
    for aoi in sorted(Path(a.emsr_dir).glob("AOI0*")):
        files = [*aoi.rglob("*.gpkg"), *aoi.rglob("*.shp")] if aoi.is_dir() else [aoi]
        hit = next(((f, n) for f in files for n in pyogrio.list_layers(f)[:, 0] if "areaOfInterestA" in str(n) or "areaOfInterestA" in f.name), None)
        if not hit: continue
        g = gpd.read_file(hit[0], layer=hit[1]).to_crs(a.crs); c = shapely.union_all(g.geometry.to_numpy()).centroid
        key = aoi.name[:5]
        res["ems_localities"].append({"aoi": key, "name": NAMES.get(key, key), "km_downstream": round(path.project(c) / 1000, 1),
                                      "offset_from_path_km": round(c.distance(path) / 1000, 2)})
    res["ems_localities"].sort(key=lambda r: r["km_downstream"])
    res["ems_order_downstream"] = [r["name"] for r in res["ems_localities"]]
    res["median_distance_to_osm_river_px"] = res["path_vs_osm_river_px"]["median"]
    exp = [n for n in ("Timure", "Syapru Besi", "Bidur", "Phosretar") if n in res["ems_order_downstream"]]   # upstream -> downstream
    res["order_ok"] = res["ems_order_downstream"] == exp
    st = gpd.read_file("data/raw/osm/settlements.geojson")
    names = " ".join(st[[c for c in st.columns if c.startswith("name") or c.startswith("alt_name")]].fillna("").astype(str).values.ravel()).lower()
    res["missing"] = [n for n in NAMES.values() if n.lower() not in names]       # EMS localities absent from the OSM settlement layer
    (d / "check.json").write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

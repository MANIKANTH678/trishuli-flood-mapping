"""CHECK-ONLY sanity test for src/analysis/flood_path.py (never feeds back into the path).
1. How far the D8 path sits from the OSM river lines (median / 90th percentile, in pixels).
2. Distance along the path and offset of each EMSR927 AOI centroid (Syapru Besi, Timure, Bidur, Phosretar), so the
   downstream order can be read off. EMS is read here only to check geometry, never as an input.
python tools/flood_path_check.py --path-dir outputs/flood_path"""
import argparse, json, re, sys
from pathlib import Path
import numpy as np, geopandas as gpd, pyogrio, shapely

NAMES = {"AOI01": "Syapru Besi", "AOI02": "Timure", "AOI03": "Bidur", "AOI05": "Phosretar"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path-dir", default="outputs/flood_path"); ap.add_argument("--rivers", default="data/raw/osm/rivers.geojson")
    ap.add_argument("--emsr-dir", default="data/external/EMSR927"); ap.add_argument("--crs", help="metric CRS (default: the CRS of data/processed/dem_30m.tif)"); ap.add_argument("--res", type=float, default=30)
    a = ap.parse_args(); d = Path(a.path_dir)
    if not a.crs:
        import rasterio
        with rasterio.open("data/processed/dem_30m.tif") as s_: a.crs = s_.crs.to_string()
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
    # EMS locality names vs the OSM settlement layer: name:en first (the local `name` is often Devanagari), then name / alt_name
    st = gpd.read_file("data/raw/osm/settlements.geojson")
    norm = lambda t: re.sub(r"[^a-z]", "", str(t).lower())
    cols = [c for c in ("name:en", "name", "int_name", "alt_name", "alt_name:en", "old_name") if c in st.columns]
    match = {}
    for n in NAMES.values():
        k = norm(n); match[n] = next((c for c in cols if any(k and k in norm(v) for v in st[c].dropna())), None)
    res["name_match"] = {n: (c or "absent") for n, c in match.items()}
    res["missing"] = [n for n, c in match.items() if c is None]                 # absent from every OSM name column
    res["missing_name_en"] = [n for n, c in match.items() if c != "name:en"]   # not found in name:en
    (d / "check.json").write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

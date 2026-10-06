#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np, geopandas as gpd, shapely
from src.analysis.impact_lib import *

TOLS = (30.0, 60.0)

def buildings(b, g, M):
    cls, T = M["cls"], M["T"]
    fl, db = mask_geom(M["flood"], T), mask_geom(M["debris"], T); both = shapely.union_all([fl, db])
    cen = shapely.centroid(g); st = sample(cls, T, shapely.get_x(cen), shapely.get_y(cen))
    domain = np.where(np.isin(st, ASSESSED), "assessed", np.where(st == 253, "not_assessed", "unobservable"))
    area = np.maximum(shapely.area(g), 1.0)
    f_fl, f_db, tier = np.zeros(len(g)), np.zeros(len(g)), np.full(len(g), "clear", dtype=object)
    if not both.is_empty:
        tree = shapely.STRtree(g)
        for tol, name in ((TOLS[1], "near60"), (TOLS[0], "near30"), (0.0, "overlap")):   # tightest tier written last
            tier[tree.query(both.buffer(tol) if tol else both, predicate="intersects")] = name
        ov = np.flatnonzero(tier == "overlap")
        f_fl[ov] = shapely.area(shapely.intersection(g[ov], fl)) / area[ov]
        f_db[ov] = shapely.area(shapely.intersection(g[ov], db)) / area[ov]
    tier = np.where(tier == "clear", np.where(domain == "assessed", "clear", domain), tier)
    cause = np.where(f_fl > 0, np.where(f_fl >= f_db, "flood", "debris"), np.where(f_db > 0, "debris", ""))
    n, ov = (lambda m: int(np.sum(m))), tier == "overlap"
    summ = {"total": len(g), "assessed": n(domain == "assessed"), "not_assessed": n(domain == "not_assessed"),
            "unobservable": n(domain == "unobservable"), "overlap": n(ov),
            "overlap_strong": n(ov & ((f_fl + f_db) >= 0.5)), "overlap_flood": n(ov & (cause == "flood")),
            "overlap_debris": n(ov & (cause == "debris")),
            "within_30m": n(np.isin(tier, ("overlap", "near30"))), "within_60m": n(np.isin(tier, ("overlap", "near30", "near60")))}
    hit = np.isin(tier, ("overlap", "near30", "near60"))
    keep = [c for c in ("osm_id", "building", "name") if c in b] + ["geometry"]
    aff = b.loc[hit, keep].assign(tier=tier[hit], overlap_frac=(f_fl + f_db)[hit].round(3), cause=cause[hit])
    return summ, aff

def roads_and_bridges(r, M):
    both = union_mask(M); g = r.geometry.to_numpy()
    br = (txt(r, "bridge") != "").to_numpy(); tun = (txt(r, "tunnel") != "").to_numpy()
    mot = r["motorable"].astype(bool).to_numpy() if "motorable" in r else np.ones(len(r), bool)
    tree, res, hit, Lhit = shapely.STRtree(g), {}, None, None
    for tol in (0.0, *TOLS):
        zone = both.buffer(tol) if tol else both
        idx = tree.query(zone, predicate="intersects"); idx = idx[~tun[idx]]
        L = shapely.length(shapely.intersection(g[idx], zone)); nb = ~br[idx]
        res[f"{int(tol)}m"] = {"roads": int(nb.sum()), "road_km": float(L[nb].sum() / 1000),
                               "motorable_road_km": float(L[nb & mot[idx]].sum() / 1000), "bridges": int(br[idx].sum())}
        if tol == 0: hit, Lhit = idx, L
    geo = gpd.GeoDataFrame(r.iloc[hit].drop(columns="geometry").assign(affected_m=Lhit.round(1), is_bridge=br[hit]),
                           geometry=shapely.intersection(g[hit], both), crs=r.crs)
    tot = {"roads_total": int((~br & ~tun).sum()), "bridges_total": int(br.sum()),
           "road_km_total": float(shapely.length(g[~br & ~tun]).sum() / 1000)}
    return res, geo, tot

def read_osm(name, crs):
    d = gpd.read_file(OSM / f"{name}.geojson").to_crs(crs)
    return d[d.geometry.notna() & ~d.geometry.is_empty].reset_index(drop=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="data/processed/fused_class_30m.tif"); ap.add_argument("--morph", type=int, default=0)
    ap.add_argument("--sens-dir", default="data/processed/_sens"); ap.add_argument("--out-dir", default="outputs")
    a = ap.parse_args(); out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    M = load_classes(a.cls, a.morph); crs = M["crs"]
    b, r = read_osm("buildings", crs), read_osm("roads", crs); g = shapely.make_valid(b.geometry.to_numpy())
    bs, baff = buildings(b, g, M); rs, raff, rt = roads_and_bridges(r, M)
    if len(baff): baff.to_file(out / "affected_buildings.gpkg", driver="GPKG")
    for name, part in (("affected_roads", raff[~raff["is_bridge"]]), ("affected_bridges", raff[raff["is_bridge"]])):
        if len(part): part.to_file(out / f"{name}.geojson", driver="GeoJSON")
    sens = {}                                         # threshold sensitivity (masks from tools/make_sens_masks.py)
    for nm in ("low", "base", "high"):
        p = a.cls if nm == "base" else Path(a.sens_dir) / nm / "fused_class_30m.tif"
        if not Path(p).exists(): continue
        Ms = M if nm == "base" else load_classes(str(p), a.morph)
        s_b, _ = buildings(b, g, Ms); s_r, _, _ = roads_and_bridges(r, Ms)
        sens[nm] = {"buildings_overlap": s_b["overlap"], "buildings_within_30m": s_b["within_30m"],
                    "buildings_within_60m": s_b["within_60m"], "motorable_road_km": round(s_r["0m"]["motorable_road_km"], 2),
                    "bridges_exposed": s_r["0m"]["bridges"]}
    rng = {k: [min(v[k] for v in sens.values()), max(v[k] for v in sens.values())] for k in next(iter(sens.values()))} if sens else {}
    mf = OSM / "manifest.json"
    summary = {"total_buildings": bs["total"], "flooded_buildings": bs["overlap_flood"], "debris_buildings": bs["overlap_debris"],
               "total_roads": rt["roads_total"], "flooded_roads": rs["0m"]["roads"],
               "total_bridges": rt["bridges_total"], "flooded_bridges": rs["0m"]["bridges"],   # legacy keys kept
               "buildings": bs, "roads_bridges": {"exposure_by_tolerance": rs, **rt},
               "sensitivity": {"scenarios": sens, "range": rng}, "class_raster": a.cls, "morph_px": a.morph,
               "osm_snapshot": json.loads(mf.read_text()).get("snapshot") if mf.exists() else None,
               "note": "Exposure = footprint/segment overlaps the detected mask. Bridges are exposed, not failed. "
                       "Only classes 0-3 are assessed; not_assessed / unobservable are UNKNOWN, not clear."}
    (out / "impact_summary.json").write_text(json.dumps(summary, indent=2)); print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
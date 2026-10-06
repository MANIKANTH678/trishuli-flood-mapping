#!/usr/bin/env python3
"""CHECK-ONLY validation of the fused class raster against EMSR927. EMS data never feeds a mask, threshold or product number."""
import argparse, json, re
from pathlib import Path
import numpy as np, geopandas as gpd, pyogrio, rasterio, shapely
from rasterio.features import rasterize
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from src.analysis.impact_lib import ASSESSED, OSM, sample

TOLS, GRADES = (0, 30, 60, 100), ("Destroyed", "Damaged", "Possibly damaged")

def ver(h):
    m = re.search(r"_v(\d+)", h[1]) or re.search(r"_v(\d+)", h[0].stem)
    return int(m[1]) if m else 0

def pick(items, token, log):
    """Latest-version layer whose name contains token; None (and a log line) if absent. Never falls back to another layer."""
    hits = [h for h in items if token.lower() in h[1].lower()]
    if not hits: log.append(f"missing layer {token}"); return None
    best = max(hits, key=ver)
    log.append(f"{token}: {best[1]} [{best[0].name}]" + (f" (other versions: {[h[1] for h in hits if h is not best]})" if len(hits) > 1 else ""))
    return best

def read(h, crs): return gpd.read_file(h[0], layer=h[1], engine="pyogrio").to_crs(crs)

def seg_metrics(pred, ref, region):
    tp, fp, fn = (int((x & y & region).sum()) for x, y in ((pred, ref), (pred, ~ref), (~pred, ref)))
    f = lambda n, d: n / d if d else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": f(tp, tp + fp), "recall": f(tp, tp + fn),
            "iou": f(tp, tp + fp + fn), "f1": f(2 * tp, 2 * tp + fp + fn)}

def tol_metrics(pred, ref, region, dpred, dref, tol):
    p, r = pred & region, ref & region
    return {"precision": float((p & (dref <= tol)).sum() / p.sum()) if p.any() else None,
            "recall": float((r & (dpred <= tol)).sum() / r.sum()) if r.any() else None}

def boot(h, blk, n=2000):
    """95% CI of a hit rate, resampling 1 km blocks (points are spatially clustered)."""
    u, inv = np.unique(blk, return_inverse=True)
    if len(u) < 2: return [None, None]
    s, c = np.bincount(inv, weights=h.astype(float)), np.bincount(inv)
    m = np.random.default_rng(0).integers(0, len(u), (n, len(u))); m = s[m].sum(1) / c[m].sum(1)
    return [round(float(np.percentile(m, 2.5)), 4), round(float(np.percentile(m, 97.5)), 4)]

def null_hits(flag, region, r, c, res, n=100):
    """Chance level that keeps blob structure: relocate each connected blob of the mask to a random assessed pixel."""
    rng = np.random.default_rng(1); lab, _ = ndi.label(flag & region)
    blobs = [np.argwhere(lab[o] == i + 1) + [o[0].start, o[1].start] for i, o in enumerate(ndi.find_objects(lab))]
    cand, out = np.argwhere(region), {t: [] for t in TOLS}
    if not blobs or not len(cand): return None
    for _ in range(n):
        m = np.zeros(flag.shape, bool)
        for px in blobs:
            q = px + (cand[rng.integers(len(cand))] - px.mean(0).astype(int))
            ok = (q[:, 0] >= 0) & (q[:, 0] < m.shape[0]) & (q[:, 1] >= 0) & (q[:, 1] < m.shape[1])
            m[q[ok, 0], q[ok, 1]] = True
        d = ndi.distance_transform_edt(~m) * res
        for t in TOLS: out[t].append(float((d[r, c] <= t).mean()))
    return {str(t): [float(np.mean(v)), float(np.std(v))] for t, v in out.items()}

def verdict(ci, null):
    if null is None or ci[0] is None: return "n/a"
    mu, sd = null
    return "above chance" if ci[0] > mu + 2 * sd else "below chance" if ci[1] < mu - 2 * sd else "indistinguishable from chance"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="data/processed/fused_class_30m.tif"); ap.add_argument("--emsr-dir", default="data/external/EMSR927")
    ap.add_argument("--bld", default="outputs/affected_buildings.gpkg"); ap.add_argument("--holdout", default="AOI03")
    ap.add_argument("--out", default="outputs/validation/emsr927_validation.json")
    a = ap.parse_args()
    with rasterio.open(a.cls) as s: cls, T, crs, res = s.read(1), s.transform, s.crs, s.res[0]
    masks = {"debris": np.isin(cls, (2, 3)), "flood_or_debris": np.isin(cls, (1, 2, 3))}
    flag, assessed = masks["flood_or_debris"], np.isin(cls, ASSESSED)
    dist = {k: ndi.distance_transform_edt(~m) * res for k, m in masks.items()}
    def cen(g):
        c = shapely.centroid(shapely.make_valid(g.geometry.to_numpy())); return np.c_[shapely.get_x(c), shapely.get_y(c)]
    allb = gpd.read_file(OSM / "buildings.geojson").to_crs(crs); allb = allb[allb.geometry.notna() & ~allb.geometry.is_empty]
    bxy = cen(allb); b_ok = np.isin(sample(cls, T, bxy[:, 0], bxy[:, 1]), ASSESSED)
    fb = None
    if Path(a.bld).exists():
        fb = gpd.read_file(a.bld).to_crs(crs); fb = fb[fb.geometry.notna() & ~fb.geometry.is_empty]; fxy, ftier = cen(fb), fb["tier"].to_numpy()

    out, pool = {}, {}
    for d in sorted(Path(a.emsr_dir).glob("AOI*")):
        log = []; rec = {"layers": log, "holdout": d.name == a.holdout}; out[d.name] = rec
        items = [(f, str(n)) for f in sorted([*d.rglob("*.gpkg"), *d.rglob("*.shp")]) for n in pyogrio.list_layers(f)[:, 0]]
        h_aoi, h_na, h_ev, h_pt = (pick(items, t, log) for t in ("areaOfInterestA", "notAnalysedA", "observedEventA", "builtUpP"))
        if h_aoi is None: rec["error"] = "no areaOfInterestA layer: AOI skipped"; continue
        valid_g = shapely.union_all(read(h_aoi, crs).geometry.to_numpy())
        if h_na: valid_g = valid_g.difference(shapely.union_all(read(h_na, crs).geometry.to_numpy()))
        if valid_g.is_empty: rec["error"] = "AOI minus notAnalysedA is empty"; continue
        vm = rasterize([(valid_g, 1)], out_shape=cls.shape, transform=T).astype(bool)
        region = {"all": vm, "assessed": vm & assessed}

        if h_ev:
            ev = read(h_ev, crs); geoms = [g for g in ev.geometry if g is not None and not g.is_empty]
            ref = rasterize([(g, 1) for g in geoms], out_shape=cls.shape, transform=T).astype(bool) if geoms else np.zeros(cls.shape, bool)
            dref = ndi.distance_transform_edt(~ref) * res
            rec["event_area"] = {"ref_px_all": int((ref & vm).sum()), "ref_px_assessed": int((ref & region["assessed"]).sum()),
                **{nm: {dom: {"strict": seg_metrics(m, ref, rg),
                              "tolerance": {str(t): tol_metrics(m, ref, rg, dist[nm], dref, t) for t in TOLS[1:]}}
                        for dom, rg in region.items()} for nm, m in masks.items()}}
            for nm in masks:
                g = pool.setdefault("holdout" if rec["holdout"] else "non_holdout", {}).setdefault(nm, {"tp": 0, "fp": 0, "fn": 0})
                for k in g: g[k] += rec["event_area"][nm]["assessed"]["strict"][k]

        if h_pt:
            p = read(h_pt, crs); p = p[p.geometry.notna() & p.geometry.within(valid_g)].reset_index(drop=True)
            rp = p.geometry.representative_point(); pxy = np.c_[rp.x.to_numpy(), rp.y.to_numpy()]
            cc, rr = ~T * (pxy[:, 0], pxy[:, 1]); rr, cc = np.floor(rr).astype(int), np.floor(cc).astype(int)
            ok = (rr >= 0) & (rr < cls.shape[0]) & (cc >= 0) & (cc < cls.shape[1])
            p, pxy, rr, cc = p[ok].reset_index(drop=True), pxy[ok], rr[ok], cc[ok]
            asm = assessed[rr, cc]; blk = (pxy[:, 0] // 1000).astype(np.int64) * 100000 + (pxy[:, 1] // 1000).astype(np.int64)
            hit = {t: dist["flood_or_debris"][rr, cc] <= t for t in TOLS}
            null = null_hits(flag, region["assessed"], rr[asm], cc[asm], res) if asm.any() else None
            grade = p["damage_gra"].astype(str).to_numpy() if "damage_gra" in p else np.array([""] * len(p))
            rec["damage_points"] = {"n": int(len(rr)), "n_assessed": int(asm.sum()),
                "recall_all": {str(t): float(hit[t].mean()) if len(rr) else None for t in TOLS},
                "recall_assessed": {str(t): ({"rate": float(hit[t][asm].mean()), "ci95": (ci := boot(hit[t][asm], blk[asm])),
                                              "chance_mean_sd": null[str(t)] if null else None,
                                              "verdict": verdict(ci, null[str(t)] if null else None)} if asm.any() else None) for t in TOLS},
                "by_grade_assessed_30m": {g: {"n": int((asm & (grade == g)).sum()),
                                              "rate": float(hit[30][asm & (grade == g)].mean()) if (asm & (grade == g)).any() else None} for g in GRADES}}
            if fb is not None and len(pxy):
                kd = cKDTree(pxy); inside = lambda xy: shapely.contains_xy(valid_g, xy[:, 0], xy[:, 1])
                def share(xy):
                    if not len(xy): return None
                    dd, _ = kd.query(xy); return {"n": int(len(xy)), **{str(t): float((dd <= t).mean()) for t in (30, 60, 100)}}
                rec["building_precision_proxy"] = {
                    "baseline_all_assessed_buildings": share(bxy[b_ok & inside(bxy)]),
                    "flagged_overlap": share(fxy[(ftier == "overlap") & inside(fxy)]),
                    "flagged_within_30m": share(fxy[np.isin(ftier, ("overlap", "near30")) & inside(fxy)]),
                    "note": "lower bound: EMS marks only what analysts graded; compare with the baseline, not with 100%"}
    for grp in pool.values():
        for g in grp.values():
            tp, fp, fn = g["tp"], g["fp"], g["fn"]
            g.update(precision=tp / (tp + fp) if tp + fp else None, recall=tp / (tp + fn) if tp + fn else None,
                     iou=tp / (tp + fp + fn) if tp + fp + fn else None)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"aois": out, "pooled_assessed_domain": pool}, indent=2)); print(json.dumps({"pooled": pool}, indent=2))

if __name__ == "__main__":
    main()
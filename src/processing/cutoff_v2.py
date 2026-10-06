#!/usr/bin/env python3
import argparse, json
from collections import Counter
from pathlib import Path
import networkx as nx, numpy as np, pandas as pd, geopandas as gpd, shapely
from scipy.spatial import cKDTree
from src.analysis.impact_lib import *

SEG_M, SNAP_M = 30.0, 1000.0
DEGRADED_RATIO, DEGRADED_ABS_M = 2.0, 2000.0
SRC = ("SRC",)

def classify(pre_m, post_m):
    if pre_m is None: return "no_pre_flood_path", None
    if post_m is None: return "cut_off", None
    ratio = post_m / max(pre_m, 1.0)
    return ("degraded" if ratio >= DEGRADED_RATIO and post_m - pre_m >= DEGRADED_ABS_M else "reachable"), ratio

def reach(G, dest_nodes):
    """(pred, dist) to the nearest destination via a zero-weight super-source (added then removed)."""
    if not dest_nodes: return {}, {}
    G.add_edges_from((SRC, d, {"w": 0.0, "e": -1}) for d in dest_nodes)
    pred, dist = nx.dijkstra_predecessor_and_distance(G, SRC, weight="w")
    G.remove_node(SRC)
    return pred, dist

def walk(pred, G, node):
    """Edge ids along the pre-flood route from node to its destination."""
    steps = []
    while pred.get(node) and pred[node][0] != SRC:
        p = pred[node][0]; steps.append(G[node][p]["e"]); node = p
    return steps

def snap(xy, kd, n, radius):
    d, i = kd.query(xy, distance_upper_bound=radius)
    return np.where(np.isfinite(d) & (i < n), i, -1), d

def load_network(crs):
    r = gpd.read_file(OSM / "roads.geojson").to_crs(crs)
    r = r[r.geometry.notna() & ~r.geometry.is_empty].explode(index_parts=False).reset_index(drop=True)
    mot = r["motorable"].astype(bool) if "motorable" in r else ~txt(r, "highway").isin(NON_MOTORABLE)
    r = r[mot.to_numpy()].reset_index(drop=True)
    xy, gi = shapely.get_coordinates(shapely.segmentize(r.geometry.to_numpy(), SEG_M), return_index=True)
    same = gi[1:] == gi[:-1]
    A, B, way = xy[:-1][same], xy[1:][same], gi[:-1][same]
    w = np.hypot(*(A - B).T); k = w > 0; A, B, way, w = A[k], B[k], way[k], w[k]
    ua, ub = list(map(tuple, np.round(A, 2))), list(map(tuple, np.round(B, 2)))
    G = nx.Graph(); G.add_edges_from((u, v, {"w": float(x), "e": i}) for i, (u, v, x) in enumerate(zip(ua, ub, w)))
    return {"G": G, "A": A, "B": B, "W": w, "ua": ua, "ub": ub,
            "bridge": (txt(r, "bridge") != "").to_numpy()[way], "tunnel": (txt(r, "tunnel") != "").to_numpy()[way],
            "lines": shapely.linestrings(np.stack([A, B], axis=1))}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="data/processed/fused_class_30m.tif")
    ap.add_argument("--sens-dir", default="data/processed/_sens"); ap.add_argument("--out", default="outputs/cutoff_settlements.json")
    a = ap.parse_args()
    base = load_classes(a.cls); crs, T = base["crs"], base["T"]
    N = load_network(crs); G = N["G"]; nodes = list(G.nodes); kd = cKDTree(np.array(nodes))
    big = len(max(nx.connected_components(G), key=len)) / G.number_of_nodes()
    print(f"network: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges, largest component {big:.0%}")

    def read(name):
        d = gpd.read_file(OSM / f"{name}.geojson").to_crs(crs)
        return d[d.geometry.notna() & ~d.geometry.is_empty].reset_index(drop=True)
    hos, setl = read("hospitals"), read("settlements")
    centre = lambda d: shapely.get_coordinates(shapely.centroid(d.geometry.to_numpy()))
    sxy, hxy = centre(setl), centre(hos)
    s_i, s_d = snap(sxy, kd, len(nodes), SNAP_M); h_i, _ = snap(hxy, kd, len(nodes), SNAP_M)     # snapped ONCE
    place = txt(setl, "place").to_numpy(); is_town = np.isin(place, ("city", "town"))
    dests = {"hospital": sorted({nodes[i] for i in h_i if i >= 0}), "town": sorted({nodes[i] for i in s_i[is_town] if i >= 0})}
    PRE = {k: reach(G, d) for k, d in dests.items()}
    mid = (N["A"] + N["B"]) / 2
    assessed = np.isin(sample(base["cls"], T, mid[:, 0], mid[:, 1]), ASSESSED)
    etree = shapely.STRtree(N["lines"])

    def blocked(both, policy):
        if both.is_empty: return np.array([], dtype=int)
        idx = etree.query(both, predicate="intersects"); idx = idx[~N["tunnel"][idx]]
        return idx[~N["bridge"][idx]] if policy == "survive" else idx
    def run(removed):
        H = G.copy(); H.remove_edges_from([(N["ua"][i], N["ub"][i]) for i in removed])
        return {k: reach(H, d) for k, d in dests.items()}
    def statuses(post):
        out = {}
        for k in dests:
            dpre, dpost, rows_ = PRE[k][1], post[k][1], []
            for j in range(len(setl)):
                if k == "town" and is_town[j]: rows_.append(("is_town", None, None, None)); continue
                n = nodes[s_i[j]] if s_i[j] >= 0 else None
                pm, qm = (dpre.get(n), dpost.get(n)) if n is not None else (None, None)
                lab, ratio = classify(pm, qm); rows_.append((lab, ratio, pm, qm))
            out[k] = rows_
        return out

    paths = {"base": a.cls}
    for nm in ("low", "high"):
        p = Path(a.sens_dir) / nm / "fused_class_30m.tif"
        if p.exists(): paths[nm] = str(p)
    rows = []
    for nm in ("low", "base", "high"):
        if nm not in paths: continue
        for morph in (-1, 0, 1):
            Mx = load_classes(paths[nm], morph); both = union_mask(Mx)
            for pol in ("fail", "survive"):
                st = statuses(run(blocked(both, pol)))
                rows.append({"thr": nm, "morph": morph, "bridges": pol,
                             **{f"{k}_{lab}": c for k in dests for lab, c in Counter(x[0] for x in st[k]).items()}})
    df = pd.DataFrame(rows).fillna(0)
    rng = {c: [int(df[c].min()), int(df[c].max())] for c in df.columns if c.endswith(("_cut_off", "_degraded"))}

    both0 = union_mask(base); removed0 = blocked(both0, "fail"); st0 = statuses(run(removed0))   # headline scenario
    rem = set(removed0.tolist()); fl_set = set(etree.query(mask_geom(base["flood"], T), predicate="intersects").tolist())
    lon, lat = to_lonlat(crs, sxy[:, 0], sxy[:, 1])
    nm_col = setl["name"].fillna("").astype(str).to_numpy() if "name" in setl else np.array([""] * len(setl))
    recs = []
    for j in range(len(setl)):
        rec = {"name": nm_col[j] or f"settlement_{j}", "lat": float(lat[j]), "lon": float(lon[j]), "place": place[j] or None,
               "snap_dist_m": round(float(s_d[j]), 1) if s_i[j] >= 0 else None}
        for k in dests:
            lab, ratio, pm, qm = st0[k][j]
            rec[k] = {"status": lab, "pre_km": round(pm / 1000, 2) if pm is not None else None,
                      "post_km": round(qm / 1000, 2) if qm is not None else None,
                      "detour_factor": round(ratio, 2) if ratio is not None else None}
        lab, _, pm, _ = st0["hospital"][j]
        rec["pre_detail"] = ("off_network" if s_i[j] < 0 else "disconnected") if lab == "no_pre_flood_path" else None
        steps = walk(PRE["hospital"][0], G, nodes[s_i[j]]) if (s_i[j] >= 0 and pm is not None) else []
        rec["route_assessed_frac"] = round(float(N["W"][steps][assessed[steps]].sum() / N["W"][steps].sum()), 2) if steps else None
        brk = next((e for e in steps if e in rem), None) if lab in ("cut_off", "degraded") else None
        if brk is not None:
            blon, blat = to_lonlat(crs, mid[brk, 0], mid[brk, 1])
            rec["first_break"] = {"lat": float(blat), "lon": float(blon), "cause": "flood" if brk in fl_set else "debris",
                                  "bridge": bool(N["bridge"][brk])}
        else: rec["first_break"] = None
        recs.append(rec)
    cnt = {k: Counter(x[0] for x in st0[k]) for k in dests}
    mf = OSM / "manifest.json"
    result = {"metadata": {"class_raster": a.cls, "osm_snapshot": json.loads(mf.read_text()).get("snapshot") if mf.exists() else None,
                           "snap_radius_m": SNAP_M, "segment_m": SEG_M,
                           "degraded_rule": f">= {DEGRADED_RATIO:g}x and >= {DEGRADED_ABS_M / 1000:g} km longer",
                           "headline_scenario": "base threshold, mask +-0 px, exposed bridges fail",
                           "scenario_axes": "threshold low/base/high x mask -1/0/+1 px x bridges fail/survive",
                           "limitations": ["Only valley-floor change is detected: blockages on hillside roads are not seen (route_assessed_frac).",
                                           "OSM motorable ways at the snapshot date; missing roads show as no_pre_flood_path; distances are ground lengths, not travel times.",
                                           "Bridges are exposed, not known to have failed.",
                                           "EMSR927 contains no cut-off ground truth; the scenario range is the uncertainty we can quantify."]},
              "summary": {"total_settlements": len(recs), "hospitals_total": len(hos), "hospitals_snapped": int((h_i >= 0).sum()),
                          "hospital_nodes": len(dests["hospital"]),
                          "towns_as_destinations": len(dests["town"]),
                          **{f"{k}_{lab}": c for k in dests for lab, c in cnt[k].items()},
                          "cut_off": cnt["hospital"]["cut_off"], "cut_off_no_path": cnt["hospital"]["cut_off"],
                          "cut_off_detour_only": cnt["hospital"]["degraded"],      # legacy keys, new meanings
                          "reachable_pre": sum(1 for r_ in st0["hospital"] if r_[2] is not None),
                          "network_largest_component": round(big, 3)},
              "sensitivity": {"scenarios": rows, "range": rng}, "settlements": recs}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(result, indent=2))
    print(json.dumps({"summary": result["summary"], "range": rng}, indent=2))

if __name__ == "__main__":
    main()
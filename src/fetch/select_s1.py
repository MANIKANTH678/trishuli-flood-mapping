#!/usr/bin/env python3
"""Step 10.2: pick the Sentinel-1 scenes for a run. One relative orbit and pass: the nearest post-event date,
at least 3 pre-event dates (up to 4) and >= 90% bbox coverage on every chosen date. Fails loudly otherwise and
records every candidate track in the output JSON.

    python -m src.fetch.select_s1 --bbox W,S,E,N --event-date YYYY-MM-DD                  # CDSE catalogue (GRD), no login
    python -m src.fetch.select_s1 --bbox W,S,E,N --event-date YYYY-MM-DD --source pc      # Planetary Computer sentinel-1-rtc, no login

Writes data/raw/sentinel1/selection.json (the folder the rest of the pipeline reads; the review draft used data/raw/s1)."""
import argparse, json, re, sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import requests, shapely
from shapely.geometry import box, shape

ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEFAULT_OUT = "data/raw/sentinel1/selection.json"


def choose(dates_by_track, event, n_pre=4, min_cov=0.9, max_pre_days=120, max_post_days=45):
    """dates_by_track: {(orbit, pass): {date: coverage}} -> best track. Prefers >= 3 refs, then the closest post scene."""
    ranked = []
    for tr, d in dates_by_track.items():
        ok = {k: v for k, v in d.items() if v >= min_cov}
        post = sorted(k for k in ok if 0 < (k - event).days <= max_post_days)
        pre = sorted((k for k in ok if 0 < (event - k).days <= max_pre_days), reverse=True)[:n_pre]
        if post and pre: ranked.append(((len(pre) >= 3, -(post[0] - event).days, len(pre)), tr, post[0], pre))
    if not ranked:
        raise ValueError(f"no relative orbit has both a post-event and a pre-event scene covering >= {min_cov:.0%} of the bbox")
    _, tr, post, pre = max(ranked, key=lambda r: r[0])
    return {"rel_orbit": tr[0], "pass": tr[1], "post": post, "pre": pre}


def search(bb, start, end):
    w, s, e, n = bb
    flt = ("Collection/Name eq 'SENTINEL-1' and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' and att/OData.CSC.StringAttribute/Value eq 'IW_GRDH_1S')"
           f" and ContentDate/Start gt {start}T00:00:00.000Z and ContentDate/Start lt {end}T23:59:59.999Z"
           f" and OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))')")
    params, url, out = {"$filter": flt, "$expand": "Attributes", "$top": 200, "$orderby": "ContentDate/Start asc"}, ODATA, []
    while url:
        r = requests.get(url, params=params if url == ODATA else None, timeout=90); r.raise_for_status()
        j = r.json(); out += j.get("value", []); url = j.get("@odata.nextLink")
    return out


def footprint(p):
    if p.get("GeoFootprint"): return shape(p["GeoFootprint"])
    m = re.search(r"(MULTIPOLYGON|POLYGON)\s*\(.*\)", p.get("Footprint", ""))
    return shapely.from_wkt(m.group(0)) if m else None


def frames_cdse(bb, ev):
    frames = defaultdict(lambda: defaultdict(list))
    for p in search(bb, ev - timedelta(days=120), ev + timedelta(days=45)):
        at = {x["Name"]: x.get("Value") for x in p.get("Attributes", []) if x.get("Name")}; ch, g = str(at.get("polarisationChannels", "")), footprint(p)
        if "VV" in ch and "VH" in ch and g is not None:
            rec = {"id": p["Id"], "name": p["Name"], "size_mb": round(p.get("ContentLength", 0) / 1e6)}
            frames[(int(at.get("relativeOrbitNumber", -1)), str(at.get("orbitDirection", "?")).upper())][date.fromisoformat(p["ContentDate"]["Start"][:10])].append((rec, g))
    return frames


def frames_pc(bb, ev, collection="sentinel-1-rtc"):
    """Same grouping from the Planetary Computer STAC (no login). Item ids stand in for product names."""
    import pystac_client
    cat = pystac_client.Client.open(PC_STAC)
    frames = defaultdict(lambda: defaultdict(list))
    rng = f"{ev - timedelta(days=120)}/{ev + timedelta(days=45)}"
    for it in cat.search(collections=[collection], bbox=list(bb), datetime=rng, limit=200).items():
        pr = it.properties; pols = [p.upper() for p in pr.get("sar:polarizations", [])]
        if "VV" not in pols or "VH" not in pols or pr.get("sat:relative_orbit") is None: continue
        d = date.fromisoformat(str(pr.get("start_datetime") or pr["datetime"])[:10])
        rec = {"id": it.id, "name": it.id, "size_mb": 0, "collection": collection}
        frames[(int(pr["sat:relative_orbit"]), str(pr.get("sat:orbit_state", "?")).upper())][d].append((rec, shape(it.geometry)))
    return frames


def select(bbox, event_date, n_pre=4, min_cov=0.9, source="cdse"):
    ev, bb = date.fromisoformat(event_date), tuple(map(float, bbox.split(","))) if isinstance(bbox, str) else tuple(bbox)
    bx = box(*bb)
    frames = frames_pc(bb, ev) if source == "pc" else frames_cdse(bb, ev)
    cov = {tr: {d: shapely.union_all([g for _, g in fs]).intersection(bx).area / bx.area for d, fs in ds.items()} for tr, ds in frames.items()}
    cands = [{"rel_orbit": k[0], "pass": k[1], "dates_ok": sorted(str(d) for d, c in v.items() if c >= min_cov),
              "dates_low_cov": {str(d): round(c, 2) for d, c in sorted(v.items()) if c < min_cov}} for k, v in cov.items()]
    try:
        sel = choose(cov, ev, n_pre, min_cov)
    except ValueError as e:
        raise ValueError(f"{e}\ncandidates: {json.dumps(cands)}") from None
    tr, keep = (sel["rel_orbit"], sel["pass"]), [sel["post"], *sel["pre"]]
    return {"event": str(ev), "bbox": ",".join(map(str, bb)), "source": source, "rel_orbit": sel["rel_orbit"], "pass": sel["pass"],
            "post": str(sel["post"]), "pre": [str(d) for d in sel["pre"]],
            "n_refs": len(sel["pre"]), "calibrated_possible": len(sel["pre"]) >= 3,
            "coverage": {str(d): round(cov[tr][d], 3) for d in keep},
            "products": {str(d): [p for p, _ in frames[tr][d]] for d in keep}, "candidates": cands}


def add_guards(out):
    """Step 11: time-of-day and platform guards (same rule as check_stack.py), recorded in selection.json."""
    from src.processing.stack_guards import stack_warnings
    out["acquisitions"], out["warnings"] = stack_warnings(out["products"])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bbox", required=True); ap.add_argument("--event-date", required=True)
    ap.add_argument("--n-pre", type=int, default=4); ap.add_argument("--min-cov", type=float, default=0.9)
    ap.add_argument("--source", choices=["cdse", "pc"], default="cdse"); ap.add_argument("--out", default=DEFAULT_OUT); a = ap.parse_args()
    try: out = select(a.bbox, a.event_date, a.n_pre, a.min_cov, a.source)
    except ValueError as e: sys.exit(f"select_s1: {e}")
    add_guards(out)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(out, indent=2))
    gb = sum(p["size_mb"] for v in out["products"].values() for p in v) / 1000
    print(f"track {out['rel_orbit']} {out['pass']}: post {out['post']}, pre {out['pre']}"
          + (f"; download ~{gb:.1f} GB" if a.source == "cdse" else " (PC: streamed, nothing to download)"))
    for w in out["warnings"]: print(w)
    if out["n_refs"] < 3: print("WARNING: fewer than 3 reference dates: no null calibration, the detector result will be UNCALIBRATED")


if __name__ == "__main__":
    main()

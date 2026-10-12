#!/usr/bin/env python3
"""Pre-event OSM layers from a DATED Geofabrik extract (no API key). Fallback for fetch_osm when OHSOME_API_KEY is not
set (clean clones, Kaggle, judging day). Same six layers and the same columns the downstream stages read as the ohsome
route; the snapshot is the extract's date, which must be strictly before the event (and by default <= event - 30 d).

    python -m src.download.osm_geofabrik --bbox W,S,E,N --event-date YYYY-MM-DD [--region asia/nepal] [--out data/raw/osm]

Geofabrik keeps dated extracts (e.g. asia/nepal-260701.osm.pbf = data as of 2026-07-01). The newest extract dated on or
before the snapshot date is used. Only the region's extract is read: a bbox that crosses the region border (e.g. the
Terai box into India) is covered only on the region side, and the manifest says so.
(c) OpenStreetMap contributors, ODbL. Needs: pip install osmium"""
import argparse, json, re, shutil, sys, urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE = "https://download.geofabrik.de"
CACHE = Path("data/raw/osm_cache")
NON_MOTORABLE = {"footway", "path", "steps", "pedestrian", "cycleway", "bridleway", "corridor", "via_ferrata", "elevator",
                 "construction", "proposed", "raceway", "bus_guideway"}          # same list as fetch_osm (ohsome route)
PLACES = {"city", "town", "village", "hamlet"}
ROAD_COLS = ("highway", "bridge", "tunnel", "name", "surface")


def pick_extract(region, snap):
    """Newest dated extract <= snap. Returns (url, extract_date)."""
    html = urllib.request.urlopen(f"{BASE}/{region}.html", timeout=60).read().decode("utf-8", "ignore")
    leaf = region.split("/")[-1]
    dated = sorted({m for m in re.findall(rf'href="({re.escape(leaf)}-(\d{{6}})\.osm\.pbf)"', html)}, key=lambda t: t[1])
    ok = [(f, datetime.strptime(d, "%y%m%d").date()) for f, d in dated if datetime.strptime(d, "%y%m%d").date() <= snap]
    if not ok: sys.exit(f"osm_geofabrik: no dated {region} extract on or before {snap} (have: {[d for _, d in dated][-6:]})")
    f, d = ok[-1]
    return f"{BASE}/{region.rsplit('/', 1)[0]}/{f}" if "/" in region else f"{BASE}/{f}", d


def download(url):
    CACHE.mkdir(parents=True, exist_ok=True); dst = CACHE / url.rsplit("/", 1)[1]
    if dst.exists() and dst.stat().st_size > 1e6: return dst
    tmp = dst.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=600) as r, open(tmp, "wb") as f: shutil.copyfileobj(r, f, 1 << 22)
    md5 = urllib.request.urlopen(url + ".md5", timeout=60).read().decode().split()[0]
    import hashlib
    h = hashlib.md5()
    with open(tmp, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""): h.update(b)
    if h.hexdigest() != md5: tmp.unlink(); sys.exit(f"osm_geofabrik: md5 mismatch for {url}")
    tmp.replace(dst); return dst


def extract(pbf, bbox):
    import osmium, shapely
    from shapely import wkb
    w, s, e, n = bbox; inb = lambda lon, lat: w <= lon <= e and s <= lat <= n
    fac = osmium.geom.WKBFactory()
    L = {k: [] for k in ("buildings", "roads", "hospitals", "clinics", "settlements", "rivers")}
    newest = {k: "" for k in L}
    keys = ("building", "highway", "place", "amenity", "healthcare", "waterway")

    def add(layer, geom, tags, oid, ts):
        props = {k: v for k, v in tags.items()}; props["osm_id"] = oid
        if layer == "roads":
            for c in ROAD_COLS: props.setdefault(c, None)
            props["motorable"] = props["highway"] not in NON_MOTORABLE
        L[layer].append({"type": "Feature", "properties": props, "geometry": shapely.geometry.mapping(geom)})
        newest[layer] = max(newest[layer], ts)

    def poi_layers(t):
        out = []
        if t.get("amenity") == "hospital" or t.get("healthcare") == "hospital": out.append("hospitals")
        if t.get("amenity") == "clinic" or t.get("healthcare") == "clinic": out.append("clinics")
        if t.get("place") in PLACES: out.append("settlements")
        return out

    fp = osmium.FileProcessor(str(pbf)).with_locations().with_areas().with_filter(osmium.filter.KeyFilter(*keys))
    for o in fp:
        t = dict(o.tags)
        try:
            if o.is_node():
                if inb(o.location.lon, o.location.lat):
                    for lay in poi_layers(t): add(lay, shapely.Point(o.location.lon, o.location.lat), t, f"node/{o.id}", o.timestamp.isoformat())
            elif o.is_way():
                nd = o.nodes
                if not nd or not any(inb(x.lon, x.lat) for x in (nd[0], nd[len(nd) // 2], nd[-1])): continue
                if "highway" in t: add("roads", wkb.loads(fac.create_linestring(o), hex=True), t, f"way/{o.id}", o.timestamp.isoformat())
                if t.get("waterway") == "river": add("rivers", wkb.loads(fac.create_linestring(o), hex=True), t, f"way/{o.id}", o.timestamp.isoformat())
            elif o.is_area():
                g = wkb.loads(fac.create_multipolygon(o), hex=True)
                c = g.representative_point()
                if not inb(c.x, c.y): continue
                oid = f"{'way' if o.from_way() else 'relation'}/{o.orig_id()}"
                if "building" in t: add("buildings", g, t, oid, o.timestamp.isoformat())
                for lay in poi_layers(t): add(lay, c, t, oid, o.timestamp.isoformat())
        except (RuntimeError, osmium.InvalidLocationError, ValueError):
            continue                                               # broken geometry / node outside the extract
    return L, newest


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bbox", required=True); ap.add_argument("--event-date", required=True)
    ap.add_argument("--snapshot", help="YYYY-MM-DD (default: event date minus 30 days)"); ap.add_argument("--region", default="asia/nepal")
    ap.add_argument("--out", default="data/raw/osm"); a = ap.parse_args()
    event = date.fromisoformat(a.event_date); snap = date.fromisoformat(a.snapshot) if a.snapshot else event - timedelta(days=30)
    if snap >= event: sys.exit(f"REFUSED: snapshot {snap} is not before the event {event}")
    bbox = tuple(map(float, a.bbox.split(",")))
    url, ext_date = pick_extract(a.region, snap)
    print(f"Geofabrik extract {url} (data as of {ext_date}; requested snapshot <= {snap})", flush=True)
    pbf = download(url)
    if shutil.which("osmium"):                       # osmium-tool: cut the bbox first (seconds) instead of scanning the region in Python
        import subprocess
        small = CACHE / f"{pbf.stem}_{'_'.join(f'{v:.3f}' for v in bbox)}.osm.pbf"
        if not small.exists():
            pad = (bbox[0] - .02, bbox[1] - .02, bbox[2] + .02, bbox[3] + .02)
            subprocess.run(["osmium", "extract", "-b", ",".join(map(str, pad)), "-s", "smart", "-O", "-o", str(small), str(pbf)], check=True)
        pbf = small
    else:
        print("osmium-tool not found: scanning the whole extract in Python (slow; apt/conda install osmium-tool to speed up)")
    L, newest = extract(pbf, bbox)
    late = {k: v for k, v in newest.items() if v and v[:10] > str(ext_date)}
    if late: sys.exit(f"REFUSED: edits after the extract date {ext_date}: {late}")
    final = Path(a.out); out = final.with_name(final.name + "_tmp")
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    for k, feats in L.items():
        (out / f"{k}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"  {k}: {len(feats):,} features | newest edit {newest[k][:10] or 'n/a'}")
    (out / "manifest.json").write_text(json.dumps({
        "snapshot": str(ext_date), "event_date": str(event), "bbox_wsen": bbox,
        "source": f"Geofabrik dated extract {url.rsplit('/', 1)[1]} ({a.region}); (c) OpenStreetMap contributors, ODbL",
        "coverage_note": f"only the {a.region} extract is read: parts of the bbox outside {a.region} have no OSM data in this run",
        "filters": {"buildings": "building=* (areas)", "roads": "highway=* (ways)", "hospitals": "amenity|healthcare=hospital",
                    "clinics": "amenity|healthcare=clinic", "settlements": "place in (city, town, village, hamlet)", "rivers": "waterway=river (ways)"},
        "counts": {k: len(v) for k, v in L.items()}, "max_last_edit": {k: v or "not provided" for k, v in newest.items()},
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2))
    final.mkdir(parents=True, exist_ok=True)
    for old in list(final.glob("*.geojson")) + [final / "manifest.json"]: old.unlink(missing_ok=True)
    for new in out.iterdir(): shutil.move(str(new), str(final / new.name))
    out.rmdir(); print(f"OK  snapshot={ext_date}  event={event}")


if __name__ == "__main__":
    main()

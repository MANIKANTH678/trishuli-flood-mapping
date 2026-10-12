#!/usr/bin/env python3
"""fetch_osm.py - pre-event OSM snapshot via the ohsome API v2 (ODbL).

Refuses to run unless --snapshot is strictly before --event-date, and writes
manifest.json (counts, filters, last-edit check) as audit evidence.

Needs an ohsome API key (free): https://account.heigit.org/signup
    export OHSOME_API_KEY="..."
Without a key (--source auto, the default) it falls back to a dated Geofabrik extract: src/download/osm_geofabrik.py.

    python -m src.download.fetch_osm --event-date 2026-08-26
    (bbox defaults to BBOX in src/config.py; override with --bbox W,S,E,N)

Dependencies: requests, shapely, pyarrow (no geopandas needed).
"""
import argparse, io, json, os, shutil, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# pyarrow is imported lazily (ohsome route only), so the Geofabrik fallback works without it
import requests
from shapely import wkb
from shapely.geometry import mapping, shape

from src.config import BBOX

API  = "https://api.heigit.org/ohsome-api/v2-rc/extraction/features.parquet"
META = "https://api.heigit.org/ohsome-api/v2-rc/metadata"
KEY = os.environ.get("OHSOME_API_KEY", "").strip().strip("\"'").strip()     # checked in main(), not at import
SESSION = requests.Session()
SESSION.headers.update({
    "Authorization": KEY,
    "User-Agent": "trishuli-flood-mapping/0.1 (hackathon; contact: your@email)",
})

LAYERS = {
    "buildings":   "building=* and geometry:polygon",
    "roads":       "highway=* and geometry:line",
    "hospitals":   "(amenity=hospital or healthcare=hospital)",
    "clinics":     "(amenity=clinic or healthcare=clinic)",
    "settlements": "place in (city, town, village, hamlet)",
    "rivers":      "waterway=river and geometry:line",
}
POINT_LAYERS = {"hospitals", "clinics", "settlements"}
ROAD_COLS = ("highway", "bridge", "tunnel", "name", "surface")
# 'track' stays motorable: many rural unpaved roads are mapped that way. Tune in Step 6.
NON_MOTORABLE = {"footway", "path", "steps", "pedestrian", "cycleway", "bridleway",
                "corridor", "via_ferrata", "elevator", "construction", "proposed",
                "raceway", "bus_guideway"}
TILE_DEG = 0.25

# v2 column names are not confirmed: the first response prints the real ones.
# Candidates are tried in order; adjust here if your columns differ.
ID_COLS   = ("osm_id", "@osmId", "osmId", "id")
TYPE_COLS = ("osm_type", "type")
TIME_COLS = ("edit_timestamp", "osm_timestamp", "timestamp", "@lastEdit", "last_edit", "lastEdit")


class Blocked(Exception):
    """Persistent 429/5xx: splitting tiles won't help."""


_printed_cols = False


def _first(row, names):
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return None


def _iso(v):
    if v is None:
        return ""
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _flatten_tags(t):
    """Tags may arrive as a dict, a list of (key, value) pairs, or a list of {key,value}."""
    if isinstance(t, dict):
        return dict(t)
    out = {}
    if isinstance(t, (list, tuple)):
        for item in t:
            if isinstance(item, dict) and "key" in item:
                out[item["key"]] = item.get("value")
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                out[item[0]] = item[1]
    return out


def request_features(bbox, flt, snapshot):
    global _printed_cols
    body = {
        "aoi": list(bbox),                                # [W, S, E, N]
        "time": snapshot,                                 # single timestamp = snapshot (v2 docs)
        "filter": flt,
        "clip": False,
    }
    r = None
    for attempt in range(5):
        r = SESSION.post(API, json=body, timeout=600)
        if r.status_code in (429, 502, 503, 504):
            wait = int(r.headers.get("Retry-After", 15 * 2 ** attempt))
            print(f"    HTTP {r.status_code}, waiting {wait}s")
            time.sleep(wait)
            continue
        if r.status_code in (400, 401, 403, 404, 422):
            sys.exit(f"ohsome rejected the request ({r.status_code}): {r.text[:300]}")
        r.raise_for_status()

        import pyarrow.parquet as pq
        tbl = pq.read_table(io.BytesIO(r.content))
        meta = tbl.schema.metadata or {}
        gcol = None
        if b"geo" in meta:
            gcol = json.loads(meta[b"geo"]).get("primary_column")
        if gcol not in tbl.column_names:
            gcol = next((c for c in ("geom", "geometry") if c in tbl.column_names), None)
        if gcol is None:
            sys.exit(f"No geometry column found. Columns: {tbl.column_names}")
        if not _printed_cols:                             # once, not per tile
            print("    columns:", tbl.column_names, "| geometry column:", gcol)
            _printed_cols = True

        feats = []
        for row in tbl.to_pylist():
            g = row.pop(gcol, None)
            if g is None:
                continue
            try:
                geom = mapping(wkb.loads(g))
            except Exception as e:
                sys.exit(f"Could not decode geometry ({type(e).__name__}: {e}). "
                        f"Geometry column may not be WKB; paste this error.")
            feats.append({"type": "Feature", "properties": row, "geometry": geom})
        if tbl.num_rows and not feats:
            sys.exit(f"Got {tbl.num_rows} rows but kept none (geometry column '{gcol}' empty?)")
        return feats
    raise Blocked(f"HTTP {r.status_code if r is not None else '?'} persists")


def fetch_bbox(bbox, flt, snapshot, depth=0):
    for attempt in range(2):
        try:
            return request_features(bbox, flt, snapshot)
        except Blocked:
            raise                                         # never split on a block
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"    retry {attempt + 1} {bbox}: {type(e).__name__}: {e}")
            time.sleep(5 * (attempt + 1))
    if depth >= 3:
        raise RuntimeError(f"ohsome failed on {bbox} even after splitting")
    x0, y0, x1, y1 = bbox
    xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    for sub in [(x0, y0, xm, ym), (xm, y0, x1, ym), (x0, ym, xm, y1), (xm, ym, x1, y1)]:
        out += fetch_bbox(sub, flt, snapshot, depth + 1)
    return out


def tiles(bbox, step=TILE_DEG):
    w, s, e, n = bbox
    x = w
    while x < e:
        y = s
        while y < n:
            yield (x, y, min(x + step, e), min(y + step, n))
            y += step
        x += step


def finalize(name, feats):
    seen, out, last_edit = set(), [], ""
    for f in feats:
        p, geom = f.get("properties", {}), f.get("geometry")
        if not geom:
            continue

        raw_id = _first(p, ID_COLS)
        if raw_id is None:
            sys.exit(f"No OSM id column found among {ID_COLS}. "
                    f"Properties seen: {list(p)[:20]}")
        otype = _first(p, TYPE_COLS)
        oid = f"{otype}/{raw_id}" if otype in ("node", "way", "relation") else str(raw_id)
        if oid in seen:                                   # dedupe across tiles
            continue
        seen.add(oid)

        g = shape(geom)
        if name in POINT_LAYERS and g.geom_type != "Point":
            g = g.representative_point()

        if "tags" in p:
            props = _flatten_tags(p["tags"])
        else:                                             # tags flattened into columns
            skip = set(ID_COLS) | set(TYPE_COLS) | set(TIME_COLS) | {"bbox"}
            props = {k: v for k, v in p.items()
                    if k not in skip and not k.startswith("@")
                    and isinstance(v, (str, int, float, bool, type(None)))}
        props["osm_id"] = oid

        ts = _iso(_first(p, TIME_COLS))
        last_edit = max(last_edit, ts)

        if name == "roads":
            for c in ROAD_COLS:
                props.setdefault(c, None)                 # damage_v2 needs a 'bridge' column
            props["motorable"] = props["highway"] not in NON_MOTORABLE
        out.append({"type": "Feature", "properties": props, "geometry": mapping(g)})
    return out, last_edit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", default=",".join(map(str, BBOX)),
                    help="W,S,E,N (default: BBOX from src/config.py)")
    ap.add_argument("--event-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--snapshot", help="YYYY-MM-DD (default: event date minus 30 days)")
    ap.add_argument("--out", default="data/raw/osm")
    ap.add_argument("--source", choices=["auto", "ohsome", "geofabrik"], default="auto",
                    help="auto = ohsome when OHSOME_API_KEY is set, else a dated Geofabrik extract (src/download/osm_geofabrik.py)")
    ap.add_argument("--region", default="asia/nepal", help="Geofabrik region for --source geofabrik")
    a = ap.parse_args()
    if a.source == "geofabrik" or (a.source == "auto" and not KEY):
        if a.source == "auto": print("OHSOME_API_KEY not set: using a dated Geofabrik extract instead (pre-event, no key)")
        from src.download import osm_geofabrik
        sys.argv = [sys.argv[0], "--bbox", a.bbox, "--event-date", a.event_date, "--region", a.region, "--out", a.out] + (["--snapshot", a.snapshot] if a.snapshot else [])
        return osm_geofabrik.main()
    if not KEY:
        sys.exit("Set OHSOME_API_KEY first (or use --source geofabrik)")

    event = date.fromisoformat(a.event_date)
    snap = date.fromisoformat(a.snapshot) if a.snapshot else event - timedelta(days=30)
    if snap >= event:
        sys.exit(f"REFUSED: snapshot {snap} is not before the event {event}")
    bbox = tuple(float(v) for v in a.bbox.split(","))

    final = Path(a.out)
    out = final.with_name(final.name + "_tmp")            # write here; swap in only on success
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    try:
        meta = SESSION.get(META, timeout=30).json()
    except Exception:
        meta = {}

    counts, last_edits = {}, {}
    for name, flt in LAYERS.items():
        print(f"[{name}] {flt}")
        feats = []
        for t in tiles(bbox):
            feats += fetch_bbox(t, flt, snap.isoformat())
            time.sleep(1)
        feats, last = finalize(name, feats)
        if last and last[:10] > snap.isoformat():
            sys.exit(f"REFUSED: {name} has edits after the snapshot ({last})")
        (out / f"{name}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": feats},
                    ensure_ascii=False, default=str),
            encoding="utf-8")
        counts[name], last_edits[name] = len(feats), last or "not provided"
        print(f"  {len(feats):,} features | newest edit: {last or 'n/a'}")

    (out / "manifest.json").write_text(json.dumps({
        "snapshot": snap.isoformat(), "event_date": event.isoformat(), "bbox_wsen": bbox,
        "source": "ohsome API v2 (HeiGIT); (c) OpenStreetMap contributors, ODbL",
        "filters": LAYERS, "counts": counts, "max_last_edit": last_edits,
        "ohsome_metadata": meta,
        "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=2, default=str))
    # success: replace the old layers (never leaves stale or half-written files behind)
    final.mkdir(parents=True, exist_ok=True)
    for old in list(final.glob("*.geojson")) + [final / "manifest.json"]:
        old.unlink(missing_ok=True)
    for new in out.iterdir():
        shutil.move(str(new), str(final / new.name))
    out.rmdir()
    print(f"\nOK  snapshot={snap}  event={event}")


if __name__ == "__main__":
    main()
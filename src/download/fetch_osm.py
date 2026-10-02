"""fetch_osm.py - fetch OSM buildings, roads, settlements via Overpass API."""
import argparse, json, time
from pathlib import Path
import requests

# Overpass mirrors — try in order
MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

HEADERS = {
    "User-Agent": "trishuli-flood-mapping/1.0 (research; contact: rks77)",
    "Accept": "application/json",
}

LAYERS = {
    "buildings":   'way["building"]({s},{w},{n},{e});',
    "roads":       'way["highway"]({s},{w},{n},{e});',
    "settlements": 'node["place"]({s},{w},{n},{e});',
}


def fetch_layer(w, s, e, n, filt, timeout=180):
    query = f"[out:json][timeout:{timeout}];({filt.format(s=s,w=w,n=n,e=e)});out geom;"
    last_err = None
    for url in MIRRORS:
        try:
            print(f"    trying {url} ...")
            r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=timeout + 30)
            if r.status_code == 200:
                return r.json()
            print(f"    -> {r.status_code}")
            last_err = f"{url}: {r.status_code}"
        except Exception as ex:
            print(f"    -> {type(ex).__name__}: {ex}")
            last_err = f"{url}: {ex}"
    raise RuntimeError(f"all mirrors failed; last error: {last_err}")


def to_geojson(ovp, layer):
    feats = []
    for el in ovp.get("elements", []):
        if layer == "settlements":
            if el.get("type") != "node": continue
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        else:
            if "geometry" not in el: continue
            coords = [[g["lon"], g["lat"]] for g in el["geometry"]]
            if len(coords) < 2: continue
            geom = {"type": "LineString", "coordinates": coords}
        feats.append({
            "type": "Feature",
            "properties": el.get("tags", {}),
            "geometry": geom,
        })
    return {"type": "FeatureCollection", "features": feats}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="W,S,E,N")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD (informational only)")
    ap.add_argument("--out", default="data/raw/osm")
    args = ap.parse_args()

    w, s, e, n = [float(x) for x in args.bbox.split(",")]
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    print(f"-> bbox W{w} S{s} E{e} N{n}")
    print(f"-> date {args.date} (informational; Overpass returns current)")

    for name, filt in LAYERS.items():
        print(f"[{name}] fetching ...")
        try:
            ovp = fetch_layer(w, s, e, n, filt)
            fc = to_geojson(ovp, name)
            path = out / f"{name}.geojson"
            path.write_text(json.dumps(fc, ensure_ascii=False))
            print(f"  OK {path} ({len(fc['features'])} features)")
        except Exception as ex:
            print(f"  FAIL {name}: {ex}")
        time.sleep(4)

    print("\ndone")


if __name__ == "__main__":
    main()

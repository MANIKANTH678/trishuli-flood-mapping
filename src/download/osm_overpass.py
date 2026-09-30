"""Download OSM data via Overpass API (with proper headers)."""
import os
import json
import time
import requests
import osm2geojson

BBOX = (27.40, 84.50, 28.40, 86.00)  # south, west, north, east
OUT_DIR = "data/raw/osm"
os.makedirs(OUT_DIR, exist_ok=True)

QUERIES = {
    "roads":       'way["highway"]',
    "buildings":   'way["building"]',
    "settlements": 'node["place"~"village|town|city"]',
    "hospitals":   'node["amenity"~"hospital|clinic"]',
}

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

# Identify your script clearly to the server
HEADERS = {
    "User-Agent": "FloodHackathon/1.0 (contact: your_email@example.com)",
    "Accept": "application/json",
}


def fetch(filter_str, retries=2):
    s, w, n, e = BBOX
    query = f"""
    [out:json][timeout:180];
    (
      {filter_str}({s},{w},{n},{e});
    );
    out body;
    >;
    out skel qt;
    """
    for url in OVERPASS_URLS:
        for attempt in range(retries):
            try:
                print(f"  → trying {url} (attempt {attempt + 1})")
                r = requests.post(url, data={"data": query}, headers=HEADERS, timeout=180)
                if r.status_code == 200:
                    return r.json()
                print(f"    HTTP {r.status_code}")
                if r.status_code == 429:
                    time.sleep(60)  # wait longer for rate limit
                else:
                    time.sleep(10)
            except Exception as ex:
                print(f"    error: {ex}")
                time.sleep(10)
    raise RuntimeError(f"All Overpass mirrors failed for {filter_str}")


def main():
    for name, filt in QUERIES.items():
        print(f"\n📥 {name} ...")
        osm_json = fetch(filt)
        elements = osm_json.get("elements", [])
        print(f"  got {len(elements)} raw elements")

        geojson = osm2geojson.json2geojson(osm_json)
        out_path = os.path.join(OUT_DIR, f"{name}.geojson")
        with open(out_path, "w") as f:
            json.dump(geojson, f)

        feats = len(geojson.get("features", []))
        size_mb = os.path.getsize(out_path) / 1e6
        print(f"  ✅ {out_path}  {feats} features  {size_mb:.2f} MB")
        time.sleep(45)  # Be polite between queries


if __name__ == "__main__":
    main()

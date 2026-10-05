#!/usr/bin/env python3
import argparse, json, requests
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

API = "https://earth-search.aws.element84.com/v1/search"
KEYS = {"B02": "blue", "B03": "green", "B04": "red", "B08": "nir", "B11": "swir16", "SCL": "scl"}
ap = argparse.ArgumentParser()
ap.add_argument("--bbox", required=True); ap.add_argument("--event-date", required=True)
ap.add_argument("--pre-days", type=int, default=70); ap.add_argument("--post-days", type=int, default=35)
ap.add_argument("--max-cloud", type=float, default=90); ap.add_argument("--out", default="data/raw/s2/scenes.json")
a = ap.parse_args(); ev = date.fromisoformat(a.event_date)
body = {"collections": ["sentinel-2-l2a"], "bbox": [float(v) for v in a.bbox.split(",")], "limit": 200,
        "datetime": f"{ev - timedelta(days=a.pre_days)}T00:00:00Z/{ev + timedelta(days=a.post_days)}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": a.max_cloud}}}
r = requests.post(API, json=body, timeout=60); r.raise_for_status(); feats = r.json()["features"]
if len(feats) >= 200: print("WARNING: 200-item cap reached; narrow --pre-days / --post-days")
scenes = []
for f in feats:
    p, A = f["properties"], f["assets"]
    if not all(k in A for k in KEYS.values()): continue
    rb = (A["red"].get("raster:bands") or [{}])[0]
    scenes.append({"id": f["id"], "date": p["datetime"][:10], "tile": p.get("grid:code"), "cloud": p.get("eo:cloud_cover"),
                   "scale": rb.get("scale", 1e-4), "offset": rb.get("offset", -0.1),
                   "assets": {b: A[k]["href"] for b, k in KEYS.items()}})
scenes.sort(key=lambda s: (s["date"], s["tile"] or ""))
Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(scenes, indent=1))
by = defaultdict(list)
for s in scenes: by[s["date"]].append(s)
for d, ss in sorted(by.items()):
    print(f"{d} {'PRE ' if d < a.event_date else 'POST'} tiles={len(ss)} cloud%={[round(s['cloud']) for s in ss]}")
print(f"{len(by)} dates, {len(scenes)} scenes")
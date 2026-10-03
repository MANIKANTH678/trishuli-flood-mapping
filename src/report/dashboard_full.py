"""P4: build a single-file HTML dashboard from the pipeline outputs.

Reads the JSON / CSV / PNG files in ``outputs/`` and writes
``outputs/dashboard.html``. Only the Python standard library is used, so the
dashboard can be rebuilt on a machine without the geospatial stack installed.

    python -m src.report.dashboard_full                 # -> outputs/dashboard.html
    python -m src.report.dashboard_full --out-dir path  # read/write another folder

Images are embedded as base64 so the file works offline. The interactive
settlement map loads Leaflet from a CDN and degrades to the table when there
is no network connection.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402

# --------------------------------------------------------------------------- #
# Static content
# --------------------------------------------------------------------------- #

FEATURE_GLOSSARY = {
    "elevation":    ("Elevation", "Height above sea level from the 30 m DEM (m)."),
    "slope":        ("Slope", "Terrain steepness derived from the DEM (degrees)."),
    "aspect":       ("Aspect", "Compass direction the slope faces (degrees)."),
    "tpi":          ("Topographic position", "Height relative to the surrounding 5-pixel neighbourhood (m)."),
    "dist_lowland": ("Distance to lowland", "Distance to the nearest low-lying terrain (m)."),
    "vv_diff":      ("VV change", "Sentinel-1 VV backscatter, post minus pre (dB). Strong drops mean open water."),
    "vh_diff":      ("VH change", "Sentinel-1 VH backscatter, post minus pre (dB)."),
    "vv_pre":       ("VV pre-event", "Pre-flood VV backscatter (dB)."),
    "vh_pre":       ("VH pre-event", "Pre-flood VH backscatter (dB)."),
}

FIGURES = [
    ("flood_mask", "flood_mask.png", "Flood mask",
     "Sentinel-1 VV change detection on the 30 m grid. Blue pixels dropped more than "
     "1.5 dB between the pre- and post-event scenes after masking slopes above 15° and "
     "permanent water. Patches under 100 pixels were removed.", True),
    ("susceptibility", "susceptibility_preview.png", "Flood susceptibility",
     "Per-pixel probability of flooding from the XGBoost model trained on terrain and "
     "SAR features. Darker red means higher probability.", False),
    ("buildings", "affected_buildings_map.png", "Flooded buildings",
     "OpenStreetMap building footprints whose centroid falls inside the flood mask.", False),
    ("roads", "affected_roads_map.png", "Flooded roads",
     "OpenStreetMap road segments whose midpoint falls inside the flood mask.", False),
]

METHOD_STEPS = [
    ("Acquire", "Sentinel-1 GRD scenes before and after the event, a 30 m DEM, and an "
                "OpenStreetMap snapshot taken before the flood."),
    ("Align", "Calibrate SAR backscatter to dB and resample everything to a common 30 m "
              "grid in UTM 45N (EPSG:32645)."),
    ("Detect", "Difference post and pre VV backscatter, threshold at −1.5 dB (Otsu-guided), "
               "mask steep slopes and permanent water, then clean small patches."),
    ("Model", "Train an XGBoost classifier on nine terrain and SAR features with 10:1 "
              "negative undersampling; score the whole area of interest."),
    ("Impact", "Intersect the flood mask with buildings, roads and settlements; find "
               "settlements disconnected from the road graph once flooded segments are removed."),
]

LIMITATIONS = [
    "30 m pixels smear small structures, so individual building counts are indicative.",
    "OpenStreetMap completeness varies across the valley; rural areas are under-mapped.",
    "Cut-off detection samples one midpoint per road segment and ignores footpaths.",
    "Steep terrain is masked out, so debris flows on slopes are not captured.",
]

DATA_FILES = [
    ("flood_mask.png", "Flood mask preview", "PNG"),
    ("susceptibility.tif", "Susceptibility probability raster", "GeoTIFF"),
    ("susceptibility_binary.tif", "Susceptibility above threshold", "GeoTIFF"),
    ("affected_buildings.gpkg", "Flooded building footprints", "GeoPackage"),
    ("affected_roads.geojson", "Flooded road segments", "GeoJSON"),
    ("cutoff_settlements.json", "Settlements with cut-off flag", "JSON"),
    ("impact_stats.json", "Headline statistics", "JSON"),
    ("impact_by_district.csv", "Flooded buildings by tagged locality", "CSV"),
    ("flood_model.joblib", "Trained XGBoost model", "joblib"),
    ("model_meta.json", "Model metrics and feature list", "JSON"),
    ("feature_importance.json", "XGBoost feature importance", "JSON"),
]

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def esc(value) -> str:
    return html.escape(str(value), quote=True)


def load_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"⚠️  {path.name}: {exc} — using default", file=sys.stderr)
        return default


def image_data_uri(path: Path) -> str | None:
    if not path.exists():
        print(f"⚠️  missing figure {path.name}", file=sys.stderr)
        return None
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def fmt_int(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "—"


def pct(part, whole, digits=1) -> str:
    try:
        return f"{100 * part / whole:.{digits}f}%"
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"


def human_size(n_bytes: int) -> str:
    size = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.0f} {unit}" if unit == "B" else f"{size:,.1f} {unit}"
        size /= 1024
    return f"{n_bytes} B"


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


_NAME_RE = re.compile(r"^(?P<type>[a-z_]+?)_(?P<id>\d+)$")


def settlement_record(raw: dict) -> dict:
    """Turn ``{"name": "hamlet_1234", ...}`` into a display-friendly record."""
    name = str(raw.get("name", ""))
    m = _NAME_RE.match(name)
    kind = m.group("type") if m else "place"
    osm_id = m.group("id") if m else ""
    label = kind.replace("_", " ").title()
    if osm_id:
        label = f"{label} · OSM {osm_id}"
    elif name:
        label = name
    return {
        "label": label,
        "type": kind,
        "id": osm_id,
        "lat": round(float(raw.get("lat", 0.0)), 5),
        "lon": round(float(raw.get("lon", 0.0)), 5),
        "district": raw.get("district") or "",
        "cut": bool(raw.get("cut_off")),
    }


def feature_chart_svg(importance: dict) -> str:
    """Horizontal bar chart of feature importance as inline SVG."""
    if not importance:
        return "<p class='muted'>No feature importance file found.</p>"
    items = sorted(importance.items(), key=lambda kv: -kv[1])
    top = max(v for _, v in items) or 1.0
    row_h, left, right, width = 30, 150, 60, 640
    height = row_h * len(items) + 8
    bar_w = width - left - right
    parts = [f'<svg class="fi-chart" viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Feature importance bar chart" xmlns="http://www.w3.org/2000/svg">']
    for i, (key, val) in enumerate(items):
        y = i * row_h + 4
        w = max(2.0, bar_w * val / top)
        name = FEATURE_GLOSSARY.get(key, (key, ""))[0]
        parts.append(
            f'<g class="fi-row"><title>{esc(name)}: {val:.3f}</title>'
            f'<text x="{left - 10}" y="{y + 15}" text-anchor="end" class="fi-label">{esc(name)}</text>'
            f'<rect x="{left}" y="{y + 2}" width="{bar_w}" height="{row_h - 8}" rx="4" class="fi-track"/>'
            f'<rect x="{left}" y="{y + 2}" width="{w:.1f}" height="{row_h - 8}" rx="4" class="fi-bar"/>'
            f'<text x="{left + w + 8:.1f}" y="{y + 15}" class="fi-value">{val:.3f}</text></g>'
        )
    parts.append("</svg>")
    return "".join(parts)


def locality_rows(csv_path: Path, flooded_total: int) -> tuple[str, int]:
    """Merge the messy ``addr:city`` tags case-insensitively and render rows."""
    if not csv_path.exists():
        return "", 0
    merged: dict[str, list] = {}
    with open(csv_path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            name, count = row[0].strip(), row[1]
            try:
                count = int(count)
            except ValueError:
                continue
            key = re.sub(r"\s+", " ", name.lower())
            if key in merged:
                merged[key][1] += count
            else:
                merged[key] = [name, count]
    rows = sorted(merged.values(), key=lambda r: -r[1])
    tagged = sum(r[1] for r in rows)
    top = rows[0][1] if rows else 1
    out = []
    for name, count in rows[:12]:
        bar = max(1.5, 100 * count / top)
        out.append(
            f"<tr><td>{esc(name)}</td>"
            f"<td class='num'>{count:,}</td>"
            f"<td class='barcell'><span class='bar' style='width:{bar:.1f}%'></span></td></tr>"
        )
    return "\n".join(out), tagged


# --------------------------------------------------------------------------- #
# Page template
# --------------------------------------------------------------------------- #

PAGE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trishuli Flood Impact</title>
<meta name="description" content="Flood extent, susceptibility and infrastructure impact for the $flood_date Trishuli–Bhote Koshi flood, Nepal.">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin="">
<style>
:root{
  --bg:#f4f6fa; --surface:#ffffff; --surface-2:#eef2f8; --border:#dbe2ee;
  --text:#14213d; --muted:#5b6b85; --accent:#1d6fd8; --accent-soft:#dce9fb;
  --water:#1d6fd8; --building:#c0392b; --road:#0e8a7d; --warn:#b7791f;
  --shadow:0 1px 2px rgba(20,33,61,.06),0 8px 24px -12px rgba(20,33,61,.18);
  --radius:14px; --nav-h:56px;
}
:root:not([data-theme="light"]){ color-scheme: light dark; }
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#0f1420; --surface:#171d2c; --surface-2:#1f2637; --border:#2b3447;
    --text:#e8edf6; --muted:#9aa7bd; --accent:#5b9cf0; --accent-soft:#1b2d4a;
    --water:#5b9cf0; --building:#ef6f5f; --road:#36c2b1; --warn:#e0a84a;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -14px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --bg:#0f1420; --surface:#171d2c; --surface-2:#1f2637; --border:#2b3447;
  --text:#e8edf6; --muted:#9aa7bd; --accent:#5b9cf0; --accent-soft:#1b2d4a;
  --water:#5b9cf0; --building:#ef6f5f; --road:#36c2b1; --warn:#e0a84a;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 28px -14px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:calc(var(--nav-h) + 12px)}
body{margin:0;background:var(--bg);color:var(--text);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Inter,sans-serif;
  -webkit-font-smoothing:antialiased}
a{color:var(--accent)}
h1,h2,h3{line-height:1.2;margin:0 0 .4rem;letter-spacing:-.01em}
h1{font-size:clamp(1.6rem,3.5vw,2.4rem)}
h2{font-size:1.35rem}
h3{font-size:1.05rem}
p{margin:.3rem 0 .8rem}
.muted{color:var(--muted)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:0 16px}

/* nav */
.nav{position:sticky;top:0;z-index:50;height:var(--nav-h);background:var(--surface);background:color-mix(in srgb,var(--surface) 88%,transparent);
  backdrop-filter:saturate(1.4) blur(10px);border-bottom:1px solid var(--border)}
.nav .wrap{display:flex;align-items:center;gap:8px;height:100%}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;white-space:nowrap}
.brand .dot{width:12px;height:12px;border-radius:50%;background:var(--water);box-shadow:0 0 0 4px var(--accent-soft)}
.nav-links{display:flex;gap:2px;margin-left:auto;overflow-x:auto;scrollbar-width:none}
.nav-links::-webkit-scrollbar{display:none}
.nav-links a{color:var(--muted);text-decoration:none;padding:6px 10px;border-radius:8px;font-size:.92rem;white-space:nowrap}
.nav-links a:hover,.nav-links a.active{color:var(--text);background:var(--surface-2)}
.btn{appearance:none;border:1px solid var(--border);background:var(--surface);color:var(--text);
  border-radius:9px;padding:6px 10px;font:inherit;font-size:.9rem;cursor:pointer;line-height:1.2}
.btn:hover{background:var(--surface-2)}
.btn.icon{width:34px;height:34px;padding:0;display:inline-grid;place-items:center;flex:none}

/* hero */
.hero{padding:40px 0 20px}
.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:.75rem;font-weight:600;color:var(--accent)}
.hero p.lead{font-size:1.05rem;max-width:68ch;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.chip{display:inline-flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--border);
  border-radius:999px;padding:5px 12px;font-size:.85rem;color:var(--muted)}
.chip b{color:var(--text);font-weight:600}

/* sections */
section{padding:28px 0}
.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.section-head p{margin:0}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}
.card .pad{padding:18px 20px}

/* KPIs */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
.kpi{padding:18px 20px;position:relative;overflow:hidden}
.kpi .label{font-size:.85rem;color:var(--muted);font-weight:500}
.kpi .value{font-size:2rem;font-weight:700;letter-spacing:-.02em;margin:4px 0 2px;font-variant-numeric:tabular-nums}
.kpi .sub{font-size:.85rem;color:var(--muted)}
.kpi .meter{height:6px;background:var(--surface-2);border-radius:999px;margin-top:12px;overflow:hidden}
.kpi .meter i{display:block;height:100%;border-radius:999px;background:var(--kpi-color,var(--accent));min-width:4px}
.kpi.buildings{--kpi-color:var(--building)} .kpi.roads{--kpi-color:var(--road)}
.kpi.settlements{--kpi-color:var(--warn)} .kpi.model{--kpi-color:var(--accent)}
.kpi::before{content:"";position:absolute;inset:0 auto 0 0;width:4px;background:var(--kpi-color,var(--accent))}

/* figures */
.figgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:16px}
.fig{display:flex;flex-direction:column;overflow:hidden}
.fig .frame{position:relative;background:var(--surface-2);aspect-ratio:3/2;display:grid;place-items:center;cursor:zoom-in;overflow:hidden}
.fig .frame.dark{background:#000}
.fig .frame img{max-width:100%;max-height:100%;object-fit:contain;transition:transform .25s ease}
.fig .frame:hover img{transform:scale(1.02)}
.fig .frame .zoom{position:absolute;right:10px;bottom:10px;background:rgba(20,33,61,.7);color:#fff;font-size:.75rem;padding:3px 8px;border-radius:6px;pointer-events:none}
.fig .frame.inverted img{filter:invert(1) hue-rotate(180deg) saturate(1.6)}
.fig .caption{padding:14px 16px 16px}
.fig .caption h3{display:flex;align-items:center;justify-content:space-between;gap:8px}
.fig .caption p{margin:.3rem 0 0;color:var(--muted);font-size:.9rem}
.fig .missing{color:var(--muted);font-size:.9rem;padding:24px;text-align:center}
.legend{display:inline-flex;align-items:center;gap:6px;font-size:.8rem;color:var(--muted);font-weight:500}
.legend i{width:10px;height:10px;border-radius:3px;display:inline-block;background:var(--c)}

/* lightbox */
.lightbox{position:fixed;inset:0;background:rgba(5,9,18,.92);display:none;z-index:100;overflow:auto;cursor:zoom-out}
.lightbox.open{display:block}
.lightbox img{display:block;margin:auto;max-width:96vw;max-height:92vh;object-fit:contain;position:absolute;inset:0;cursor:zoom-in}
.lightbox.full img{position:static;max-width:none;max-height:none;cursor:zoom-out;padding:24px}
.lightbox .lb-bar{position:fixed;top:0;left:0;right:0;display:flex;justify-content:space-between;align-items:center;
  padding:12px 16px;color:#fff;font-size:.9rem;background:linear-gradient(rgba(0,0,0,.6),transparent);pointer-events:none}
.lightbox .lb-bar .btn{pointer-events:auto;background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.25);color:#fff}

/* model */
.model-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:16px;align-items:start}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:16px}
.metric{background:var(--surface-2);border-radius:10px;padding:10px 12px}
.metric .v{font-size:1.4rem;font-weight:700;font-variant-numeric:tabular-nums}
.metric .k{font-size:.78rem;color:var(--muted)}
.fi-wrap{overflow-x:auto}
.fi-chart{width:100%;min-width:460px;height:auto;display:block}
.fi-label{font-size:12.5px;fill:var(--text)}
.fi-value{font-size:12px;fill:var(--muted);font-variant-numeric:tabular-nums}
.fi-track{fill:var(--surface-2)}
.fi-bar{fill:var(--accent)}
.fi-row:hover .fi-bar{fill:var(--water);opacity:.85}
details{border-top:1px solid var(--border);margin-top:12px;padding-top:10px}
summary{cursor:pointer;color:var(--muted);font-size:.9rem}
pre{background:var(--surface-2);padding:12px;border-radius:10px;overflow:auto;font-size:.82rem;margin:.6rem 0 0}

/* tables */
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{padding:.55rem .7rem;border-bottom:1px solid var(--border);text-align:left;vertical-align:middle}
th{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600;background:var(--surface)}
tbody tr:hover{background:var(--surface-2)}
th.sortable{cursor:pointer;user-select:none;white-space:nowrap}
th.sortable::after{content:"↕";opacity:.4;margin-left:5px;font-size:.8em}
th.sortable.asc::after{content:"↑";opacity:1} th.sortable.desc::after{content:"↓";opacity:1}
.barcell{width:40%}
.bar{display:block;height:8px;border-radius:999px;background:var(--building)}
.table-scroll{overflow:auto;max-height:520px;border-top:1px solid var(--border)}
.table-scroll thead th{position:sticky;top:0;z-index:1}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.78rem;font-weight:600;background:var(--surface-2);color:var(--muted);text-transform:capitalize}
.pill.hamlet{background:#fdf1dc;color:#8a5a0d} .pill.village{background:#e3f1ff;color:#1a56a7}
.pill.town{background:#e4f6f1;color:#0b6b5b} .pill.city{background:#f3e5ff;color:#6a2ca8}
:root[data-theme="dark"] .pill.hamlet,:root[data-theme="dark"] .pill.village,:root[data-theme="dark"] .pill.town,:root[data-theme="dark"] .pill.city{background:var(--surface-2)}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]) .pill{background:var(--surface-2)}}
.linkbtn{background:none;border:0;color:var(--accent);cursor:pointer;font:inherit;padding:0;font-size:.85rem}
.linkbtn:hover{text-decoration:underline}

/* settlements */
.settle-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
#settlement-map{height:460px;border-radius:var(--radius);z-index:1;background:var(--surface-2)}
#settlement-map.offline{display:grid;place-items:center;text-align:center;padding:24px;color:var(--muted)}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:12px 14px}
.toolbar input,.toolbar select{font:inherit;font-size:.9rem;padding:7px 10px;border:1px solid var(--border);border-radius:9px;background:var(--surface);color:var(--text)}
.toolbar input{flex:1;min-width:160px}
.toolbar .count{margin-left:auto;font-size:.85rem;color:var(--muted);white-space:nowrap}
.leaflet-container{font:inherit}
.leaflet-popup-content{font-size:.9rem;line-height:1.4}
.leaflet-popup-content b{display:block}
.map-legend{display:flex;gap:14px;flex-wrap:wrap;padding:10px 14px;font-size:.82rem;color:var(--muted)}
.map-legend span{display:inline-flex;align-items:center;gap:6px}
.map-legend i{width:10px;height:10px;border-radius:50%;display:inline-block;background:var(--c);border:2px solid var(--c)}
.map-legend i.hollow{background:transparent}

/* methods */
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;counter-reset:step}
.step{padding:16px 18px;position:relative}
.step::before{counter-increment:step;content:counter(step);display:inline-grid;place-items:center;width:26px;height:26px;border-radius:50%;
  background:var(--accent-soft);color:var(--accent);font-weight:700;font-size:.85rem;margin-bottom:8px}
.step h3{font-size:1rem}
.step p{margin:0;color:var(--muted);font-size:.9rem}
.callouts{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:14px}
.callout{border-left:3px solid var(--warn);background:var(--surface);border-radius:0 10px 10px 0;padding:10px 14px;font-size:.9rem;color:var(--muted)}

footer{padding:30px 0 50px;color:var(--muted);font-size:.85rem;border-top:1px solid var(--border);margin-top:20px}
footer .wrap{display:flex;flex-wrap:wrap;gap:8px 20px;justify-content:space-between}

@media (max-width:860px){
  .model-grid,.settle-grid{grid-template-columns:minmax(0,1fr)}
  .brand .text{display:none}
  .section-head{flex-direction:column;gap:4px}
  #settlement-map{height:360px}
  .hero{padding:28px 0 12px}
  .barcell{width:30%}
}
@media print{
  .nav,.toolbar,.lightbox,#settlement-map,.zoom{display:none!important}
  body{background:#fff;color:#000}
  .card{box-shadow:none;break-inside:avoid}
  section{padding:14px 0}
}
</style>
</head>
<body>
<header class="nav">
  <div class="wrap">
    <div class="brand"><span class="dot" aria-hidden="true"></span><span class="text">Trishuli Flood Impact</span></div>
    <nav class="nav-links" aria-label="Sections">
      <a href="#overview">Overview</a><a href="#maps">Maps</a><a href="#model">Model</a>
      <a href="#settlements">Settlements</a><a href="#methods">Methods</a><a href="#data">Data</a>
    </nav>
    <button class="btn icon" id="theme-toggle" title="Toggle dark mode" aria-label="Toggle dark mode">◐</button>
  </div>
</header>

<main class="wrap">
<section class="hero" id="overview">
  <div class="eyebrow">Track B · Multimodal AI Hackathon 2026</div>
  <h1>Trishuli–Bhote Koshi flood, $flood_date_long</h1>
  <p class="lead">Flood extent mapped from Sentinel-1 radar change detection, a learned susceptibility
  surface, and the buildings, roads and settlements the water reached. All inputs are free, open data.</p>
  <div class="chips">
    <span class="chip">Pre-event scene <b>$pre_date</b></span>
    <span class="chip">Post-event scene <b>$post_date</b></span>
    <span class="chip">Sensor <b>Sentinel-1 GRD · VV/VH</b></span>
    <span class="chip">Grid <b>$pixel_size m · $crs</b></span>
    <span class="chip">Area of interest <b>$bbox</b></span>
    <span class="chip">OSM snapshot <b>$osm_date</b></span>
  </div>
</section>

<section aria-labelledby="kpi-head">
  <div class="section-head"><h2 id="kpi-head">Impact at a glance</h2><p class="muted">Counts come from intersecting the flood mask with the pre-flood OpenStreetMap snapshot.</p></div>
  <div class="kpis">
    <div class="card kpi buildings">
      <div class="label">Flooded buildings</div>
      <div class="value">$flooded_buildings</div>
      <div class="sub">$pct_buildings of $total_buildings mapped buildings</div>
      <div class="meter"><i style="width:$pct_buildings_w%"></i></div>
    </div>
    <div class="card kpi roads">
      <div class="label">Flooded road segments</div>
      <div class="value">$flooded_roads</div>
      <div class="sub">$pct_roads of $total_roads road segments</div>
      <div class="meter"><i style="width:$pct_roads_w%"></i></div>
    </div>
    <div class="card kpi settlements">
      <div class="label">Cut-off settlements</div>
      <div class="value">$cutoff_settlements</div>
      <div class="sub">$pct_cutoff of $total_settlements settlements lost road access</div>
      <div class="meter"><i style="width:$pct_cutoff_w%"></i></div>
    </div>
    <div class="card kpi model">
      <div class="label">Susceptibility model</div>
      <div class="value">$auc <span class="sub">AUC</span></div>
      <div class="sub">F1 $f1 at threshold $threshold · $n_features features</div>
      <div class="meter"><i style="width:$auc_w%"></i></div>
    </div>
  </div>
</section>

<section id="maps" aria-labelledby="maps-head">
  <div class="section-head"><h2 id="maps-head">Maps</h2><p class="muted">Click any map to enlarge. The flood mask is a raw raster; use the toggle to view it on a light background.</p></div>
  <div class="figgrid">
$figures
  </div>
</section>

<section id="model" aria-labelledby="model-head">
  <div class="section-head"><h2 id="model-head">Susceptibility model</h2><p class="muted">XGBoost classifier, 70/30 split, negatives undersampled $neg_ratio:1 in training only.</p></div>
  <div class="model-grid">
    <div class="card"><div class="pad">
      <div class="metrics">
        <div class="metric"><div class="v">$auc</div><div class="k">ROC AUC (held-out)</div></div>
        <div class="metric"><div class="v">$f1</div><div class="k">Best F1</div></div>
        <div class="metric"><div class="v">$threshold</div><div class="k">Probability threshold</div></div>
        <div class="metric"><div class="v">$n_features</div><div class="k">Input features</div></div>
      </div>
      <h3>Feature importance</h3>
      <p class="muted" style="margin-top:0">Gain-based importance from the trained booster. Radar change dominates; slope and distance to lowland add the terrain context.</p>
      <div class="fi-wrap">$feature_chart</div>
      <details><summary>Raw model metadata</summary><pre>$model_meta_json</pre></details>
    </div></div>
    <div class="card"><div class="pad" style="padding-bottom:6px">
      <h3>What the features mean</h3>
      <p class="muted" style="margin-top:0">All layers are sampled on the same $pixel_size m grid.</p>
    </div>
      <table>
        <thead><tr><th>Feature</th><th class="num">Importance</th></tr></thead>
        <tbody>$feature_rows</tbody>
      </table>
    </div>
  </div>
</section>

<section id="settlements" aria-labelledby="settle-head">
  <div class="section-head"><h2 id="settle-head">Cut-off settlements</h2><p class="muted">$cutoff_settlements of $total_settlements OpenStreetMap places lost every road connection once flooded segments were removed.</p></div>
  <div class="settle-grid">
    <div class="card" style="overflow:hidden">
      <div id="settlement-map" role="region" aria-label="Map of cut-off settlements"></div>
      <div class="map-legend">
        <span><i style="--c:var(--building)"></i>Cut-off settlement</span>
        <span><i class="hollow" style="--c:var(--muted)"></i>Still connected</span>
        <span><i class="hollow" style="--c:var(--accent);border-radius:2px"></i>Area of interest</span>
      </div>
    </div>
    <div class="card" style="overflow:hidden">
      <div class="toolbar">
        <input id="settle-search" type="search" placeholder="Search by place type or OSM id…" aria-label="Search settlements">
        <select id="settle-type" aria-label="Filter by place type">
          <option value="">All types</option>
$type_options
        </select>
        <span class="count" id="settle-count"></span>
      </div>
      <div class="table-scroll">
        <table id="settle-table">
          <thead><tr>
            <th class="sortable" data-key="type">Type</th>
            <th class="sortable" data-key="id">OSM id</th>
            <th class="sortable num" data-key="lat">Lat</th>
            <th class="sortable num" data-key="lon">Lon</th>
            <th></th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>
$locality_block
</section>

<section id="methods" aria-labelledby="methods-head">
  <div class="section-head"><h2 id="methods-head">How it was made</h2><p class="muted">Five steps, all reproducible from the <code>src/</code> package.</p></div>
  <div class="steps">
$method_steps
  </div>
  <h3 style="margin-top:22px">Limitations</h3>
  <div class="callouts">
$limitations
  </div>
</section>

<section id="data" aria-labelledby="data-head">
  <div class="section-head"><h2 id="data-head">Output files</h2><p class="muted">Links resolve when this page is opened from the <code>outputs/</code> folder.</p></div>
  <div class="card" style="overflow:hidden">
    <table>
      <thead><tr><th>File</th><th>Contents</th><th>Format</th><th class="num">Size</th></tr></thead>
      <tbody>$data_rows</tbody>
    </table>
  </div>
</section>
</main>

<footer><div class="wrap">
  <span>Generated $generated_at$commit_note</span>
  <span>Data: Copernicus Sentinel-1 · OpenStreetMap contributors · 30 m DEM</span>
</div></footer>

<div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="Enlarged map">
  <div class="lb-bar"><span id="lb-title"></span><span><button class="btn" id="lb-fit">Fit / 100%</button> <button class="btn" id="lb-close">Close ✕</button></span></div>
  <img id="lb-img" alt="">
</div>

<script id="dash-data" type="application/json">$dash_json</script>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
<script>
(function(){
  var DASH = JSON.parse(document.getElementById('dash-data').textContent);
  var root = document.documentElement;

  /* theme */
  var toggle = document.getElementById('theme-toggle');
  var saved = null;
  try { saved = localStorage.getItem('trishuli-theme'); } catch (e) {}
  if (saved) root.setAttribute('data-theme', saved);
  toggle.addEventListener('click', function(){
    var dark = root.getAttribute('data-theme') === 'dark' ||
      (!root.getAttribute('data-theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try { localStorage.setItem('trishuli-theme', next); } catch (e) {}
  });

  /* active nav link */
  var links = Array.prototype.slice.call(document.querySelectorAll('.nav-links a'));
  var targets = links.map(function(a){ return document.querySelector(a.getAttribute('href')); });
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if (!en.isIntersecting) return;
        links.forEach(function(a){ a.classList.toggle('active', a.getAttribute('href') === '#' + en.target.id); });
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    targets.forEach(function(t){ if (t) io.observe(t); });
  }

  /* lightbox */
  var lb = document.getElementById('lightbox'), lbImg = document.getElementById('lb-img'), lbTitle = document.getElementById('lb-title');
  function openLb(src, title){ lbImg.src = src; lbImg.alt = title; lbTitle.textContent = title; lb.classList.add('open'); lb.classList.remove('full'); document.body.style.overflow = 'hidden'; }
  function closeLb(){ lb.classList.remove('open'); document.body.style.overflow = ''; }
  document.querySelectorAll('.fig .frame img').forEach(function(img){
    img.parentNode.addEventListener('click', function(){ openLb(img.src, img.alt); });
  });
  document.getElementById('lb-close').addEventListener('click', function(e){ e.stopPropagation(); closeLb(); });
  document.getElementById('lb-fit').addEventListener('click', function(e){ e.stopPropagation(); lb.classList.toggle('full'); });
  lbImg.addEventListener('click', function(e){ e.stopPropagation(); lb.classList.toggle('full'); });
  lb.addEventListener('click', closeLb);
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && lb.classList.contains('open')) closeLb(); });

  /* flood-mask background toggle */
  document.querySelectorAll('[data-invert]').forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      var frame = document.getElementById(btn.getAttribute('data-invert'));
      var on = frame.classList.toggle('inverted');
      frame.classList.toggle('dark', !on);
      btn.textContent = on ? 'Dark background' : 'Light background';
    });
  });

  /* settlements: map */
  var mapEl = document.getElementById('settlement-map');
  var map = null, markers = {};
  var all = DASH.settlements, cut = all.filter(function(s){ return s.cut; });
  if (window.L) {
    map = L.map(mapEl, { scrollWheelZoom: false });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    var cutLayer = L.featureGroup(), okLayer = L.featureGroup();
    var b = DASH.bbox;
    var aoi = L.rectangle([[b[1], b[0]], [b[3], b[2]]], { color: '#1d6fd8', weight: 1.5, fill: false, dashArray: '6 4' });
    all.forEach(function(s){
      var m = L.circleMarker([s.lat, s.lon], s.cut
        ? { radius: 6, color: '#fff', weight: 1.5, fillColor: '#c0392b', fillOpacity: .9 }
        : { radius: 3, color: '#7f8c9b', weight: 1, fillColor: '#7f8c9b', fillOpacity: .35 });
      m.bindPopup('<b>' + h(s.label) + '</b>' + (s.cut ? 'Cut off from the road network' : 'Still connected') +
        '<br>' + s.lat.toFixed(4) + ', ' + s.lon.toFixed(4) +
        '<br><a target="_blank" rel="noopener" href="' + osmUrl(s) + '">Open in OpenStreetMap</a>');
      (s.cut ? cutLayer : okLayer).addLayer(m);
      if (s.cut) markers[s.id || s.label] = m;
    });
    aoi.addTo(map); cutLayer.addTo(map);
    L.control.layers(null, { 'Cut-off settlements': cutLayer, 'Connected settlements': okLayer, 'Area of interest': aoi }, { collapsed: true }).addTo(map);
    var bounds = cutLayer.getLayers().length ? cutLayer.getBounds().pad(0.15) : aoi.getBounds();
    map.fitBounds(bounds);
    map.on('click', function(){ map.scrollWheelZoom.enable(); });
  } else {
    mapEl.classList.add('offline');
    mapEl.innerHTML = '<div><strong>Interactive map unavailable offline.</strong><br>Connect to the internet and reload, or use the table and the OpenStreetMap links.</div>';
  }
  function h(v){ return String(v).replace(/[&<>"']/g, function(c){ return '&#' + c.charCodeAt(0) + ';'; }); }
  function osmUrl(s){ return 'https://www.openstreetmap.org/?mlat=' + s.lat + '&mlon=' + s.lon + '#map=15/' + s.lat + '/' + s.lon; }

  /* settlements: table */
  var tbody = document.querySelector('#settle-table tbody'), search = document.getElementById('settle-search'),
      typeSel = document.getElementById('settle-type'), countEl = document.getElementById('settle-count');
  var sortKey = 'type', sortDir = 1;
  function render(){
    var q = search.value.trim().toLowerCase(), t = typeSel.value;
    var rows = cut.filter(function(s){
      return (!t || s.type === t) && (!q || (s.label + ' ' + s.type + ' ' + s.id).toLowerCase().indexOf(q) !== -1);
    });
    rows.sort(function(a, b){
      var x = a[sortKey], y = b[sortKey];
      if (typeof x === 'string') { x = x.toLowerCase(); y = String(y).toLowerCase(); }
      return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
    });
    tbody.innerHTML = rows.map(function(s){
      return '<tr data-id="' + h(s.id || s.label) + '">' +
        '<td><span class="pill ' + h(s.type) + '">' + h(s.type.replace('_', ' ')) + '</span></td>' +
        '<td><a href="' + osmUrl(s) + '" target="_blank" rel="noopener" title="Open in OpenStreetMap">' + h(s.id || s.label) + '</a></td>' +
        '<td class="num">' + s.lat.toFixed(4) + '</td><td class="num">' + s.lon.toFixed(4) + '</td>' +
        '<td class="num">' + (map ? '<button class="linkbtn" data-locate>Show</button> · ' : '') +
        '<button class="linkbtn" data-copy="' + s.lat + ', ' + s.lon + '">Copy</button></td></tr>';
    }).join('');
    countEl.textContent = rows.length + ' of ' + cut.length + ' shown';
  }
  search.addEventListener('input', render);
  typeSel.addEventListener('change', render);
  document.querySelectorAll('#settle-table th.sortable').forEach(function(th){
    th.addEventListener('click', function(){
      var k = th.getAttribute('data-key');
      if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = 1; }
      document.querySelectorAll('#settle-table th.sortable').forEach(function(h){ h.classList.remove('asc', 'desc'); });
      th.classList.add(sortDir === 1 ? 'asc' : 'desc');
      render();
    });
  });
  tbody.addEventListener('click', function(e){
    var btn = e.target.closest('button'); if (!btn) return;
    var tr = e.target.closest('tr'), m = markers[tr.getAttribute('data-id')];
    if (btn.hasAttribute('data-locate') && m) {
      mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      map.setView(m.getLatLng(), Math.max(map.getZoom(), 13)); m.openPopup();
    } else if (btn.hasAttribute('data-copy')) {
      var txt = btn.getAttribute('data-copy'), old = btn.textContent;
      var done = function(){ btn.textContent = 'Copied'; setTimeout(function(){ btn.textContent = old; }, 1200); };
      if (navigator.clipboard) navigator.clipboard.writeText(txt).then(done, done); else { window.prompt('Coordinates', txt); }
    }
  });
  render();
})();
</script>
</body>
</html>
""")

# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #

def build(out_dir: Path) -> Path:
    stats = load_json(out_dir / "impact_stats.json", {})
    meta = load_json(out_dir / "model_meta.json", {})
    importance = load_json(out_dir / "feature_importance.json", {})
    raw_settlements = load_json(out_dir / "cutoff_settlements.json", [])
    if not isinstance(importance, dict):
        importance = {}

    settlements = [settlement_record(x) for x in raw_settlements if isinstance(x, dict)]
    cut = [s for s in settlements if s["cut"]]
    total_settlements = stats.get("total_settlements", len(settlements))
    cutoff_settlements = stats.get("cutoff_settlements", len(cut))

    total_b, flooded_b = stats.get("total_buildings"), stats.get("flooded_buildings")
    total_r, flooded_r = stats.get("total_roads"), stats.get("flooded_roads")

    def width(part, whole):
        try:
            return f"{min(100.0, 100 * part / whole):.2f}"
        except (TypeError, ZeroDivisionError):
            return "0"

    auc = meta.get("auc")
    f1 = meta.get("f1_at_optimal")
    threshold = meta.get("optimal_threshold")

    # Figures ---------------------------------------------------------------
    legends = {
        "flood_mask": ("Flooded", "var(--water)"),
        "susceptibility": ("High probability", "#9e0c2a"),
        "buildings": ("Building", "var(--building)"),
        "roads": ("Road", "var(--road)"),
    }
    fig_html = []
    for key, fname, title, caption, dark in FIGURES:
        uri = image_data_uri(out_dir / fname)
        legend_label, legend_color = legends[key]
        if uri:
            frame = (f'<div class="frame{" dark" if dark else ""}" id="frame-{key}">'
                     f'<img src="{uri}" alt="{esc(title)}" loading="lazy"><span class="zoom">Click to enlarge</span></div>')
        else:
            frame = f'<div class="frame"><div class="missing">{esc(fname)} not found. Run the pipeline step that produces it.</div></div>'
        toggle = (f' <button class="btn" data-invert="frame-{key}" style="font-size:.78rem;padding:3px 8px">Light background</button>'
                  if dark and uri else "")
        fig_html.append(
            f'<figure class="card fig" style="margin:0">{frame}'
            f'<figcaption class="caption"><h3><span>{esc(title)}</span>'
            f'<span class="legend"><i style="--c:{legend_color}"></i>{esc(legend_label)}{toggle}</span></h3>'
            f'<p>{esc(caption)}</p></figcaption></figure>'
        )

    # Model -----------------------------------------------------------------
    feature_rows = []
    order = meta.get("features") or list(FEATURE_GLOSSARY)
    for key in order:
        name, desc = FEATURE_GLOSSARY.get(key, (key, ""))
        imp = importance.get(key)
        feature_rows.append(
            f"<tr><td><b>{esc(name)}</b> <code class='muted' style='font-size:.78rem'>{esc(key)}</code>"
            f"<div class='muted' style='font-size:.86rem'>{esc(desc)}</div></td>"
            f"<td class='num'>{'—' if imp is None else f'{imp:.3f}'}</td></tr>"
        )

    # Settlements -----------------------------------------------------------
    type_counts: dict[str, int] = {}
    for s in cut:
        type_counts[s["type"]] = type_counts.get(s["type"], 0) + 1
    type_options = "\n".join(
        f'          <option value="{esc(t)}">{esc(t.replace("_", " ").title())} ({n})</option>'
        for t, n in sorted(type_counts.items(), key=lambda kv: -kv[1])
    )

    loc_rows, tagged = locality_rows(out_dir / "impact_by_district.csv", flooded_b or 0)
    if loc_rows:
        coverage = pct(tagged, flooded_b) if flooded_b else "—"
        locality_block = f"""
  <div class="card" style="margin-top:16px;overflow:hidden">
    <div class="pad" style="padding-bottom:8px">
      <h3>Flooded buildings by tagged locality</h3>
      <p class="muted" style="margin:0">Only {tagged:,} of the {fmt_int(flooded_b)} flooded buildings ({coverage}) carry an
      OpenStreetMap <code>addr:city</code> tag, so this ranks where tagging is dense rather than where damage is worst.
      Spelling variants were merged.</p>
    </div>
    <table>
      <thead><tr><th>Locality</th><th class="num">Buildings</th><th></th></tr></thead>
      <tbody>{loc_rows}</tbody>
    </table>
  </div>"""
    else:
        locality_block = ""

    # Methods / data --------------------------------------------------------
    method_steps = "\n".join(
        f'    <div class="card step"><h3>{esc(t)}</h3><p>{esc(d)}</p></div>' for t, d in METHOD_STEPS)
    limitations = "\n".join(f'    <div class="callout">{esc(x)}</div>' for x in LIMITATIONS)

    data_rows = []
    for fname, desc, fmt in DATA_FILES:
        p = out_dir / fname
        if not p.exists():
            continue
        data_rows.append(
            f'<tr><td><a href="{esc(fname)}">{esc(fname)}</a></td><td class="muted">{esc(desc)}</td>'
            f'<td>{esc(fmt)}</td><td class="num">{human_size(p.stat().st_size)}</td></tr>'
        )

    dash = {
        "bbox": list(config.BBOX),
        "settlements": [
            {"label": s["label"], "type": s["type"], "id": s["id"],
             "lat": s["lat"], "lon": s["lon"], "cut": s["cut"]} for s in settlements
        ],
    }
    # Escape characters that could terminate the <script> block or inject markup.
    dash_json = (json.dumps(dash, separators=(",", ":"))
                 .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))

    flood_date = datetime.strptime(config.FLOOD_DATE, "%Y-%m-%d")
    commit = git_commit()
    bbox = config.BBOX
    page = PAGE.substitute(
        flood_date=esc(config.FLOOD_DATE),
        flood_date_long=f"{flood_date.day} {flood_date:%B %Y}",
        pre_date=esc(config.PRE_DATE), post_date=esc(config.POST_DATE),
        pixel_size=esc(config.PIXEL_SIZE), crs=esc(config.CRS),
        bbox=f"{bbox[0]:.1f}–{bbox[2]:.1f}°E · {bbox[1]:.1f}–{bbox[3]:.1f}°N",
        osm_date=esc(config.OSM_SNAPSHOT_DATE),
        flooded_buildings=fmt_int(flooded_b), total_buildings=fmt_int(total_b),
        pct_buildings=pct(flooded_b, total_b), pct_buildings_w=width(flooded_b, total_b),
        flooded_roads=fmt_int(flooded_r), total_roads=fmt_int(total_r),
        pct_roads=pct(flooded_r, total_r), pct_roads_w=width(flooded_r, total_r),
        cutoff_settlements=fmt_int(cutoff_settlements), total_settlements=fmt_int(total_settlements),
        pct_cutoff=pct(cutoff_settlements, total_settlements),
        pct_cutoff_w=width(cutoff_settlements, total_settlements),
        auc="—" if auc is None else f"{auc:.3f}", auc_w="0" if auc is None else f"{100 * auc:.1f}",
        f1="—" if f1 is None else f"{f1:.2f}",
        threshold="—" if threshold is None else f"{threshold:.2f}",
        n_features=esc(meta.get("n_features", len(order))),
        neg_ratio=esc(meta.get("neg_ratio", "—")),
        figures="\n".join(fig_html),
        feature_chart=feature_chart_svg(importance),
        feature_rows="\n".join(feature_rows),
        model_meta_json=esc(json.dumps(meta, indent=2)),
        type_options=type_options,
        locality_block=locality_block,
        method_steps=method_steps,
        limitations=limitations,
        data_rows="\n".join(data_rows) or '<tr><td colspan="4" class="muted">No output files found.</td></tr>',
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        commit_note=f" · commit {esc(commit)}" if commit else "",
        dash_json=dash_json,
    )

    out_path = out_dir / "dashboard.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default=str(ROOT / config.OUTPUT_DIR),
                        help="folder holding the pipeline outputs (default: outputs/)")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir).resolve()
    if not out_dir.is_dir():
        print(f"❌ {out_dir} is not a directory", file=sys.stderr)
        return 1
    path = build(out_dir)
    print(f"✅ {os.path.relpath(path, ROOT)} written ({human_size(path.stat().st_size)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
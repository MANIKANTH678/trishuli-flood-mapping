"""Project configuration. Secrets come from environment variables, never from this file."""
import os
from pathlib import Path

FLOOD_DATE = "2026-08-26"
PRE_DATE = "2026-08-16"
POST_DATE = "2026-08-28"
OSM_SNAPSHOT_DATE = "2026-07-27"

def _env(name, default=""):
    """Read an env var, tolerating quotes/spaces added by cmd's `set NAME="value"`."""
    return os.environ.get(name, default).strip().strip("\"'").strip()


# Copernicus Data Space credentials (used by src/fetch/fetch_sentinel1.py).
# In cmd:  set COPERNICUS_USER=you@example.com   and   set COPERNICUS_PASS=your-password
COPERNICUS_USER = _env("COPERNICUS_USER")
COPERNICUS_PASS = _env("COPERNICUS_PASS")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

S1_DIR = DATA_DIR / "raw" / "sentinel1"
DEM_DIR = DATA_DIR / "raw" / "dem"
S2_PRE_DIR = DATA_DIR / "raw" / "sentinel2" / "pre"      # optional
S2_POST_DIR = DATA_DIR / "raw" / "sentinel2" / "post"    # optional
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = BASE_DIR / "outputs"

# The tightened Rasuwa corridor bounding box: [west, south, east, north]
BBOX = [84.95, 27.80, 85.55, 28.35]

CRS = "EPSG:32645"      # matches TARGET_EPSG in geocode_s1.py
PIXEL_SIZE = 30         # metres

# --- Step 10.3: per-run configuration -------------------------------------------------------------------------
# src/run.py writes run.json at the repo root (bbox, event date, selected track and dates, area name). When it exists
# it overrides the case-study constants above, so older scripts keep working and the defaults reproduce the
# Trishuli case study when there is no run.json.
import json
_RUN = json.loads((BASE_DIR / "run.json").read_text(encoding="utf-8")) if (BASE_DIR / "run.json").exists() else {}
RUN = _RUN
FLOOD_DATE = _RUN.get("event_date", "2026-08-26")
PRE_DATE, POST_DATE = (_RUN.get("pre_dates") or ["2026-08-16"])[0], _RUN.get("post_date", "2026-08-28")
OSM_SNAPSHOT_DATE = _RUN.get("osm_snapshot", "2026-07-27")
if "bbox" in _RUN: BBOX = list(map(float, _RUN["bbox"].split(",")))
if "epsg" in _RUN: CRS = f"EPSG:{_RUN['epsg']}"
TRACK = _RUN.get("track", "asc85")
REF_SPLITS = ["pre", "placebo", "pre3", "pre4"]                       # nearest pre-event date first
REF_DATES = dict(zip(REF_SPLITS, _RUN.get("pre_dates") or ["2026-08-16", "2026-08-04", "2026-07-23", "2026-07-11"]))
REF_DATES["post"] = POST_DATE
AREA_NAME = _RUN.get("name_long") or ("Trishuli / Bhote Koshi, Rasuwa, Nepal" if not _RUN else _RUN.get("name", "area"))
TITLE = _RUN.get("title") or (f"Trishuli / Bhote Koshi flood, {FLOOD_DATE}" if not _RUN else f"{AREA_NAME}: Sentinel-1 change, event {FLOOD_DATE}")
CASE_STUDY = not _RUN or _RUN.get("case_study", False)              # case-study-only evidence sections are optional anyway
S1_SOURCE = _RUN.get("s1_source", "snap")                            # snap = SNAP sigma0 (headline); pc = PC RTC gamma0 cross-check
S1_SOURCE_LABEL = "PC RTC gamma0, cross-check route" if S1_SOURCE == "pc" else "SNAP sigma0 (terrain-corrected)"
COPERNICUS_USER, COPERNICUS_PASS = _env("COPERNICUS_USER") or None, _env("COPERNICUS_PASS") or None

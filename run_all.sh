#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
BBOX="${1:-84.95,27.80,85.55,28.35}"
SPLITS="pre,placebo,pre3,pre4,post"
EVENT_DATE="2026-08-26"

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=python; fi

echo "=== Trishuli flood pipeline  bbox=$BBOX ==="

echo "[1/12] fetch Sentinel-1"
$PY src/fetch/fetch_sentinel1.py --download

echo "[2/12] unzip scenes"
$PY -c "import pathlib, zipfile; [zipfile.ZipFile(z).extractall(z.parent) for p in ['data/raw/sentinel1/'+s for s in '$SPLITS'.split(',')] for z in pathlib.Path(p).glob('*.SAFE.zip') if not z.with_suffix('').exists()]"

echo "[3/12] orbit / pass / 12-day gate"        # exits 1 and stops the pipeline on violation
$PY src/processing/align_v2_checks.py
$PY -m src.processing.check_stack "$SPLITS"

echo "[4/12] fetch OSM"                          # no fallback: failure must stop the run
# event = flood date; fetch_osm snapshots 30 days earlier (2026-07-27, pre-event)
$PY -m src.download.fetch_osm --bbox "$BBOX" --event-date "$EVENT_DATE" --out data/raw/osm

EPSG=$($PY -c "from src.processing.grid import utm_epsg as u; w,s,e,n=map(float,'$BBOX'.split(',')); print(u((w+e)/2,(s+n)/2))" | tr -d '\r')

echo "[5/12] DEM (Copernicus GLO-30)"
$PY -m src.fetch.fetch_dem --bbox "$BBOX"

echo "[6/12] S1 SNAP preprocessing"
$PY -m src.processing.s1_preprocess --bbox "$BBOX" --epsg "$EPSG" --splits "$SPLITS"

echo "[7/12] grid + dB"
$PY -m src.processing.s1_to_grid --bbox "$BBOX" --epsg "$EPSG" --splits "$SPLITS"

echo "[8/12] change detection (geometry, HAND, radar mask, null calibration, detector)"
$PY -m src.analysis.geometry --bbox "$BBOX"
$PY -m src.analysis.hand
$PY -m src.analysis.radar_mask
$PY -m src.analysis.calibrate_null
$PY -m src.analysis.detect

echo "[8b/12] Sentinel-2 branch + fusion (must run before damage and cutoff)"
$PY -m src.fetch.s2_search --bbox "$BBOX" --event-date "$EVENT_DATE"
$PY -m src.processing.s2_ingest --bbox "$BBOX" --epsg "$EPSG" --dates "$(cat data/raw/s2/dates.txt)"
$PY -m src.analysis.s2_detect --event "$EVENT_DATE"
$PY -m src.analysis.fuse

echo "[9/12] damage"
$PY tools/make_sens_masks.py
$PY -m src.processing.damage_v2

echo "[9b/12] cutoff (hospital reachability; the report checks this is newer than flood_mask.tif)"
$PY -m src.processing.cutoff_v2

echo "[10/12] validation (EMSR927, check-only)"
HAVE_EMSR=0
if [ -d data/external/EMSR927 ]; then
  HAVE_EMSR=1
  $PY src/validation/emsr927_comparison.py
  $PY src/validation/damage_sanity_check.py
else
  echo "  EMSR927 folder absent, skipping validation"
fi

echo "[11/12] mask validation (must be newer than flood_mask.tif for the report)"
$PY tools/signal_check.py
$PY tools/unet_corridor.py
if [ "$HAVE_EMSR" -eq 1 ]; then
  $PY tools/null_recall_aoi.py
fi

echo "[12/12] maps, dashboard, slides, situation report"
$PY src/report/impact.py
$PY -m src.report.dashboard_full
$PY src/report/slides.py
$PY src/report/situation_report.py

echo "=== DONE ==="
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
BBOX="${1:-84.95,27.80,85.55,28.35}"

echo "=== Trishuli flood pipeline  bbox=$BBOX ==="

echo "[1/12] fetch Sentinel-1"
python src/fetch/fetch_sentinel1.py --download

echo "[2/12] unzip scenes"
python -c "import pathlib, zipfile; [zipfile.ZipFile(z).extractall(z.parent) for p in ['data/raw/sentinel1/pre', 'data/raw/sentinel1/post'] for z in pathlib.Path(p).glob('*.SAFE.zip') if not z.with_suffix('').exists()]"

echo "[3/12] orbit / pass / 12-day gate"        # exits 1 and stops the pipeline on violation
python src/processing/align_v2_checks.py

echo "[4/12] fetch OSM"                          # no fallback: failure must stop the run
if [ "${SKIP_OSM:-0}" = "1" ]; then
  echo "  SKIP_OSM=1: using existing data/raw/osm"
else
  # event = flood date; fetch_osm snapshots 30 days earlier (2026-07-27, pre-event)
  python -m src.download.fetch_osm --bbox "$BBOX" --event-date "2026-08-26" --out data/raw/osm
fi

EPSG=$(python -c "from src.processing.grid import utm_epsg as u; w,s,e,n=map(float,'$BBOX'.split(',')); print(u((w+e)/2,(s+n)/2))")

echo "[5/12] DEM (Copernicus GLO-30)"
python -m src.fetch.fetch_dem --bbox "$BBOX"

echo "[6/12] S1 SNAP preprocessing"
python -m src.processing.s1_preprocess --bbox "$BBOX" --epsg "$EPSG"

echo "[7/12] grid + dB"
python -m src.processing.s1_to_grid --bbox "$BBOX" --epsg "$EPSG"

echo "[8/12] flood detect"
python src/processing/flood_detect_v2.py

echo "[9/12] damage"
python src/processing/damage_v2.py

echo "[9b/12] cutoff (hospital reachability; the report checks this is newer than flood_mask.tif)"
python src/processing/cutoff_v2.py

echo "[10/12] validation (EMSR927, check-only)"
HAVE_EMSR=0
if [ -d data/external/EMSR927 ]; then
  HAVE_EMSR=1
  python src/validation/emsr927_comparison.py
  python src/validation/damage_sanity_check.py
else
  echo "  EMSR927 folder absent, skipping validation"
fi

echo "[11/12] mask validation (must be newer than flood_mask.tif for the report)"
python tools/signal_check.py
python tools/unet_corridor.py
if [ "$HAVE_EMSR" -eq 1 ]; then
  python tools/null_recall_aoi.py
fi

echo "[12/12] maps, dashboard, slides, situation report"
python src/report/impact.py
python -m src.report.dashboard_full
python src/report/slides.py
if [ "$HAVE_EMSR" -eq 1 ]; then
  python src/report/situation_report.py
else
  echo "  null_recall_aoi did not run (needs EMSR927), so the report would refuse; skipping situation report"
fi

echo "=== DONE ==="
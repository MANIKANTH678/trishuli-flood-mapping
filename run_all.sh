#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
BBOX="${1:-84.95,27.80,85.55,28.35}"

echo "=== Trishuli flood pipeline  bbox=$BBOX ==="

echo "[1/10] fetch Sentinel-1"
python src/fetch/fetch_sentinel1.py --download

echo "[2/10] unzip scenes"
python -c "import pathlib, zipfile; [zipfile.ZipFile(z).extractall(z.parent) for p in ['data/raw/sentinel1/pre', 'data/raw/sentinel1/post'] for z in pathlib.Path(p).glob('*.SAFE.zip') if not z.with_suffix('').exists()]"

echo "[3/10] orbit / pass / 12-day gate"        # exits 1 and stops the pipeline on violation
python src/processing/align_v2_checks.py

echo "[4/10] fetch OSM"                          # no fallback: failure must stop the run
python -m src.download.fetch_osm --bbox "$BBOX" --event-date "2026-07-27" --out data/raw/osm

EPSG=$(python -c "from src.processing.grid import utm_epsg as u; w,s,e,n=map(float,'$BBOX'.split(',')); print(u((w+e)/2,(s+n)/2))")

echo "[5/10] DEM (Copernicus GLO-30)"
python -m src.fetch.fetch_dem --bbox "$BBOX"

echo "[6/10] S1 SNAP preprocessing"
python -m src.processing.s1_preprocess --bbox "$BBOX" --epsg "$EPSG"

echo "[7/10] grid + dB"
python -m src.processing.s1_to_grid --bbox "$BBOX" --epsg "$EPSG"

echo "[8/10] flood detect"
python src/processing/flood_detect_v2.py

echo "[9/10] damage"
python src/processing/damage_v2.py

echo "[10/10] validation (EMSR927, check-only)"
if [ -d data/external/EMSR927 ]; then
  python src/validation/emsr927_comparison.py
  python src/validation/damage_sanity_check.py
else
  echo "  EMSR927 folder absent, skipping validation"
fi

echo "=== DONE ==="
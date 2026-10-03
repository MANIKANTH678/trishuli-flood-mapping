#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
BBOX="${1:-84.50,27.40,86.00,28.40}"

echo "=== Trishuli flood pipeline  bbox=$BBOX ==="

echo "[1/9] fetch Sentinel-1"
python src/fetch/fetch_sentinel1.py --download

echo "[2/9] unzip scenes"
for z in data/raw/s1/pre/*.zip data/raw/s1/post/*.zip; do
  unzip -n -q "\(z" -d "\)(dirname "$z")"
done

echo "[3/9] orbit / pass / 12-day gate"          # exits 1 and stops the pipeline on violation
python src/processing/align_v2_checks.py

echo "[4/9] fetch OSM"                           # no fallback: failure must stop the run
python -m src.download.fetch_osm --bbox "$BBOX" --date 2026-07-27 --out data/raw/osm

echo "[5/9] geocode S1"
python src/processing/geocode_s1.py

echo "[6/9] align"
python src/processing/align.py

echo "[7/9] flood detect"
python src/processing/flood_detect_v2.py

echo "[8/9] damage"
python src/processing/damage_v2.py

echo "[9/9] validation (EMSR927, check-only)"
if [ -d data/external/EMSR927 ]; then
  python src/validation/emsr927_comparison.py
  python src/validation/damage_sanity_check.py
else
  echo "  EMSR927 folder absent, skipping validation"
fi

echo "=== DONE ==="

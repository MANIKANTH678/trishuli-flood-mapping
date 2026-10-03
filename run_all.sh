#!/usr/bin/env bash
set -e
BBOX="${1:-84.50,27.40,86.00,28.40}"
PRE_DATE="${2:-2026-08-16}"
POST_DATE="${3:-2026-08-28}"
echo "=== Trishuli flood pipeline ==="
echo "bbox=$BBOX  pre=$PRE_DATE  post=$POST_DATE"

echo "[1/8] fetch Sentinel-1 (pre + post, password auth via src/config.py)"
python src/fetch/fetch_sentinel1.py --download

echo "[2/8] fetch OSM (pre-flood snapshot)"
python -m src.download.fetch_osm --bbox "$BBOX" --date 2026-07-27 --out data/raw/osm || \
  echo "  (fetch_osm failed — reuse existing data/raw/osm/)"

echo "[3/8] geocode S1 SAFE → georeferenced TIFFs (EPSG:32645)"
python src/processing/geocode_s1.py

echo "[4/8] align (DEM + S1 + S2 → 30 m UTM 45N grid)"
python src/processing/align.py

echo "[5/8] flood detect v2"
python src/processing/flood_detect_v2.py

echo "[6/8] damage v2"
python src/processing/damage_v2.py

echo "[7/8] EMSR927 validation"
python src/validation/emsr927_comparison.py \
  --flood-mask data/processed/flood_mask.tif \
  --emsr-dir data/external/EMSR927 \
  --out data/processed/emsr927_comparison.json

echo "[8/8] damage sanity check"
python src/validation/damage_sanity_check.py

echo "=== DONE ==="

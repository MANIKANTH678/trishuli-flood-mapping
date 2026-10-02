#!/usr/bin/env bash
set -e
BBOX="${1:-84.30,27.85,84.45,28.00}"
DATE="${2:-2026-08-20}"
echo "=== Trishuli flood pipeline ==="
echo "bbox=$BBOX  date=$DATE"

echo "[1/8] fetch Sentinel-1"
python -m src.download.fetch_sentinel1 --bbox "$BBOX" --start "$DATE" --end "$DATE" --out data/raw/s1 --max 1

echo "[2/8] fetch OSM"
python -m src.download.fetch_osm --bbox "$BBOX" --date "$DATE" --out data/raw/osm

echo "[3/8] align"
python -m src.processing.align

echo "[4/8] flood detect v2"
python -m src.processing.flood_detect_v2

echo "[5/8] damage v2"
python -m src.processing.damage_v2

echo "[6/8] cutoff"
python -m src.processing.cutoff

echo "[7/8] impact"
python -m src.report.impact || true

echo "[8/8] dashboard"
python -m src.report.dashboard_full || true

echo "=== DONE ==="

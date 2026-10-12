#!/usr/bin/env bash
# Retired in Step 10: thin wrapper over the one entry point, src/run.py (fail-fast, timings, resume, clean-run check).
# Every stage, its order and its CLI now live in src/run.py; nothing is duplicated here.
#
#   ./run_all.sh                                   # Trishuli case study, SNAP route (needs COPERNICUS_USER/PASS + SNAP gpt)
#   ./run_all.sh 84.3,26.9,84.9,27.4 2026-08-26 --profile fast --s1-source pc --name terai
#   ./run_all.sh <bbox> <event-date> --from-stage detect
set -euo pipefail
cd "$(dirname "$0")"
BBOX="${1:-84.95,27.80,85.55,28.35}"
EVENT_DATE="${2:-2026-08-26}"
shift $(( $# >= 2 ? 2 : $# ))

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else PY=python; fi

exec "$PY" -m src.run --bbox "$BBOX" --event-date "$EVENT_DATE" "$@"

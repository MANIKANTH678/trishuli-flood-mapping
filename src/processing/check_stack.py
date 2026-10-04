import sys
from datetime import datetime
from pathlib import Path
from src.processing.align_v2_checks import read_manifest

S1, splits, rows = Path("data/raw/sentinel1"), sys.argv[1].split(","), {}
for sp in splits:
    ms = [read_manifest(d) for d in sorted((S1 / sp).glob("*.SAFE"))]
    ms = [m for m in ms if m]
    if not ms: sys.exit(f"FAIL: no scenes in {sp}")
    rows[sp] = (min(datetime.fromisoformat(m["start"].replace("Z", "+00:00")) for m in ms),
                {m["relOrbit"] for m in ms}, {m["pass"] for m in ms})
orbits = set().union(*[r[1] for r in rows.values()]); passes = set().union(*[r[2] for r in rows.values()])
anchor = rows[splits[0]][0]; ok = len(orbits) == 1 and len(passes) == 1
for sp, (t, _, _) in rows.items():
    d = (t - anchor).total_seconds() / 86400
    print(f"{sp:8s} {t:%Y-%m-%d %H:%M}  {d:+7.2f} d"); ok &= abs(d - 12 * round(d / 12)) < 0.1
print("orbits", orbits, "passes", passes); sys.exit(0 if ok else 1)
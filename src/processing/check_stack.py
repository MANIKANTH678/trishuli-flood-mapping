"""Stack check (Step 10.1): every split must be the same relative orbit and pass (fatal). Date offsets that are not a
multiple of the 6/12-day repeat, first-frame times more than 10 min apart (Step 11)
and mixed platforms (S1A next to S1D) only print a WARNING.

python -m src.processing.check_stack pre,placebo,pre3,pre4,post"""
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
tod = [t.hour * 60 + t.minute for t, _, _ in rows.values()]
if max(tod) - min(tod) > 10: print(f"WARNING: acquisition times differ by {max(tod) - min(tod)} min: not the same orbit track?")
plat = {sp: sorted({d.name[:3] for d in (S1 / sp).glob("*.SAFE")}) for sp in splits}
if len(set().union(*plat.values())) > 1:                  # Step 11: S1A and S1D share relative orbits at a different phase
    print(f"WARNING: the stack mixes platforms {plat}: same track, different satellite (dates can sit off the 12-day grid)")
orbits = set().union(*[r[1] for r in rows.values()]); passes = set().union(*[r[2] for r in rows.values()])
anchor = rows[splits[0]][0]; ok = len(orbits) == 1 and len(passes) == 1
for sp, (t, _, _) in rows.items():
    d = (t - anchor).total_seconds() / 86400
    print(f"{sp:8s} {t:%Y-%m-%d %H:%M}  {d:+7.2f} d")
    if abs(d - 6 * round(d / 6)) >= 0.1:                  # Step 10.1: a warning, not a failure
        print(f"WARNING: {sp} is {d:+.2f} d from {splits[0]}, not a multiple of the 6/12-day repeat (same-track geometry is what matters)")
print("orbits", orbits, "passes", passes)
if not ok: print("FAIL: the stack mixes relative orbits or passes")
sys.exit(0 if ok else 1)
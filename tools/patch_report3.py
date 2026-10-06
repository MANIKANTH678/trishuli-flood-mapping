from pathlib import Path
P = Path("src/report/situation_report.py")
t = P.read_text(encoding="utf-8")

def rep(old, new):
    global t
    if old not in t: raise SystemExit(f"NOT FOUND: {old[:80]}")
    t = t.replace(old, new)

# 1. variable clash: rename my Step 3 args variable (keep the area variable a3 intact)
rep('a3 = s3e["args"]', 's3a = s3e["args"]')
rep("Step 3 test ({a3['first']} → {a3['second']}; pixels flagged as decreases by robust z at threshold {a3['thr']:g})",
    "Step 3 test ({s3a['first']} → {s3a['second']}; pixels flagged as decreases by robust z at threshold {s3a['thr']:g})")

# 2. dates for all split names (from compare_pairs.py labels; verify against your scenes)
rep('REF_DATES = {"pre": config.PRE_DATE, "post": config.POST_DATE}   # add "placebo": "...", "pre3": "...", "pre4": "..."',
    'REF_DATES = {"pre": config.PRE_DATE, "post": config.POST_DATE, "placebo": "2026-08-04", "pre3": "2026-07-23", "pre4": "2026-07-11"}')

P.write_text(t, encoding="utf-8"); print("patched")
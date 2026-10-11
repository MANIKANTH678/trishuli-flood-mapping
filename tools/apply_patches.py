"""Small, idempotent edits to existing files (run once from the repo root; safe to re-run).
Each edit looks for an exact anchor; if the anchor is missing it says so and changes nothing in that file.
A .bak copy is written before the first change.

1. src/report/situation_report.py
   - one-page footer: the three required attribution strings, verbatim
   - both reports: the class-null statement from outputs/validation/class_nulls.json in the Situation text
2. src/report/dashboard.py
   - panel: the class-null statement under "not a validated flood extent"

python tools/apply_patches.py"""
import shutil
from pathlib import Path

ATTR_REQ = ('"Contains modified Copernicus Sentinel data 2026." "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus '
            'Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved." '
            '"© OpenStreetMap contributors." Full list: ATTRIBUTION.md.')
NOTE_DEF = ('_cn = ROOT / "outputs/validation/class_nulls.json"\n'
            'NULL_NOTE = "" if not _cn.exists() else " " + json.loads(_cn.read_text(encoding="utf-8"))["statement"]\n')

EDITS = {
    "src/report/situation_report.py": [
        ("try:\n    det, imp = J(DETECT), J(\"outputs/impact_summary.json\")",
         NOTE_DEF + "try:\n    det, imp = J(DETECT), J(\"outputs/impact_summary.json\")"),
        ("the result is exposure to a detected mask, **not a validated flood extent**.\"\"\"))",
         "the result is exposure to a detected mask, **not a validated flood extent**.{NULL_NOTE}\"\"\"))"),
        ("Counts below are exposure to that mask.\")", "Counts below are exposure to that mask.\" + NULL_NOTE)"),
    ],
    "src/report/dashboard.py": [
        ("    panel = (f\"<div style='position:fixed;top:10px;left:50px;",
         "    _cn = Path(\"outputs/validation/class_nulls.json\")\n"
         "    null_note = \"\" if not _cn.exists() else \"<br><b>\" + json.loads(_cn.read_text(encoding=\"utf-8\"))[\"statement\"] + \"</b>\"\n"
         "    panel = (f\"<div style='position:fixed;top:10px;left:50px;"),
        ("f\"not a validated flood extent</i><br>Detector status:", "f\"not a validated flood extent</i>{null_note}<br>Detector status:"),
    ],
}

def main():
    for f, edits in EDITS.items():
        p = Path(f)
        if not p.exists(): print(f"SKIP {f}: not found"); continue
        s = p.read_text(encoding="utf-8"); orig = s
        for old, new in edits:
            if new in s: print(f"  ok   {f}: already applied ({new[:50]!r}...)"); continue
            if old not in s: print(f"  MISS {f}: anchor not found ({old[:60]!r}...) - edit by hand"); continue
            s = s.replace(old, new, 1); print(f"  done {f}: {old[:50]!r}...")
        if s != orig:
            bak = p.with_suffix(p.suffix + ".bak")
            if not bak.exists(): shutil.copy2(p, bak)
            p.write_text(s, encoding="utf-8")

if __name__ == "__main__":
    main()

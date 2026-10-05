from pathlib import Path

def patch(path, fn):
    p = Path(path); s = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    p.write_text(fn(s), encoding="utf-8", newline="\n")

def rep(s, old, new):
    assert s.count(old) == 1, f"anchor not found exactly once: {old[:70]!r}"
    return s.replace(old, new)

def fix_report(s):
    # 1. EMS files are required only when EMS is present
    s = rep(s, '''files = ["outputs/impact_summary.json", "outputs/cutoff_settlements.json",
         "data/processed/emsr927_comparison.json", "outputs/validation/signal_check.json",
         "outputs/validation/null_recall_aoi.json", "outputs/validation/unet_corridor.json"]
''', '''files = ["outputs/impact_summary.json", "outputs/cutoff_settlements.json",
         "outputs/validation/signal_check.json", "outputs/validation/unet_corridor.json"]
have_ems = ((ROOT / "data/external/EMSR927").is_dir()
            and (ROOT / "data/processed/emsr927_comparison.json").exists()
            and (ROOT / "outputs/validation/null_recall_aoi.json").exists())
if have_ems:
    files += ["data/processed/emsr927_comparison.json", "outputs/validation/null_recall_aoi.json"]
''')
    s = rep(s, 'emsr = J("data/processed/emsr927_comparison.json")["aois"]',
               'emsr = J("data/processed/emsr927_comparison.json")["aois"] if have_ems else {}')
    s = rep(s, 'nul = J("outputs/validation/null_recall_aoi.json")',
               'nul = J("outputs/validation/null_recall_aoi.json") if have_ems else {}')
    s = rep(s, "for k, a in emsr.items():", "for k, a in (emsr.items() if have_ems else []):")

    # 2. EMS validation block, built separately
    block = '''    ems_block = ""
    if have_ems:
        ems_block = f"""## 4. Validation against Copernicus EMS (EMSR927, check-only)

> Validation only. EMS data is not an input to any map or number above.

EMSR927 mapped {tot:,} damaged structures in four Areas of Interest ({grades['Destroyed']:,} Destroyed, {grades['Damaged']:,} Damaged, {grades['Possibly damaged']:,} Possibly damaged). Per AOI, the mask hit rate on EMSR927 damage points against a random mask of the same size placed on flat pixels inside the AOI:

| AOI | Damage points | Points in raster | Inside mask | Mask px in AOI | Flat px in AOI | Observed hit | Null (mean ± sd) |
|---|---|---|---|---|---|---|---|
""" + "\\n".join(rows) + """

Where the mask has no or almost no pixels, the miss is a coverage limit of the method, not a measured detection error. Where hit rates exceed the null, the mask is associated with damage in built-up lowlands; this does not distinguish flooding from other change.
"""

'''
    s = rep(s, '    md = f"""# Situation Report', block + '    md = f"""# Situation Report')

    # 3. Section 1 without EMS numbers
    i = s.index("Copernicus EMS Rapid Mapping (EMSR927) mapped {tot:,}")
    j = s.index("\n", i)
    s = s[:i] + ("Post-event analysis of the flash flood on the Trishuli / Bhote Koshi, built from system-derived maps only "
                 "(Sentinel-1 and, where available, Sentinel-2). Copernicus EMS products are used for checking only and appear "
                 "only in the labelled validation section, when present.") + s[j:]

    # 4. Replace old section 4 (header .. closing paragraph) with the block
    a = s.index("## 4. Comparison with EMSR927 damage points")
    tail = "this does not distinguish flooding from other change.\n\n"
    b = s.index(tail, a) + len(tail)
    s = s[:a] + "{ems_block}\n\n" + s[b:]

    # 5. EMS mentions in limitations / sources only when present
    s = rep(s, "- EMSR927 GRA products contain no flood-extent layer; validation is proxy only.\n",
               "{'- EMSR927 GRA products contain no flood-extent layer; validation is proxy only.' if have_ems else ''}\n")
    s = rep(s, "- Copernicus EMS Rapid Mapping, EMSR927\n",
               "{'- Copernicus EMS Rapid Mapping, EMSR927 (validation only)' if have_ems else ''}\n")
    return s
patch("src/report/situation_report.py", fix_report)

def fix_run(s):
    return rep(s, '''if [ "$HAVE_EMSR" -eq 1 ]; then
  $PY src/report/situation_report.py
else
  echo "  null_recall_aoi did not run (needs EMSR927), so the report would refuse; skipping situation report"
fi
''', '$PY src/report/situation_report.py\n')
patch("run_all.sh", fix_run)
print("patched")

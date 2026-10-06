from pathlib import Path
def sub(path, old, new):
    p = Path(path); t = p.read_text(encoding="utf-8")
    if old not in t: print("NOT FOUND in", path, ":", old[:50]); return
    p.write_text(t.replace(old, new), encoding="utf-8"); print("fixed", path)

sub("docs/validation_log.md", "flood_mask_coverage", "the retired mask-coverage field")
sub("docs/validation_log.md", "plus the follow-up fix commit (record its hash here)", "plus a84ac96 and ff31d1c")
sub("src/report/situation_report.py", "AOI03 was not used to tune the detector.",
    "AOI03 was scored 4 times (docs/validation_log.md); S1 parameters unchanged since tag detector-frozen.")
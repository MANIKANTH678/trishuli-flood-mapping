"""The claims withdrawn in Step 0 must not come back in any source, doc or generated page (Step 9 review)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STALE = ["no flood signal could be detected", "cannot resolve the event", "thresholded dark tail", "new open water"]
SKIP = {"tests", "runs", ".git", ".venv", "venv", "doc_backups", "node_modules", "vendor", "_pre_ohsome_backup", "archive", "old_outputs"}
APPEND_ONLY = {"docs/validation_log.md"}      # dated history log: past wording is kept as a record, not a claim

def test_no_withdrawn_claims():
    hits = []
    for p in ROOT.rglob("*"):
        if p.suffix not in (".py", ".md", ".html") or not p.is_file() or SKIP & set(p.relative_to(ROOT).parts) \
                or p.relative_to(ROOT).as_posix() in APPEND_ONLY \
                or any("backup" in part.lower() for part in p.relative_to(ROOT).parts): continue
        t = p.read_text(encoding="utf-8", errors="ignore").lower()
        hits += [f"{p.relative_to(ROOT)}: {s}" for s in STALE if s in t]
    assert not hits, "\n".join(hits)

def test_retired_static_dashboard_is_gone():
    assert not (ROOT / "src/report/dashboard_full.py").exists()
    assert not (ROOT / "outputs/dashboard.html").exists()

"""src/run.py stage order and route switches (replaces test_run_all_order.py: run_all.sh is now a thin wrapper)."""
from types import SimpleNamespace
from src.run import stages, REF_SPLITS

SEL = {"pre": ["2026-08-16", "2026-08-04", "2026-07-23", "2026-07-11"], "post": "2026-08-28", "rel_orbit": 85, "pass": "ASCENDING"}

def names(source="snap", profile="full", n_pre=4):
    a = SimpleNamespace(bbox="84.95,27.80,85.55,28.35", event_date="2026-08-26", profile=profile, s1_source=source)
    return [n for n, _ in stages(a, dict(SEL, pre=SEL["pre"][:n_pre]), "32645", "asc85")]

def test_fusion_runs_before_damage_and_cutoff():
    s = names()
    assert s.index("detect") < s.index("fuse") < s.index("sens_masks") < s.index("damage") < s.index("cutoff") < s.index("dashboard") < s.index("report")

def test_pc_route_replaces_the_snap_stages_and_keeps_the_gate():
    s = names("pc", "fast")
    for gone in ("fetch_s1", "unzip_s1", "check_stack", "snap", "grid", "s2_search", "sens_masks", "ai_scenes"): assert gone not in s
    assert s.index("dem") < s.index("pc_stack") < s.index("geometry") < s.index("hand") < s.index("null_calibration") < s.index("detect")

def test_null_calibration_needs_three_references():
    assert "null_calibration" in names(n_pre=3) and "null_calibration" not in names(n_pre=2)
    assert REF_SPLITS[0] == "pre"

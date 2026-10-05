def test_fusion_runs_before_damage_and_cutoff():
    s = open("run_all.sh", encoding="utf-8").read()
    assert s.index("src.analysis.fuse") < s.index("damage_v2.py") < s.index("cutoff_v2.py")

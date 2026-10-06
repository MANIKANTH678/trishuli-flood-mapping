def test_fusion_runs_before_damage_and_cutoff():
    s = open("run_all.sh", encoding="utf-8").read()
    assert s.index("src.analysis.fuse") < s.index("tools/make_sens_masks.py") < s.index("src.processing.damage_v2") < s.index("src.processing.cutoff_v2")

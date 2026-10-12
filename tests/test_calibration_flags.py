from src.analysis.detect import calibration_flags
def test_terai_is_not_calibrated_and_case_study_is():
    t = calibration_flags({"alpha": 0.001, "null_far_max_at_t_hi": 0.0020217}, 0.0060652, 2863.85)
    c = calibration_flags({"alpha": 0.001, "null_far_max_at_t_hi": 0.00035126}, 0.0010538, 199.853)
    assert (t["calibrated"], t["min_detectable_km2"]) == (False, 17.37) and (c["calibrated"], c["min_detectable_km2"]) == (True, 0.211)

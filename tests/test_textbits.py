"""Step 11 review items 3 and 5: calibration wording, zero-count/plural/conditional sentences, GRD/RTC label."""
from src.report import textbits as T

TERAI = {"calibrated": False, "alpha_met": False, "null_far_max": 0.0020217, "gate_threshold": 0.0060652, "floor_km2": 2863.85,
         "min_detectable_km2": 17.37}
CASE = {"calibrated": True, "alpha_met": True, "null_far_max": 0.00035126, "gate_threshold": 0.0010538, "floor_km2": 199.853,
        "min_detectable_km2": 0.211}


def test_calibration_target_not_met_wording():
    assert T.cal_phrase(TERAI) == "calibration target not met; minimum detectable area ≈ 17 km²"
    assert "calibrated against" not in T.cal_phrase(TERAI)
    assert T.cal_phrase(CASE).startswith("calibrated against pre-event nulls") and "≈ 0.21 km²" in T.cal_phrase(CASE)
    assert T.cal_phrase({"calibrated": False, "null_far_max": None, "gate_threshold": None}).startswith("UNCALIBRATED")
    assert "१७" in T.cal_phrase_ne(TERAI) and "लक्ष्य पूरा भएन" in T.cal_phrase_ne(TERAI)


def test_mda_falls_back_to_gate_times_floor():
    assert T.mda_text({"gate_threshold": 0.0060652, "floor_km2": 2863.85}) == "17"
    assert T.mda_text({"gate_threshold": None}) is None


def test_plurals_and_zero_counts():
    assert T.no_route_text(1) == " (1 settlement has no pre-flood route)"
    assert T.no_route_text(141) == " (141 settlements have no pre-flood route)"
    assert T.no_route_text(0) == ""
    assert T.plural(1, "bridge") == "1 bridge" and T.plural(2, "bridge") == "2 bridges"


def test_next_steps_conditional_lines():
    none = T.next_steps(False, 0)
    assert not any("0 cut-off" in s for s in none) and not any("inside the ranges above" in s for s in none)
    assert [s[:2] for s in none] == ["1.", "2."]
    full = T.next_steps(True, 4)
    assert "inside the ranges above" in full[0] and "Check the 4 cut-off first-break points" in full[1] and full[2].startswith("3.")
    assert "Check the 1 cut-off first-break point against" in T.next_steps(True, 1)[1]


def test_rtc_is_not_labelled_grd():
    assert T.source_label(True) == "Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD)"
    assert "GRD (" not in T.source_label(True) and T.source_label(False).startswith("Sentinel-1 GRD (Copernicus Data Space")


def test_single_scenario_is_not_a_range():
    base_only = {"sensitivity": {"scenarios": {"base": {}}, "range": {"buildings_overlap": [0, 0]}}}
    full = {"sensitivity": {"scenarios": {"low": {}, "base": {}, "high": {}}, "range": {"buildings_overlap": [244, 1078]}}}
    assert T.scenario_range(base_only) == {} and T.scenario_range(full) == {"buildings_overlap": [244, 1078]}

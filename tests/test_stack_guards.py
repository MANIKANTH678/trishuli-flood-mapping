"""Step 11 review item 2: time-of-day guard (check_stack.py and the PC-route selection) and the platform-mix warning."""
from datetime import datetime
from pathlib import Path
from src.processing.stack_guards import tod_warning, stack_warnings, parse_name
from src.fetch.select_s1 import add_guards

# Dry run 1 (negative control) selection: the 06-22 reference is Sentinel-1A, the others Sentinel-1D (all rel. orbit 85 ascending)
DRY1 = {"2026-08-04": [{"name": "S1D_IW_GRDH_1SDV_20260804T122140_20260804T122205_003976_00737A_rtc"},
                       {"name": "S1D_IW_GRDH_1SDV_20260804T122115_20260804T122140_003976_00737A_rtc"}],
        "2026-07-23": [{"name": "S1D_IW_GRDH_1SDV_20260723T122115_20260723T122140_003801_006D5D_rtc"}],
        "2026-07-11": [{"name": "S1D_IW_GRDH_1SDV_20260711T122114_20260711T122139_003626_00675A_rtc"}],
        "2026-06-29": [{"name": "S1D_IW_GRDH_1SDV_20260629T122113_20260629T122138_003451_006174_rtc"}],
        "2026-06-22": [{"name": "S1A_IW_GRDH_1SDV_20260622T122218_20260622T122243_065082_083408_rtc"}]}


def test_tod_guard_fires_only_above_10_minutes():
    same = [datetime(2026, 8, 4, 12, 21), datetime(2026, 6, 22, 12, 22)]
    other = [datetime(2026, 8, 4, 12, 21), datetime(2026, 8, 5, 0, 5)]          # an ascending and a descending pass
    assert tod_warning(same) is None
    assert "differ by 736 min" in tod_warning(other)


def test_dry_run_1_flags_the_platform_mix_but_not_the_time():
    acq, w = stack_warnings(DRY1)
    assert acq["2026-06-22"] == {"platforms": ["S1A"], "start_utc": "2026-06-22T12:22:18Z"}
    assert acq["2026-08-04"]["start_utc"] == "2026-08-04T12:21:15Z"
    assert len(w) == 1 and "mixes platforms S1A (2026-06-22), S1D" in w[0]


def test_select_records_guards_and_check_stack_has_the_guard():
    out = add_guards({"products": DRY1}); assert out["warnings"] and set(out["acquisitions"]) == set(DRY1)
    assert parse_name("not-a-product") == (None, None)
    src = Path("src/processing/check_stack.py").read_text(encoding="utf-8")
    assert "tod = [t.hour * 60 + t.minute for t, _, _ in rows.values()]" in src and "not the same orbit track?" in src

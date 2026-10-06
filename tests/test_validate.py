import numpy as np, pytest
from pathlib import Path
from src.validation.emsr927_validate import seg_metrics, pick, boot

def test_seg_metrics():
    pred = np.zeros((10, 10), bool); ref = pred.copy(); pred[:5] = True; ref[:, :5] = True
    m = seg_metrics(pred, ref, np.ones((10, 10), bool))
    assert (m["precision"], m["recall"]) == (0.5, 0.5) and m["iou"] == pytest.approx(1 / 3)

def test_pick_latest_version_and_never_reads_missing_layer():
    items = [(Path("a.gpkg"), "observedEventA_v1"), (Path("a.gpkg"), "observedEventA_v2")]; log = []
    assert pick(items, "observedEventA", log)[1].endswith("v2")
    assert pick(items, "notAnalysedA", log) is None and any("missing" in l for l in log)

def test_boot_ci_brackets_rate():
    h = np.array([1, 0] * 200, bool); blk = np.repeat(np.arange(40), 10)
    lo, hi = boot(h, blk); assert lo <= 0.5 <= hi
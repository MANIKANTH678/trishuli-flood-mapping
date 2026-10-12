"""Step 11: path-2 metrics (labelled pixels only, chip bootstrap, A/B agreement) on synthetic labels."""
import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location("hp2", Path("tools/himalaya_path2.py")); hp2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(hp2)


def test_counts_ignore_unlabelled_pixels():
    lab = np.array([[1, 1, 0, -1], [0, -1, -1, -1]]); pred = np.array([[1, 0, 1, 1], [0, 1, 1, 1]], bool)
    assert hp2.counts(pred, lab) == (1, 1, 1, 4, 2)          # predictions on -1 pixels never count


def test_pooled_iou_bootstrap_and_per_chip_pixels():
    per = {"a": (10, 0, 0, 50, 10), "b": (0, 10, 10, 40, 10), "c": (0, 0, 0, 0, 0)}
    s = hp2.summarise(per, 0.4)
    assert s["pooled_iou_labelled_pixels"] == 10 / 30 and s["n_chips_with_labels"] == 2 and s["labelled_pixels_per_chip"]["c"] == 0
    lo, hi = s["iou_ci95_chip_bootstrap"]; assert 0 <= lo <= 10 / 30 <= hi <= 1
    assert hp2.bootstrap_ci([(1, 0, 0)]) is None


def test_ab_agreement_uses_first_8_and_jointly_labelled_pixels():
    a = np.array([[1, 1, 0, -1]]); b = np.array([[1, 0, 0, 1]])
    pairs = [(f"c{i}", a, b) for i in range(10)]
    r = hp2.ab_agreement(pairs)
    assert r["n_chips"] == 8 and r["iou_A_vs_B"] == 0.5 and r["chips"][-1] == "c7"


def test_amendment_is_logged_before_labelling():
    assert hp2.AMENDMENT in Path("docs/validation_log.md").read_text(encoding="utf-8")

import json, warnings
from pathlib import Path
import numpy as np
from src.analysis.changelib import rd, domain

thr = json.load(open("outputs/ai/smp_resnet34/threshold.json"))["threshold"]; hand, mask, _ = domain("data/processed", 30)
p10 = rd("data/processed/ai/prob_post_10m.tif")[0]; h, w = (n // 3 * 3 for n in p10.shape)
with warnings.catch_warnings():
    warnings.simplefilter("ignore"); p30 = np.nanmean(p10[:h, :w].reshape(h // 3, 3, w // 3, 3), axis=(1, 3))
d = Path("data/interim/s2/20260827"); sl = (slice(0, p30.shape[0]), slice(0, p30.shape[1]))
mndwi, clear = rd(d / "mndwi_30m.tif")[0][sl], rd(d / "clear_30m.tif")[0][sl]
ok = np.isfinite(p30) & np.isfinite(mndwi) & (clear > 0.9) & (hand[sl] <= 30) & (mask[sl] == 0)
ref = mndwi > 0.1
print("thr", thr, "| prob on S2-water: median %.3f mean %.3f | prob on S2-land: median %.3f mean %.3f" % (
    np.median(p30[ok & ref]), p30[ok & ref].mean(), np.median(p30[ok & ~ref]), p30[ok & ~ref].mean()))
print("threshold sweep (IoU / R):")
for t in (0.05, 0.1, 0.2, 0.3, 0.5):
    pr = p30 > t; tp = (pr & ref & ok).sum(); fp = (pr & ~ref & ok).sum(); fn = (~pr & ref & ok).sum()
    print(f"  {t}: IoU={tp/max(tp+fp+fn,1):.3f} R={tp/max(tp+fn,1):.3f}")
print("shift test (dy,dx -> IoU):")
for dy in range(-3, 4):
    for dx in range(-3, 4):
        pr = np.roll(p30 > thr, (dy, dx), (0, 1)); tp = (pr & ref & ok).sum(); fp = (pr & ~ref & ok).sum(); fn = (~pr & ref & ok).sum()
        v = tp / max(tp + fp + fn, 1)
        if v > 0.08 or (dy, dx) == (0, 0): print(f"  ({dy},{dx}): {v:.3f}")
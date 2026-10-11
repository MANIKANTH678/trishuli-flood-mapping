import json
import numpy as np
from src.analysis.changelib import rd, domain

thr = json.load(open("outputs/ai/smp_resnet34/threshold.json"))["threshold"]
hand, mask, _ = domain("data/processed", 30)
p10 = rd("data/processed/ai/prob_post_10m.tif")[0]; h, w = (n // 3 * 3 for n in p10.shape)
p30 = np.nanmean(p10[:h, :w].reshape(h // 3, 3, w // 3, 3), axis=(1, 3))
sl = (slice(0, p30.shape[0]), slice(0, p30.shape[1])); H = hand[sl]; M = mask[sl]
pr = p30 > thr
floor = np.isfinite(H) & (H <= 30) & (M == 0)
print("predicted-water km2 total      :", round(pr.sum() * 900 / 1e6, 1))
print("  on valley floor (HAND<=30)   :", round((pr & floor).sum() * 900 / 1e6, 1))
print("  HAND 30-100 m                :", round((pr & (H > 30) & (H <= 100)).sum() * 900 / 1e6, 1))
print("  HAND > 100 m                 :", round((pr & (H > 100)).sum() * 900 / 1e6, 1))
print("fraction of floor predicted water:", round((pr & floor).sum() / floor.sum(), 4))
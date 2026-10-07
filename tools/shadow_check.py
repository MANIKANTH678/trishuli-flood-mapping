import json
from pathlib import Path
import numpy as np
from src.analysis.changelib import domain, rd

thr = json.load(open("outputs/ai/smp_resnet34/threshold.json"))["threshold"]
hand, mask, dem = domain("data/processed", 10)
P = lambda s: rd(Path(f"data/processed/ai/prob_{s}_10m.tif"))[0]
pre, post = P("pre"), P("post")
valid = np.isfinite(pre) & np.isfinite(post) & np.isfinite(dem)
both = (pre > thr) & (post > thr)
new = (post > thr) & ~(pre > thr)
sets = {"all valid": valid,
        "radar mask removed": valid & (mask == 0),
        "mask removed + HAND<=30": valid & (mask == 0) & np.isfinite(hand) & (hand <= 30)}
for k, m in sets.items():
    print(f"{k}: n={int(m.sum())} | flagged in both {100*both[m].mean():.2f}% | new water {100*new[m].mean():.2f}%")
print(f"share of 'both' pixels inside the radar mask: {100*both[valid & (mask != 0)].sum()/max(both[valid].sum(),1):.1f}%")
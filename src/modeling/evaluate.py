import argparse, json
from collections import defaultdict
from pathlib import Path
import numpy as np, torch
from torch.utils.data import DataLoader
from src.modeling.dataset import Sen1Floods11
from src.modeling.common import build_model, probs, pooled

def chip_ci(items, thr, n=1000):
    c = np.array([[((p > thr) & y & v).sum(), ((p > thr) & ~y & v).sum(), (~(p > thr) & y & v).sum()] for _, p, y, v in items], float)
    rng = np.random.default_rng(0); s = [c[rng.integers(0, len(c), len(c))].sum(0) for _ in range(n)]
    iou = [t / (t + f + m) if t + f + m else 0.0 for t, f, m in s]
    return [round(float(np.percentile(iou, q)), 4) for q in (2.5, 97.5)]

def summarize(items, thr):
    by = defaultdict(list)
    for it in items: by[it[0].split("_")[0]].append(it)
    return {"n_chips": len(items), "at_threshold": pooled(items, thr), "at_0.5": pooled(items, 0.5), "iou_ci95_chip_bootstrap": chip_ci(items, thr),
            "per_region": {r: {"n_chips": len(v), "iou": round(pooled(v, thr)["iou"], 4)} for r, v in sorted(by.items())}}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="smp_resnet34"); ap.add_argument("--run"); ap.add_argument("--ckpt"); ap.add_argument("--thr", type=float)
    ap.add_argument("--extra"); ap.add_argument("--extra-s1"); ap.add_argument("--extra-lbl"); ap.add_argument("--out")
    a = ap.parse_args(); run = Path(a.run or f"outputs/ai/{a.arch}"); dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model(a.arch).to(dev); model.load_state_dict(torch.load(a.ckpt or run / "model.pt", map_location=dev))
    thr = a.thr if a.thr is not None else json.load(open(run / "threshold.json"))["threshold"]
    sets = {"valid": Sen1Floods11("flood_valid_data.csv"), "test": Sen1Floods11("flood_test_data.csv"), "bolivia": Sen1Floods11("flood_bolivia_data.csv")}
    if a.extra: sets["himalaya_chips"] = Sen1Floods11(a.extra, s1_dir=a.extra_s1, lbl_dir=a.extra_lbl)
    res = {"arch": a.arch, "threshold": thr,
           "roles": {"valid": "checkpoint and threshold selection", "test": "held-out chips from TRAINING events (same events, different chips)",
                     "bolivia": "held-out REGION (not Himalayan)", "himalaya_chips": "team-labelled, unseen region and terrain"},
           "splits": {k: summarize(probs(model, DataLoader(d, 8), dev), thr) for k, d in sets.items()}}
    out = Path(a.out or run / "metrics.json"); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(res, indent=2))
    print({k: v["at_threshold"]["iou"] for k, v in res["splits"].items()})

if __name__ == "__main__":
    main()
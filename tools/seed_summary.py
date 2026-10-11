"""Step 8B: mean +/- sd over the shipped seed-0 model and seeds 1-2 (val, test, Bolivia; pooled IoU at each run's own val threshold).
python tools/seed_summary.py  ->  outputs/validation/seeds_summary.json"""
import json, statistics as st
from pathlib import Path

RUNS = {0: "outputs/ai/smp_resnet34", 1: "outputs/ai_seed1/smp_resnet34", 2: "outputs/ai_seed2/smp_resnet34"}
SPLITS = ["valid", "test", "bolivia"]

def main():
    per = {}
    for s, d in RUNS.items():
        m = json.loads((Path(d) / "metrics.json").read_text()); thr = json.loads((Path(d) / "threshold.json").read_text())["threshold"]
        per[s] = {"threshold": thr, **{k: round(m["splits"][k]["at_threshold"]["iou"], 4) for k in SPLITS}}
    v = lambda k: [per[s][k] for s in per]
    summ = {k: {"mean": round(st.mean(v(k)), 4), "sd": round(st.stdev(v(k)), 4) if len(per) > 1 else None,
                "min": min(v(k)), "max": max(v(k)), "n_seeds": len(per)} for k in SPLITS}
    out = {"model": "smp_resnet34 (ResNet34 U-Net), Sen1Floods11 hand-labelled", "shipped": "seed 0", "per_seed": per, "summary": summ,
           "note": "sd over 3 seeds; each seed's threshold is tuned on its own validation split"}
    Path("outputs/validation/seeds_summary.json").write_text(json.dumps(out, indent=2))
    print("seed  thr   " + "  ".join(f"{k:>8}" for k in SPLITS))
    for s, r in per.items(): print(f"{s:>4}  {r['threshold']:<4}  " + "  ".join(f"{r[k]:>8.4f}" for k in SPLITS))
    print("mean±sd    " + "  ".join(f"{summ[k]['mean']:.3f}±{summ[k]['sd']:.3f}" for k in SPLITS))

if __name__ == "__main__":
    main()

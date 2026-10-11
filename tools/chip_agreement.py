"""Step 8C: inter-annotator agreement (noise ceiling) on chips labelled by both A and B, plus a chips.csv of usable A-labels.
python tools/chip_agreement.py -> outputs/validation/himalaya_label_agreement.json, data/external/himalaya_chips/chips_labelled.csv"""
import json
from pathlib import Path
import numpy as np, rasterio

def rd(p):
    with rasterio.open(p) as s: return s.read(1), s.tags().get("status")

def main():
    d = Path("data/external/himalaya_chips"); names = [l.split(",")[0].replace("_S1.tif", "") for l in (d / "chips.csv").read_text().split()]
    usable, both = [], []
    tp = fp = fn = 0; per = []
    for n in names:
        a, sa = rd(d / "Label_A" / f"{n}_Label.tif")
        if sa == "labelled" and (a != -1).any(): usable.append(n)
        pb = d / "Label_B" / f"{n}_Label.tif"
        if pb.exists():
            b, sb = rd(pb)
            if sa == "labelled" and sb == "labelled":
                v = (a != -1) & (b != -1); A, B = (a == 1) & v, (b == 1) & v
                c = (int((A & B).sum()), int((A & ~B).sum()), int((~A & B).sum())); per.append(c)
                tp += c[0]; fp += c[1]; fn += c[2]; both.append(n)
    (d / "chips_labelled.csv").write_text("".join(f"{n}_S1.tif,{n}_Label.tif\n" for n in usable))
    ci = None
    if len(per) >= 2:
        rng = np.random.default_rng(0); P = np.array(per, float); bs = []
        for _ in range(2000):
            t, f, m = P[rng.integers(0, len(P), len(P))].sum(0); bs.append(t / max(t + f + m, 1))
        ci = [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]
    res = {"n_chips_preregistered": len(names), "n_usable_A": len(usable), "n_chips": len(both),
           "iou_A_vs_B": round(tp / max(tp + fp + fn, 1), 3) if both else None, "iou_ci95_chip_bootstrap": ci,
           "note": "the model cannot be scored above the inter-annotator IoU; with ~20 chips the bootstrap CI is wide"}
    Path("outputs/validation").mkdir(parents=True, exist_ok=True)
    Path("outputs/validation/himalaya_label_agreement.json").write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

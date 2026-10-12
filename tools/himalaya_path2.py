"""Step 11, Himalayan chips path 2 (amendment in docs/validation_log.md, 2026-10-12): score the model on LABELLED PIXELS ONLY.

Labels (people, tools/label_chips.py, docs/chip_protocol.md): 1 = open water incl. turbid, 0 = not water,
-1 = cloud / cloud shadow / unsure (ignored). All 20 chips stay; a chip with no labelled pixel simply adds nothing.

    python tools/himalaya_path2.py                                   # post-event chips (27 Aug S2), annotator A + B
    python tools/himalaya_path2.py --chips data/external/himalaya_chips_pre --tag pre    # pre-event chips, reported separately

Reports (outputs/validation/himalaya_path2_<tag>.json):
  - pooled IoU over labelled pixels (model threshold from models/threshold.json), precision, recall;
  - labelled pixels per chip (and water pixels per chip);
  - chip-bootstrap 95% CI of the pooled IoU (chips resampled with replacement, 2000 draws, seed 0);
  - A/B agreement IoU on the first 8 chips in points.csv order that both annotators labelled.
Refuses to run until the path-2 amendment is in docs/validation_log.md (it must predate the labels)."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

AMENDMENT = "Amendment: no chip reached 70% clear. Chips will be labelled on clear pixels only (cloud/shadow = −1); all 20 stay."


def counts(pred, lab):
    """pred: bool water prediction; lab: int labels (1/0/-1). -> (tp, fp, fn, n_labelled, n_water) on labelled pixels."""
    v = lab != -1; y = (lab == 1) & v; p = pred & v
    return int((p & y).sum()), int((p & ~y).sum()), int((~p & y & v).sum()), int(v.sum()), int(y.sum())


def iou(tp, fp, fn): return tp / (tp + fp + fn) if tp + fp + fn else None


def bootstrap_ci(per_chip, n=2000, seed=0):
    """per_chip: list of (tp, fp, fn, ...) -> [lo, hi] 95% CI of the pooled IoU, chips resampled. None if < 2 chips."""
    C = np.array([c[:3] for c in per_chip], float)
    if len(C) < 2: return None
    rng = np.random.default_rng(seed); s = []
    for _ in range(n):
        t, f, m = C[rng.integers(0, len(C), len(C))].sum(0)
        if t + f + m: s.append(t / (t + f + m))
    return [round(float(np.percentile(s, 2.5)), 3), round(float(np.percentile(s, 97.5)), 3)] if s else None


def ab_agreement(pairs, first=8):
    """pairs: [(name, label_A, label_B)] in points.csv order, both labelled. IoU of water over pixels BOTH labelled,
    on the first `first` chips."""
    use = pairs[:first]; tp = fp = fn = 0
    for _, a, b in use:
        v = (a != -1) & (b != -1); A, B = (a == 1) & v, (b == 1) & v
        tp += int((A & B).sum()); fp += int((A & ~B).sum()); fn += int((~A & B).sum())
    return {"n_chips": len(use), "chips": [n for n, _, _ in use], "iou_A_vs_B": None if not use else iou(tp, fp, fn)}


def summarise(per, thr):
    tp, fp, fn = (sum(c[i] for c in per.values()) for i in range(3))
    return {"threshold": thr, "n_chips_with_labels": sum(1 for c in per.values() if c[3] > 0), "n_chips_total": len(per),
            "pooled_iou_labelled_pixels": iou(tp, fp, fn), "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None, "iou_ci95_chip_bootstrap": bootstrap_ci([c for c in per.values() if c[3] > 0]),
            "labelled_pixels_per_chip": {k: c[3] for k, c in per.items()}, "water_pixels_per_chip": {k: c[4] for k, c in per.items()}}


def read_label(p):
    import rasterio
    if not p.exists(): return None
    with rasterio.open(p) as s:
        a, st = s.read(1).astype(int), s.tags().get("status")
    return a if st == "labelled" else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--chips", default="data/external/himalaya_chips"); ap.add_argument("--tag", default="post")
    ap.add_argument("--points", default="data/external/himalaya_chips/points.csv")
    ap.add_argument("--run", default="models"); ap.add_argument("--arch", default="smp_resnet34"); ap.add_argument("--thr", type=float)
    a = ap.parse_args()
    if AMENDMENT not in Path("docs/validation_log.md").read_text(encoding="utf-8"):
        sys.exit("himalaya_path2: the path-2 amendment is not in docs/validation_log.md; add it (dated) before labelling")
    d = Path(a.chips); suffix = "_pre" if a.tag == "pre" else ""
    order = [l.split(",")[0] + suffix for l in Path(a.points).read_text().splitlines()[1:] if l.strip()]
    labA = {n: read_label(d / "Label_A" / f"{n}_Label.tif") for n in order}
    labA = {n: v for n, v in labA.items() if v is not None}
    if not labA: sys.exit(f"himalaya_path2: no chip in {d}/Label_A has status=labelled yet (label with tools/label_chips.py first)")
    import torch, rasterio
    from src.modeling.common import build_model, load_weights
    from src.modeling.dataset import normalize
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model(a.arch, pretrained=False).to(dev); load_weights(model, Path(a.run), None, dev); model.eval()
    thr = a.thr if a.thr is not None else json.loads((Path(a.run) / "threshold.json").read_text())["threshold"]
    per = {}
    for n, lab in labA.items():
        with rasterio.open(d / "S1" / f"{n}_S1.tif") as s: s1 = s.read().astype("float32")
        x = torch.from_numpy(np.nan_to_num(normalize(s1), nan=0.0)[None]).to(dev)
        with torch.no_grad(): p = torch.sigmoid(model(x))[0, 0].cpu().numpy()
        lab = np.where(np.isfinite(s1).all(0), lab, -1)            # NaN S1 pixels are not scored
        per[n] = counts(p > thr, lab)
    res = {"split": a.tag, "rule": AMENDMENT, **summarise(per, thr)}
    pairs = [(n, labA[n], b) for n in order if n in labA and (b := read_label(d / "Label_B" / f"{n}_Label.tif")) is not None]
    res["ab_agreement_first8"] = ab_agreement(pairs)
    res["note"] = ("n < 8 labelled chips: qualitative only" if res["n_chips_with_labels"] < 8 else
                   "the model cannot be scored above the A/B agreement; ~20 chips give a wide CI")
    out = Path(f"outputs/validation/himalaya_path2_{a.tag}.json"); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2)); print(json.dumps({k: v for k, v in res.items() if "per_chip" not in k}, indent=2))


if __name__ == "__main__":
    main()

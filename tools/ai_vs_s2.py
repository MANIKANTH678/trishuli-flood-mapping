"""Step 8C (quick complement): agreement of the AI water mask with Sentinel-2 MNDWI water on clear valley-floor pixels.
S2 is a PSEUDO-reference (turbid water fools MNDWI; S1/S2 are 1-4 days apart; compared at 30 m): report AGREEMENT, not accuracy.
Needs data/processed/ai/prob_{post,pre}_10m.tif (python -m src.modeling.predict_scene --splits post,pre).
python tools/ai_vs_s2.py  ->  outputs/validation/ai_vs_s2.json"""
import json, sys, warnings
from pathlib import Path
import numpy as np
from src.analysis.changelib import rd, domain

PAIRS = (("post", "20260827"), ("pre", "20260812"))

def main():
    thr = json.load(open("outputs/ai/smp_resnet34/threshold.json"))["threshold"]; hand, mask, _ = domain("data/processed", 30)
    res = {"threshold": thr, "reference": "S2 MNDWI > 0.1 on pixels with clear > 0.9, HAND <= 30 m, radar-observable",
           "caveat": "pseudo-reference: agreement, not accuracy", "results": {}}
    for split, s2date in PAIRS:
        pp, d = Path(f"data/processed/ai/prob_{split}_10m.tif"), Path("data/interim/s2") / s2date
        if not pp.exists(): sys.exit(f"missing {pp}: run  python -m src.modeling.predict_scene --splits post,pre")
        if not (d / "mndwi_30m.tif").exists(): res["results"][split] = {"s2_date": s2date, "error": "no mndwi_30m.tif"}; continue
        p10 = rd(pp)[0]; p10[p10 < -1] = np.nan; h, w = (n // 3 * 3 for n in p10.shape)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); p30 = np.nanmean(p10[:h, :w].reshape(h // 3, 3, w // 3, 3), axis=(1, 3))
        sl = (slice(0, p30.shape[0]), slice(0, p30.shape[1]))
        mndwi, clear = rd(d / "mndwi_30m.tif")[0][sl], rd(d / "clear_30m.tif")[0][sl]
        ok = np.isfinite(p30) & np.isfinite(mndwi) & (clear > 0.9) & (hand[sl] <= 30) & (mask[sl] == 0)
        pred, ref = (p30 > thr)[ok], (mndwi > 0.1)[ok]
        tp, fp, fn = int((pred & ref).sum()), int((pred & ~ref).sum()), int((~pred & ref).sum())
        r = {"s2_date": s2date, "n_px": int(ok.sum()), "s2_water_px": int(ref.sum()), "ai_water_px": int(pred.sum()),
             "iou": round(tp / max(tp + fp + fn, 1), 3), "precision": round(tp / max(tp + fp, 1), 3), "recall": round(tp / max(tp + fn, 1), 3)}
        res["results"][split] = r
        print(split, s2date, f"n={r['n_px']:,} S2-water={r['s2_water_px']:,} IoU={r['iou']:.3f} P={r['precision']:.3f} R={r['recall']:.3f}")
    Path("outputs/validation").mkdir(parents=True, exist_ok=True)
    Path("outputs/validation/ai_vs_s2.json").write_text(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

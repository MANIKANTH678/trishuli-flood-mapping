"""Find optimal probability threshold for the trained model."""
import os, sys
import numpy as np
import joblib
import rioxarray
from sklearn.model_selection import train_test_split
from sklearn.metrics import f1_score, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR

FEATURES = ["elevation", "slope", "aspect", "tpi", "dist_lowland",
            "vv_diff", "vh_diff", "vv_pre", "vh_pre"]


def load_stack(feat_dir):
    return np.stack([np.load(os.path.join(feat_dir, f"{f}.npy")) for f in FEATURES], axis=-1)


def main():
    feat_dir = os.path.join(OUTPUTS_DIR, "features")
    X = load_stack(feat_dir)
    y = rioxarray.open_rasterio(os.path.join(PROCESSED_DIR, "flood_mask.tif"),
                                masked=True).squeeze().values
    y = (y == 1).astype(np.uint8)

    H, W, N = X.shape
    Xf = X.reshape(-1, N).astype(np.float32)
    yf = y.reshape(-1).astype(np.uint8)
    valid = np.all(np.isfinite(Xf), axis=1)
    Xf, yf = Xf[valid], yf[valid]

    _, Xte, _, yte = train_test_split(Xf, yf, test_size=0.3,
                                       random_state=42, stratify=yf)

    clf = joblib.load(os.path.join(OUTPUTS_DIR, "flood_model.joblib"))
    proba = clf.predict_proba(Xte)[:, 1]

    print(f"{'thresh':>8}  {'precision':>10}  {'recall':>8}  {'F1':>8}")
    best_f1, best_t = 0, 0.5
    for t in np.arange(0.05, 0.96, 0.05):
        pred = (proba > t).astype(int)
        if pred.sum() == 0:
            continue
        p = precision_score(yte, pred, zero_division=0)
        r = recall_score(yte, pred, zero_division=0)
        f = f1_score(yte, pred, zero_division=0)
        print(f"{t:>8.2f}  {p:>10.4f}  {r:>8.4f}  {f:>8.4f}")
        if f > best_f1:
            best_f1, best_t = f, t

    print(f"\n✅ Best threshold: {best_t:.2f}  →  F1 = {best_f1:.4f}")


if __name__ == "__main__":
    main()

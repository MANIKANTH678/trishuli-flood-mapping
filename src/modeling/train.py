"""Train flood susceptibility model with balanced undersampling."""
import os, sys, json
import numpy as np
import joblib
import rioxarray
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix, precision_score, recall_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR

FEATURES = ["elevation", "slope", "aspect", "tpi", "dist_lowland",
            "vv_diff", "vh_diff", "vv_pre", "vh_pre"]

# How many non-flood pixels per flood pixel to keep during training
NEG_RATIO = 10


def load_stack(feat_dir):
    return np.stack([np.load(os.path.join(feat_dir, f"{f}.npy")) for f in FEATURES], axis=-1)


def main():
    feat_dir = os.path.join(OUTPUTS_DIR, "features")
    print("Loading features...")
    X = load_stack(feat_dir)
    y = rioxarray.open_rasterio(os.path.join(PROCESSED_DIR, "flood_mask.tif"),
                                masked=True).squeeze().values
    y = (y == 1).astype(np.uint8)
    print(f"  X shape: {X.shape}  flood pixels: {int(y.sum()):,}")

    H, W, N = X.shape
    Xf = X.reshape(-1, N).astype(np.float32)
    yf = y.reshape(-1).astype(np.uint8)
    valid = np.all(np.isfinite(Xf), axis=1)
    Xf, yf = Xf[valid], yf[valid]
    print(f"  samples after NaN drop: {len(Xf):,}  flood: {int(yf.sum()):,}")

    # Split FIRST (on full data), then undersample the training negatives only
    Xtr, Xte, ytr, yte = train_test_split(
        Xf, yf, test_size=0.3, random_state=42, stratify=yf
    )

    # Undersample negatives in TRAINING set
    pos_idx = np.where(ytr == 1)[0]
    neg_idx = np.where(ytr == 0)[0]
    n_keep_neg = min(len(neg_idx), len(pos_idx) * NEG_RATIO)
    rng = np.random.default_rng(42)
    neg_keep = rng.choice(neg_idx, size=n_keep_neg, replace=False)
    keep = np.concatenate([pos_idx, neg_keep])
    Xtr_b, ytr_b = Xtr[keep], ytr[keep]
    print(f"  training set balanced: {len(Xtr_b):,}  "
          f"(pos={int(ytr_b.sum()):,}, neg={int((ytr_b==0).sum()):,})")
    print(f"  test set (unchanged, real distribution): {len(Xte):,}")

    print("\nTraining XGBoost...")
    from xgboost import XGBClassifier
    clf = XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
        eval_metric="logloss",
    )
    clf.fit(Xtr_b, ytr_b)

    proba = clf.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, proba)

    print(f"\n{'thresh':>8}  {'precision':>10}  {'recall':>8}  {'F1':>8}")
    best_f1, best_t = 0, 0.5
    for t in np.arange(0.1, 0.96, 0.05):
        pred = (proba > t).astype(int)
        if pred.sum() == 0:
            continue
        p = precision_score(yte, pred, zero_division=0)
        r = recall_score(yte, pred, zero_division=0)
        f = f1_score(yte, pred, zero_division=0)
        print(f"{t:>8.2f}  {p:>10.4f}  {r:>8.4f}  {f:>8.4f}")
        if f > best_f1:
            best_f1, best_t = f, t

    print(f"\n✅ AUC (unchanged): {auc:.4f}")
    print(f"✅ Best threshold: {best_t:.2f}  →  F1 = {best_f1:.4f}")

    pred = (proba > best_t).astype(int)
    print(f"Precision @ best: {precision_score(yte, pred):.4f}")
    print(f"Recall    @ best: {recall_score(yte, pred):.4f}")
    print(f"Confusion matrix:\n{confusion_matrix(yte, pred)}")

    joblib.dump(clf, os.path.join(OUTPUTS_DIR, "flood_model.joblib"))
    imp = dict(zip(FEATURES, clf.feature_importances_.tolist()))
    with open(os.path.join(OUTPUTS_DIR, "feature_importance.json"), "w") as f:
        json.dump(imp, f, indent=2)
    with open(os.path.join(OUTPUTS_DIR, "model_meta.json"), "w") as f:
        json.dump({
            "auc": float(auc),
            "optimal_threshold": float(best_t),
            "f1_at_optimal": float(best_f1),
            "n_features": N,
            "features": FEATURES,
            "neg_ratio": NEG_RATIO
        }, f, indent=2)

    print("\nFeature importance:")
    for k, v in sorted(imp.items(), key=lambda x: -x[1]):
        print(f"  {k:15s}  {v:.4f}")

    print(f"\nSaved → outputs/flood_model.joblib")
    print(f"Saved → outputs/model_meta.json")


if __name__ == "__main__":
    main()

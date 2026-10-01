"""Compare P2 observed flood mask vs P3 predicted flood.

Looks for the observed flood mask in several candidate locations, because
P2 only committed the PNG preview, not the GeoTIFF raster. Fails with a
clear message if none are found.
"""
import os
import sys
import glob
import json
import numpy as np
import rioxarray
import matplotlib
matplotlib.use("Agg")   # headless
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Make repo root importable
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

try:
    from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR
except Exception:
    # Fallback if config isn't importable
    REPO = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    PROCESSED_DIR = os.path.join(REPO, "data", "processed")
    OUTPUTS_DIR = os.path.join(REPO, "outputs")


# Candidate locations for the observed flood raster
OBS_CANDIDATES = [
    os.path.join(PROCESSED_DIR, "flood_mask.tif"),
    os.path.join(OUTPUTS_DIR, "flood_mask.tif"),
    os.path.join(OUTPUTS_DIR, "flood_mask_observed.tif"),
    os.path.join(OUTPUTS_DIR, "observed_flood.tif"),
    os.path.join(PROCESSED_DIR, "flood_mask_v2.tif"),
]

PRED_PATH = os.path.join(OUTPUTS_DIR, "susceptibility_binary.tif")


def _find_file(candidates, label):
    for p in candidates:
        if os.path.isfile(p):
            print(f"✅ Found {label}: {p}")
            return p
    # Last-ditch: glob for anything resembling a flood mask
    roots = [PROCESSED_DIR, OUTPUTS_DIR, "."]
    hits = []
    for r in roots:
        hits += glob.glob(os.path.join(r, "*flood*mask*.tif"))
        hits += glob.glob(os.path.join(r, "*flood*.tif"))
    hits = [h for h in hits if os.path.isfile(h)]
    if hits:
        print(f"✅ Found {label} via glob: {hits[0]}")
        return hits[0]
    print(f"\n❌ Could not find {label}.")
    print(f"   Checked:")
    for c in candidates:
        print(f"     - {c}")
    print(f"   Globbed {roots} for *flood*mask*.tif / *flood*.tif")
    print(f"\n   👉 Ask P2 to commit the GeoTIFF to data/processed/flood_mask.tif")
    print(f"      (flood_mask.png is only a preview image, not a raster.)\n")
    return None


def _load_mask(path):
    arr = rioxarray.open_rasterio(path, masked=True).squeeze()
    # Handle multi-band rasters — take first band
    if arr.ndim == 3:
        arr = arr.isel(band=0)
    vals = arr.values
    # Accept either boolean-ish or 0/1
    vals = np.nan_to_num(vals, nan=0)
    return (vals > 0).astype(np.uint8)


def main():
    print("=== P4 Step 1.1 — Comparison figure ===\n")

    obs_path = _find_file(OBS_CANDIDATES, "observed flood mask (P2)")
    if obs_path is None:
        sys.exit(1)

    if not os.path.isfile(PRED_PATH):
        print(f"❌ Could not find predicted mask: {PRED_PATH}")
        print("   👉 Ask P3 to commit outputs/susceptibility_binary.tif")
        sys.exit(1)

    print(f"✅ Found predicted mask: {PRED_PATH}\n")

    # Load both
    obs_da = rioxarray.open_rasterio(obs_path, masked=True).squeeze()
    pred_da = rioxarray.open_rasterio(PRED_PATH, masked=True).squeeze()

    # If shapes mismatch, try to align by resampling pred to obs grid
    if obs_da.shape != pred_da.shape:
        print(f"⚠️  Shape mismatch: obs {obs_da.shape} vs pred {pred_da.shape}")
        print("   Resampling predicted → observed grid ...")
        pred_da = pred_da.rio.reproject_match(obs_da)

    obs = _load_mask(obs_path)
    pred = (np.nan_to_num(pred_da.values, nan=0) > 0).astype(np.uint8)

    if obs.shape != pred.shape:
        print(f"❌ Shapes still mismatch: obs {obs.shape} vs pred {pred.shape}")
        print("   Ask P2/P3 to confirm both rasters are on the same grid.")
        sys.exit(1)

    # Overlay math
    both     = (obs == 1) & (pred == 1)
    only_obs = (obs == 1) & (pred == 0)
    only_pred = (obs == 0) & (pred == 1)

    TP = int(both.sum())
    FN = int(only_obs.sum())
    FP = int(only_pred.sum())
    TN = int((~((obs == 1) | (pred == 1))).sum())

    precision = TP / max(TP + FP, 1)
    recall    = TP / max(TP + FN, 1)
    f1        = 2 * precision * recall / max(precision + recall, 1e-9)
    iou       = TP / max(TP + FP + FN, 1)

    print(f"TP={TP:,}  FN={FN:,}  FP={FP:,}  TN={TN:,}")
    print(f"Precision={precision:.4f}")
    print(f"Recall   ={recall:.4f}")
    print(f"F1       ={f1:.4f}")
    print(f"IoU      ={iou:.4f}\n")

    # Plot 3-panel
    fig, axes = plt.subplots(1, 3, figsize=(20, 8))

    axes[0].imshow(obs.astype(int), cmap="Blues")
    axes[0].set_title(f"Observed flood (P2)\n{obs.sum()*900/1e6:.2f} km²",
                      fontsize=14)
    axes[0].axis("off")

    axes[1].imshow(pred.astype(int), cmap="Blues")
    axes[1].set_title(f"Predicted flood (P3)\n{pred.sum()*900/1e6:.2f} km²",
                      fontsize=14)
    axes[1].axis("off")

    overlay = np.zeros((*obs.shape, 3), dtype=np.uint8)
    overlay[both]      = [30, 200, 30]
    overlay[only_obs]  = [30, 100, 255]
    overlay[only_pred] = [255, 60, 60]

    axes[2].imshow(overlay)
    axes[2].set_title(f"Agreement\nIoU={iou:.3f}   F1={f1:.3f}", fontsize=14)
    axes[2].axis("off")
    axes[2].legend(handles=[
        mpatches.Patch(color="#1ec81e", label=f"Both (TP={TP:,})"),
        mpatches.Patch(color="#1e64ff", label=f"Missed (FN={FN:,})"),
        mpatches.Patch(color="#ff3c3c", label=f"False alarm (FP={FP:,})"),
    ], loc="lower right", fontsize=11)

    plt.tight_layout()
    cmp_png = os.path.join(OUTPUTS_DIR, "comparison.png")
    plt.savefig(cmp_png, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"✅ {cmp_png}")

    # Save metrics
    metrics_path = os.path.join(OUTPUTS_DIR, "validation_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump({
            "observed_source": obs_path,
            "predicted_source": PRED_PATH,
            "TP": TP, "FN": FN, "FP": FP, "TN": TN,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "iou": iou,
            "observed_km2": float(obs.sum() * 900 / 1e6),
            "predicted_km2": float(pred.sum() * 900 / 1e6),
        }, f, indent=2)
    print(f"✅ {metrics_path}")


if __name__ == "__main__":
    main()

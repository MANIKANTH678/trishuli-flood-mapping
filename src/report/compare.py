"""Compare P2 observed flood mask vs P3 predicted flood."""
import os, sys, json
import numpy as np
import rioxarray
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR


def main():
    obs = rioxarray.open_rasterio(
        os.path.join(PROCESSED_DIR, "flood_mask.tif"), masked=True
    ).squeeze().values.astype(np.uint8)
    pred = rioxarray.open_rasterio(
        os.path.join(OUTPUTS_DIR, "susceptibility_binary.tif"), masked=True
    ).squeeze().values.astype(np.uint8)

    obs = (obs == 1)
    pred = (pred == 1)
    both = obs & pred
    only_obs = obs & ~pred
    only_pred = pred & ~obs

    TP = int(both.sum()); FN = int(only_obs.sum())
    FP = int(only_pred.sum()); TN = int((~obs & ~pred).sum())

    precision = TP / max(TP + FP, 1)
    recall    = TP / max(TP + FN, 1)
    f1        = 2 * precision * recall / max(precision + recall, 1e-9)
    iou       = TP / max(TP + FP + FN, 1)

    print(f"TP={TP:,} FN={FN:,} FP={FP:,} TN={TN:,}")
    print(f"Precision={precision:.4f}")
    print(f"Recall={recall:.4f}")
    print(f"F1={f1:.4f}")
    print(f"IoU={iou:.4f}")

    fig, axes = plt.subplots(1, 3, figsize=(20, 8))

    axes[0].imshow(obs.astype(int), cmap="Blues")
    axes[0].set_title(f"Observed flood (P2)\n{obs.sum()*900/1e6:.2f} km²", fontsize=14)
    axes[0].axis("off")

    axes[1].imshow(pred.astype(int), cmap="Blues")
    axes[1].set_title(f"Predicted flood (P3)\n{pred.sum()*900/1e6:.2f} km²", fontsize=14)
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
    plt.savefig(os.path.join(OUTPUTS_DIR, "comparison.png"),
                dpi=110, bbox_inches="tight")
    print("✅ outputs/comparison.png")

    with open(os.path.join(OUTPUTS_DIR, "validation_metrics.json"), "w") as f:
        json.dump({
            "TP": TP, "FN": FN, "FP": FP, "TN": TN,
            "precision": precision, "recall": recall,
            "f1": f1, "iou": iou,
            "observed_km2": obs.sum()*900/1e6,
            "predicted_km2": pred.sum()*900/1e6,
        }, f, indent=2)
    print("✅ outputs/validation_metrics.json")


if __name__ == "__main__":
    main()

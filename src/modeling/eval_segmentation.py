"""eval_segmentation.py - evaluate U-Net on a held-out split."""
import json
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.modeling.dataset import Sen1Floods11
from src.modeling.unet import UNet

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"
CKPT = OUT / "flood_unet.pt"
SPLIT = "flood_test_data.csv"


def metrics(logits, mask, valid, thr=0.0):
    pred = (logits > thr).float()
    tp = ((pred==1)&(mask==1)&(valid==1)).sum().item()
    fp = ((pred==1)&(mask==0)&(valid==1)).sum().item()
    fn = ((pred==0)&(mask==1)&(valid==1)).sum().item()
    iou = tp / (tp + fp + fn + 1e-9)
    f1  = 2*tp / (2*tp + fp + fn + 1e-9)
    return iou, f1, tp, fp, fn


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ds = Sen1Floods11(SPLIT)
    dl = DataLoader(ds, batch_size=4, shuffle=False, num_workers=4)
    print(f"split: {SPLIT} | chips: {len(ds)} | device: {device}")

    model = UNet().to(device)
    model.load_state_dict(torch.load(CKPT, map_location=device))
    model.eval()
    print(f"loaded: {CKPT}")

    ious, f1s = [], []
    TP = FP = FN = 0
    with torch.no_grad():
        for b in tqdm(dl, ncols=80):
            x = b["image"].to(device)
            y = b["mask"].to(device)
            v = b["valid"].to(device)
            out = model(x)
            iou, f1, tp, fp, fn = metrics(out, y, v)
            ious.append(iou); f1s.append(f1)
            TP += tp; FP += fp; FN += fn

    global_iou = TP / (TP + FP + FN + 1e-9)
    global_f1  = 2*TP / (2*TP + FP + FN + 1e-9)

    result = {
        "split": SPLIT,
        "n_chips": len(ds),
        "mean_iou":   round(float(np.mean(ious)), 4),
        "mean_f1":    round(float(np.mean(f1s)), 4),
        "global_iou": round(global_iou, 4),
        "global_f1":  round(global_f1, 4),
        "tp": TP, "fp": FP, "fn": FN,
    }
    out_path = OUT / "unet_test_metrics.json"
    json.dump(result, open(out_path, "w"), indent=2)
    print(f"\n{json.dumps(result, indent=2)}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()

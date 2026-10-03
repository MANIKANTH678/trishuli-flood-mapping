"""train_segmentation.py - train U-Net on Sen1Floods11 hand-labeled chips.

Runs on CPU. Approx 30-60 min for 20 epochs on a 20-core machine.
Writes:
  outputs/flood_unet.pt        (best-val checkpoint)
  outputs/flood_unet_last.pt   (last epoch)
  outputs/unet_metrics.json    (per-epoch metrics)
"""
import json, time, signal, sys, os
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.modeling.dataset import Sen1Floods11
from src.modeling.unet import UNet

ROOT = Path(__file__).resolve().parents[2]
OUT  = ROOT / "outputs"; OUT.mkdir(exist_ok=True)

EPOCHS = 20
BATCH  = 4
LR     = 1e-3
WORKERS = 8


def metrics(logits, mask, valid, thr=0.0):
    """IoU and F1 computed only on valid pixels. logits: pre-sigmoid."""
    pred = (logits > thr).float()
    v = valid
    tp = ((pred == 1) & (mask == 1) & (v == 1)).sum().item()
    fp = ((pred == 1) & (mask == 0) & (v == 1)).sum().item()
    fn = ((pred == 0) & (mask == 1) & (v == 1)).sum().item()
    iou = tp / (tp + fp + fn + 1e-9)
    f1  = 2 * tp / (2 * tp + fp + fn + 1e-9)
    return iou, f1


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    tr_ds = Sen1Floods11("flood_train_data.csv")
    va_ds = Sen1Floods11("flood_valid_data.csv")
    print(f"train chips: {len(tr_ds)} | val chips: {len(va_ds)}")

    tr = DataLoader(tr_ds, batch_size=BATCH, shuffle=True,  num_workers=WORKERS)
    va = DataLoader(va_ds, batch_size=BATCH, shuffle=False, num_workers=WORKERS)

    model = UNet().to(device)
    opt   = torch.optim.Adam(model.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=EPOCHS)
    loss_fn = nn.BCEWithLogitsLoss(reduction="none")

    best_iou = 0.0
    history = []

    def save_and_exit(signum, frame):
        print("\ncaught signal - saving last checkpoint ...")
        torch.save(model.state_dict(), OUT / "flood_unet_last.pt")
        json.dump(history, open(OUT / "unet_metrics.json", "w"), indent=2)
        sys.exit(0)

    signal.signal(signal.SIGINT,  save_and_exit)
    signal.signal(signal.SIGTERM, save_and_exit)

    for epoch in range(1, EPOCHS + 1):
        # ---- train ----
        model.train()
        tr_loss = 0.0
        tr_n = 0
        t0 = time.time()
        pbar = tqdm(tr, desc=f"epoch {epoch}/{EPOCHS} train", ncols=90)
        for b in pbar:
            x   = b["image"].to(device)
            y   = b["mask"].to(device)
            v   = b["valid"].to(device)
            opt.zero_grad()
            out = model(x)
            loss_per_px = loss_fn(out, y)
            loss = (loss_per_px * v).sum() / (v.sum() + 1e-6)
            loss.backward()
            opt.step()
            tr_loss += loss.item() * x.size(0)
            tr_n += x.size(0)
            pbar.set_postfix(loss=f"{loss.item():.4f}")
        tr_loss /= max(tr_n, 1)
        sched.step()

        # ---- validate ----
        model.eval()
        va_loss = 0.0
        va_n = 0
        ious, f1s = [], []
        with torch.no_grad():
            for b in va:
                x = b["image"].to(device)
                y = b["mask"].to(device)
                v = b["valid"].to(device)
                out = model(x)
                l = (loss_fn(out, y) * v).sum() / (v.sum() + 1e-6)
                va_loss += l.item() * x.size(0)
                va_n += x.size(0)
                iou, f1 = metrics(out, y, v)
                ious.append(iou); f1s.append(f1)
        va_loss /= max(va_n, 1)
        iou_m = float(np.mean(ious))
        f1_m  = float(np.mean(f1s))

        row = {
            "epoch":   epoch,
            "train_loss": round(tr_loss, 4),
            "val_loss":   round(va_loss, 4),
            "val_iou":    round(iou_m, 4),
            "val_f1":     round(f1_m, 4),
            "lr":         round(opt.param_groups[0]["lr"], 6),
            "secs":       round(time.time() - t0, 1),
        }
        history.append(row)
        print(f"  → {row}")

        torch.save(model.state_dict(), OUT / "flood_unet_last.pt")
        if iou_m > best_iou:
            best_iou = iou_m
            torch.save(model.state_dict(), OUT / "flood_unet.pt")
            print(f"  *** new best val IoU: {best_iou:.4f}")

        json.dump(history, open(OUT / "unet_metrics.json", "w"), indent=2)

    final = {
        "dataset":  "Sen1Floods11 v1.1 (hand-labeled)",
        "splits":   {"train": len(tr_ds), "val": len(va_ds)},
        "epochs":   EPOCHS,
        "best_val_iou": round(best_iou, 4),
        "final_val_iou": round(history[-1]["val_iou"], 4),
        "final_val_f1":  round(history[-1]["val_f1"], 4),
        "device":   device,
        "history":  history,
    }
    json.dump(final, open(OUT / "unet_metrics.json", "w"), indent=2)
    print(f"\ndone. best val IoU: {best_iou:.4f}")
    print(f"checkpoint: {OUT/'flood_unet.pt'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""eval_himalaya_heldout.py — Day 7 evaluation.

Sen1Floods11 has no true Himalayan/SAR-mountain-flood scenes. This script
evaluates the trained U-Net on the closest-available proxy: monsoon-subcontinent
chips (India + Pakistan) from the Sen1Floods11 val split.

Also produces a prediction-only run on the Rasuwa/Trishuli SAR rasters
(no ground truth exists there).

Output: outputs/himalaya_heldout_metrics.json
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

import numpy as np
import rasterio
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.modeling.dataset import DATA, S1_DIR, LBL_DIR
from src.modeling.unet import UNet

CKPT = ROOT / "outputs/flood_unet.pt"
OUT  = ROOT / "outputs/himalaya_heldout_metrics.json"

PROXY_REGIONS = {"India", "Pakistan"}
RASUWA_PRE  = ROOT / "data/processed/s1_pre_VV_30m.tif"
RASUWA_POST = ROOT / "data/processed/s1_post_VV_30m.tif"
RASUWA_PRE_VH  = ROOT / "data/processed/s1_pre_VH_30m.tif"
RASUWA_POST_VH = ROOT / "data/processed/s1_post_VH_30m.tif"


def load_val_split(regions: set[str] | None):
    csv = DATA / "splits" / "flood_valid_data.csv"
    pairs = []
    for line in csv.read_text().strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        if regions is not None:
            region = parts[0].split("_")[0]
            if region not in regions:
                continue
        pairs.append((parts[0], parts[1]))
    return pairs


def load_chip(s1_name, lbl_name):
    with rasterio.open(S1_DIR / s1_name) as src:
        s1 = src.read().astype("float32")   # (2, H, W)
    with rasterio.open(LBL_DIR / lbl_name) as src:
        lbl = src.read(1).astype("float32")
    s1 = np.clip((s1 + 25.0) / 15.0, -3.0, 3.0)
    s1 = np.nan_to_num(s1, nan=0.0)
    valid = (lbl != -1).astype("float32")
    lbl = np.clip(lbl, 0, 1).astype("float32")
    return s1, lbl, valid


def batch_metrics(tp, fp, fn, tn):
    iou = tp / (tp + fp + fn + 1e-9)
    f1  = 2 * tp / (2 * tp + fp + fn + 1e-9)
    prec = tp / (tp + fp + 1e-9)
    rec  = tp / (tp + fn + 1e-9)
    acc  = (tp + tn) / (tp + tn + fp + fn + 1e-9)
    return iou, f1, prec, rec, acc


def eval_on_pairs(model, pairs, device, thr=0.0):
    tp = fp = fn = tn = 0
    per_chip = []
    for s1_name, lbl_name in pairs:
        s1, lbl, valid = load_chip(s1_name, lbl_name)
        x = torch.from_numpy(s1).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(x)[0, 0].cpu().numpy()
        pred = (logits > thr).astype("float32")
        v = valid.astype(bool)
        ctp = int(((pred == 1) & (lbl == 1) & v).sum())
        cfp = int(((pred == 1) & (lbl == 0) & v).sum())
        cfn = int(((pred == 0) & (lbl == 1) & v).sum())
        ctn = int(((pred == 0) & (lbl == 0) & v).sum())
        tp += ctp; fp += cfp; fn += cfn; tn += ctn
        if (ctp + cfp + cfn) > 0:
            per_chip.append({
                "chip": s1_name,
                "iou": round(ctp / (ctp + cfp + cfn + 1e-9), 4),
                "f1":  round(2*ctp / (2*ctp + cfp + cfn + 1e-9), 4),
                "n_water_px": ctp + cfn,
            })
    iou, f1, prec, rec, acc = batch_metrics(tp, fp, fn, tn)
    return {
        "iou": round(iou, 4), "f1": round(f1, 4),
        "precision": round(prec, 4), "recall": round(rec, 4),
        "overall_accuracy": round(acc, 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "n_chips": len(pairs),
        "per_chip": per_chip,
    }


def tile_and_predict(model, device, pre, post, tile=512, stride=256):
    """Tile the Rasuwa SAR rasters and run model on each 2-channel tile."""
    with rasterio.open(pre) as src:
        pre_vv = src.read(1).astype("float32")
        T = src.transform
        crs = src.crs
    with rasterio.open(post) as src:
        post_vv = src.read(1).astype("float32")
    with rasterio.open(RASUWA_PRE_VH) as src:
        pre_vh = src.read(1).astype("float32")
    with rasterio.open(RASUWA_POST_VH) as src:
        post_vh = src.read(1).astype("float32")

    d_vv = post_vv - pre_vv
    d_vh = post_vh - pre_vh
    # normalize the same way as training (dB change, roughly -25..+5)
    stack = np.stack([np.clip((d_vv + 15) / 10, -3, 3),
                      np.clip((d_vh + 15) / 10, -3, 3)], axis=0)
    stack = np.nan_to_num(stack, nan=0.0)

    H, W = stack.shape[1], stack.shape[2]
    n_tiles = 0
    flood_px = 0
    total_px = 0
    model.eval()
    with torch.no_grad():
        for y in range(0, H - tile + 1, stride):
            for x in range(0, W - tile + 1, stride):
                t = stack[:, y:y+tile, x:x+tile]
                if not np.isfinite(t).all():
                    continue
                xb = torch.from_numpy(t).unsqueeze(0).to(device)
                logits = model(xb)[0, 0].cpu().numpy()
                pred = (logits > 0.0)
                flood_px += int(pred.sum())
                total_px += int(pred.size)
                n_tiles += 1
    return {
        "n_tiles": n_tiles,
        "flood_px": flood_px,
        "total_px": total_px,
        "predicted_flood_fraction": round(flood_px / max(total_px, 1), 4),
        "note": ("Prediction-only. No ground-truth mask exists for the Rasuwa "
                 "GLOF; the S1 pre/post pair was shown not to contain the "
                 "flood signal (see outputs/diagnostics/aoi_backscatter_diagnostics.json). "
                 "Values here reflect the model's response, not real accuracy."),
    }


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    model = UNet().to(device)
    model.load_state_dict(torch.load(CKPT, map_location=device))
    model.eval()
    print(f"loaded {CKPT}")

    # Full val split (all regions) for context
    all_pairs = load_val_split(None)
    print(f"full val: {len(all_pairs)} chips")
    full = eval_on_pairs(model, all_pairs, device)
    print(f"  full val IoU={full['iou']}  F1={full['f1']}")

    # Proxy-Himalaya subset
    proxy_pairs = load_val_split(PROXY_REGIONS)
    print(f"proxy-Himalaya: {len(proxy_pairs)} chips  ({sorted(PROXY_REGIONS)})")
    proxy = eval_on_pairs(model, proxy_pairs, device)
    print(f"  proxy IoU={proxy['iou']}  F1={proxy['f1']}")

    # Rasuwa prediction-only
    print("tiling Rasuwa SAR for prediction ...")
    rasuwa = tile_and_predict(model, device,
                              RASUWA_PRE, RASUWA_POST)
    print(f"  {rasuwa['n_tiles']} tiles, "
          f"flood fraction={rasuwa['predicted_flood_fraction']}")

    result = {
        "dataset": "Sen1Floods11 v1.1 (hand-labeled)",
        "model_checkpoint": str(CKPT.relative_to(ROOT)),
        "device": device,
        "caveat": ("Sen1Floods11 contains no true Himalayan/SAR-mountain-flood "
                   "scenes. The 'proxy_himalaya' section uses the closest-"
                   "available monsoon-subcontinent chips (India, Pakistan). "
                   "The 'rasuwa_prediction' section is prediction-only — no "
                   "ground truth exists for that event."),
        "sen1floods11_full_val": {
            "iou": full["iou"], "f1": full["f1"],
            "precision": full["precision"], "recall": full["recall"],
            "overall_accuracy": full["overall_accuracy"],
            "n_chips": full["n_chips"],
        },
        "proxy_himalaya": {
            "regions": sorted(PROXY_REGIONS),
            "iou": proxy["iou"], "f1": proxy["f1"],
            "precision": proxy["precision"], "recall": proxy["recall"],
            "overall_accuracy": proxy["overall_accuracy"],
            "n_chips": proxy["n_chips"],
            "per_chip": proxy["per_chip"],
        },
        "rasuwa_prediction": rasuwa,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

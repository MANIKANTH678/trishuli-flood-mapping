import argparse, json, time
from pathlib import Path
import numpy as np, torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from src.modeling.dataset import Sen1Floods11
from src.modeling.common import build_model, probs, pooled, best_threshold

def loss_fn(logit, y, v):                                       # masked BCE + Dice
    bce = (F.binary_cross_entropy_with_logits(logit, y, reduction="none") * v).sum() / v.sum().clamp(min=1)
    p = torch.sigmoid(logit) * v
    return bce + 1 - (2 * (p * y).sum() + 1) / (p.sum() + (y * v).sum() + 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="smp_resnet34"); ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8); ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--workers", type=int, default=2); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out", default="outputs/ai")
    a = ap.parse_args(); torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"; out = Path(a.out) / a.arch; out.mkdir(parents=True, exist_ok=True)
    tr = DataLoader(Sen1Floods11("flood_train_data.csv", augment=True), a.batch, shuffle=True, num_workers=a.workers, drop_last=True)
    va = DataLoader(Sen1Floods11("flood_valid_data.csv"), a.batch, num_workers=a.workers)
    model = build_model(a.arch).to(dev); opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, a.epochs); scaler = torch.cuda.amp.GradScaler(enabled=dev == "cuda")
    best, hist = -1.0, []
    for ep in range(1, a.epochs + 1):
        model.train(); t0, tl = time.time(), 0.0
        for b in tr:
            x, y, v = (b[k].to(dev) for k in ("image", "mask", "valid"))
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=dev, enabled=dev == "cuda"): logit = model(x)
            loss = loss_fn(logit.float(), y, v)
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); tl += loss.item()
        sched.step(); m = pooled(probs(model, va, dev), 0.5)       # checkpoint = best POOLED val IoU
        hist.append({"epoch": ep, "train_loss": round(tl / len(tr), 4), **{f"val_{k}": round(m[k], 4) for k in ("iou", "f1", "precision", "recall")},
                     "secs": round(time.time() - t0, 1)}); print(hist[-1])
        if m["iou"] > best: best = m["iou"]; torch.save(model.state_dict(), out / "model.pt")
    model.load_state_dict(torch.load(out / "model.pt", map_location=dev)); items = probs(model, va, dev); thr = best_threshold(items)
    (out / "threshold.json").write_text(json.dumps({"threshold": thr}))                  # tuned on VAL only
    (out / "train_log.json").write_text(json.dumps({"arch": a.arch, "seed": a.seed, "epochs": a.epochs, "device": dev,
        "best_val_pooled_iou_at_0.5": best, "threshold": thr, "val_at_threshold": pooled(items, thr), "history": hist}, indent=2))
    print("best val pooled IoU", round(best, 4), "| tuned threshold", thr)

if __name__ == "__main__":
    main()
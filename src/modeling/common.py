import numpy as np, torch

def build_model(arch, pretrained=True):
    """pretrained=False when a checkpoint is loaded next: skips the ImageNet download (works offline on judging day)."""
    if arch == "unet":
        from src.modeling.unet import UNet
        return UNet()
    if arch.startswith("smp_"):                                 # pip install segmentation-models-pytorch
        import segmentation_models_pytorch as smp
        return smp.Unet(arch[4:], encoder_weights="imagenet" if pretrained else None, in_channels=2, classes=1)
    raise ValueError(f"unknown arch {arch}")

class Counts:
    def __init__(self): self.tp = self.fp = self.fn = self.tn = 0
    def add(self, pred, y, valid):
        p, t, v = pred.bool(), y.bool(), valid.bool()
        self.tp += int((p & t & v).sum()); self.fp += int((p & ~t & v).sum())
        self.fn += int((~p & t & v).sum()); self.tn += int((~p & ~t & v).sum()); return self
    def metrics(self):
        tp, fp, fn, tn = self.tp, self.fp, self.fn, self.tn; r = lambda a, b: a / b if b else 0.0
        return {"iou": r(tp, tp + fp + fn), "f1": r(2 * tp, 2 * tp + fp + fn), "precision": r(tp, tp + fp),
                "recall": r(tp, tp + fn), "accuracy": r(tp + tn, tp + tn + fp + fn), "tp": tp, "fp": fp, "fn": fn, "tn": tn}

@torch.no_grad()
def probs(model, loader, device):
    model.eval(); out = []
    for b in loader:
        p = torch.sigmoid(model(b["image"].to(device))).cpu()
        for i in range(len(p)):
            out.append((b["name"][i], p[i, 0].numpy(), b["mask"][i, 0].numpy() > 0.5, b["valid"][i, 0].numpy() > 0.5))
    return out

def pooled(items, thr):                                         # POOLED over all pixels of all chips, everywhere
    c = Counts()
    for _, p, y, v in items: c.add(torch.from_numpy(p > thr), torch.from_numpy(y), torch.from_numpy(v))
    return c.metrics()

def best_threshold(items, grid=np.arange(0.2, 0.81, 0.05)):
    return round(float(max(grid, key=lambda t: pooled(items, t)["iou"])), 2)


# --- Step 10.4: weights live in models/ (never archived by `src.run --clean`) ------------------------------------
WEIGHT_NAMES = ("model.pt", "flood_unet_resnet34.pt", "flood_unet_resnet34_fp16.pt")


def default_run(arch="smp_resnet34"):
    """models/ when it holds weights (Step 10), else the training folder outputs/ai/<arch> (older checkouts)."""
    from pathlib import Path
    m = Path("models")
    return m if any((m / n).exists() for n in WEIGHT_NAMES) else Path(f"outputs/ai/{arch}")


def load_weights(model, run, ckpt=None, map_location="cpu"):
    """Load a state dict from --ckpt or the first of WEIGHT_NAMES in `run`; float16 copies are cast back to float32."""
    from pathlib import Path
    import torch
    p = Path(ckpt) if ckpt else next((Path(run) / n for n in WEIGHT_NAMES if (Path(run) / n).exists()), None)
    if p is None: raise SystemExit(f"no weights in {run} (looked for {', '.join(WEIGHT_NAMES)}); run tools/export_fp16.py or copy model.pt")
    sd = torch.load(p, map_location=map_location)
    sd = {k: (v.float() if torch.is_tensor(v) and v.is_floating_point() else v) for k, v in sd.items()}
    model.load_state_dict(sd); print(f"weights: {p}")
    return p

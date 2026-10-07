import numpy as np, torch

def build_model(arch):
    if arch == "unet":
        from src.modeling.unet import UNet
        return UNet()
    if arch.startswith("smp_"):                                 # pip install segmentation-models-pytorch
        import segmentation_models_pytorch as smp
        return smp.Unet(arch[4:], encoder_weights="imagenet", in_channels=2, classes=1)
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
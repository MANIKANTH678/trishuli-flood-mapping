"""Step 11, Himalayan chips path 3 (fallback figure): six example panels, chosen by FILE ORDER only (the first six chips in
data/external/himalaya_chips/chips.csv), never by how the prediction looks. Columns: Sentinel-2 true colour (27 Aug 2026,
labelling image), Sentinel-1 VV (dB, the model input) and the model water probability.

    python tools/himalaya_example_panels.py [--out outputs/figures/himalaya_example_panels.png] [--n 6]
    python tools/himalaya_example_panels.py --no-prob --out check.png     # layout check without any model output

This is qualitative context, not a test: no labels, no score. Annotators should label (path 2) before opening it."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np, rasterio
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt


def true_colour(s2):
    rgb = np.stack([s2[2], s2[1], s2[0]], -1) if s2.shape[0] >= 3 else np.repeat(s2[:1].transpose(1, 2, 0), 3, -1)
    rgb = np.nan_to_num(rgb.astype("float32")); hi = np.percentile(rgb[rgb > 0], 98) if (rgb > 0).any() else 1
    return np.clip(rgb / max(hi, 1e-6), 0, 1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--chips", default="data/external/himalaya_chips")
    ap.add_argument("--out", default="outputs/figures/himalaya_example_panels.png"); ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--no-prob", action="store_true"); ap.add_argument("--run", default="models"); a = ap.parse_args()
    d = Path(a.chips); names = [l.split(",")[0].replace("_S1.tif", "") for l in (d / "chips.csv").read_text().split()][:a.n]
    model = None
    if not a.no_prob:
        import torch
        from src.modeling.common import build_model, load_weights
        from src.modeling.dataset import normalize
        model = build_model("smp_resnet34", pretrained=False); load_weights(model, Path(a.run)); model.eval()
        thr = json.loads((Path(a.run) / "threshold.json").read_text())["threshold"]
    fig, ax = plt.subplots(len(names), 3, figsize=(9, 3 * len(names)))
    for i, n in enumerate(names):
        with rasterio.open(d / "S1" / f"{n}_S1.tif") as s: s1 = s.read().astype("float32")
        s2p = d / "S2" / f"{n}_S2.tif"
        if s2p.exists():
            with rasterio.open(s2p) as s: ax[i, 0].imshow(true_colour(s.read()))
        ax[i, 1].imshow(s1[0], cmap="gray", vmin=-25, vmax=0)
        if model is not None:
            with torch.no_grad():
                p = torch.sigmoid(model(torch.from_numpy(np.nan_to_num(normalize(s1), nan=0.0)[None])))[0, 0].numpy()
            im = ax[i, 2].imshow(p, cmap="Blues", vmin=0, vmax=1); ax[i, 2].contour(p > thr, levels=[0.5], colors="red", linewidths=0.5)
        else:
            ax[i, 2].text(0.5, 0.5, "model probability\n(not drawn: --no-prob)", ha="center", va="center", transform=ax[i, 2].transAxes)
        ax[i, 0].set_ylabel(n, fontsize=9)
        for j, t in enumerate(("Sentinel-2 true colour, 27 Aug", "Sentinel-1 VV (dB), 28 Aug", "Model water probability (red: > threshold)")):
            ax[i, j].set_xticks([]); ax[i, j].set_yticks([])
            if i == 0: ax[i, j].set_title(t, fontsize=9)
    fig.suptitle("Himalayan chips: first six in file order (qualitative only, no labels, no score)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.975)); Path(a.out).parent.mkdir(parents=True, exist_ok=True); fig.savefig(a.out, dpi=110); print("wrote", a.out)


if __name__ == "__main__":
    main()

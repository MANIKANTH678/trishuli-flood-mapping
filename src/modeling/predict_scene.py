import argparse
from pathlib import Path
import numpy as np, rasterio, torch
from src.modeling.dataset import normalize
from src.modeling.common import build_model

@torch.no_grad()
def predict(model, dev, db, T, stride):
    H, W = db.shape[1:]; x = normalize(db); ok = np.isfinite(x).all(0); x = np.nan_to_num(x, nan=0.0)
    pad = lambda n: T + -(-max(n - T, 0) // stride) * stride - n
    x = np.pad(x, ((0, 0), (0, pad(H)), (0, pad(W))), mode="reflect"); okp = np.pad(ok, ((0, pad(H)), (0, pad(W))))
    w1 = np.hanning(T).astype("float32") + 1e-3; win = np.outer(w1, w1)
    acc, wsum = np.zeros(x.shape[1:], "float32"), np.zeros(x.shape[1:], "float32")
    tiles = [(i, j) for i in range(0, x.shape[1] - T + 1, stride) for j in range(0, x.shape[2] - T + 1, stride) if okp[i:i + T, j:j + T].mean() > 0.05]
    for k in range(0, len(tiles), 8):
        b = tiles[k:k + 8]; xb = torch.from_numpy(np.stack([x[:, i:i + T, j:j + T] for i, j in b])).to(dev)
        for (i, j), p in zip(b, torch.sigmoid(model(xb)).cpu().numpy()[:, 0]):
            acc[i:i + T, j:j + T] += p * win; wsum[i:i + T, j:j + T] += win
    prob = np.where(wsum > 0, acc / np.maximum(wsum, 1e-6), np.nan)[:H, :W]; prob[~ok] = np.nan
    return prob.astype("float32")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="smp_resnet34"); ap.add_argument("--run"); ap.add_argument("--ckpt")
    ap.add_argument("--splits", default="post,pre,placebo,pre3,pre4"); ap.add_argument("--res", type=int, default=10)
    ap.add_argument("--proc-dir", default="data/processed"); ap.add_argument("--out-dir", default="data/processed/ai")
    ap.add_argument("--tile", type=int, default=512); ap.add_argument("--stride", type=int, default=256)
    a = ap.parse_args(); run = Path(a.run or f"outputs/ai/{a.arch}"); dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = build_model(a.arch).to(dev); model.load_state_dict(torch.load(a.ckpt or run / "model.pt", map_location=dev)); model.eval()
    Path(a.out_dir).mkdir(parents=True, exist_ok=True)
    for sp in a.splits.split(","):
        with rasterio.open(f"{a.proc_dir}/s1_{sp}_VV_{a.res}m.tif") as s: vv, prof = s.read(1, masked=True).astype("float32").filled(np.nan), s.profile
        with rasterio.open(f"{a.proc_dir}/s1_{sp}_VH_{a.res}m.tif") as s: vh = s.read(1, masked=True).astype("float32").filled(np.nan)
        prob = predict(model, dev, np.stack([vv, vh]), a.tile, a.stride)
        prof.update(dtype="float32", nodata=-9999.0, count=1, compress="deflate")
        with rasterio.open(f"{a.out_dir}/prob_{sp}_{a.res}m.tif", "w", **prof) as d: d.write(np.where(np.isfinite(prob), prob, -9999.0).astype("float32"), 1)
        print("wrote", sp)

if __name__ == "__main__":
    main()
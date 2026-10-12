"""Step 10.4: move the shipped water model into models/ and write a float16 copy that fits under GitHub's 100 MB limit.

python tools/export_fp16.py [--src outputs/ai/smp_resnet34] [--out models] [--check]

Writes models/flood_unet_resnet34_fp16.pt (all floating tensors cast to float16, ~half of the 93 MB float32 file),
models/threshold.json (copied) and models/SHA256SUMS. --check runs both models on random S1-like input and reports
the largest probability difference and the share of pixels whose >= threshold call changes.
predict_scene / evaluate load models/ automatically (src.modeling.common.load_weights casts float16 back to float32)."""
import argparse, hashlib, json, shutil
from pathlib import Path
import sys, torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default="outputs/ai/smp_resnet34"); ap.add_argument("--out", default="models")
    ap.add_argument("--arch", default="smp_resnet34"); ap.add_argument("--check", action="store_true"); a = ap.parse_args()
    src, out = Path(a.src), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fp32 = src / "model.pt" if (src / "model.pt").exists() else out / "flood_unet_resnet34.pt"
    sd = torch.load(fp32, map_location="cpu")
    half = {k: (v.half() if torch.is_tensor(v) and v.is_floating_point() else v) for k, v in sd.items()}
    dst = out / "flood_unet_resnet34_fp16.pt"; torch.save(half, dst)
    if (src / "threshold.json").exists(): shutil.copy(src / "threshold.json", out / "threshold.json")
    sums = {p.name: sha256(p) for p in (fp32, dst, out / "threshold.json") if p.exists()}
    (out / "SHA256SUMS").write_text("".join(f"{v}  {k}\n" for k, v in sums.items()))
    print(f"{fp32}: {fp32.stat().st_size / 1e6:.1f} MB -> {dst}: {dst.stat().st_size / 1e6:.1f} MB")
    res = {"fp32": str(fp32), "fp32_mb": round(fp32.stat().st_size / 1e6, 1), "fp16": str(dst), "fp16_mb": round(dst.stat().st_size / 1e6, 1), "sha256": sums}
    if a.check:
        from src.modeling.common import build_model
        thr = json.loads((out / "threshold.json").read_text())["threshold"] if (out / "threshold.json").exists() else 0.5
        m32, m16 = build_model(a.arch, pretrained=False), build_model(a.arch, pretrained=False)
        m32.load_state_dict(sd); m16.load_state_dict({k: (v.float() if torch.is_tensor(v) and v.is_floating_point() else v) for k, v in half.items()})
        m32.eval(); m16.eval()
        chips = sorted(Path("data/external/himalaya_chips/S1").glob("*_S1.tif"))
        if chips:                                    # real Sentinel-1 input: the 20 Himalayan chips (post-event, 10 m dB)
            import numpy as np, rasterio
            from src.modeling.dataset import normalize
            arr = np.stack([np.nan_to_num(normalize(rasterio.open(c).read().astype("float32")), nan=0.0) for c in chips])
            x, what = torch.from_numpy(arr), f"{len(chips)} Himalayan S1 chips (256x256, 10 m)"
        else:
            torch.manual_seed(0); x, what = torch.randn(2, 2, 256, 256), "2 random 256x256 chips (normalised space)"
        with torch.no_grad(): p32, p16 = torch.sigmoid(m32(x)), torch.sigmoid(m16(x))
        res["check"] = {"max_abs_prob_diff": float((p32 - p16).abs().max()), "mean_abs_prob_diff": float((p32 - p16).abs().mean()),
                        "flipped_at_threshold": float(((p32 >= thr) != (p16 >= thr)).float().mean()), "threshold": thr, "input": what}
        print(res["check"])
    (out / "export_fp16.json").write_text(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

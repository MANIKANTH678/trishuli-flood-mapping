import glob, json, re, shutil
from importlib import metadata
from pathlib import Path
import numpy as np

BAK = Path("outputs/doc_backups"); BAK.mkdir(parents=True, exist_ok=True)
def rw(path, fn):
    p = Path(path); shutil.copy2(p, BAK / (p.name + ".final.bak"))
    t = open(p, encoding="utf-8", newline="").read(); nl = "\r\n" if "\r\n" in t else "\n"
    new = fn(t, nl)
    open(p, "w", encoding="utf-8", newline="").write(new); print("patched", path)

def lines(swaps):
    def f(t, nl):
        out = []
        for l in t.splitlines(keepends=True):
            body = l.rstrip("\r\n"); end = l[len(body):]
            for pre, new in swaps:
                if body.startswith(pre): body = new; break
            out.append(body + end)
        return "".join(out)
    return f

rw("FINAL_REPORT.md", lambda t, nl: lines([
    ("| U-Net proxy-Himalaya IoU", "| Himalayan labelled chips | not made | no labelled Himalayan test exists; Sen1Floods11 has no Himalayan scenes |"),
    ("| Proxy-Himalaya, India + Pakistan", "| Proxy-Himalaya (withdrawn: India and Pakistan are neither mountainous nor unseen) | n/a | n/a | n/a | n/a |"),
])(t, nl).replace("python tools/unet_corridor.py", "python -m src.modeling.predict_scene --arch smp_resnet34" + nl + "    python -m src.analysis.ai_corridor"))
rw("run_all.sh", lambda t, nl: t.replace("$PY tools/unet_corridor.py", "$PY -m src.modeling.predict_scene --arch smp_resnet34" + nl + "$PY -m src.analysis.ai_corridor"))
rw("src/report/dashboard_full.py", lambda t, nl: t.replace('("validation/unet_corridor.json", "U-Net corridor check", "JSON")', '("validation/ai_corridor.json", "AI corridor check (prediction-only)", "JSON")'))

# ---- model card ----
ld = lambda p: json.load(open(p, encoding="utf-8"))
old, un, rn = ld("outputs/ai/old_baseline.json"), ld("outputs/ai/unet/metrics.json"), ld("outputs/ai/smp_resnet34/metrics.json")
tl, ul, co = ld("outputs/ai/smp_resnet34/train_log.json"), ld("outputs/ai/unet/train_log.json"), ld("outputs/validation/ai_corridor.json")
def cell(m, s):
    if s not in m["splits"]: return "not made"
    v = m["splits"][s]; lo, hi = v["iou_ci95_chip_bootstrap"]; return f"{v['at_threshold']['iou']:.3f} [{lo:.2f}, {hi:.2f}]"
def domain():
    try:
        import rasterio
        from src.modeling.dataset import S1_DIR
        pct = lambda a: np.nanpercentile(a, [5, 50, 95]).round(1)
        parts = []
        for f in sorted(glob.glob(str(S1_DIR / "*.tif")))[::4]:
            with rasterio.open(f) as s: parts.append(s.read().astype("float32").reshape(2, -1)[:, ::50])
        tr = np.concatenate(parts, axis=1); out, flag = [], False
        for i, pol in enumerate(("VV", "VH")):
            with rasterio.open(f"data/processed/s1_post_{pol}_10m.tif") as s: a = s.read(1, masked=True).astype("float32").filled(np.nan)[::10, ::10]
            t, p = pct(tr[i]), pct(a); d = float(p[1] - t[1]); flag |= abs(d) > 3.5
            out.append(f"- {pol}: Sen1Floods11 p5/p50/p95 = {t.tolist()}; Trishuli post = {p.tolist()}; median difference {d:+.1f} dB")
        out.append("- Medians differ by more than about 3.5 dB: possible radiometry mismatch; interpret with caution." if flag else "- Medians are within about 3.5 dB of the training data.")
        return "\n".join(out)
    except Exception as e: return f"- Domain check not run ({type(e).__name__}: {e})"
ex, nl_ = co["event"]["excess"], co["max_null_excess"]; ratio = ex / nl_ if nl_ > 0 else float("inf")
weak = ", ".join(f"{k} {v['iou']:.2f} (n={v['n_chips']})" for k, v in sorted(rn["splits"]["test"]["per_region"].items(), key=lambda kv: kv[1]["iou"])[:3])
table = f"""| Row | Val IoU (pooled) | Test | Bolivia (unseen region) |
|---|---|---|---|
| Old checkpoint, thr {old['threshold']} | {cell(old,'valid')} | {cell(old,'test')} | {cell(old,'bolivia')} |
| U-Net, {ul['epochs']} epochs, thr {un['threshold']} | {cell(un,'valid')} | {cell(un,'test')} | {cell(un,'bolivia')} |
| **ResNet34-U-Net, {tl['epochs']} epochs, thr {rn['threshold']}** | **{cell(rn,'valid')}** | **{cell(rn,'test')}** | **{cell(rn,'bolivia')}** |"""
Path("MODEL_CARD.md").write_text(f"""# Model card: Sentinel-1 open-water segmentation

## Model
ResNet34-encoder U-Net (segmentation-models-pytorch, ImageNet-pretrained encoder, 2-channel input). Input: Sentinel-1 VV+VH in dB, normalized as clip((x+25)/15, -3, 3). Output: per-pixel open-water probability. Threshold {rn['threshold']}, chosen on validation only.

## Training data
Sen1Floods11 hand-labelled chips (Bonafilia et al., CVPR Workshops 2020), published train/valid splits. {tl['epochs']} epochs, AdamW, masked BCE + Dice, rot90/flip augmentation, seed {tl['seed']}. Checkpoint and threshold selected on validation pooled IoU. No EMS (EMSR927) data was used for training or tuning.

## What it detects
Open water only. No allowed dataset labels debris; debris and damage evidence come from the change detector.

## Results (pooled IoU, 95% chip-bootstrap CI)
{table}

Himalayan hand-labelled chips: {cell(rn,'himalaya_chips')}. Test chips come from the training events, so Bolivia ({rn['splits']['bolivia']['n_chips']} chips) is the only unseen-region test. The two new models are not separable on test or Bolivia (intervals overlap); ResNet34 was chosen on validation IoU.

## Himalayan evidence
Sen1Floods11 has no Himalayan scenes. Corridor test (prediction-only, no flood-extent reference; shadow/layover masked, floor via HAND): new-water excess {ex:.4f} vs largest leave-one-out null {nl_:.4f} ({ratio:.2f}x), verdict: {co['verdict']}.

## Failure modes
Radar shadow in mountains; turbid or sediment-laden water; urban areas; arid scenes. Weakest test regions: {weak}.

## Radiometry check (training chips vs Trishuli post-event scene)
{domain()}

## Licences and attribution
Sen1Floods11 (Bonafilia et al., 2020). ImageNet-pretrained ResNet34 weights via segmentation-models-pytorch; check and cite the weights' licence.
""", encoding="utf-8"); print("wrote MODEL_CARD.md")

req = Path("requirements.txt"); rl = req.read_text(encoding="utf-8").splitlines() if req.exists() else []
rl = [l for l in rl if not re.match(r"\s*(torch|segmentation[-_]models[-_]pytorch)\b", l, re.I)]
for pkg in ("torch", "segmentation-models-pytorch"):
    try: rl.append(f"{pkg}=={metadata.version(pkg)}")
    except Exception as e: print("could not pin", pkg, e)
req.write_text("\n".join(dict.fromkeys(rl)) + "\n", encoding="utf-8"); print("pinned requirements.txt")
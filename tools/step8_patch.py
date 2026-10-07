import json, re, shutil
from pathlib import Path

ld = lambda p: json.load(open(p, encoding="utf-8"))
old, un, rn = ld("outputs/ai/old_baseline.json"), ld("outputs/ai/unet/metrics.json"), ld("outputs/ai/smp_resnet34/metrics.json")
tl, ul, co = ld("outputs/ai/smp_resnet34/train_log.json"), ld("outputs/ai/unet/train_log.json"), ld("outputs/validation/ai_corridor.json")

def cell(m, s):
    if s not in m["splits"]: return "not made"
    v = m["splits"][s]; lo, hi = v["iou_ci95_chip_bootstrap"]
    return f"{v['at_threshold']['iou']:.3f} [{lo:.2f}, {hi:.2f}]"

BAK = Path("outputs/doc_backups"); BAK.mkdir(parents=True, exist_ok=True)
def load(p):
    shutil.copy2(p, BAK / (Path(p).name + ".step8.bak")); return Path(p).read_text(encoding="utf-8")
def sub(txt, old_s, new_s, label, count=1):
    n = txt.count(old_s); print(("OK     " if n == count else f"MISSING({n}) ") + label)
    return txt.replace(old_s, new_s) if n == count else txt
def swap_line(txt, prefix, new, label):
    hit = 0; out = []
    for l in txt.split("\n"):
        if l.startswith(prefix): out.append(new); hit += 1
        else: out.append(l)
    print(("OK     " if hit == 1 else f"MISSING({hit}) ") + label); return "\n".join(out)

ex, nl = co["event"]["excess"], co["max_null_excess"]
ratio = ex / nl if nl > 0 else float("inf")
bo = rn["splits"]["bolivia"]; blo, bhi = bo["iou_ci95_chip_bootstrap"]
him = cell(rn, "himalaya_chips")

# ---------------- README ----------------
r = load("README.md")
r = sub(r, "A U-Net water check\n> shows no net change.",
        "A Sen1Floods11-trained water\n> model, run prediction-only on the corridor, is not separable from pre-event nulls.", "status paragraph")
r = sub(r, "`tools/signal_check.py`, `tools/unet_corridor.py`",
        "`tools/signal_check.py`, `src/modeling/predict_scene.py`, `src/analysis/ai_corridor.py`", "pipeline row 11")
r = swap_line(r, "| Train U-Net", "| Train water model | `src/modeling/train_segmentation.py` | `outputs/ai/<arch>/model.pt`, `train_log.json`, `threshold.json` |", "train row")
r = swap_line(r, "| Eval U-Net", "| Evaluate water model | `src/modeling/evaluate.py` | `outputs/ai/<arch>/metrics.json` |", "eval row")

table = f"""| Row | Val IoU (pooled) | Test | Bolivia (unseen region) |
|---|---|---|---|
| Old checkpoint, thr {old['threshold']} (the old 0.523 was a mean of per-batch IoUs) | {cell(old,'valid')} | {cell(old,'test')} | {cell(old,'bolivia')} |
| U-Net, {ul['epochs']} epochs, thr {un['threshold']} | {cell(un,'valid')} | {cell(un,'test')} | {cell(un,'bolivia')} |
| **ResNet34-U-Net, {tl['epochs']} epochs, thr {rn['threshold']}** | **{cell(rn,'valid')}** | **{cell(rn,'test')}** | **{cell(rn,'bolivia')}** |"""
section = f"""## Train / eval water model

Trained on **Sen1Floods11 v1.1** hand-labelled chips (Bonafilia et al., 2020); open water only. Checkpoint and
threshold are chosen on validation only. Pooled IoU over all valid pixels, 95% chip-bootstrap CIs:

{table}

Test chips come from the training events, so Bolivia ({bo['n_chips']} chips) is the only unseen-region test and its
interval is wide. Sen1Floods11 contains no Himalayan scenes. See `MODEL_CARD.md`.
"""
m = re.search(r"## Train / eval U-Net\n.*?(?=\n## Key results)", r, re.S)
print(("OK     " if m else "MISSING ") + "train/eval section")
if m: r = r[:m.start()] + section + r[m.end():]

r = swap_line(r, "| U-Net val IoU",
    f"| Water model (ResNet34 U-Net, Sen1Floods11), pooled IoU [95% CI] | val {cell(rn,'valid')}; test {cell(rn,'test')}; Bolivia {cell(rn,'bolivia')}. Old checkpoint: val {old['splits']['valid']['at_threshold']['iou']:.3f}, test {old['splits']['test']['at_threshold']['iou']:.3f}, Bolivia {old['splits']['bolivia']['at_threshold']['iou']:.3f} |", "key row: val IoU")
r = swap_line(r, "| U-Net proxy-Himalaya",
    f"| Labelled Himalayan chips | {him + ('' if him != 'not made' else ': no labelled Himalayan test exists; Sen1Floods11 has no Himalayan scenes')} |", "key row: himalaya")
r = swap_line(r, "| U-Net corridor water check",
    f"| AI corridor water test (prediction-only, shadow/layover masked, floor via HAND) | New-water excess main − tributary floor {100*ex:.2f}% vs largest leave-one-out null {100*nl:.2f}% ({ratio:.2f}x): {co['verdict']}. Does not independently confirm the flood |", "key row: corridor")
Path("README.md").write_text(r, encoding="utf-8")

# ---------------- situation_report.py ----------------
s = load("src/report/situation_report.py")
s = sub(s, "outputs/validation/unet_corridor.json", "outputs/validation/ai_corridor.json", "ai_corridor path (3 places)", count=3)
s = sub(s, '    pct = lambda d: 100 * d["flood_px"] / d["covered_px"]\n', '''    ai_m = J("outputs/ai/smp_resnet34/metrics.json")
    _bo = ai_m["splits"]["bolivia"]; _ci = _bo["iou_ci95_chip_bootstrap"]
    _ex, _nl = un["event"]["excess"], un["max_null_excess"]
    ai_sentence = (f"A Sen1Floods11-trained water model (ResNet34 U-Net; unseen-region IoU {_bo['at_threshold']['iou']:.2f}, 95% CI {_ci[0]:.2f}–{_ci[1]:.2f}, {_bo['n_chips']} chips; no Himalayan training scenes) "
                   f"finds a new-water excess on the main floor of {100 * _ex:.2f}% against a pre-event null maximum of {100 * _nl:.2f}%: {un['verdict']}. Prediction-only; not independent evidence.")
''', "ai_sentence block")
s = sub(s, "The U-Net (Sen1Floods11) flags {pct(un['post']):.2f}% of the corridor post and {pct(un['pre']):.2f}% pre: it does not separate the scenes and is not independent evidence.",
        "{ai_sentence}", "report sentence")
Path("src/report/situation_report.py").write_text(s, encoding="utf-8")
print("done; backups in", BAK)
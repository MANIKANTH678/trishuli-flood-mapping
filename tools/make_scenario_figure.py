"""Step 9.4 figure: the scenario range behind every headline count (no new analysis; reads the JSON the pipeline wrote).
python tools/make_scenario_figure.py  -> outputs/figures/scenario_range.png"""
import json
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

def main():
    cut = json.loads(Path("outputs/cutoff_settlements.json").read_text(encoding="utf-8"))
    imp = json.loads(Path("outputs/impact_summary.json").read_text(encoding="utf-8"))
    rows = cut["sensitivity"]["scenarios"]
    lab = [f"{r['thr']}\n{'+' if r['morph'] > 0 else ''}{r['morph']}px\n{r['bridges'][:4]}" for r in rows]
    head = [i for i, r in enumerate(rows) if r["thr"] == "base" and r["morph"] == 0 and str(r["bridges"]).startswith("fail")]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.4), gridspec_kw={"width_ratios": [3, 1.2]})
    x = range(len(rows)); co = [r.get("hospital_cut_off", 0) for r in rows]; de = [r.get("hospital_degraded", 0) for r in rows]
    ax[0].bar(x, co, color=["#b91c1c" if i in head else "#f87171" for i in x], label="cut off from every hospital")
    ax[0].bar(x, de, bottom=co, color="#fdba74", label="degraded (≥2× and ≥2 km longer)")
    ax[0].set_xticks(list(x), lab, fontsize=6.5); ax[0].set_ylabel("settlements"); ax[0].legend(fontsize=7, loc="upper left")
    ax[0].set_title("Cut-off by scenario (threshold × mask ±1 px × bridge policy); dark = headline", fontsize=8.5)
    sc = imp["sensitivity"]["scenarios"]; ks = [k for k in ("low", "base", "high") if k in sc]
    ax[1].bar(ks, [sc[k]["buildings_overlap"] for k in ks], color=["#2563eb" if k == "base" else "#93c5fd" for k in ks])
    ax[1].set_title("Buildings overlapping the mask", fontsize=8.5); ax[1].tick_params(labelsize=7)
    fig.tight_layout(); out = Path("outputs/figures/scenario_range.png"); out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150); print("wrote", out)

if __name__ == "__main__":
    main()

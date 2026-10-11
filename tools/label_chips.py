"""Step 8C: hand-label open water on each chip from the Sentinel-2 27 Aug image ONLY (the model prediction is never shown).
Left: S2 true colour. Right: S2 false colour (SWIR1-NIR-red, water is dark blue/black). Draw around water with the mouse (lasso).
Keys:  a = add lasso as water   e = erase lasso   c = clear   u = mark whole chip unusable (cloud) and skip
       n = save labelled chip and go to next     q = quit (progress kept; rerun to continue)
Pixels you never touch become 0 (dry) when you press n, except S2 nodata/cloud, which stays -1 (not scored).
python tools/label_chips.py --annotator A            (all chips)
python tools/label_chips.py --annotator B --subset 8 (second annotator, first 8 chips: noise ceiling)"""
import argparse
from pathlib import Path
import numpy as np, rasterio, matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.widgets import LassoSelector

def stretch(x):
    lo, hi = np.nanpercentile(x, 2), np.nanpercentile(x, 98); return np.clip((x - lo) / max(hi - lo, 1e-6), 0, 1)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--annotator", required=True, choices=["A", "B"])
    ap.add_argument("--subset", type=int); ap.add_argument("--dir", default="data/external/himalaya_chips"); a = ap.parse_args()
    d = Path(a.dir); names = [l.split(",")[0].replace("_S1.tif", "") for l in (d / "chips.csv").read_text().split()]
    names = names[:a.subset] if a.subset else names
    yy, xx = np.mgrid[:256, :256]; pts = np.c_[xx.ravel(), yy.ravel()]
    for name in names:
        lp = d / f"Label_{a.annotator}" / f"{name}_Label.tif"
        with rasterio.open(lp) as s: lbl, prof = s.read(1), s.profile
        if (lbl != -1).any() or prof.get("tags") == "done": continue
        with rasterio.open(d / "S2" / f"{name}_S2.tif") as s: s2 = s.read()
        if np.isnan(s2).all(): print(name, "has no S2 pixels: skipped"); continue
        nod = np.isnan(s2).any(0); water = np.zeros((256, 256), bool); state = {"act": None}
        fig, ax = plt.subplots(1, 2, figsize=(12, 6)); fig.suptitle(f"{name}  annotator {a.annotator}  (a add, e erase, c clear, u unusable, n next, q quit)")
        tc, fc = np.dstack([stretch(s2[i]) for i in (0, 1, 2)]), np.dstack([stretch(s2[i]) for i in (4, 3, 0)])
        ims = [ax[0].imshow(tc), ax[1].imshow(fc)]; ov = [x.imshow(np.zeros((256, 256, 4))) for x in ax]
        def redraw():
            o = np.zeros((256, 256, 4)); o[water] = (0, 0.6, 1, 0.45); o[nod] = (1, 0, 0, 0.25)
            for im in ov: im.set_data(o)
            fig.canvas.draw_idle()
        def on_lasso(verts):
            sel = MPath(verts).contains_points(pts).reshape(256, 256); state["sel"] = sel
        lassos = [LassoSelector(x, on_lasso) for x in ax]
        def on_key(ev):
            nonlocal water
            if ev.key in ("a", "e") and "sel" in state: water = (water | state["sel"]) if ev.key == "a" else (water & ~state["sel"]); redraw()
            elif ev.key == "c": water[:] = False; redraw()
            elif ev.key in ("n", "u", "q"): state["act"] = ev.key; plt.close(fig)
        fig.canvas.mpl_connect("key_press_event", on_key); redraw(); plt.show()
        if state["act"] == "q": break
        out = np.where(nod, -1, water.astype("int16")).astype("int16") if state["act"] == "n" else np.full((256, 256), -1, "int16")
        if state["act"] == "u": out[0, 0] = -2                      # marks 'seen, unusable' so the chip is not shown again
        with rasterio.open(lp, "w", **prof) as s: s.write(np.where(out == -2, -1, out)[None]); s.update_tags(status="unusable" if state["act"] == "u" else "labelled")
        print(name, state["act"], int(water.sum()), "water px")

if __name__ == "__main__":
    main()

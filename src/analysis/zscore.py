#!/usr/bin/env python3
import argparse, json, re
from pathlib import Path
import numpy as np, pandas as pd, rasterio, geopandas as gpd
from rasterio.features import rasterize
from pyproj import Transformer
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource

P = Path("data/processed")
ap = argparse.ArgumentParser()
ap.add_argument("--first", default="pre"); ap.add_argument("--second", default="post")
ap.add_argument("--res", type=int, default=30, choices=[10, 30]); ap.add_argument("--smooth", type=int, default=1)
ap.add_argument("--floor-m", type=float, default=30); ap.add_argument("--ctrl-m", type=float, default=100)
ap.add_argument("--thr", type=float, default=3.5); ap.add_argument("--min-patch", type=int, default=8)
ap.add_argument("--main-names", default=r"trishuli|trisuli|bhote\s*koshi|bhotekoshi")
ap.add_argument("--main-line"); ap.add_argument("--main-buf-m", type=float, default=1500)
ap.add_argument("--trib-min-m", type=float, default=2500); ap.add_argument("--tag", default="event")
a = ap.parse_args(); R = a.res
MINPX = a.min_patch * (9 if R == 10 else 1)

def rd(path):
    with rasterio.open(path) as s:
        return s.read(1, masked=True).astype("float32").filled(np.nan), s.transform, s.crs, s.res[0]
def up(x): return x if R == 30 else np.repeat(np.repeat(x, 3, 0), 3, 1)
def smooth_db(db, n):
    if n <= 1: return db
    ok = np.isfinite(db); lin = np.where(ok, 10 ** (db / 10), 0).astype("float32")
    num, den = ndi.uniform_filter(lin, n), ndi.uniform_filter(ok.astype("float32"), n)
    with np.errstate(divide="ignore", invalid="ignore"): out = 10 * np.log10(num / den)
    out[(den < 0.5) | ~np.isfinite(out)] = np.nan; return out.astype("float32")
def patch_filter(m, minpx):
    lab, n = ndi.label(m)
    if n == 0: return m
    keep = np.zeros(n + 1, bool); keep[1:] = ndi.sum(m, lab, np.arange(1, n + 1)) >= minpx
    return keep[lab]

_, T, crs, res = rd(P / f"s1_{a.first}_VV_{R}m.tif")
lr = {pol: smooth_db(rd(P / f"s1_{a.second}_{pol}_{R}m.tif")[0], a.smooth)
           - smooth_db(rd(P / f"s1_{a.first}_{pol}_{R}m.tif")[0], a.smooth) for pol in ("VV", "VH")}
dem = rd(P / f"dem_{R}m.tif")[0]
hand, mask = up(rd(P / "hand_30m.tif")[0]), up(rd(P / "radar_mask_30m.tif")[0])
base = np.isfinite(hand) & np.isfinite(dem)
valid = base & np.isfinite(lr["VV"]) & np.isfinite(lr["VH"]) & (mask == 0)

# --- main stem from OSM names (or a hand-drawn line); EMS is NOT used here ---
rv = gpd.read_file("data/raw/osm/rivers.geojson").to_crs(crs)
if a.main_line: main = gpd.read_file(a.main_line).to_crs(crs)
else:
    cols = [c for c in rv.columns if c.startswith("name")]
    nm = rv[cols].fillna("").agg(" ".join, axis=1) if cols else pd.Series("", index=rv.index)
    main = rv[nm.str.contains(a.main_names, case=False, regex=True)]
if main.empty: raise SystemExit("no main-stem rivers matched: pass --main-line (draw one in QGIS)")
print(f"main-stem OSM segments: {len(main)}")
ms = rasterize(main.geometry, out_shape=dem.shape, transform=T, all_touched=True)
dist = ndi.distance_transform_edt(ms == 0) * res

main_all = base & (hand <= a.floor_m) & (dist <= a.main_buf_m)
floor = valid & (hand <= a.floor_m)
classes = {"main_floor": floor & (dist <= a.main_buf_m), "trib_floor": floor & (dist >= a.trib_min_m),
           "hillslope_ctrl": valid & (hand >= a.ctrl_m)}
ctrl = classes["hillslope_ctrl"]
obs = {"main_floor_px": int(main_all.sum()),
       "observable_fraction": float(classes["main_floor"].sum() / max(main_all.sum(), 1)),
       "unobservable_by_cause": {n: float((main_all & (mask == c)).sum() / max(main_all.sum(), 1))
                                 for c, n in {1: "layover", 2: "shadow", 3: "cast_shadow", 4: "poor_lia"}.items()}}
print(obs)

# --- robust z, per 250 m elevation band of the hillslope control ---
band = np.digitize(dem, np.arange(0, 6001, 250)); z = {}
for pol, x in lr.items():
    gm = np.median(x[ctrl]); gs = 1.4826 * np.median(np.abs(x[ctrl] - gm))
    med, sig = np.full(x.shape, gm, "float32"), np.full(x.shape, gs, "float32")
    for b in np.unique(band[ctrl]):
        m = ctrl & (band == b)
        if m.sum() >= 5000:
            mb = np.median(x[m]); sb = 1.4826 * np.median(np.abs(x[m] - mb))
            med[band == b], sig[band == b] = mb, max(sb, 1e-3)
    z[pol] = (x - med) / sig

neg = {p: patch_filter((z[p] < -a.thr) & valid, MINPX) for p in z}
pos = {p: patch_filter((z[p] > a.thr) & valid, MINPX) for p in z}
stats = {p: {c: {"n_px": int(m.sum()), "median_z": float(np.median(z[p][m])) if m.any() else None,
                 "frac_neg": float(neg[p][m].mean()) if m.any() else None,
                 "frac_pos": float(pos[p][m].mean()) if m.any() else None}
             for c, m in classes.items()} for p in z}

# --- block bootstrap (2 km blocks) of main-minus-tributary exceedance ---
B = max(int(2000 / res), 1)
def tab(m, ex):
    r, c = np.nonzero(m)
    g = pd.DataFrame({"b": (r // B) * 100000 + c // B, "e": ex[r, c]}).groupby("b")["e"].agg(["size", "sum"])
    return g["size"].to_numpy(), g["sum"].to_numpy()
def boot(ex, n=2000):
    rng = np.random.default_rng(0); (nm_, em), (nt, et) = tab(classes["main_floor"], ex), tab(classes["trib_floor"], ex)
    d, q = [], []
    for _ in range(n):
        i, j = rng.integers(0, len(nm_), len(nm_)), rng.integers(0, len(nt), len(nt))
        fm, ft = em[i].sum() / nm_[i].sum(), et[j].sum() / nt[j].sum()
        d.append(fm - ft); q.append(fm / max(ft, 1e-4))
    pc = lambda v: [float(np.percentile(v, k)) for k in (2.5, 50, 97.5)]
    return {"excess_ci": pc(d), "ratio_ci": pc(q)}
bs = {p: {"neg": boot(neg[p]), "pos": boot(pos[p])} for p in z}

# --- latitude profile along the main stem ---
r, c = np.nonzero(main_all)
lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(T.c + (c + .5) * T.a, T.f + (r + .5) * T.e)
okpx, rb, rows = valid[r, c], np.floor(lat / 0.01).astype(int), []
for b in np.unique(rb):
    s = rb == b; sk = s & okpx; row = {"lat": (b + .5) * 0.01, "obs_frac": sk.sum() / s.sum()}
    for p in z:
        for k, arr in (("neg", neg[p]), ("pos", pos[p])):
            row[f"{p}_{k}"] = float(arr[r[sk], c[sk]].mean()) if sk.sum() >= 30 else np.nan
    rows.append(row)
pf = pd.DataFrame(rows).sort_values("lat"); Path("outputs/figures").mkdir(parents=True, exist_ok=True)
pf.to_csv(f"outputs/diagnostics/step3_profile_{a.tag}.csv", index=False)
fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
ax[0].plot(pf.lat, pf.obs_frac, "k"); ax[0].set_ylabel("observable fraction")
for i, k, t in ((1, "neg", "darkening"), (2, "pos", "brightening")):
    for p, col in (("VV", "C0"), ("VH", "C1")):
        ax[i].plot(pf.lat, pf[f"{p}_{k}"], col, label=p)
        ax[i].axhline(stats[p]["trib_floor"][f"frac_{k}"] or 0, color=col, ls="--", lw=.8)
    ax[i].set_ylabel(f"frac |z|>{a.thr} ({t})"); ax[i].legend()
ax[2].set_xlabel("latitude (dashed = tributary-floor baseline)"); fig.tight_layout()
fig.savefig(f"outputs/figures/step3_profile_{a.tag}.png", dpi=150)

# --- map: z on valley floors over hillshade; unobservable main floor in magenta ---
rs, cs = np.nonzero(main_all | classes["trib_floor"]); k = 50
sl = (slice(max(rs.min() - k, 0), rs.max() + k), slice(max(cs.min() - k, 0), cs.max() + k))
hs = LightSource(315, 45).hillshade(np.nan_to_num(dem[sl], nan=float(np.nanmean(dem))), dx=res, dy=res)
zz = np.where((classes["main_floor"] | classes["trib_floor"])[sl], np.clip(z["VV"][sl], -6, 6), np.nan)
fig, ax = plt.subplots(figsize=(8, 10)); ax.imshow(hs, cmap="gray")
ax.imshow(np.where((main_all & ~valid)[sl], 1.0, np.nan), cmap="spring", vmin=0, vmax=1)
im = ax.imshow(zz, cmap="RdBu_r", vmin=-6, vmax=6); ax.axis("off")
fig.colorbar(im, shrink=.5, label=f"z of VV change ({a.second} vs {a.first}); magenta = unobservable")
fig.text(.01, .005, "Contains modified Copernicus Sentinel data 2026 | Copernicus WorldDEM-30 (c) DLR/Airbus | (c) OpenStreetMap contributors", fontsize=6)
fig.savefig(f"outputs/figures/step3_map_{a.tag}.png", dpi=200, bbox_inches="tight")

Path(f"outputs/diagnostics/step3_{a.tag}.json").write_text(json.dumps(
    {"tag": a.tag, "args": vars(a), "geometry": json.load(open("outputs/diagnostics/look_geometry.json")),
     "observability": obs, "stats": stats, "bootstrap": bs}, indent=2))
print(json.dumps({"stats": stats, "bootstrap": bs}, indent=2))

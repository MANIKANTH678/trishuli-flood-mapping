#!/usr/bin/env python3
"""Pre/post Sentinel-1 VV pair for one Bidur valley-floor reach, for the deck.

Run from the repo root:
    python tools/make_bidur_pair.py
Writes outputs/figures/bidur_pre_vv.png, bidur_post_vv.png and bidur_box.json.
Same extent, same 1600x1600 px, same -25..0 dB stretch, no margins or titles.
"""
import argparse, json
from pathlib import Path
import numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds, transform as warp_pts
from rasterio.features import shapes
from scipy.ndimage import uniform_filter
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

CLASSES = {1: ("flood-like (water-like change)", "#22D3EE"),
           2: ("dark change", "#F59E0B"),
           3: ("bright change", "#EC4899")}

ap = argparse.ArgumentParser()
ap.add_argument("--proc-dir", default="data/processed")
ap.add_argument("--cls", default="data/processed/fused_class_30m.tif")
ap.add_argument("--pre", default="pre"); ap.add_argument("--post", default="post")
ap.add_argument("--search", default="85.10,27.86,85.24,27.98",
                help="lon/lat window around Bidur to look for the densest reach")
ap.add_argument("--bbox", help="force W,S,E,N in lon/lat and skip the search")
ap.add_argument("--size-km", type=float, default=3.0)
ap.add_argument("--vmin", type=float, default=-25); ap.add_argument("--vmax", type=float, default=0)
ap.add_argument("--px", type=int, default=1600)
ap.add_argument("--out", default="outputs/figures")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

def vv_path(split):
    for r in (10, 20, 30):
        p = Path(a.proc_dir) / f"s1_{split}_VV_{r}m.tif"
        if p.exists(): return p
    raise SystemExit(f"no s1_{split}_VV_*m.tif in {a.proc_dir}")
pre_p, post_p = vv_path(a.pre), vv_path(a.post)

with rasterio.open(a.cls) as c:
    crs = c.crs
    if a.bbox:
        W, S, E, N = map(float, a.bbox.split(","))
        x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, W, S, E, N)
    else:   # densest square of size-km inside the search window
        sx0, sy0, sx1, sy1 = transform_bounds("EPSG:4326", crs, *map(float, a.search.split(",")))
        win = from_bounds(sx0, sy0, sx1, sy1, c.transform).round_offsets().round_lengths()
        cl = c.read(1, window=win); t = c.window_transform(win)
        det = np.isin(cl, list(CLASSES)).astype("float32")
        k = max(3, int(round(a.size_km * 1000 / abs(t.a))))
        dens = uniform_filter(det, size=k, mode="constant")
        h = k // 2; dens[:h, :] = dens[-h:, :] = 0; dens[:, :h] = dens[:, -h:] = 0
        r, cc = np.unravel_index(np.argmax(dens), dens.shape)
        cx, cy = t * (cc + 0.5, r + 0.5); half = a.size_km * 500
        x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
        print(f"densest {a.size_km} km box: {dens[r, cc]*100:.1f}% of pixels detected")
    cwin = from_bounds(x0, y0, x1, y1, c.transform)
    cls = c.read(1, window=cwin, boundless=True, fill_value=255,
                 out_shape=(a.px, a.px), resampling=rasterio.enums.Resampling.nearest)

def read_db(p):
    with rasterio.open(p) as s:
        if s.crs != crs: raise SystemExit(f"{p} CRS {s.crs} differs from class raster {crs}")
        w = from_bounds(x0, y0, x1, y1, s.transform)
        v = s.read(1, window=w, boundless=True, masked=True, out_shape=(a.px, a.px),
                   resampling=rasterio.enums.Resampling.bilinear).astype("float32").filled(np.nan)
    if np.nanmedian(v) > 0:   # linear power, not dB
        with np.errstate(divide="ignore", invalid="ignore"): v = 10 * np.log10(v)
    return v

def render(arr, path, outline):
    dpi = 100
    fig = plt.figure(figsize=(a.px / dpi, a.px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.imshow(arr, cmap="gray", vmin=a.vmin, vmax=a.vmax, interpolation="nearest",
              extent=(0, a.px, a.px, 0))
    ax.set_facecolor("black")
    if outline:
        tr = rasterio.Affine.identity()
        for k, (_, col) in CLASSES.items():
            m = (cls == k).astype("uint8")
            for geom, val in shapes(m, mask=m.astype(bool), transform=tr):
                for ring in geom["coordinates"]:
                    xs, ys = zip(*ring); ax.plot(xs, ys, color=col, lw=2.2, solid_joinstyle="round")
    ax.set_xlim(0, a.px); ax.set_ylim(a.px, 0)
    fig.savefig(path, dpi=dpi, pad_inches=0); plt.close(fig)

pre, post = read_db(pre_p), read_db(post_p)
render(pre, out / "bidur_pre_vv.png", False)
render(post, out / "bidur_post_vv.png", True)

lon, lat = warp_pts(crs, "EPSG:4326", [x0, x1], [y0, y1])
px_m = (x1 - x0) / a.px
info = {"bbox_lonlat_WSEN": [round(lon[0], 5), round(lat[0], 5), round(lon[1], 5), round(lat[1], 5)],
        "bbox_projected": [x0, y0, x1, y1], "crs": str(crs), "size_km": a.size_km,
        "pre": str(pre_p), "post": str(post_p), "classes": str(a.cls),
        "stretch_db": [a.vmin, a.vmax], "png_px": a.px, "render_px_m": round(px_m, 2),
        "pixels_by_class_in_box": {CLASSES[k][0]: int((cls == k).sum()) for k in CLASSES},
        "legend": {v[0]: v[1] for v in CLASSES.values()}}
json.dump(info, open(out / "bidur_box.json", "w"), indent=1)
print(json.dumps(info["bbox_lonlat_WSEN"]), "->", out / "bidur_pre_vv.png", out / "bidur_post_vv.png")

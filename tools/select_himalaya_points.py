"""Pre-register the Himalayan evaluation chips BEFORE looking at any model prediction.
Reads only terrain, radar-geometry, S2-cloud and pre-event OSM river layers (no probabilities, no masks, no EMS).
Strata: main stem (Trishuli / Bhote Koshi floor), tributary floors (>= 3 km from the main stem), hillside radar shadow/layover.
Writes data/external/himalaya_chips/points.csv and appends its SHA-256 to docs/validation_log.md.

python tools/select_himalaya_points.py --n-main 8 --n-trib 8 --n-hill 4 --seed 2026"""
import argparse, hashlib, datetime as dt
from pathlib import Path
import numpy as np, rasterio, geopandas as gpd
from rasterio.features import rasterize
from scipy import ndimage as ndi
from pyproj import Transformer

MAIN = r"trishuli|trisuli|bhote\s*koshi|bhotekoshi"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hand", default="data/processed/hand_30m.tif"); ap.add_argument("--radar-mask", default="data/processed/radar_mask_30m.tif")
    ap.add_argument("--s2-clear", default="data/interim/s2/20260827/clear_30m.tif"); ap.add_argument("--rivers", default="data/raw/osm/rivers.geojson")
    ap.add_argument("--n-main", type=int, default=8); ap.add_argument("--n-trib", type=int, default=8); ap.add_argument("--n-hill", type=int, default=4)
    ap.add_argument("--spacing-m", type=float, default=3000); ap.add_argument("--min-clear", type=float, default=0.15); ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="data/external/himalaya_chips/points.csv"); ap.add_argument("--log", default="docs/validation_log.md")
    a = ap.parse_args()
    with rasterio.open(a.hand) as s: hand, T, crs, res = s.read(1, masked=True).filled(np.nan).astype("float32"), s.transform, s.crs, s.res[0]
    with rasterio.open(a.radar_mask) as s: rmask = s.read(1)
    with rasterio.open(a.s2_clear) as s: clear = s.read(1, masked=True).filled(0).astype("float32")
    rv = gpd.read_file(a.rivers).to_crs(crs); cols = [c for c in rv.columns if c.startswith("name")]
    is_main = rv[cols].fillna("").astype(str).agg(" ".join, axis=1).str.contains(MAIN, case=False, regex=True) if cols else np.zeros(len(rv), bool)
    burn = lambda g: rasterize(g.geometry, out_shape=hand.shape, transform=T, all_touched=True).astype(bool) if len(g) else np.zeros(hand.shape, bool)
    d_main = ndi.distance_transform_edt(~burn(rv[is_main])) * res; d_any = ndi.distance_transform_edt(~burn(rv)) * res
    k = int(1280 / res)                                                   # chip half-width (256 px x 10 m)
    clear_frac = ndi.uniform_filter((clear > 0.9).astype("float32"), 2 * k + 1)
    edge = np.zeros(hand.shape, bool); edge[k:-k, k:-k] = True
    ok = edge & (clear_frac >= a.min_clear) & (clear > 0.9) & np.isfinite(hand)   # cloudy pixels inside a chip are labelled -1 (ignored)
    strata = {"main": ok & (d_main <= 150) & (hand <= 10) & (rmask == 0),
              "trib": ok & (d_any <= 150) & (d_main >= 3000) & (hand <= 10) & (rmask == 0),
              "hill": ok & (rmask != 0) & (hand > 100) & (d_any >= 1000)}
    want = {"main": a.n_main, "trib": a.n_trib, "hill": a.n_hill}
    rng = np.random.default_rng(a.seed); chosen = []
    to_ll = Transformer.from_crs(crs, 4326, always_xy=True)
    for name, m in strata.items():
        rr, cc = np.where(m); order = rng.permutation(len(rr)); n = 0
        for i in order:
            x, y = T * (cc[i] + .5, rr[i] + .5)
            if all(np.hypot(x - px, y - py) >= a.spacing_m for _, _, px, py in chosen):
                chosen.append((name, n, x, y)); n += 1
                if n == want[name]: break
        if n < want[name]: print(f"warning: only {n} {name} points satisfy the rules")
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["name,lon,lat,stratum"] + [f"{s}_{i:02d},{lo:.5f},{la:.5f},{s}" for s, i, x, y in chosen for lo, la in [to_ll.transform(x, y)]]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()[:16]
    Path(a.log).parent.mkdir(parents=True, exist_ok=True)
    with open(a.log, "a", encoding="utf-8") as f:
        f.write(f"\n- {dt.datetime.now():%Y-%m-%d %H:%M} Himalayan chip points pre-registered before any prediction was viewed: "
                f"{out.as_posix()} sha256[:16]={sha} ({len(chosen)} points; strata main/trib/hill; seed {a.seed}).\n")
    print(out, sha, {s: sum(1 for c in chosen if c[0] == s) for s in want})

if __name__ == "__main__":
    main()

import argparse, json, warnings
from pathlib import Path
import numpy as np, geopandas as gpd
from rasterio.features import rasterize
from scipy import ndimage as ndi
from src.analysis.changelib import domain, patch_filter, rd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", default="pre,placebo,pre3,pre4"); ap.add_argument("--post", default="post")
    ap.add_argument("--run", default="outputs/ai/smp_resnet34"); ap.add_argument("--prob-dir", default="data/processed/ai")
    ap.add_argument("--floor-m", type=float, default=30); ap.add_argument("--min-patch", type=int, default=72)      # 8 px at 30 m
    ap.add_argument("--main-names", default=r"trishuli|trisuli|bhote\s*koshi|bhotekoshi")
    ap.add_argument("--main-buf-m", type=float, default=1500); ap.add_argument("--trib-min-m", type=float, default=2500)
    ap.add_argument("--out", default="outputs/validation/ai_corridor.json")
    a = ap.parse_args(); refs = a.refs.split(","); thr = json.load(open(Path(a.run) / "threshold.json"))["threshold"]
    P = lambda s: rd(Path(a.prob_dir) / f"prob_{s}_10m.tif")[0]
    hand, mask, dem = domain("data/processed", 10)
    _, prof = rd(Path(a.prob_dir) / f"prob_{a.post}_10m.tif"); T, crs = prof["transform"], prof["crs"]
    rv = gpd.read_file("data/raw/osm/rivers.geojson").to_crs(crs); cols = [c for c in rv.columns if c.startswith("name")]
    stem = rv[rv[cols].fillna("").agg(" ".join, axis=1).str.contains(a.main_names, case=False, regex=True)] if cols else rv.iloc[0:0]
    if stem.empty: raise SystemExit("no main-stem rivers matched (see zscore.py --main-line)")
    dist = ndi.distance_transform_edt(rasterize(stem.geometry, out_shape=dem.shape, transform=T, all_touched=True) == 0) * 10.0
    ok = np.isfinite(hand) & np.isfinite(dem) & (mask == 0) & (hand <= a.floor_m)
    cls = {"main_floor": ok & (dist <= a.main_buf_m), "trib_floor": ok & (dist >= a.trib_min_m)}

    def new_water(target, others):
        pt = P(target)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); po = np.nanmedian(np.stack([P(s) for s in others]), axis=0)
        nw = patch_filter((pt > thr) & (po < thr), a.min_patch)                   # NaN compares False
        d = {k: float(nw[m].mean()) for k, m in cls.items()}; return {**d, "excess": d["main_floor"] - d["trib_floor"]}
    ev = new_water(a.post, refs); nulls = {j: new_water(j, [r for r in refs if r != j]) for j in refs}
    worst = max(n["excess"] for n in nulls.values())
    res = {"threshold": thr, "prediction_only": True, "event": ev, "nulls": nulls, "max_null_excess": worst,
           "verdict": "event exceeds every leave-one-out null by more than 2x" if ev["excess"] > 2 * max(worst, 1e-4) else "not separable from the nulls",
           "note": "Model trained on Sen1Floods11 (flat floodplains); radar shadow/layover masked via the DEM mask, floor via HAND."}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(res, indent=2)); print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
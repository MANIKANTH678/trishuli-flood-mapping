import argparse, json
from pathlib import Path
import numpy as np, rasterio

def fuse(s1, s2):
    s1_obs, s2_obs = np.isin(s1, (0, 1, 2, 3)), np.isin(s2, (0, 1, 2))
    f1, f2 = np.isin(s1, (1, 2, 3)), np.isin(s2, (1, 2))
    fused = np.full(s1.shape, 255, np.uint8)
    fused[s1 == 253] = 253; fused[s1_obs | s2_obs] = 0; fused[(s1 == 254) & ~s2_obs] = 254
    fused[s1 == 3] = 3; fused[(s1 == 2) | (s2 == 2)] = 2; fused[(s1 == 1) | (s2 == 1)] = 1
    source = (f1 * 1 + f2 * 2).astype(np.uint8)                     # 1 = S1 only, 2 = S2 only, 3 = both
    conf = np.zeros(s1.shape, np.uint8)
    conf[f1 & f2] = 3                                               # both sensors agree
    conf[(f1 & ~f2 & ~s2_obs) | (f2 & ~f1 & ~s1_obs)] = 2          # one sensor, the other not observing
    conf[(f1 & ~f2 & s2_obs) | (f2 & ~f1 & s1_obs)] = 1            # one sensor, the other observed and disagrees
    coverage = (s1_obs * 1 + s2_obs * 2).astype(np.uint8)           # bit flags: 1 = S1 assessed, 2 = S2 clear
    return fused, source, conf, coverage

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--s1", default="data/processed/detect_class_30m.tif"); ap.add_argument("--s2", default="data/processed/s2_class_30m.tif")
    ap.add_argument("--out-dir", default="data/processed"); a = ap.parse_args()
    with rasterio.open(a.s1) as s: s1, prof = s.read(1), s.profile
    if Path(a.s2).exists():
        with rasterio.open(a.s2) as s: s2 = s.read(1)
    else: s2 = np.full(s1.shape, 255, np.uint8); print("no S2 raster: fusing S1 only")
    fused, source, conf, cov = fuse(s1, s2); prof.update(dtype="uint8", nodata=255, count=1, compress="deflate")
    def put(n, x):
        with rasterio.open(Path(a.out_dir) / n, "w", **prof) as d: d.write(x.astype("uint8"), 1)
    put("fused_class_30m.tif", fused); put("fusion_source_30m.tif", source); put("fusion_confidence_30m.tif", conf); put("coverage_30m.tif", cov)
    put("flood_mask.tif", fused == 1); put("debris_mask.tif", (fused == 2) | (fused == 3)); put("observable_mask.tif", cov > 0)
    fl = np.isin(fused, (1, 2, 3)); pk = 900 / 1e6
    print(json.dumps({"flagged_km2": float(fl.sum() * pk), "s1_only": float((source[fl] == 1).sum() * pk),
          "s2_only": float((source[fl] == 2).sum() * pk), "both": float((source[fl] == 3).sum() * pk),
          "observed_by_s2_km2": float(((cov & 2) > 0).sum() * pk)}, indent=2))
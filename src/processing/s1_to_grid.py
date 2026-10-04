import argparse
from pathlib import Path
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from src.processing.grid import make_grids

ND = -9999.0
TC, OUT = Path("data/interim/s1_tc"), Path("data/processed")

def write(path, arr, t, epsg):
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=1, dtype="float32", crs=f"EPSG:{epsg}", transform=t,
                       nodata=ND, compress="deflate", tiled=True) as d:
        d.write(np.where(np.isfinite(arr), arr, ND).astype("float32"), 1)

def mosaic_linear(files, t, W, H, epsg):
    acc = np.zeros((H, W)); cnt = np.zeros((H, W), np.uint16)
    for f in files:
        tmp = np.full((H, W), np.nan, np.float32)
        with rasterio.open(f) as src:
            reproject(rasterio.band(src, 1), tmp, src_transform=src.transform,
                      src_crs=src.crs or f"EPSG:{epsg}", src_nodata=0,
                      dst_transform=t, dst_crs=f"EPSG:{epsg}", dst_nodata=np.nan,
                      resampling=Resampling.nearest)
        ok = np.isfinite(tmp) & (tmp > 0)
        acc[ok] += tmp[ok]; cnt[ok] += 1
    out = np.full((H, W), np.nan, np.float32); m = cnt > 0
    out[m] = acc[m] / cnt[m]
    return out

def block_mean(a, f=3, min_valid=5):
    h, w = a.shape; ok = np.isfinite(a)
    s = np.where(ok, a, 0).reshape(h // f, f, w // f, f).sum((1, 3))
    c = ok.reshape(h // f, f, w // f, f).sum((1, 3))
    out = (s / np.maximum(c, 1)).astype(np.float32); out[c < min_valid] = np.nan
    return out

def db(lin):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(lin > 0, 10 * np.log10(lin), np.nan)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True); ap.add_argument("--epsg", required=True)
    ap.add_argument("--dem", default="data/raw/dem/dem_glo30_wgs84.tif"); ap.add_argument("--splits", default="pre,post")
    a = ap.parse_args()
    bbox = tuple(map(float, a.bbox.split(","))); g = make_grids(bbox, a.epsg)
    OUT.mkdir(parents=True, exist_ok=True)

    for res in (10, 30):
        t, W, H = g[res]; dem = np.full((H, W), np.nan, np.float32)
        with rasterio.open(a.dem) as src:
            reproject(rasterio.band(src, 1), dem, src_nodata=-9999, dst_nodata=np.nan,
                      dst_transform=t, dst_crs=f"EPSG:{a.epsg}", resampling=Resampling.bilinear)
        write(OUT / f"dem_{res}m.tif", dem, t, a.epsg)

    for split in a.splits.split(","):
        for pol in ("VV", "VH"):
            files = sorted((TC / split).glob(f"*.data/Sigma0_{pol}.img"))
            if not files: raise SystemExit(f"missing Sigma0_{pol} for {split}")
            t10, W, H = g[10]
            lin = mosaic_linear(files, t10, W, H, a.epsg)
            write(OUT / f"s1_{split}_{pol}_10m.tif", db(lin), t10, a.epsg)
            lin30 = block_mean(lin); t30 = g[30][0]
            write(OUT / f"s1_{split}_{pol}_30m.tif", db(lin30), t30, a.epsg)
            v = db(lin30); print(f"{split} {pol}: median {np.nanmedian(v):.1f} dB, "
                                 f"valid {np.isfinite(v).mean():.0%}")

if __name__ == "__main__":
    main()
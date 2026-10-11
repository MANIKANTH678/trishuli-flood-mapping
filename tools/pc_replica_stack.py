#!/usr/bin/env python3
"""Rebuild the five track-85 Sentinel-1 scenes on THIS repo's 30 m grid from Microsoft Planetary Computer
(Sentinel-1 RTC, no login), into a separate folder, so the detector and class-level nulls can run on a machine
without SNAP or the 10 m SAFE stack. Allowed input only (Sentinel-1). It never touches data/processed.

python tools/pc_replica_stack.py --grid data/processed/dem_30m.tif --out data/processed_pc

Note: PC RTC is terrain-flattened gamma0, the SNAP stack is sigma0 terrain-corrected. Numbers from the replica are a
cross-check of the method, not a replacement for the SNAP-stack numbers."""
import argparse, shutil
from pathlib import Path
import numpy as np, rasterio, pystac_client, planetary_computer
from rasterio.warp import reproject, Resampling, transform_bounds

SCENES = {"pre4": "2026-07-11", "pre3": "2026-07-23", "placebo": "2026-08-04", "pre": "2026-08-16", "post": "2026-08-28"}
TRACK, DIRECTION = 85, "ascending"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--grid", default="data/processed/dem_30m.tif")
    ap.add_argument("--out", default="data/processed_pc"); ap.add_argument("--src", default="data/processed")
    a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    with rasterio.open(a.grid) as g: prof, T, crs, shp = g.profile, g.transform, g.crs, g.shape
    bbox = transform_bounds(crs, "EPSG:4326", *rasterio.transform.array_bounds(*shp, T))
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
    prof.update(dtype="float32", nodata=np.nan, count=1, compress="deflate", predictor=3)
    for split, day in SCENES.items():
        items = [it for it in cat.search(collections=["sentinel-1-rtc"], bbox=bbox, datetime=f"{day}/{day}").items()
                 if it.properties.get("sat:relative_orbit") == TRACK and it.properties.get("sat:orbit_state") == DIRECTION]
        if not items: raise SystemExit(f"no track {TRACK} scene on {day}")
        for pol in ("VV", "VH"):
            lin = np.zeros(shp, "float64"); n = np.zeros(shp, "float64")
            for it in items:                                  # mosaic the frames of that pass in linear power
                with rasterio.open(it.assets[pol.lower()].href) as s:
                    dst = np.full(shp, np.nan, "float32")
                    reproject(rasterio.band(s, 1), dst, dst_transform=T, dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.average)
                ok = np.isfinite(dst) & (dst > 0); lin[ok] += dst[ok]; n[ok] += 1
            with np.errstate(divide="ignore", invalid="ignore"): db = (10 * np.log10(lin / n)).astype("float32")
            db[n == 0] = np.nan
            with rasterio.open(out / f"s1_{split}_{pol}_30m.tif", "w", **prof) as d: d.write(db, 1)
            print(split, day, pol, f"{np.isfinite(db).mean():.3f} valid", flush=True)
    for f in ("hand_30m.tif", "radar_mask_30m.tif", "dem_30m.tif"):      # same domain files as the SNAP run
        shutil.copy(Path(a.src) / f, out / f)
    (out / "SOURCE.txt").write_text("Sentinel-1 RTC (Microsoft Planetary Computer), track 85 ascending, reprojected to the grid of "
                                    f"{a.grid}. Contains modified Copernicus Sentinel data 2026.\n")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""PC route (`python -m src.run --s1-source pc`): Sentinel-1 RTC from Microsoft Planetary Computer, no login, no SNAP.

Replaces the fetch_s1 / unzip_s1 / check_stack / snap / grid stages of the SNAP route and writes the SAME files the
downstream stages read:
  data/processed/dem_30m.tif, dem_10m.tif           the analysis grid (src.processing.s1_to_grid.grid_dem, as in the SNAP route)
  data/processed/s1_{split}_{VV,VH}_30m.tif         dB, nodata -9999, on that grid (split = post, pre, placebo, pre3, pre4)
  data/raw/sentinel1/pc_annotation/pre/*.xml        GRD product annotation of the nearest pre scene (src.analysis.geometry --ann-dir)
  data/raw/sentinel1/pc_source.json                 what was used, labelled "PC RTC gamma0 (Sentinel-1 RTC, third-party processed from GRD), cross-check only"

Scenes come from data/raw/sentinel1/selection.json written by `src.fetch.select_s1 --source pc` (one relative orbit and
pass, the nearest post date, up to four pre dates). Logic follows tools/pc_replica_stack.py, generalised to the
selection's track and dates.

PC RTC is radiometrically terrain-flattened gamma0; the SNAP route is terrain-corrected sigma0. Numbers from this route
are a cross-check of the method, never the SNAP headline.

python -m src.processing.pc_stack --bbox W,S,E,N --epsg 32645 [--selection data/raw/sentinel1/selection.json]"""
import argparse, json, time
from pathlib import Path
import numpy as np, rasterio
from rasterio.warp import reproject, Resampling

LABEL = "PC RTC gamma0 (Sentinel-1 RTC, third-party processed from GRD), cross-check only"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
SPLITS = ["pre", "placebo", "pre3", "pre4"]          # nearest pre-event date first (same order as fetch_sentinel1)
ND = -9999.0


def catalog():
    import pystac_client, planetary_computer
    return pystac_client.Client.open(STAC, modifier=planetary_computer.sign_inplace)


def items_by_id(cat, collection, ids):
    its = list(cat.search(collections=[collection], ids=list(ids)).items())
    missing = set(ids) - {i.id for i in its}
    if missing: raise SystemExit(f"pc_stack: {collection} items not found: {sorted(missing)}")
    return its


def mosaic_db(items, pol, T, crs, shp, tries=3):
    """Average the frames of one pass in linear power on the target grid (frames overlap by a few km)."""
    lin = np.zeros(shp, "float64"); n = np.zeros(shp, "float64")
    for it in items:
        for k in range(tries):
            try:
                with rasterio.open(it.assets[pol.lower()].href) as s:
                    dst = np.full(shp, np.nan, "float32")
                    reproject(rasterio.band(s, 1), dst, dst_transform=T, dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.average)
                break
            except rasterio.errors.RasterioIOError as e:            # signed URLs expire / transient HTTP errors
                if k == tries - 1: raise
                print(f"  retry {it.id} {pol}: {e}"); time.sleep(5 * (k + 1)); it = refresh(it)
        ok = np.isfinite(dst) & (dst > 0); lin[ok] += dst[ok]; n[ok] += 1
    with np.errstate(divide="ignore", invalid="ignore"): db = (10 * np.log10(lin / n)).astype("float32")
    db[n == 0] = np.nan
    return db


def refresh(it):
    import planetary_computer
    return planetary_computer.sign(it)


def write(path, arr, prof):
    with rasterio.open(path, "w", **prof) as d: d.write(np.where(np.isfinite(arr), arr, ND).astype("float32"), 1)


def fetch_annotation(cat, rtc_items, out_dir):
    """Product annotation XML of the matching GRD scenes (heading, pass, incidence angles) for the geometry stage."""
    import urllib.request
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    grd = items_by_id(cat, "sentinel-1-grd", [i.id.removesuffix("_rtc") for i in rtc_items])
    got = []
    for it in grd:
        a = it.assets.get("schema-product-vv")
        if a is None: continue
        f = out_dir / f"s1-{it.id.lower()}-vv-annotation.xml"
        # PC's "schema-product-vv" asset points at annotation/rfi/rfi-iw-vv.xml for recent IPF products (seen 2026-10-12);
        # the product annotation (heading, pass, geolocation grid) is annotation/iw-vv.xml in the same folder.
        base, _, sas = a.href.partition("?")
        cands = [a.href, base.split("/annotation/")[0] + "/annotation/iw-vv.xml" + ("?" + sas if sas else "")]
        for href in dict.fromkeys(cands):
            try:
                with urllib.request.urlopen(href, timeout=120) as r: x = r.read()
            except OSError: continue
            if b"<platformHeading>" in x:
                f.write_bytes(x); got.append(f.name); break
    if not got: raise SystemExit("pc_stack: no GRD product annotation found for the pre scene (needed for the radar geometry)")
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True); ap.add_argument("--epsg", required=True)
    ap.add_argument("--selection", default="data/raw/sentinel1/selection.json")
    ap.add_argument("--dem", default="data/raw/dem/dem_glo30_wgs84.tif"); ap.add_argument("--out", default="data/processed")
    ap.add_argument("--no-10m", action="store_true", help="skip dem_10m.tif (only the AI layer reads 10 m inputs)")
    a = ap.parse_args()
    from src.processing.s1_to_grid import grid_dem
    sel = json.loads(Path(a.selection).read_text())
    if sel.get("source") != "pc": raise SystemExit(f"pc_stack: {a.selection} was not made with --source pc (source={sel.get('source')})")
    bbox = tuple(map(float, a.bbox.split(",")))
    g = grid_dem(bbox, a.epsg, a.dem, resolutions=(30,) if a.no_10m else (10, 30), out=a.out)
    T, W, H = g[30]; crs = f"EPSG:{a.epsg}"; shp = (H, W)
    prof = {"driver": "GTiff", "height": H, "width": W, "count": 1, "dtype": "float32", "crs": crs, "transform": T,
            "nodata": ND, "compress": "deflate", "tiled": True}
    splits = dict(zip(SPLITS, sel["pre"])); splits["post"] = sel["post"]
    cat = catalog(); log = {"label": LABEL, "collection": "sentinel-1-rtc", "rel_orbit": sel["rel_orbit"], "pass": sel["pass"],
                            "grid": f"{a.out}/dem_30m.tif", "epsg": int(a.epsg), "splits": {}}
    for split, day in splits.items():
        ids = [p["id"] for p in sel["products"][day]]
        its = items_by_id(cat, "sentinel-1-rtc", ids)
        for it in its:                                      # the selection is one track; refuse anything else
            pr = it.properties
            if int(pr["sat:relative_orbit"]) != int(sel["rel_orbit"]) or str(pr["sat:orbit_state"]).upper() != sel["pass"].upper():
                raise SystemExit(f"pc_stack: {it.id} is not track {sel['rel_orbit']} {sel['pass']}")
        log["splits"][split] = {"date": day, "items": ids}
        for pol in ("VV", "VH"):
            db = mosaic_db(its, pol, T, crs, shp)
            write(Path(a.out) / f"s1_{split}_{pol}_30m.tif", db, prof)
            print(f"{split} {day} {pol}: median {np.nanmedian(db) if np.isfinite(db).any() else float('nan'):.1f} dB, "
                  f"valid {np.isfinite(db).mean():.0%}  [{LABEL}]", flush=True)
        if split == "pre":
            log["annotation"] = fetch_annotation(cat, its, "data/raw/sentinel1/pc_annotation/pre")
    Path("data/raw/sentinel1").mkdir(parents=True, exist_ok=True)
    Path("data/raw/sentinel1/pc_source.json").write_text(json.dumps(log, indent=2))
    print("wrote", ", ".join(f"s1_{s}_{{VV,VH}}_30m.tif" for s in splits), f"({LABEL})")


if __name__ == "__main__":
    main()

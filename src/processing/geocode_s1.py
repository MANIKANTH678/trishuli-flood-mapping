#!/usr/bin/env python3
"""Geocode Sentinel-1 GRD measurement TIFFs using GCPs from annotation XML.

Reads each .SAFE under data/raw/s1/{pre,post}/, extracts geolocation GCPs
from annotation/s1*-{pol}-*.xml, and produces gdalwarp'd rasters in
data/raw/s1/{split}/geocoded/.
"""
import subprocess, sys
from pathlib import Path
import xml.etree.ElementTree as ET

S1_ROOT = Path("data/raw/s1")
SPLITS  = ["pre", "post"]
POLS    = ["vv", "vh"]
TARGET_EPSG = "32645"
RES         = "30"


def find_annotation(safe_dir: Path, pol: str):
    for f in sorted(safe_dir.glob(f"annotation/s1*-{pol}-*.xml")):
        if "calibration" not in str(f):
            return f
    return None


def find_measurement(safe_dir: Path, pol: str):
    for ext in ("tiff", "tif"):
        hits = list(safe_dir.glob(f"measurement/s1*-{pol}-*.{ext}"))
        if hits:
            return hits[0]
    return None


def read_gcps(ann_xml: Path):
    root = ET.parse(ann_xml).getroot()
    gcps = []
    for pt in root.iter():
        if not pt.tag.endswith("geolocationGridPoint"):
            continue
        line = pixel = lat = lon = None
        for c in pt:
            tag = c.tag.split("}")[-1]
            if   tag == "line":      line  = int(c.text)
            elif tag == "pixel":     pixel = int(c.text)
            elif tag == "latitude":  lat   = float(c.text)
            elif tag == "longitude": lon   = float(c.text)
        if None not in (line, pixel, lat, lon):
            gcps.append((pixel, line, lon, lat))
    return gcps


def make_vrt(measurement_tif: Path, gcps, vrt: Path):
    cmd = ["gdal_translate", "-of", "VRT", "-a_srs", "EPSG:4326"]
    for pixel, line, lon, lat in gcps:
        cmd += ["-gcp", str(pixel), str(line), str(lon), str(lat)]
    cmd += [str(measurement_tif), str(vrt)]
    subprocess.run(cmd, check=True, capture_output=True)


def warp(vrt: Path, out_tif: Path):
    cmd = [
        "gdalwarp",
        "-t_srs", f"EPSG:{TARGET_EPSG}",
        "-tr", RES, RES,
        "-r", "bilinear",
        "-order", "1",
        "-co", "COMPRESS=DEFLATE",
        "-co", "TILED=YES",
        "-overwrite",
        str(vrt), str(out_tif),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def process_safe(safe_dir: Path, split: str):
    out_dir = S1_ROOT / split / "geocoded"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = safe_dir.name[:45]

    for pol in POLS:
        ann  = find_annotation(safe_dir, pol)
        meas = find_measurement(safe_dir, pol)
        if not ann or not meas:
            print(f"  [{split}] {tag}  {pol}: missing ann/meas — skip")
            continue

        out_tif = out_dir / f"{safe_dir.name}__{pol}.tif"
        if out_tif.exists():
            print(f"  [{split}] {tag}  {pol}: already exists")
            continue

        gcps = read_gcps(ann)
        print(f"  [{split}] {tag}  {pol}: {len(gcps)} GCPs")

        vrt = out_dir / f"{safe_dir.name}__{pol}.vrt"
        make_vrt(meas, gcps, vrt)
        warp(vrt, out_tif)
        vrt.unlink(missing_ok=True)
        print(f"         → {out_tif.name}")


def main():
    for split in SPLITS:
        split_dir = S1_ROOT / split
        if not split_dir.is_dir():
            continue
        safes = sorted(p for p in split_dir.iterdir() if p.is_dir() and p.suffix == ".SAFE")
        print(f"=== {split}: {len(safes)} SAFE folder(s) ===")
        for safe in safes:
            process_safe(safe, split)


if __name__ == "__main__":
    main()

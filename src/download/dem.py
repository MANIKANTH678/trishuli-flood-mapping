"""Download Copernicus GLO-30 DEM tiles for the study area."""
import math
import os
import sys

import boto3
import tifffile
import numpy as np
from botocore import UNSIGNED
from botocore.config import Config

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import BBOX, DEM_DIR


def download_tile(lon_sw, lat_sw, out_dir=DEM_DIR):
    lat_str = f"N{lat_sw:02d}" if lat_sw >= 0 else f"S{abs(lat_sw):02d}"
    lon_str = f"E{lon_sw:03d}" if lon_sw >= 0 else f"W{abs(lon_sw):03d}"
    name = f"Copernicus_DSM_COG_10_{lat_str}_00_{lon_str}_00_DEM"
    key = f"{name}/{name}.tif"
    out = os.path.join(out_dir, f"{name}.tif")
    os.makedirs(out_dir, exist_ok=True)
    if os.path.exists(out):
        print(f"✓ Already have {name}")
        return out
    print(f"⬇ Downloading {name} ...")
    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    s3.download_file("copernicus-dem-30m", key, out)
    print(f"  saved {os.path.getsize(out) / 1e6:.1f} MB")
    return out


def download_corridor():
    west, south, east, north = BBOX
    for lon in range(math.floor(west), math.floor(east) + 1):
        for lat in range(math.floor(south), math.floor(north) + 1):
            download_tile(lon, lat)


if __name__ == "__main__":
    download_corridor()
    print("\n✅ DEM download complete.")

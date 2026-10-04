import argparse, math, urllib.request, urllib.error
from pathlib import Path
import rasterio
from rasterio.merge import merge

BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
OUT = Path("data/raw/dem"); TILES = OUT / "tiles"

def tile_name(lat, lon):
    return (f"Copernicus_DSM_COG_10_{'N' if lat >= 0 else 'S'}{abs(lat):02d}_00_"
            f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}_00_DEM")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--bbox", required=True)
    w, s, e, n = map(float, ap.parse_args().bbox.split(","))
    TILES.mkdir(parents=True, exist_ok=True)
    got = []
    for lat in range(math.floor(s - 0.1), math.floor(n + 0.1) + 1):
        for lon in range(math.floor(w - 0.1), math.floor(e + 0.1) + 1):
            nm = tile_name(lat, lon); f = TILES / f"{nm}.tif"
            if not f.exists():
                try: urllib.request.urlretrieve(f"{BASE}/{nm}/{nm}.tif", f)
                except urllib.error.HTTPError as ex:
                    print(f"skip {nm}: HTTP {ex.code}"); continue
            got.append(f)
    if not got: raise SystemExit("no DEM tiles available")
    srcs = [rasterio.open(f) for f in got]
    arr, tr = merge(srcs, bounds=(w - .1, s - .1, e + .1, n + .1), nodata=-9999.0)
    meta = srcs[0].meta | {"height": arr.shape[1], "width": arr.shape[2], "transform": tr,
                           "nodata": -9999.0, "dtype": "float32", "compress": "deflate"}
    with rasterio.open(OUT / "dem_glo30_wgs84.tif", "w", **meta) as dst:
        dst.write(arr.astype("float32"))
    print("wrote", OUT / "dem_glo30_wgs84.tif")

if __name__ == "__main__":
    main()
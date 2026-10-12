"""Step 8C: cut 256x256 (10 m) Himalayan evaluation chips at the PRE-REGISTERED points (tools/select_himalaya_points.py).
Writes, in Sen1Floods11 layout so src.modeling.evaluate --extra works unchanged:
  data/external/himalaya_chips/S1/<name>_S1.tif      post-event S1 VV,VH dB (the model input)
  data/external/himalaya_chips/S2/<name>_S2.tif      Sentinel-2 L2A 27 Aug 2026 RGB+NIR+SWIR1 (labelling only; Planetary Computer, no login)
  data/external/himalaya_chips/Label_A/, Label_B/   empty labels (-1 = not labelled) for tools/label_chips.py
  data/external/himalaya_chips/chips.csv
python tools/make_himalaya_chips.py [--points data/external/himalaya_chips/points.csv] [--s2-date 2026-08-27]

Pre-event option (Step 10; used when fewer than 8 post-event chips pass tools/chip_clear.py):
python tools/make_himalaya_chips.py --split pre        # s1_pre_*_10m.tif (2026-08-16) + the 12 Aug 2026 S2, same points
  -> data/external/himalaya_chips_pre/, chip names tagged <name>_pre, chips_meta.csv says split=pre. These chips test the
     model on river water vs hillside shadow WITHOUT an event; report them separately from the post-event chips.
Labelling is done by people (tools/label_chips.py) under docs/chip_protocol.md; this script never labels anything."""
import argparse
from pathlib import Path
import numpy as np, rasterio
from pyproj import Transformer
from rasterio.windows import Window
from rasterio.warp import reproject, Resampling

def s2_items(bbox, date):
    import pystac_client, planetary_computer as pc
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=pc.sign_inplace)
    return list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{date}/{date}").items())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--points", default="data/external/himalaya_chips/points.csv"); ap.add_argument("--s2-date")
    ap.add_argument("--split", choices=["post", "pre"], default="post", help="S1 scene to cut: post (event) or pre (no-event control)")
    ap.add_argument("--out"); a = ap.parse_args()
    a.s2_date = a.s2_date or ("2026-08-27" if a.split == "post" else "2026-08-12")
    out = Path(a.out or ("data/external/himalaya_chips" if a.split == "post" else "data/external/himalaya_chips_pre"))
    tag = "" if a.split == "post" else "_pre"; meta = ["name,split,s1_file,s2_date,purpose"]
    for sub in ("S1", "S2", "Label_A", "Label_B"): (out / sub).mkdir(parents=True, exist_ok=True)
    pts = [l.split(",") for l in Path(a.points).read_text().splitlines()[1:] if l.strip()]
    rows = []
    with rasterio.open(f"data/processed/s1_{a.split}_VV_10m.tif") as v, rasterio.open(f"data/processed/s1_{a.split}_VH_10m.tif") as h:
        tf, inv = Transformer.from_crs(4326, v.crs, always_xy=True), Transformer.from_crs(v.crs, 4326, always_xy=True)
        for name0, lon, lat, *_ in pts:
            name = name0 + tag
            r, c = v.index(*tf.transform(float(lon), float(lat))); win = Window(c - 128, r - 128, 256, 256); T = v.window_transform(win)
            prof = {"driver": "GTiff", "height": 256, "width": 256, "crs": v.crs, "transform": T, "compress": "deflate"}
            arr = np.stack([x.read(1, window=win, boundless=True, masked=True).astype("float32").filled(np.nan) for x in (v, h)])
            with rasterio.open(out / "S1" / f"{name}_S1.tif", "w", count=2, dtype="float32", **prof) as d: d.write(arr)
            for ann in ("A", "B"):
                p = out / f"Label_{ann}" / f"{name}_Label.tif"
                if not p.exists():
                    with rasterio.open(p, "w", count=1, dtype="int16", nodata=None, **prof) as d: d.write(np.full((1, 256, 256), -1, "int16"))
            x0, y0 = T * (0, 0); x1, y1 = T * (256, 256); lo0, la0 = inv.transform(x0, y1); lo1, la1 = inv.transform(x1, y0)
            s2 = np.full((5, 256, 256), np.nan, "float32")
            try:
                for it in s2_items([lo0, la0, lo1, la1], a.s2_date):
                    for k, b in enumerate(("B04", "B03", "B02", "B08", "B11")):
                        tmp = np.full((256, 256), np.nan, "float32")
                        with rasterio.open(it.assets[b].href) as src:
                            reproject(rasterio.band(src, 1), tmp, dst_transform=T, dst_crs=v.crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
                        tmp[tmp == 0] = np.nan; s2[k] = np.where(np.isnan(s2[k]), tmp, s2[k])
            except Exception as ex:
                print(f"{name}: S2 fetch failed ({ex}); label from the S2 indices in data/interim/s2 instead")
            with rasterio.open(out / "S2" / f"{name}_S2.tif", "w", count=5, dtype="float32", **prof) as d: d.write(s2)
            rows.append(f"{name}_S1.tif,{name}_Label.tif"); print("chip", name)
            meta.append(f"{name},{a.split},s1_{a.split}_VV/VH_10m.tif,{a.s2_date},{'event test' if a.split == 'post' else 'no-event control: river water vs hillside shadow'}")
    (out / "chips.csv").write_text("\n".join(rows) + "\n")
    (out / "chips_meta.csv").write_text("\n".join(meta) + "\n")
    print(f"{len(rows)} chips. Next: python tools/label_chips.py --annotator A  (and B on a subset)")

if __name__ == "__main__":
    main()

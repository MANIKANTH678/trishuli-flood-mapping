import argparse, json, numpy as np, rasterio
from scipy.ndimage import map_coordinates

ap = argparse.ArgumentParser()
ap.add_argument("--dem", default="data/processed/dem_30m.tif")
ap.add_argument("--geom", default="outputs/diagnostics/look_geometry.json")
ap.add_argument("--out", default="data/processed/radar_mask_30m.tif")
ap.add_argument("--lia-min", type=float, default=20.0); ap.add_argument("--lia-max", type=float, default=70.0)
a = ap.parse_args()

g = json.load(open(a.geom))
th, ph = np.radians(g["incidence_deg"]), np.radians(g["toward_sensor_azimuth_deg"])
with rasterio.open(a.dem) as src:
    dem = src.read(1, masked=True).astype("float32").filled(np.nan); prof, res = src.profile, src.res[0]

d_row, d_col = np.gradient(dem, res)                  # rows increase southward
dzdE, dzdN = d_col, -d_row
p = dzdE * np.sin(ph) + dzdN * np.cos(ph)             # >0: terrain rises toward the sensor (back slope)
lia = np.degrees(np.arccos(np.clip((np.cos(th) - np.sin(th) * p) / np.sqrt(1 + dzdE**2 + dzdN**2), -1, 1)))
layover = p < -np.tan(th)                              # sensor-facing slope steeper than incidence
shadow = p > 1 / np.tan(th)                            # back slope steeper than 90 - incidence

H, W = dem.shape
rr, cc = np.mgrid[0:H, 0:W].astype("float32")
cast = np.zeros((H, W), bool)                          # cast shadow: a ridge between pixel and sensor
for d in np.arange(res, 5000, res):
    z = map_coordinates(dem, [rr - np.cos(ph) * d / res, cc + np.sin(ph) * d / res],
                        order=1, mode="nearest")
    cast |= (z - dem) > d / np.tan(th)

code = np.zeros((H, W), np.uint8)
code[(lia < a.lia_min) | (lia > a.lia_max)] = 4
code[cast] = 3; code[shadow] = 2; code[layover] = 1    # later lines win
code[~np.isfinite(dem)] = 255
prof.update(dtype="uint8", nodata=255, count=1, compress="deflate")
with rasterio.open(a.out, "w", **prof) as d: d.write(code, 1)
v = code[code != 255]
print({n: f"{(v == c).mean():.1%}" for c, n in
       [(0, "ok"), (1, "layover"), (2, "shadow"), (3, "cast_shadow"), (4, "poor_LIA")]})
"""Static map for the one-page situation report: detected classes plus exposed roads / bridges (empty layers are fine)."""
from pathlib import Path
import geopandas as gpd, rasterio, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
with rasterio.open("data/processed/fused_class_30m.tif") as s:
    cls, ext, crs = s.read(1), (s.bounds.left, s.bounds.right, s.bounds.bottom, s.bounds.top), s.crs
fig, ax = plt.subplots(figsize=(7, 4.6), dpi=150)
ax.set_facecolor("#f4f4f4")
cls = cls.copy(); cls[cls > 3] = 0
rgba = ListedColormap([(0, 0, 0, 0), "#1f77b4", "#444444", "#ff7f0e"])
ax.imshow(cls, cmap=rgba, vmin=0, vmax=3, extent=ext, interpolation="nearest")
for f, kw in (("outputs/affected_roads.geojson", {"color": "#d62728", "linewidth": 0.8}),
              ("outputs/affected_bridges.geojson", {"color": "#9467bd", "markersize": 10})):
    if Path(f).exists():
        g = gpd.read_file(f)
        if len(g): g.to_crs(crs).plot(ax=ax, **kw)
ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
ax.legend(handles=[Patch(color="#1f77b4", label="flood-like (water-like backscatter change)"), Patch(color="#444444", label="dark change"),
                   Patch(color="#ff7f0e", label="bright change"), Patch(color="#d62728", label="roads in mask"),
                   Patch(color="#9467bd", label="bridges in mask (exposed, not failed)")], loc="lower left", fontsize=6)
ax.set_title("Detected mask (unvalidated) and exposed roads/bridges", fontsize=8); ax.set_axis_off()
Path("outputs/reports").mkdir(parents=True, exist_ok=True)
fig.savefig("outputs/reports/situation_map.png", bbox_inches="tight"); print("ok")

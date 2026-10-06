import numpy as np, shapely, geopandas as gpd
from scipy.spatial import cKDTree
from src.analysis.impact_lib import *
from src.processing.cutoff_v2 import load_network, snap, SNAP_M
M = load_classes(); N = load_network(M["crs"]); nodes = list(N["G"].nodes); kd = cKDTree(np.array(nodes))
idx = shapely.STRtree(N["lines"]).query(union_mask(M), predicate="intersects")
print("segments in mask:", len(idx), "| bridge:", int(N["bridge"][idx].sum()), "| tunnel:", int(N["tunnel"][idx].sum()))
h = gpd.read_file(OSM / "hospitals.geojson").to_crs(M["crs"])
xy = shapely.get_coordinates(shapely.centroid(h.geometry.to_numpy()))
i, _ = snap(xy, kd, len(nodes), SNAP_M); d, _ = kd.query(xy)
print("hospitals:", len(h), "| snapped:", int((i >= 0).sum()), "| unique nodes:", len({int(x) for x in i if x >= 0}))
print("nearest-node distance (m), unsnapped:", np.round(d[i < 0]).tolist())
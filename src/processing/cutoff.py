"""P1: find settlements cut off from the main road network after flooding."""
import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import networkx as nx
import rasterio
from rasterio.features import shapes as rio_shapes
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
FLOOD = ROOT / "data/processed/flood_mask.tif"
RDS   = ROOT / "data/raw/osm/roads.geojson"
SET   = ROOT / "data/raw/osm/settlements.geojson"
OUT   = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

print("Vectorizing flood mask ...")
with rasterio.open(FLOOD) as src:
    arr = src.read(1)
    mask_crs = src.crs
    transform = src.transform

flood_geoms = [
    shape(g) for g, v in rio_shapes(arr.astype("uint8"), mask=arr == 1, transform=transform)
]
flood_poly = unary_union(flood_geoms)
print(f"  polygon area: {flood_poly.area:,.0f}")

print("Loading roads ...")
r = gpd.read_file(RDS).to_crs(mask_crs)
print(f"  {len(r)} segments")
mid = r.geometry.interpolate(0.5, normalized=True)
r_alive = r[~mid.within(flood_poly)].copy()
print(f"  {len(r_alive)} remain after removing flooded segments")

print("Building graph ...")
G = nx.Graph()
for geom in r_alive.geometry:
    if geom is None or geom.is_empty:
        continue
    if geom.geom_type == "LineString":
        parts = [geom]
    elif geom.geom_type == "MultiLineString":
        parts = list(geom.geoms)
    else:
        continue
    for part in parts:
        coords = [(round(x, 6), round(y, 6)) for x, y in part.coords]
        for a, b_ in zip(coords[:-1], coords[1:]):
            G.add_edge(a, b_)
print(f"  graph: {G.number_of_nodes():,} nodes | {G.number_of_edges():,} edges")

if G.number_of_nodes() > 0:
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    main = comps[0]
    print(f"  {len(comps)} components; largest has {len(main):,} nodes")
    nodes_arr = np.array(list(G.nodes))
else:
    main = set()
    nodes_arr = np.zeros((0, 2))

print("Loading settlements ...")
s = gpd.read_file(SET).to_crs(mask_crs)
print(f"  {len(s)} settlements")

if len(nodes_arr):
    from scipy.spatial import cKDTree
    tree = cKDTree(nodes_arr)
else:
    tree = None

results = []
for _, row in s.iterrows():
    geom = row.geometry
    if geom is None or geom.is_empty:
        continue
    x, y = geom.x, geom.y
    if tree is None:
        cut = True
    else:
        _, idx = tree.query([x, y])
        cut = tuple(nodes_arr[idx]) not in main
    results.append({
        "name": row.get("name") or row.get("district") or f"settlement_{row.get('id')}",
        "lat": float(y),
        "lon": float(x),
        "district": row.get("district"),
        "cut_off": bool(cut),
    })

n_cut = sum(r["cut_off"] for r in results)
out = OUT / "cutoff_settlements.json"
with open(out, "w") as f:
    json.dump(results, f, indent=2)
print(f"✅ {out} ({len(results)} settlements, {n_cut} cut off)")

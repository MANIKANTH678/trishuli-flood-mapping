#!/usr/bin/env python3
"""cutoff_v2.py — hospital reachability for settlements, pre vs post flood.

Improvements over cutoff.py:
  * Destination = nearest reachable hospital (not just "in main network")
  * Shortest-path road distance (NetworkX multi-source Dijkstra)
  * Pre-flood baseline vs post-flood delta → detour_factor
  * cut_off flag = no path OR detour_factor > DETOUR_MAX
  * Output includes which hospital serves each settlement + its distance

Algorithm:
  1. Load OSM roads, project to flood-mask CRS (EPSG:32645).
  2. Build weighted graph (edge weight = Euclidean length in meters).
  3. Snap settlements and hospitals to nearest graph node (≤ SNAP_RADIUS_M).
  4. Multi-source Dijkstra from all hospital-snapped nodes → dist to nearest
     hospital for every node in the graph. Pre-flood.
  5. Remove roads whose midpoint is inside flood_mask, rebuild graph, run
     the same Dijkstra → post-flood distances.
  6. For each settlement: read pre/post distances, compute detour_factor,
     set cut_off = (post is inf) OR (detour_factor > DETOUR_MAX).

Output: outputs/cutoff_settlements.json
"""
from __future__ import annotations

import json
import math
import sys
import os
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import rasterio
from scipy.spatial import cKDTree
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FLOOD = ROOT / "data/processed/flood_mask.tif"
RDS   = ROOT / "data/raw/osm/roads.geojson"
HOS   = ROOT / "data/raw/osm/hospitals.geojson"
SET   = ROOT / "data/raw/osm/settlements.geojson"
OUT   = ROOT / "outputs/cutoff_settlements.json"

SNAP_RADIUS_M = 1000.0     # settlement/hospital must be within 1 km of a road node
DETOUR_MAX    = 3.0        # post/pre path ratio above which we flag as cut off


# ---------- helpers ----------

def load_flood_polygon():
    with rasterio.open(FLOOD) as src:
        arr = src.read(1)
        crs = src.crs
        tr = src.transform
    from rasterio.features import shapes as rio_shapes
    from shapely.geometry import shape
    from shapely.ops import unary_union
    geoms = [shape(g) for g, v in rio_shapes(arr.astype("uint8"),
                                             mask=(arr == 1),
                                             transform=tr)]
    return unary_union(geoms) if geoms else None, crs


def build_graph(roads: gpd.GeoDataFrame) -> nx.Graph:
    G = nx.Graph()
    for geom in roads.geometry:
        if geom is None or geom.is_empty:
            continue
        parts = [geom] if geom.geom_type == "LineString" else \
                list(geom.geoms) if geom.geom_type == "MultiLineString" else []
        for part in parts:
            coords = [(round(x, 4), round(y, 4)) for x, y in part.coords]
            for a, b in zip(coords[:-1], coords[1:]):
                w = math.hypot(a[0] - b[0], a[1] - b[1])
                if w <= 0:
                    continue
                # keep shorter edge if the pair already exists
                if G.has_edge(a, b):
                    if w < G[a][b]["weight"]:
                        G[a][b]["weight"] = w
                else:
                    G.add_edge(a, b, weight=w)
    return G


def node_kdtree(G: nx.Graph):
    nodes = np.array(list(G.nodes), dtype=np.float64)
    return nodes, cKDTree(nodes) if len(nodes) else None


def snap(points: gpd.GeoSeries, tree: cKDTree, nodes: np.ndarray,
         radius: float):
    """Return (node_idx per point, node_xy per point, distance per point).
    -1 means no node within radius.
    """
    idxs, dists = tree.query(list(zip(points.x.values, points.y.values)),
                             k=1, distance_upper_bound=radius)
    n = len(idxs)
    ok = np.isfinite(dists) & (idxs < len(nodes))
    idxs = np.where(ok, idxs, -1).astype(np.int64)
    return idxs, dists


def nearest_hospital_distances(G: nx.Graph, hospital_nodes: list[tuple]):
    """Multi-source Dijkstra → {node: distance_m_to_nearest_hospital}."""
    if not hospital_nodes:
        return {}
    return nx.multi_source_dijkstra_path_length(G, sources=hospital_nodes,
                                                weight="weight")


# ---------- main ----------

def main():
    flood_poly, mask_crs = load_flood_polygon()
    print(f"flood polygon loaded  (crs={mask_crs})")

    print("loading roads / hospitals / settlements ...")
    roads = gpd.read_file(RDS).to_crs(mask_crs)
    hos   = gpd.read_file(HOS).to_crs(mask_crs)
    setl  = gpd.read_file(SET).to_crs(mask_crs)
    print(f"  roads: {len(roads):,}  hospitals: {len(hos):,}  settlements: {len(setl):,}")

    # ensure point geometries — some OSM features are polygons (hospital buildings)
    def to_points(gdf):
        non_pt = ~gdf.geometry.geom_type.isin(["Point", "MultiPoint"])
        if non_pt.any():
            gdf = gdf.copy()
            gdf.loc[non_pt, "geometry"] = gdf.loc[non_pt, "geometry"].centroid
        return gdf

    hos  = to_points(hos)
    setl = to_points(setl)
    print(f"  after point normalization: "
          f"hospitals {hos.geometry.geom_type.value_counts().to_dict()}  "
          f"settlements {setl.geometry.geom_type.value_counts().to_dict()}")

    # ---- PRE-FLOOD GRAPH ----
    print("building pre-flood graph ...")
    # Restrict to the study region to keep graph tractable
    # (0.1 degree buffer around settlements)
    from shapely.geometry import box
    sb = setl.total_bounds  # minx, miny, maxx, maxy
    buffer_m = 5000
    study_bbox = box(sb[0] - buffer_m, sb[1] - buffer_m,
                     sb[2] + buffer_m, sb[3] + buffer_m)
    n_before = len(roads)
    roads = roads[roads.geometry.intersects(study_bbox)].copy()
    print(f"  roads filtered to study region: {len(roads):,}/{n_before:,}")

    G_pre = build_graph(roads)
    print(f"  nodes={G_pre.number_of_nodes():,}  edges={G_pre.number_of_edges():,}")
    if G_pre.number_of_nodes() == 0:
        sys.exit("graph is empty — check roads CRS / geometry")

    nodes_pre, tree_pre = node_kdtree(G_pre)

    # snap hospitals & settlements to pre-flood graph
    h_idx_pre, h_d = snap(hos.geometry, tree_pre, nodes_pre, SNAP_RADIUS_M)
    s_idx_pre, s_d = snap(setl.geometry, tree_pre, nodes_pre, SNAP_RADIUS_M)
    hos_in = h_idx_pre >= 0
    set_in = s_idx_pre >= 0
    print(f"  hospitals snapped:   {int(hos_in.sum())}/{len(hos)}")
    print(f"  settlements snapped: {int(set_in.sum())}/{len(setl)}")

    hospital_nodes = [tuple(nodes_pre[i]) for i in h_idx_pre[hos_in]]
    print(f"running pre-flood Dijkstra from {len(hospital_nodes)} hospitals ...")
    dist_pre = nearest_hospital_distances(G_pre, hospital_nodes)

    # ---- POST-FLOOD GRAPH ----
    print("removing roads inside flood polygon ...")
    mids = roads.geometry.interpolate(0.5, normalized=True)
    roads_post = roads[~mids.within(flood_poly)].copy() if flood_poly else roads
    print(f"  roads remaining: {len(roads_post):,}/{len(roads):,}")

    G_post = build_graph(roads_post)
    print(f"  post graph nodes={G_post.number_of_nodes():,}  "
          f"edges={G_post.number_of_edges():,}")
    nodes_post, tree_post = node_kdtree(G_post)

    # snap hospitals to post graph (settlements too, for distance lookup)
    h_idx_post, _ = snap(hos.geometry, tree_post, nodes_post, SNAP_RADIUS_M)
    s_idx_post, _ = snap(setl.geometry, tree_post, nodes_post, SNAP_RADIUS_M)
    hospital_nodes_post = [tuple(nodes_post[i]) for i in h_idx_post[h_idx_post >= 0]]
    print(f"running post-flood Dijkstra from {len(hospital_nodes_post)} hospitals ...")
    dist_post = nearest_hospital_distances(G_post, hospital_nodes_post)

    # ---- per-settlement results ----
    print("computing per-settlement reachability ...")
    results = []
    n_cut = n_no_path = n_detour = 0
    import pandas as pd
    for i, row in setl.iterrows():
        nm = row.get("name")
        di = row.get("district")
        if not pd.notna(nm):
            nm = di if pd.notna(di) else None
        if not pd.notna(nm):
            nm = f"settlement_{row.get('id', i)}"
        name = str(nm)
        lon, lat = row.geometry.x, row.geometry.y
        district = str(di) if pd.notna(di) else None

        # pre-flood
        pre_m = None
        if s_idx_pre[i] >= 0:
            node_pre = tuple(nodes_pre[s_idx_pre[i]])
            pre_m = dist_pre.get(node_pre)
        pre_km = pre_m / 1000.0 if pre_m is not None else None

        # post-flood
        post_m = None
        if s_idx_post[i] >= 0:
            node_post = tuple(nodes_post[s_idx_post[i]])
            post_m = dist_post.get(node_post)
        post_km = post_m / 1000.0 if post_m is not None else None

        # verdict
        reason = None
        if pre_km is None:
            cut = False; reason = "unsnapped_pre"
        elif post_km is None:
            cut = True; reason = "no_post_flood_path"
            n_no_path += 1
        else:
            df = post_km / max(pre_km, 0.1)
            if df > DETOUR_MAX:
                cut = True; reason = f"detour_{df:.2f}x"
                n_detour += 1
            else:
                cut = False

        if cut:
            n_cut += 1

        results.append({
            "name": str(name),
            "lat": float(lat),
            "lon": float(lon),
            "district": str(district) if district is not None else None,
            "pre_flood_hospital_km": round(pre_km, 3) if pre_km is not None else None,
            "post_flood_hospital_km": round(post_km, 3) if post_km is not None else None,
            "detour_factor": round(post_km / max(pre_km, 0.1), 3)
                             if (pre_km and post_km) else None,
            "cut_off": bool(cut),
            "cut_off_reason": reason,
        })

    # ---- output ----
    result = {
        "metadata": {
            "source_flood_mask": str(FLOOD.relative_to(ROOT)),
            "snap_radius_m": SNAP_RADIUS_M,
            "detour_max": DETOUR_MAX,
            "note": ("Pre-flood graph uses all OSM roads; post-flood graph removes "
                     "roads whose midpoint lies inside flood_mask.tif. Because the "
                     "SAR flood mask was shown not to contain the GLOF signal "
                     "(see outputs/diagnostics/aoi_backscatter_diagnostics.json), "
                     "the 'cut_off' flags here reflect the preliminary, under rebuild, not the "
                     "real event. The machinery is correct; the input is not."),
        },
        "summary": {
            "total_settlements": len(results),
            "hospitals_total": len(hos),
            "hospitals_snapped_pre": int(hos_in.sum()),
            "hospitals_snapped_post": int((h_idx_post >= 0).sum()),
            "reachable_pre": sum(1 for r in results
                                 if r["pre_flood_hospital_km"] is not None),
            "reachable_post": sum(1 for r in results
                                  if r["post_flood_hospital_km"] is not None),
            "cut_off": n_cut,
            "cut_off_no_path": n_no_path,
            "cut_off_detour_only": n_detour,
        },
        "settlements": results,
    }
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\n✅ {OUT}")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()

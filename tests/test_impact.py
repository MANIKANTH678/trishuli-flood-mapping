import networkx as nx, numpy as np, shapely, geopandas as gpd
from affine import Affine
from src.processing.cutoff_v2 import classify, reach
from src.processing.damage_v2 import buildings

def test_cut_degraded_reachable_and_no_pre_path():
    G = nx.Graph()
    for u, v, w, e in [((0, 0), (1, 0), 1000, 0), ((1, 0), (2, 0), 1000, 1), ((1, 0), (1, 5), 10000, 2),
                       ((1, 5), (2, 0), 10000, 3), ((1, 0), (9, 0), 1000, 4)]:
        G.add_edge(u, v, w=w, e=e)
    _, pre = reach(G, [(0, 0)])
    G.remove_edges_from([((1, 0), (2, 0)), ((1, 0), (9, 0))])
    _, post = reach(G, [(0, 0)])
    assert classify(pre[(2, 0)], post.get((2, 0)))[0] == "degraded"
    assert classify(pre[(9, 0)], post.get((9, 0)))[0] == "cut_off"
    assert classify(pre[(1, 0)], post.get((1, 0)))[0] == "reachable"
    assert classify(None, None)[0] == "no_pre_flood_path"
    assert not G.has_node(("SRC",))                         # super-source must not leak into the graph

def test_building_tiers_and_unknown_domains():
    cls = np.zeros((100, 100), np.uint8); cls[10:12, 10:12] = 1; cls[49, 50] = 253
    T = Affine(30, 0, 0, 0, -30, 3000)
    M = {"cls": cls, "T": T, "crs": None, "flood": cls == 1, "debris": np.zeros(cls.shape, bool)}
    g = np.array([shapely.box(310, 2650, 330, 2670), shapely.box(375, 2650, 390, 2670),
                  shapely.box(600, 2000, 620, 2020), shapely.box(1500, 1500, 1520, 1520)], dtype=object)
    s, aff = buildings(gpd.GeoDataFrame(geometry=list(g)), g, M)
    assert (s["overlap"], s["within_30m"], s["not_assessed"], s["assessed"]) == (1, 2, 1, 3)
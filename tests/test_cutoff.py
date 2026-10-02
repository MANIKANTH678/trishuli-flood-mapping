import geopandas as gpd, networkx as nx
from shapely.geometry import LineString
def test_build_graph_creates_edges():
    from src.processing.cutoff_v2 import build_graph
    g = gpd.GeoDataFrame({"geometry":[LineString([(0,0),(100,0),(200,0)])]}, crs="EPSG:32645")
    G = build_graph(g)
    assert G.number_of_nodes()==3 and G.number_of_edges()==2
    assert G[(0.0,0.0)][(100.0,0.0)]["weight"]==100.0
def test_kdtree():
    from src.processing.cutoff_v2 import build_graph, node_kdtree
    g = gpd.GeoDataFrame({"geometry":[LineString([(0,0),(10,0),(20,0)])]}, crs="EPSG:32645")
    nodes, tree = node_kdtree(build_graph(g))
    assert nodes.shape==(3,2) and tree is not None
def test_empty_hospital_sources():
    from src.processing.cutoff_v2 import nearest_hospital_distances
    G = nx.Graph(); G.add_edge((0,0),(1,0), weight=1.0)
    assert nearest_hospital_distances(G, []) == {}

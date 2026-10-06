   import geopandas as gpd, sqlite3
   a = "data/external/_superseded_EMSR927_AOI05_v2/EMSR927_AOI05_GRA_PRODUCT_v2.gpkg"
   b = "data/external/EMSR927/AOI05/EMSR927_AOI05_GRA_PRODUCT_v3.gpkg"
   for l in ("observedEventA_v2", "notAnalysedA_v2", "builtUpP_v2"):
       A, B = gpd.read_file(a, layer=l), gpd.read_file(b, layer=l)
       print(l, len(A), len(B), "same geometry:", A.geometry.unary_union.equals(B.geometry.unary_union))
   for f in (a, b):
       print(sqlite3.connect("file:" + f + "?mode=ro", uri=True).execute("select * from source_v2").fetchall())
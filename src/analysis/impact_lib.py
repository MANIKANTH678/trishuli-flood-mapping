"""impact_lib.py - class raster -> masks / geometries, OSM text helper, raster sampling."""
import ast
from pathlib import Path
import numpy as np, pandas as pd, rasterio, shapely
from pyproj import Transformer
from rasterio.features import shapes
from scipy import ndimage as ndi
from shapely.geometry import Polygon, shape

OSM = Path("data/raw/osm")
ASSESSED = (0, 1, 2, 3)            # classes the detector actually looked at (253/254/255 = unknown)

def _non_motorable(src="src/download/fetch_osm.py"):
    """Read NON_MOTORABLE from fetch_osm.py without importing it (the import exits unless OHSOME_API_KEY is set)."""
    try:
        for n in ast.parse(Path(src).read_text(encoding="utf-8")).body:
            if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == "NON_MOTORABLE" for t in n.targets):
                return frozenset(ast.literal_eval(n.value))
    except Exception:
        pass
    return frozenset({"footway", "path", "pedestrian", "steps", "cycleway", "bridleway", "corridor", "proposed", "construction"})

NON_MOTORABLE = _non_motorable()

def txt(df, name):
    """Lower-cased text column; '' where missing, 'no' or 'none'."""
    if name not in df: return pd.Series("", index=df.index)
    return df[name].fillna("").astype(str).str.lower().replace({"none": "", "nan": "", "no": ""})

def load_classes(path="data/processed/fused_class_30m.tif", morph=0):
    with rasterio.open(path) as s:
        cls, T, crs, res = s.read(1), s.transform, s.crs, s.res[0]
    flood, debris = cls == 1, np.isin(cls, (2, 3))
    if morph:                                       # +-1 px: grow/shrink, never into unassessed pixels
        grow = ndi.binary_dilation if morph > 0 else ndi.binary_erosion
        st, ok = ndi.generate_binary_structure(2, 1), np.isin(cls, ASSESSED)
        flood, debris = (grow(m, st, abs(morph)) & ok for m in (flood, debris))
    return {"cls": cls, "T": T, "crs": crs, "res": res, "flood": flood, "debris": debris}

def mask_geom(m, T):
    g = [shape(s) for s, _ in shapes(m.astype("uint8"), mask=m, transform=T)]
    return shapely.union_all(g) if g else Polygon()

def union_mask(M): return shapely.union_all([mask_geom(M["flood"], M["T"]), mask_geom(M["debris"], M["T"])])

def sample(arr, T, xs, ys, fill=255):
    c, r = ~T * (np.asarray(xs), np.asarray(ys))
    c, r = np.floor(c).astype(int), np.floor(r).astype(int)
    ok = (c >= 0) & (c < arr.shape[1]) & (r >= 0) & (r < arr.shape[0])
    out = np.full(len(c), fill, arr.dtype); out[ok] = arr[r[ok], c[ok]]
    return out

def to_lonlat(crs, x, y): return Transformer.from_crs(crs, 4326, always_xy=True).transform(x, y)
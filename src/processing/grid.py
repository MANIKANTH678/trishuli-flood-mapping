import math
from pyproj import Transformer
from rasterio.transform import from_origin

def utm_epsg(lon, lat):
    return (32600 if lat >= 0 else 32700) + int((lon + 180) // 6) + 1

def make_grids(bbox, epsg):
    """30 m grid snapped to multiples of 30 m, plus a nested 10 m grid (3x finer)."""
    w, s, e, n = bbox
    tf = Transformer.from_crs(4326, epsg, always_xy=True)
    xs, ys = zip(*[tf.transform(x, y) for x, y in [(w, s), (e, s), (e, n), (w, n)]])
    x0, y1 = math.floor(min(xs) / 30) * 30, math.ceil(max(ys) / 30) * 30
    W, H = math.ceil((max(xs) - x0) / 30), math.ceil((y1 - min(ys)) / 30)
    return {30: (from_origin(x0, y1, 30, 30), W, H),
            10: (from_origin(x0, y1, 10, 10), W * 3, H * 3)}
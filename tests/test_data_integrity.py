from pathlib import Path
import rasterio, numpy as np, pytest
ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data/processed"
REQ = ["dem_30m.tif","s1_pre_VV_30m.tif","s1_pre_VH_30m.tif",
       "s1_post_VV_30m.tif","s1_post_VH_30m.tif","flood_mask.tif"]
def _p(n):
    p = PROC / n
    if not p.exists(): pytest.skip(f"missing {p}")
    return p
def test_all_rasters_share_grid():
    ref = None
    for n in REQ:
        with rasterio.open(_p(n)) as s:
            k = (s.crs, s.shape, tuple(s.transform)[:6])
        if ref is None: ref = k
        else: assert k == ref, f"{n} grid mismatch"
def test_flood_mask_is_binary():
    with rasterio.open(_p("flood_mask.tif")) as s: arr = s.read(1)
    assert set(np.unique(arr).tolist()).issubset({0,1})
def test_s1_values_in_db_range():
    with rasterio.open(_p("s1_pre_VV_30m.tif")) as s:
        arr = s.read(1); nd = s.nodata
    v = arr[arr != (nd if nd is not None else -9999)]
    if v.size == 0: pytest.skip("no valid px")
    p01, p99 = np.percentile(v, [1,99])
    assert -60 < p01 < 10 and -40 < p99 < 10

import numpy as np
def test_otsu_or_fallback_returns_float():
    from src.processing.flood_detect_v2 import otsu_or_fallback
    d = np.random.default_rng(0).normal(-1.0,1.0,10_000).astype(np.float32)
    thr, src = otsu_or_fallback(d, -1.5)
    assert isinstance(thr, float) and thr < 0
def test_otsu_handles_empty():
    from src.processing.flood_detect_v2 import otsu_or_fallback
    thr, src = otsu_or_fallback(np.array([], dtype=np.float32), -1.5)
    assert thr == -1.5 and "fallback" in src
def test_lee_filter_shape():
    from src.processing.flood_detect_v2 import lee_filter_db
    img = np.random.default_rng(0).normal(-10,2,(64,64)).astype(np.float32)
    out = lee_filter_db(img, size=5, enl=4.0)
    assert out.shape == img.shape
    assert np.isfinite(out).sum() == np.isfinite(img).sum()

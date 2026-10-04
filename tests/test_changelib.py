import numpy as np
from src.analysis.changelib import robust_z, hysteresis, patch_filter

def test_patch_filter_drops_speckle():
    m = np.zeros((50, 50), bool); m[5, 5] = True; m[20:30, 20:30] = True
    out = patch_filter(m, 8); assert not out[5, 5] and out[25, 25]

def test_injected_drop_found_without_halo():
    lr = np.random.default_rng(0).normal(0, 1, (200, 200)).astype("float32")
    dem = np.full((200, 200), 800, "float32"); lr[80:100, 80:100] -= 8
    z = robust_z(lr, dem, np.ones(lr.shape, bool)); got = hysteresis(z < -3.5, z < -2.5, 8)
    assert got[85:95, 85:95].mean() > 0.95 and got.sum() < 600
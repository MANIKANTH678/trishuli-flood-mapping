import numpy as np
from src.analysis.fuse import fuse

def test_fuse_source_and_confidence():
    s1 = np.array([[1, 2, 254, 253, 2, 0]], np.uint8); s2 = np.array([[1, 254, 2, 2, 0, 254]], np.uint8)
    fused, source, conf, cov = fuse(s1, s2)
    assert fused.tolist() == [[1, 2, 2, 2, 2, 0]]
    assert source.tolist() == [[3, 1, 2, 2, 1, 0]]
    assert conf.tolist() == [[3, 2, 2, 2, 1, 0]]
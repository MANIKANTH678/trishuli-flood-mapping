import numpy as np
def _iou(a,b):
    a=a.astype(bool); b=b.astype(bool)
    u=np.logical_or(a,b).sum()
    return np.logical_and(a,b).sum()/u if u else 0.0
def test_iou_identical(): assert _iou(np.array([[1,1]]),np.array([[1,1]]))==1.0
def test_iou_disjoint():  assert _iou(np.array([[1,0]]),np.array([[0,1]]))==0.0
def test_iou_third():     assert abs(_iou(np.array([[1,1],[0,0]]),np.array([[1,0],[1,0]]))-1/3)<1e-9

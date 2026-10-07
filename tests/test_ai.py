import numpy as np, torch
from src.modeling.dataset import normalize
from src.modeling.common import Counts

def test_normalize_convention():
    assert np.allclose(normalize([-25.0, -10.0, 5.0, 40.0]), [0.0, 1.0, 2.0, 3.0])        # clipped at 3

def test_pooled_iou_is_not_mean_of_chips():
    c = Counts(); c.add(torch.ones(10), torch.ones(10), torch.ones(10)); c.add(torch.zeros(90), torch.ones(90), torch.ones(90))
    assert abs(c.metrics()["iou"] - 0.1) < 1e-9                                             # mean of chip IoUs would be 0.5

def test_scene_inference_uses_shared_normalize():
    s = open("src/modeling/predict_scene.py", encoding="utf-8").read()
    assert "from src.modeling.dataset import normalize" in s and "+ 25" not in s and "+ 15" not in s
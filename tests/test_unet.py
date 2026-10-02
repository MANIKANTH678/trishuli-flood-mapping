import pytest
def test_unet_forward_shape():
    torch = pytest.importorskip("torch")
    from src.modeling.unet import UNet
    y = UNet(in_ch=2, base=8)(torch.randn(1,2,64,64))
    assert y.shape==(1,1,64,64)
def test_param_count():
    torch = pytest.importorskip("torch")
    from src.modeling.unet import UNet
    n = sum(p.numel() for p in UNet(base=32).parameters())
    assert 1_000_000 < n < 15_000_000

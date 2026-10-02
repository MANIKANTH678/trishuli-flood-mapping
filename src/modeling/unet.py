"""unet.py - small U-Net for flood segmentation (dual-pol SAR input)."""
import torch
import torch.nn as nn


def block(i, o):
    return nn.Sequential(
        nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
        nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    def __init__(self, in_ch=2, base=32):
        super().__init__()
        self.e1 = block(in_ch, base)
        self.e2 = block(base, base * 2)
        self.e3 = block(base * 2, base * 4)
        self.e4 = block(base * 4, base * 8)
        self.pool = nn.MaxPool2d(2)

        self.u3 = nn.ConvTranspose2d(base * 8, base * 4, 2, 2)
        self.d3 = block(base * 8, base * 4)
        self.u2 = nn.ConvTranspose2d(base * 4, base * 2, 2, 2)
        self.d2 = block(base * 4, base * 2)
        self.u1 = nn.ConvTranspose2d(base * 2, base, 2, 2)
        self.d1 = block(base * 2, base)

        self.out = nn.Conv2d(base, 1, 1)

    def forward(self, x):
        e1 = self.e1(x)
        e2 = self.e2(self.pool(e1))
        e3 = self.e3(self.pool(e2))
        e4 = self.e4(self.pool(e3))
        d3 = self.d3(torch.cat([self.u3(e4), e3], 1))
        d2 = self.d2(torch.cat([self.u2(d3), e2], 1))
        d1 = self.d1(torch.cat([self.u1(d2), e1], 1))
        return self.out(d1)


if __name__ == "__main__":
    m = UNet()
    n = sum(p.numel() for p in m.parameters())
    print(f"params: {n/1e6:.2f} M")
    x = torch.randn(2, 2, 512, 512)
    with torch.no_grad():
        y = m(x)
    print(f"in:  {x.shape}")
    print(f"out: {y.shape}")

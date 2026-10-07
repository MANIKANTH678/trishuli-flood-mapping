import glob, numpy as np, rasterio
from src.modeling.dataset import S1_DIR
pct = lambda a: np.nanpercentile(a, [5, 50, 95]).round(1)
tr = np.concatenate([rasterio.open(f).read().reshape(2, -1)[:, ::50] for f in sorted(glob.glob(str(S1_DIR / "*.tif")))[::4]], axis=1)
for i, pol in enumerate(("VV", "VH")):
    with rasterio.open(f"data/processed/s1_post_{pol}_10m.tif") as s: a = s.read(1, masked=True).astype("float32").filled(np.nan)[::10, ::10]
    print(pol, "Sen1Floods11 p5/p50/p95:", pct(tr[i]), "| Trishuli post:", pct(a))
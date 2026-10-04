import sys, json, os, numpy as np, rasterio, torch
from pathlib import Path
ROOT = Path(".").resolve(); sys.path.insert(0, str(ROOT))
from src.modeling.unet import UNet

P = ROOT / "data/processed"
def rd(n):
    with rasterio.open(P / n) as s:
        return s.read(1, masked=True).astype("float32").filled(np.nan)

model = UNet()
model.load_state_dict(torch.load(ROOT / "outputs/flood_unet.pt", map_location="cpu")); model.eval()

def mask(st, tile=512, stride=256):
    st = np.nan_to_num(st, nan=0.0); H, W = st.shape[1:]
    pred = np.zeros((H, W), bool); cov = np.zeros((H, W), bool)
    with torch.no_grad():
        for y in range(0, H - tile + 1, stride):
            for x in range(0, W - tile + 1, stride):
                lg = model(torch.from_numpy(st[:, y:y+tile, x:x+tile]).unsqueeze(0))[0, 0].numpy()
                pred[y:y+tile, x:x+tile] |= lg > 0; cov[y:y+tile, x:x+tile] = True
    return pred, cov

norm = lambda a: np.clip((a + 25) / 15, -3, 3)
po, co = mask(np.stack([norm(rd("s1_post_VV_30m.tif")), norm(rd("s1_post_VH_30m.tif"))]))
pr, cr = mask(np.stack([norm(rd("s1_pre_VV_30m.tif")), norm(rd("s1_pre_VH_30m.tif"))]))

res = {"post": dict(flood_px=int(po.sum()), covered_px=int(co.sum())),
       "pre":  dict(flood_px=int(pr.sum()), covered_px=int(cr.sum())),
       "new_water_px": int((po & ~pr).sum()), "lost_water_px": int((pr & ~po).sum())}
print(res)
os.makedirs("outputs/validation", exist_ok=True)
json.dump(res, open("outputs/validation/unet_corridor.json", "w"), indent=2)
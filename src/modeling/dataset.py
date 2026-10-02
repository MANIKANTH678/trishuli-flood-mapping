"""dataset.py - Sen1Floods11 paired (S1, Label) Dataset."""
from pathlib import Path
import numpy as np
import rasterio
import torch
from torch.utils.data import Dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/external/sen1floods11/v1.1"
S1_DIR  = DATA / "data/flood_events/HandLabeled/S1Hand"
LBL_DIR = DATA / "data/flood_events/HandLabeled/LabelHand"


class Sen1Floods11(Dataset):
    def __init__(self, split_csv):
        csv = DATA / "splits" / split_csv
        self.pairs = []
        for line in csv.read_text().strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                self.pairs.append((parts[0], parts[1]))

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        s1_name, lbl_name = self.pairs[i]
        with rasterio.open(S1_DIR / s1_name) as src:
            s1 = src.read().astype("float32")          # (2, H, W): VV, VH
        with rasterio.open(LBL_DIR / lbl_name) as src:
            lbl = src.read(1).astype("float32")        # (H, W): 0/1/-1

        s1 = np.clip((s1 + 25.0) / 15.0, -3.0, 3.0)
        s1 = np.nan_to_num(s1, nan=0.0)

        valid = (lbl != -1).astype("float32")
        lbl = np.clip(lbl, 0, 1).astype("float32")

        return {
            "image": torch.from_numpy(s1),
            "mask":  torch.from_numpy(lbl).unsqueeze(0),
            "valid": torch.from_numpy(valid).unsqueeze(0),
        }


if __name__ == "__main__":
    ds = Sen1Floods11("flood_train_data.csv")
    print(f"train pairs: {len(ds)}")
    x = ds[0]
    print(f"image: {x['image'].shape} {x['image'].dtype}")
    print(f"mask:  {x['mask'].shape}  {x['mask'].dtype}")
    print(f"mask values: {x['mask'].unique().tolist()}")
    print(f"valid: {x['valid'].shape}  {x['valid'].dtype}")

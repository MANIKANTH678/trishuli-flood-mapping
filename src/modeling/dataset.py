from pathlib import Path
import numpy as np, rasterio, torch
from torch.utils.data import Dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/external/sen1floods11/v1.1"
S1_DIR = DATA / "data/flood_events/HandLabeled/S1Hand"
LBL_DIR = DATA / "data/flood_events/HandLabeled/LabelHand"
SPLIT_DIR = DATA / "splits/flood_handlabeled"

def normalize(db):
    """dB (VV, VH) -> network input. Defined ONLY here. NaN stays NaN; callers mask it."""
    return np.clip((np.asarray(db, "float32") + 25.0) / 15.0, -3.0, 3.0)

def read_pairs(csv):
    csv = Path(csv)
    if not csv.exists(): csv = SPLIT_DIR / csv.name
    rows = [[p.strip() for p in l.split(",")] for l in csv.read_text().strip().splitlines()]
    return [(r[0], r[1]) for r in rows if len(r) >= 2]

class Sen1Floods11(Dataset):
    def __init__(self, csv, augment=False, s1_dir=S1_DIR, lbl_dir=LBL_DIR):
        self.pairs, self.augment, self.s1_dir, self.lbl_dir = read_pairs(csv), augment, Path(s1_dir), Path(lbl_dir)
    def __len__(self): return len(self.pairs)
    def __getitem__(self, i):
        s1_name, lbl_name = self.pairs[i]
        with rasterio.open(self.s1_dir / s1_name) as s: s1 = s.read().astype("float32")
        with rasterio.open(self.lbl_dir / lbl_name) as s: lbl = s.read(1).astype("float32")
        valid = (lbl != -1) & np.isfinite(s1).all(0)           # NaN pixels are invalid, NOT "very dark"
        x, y = np.nan_to_num(normalize(s1), nan=0.0), np.clip(lbl, 0, 1)
        if self.augment:                                        # rot90 + flips
            k = int(torch.randint(4, (1,)))
            x, y, valid = (np.rot90(a, k, axes=(-2, -1)) for a in (x, y, valid))
            if torch.rand(1) < 0.5: x, y, valid = (a[..., ::-1] for a in (x, y, valid))
        t = lambda a: torch.from_numpy(np.ascontiguousarray(a, dtype="float32"))
        return {"image": t(x), "mask": t(y)[None], "valid": t(valid)[None], "name": s1_name}

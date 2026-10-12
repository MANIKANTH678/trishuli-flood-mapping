"""Clear-sky check for the Himalayan chips BEFORE labelling (rule fixed in docs/chip_protocol.md: drop any chip whose
Sentinel-2 clear fraction on the labelling date is below 0.70, and list the dropped chips).

python tools/chip_clear.py 20260827                                    # post-event chips (labelled from the 27 Aug S2)
python tools/chip_clear.py 20260812 --chips data/external/himalaya_chips_pre/S1    # pre-event chips (12 Aug S2)

clear = mean of data/interim/s2/<date>/clear_30m.tif over the chip footprint (no-data pixels ignored, as in the review);
valid = share of the footprint that has any S2 data at all (a chip with valid < 1 is partly outside the S2 tiles)."""
import argparse
from pathlib import Path
import numpy as np, rasterio
from rasterio.windows import from_bounds

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("date"); ap.add_argument("--chips", default="data/external/himalaya_chips/S1")
    ap.add_argument("--min-clear", type=float, default=0.7); a = ap.parse_args()
    keep = 0; files = sorted(Path(a.chips).glob("*_S1.tif"))
    with rasterio.open(f"data/interim/s2/{a.date}/clear_30m.tif") as clr:
        print(f"chip-clear check, S2 date {a.date}, rule: KEEP if clear >= {a.min_clear:.2f}")
        for f in files:
            with rasterio.open(f) as s: b = s.bounds
            a_ = clr.read(1, window=from_bounds(*b, transform=clr.transform), boundless=True, masked=True).filled(np.nan)
            c = np.nanmean(a_) if np.isfinite(a_).any() else float("nan"); v = float(np.isfinite(a_).mean())
            ok = bool(np.isfinite(c) and c >= a.min_clear); keep += ok
            print(f"{f.stem[:-3]:20s} clear={c:.2f} valid={v:.2f} {'KEEP' if ok else 'DROP'}")
    print(f"KEEP {keep} of {len(files)}")

if __name__ == "__main__":
    main()

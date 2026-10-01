"""Generate full-AOI flood susceptibility raster from trained model."""
import os, sys
import numpy as np
import joblib
import rioxarray

sys.path.insert(0, os.path.dirname(os.path.dirname
(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR

FEATURES = ["elevation", "slope", "aspect", "tpi", "dist_lowland",
            "vv_diff", "vh_diff", "vv_pre", "vh_pre"]


def main():
    feat_dir = os.path.join(OUTPUTS_DIR, "features")
    X = np.stack([np.load(os.path.join(feat_dir, f"{f}.npy")) for f in FEATURES], axis=-1)
    H, W, N = X.shape

    clf = joblib.load(os.path.join(OUTPUTS_DIR, "flood_model.joblib"))

    Xf = X.reshape(-1, N).astype(np.float32)
    valid = np.all(np.isfinite(Xf), axis=1)
    proba = np.zeros(len(Xf), dtype=np.float32)
    proba[valid] = clf.predict_proba(Xf[valid])[:, 1]
    proba = proba.reshape(H, W)

    # Reference for georeferencing
    ref = rioxarray.open_rasterio(os.path.join(PROCESSED_DIR, "dem_30m.tif"),
                                  masked=True).squeeze()

    def _clean(da):
        """Remove old attrs/encoding that conflict with to_raster."""
        da.attrs = {}
        da.encoding = {}
        return da

    # --- Probability raster ---
    out = ref.copy()
    out.values = proba
    out = _clean(out)
    out.rio.write_nodata(-1, inplace=True)
    out.rio.write_crs(ref.rio.crs, inplace=True)
    out.rio.write_transform(ref.rio.transform(), inplace=True)
    out.rio.to_raster(os.path.join(OUTPUTS_DIR, "susceptibility.tif"))
    print(f"✅ outputs/susceptibility.tif   "
          f"range={proba.min():.3f}–{proba.max():.3f}  mean={proba.mean():.3f}")

    # --- Binary raster ---
    binary = (proba > 0.96).astype(np.uint8)
    out2 = ref.copy()
    out2.values = binary
    out2 = _clean(out2)
    out2.rio.write_nodata(0, inplace=True)
    out2.rio.write_crs(ref.rio.crs, inplace=True)
    out2.rio.write_transform(ref.rio.transform(), inplace=True)
    out2.rio.to_raster(os.path.join(OUTPUTS_DIR, "susceptibility_binary.tif"))
    print(f"✅ outputs/susceptibility_binary.tif   "
          f"predicted flood pixels: {int(binary.sum()):,}  "
          f"area: {binary.sum()*900/1e6:.2f} km²")


if __name__ == "__main__":
    main()

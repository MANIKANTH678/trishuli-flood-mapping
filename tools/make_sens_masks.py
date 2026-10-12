"""Threshold-sensitivity masks (low / base / high) for the scenario ranges in damage_v2 / cutoff_v2.
python tools/make_sens_masks.py [--ref pre,placebo,pre3,pre4]     (src.run passes the run's reference splits)"""
import argparse, subprocess, sys
from pathlib import Path

SCEN = {"low": (3.0, 2.0), "base": (4.0, 2.5), "high": (5.0, 3.0)}      # (t_hi, t_lo): base +- 1 sigma
ap = argparse.ArgumentParser(); ap.add_argument("--ref", default="pre,placebo,pre3,pre4"); a = ap.parse_args()
for name, (hi, lo) in SCEN.items():
    d = Path("data/processed/_sens") / name; d.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "src.analysis.detect", "--ref", a.ref, "--t-hi", str(hi), "--t-lo", str(lo), "--no-gate",
                    "--out-dir", str(d), "--track-id", f"sens_{name}"], check=True)
    subprocess.run([sys.executable, "-m", "src.analysis.fuse", "--s1", str(d / "detect_class_30m.tif"), "--out-dir", str(d)], check=True)

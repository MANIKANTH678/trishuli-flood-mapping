#!/usr/bin/env python3
"""Compare damage_v2 outputs against EMSR927 builtUpP damage totals."""
from __future__ import annotations
import json
from pathlib import Path
from collections import Counter

import geopandas as gpd
import pyogrio

ROOT = Path(__file__).resolve().parents[2]
EMSR = ROOT / "data/external/EMSR927"
OUT  = ROOT / "outputs/validation"
OUT.mkdir(parents=True, exist_ok=True)

IMPACT = ROOT / "outputs/impact_summary.json"
impact = json.loads(IMPACT.read_text()) if IMPACT.exists() else {}

AOI_DIRS = {
    "AOI01": ("Syapru Besi", 28.1686, 85.3357),
    "AOI02": ("Timure",      28.2612, 85.3688),
    "AOI03": ("Bidur",       27.9329, 85.1461),
    "AOI05": ("Phosretar",   27.8300, 85.0246),
}


def emsr_counts(aoi_dir: Path):
    gpkgs = list(aoi_dir.glob("*.gpkg"))
    if not gpkgs:
        return None
    gpkg = gpkgs[0]
    layers = pyogrio.list_layers(gpkg)[:, 0].tolist()
    bld_lyr = next((l for l in layers if l.startswith("builtUpP")), None)
    if not bld_lyr:
        return None
    gdf = gpd.read_file(gpkg, layer=bld_lyr, engine="pyogrio")
    return Counter(gdf["damage_gra"].tolist())


result = {
    "our_impact_summary": impact,
    "emsr927_by_aoi": {},
    "comparison": {
        "our_flooded_buildings": impact.get("flooded_buildings"),
        "emsr927_destroyed_total": 0,
        "emsr927_damaged_total": 0,
        "emsr927_possibly_total": 0,
    },
}

print(f"{'AOI':8s}  {'locality':14s}  {'Destroyed':>10s}  {'Damaged':>8s}  "
      f"{'Possibly':>9s}  {'total':>6s}")
print("-" * 70)
for aoi, (locality, lat, lon) in AOI_DIRS.items():
    counts = emsr_counts(EMSR / aoi)
    if counts is None:
        print(f"{aoi:8s}  {locality:14s}  (no gpkg / no builtUpP)")
        continue
    d = counts.get("Destroyed", 0)
    m = counts.get("Damaged", 0)
    p = counts.get("Possibly damaged", 0)
    total = d + m + p
    print(f"{aoi:8s}  {locality:14s}  {d:>10d}  {m:>8d}  {p:>9d}  {total:>6d}")
    result["emsr927_by_aoi"][aoi] = {
        "locality": locality, "Destroyed": d, "Damaged": m,
        "Possibly damaged": p, "total": total,
    }
    result["comparison"]["emsr927_destroyed_total"] += d
    result["comparison"]["emsr927_damaged_total"]   += m
    result["comparison"]["emsr927_possibly_total"]  += p

print()
print("Our impact_summary.json:")
print(f"  flooded_buildings = {impact.get('flooded_buildings', '?')}")
print(f"  debris_buildings  = {impact.get('debris_buildings', '?')}")
print(f"  flooded_bridges   = {impact.get('flooded_bridges', '?')}")
print()
print("EMSR927 (all AOIs):")
print(f"  Destroyed total         = {result['comparison']['emsr927_destroyed_total']}")
print(f"  Damaged total           = {result['comparison']['emsr927_damaged_total']}")
print(f"  Possibly damaged total  = {result['comparison']['emsr927_possibly_total']}")

OUT.joinpath("damage_sanity.json").write_text(json.dumps(result, indent=2))
print(f"\nWrote {OUT/'damage_sanity.json'}")

#!/usr/bin/env python3
"""
Day 8 -- EMSR927 proxy validation of flood_mask.tif.

EMSR927 (Flood in Nepal, GLOF, 26 Aug 2026) GRA products contain:
  - observedEventA : landslide polygons (NOT flood polygons)
  - builtUpP       : building damage points with `damage_gra` field
  - areaOfInterestA: AOI polygon
  - notAnalysedA   : areas analysts did not assess

Because there is no flood extent layer, we cannot compute IoU/F1 against
a reference flood mask. Instead we compute proxy metrics:

  1. damage_point_recall
  2. landslide_overlap (fraction of landslide area inside flood mask)
  3. flood_mask_coverage (fraction of flood mask inside AOI)

All statistics exclude notAnalysedA pixels and are clipped to the AOI.

Output: data/processed/emsr927_comparison.json
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import geopandas as gpd
import pyogrio
import rasterio
from rasterio.features import rasterize
from shapely.ops import unary_union

DAMAGE_GRADES = ["Destroyed", "Damaged", "Possibly damaged"]


# ---------- helpers ----------

def list_layers(gpkg: Path) -> list[str]:
    return pyogrio.list_layers(gpkg)[:, 0].tolist()


def find_layer(layers, prefix: str) -> str | None:
    for lyr in layers:
        if lyr.startswith(prefix):
            return lyr
    return None


def find_gpkg(aoi_dir: Path) -> Path:
    hits = sorted(aoi_dir.glob("*.gpkg"))
    if not hits:
        raise FileNotFoundError(f"No .gpkg in {aoi_dir}")
    return hits[0]


def sample_raster_at_points(mask, transform, xs, ys) -> np.ndarray:
    """Boolean array: True where point falls inside mask==1 and in-bounds."""
    out = np.zeros(len(xs), dtype=bool)
    if len(xs) == 0:
        return out
    rows, cols = rasterio.transform.rowcol(transform, xs, ys)
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    h, w = mask.shape
    inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
    out[inside] = mask[rows[inside], cols[inside]]
    return out


def rasterize_union(geom, out_shape, transform, all_touched=False) -> np.ndarray:
    if geom is None or geom.is_empty:
        return np.zeros(out_shape, dtype=np.uint8)
    return rasterize(
        [(geom, 1)],
        out_shape=out_shape,
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=all_touched,
    )


def rasterize_gdf(gdf, out_shape, transform, all_touched=False) -> np.ndarray:
    if gdf.empty:
        return np.zeros(out_shape, dtype=np.uint8)
    geoms = [g for g in gdf.geometry if g is not None and not g.is_empty]
    if not geoms:
        return np.zeros(out_shape, dtype=np.uint8)
    return rasterize(
        [(g, 1) for g in geoms],
        out_shape=out_shape,
        transform=transform,
        fill=0,
        dtype=np.uint8,
        all_touched=all_touched,
    )


# ---------- per-AOI processing ----------

def process_aoi(aoi_dir: Path, flood_mask: np.ndarray, profile) -> tuple[str, dict]:
    gpkg = find_gpkg(aoi_dir)
    layers = list_layers(gpkg)

    aoi_lyr = find_layer(layers, "areaOfInterestA")
    obs_lyr = find_layer(layers, "observedEventA")
    bld_lyr = find_layer(layers, "builtUpP")
    na_lyr  = find_layer(layers, "notAnalysedA")

    aoi_gdf = gpd.read_file(gpkg, layer=aoi_lyr, engine="pyogrio")
    locality = str(aoi_gdf["locality"].iloc[0])
    area_id  = str(aoi_gdf["area_id"].iloc[0]).zfill(2)
    emsr_id  = str(aoi_gdf["emsr_id"].iloc[0])

    raster_crs = profile["crs"]
    transform  = profile["transform"]
    out_shape  = flood_mask.shape

    aoi_proj = aoi_gdf.to_crs(raster_crs)
    aoi_union = unary_union(aoi_proj.geometry.tolist())

    # valid area = AOI \ notAnalysedA
    if na_lyr:
        na_gdf = gpd.read_file(gpkg, layer=na_lyr, engine="pyogrio").to_crs(raster_crs)
        na_union = unary_union(na_gdf.geometry.tolist()) if len(na_gdf) else None
    else:
        na_union = None

    valid_geom = aoi_union.difference(na_union) if na_union is not None else aoi_union

    valid_mask = rasterize_union(valid_geom, out_shape, transform).astype(bool)

    # ---- 1. Damage point recall
    pts = gpd.read_file(gpkg, layer=bld_lyr, engine="pyogrio").to_crs(raster_crs)
    if na_union is not None:
        pts = pts[~pts.geometry.intersects(na_union)]
    pts = pts[pts.geometry.intersects(aoi_union)]

    damage = {"total": int(len(pts)), "inside_flood_mask": 0, "recall": 0.0, "by_grade": {}}
    if len(pts):
        xs = pts.geometry.x.to_numpy()
        ys = pts.geometry.y.to_numpy()
        inside = sample_raster_at_points(flood_mask, transform, xs, ys)
        damage["inside_flood_mask"] = int(inside.sum())
        damage["recall"] = float(inside.mean())
        grade_col = pts["damage_gra"].to_numpy()
        for grade in DAMAGE_GRADES:
            sel = grade_col == grade
            n = int(sel.sum())
            if n == 0:
                continue
            sub_inside = sample_raster_at_points(flood_mask, transform, xs[sel], ys[sel])
            damage["by_grade"][grade] = {
                "total": n,
                "inside": int(sub_inside.sum()),
                "recall": float(sub_inside.mean()),
            }

    # ---- 2. Landslide overlap
    land = gpd.read_file(gpkg, layer=obs_lyr, engine="pyogrio").to_crs(raster_crs)
    land = land[land.geometry.intersects(valid_geom)].copy()
    if len(land):
        land["geometry"] = land.geometry.intersection(valid_geom)
        land_mask = rasterize_gdf(land, out_shape, transform).astype(bool)
    else:
        land_mask = np.zeros(out_shape, dtype=bool)

    land_px = int(land_mask.sum())
    overlap_px = int((land_mask & flood_mask).sum())

    # ---- 3. Flood coverage inside AOI
    flood_in_aoi_px = int((flood_mask & valid_mask).sum())
    flood_total_px  = int(flood_mask.sum())

    # pixel area (assumes projected CRS; check below)
    pa_km2 = abs(transform.a * transform.e) / 1e6

    key = f"AOI{area_id}_{locality.replace(' ', '_')}"
    stats = {
        "emsr_id": emsr_id,
        "locality": locality,
        "area_id": area_id,
        "raster_crs": str(raster_crs),
        "damage_points": {
            **damage,
            "note": "Excludes points inside notAnalysedA and outside AOI.",
        },
        "landslide_overlap": {
            "n_polygons_intersecting_aoi": int(len(land)),
            "landslide_area_km2": round(land_px * pa_km2, 6),
            "overlap_area_km2": round(overlap_px * pa_km2, 6),
            "overlap_fraction": (overlap_px / land_px) if land_px else None,
        },
        "flood_mask_coverage": {
            "flood_area_in_aoi_km2": round(flood_in_aoi_px * pa_km2, 6),
            "flood_area_total_km2": round(flood_total_px * pa_km2, 6),
            "fraction_in_aoi": (flood_in_aoi_px / flood_total_px) if flood_total_px else None,
        },
    }
    return key, stats


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flood-mask", default="data/processed/flood_mask.tif")
    ap.add_argument("--emsr-dir",   default="data/external/EMSR927")
    ap.add_argument("--out",        default="data/processed/emsr927_comparison.json")
    args = ap.parse_args()

    fm_path = Path(args.flood_mask)
    if not fm_path.exists():
        raise SystemExit(f"flood_mask not found: {fm_path}")

    with rasterio.open(fm_path) as src:
        arr = src.read(1)
        nodata = src.nodata
        profile = src.profile

    if profile["crs"] is None:
        raise SystemExit("flood_mask has no CRS")
    if profile["crs"].is_geographic:
        warnings.warn("flood_mask CRS is geographic; pixel-area math will be approximate. "
                      "Reproject to a projected CRS (e.g. EPSG:32645) for accurate areas.")

    flood_mask = (arr > 0) & (arr != nodata) if nodata is not None else (arr > 0)

    emsr_dir = Path(args.emsr_dir)
    aoi_dirs = sorted(p for p in emsr_dir.iterdir() if p.is_dir() and p.name.startswith("AOI"))

    result = {
        "metadata": {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "flood_mask": str(fm_path),
            "emsr_dir": str(emsr_dir),
            "emsr_activation": "EMSR927",
            "emsr_event": "Flood in Nepal (Rasuwa/Nuwakot GLOF, 26 Aug 2026)",
            "caveats": [
                "EMSR927 GRA products contain NO flood extent layer.",
                "Validation uses building damage-point recall and landslide overlap as PROXY metrics, NOT IoU against a reference flood mask.",
                "Damage may be caused by mass movement (landslides) rather than flooding; low damage-point recall is therefore not, on its own, a detector error.",
                "notAnalysedA polygons are excluded from all statistics.",
            ],
        },
        "aois": {},
    }

    def _json_default(o):
        if isinstance(o, (np.floating, np.integer)):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return str(o)

    for aoi_dir in aoi_dirs:
        try:
            key, stats = process_aoi(aoi_dir, flood_mask, profile)
            result["aois"][key] = stats
            print(f"OK  {key}  "
                  f"damage_recall={stats['damage_points']['recall']:.3f}  "
                  f"landslide_overlap={stats['landslide_overlap']['overlap_fraction']}")
        except Exception as e:
            print(f"FAIL {aoi_dir.name}: {e}")
            result["aois"][aoi_dir.name] = {"error": str(e)}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=_json_default))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()

# Trishuli Flood Damage Mapping

**Track B — Multimodal AI Hackathon 2026**

Post-event damage assessment for the **26 August 2026 Trishuli–Bhote Koshi
flash flood (Rasuwa District, Nepal)** using free Sentinel-1 SAR, DEM,
OpenStreetMap data: ohsome API snapshot 2026-07-27 (pre-event), manifest in `data/raw/osm/manifest.json`. © OpenStreetMap contributors (ODbL).

> **Status.** Earlier versions of this README claimed the Sentinel-1 pair contains no
> GLOF signal. That claim is withdrawn: the diagnostic behind it used 600 m window
> medians at EMSR927 coordinates on GCP-geocoded, uncalibrated imagery, which cannot
> support it. Preprocessing is being rebuilt (calibrated, terrain-corrected σ⁰).
> Numbers below come from the baseline pipeline (`v0-baseline`) and are **not reliable**.

## Pipeline

    fetch (S1 + OSM) -> geocode S1 -> align (30 m UTM 45N) -> detect (SAR)
        -> damage (OSM intersect) -> cutoff (hospital reachability)
        -> validate (EMSR927) -> sanity checks -> report

| Stage              | Script                                  | Output                                   |
| ------------------ | --------------------------------------- | ---------------------------------------- |
| S1 download        | `src/fetch/fetch_sentinel1.py`          | `data/raw/s1/{pre,post}/*.SAFE`          |
| OSM download       | `src/download/fetch_osm.py`             | `data/raw/osm/*.geojson`                 |
| Geocode            | `src/processing/geocode_s1.py`          | `data/raw/s1/*/geocoded/*.tif`           |
| Align              | `src/processing/align.py`               | `data/processed/s1_*_30m.tif`            |
| Orbit check        | `src/processing/align_v2_checks.py`     | (validation gate)                        |
| Flood detect       | `src/processing/flood_detect_v2.py`     | `data/processed/flood_mask.tif`          |
| Damage             | `src/processing/damage_v2.py`           | `outputs/affected_*.geojson`             |
| Cutoff             | `src/processing/cutoff_v2.py`           | `outputs/cutoff_settlements.json`        |
| Train U-Net        | `src/modeling/train_segmentation.py`    | `outputs/flood_unet.pt`                  |
| Eval U-Net         | `src/modeling/eval_himalaya_heldout.py` | `outputs/himalaya_heldout_metrics.json`  |
| EMSR927 validation | `src/validation/emsr927_comparison.py`  | `data/processed/emsr927_comparison.json` |
| Damage sanity      | `src/validation/damage_sanity_check.py` | `outputs/validation/damage_sanity.json`  |

## Setup

    python3 -m venv ~/flood-venv
    source ~/flood-venv/bin/activate
    pip install -r requirements.txt

Set credentials in `src/config.py`:

    COPERNICUS_USER = "you@example.com"
    COPERNICUS_PASS = "your-password"

Register free at . `src/config.py` is
`.gitignore`d to prevent accidental commits.

## Run

    bash run_all.sh

or step-by-step (see Pipeline table above).

## Train / eval U-Net

    python -m src.modeling.train_segmentation      # ~2.5 h CPU, 20 epochs
    python src/modeling/eval_himalaya_heldout.py   # ~5 min

Trained on **Sen1Floods11 v1.1** (252 train / 89 val). Best val IoU **0.523**,
final F1 **0.593**. Proxy-Himalaya (India + Pakistan) IoU **0.554**.

## Key results

| Metric                       | Value (baseline, unreliable) |
| ---------------------------- | ---------------------------- |
| U-Net val IoU (Sen1Floods11) | 0.523                        |
| U-Net proxy-Himalaya IoU     | 0.554                        |
| EMSR927 damage-point recall  | 0.000                        |
| Our flooded buildings        | 61,977 (16x EMSR927 3,816)   |

Full discussion: `FINAL_REPORT.md`.

## Tests

    python -m pytest tests/ -q

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md). Code: MIT. Data: own licenses.

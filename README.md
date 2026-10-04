# Trishuli Flood Damage Mapping

**Track B — Multimodal AI Hackathon 2026**

Post-event damage assessment for the **26 August 2026 Trishuli–Bhote Koshi
flash flood (Rasuwa District, Nepal)** using free Sentinel-1 SAR, a DEM and
OpenStreetMap (ohsome API snapshot 2026-07-27, pre-event; manifest in
`data/raw/osm/manifest.json`). © OpenStreetMap contributors (ODbL).

> **Status.** Sentinel-1 preprocessing is SNAP-based (calibrated, terrain-corrected
> σ⁰, Copernicus GLO-30 DEM). The flood mask is a SAR change-detection product, **not a
> validated flood extent**. Evidence is mixed (see Key results): the river itself shows no
> median backscatter change, and the mask coincides with EMSR927 damage points at Bidur and
> Phosretar more than a random null does, but nearly all of the mask area inside those two
> AOIs lies on mapped landslide polygons, the mask is empty at the two Rasuwa AOIs, and a
> U-Net water check shows no net change. An earlier README claimed the pair holds no GLOF
> signal; that claim is withdrawn, because its diagnostic used uncalibrated, GCP-geocoded
> imagery.

## Pipeline

`run_all.sh` runs these stages in order. A failure stops the run.

| #   | Stage                           | Script                                                                          | Output                                             |
| --- | ------------------------------- | ------------------------------------------------------------------------------- | -------------------------------------------------- |
| 1   | S1 download                     | `src/fetch/fetch_sentinel1.py`                                                  | `data/raw/sentinel1/{pre,post}/*.SAFE.zip`         |
| 2   | Unzip                           | inline in `run_all.sh`                                                          | `data/raw/sentinel1/{pre,post}/*.SAFE`             |
| 3   | Orbit / pass / 12-day gate      | `src/processing/align_v2_checks.py`                                             | (gate; exits 1 on violation)                       |
| 4   | OSM download                    | `src/download/fetch_osm.py`                                                     | `data/raw/osm/*.geojson`, `manifest.json`          |
| 5   | DEM                             | `src/fetch/fetch_dem.py`                                                        | `data/raw/dem/dem_glo30_wgs84.tif`                 |
| 6   | SNAP preprocessing              | `src/processing/s1_preprocess.py`                                               | `data/interim/s1_tc/`                              |
| 7   | Grid + dB                       | `src/processing/s1_to_grid.py`                                                  | 30 m UTM 45N VV/VH dB rasters in `data/processed/` |
| 8   | Flood detect                    | `src/processing/flood_detect_v2.py`                                             | `flood_mask.tif`, `debris_mask.tif`                |
| 9   | Damage                          | `src/processing/damage_v2.py`                                                   | `outputs/affected_*`, `impact_summary.json`        |
| 9b  | Cutoff                          | `src/processing/cutoff_v2.py`                                                   | `outputs/cutoff_settlements.json`                  |
| 10  | EMSR927 validation              | `src/validation/emsr927_comparison.py`                                          | `data/processed/emsr927_comparison.json`           |
| 10  | Damage sanity                   | `src/validation/damage_sanity_check.py`                                         | `outputs/validation/damage_sanity.json`            |
| 11  | Mask validation                 | `tools/signal_check.py`, `tools/unet_corridor.py`, `tools/null_recall_aoi.py`   | JSON per tool                                      |
| 12  | Maps, dashboard, slides, report | `src/report/impact.py`, `dashboard_full.py`, `slides.py`, `situation_report.py` | `outputs/`                                         |

Steps 10 and 11 (`null_recall_aoi.py`) and the situation report need `data/external/EMSR927`;
without it they are skipped.

Not part of `run_all.sh`:

| Stage       | Script                                  | Output                                  |
| ----------- | --------------------------------------- | --------------------------------------- |
| Train U-Net | `src/modeling/train_segmentation.py`    | `outputs/flood_unet.pt`                 |
| Eval U-Net  | `src/modeling/eval_himalaya_heldout.py` | `outputs/himalaya_heldout_metrics.json` |

## Setup

```
python -m venv .venv
.venv\Scripts\activate          # Windows;  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Requirements beyond Python packages:

- **bash** to run `run_all.sh` (Git Bash or WSL on Windows).
- **ESA SNAP** installed, for step 6.
- **Network access** for the OSM (ohsome) and DEM downloads.
- **An ohsome API key** for step 4 (free, https://account.heigit.org/signup), set as the
  environment variable `OHSOME_API_KEY` for the session. Never commit it.
- **Copernicus Data Space credentials**, needed only if scenes are not already on disk.
  Register free at https://dataspace.copernicus.eu/ and set in `src/config.py`
  (`.gitignore`d):

```
COPERNICUS_USER = "you@example.com"
COPERNICUS_PASS = "your-password"
```

## Run

```
bash run_all.sh
```

The Sentinel-1 date windows (pre 13–19 Aug, post 25–31 Aug 2026, relative orbit 85,
ascending) and the event date are fixed for this flood. The pair used is 2026-08-16
and 2026-08-28, 12 days apart; each date is two consecutive frames of one pass.

**Verified.** With `data/interim/s1_tc/` deleted, `run_all.sh` regenerated the SNAP outputs
and reproduced every figure in Key results. The OSM inputs for that run were restored from a
saved 2026-07-27 snapshot, because the ohsome quota was exhausted.

**ohsome quota.** Step 4 queries the ohsome API and can fail with `403 Quota exceeded`.
Wait for the quota to reset and rerun.

**Freshness guards.** The situation report refuses to run if the OSM manifest snapshot
differs from `config.OSM_SNAPSHOT_DATE`, or if `cutoff_settlements.json` and the three
validation JSONs from step 11 are older than `flood_mask.tif`.

## Train / eval U-Net

```
python -m src.modeling.train_segmentation      # ~2.5 h CPU, 20 epochs
python src/modeling/eval_himalaya_heldout.py   # ~5 min
```

Trained on **Sen1Floods11 v1.1** (252 train / 89 val). Best val IoU **0.523**,
final F1 **0.593**. Proxy-Himalaya (India + Pakistan) IoU **0.554**.

## Key results

| Metric                                     | Value                                                                                                                                                                                                                      |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| U-Net val IoU (best epoch, per-batch mean) | 0.523 (pooled held-out: 0.574)                                                                                                                                                                                             |
| U-Net proxy-Himalaya IoU                   | 0.554                                                                                                                                                                                                                      |
| SAR flood / debris mask                    | 5,802 px (5.22 km²) / 652 px (0.59 km²)                                                                                                                                                                                    |
| Backscatter change (post − pre)            | river, 60 m buffer: median +0.02 dB, p1 −6.22 dB; river shifted ±1500 m: −0.08 dB, p1 −4.74 / −4.46 dB; whole scene: +0.00 dB. Mask pixels: −3.03 dB (the mask is selected on change, so this is not independent evidence) |
| EMSR927 damage points inside mask          | 966 of 3,816 (25.3%): Bidur 867 of 2,343, Phosretar 99 of 609, Syapru Besi 0, Timure 0                                                                                                                                     |
| EMSR927 hit rate vs random null            | Bidur 0.370 vs 0.113 ± 0.010; Phosretar 0.170 vs 0.091 ± 0.017 (the null test uses 581 of Phosretar's 609 points)                                                                                                          |
| Mask area on mapped landslide polygons     | Bidur 1.73 of 1.77 km² (98%); Phosretar 1.62 of 1.67 km² (97%), so recall there cannot be read as flood detection                                                                                                          |
| Mask pixels in Syapru Besi / Timure        | 0 (slope filter leaves 163 / 282 flat pixels), so recall 0.0                                                                                                                                                               |
| U-Net corridor water check                 | 21,020 new vs 21,627 lost water px: no net change, so it does **not** independently confirm the flood                                                                                                                      |
| Buildings in mask (not a validated flood)  | 991 flooded + 102 debris, of 189,503 (0.523 % flooded)                                                                                                                                                                     |
| Roads / bridges in mask                    | 83 of 14,151 roads (0.587 %); 21 of 385 bridges                                                                                                                                                                            |
| Settlements cut off from all 20 hospitals  | 4 of 446 (no remaining road path); derived from an unvalidated mask. All four lie in the far north near the border crossing and appear to be Tibetan-side villages (to be verified)                                        |

Hit rates are "better than chance", not accuracy. No locality or district breakdown is
reported: none of the flooded buildings carries an OSM `addr:city` tag and no administrative
boundary layer is included.

Full discussion: `FINAL_REPORT.md`.

## Known issues

- Step 6 skips any scene whose output already exists in `data/interim/s1_tc/` (it checks the
  filename only, not the parameters). Delete that folder after changing the bbox, EPSG or
  spacing, or to force a rerun. Set `GPT=<path to gpt.exe>` if SNAP is not on PATH.
- `flood_detect_v2.py` prints `Error in sys.excepthook` three times at exit; the masks are
  written and the pipeline continues.
- `fetch_sentinel1.py` shows `pol=?` because it reads the wrong attribute name (cosmetic).

## Tests

```
python -m pytest tests/ -q
```

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md). Code: MIT. Data: own licenses.

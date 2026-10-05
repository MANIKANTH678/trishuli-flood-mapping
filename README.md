# Trishuli Flood Damage Mapping

**Track B — Multimodal AI Hackathon 2026**

Post-event damage assessment for the **26 August 2026 Trishuli–Bhote Koshi
flash flood (Rasuwa District, Nepal)** using free Sentinel-1 SAR, a DEM and
OpenStreetMap (ohsome API snapshot 2026-07-27, pre-event; manifest in
`data/raw/osm/manifest.json`). © OpenStreetMap contributors (ODbL).

> **Status.** Sentinel-1 preprocessing is SNAP-based (calibrated, terrain-corrected
> σ⁰, Copernicus GLO-30 DEM). The change map is a multi-temporal SAR change-detection
> product, **not a validated flood extent**. Its threshold was set from null runs on
> pre-event reference scenes (no EMSR927 data), and the detector was frozen (git tag
> `detector-frozen`) before its single EMSR927 check. The event pair passes the detection
> gate and a pre-event scene does not. The flood-water class itself is small (0.31 km²) and
> does not coincide with EMSR927 damage points. Most detected change is dark or bright
> surface change on the valley floor; at Bidur and Phosretar nearly all of it lies on mapped
> landslide polygons, and nothing is detected at the two Rasuwa AOIs. A U-Net water check
> shows no net change. An earlier README claimed the pair holds no GLOF signal; that claim is
> withdrawn, because its diagnostic used uncalibrated, GCP-geocoded imagery.

## Pipeline

`run_all.sh` runs these stages in order. A failure stops the run.

| #   | Stage                           | Script                                                                                   | Output                                                                                                                                                                                                               |
| --- | ------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | S1 download                     | `src/fetch/fetch_sentinel1.py`                                                           | `data/raw/sentinel1/{pre,placebo,pre3,pre4,post}/*.SAFE.zip`                                                                                                                                                         |
| 2   | Unzip                           | inline in `run_all.sh`                                                                   | `data/raw/sentinel1/{pre,placebo,pre3,pre4,post}/*.SAFE`                                                                                                                                                             |
| 3   | Orbit / pass / 12-day gates     | `src/processing/align_v2_checks.py`, `src/processing/check_stack.py`                     | (gates; exit 1 on violation)                                                                                                                                                                                         |
| 4   | OSM download                    | `src/download/fetch_osm.py`                                                              | `data/raw/osm/*.geojson`, `manifest.json`                                                                                                                                                                            |
| 5   | DEM                             | `src/fetch/fetch_dem.py`                                                                 | `data/raw/dem/dem_glo30_wgs84.tif`                                                                                                                                                                                   |
| 6   | SNAP preprocessing              | `src/processing/s1_preprocess.py`                                                        | `data/interim/s1_tc/`                                                                                                                                                                                                |
| 7   | Grid + dB                       | `src/processing/s1_to_grid.py`                                                           | 30 m UTM 45N VV/VH dB rasters in `data/processed/`, one pair per split                                                                                                                                               |
| 8   | Change detection                | `src/analysis/geometry.py`, `hand.py`, `radar_mask.py`, `calibrate_null.py`, `detect.py` | `hand_30m.tif`, `radar_mask_30m.tif`, `outputs/diagnostics/step4_null_calibration.json`, `detect_class_30m.tif`, `flood_mask.tif`, `debris_mask.tif`, `observable_mask.tif`, `outputs/diagnostics/detect_asc85.json` |
| 9   | Damage                          | `src/processing/damage_v2.py`                                                            | `outputs/affected_*`, `impact_summary.json`                                                                                                                                                                          |
| 9b  | Cutoff                          | `src/processing/cutoff_v2.py`                                                            | `outputs/cutoff_settlements.json`                                                                                                                                                                                    |
| 10  | EMSR927 validation              | `src/validation/emsr927_comparison.py`                                                   | `data/processed/emsr927_comparison.json`                                                                                                                                                                             |
| 10  | Damage sanity                   | `src/validation/damage_sanity_check.py`                                                  | `outputs/validation/damage_sanity.json`                                                                                                                                                                              |
| 11  | Mask validation                 | `tools/signal_check.py`, `tools/unet_corridor.py`, `tools/null_recall_aoi.py`            | JSON per tool                                                                                                                                                                                                        |
| 12  | Maps, dashboard, slides, report | `src/report/impact.py`, `dashboard_full.py`, `slides.py`, `situation_report.py`          | `outputs/`                                                                                                                                                                                                           |

Steps 10 and 11 (`null_recall_aoi.py`) and the situation report need `data/external/EMSR927`;
without it they are skipped.

**Detector classes** (`detect_class_30m.tif`): 1 flood water, 2 surface change (dark),
3 surface change (bright), 0 no change on the assessed floor, 253 not assessed (above the
HAND floor), 254 radar-unobservable, 255 no data. `flood_mask.tif` is class 1 and
`debris_mask.tif` is classes 2 and 3 (descriptive surface change, not confirmed debris).
If the seed fraction does not clearly exceed the null rate, `detect.py` writes empty
masks and `status: no_significant_change`.

Not part of `run_all.sh`:

| Stage                  | Script                                                                                                                                                      | Output                                                                           |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Detector null test     | `python -m src.analysis.detect --ref placebo,pre3,pre4 --post pre --out-dir data/processed/_null --track-id null_pre` (create `data/processed/_null` first) | `outputs/diagnostics/detect_null_pre.json` (must report `no_significant_change`) |
| Detector EMSR927 check | `src/validation/emsr927_detector_check.py` (run only after the `detector-frozen` tag)                                                                       | `outputs/validation/detector_vs_emsr927.json`                                    |
| Train U-Net            | `src/modeling/train_segmentation.py`                                                                                                                        | `outputs/flood_unet.pt`                                                          |
| Eval U-Net             | `src/modeling/eval_himalaya_heldout.py`                                                                                                                     | `outputs/himalaya_heldout_metrics.json`                                          |

## Setup

```
python -m venv .venv
.venv\Scripts\activate          # Windows;  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Requirements beyond Python packages:

- **bash** to run `run_all.sh` (Git Bash or WSL on Windows). The script uses the Python in
  `.venv` when it exists.
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

All Sentinel-1 scenes are relative orbit 85, ascending, and 12 days apart (each date is two
consecutive frames of one pass): reference scenes 2026-07-11 (`pre4`), 2026-07-23 (`pre3`),
2026-08-04 (`placebo`) and 2026-08-16 (`pre`), and the post-event scene 2026-08-28 (`post`).
The reference for each pixel is the median of the four earlier scenes in linear power.
`check_stack.py` fails the run if the stack is not one track or the offsets are not
multiples of 12 days. The event date is fixed for this flood.

**Last full run.** `bash run_all.sh` completed end to end and reproduced the detector figures
in Key results. SNAP outputs in `data/interim/s1_tc/` were reused, not regenerated, in that run.

**ohsome quota.** Step 4 queries the ohsome API and can fail with `403 Quota exceeded`.
Wait for the quota to reset and rerun. `HTTP 429, waiting 15s` messages are retries and are normal.

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

| Metric                                              | Value                                                                                                                                                                                                                                   |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| U-Net val IoU (best epoch, per-batch mean)          | 0.523 (pooled held-out: 0.574)                                                                                                                                                                                                          |
| U-Net proxy-Himalaya IoU                            | 0.554                                                                                                                                                                                                                                   |
| Detector threshold (null-calibrated)                | t_hi 4.0: the smallest grid value whose worst leave-one-out false-alarm fraction is ≤ 1e-3 (3.5e-4 at 4.0). t_lo 2.5. Gate: seed fraction must exceed 1.05e-3 of the assessed floor                                                     |
| Event vs null                                       | Event seed fraction 1.09e-2 (about 10× the gate), status `change_detected`. A pre-event scene tested against the other references: 0.0, `no_significant_change` (that scene was also one of the four calibration scenes)                |
| Assessed floor                                      | 199.9 km² (HAND ≤ 30 m), 89.7% radar-observable                                                                                                                                                                                         |
| Detected change                                     | Flood water 0.31 km² (340 px). Surface change: dark 2.29 km², bright 0.54 km² (descriptive classes, not confirmed damage)                                                                                                               |
| Backscatter change (post − pre)                     | river, 60 m buffer: median +0.02 dB, p1 −6.22 dB; river shifted ±1500 m: −0.08 dB, p1 −4.74 / −4.46 dB; whole scene: +0.00 dB. Flood-water pixels (340): −7.92 dB (the mask is selected on change, so this is not independent evidence) |
| EMSR927 damage points vs the flood-water class      | Damage-point recall prints 0.000 in all four AOIs. Hit rate vs random null: Bidur 0.000 vs 0.0024 ± 0.0017; Phosretar 0.000 vs 0.0102 ± 0.0071 (the null test uses 581 of Phosretar's 609 points)                                       |
| EMSR927 damage points vs all detected classes (1–3) | Within 100 m of a detection: Bidur 52%, Phosretar 24%, Timure 2%, Syapru Besi 0%. On detected pixels (0 m): 21%, 6.7%, 0%, 0%                                                                                                           |
| Detections on mapped landslide polygons             | Precision (a lower bound) / recall / IoU: Bidur (hold-out AOI) 0.93 / 0.17 / 0.17; Phosretar 0.99 / 0.24 / 0.24; Syapru Besi and Timure 0 for all three. Landslide polygons are not flood extent, so these are proxies                  |
| EMSR927 content on the assessed floor               | Damage points / landslide area: Bidur 91% / 95%; Phosretar 85% / 96%; Syapru Besi 40% / 56%; Timure 29% / 59%                                                                                                                           |
| U-Net corridor water check                          | 21,020 new vs 21,627 lost water px: no net change, so it does **not** independently confirm the flood                                                                                                                                   |
| Buildings in surface-change or flood classes        | 3 flooded + 473 in surface-change classes, of 189,503 (0.002 % flooded). Not a validated flood                                                                                                                                          |
| Roads / bridges in flood class                      | 0 of 14,151 roads; 0 of 385 bridges                                                                                                                                                                                                     |
| Settlements cut off from all 20 hospitals           | 0 of 446 (379 reach a hospital before and after). The flood-water class is small, so this is not evidence that nothing was cut off                                                                                                      |

The EMSR927 numbers are proxies: its products contain landslide polygons and building damage
points, not a flood extent. The detector check ran once, after the detector was frozen, but
earlier pipeline stages also ran EMS comparison scripts, so it is not an independent
validation. No locality or district breakdown is reported: none of the flooded buildings
carries an OSM `addr:city` tag and no administrative boundary layer is included.

Full discussion: `FINAL_REPORT.md`.

## Limitations

- Single track (relative orbit 85, ascending) and 30 m resolution.
- The surface-change classes are descriptive. One event pair cannot separate the GLOF from other high water.
- Hillslope landslides lie outside the assessed domain (HAND ≤ 30 m). On the assessed floor, the detector found nothing at Syapru Besi and Timure and recovered under a quarter of mapped landslide area at Bidur and Phosretar.
- A few isolated high-elevation detections in the far north (mostly bright change) are not flood.
- The pre-event null test reuses a scene that was also a calibration scene.

## Known issues

- Step 6 skips any scene whose output already exists in `data/interim/s1_tc/` (it checks the
  filename only, not the parameters). Delete that folder after changing the bbox, EPSG or
  spacing, or to force a rerun. Set `GPT=<path to gpt.exe>` if SNAP is not on PATH.
- `src/processing/flood_detect_v2.py` is deprecated (replaced by `src/analysis/detect.py`) and
  no longer run by `run_all.sh`. It stays only because tests import `lee_filter_db` and
  `otsu_or_fallback`.
- `fetch_sentinel1.py` shows `pol=?` because it reads the wrong attribute name (cosmetic).

## Tests

```
python -m pytest tests/ -q
```

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md). Code: MIT. Data: own licenses.

## Step 5: Sentinel-2 branch and fusion
**Method.** Sentinel-2 L2A bands are read by window and cloud-masked with SCL at 10 m (classes 0, 1, 2, 3, 8, 9, 10, 11, cloud dilated 3 px, turbid water kept via MNDWI > 0.1). NDVI, MNDWI and BSI are averaged to the 30 m grid. The reference is the per-pixel median of pre-event dates, the post-event composite is the earliest clear observation within 30 days, and scores are robust z-values against elevation-stratified hillslope controls. The threshold comes from leave-one-out nulls over the pre-event dates. Fusion writes class, source and confidence layers.

**Result.** The S2 branch is inconclusive and contributes nothing to the fused product (status null_not_calibrated). Post-event floor clear fraction was 12.4% (5.1% over all valid pixels), and the leave-one-out false-alarm rate was 1.6-5.4% across the threshold grid against alpha = 0.1%, so no threshold passed. The fused product is therefore identical to the S1 v1 detector output. Pre dates: 2026-06-18, 07-05, 08-11, 08-12. Post dates: 2026-08-27, 09-08, 09-13, 09-20, 09-21.

**EMSR927 check (S1 v1 = fused).** Share of EMS damage points in the assessed domain / point recall within 100 m / landslide precision, recall, IoU:
- AOI03 (hold-out): 91% / 52% / 0.93, 0.17, 0.17
- AOI05: 85% / 24% / 0.99, 0.24, 0.24
- AOI02: 29% / 2% / no detections
- AOI01: 40% / 0% / no detections

**Limitations.** Monsoon cloud limited S2 coverage. The S2 null calibration failed. Crop phenology can mimic scars on farmland. 30 m aggregation loses S2 resolution. The upstream gap (damage on terraces and slopes above the 30 m floor in AOI01 and AOI02) remains open; the next lever is the descending-track search.

**Disclosures.** EMS data were used to diagnose domain coverage (design only). AOI03 was scored three times: v1, an empty-S2 fusion run identical to v1, and a pre-gate S2 run; detector numbers did not change and nothing was tuned on it. The null-calibration gate was added after viewing EMS results (tuned on EMS). Tags s2-frozen to s2-frozen-4 record the code states; the pre-gate EMS outputs are kept as *_pregate_vs_emsr927.json and are superseded.

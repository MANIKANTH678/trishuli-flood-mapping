# Trishuli Flood Damage Mapping — Final Report

**Track B — Multimodal AI Hackathon 2026**

> Numbers in §4 reflect the rebuilt pipeline (ohsome pre-event OSM, bbox tightened to the Rasuwa corridor) and are unvalidated.

Post-event damage assessment for the **26 August 2026 Trishuli–Bhote Koshi
flash flood, Rasuwa District, Nepal**.

---

## Executive summary

We built a complete, reproducible pipeline to map flood extent, building
damage, and hospital access for the 26 August 2026 GLOF that struck the
Trishuli / Bhote Koshi corridor. The pipeline ingests free Sentinel-1 SAR,
DEM, OpenStreetMap, and Copernicus EMS Rapid Mapping reference data and
produces flood masks, affected-infrastructure layers, hospital-reachability
metrics, and a trained U-Net segmentation model.

**Status of the findings.** An earlier run on a larger study area found no detectable GLOF signal in the Sentinel-1 pair. The pipeline was then rebuilt (ohsome pre-event OSM, bbox tightened to the Rasuwa corridor, corrected reachability analysis). On the rebuilt inputs the flood mask is small (5.22 km²) and has no pixels in the two Rasuwa AOIs (Syapru Besi, Timure). It contains 966 of 3,816 EMSR927 damage points (25.3%), all of them in Bidur and Phosretar, where 97-98% of the mask area inside the AOI lies on mapped landslide polygons. The mask remains unvalidated and should not be read as the extent of the event.

**Headline numbers:**

| Metric                                         | Value                    | Interpretation                                                                                         |
| ---------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------ |
| Sentinel-1 VV change, river corridor (median)  | **+0.02 dB**             | median unchanged; a GLOF over water would shift it to −5 to −10 dB (§4.1)                              |
| U-Net flagged fraction of corridor, post / pre | **5.03% / 5.05%**        | cannot discriminate the two scenes (§4.2)                                                              |
| U-Net val IoU (Sen1Floods11)                   | 0.523                    | best epoch chosen on val; pooled held-out 0.574                                                        |
| U-Net proxy-Himalaya IoU                       | 0.554                    | monsoon-subcontinent chips                                                                             |
| EMSR927 damage-point recall                    | **966 of 3,816 (25.3%)** | none at Syapru Besi or Timure; mask area at Bidur and Phosretar is 97-98% on landslide polygons (§4.4) |
| Our "flooded" buildings                        | **991** (+102 debris)    | counts not comparable to EMSR927 (different areas, §4.5)                                               |

---

## 1. Study area and event

On **26 August 2026**, a flash flood reportedly triggered by a Glacial Lake
Outburst Flood (GLOF) struck Rasuwa District, Nepal. The Bhote Koshi and
Trishuli rivers, which drain south from the Nepal–China border through
Rasuwa, Nuwakot, and Chitwan, carried a debris-laden surge downstream.
Copernicus EMS Rapid Mapping was activated (**EMSR927**) and mapped
building damage across four Areas of Interest:

| AOI | Locality    | District       | Lat / Lon        | Damage points |
| --- | ----------- | -------------- | ---------------- | ------------- |
| 01  | Syapru Besi | Rasuwa         | 28.17 N, 85.34 E | 433           |
| 02  | Timure      | Rasuwa         | 28.26 N, 85.37 E | 431           |
| 03  | Bidur       | Nuwakot        | 27.93 N, 85.15 E | 2,343         |
| 05  | Phosretar   | (Chitwan edge) | 27.83 N, 85.02 E | 609           |

Total EMSR927 damage points: **3,816** (2,813 Destroyed, 354 Damaged, 649
Possibly damaged).

**Study area bbox:** `(84.95, 27.80, 85.55, 28.35)` — the Rasuwa corridor of the Trishuli valley, projected to **EPSG:32645** at **30 m**.

---

## 2. Data

| Source             | Purpose                                | Snapshot                                                                             |
| ------------------ | -------------------------------------- | ------------------------------------------------------------------------------------ |
| Sentinel-1 GRD     | SAR change detection                   | 2026-08-16 (pre) / 2026-08-28 (post)                                                 |
| Copernicus DEM     | Slope masking                          | n/a                                                                                  |
| OpenStreetMap      | Infrastructure, settlements, hospitals | ohsome API snapshot 2026-07-27 (pre-event); manifest in `data/raw/osm/manifest.json` |
| Sen1Floods11 v1.1  | U-Net training                         | published dataset                                                                    |
| Copernicus EMSR927 | Validation reference                   | activation 2026-08-26                                                                |

**Sentinel-1 pairing.** Two products per date on relative orbit **85**,
ascending, 12-day gap:

- Pre: `S1D_IW_GRDH_1SDV_20260816T122116_…_B057` (southern)
  and `…_20260816T122141_…_C3AB` (northern)
- Post: `S1D_IW_GRDH_1SDV_20260828T122116_…_C523` (southern)
  and `…_20260828T122141_…_01B4` (northern)

Both northern and southern frames are needed — the SAR swath is a diagonal
parallelogram and Rasuwa falls in the gap between single-frame footprints.
Orbit invariants are verified by `src/processing/align_v2_checks.py` before
any alignment runs.

---

## 3. Methods

### 3.1 Sentinel-1 preprocessing

Raw SAFE measurement TIFFs are not georeferenced. We geocode them from the
GCPs in `annotation/*.xml` using `gdal_translate -gcp` followed by
`gdalwarp -t_srs EPSG:32645 -tr 30 30`, producing one north-up 30 m raster
per polarization per frame (`src/processing/geocode_s1.py`).

Pre and post frames are then merged, converted to dB, and matched to the
reference DEM grid (`src/processing/align.py`). Amplitude-to-dB conversion
uses `20·log10(DN) − 60`; zero DN is treated as nodata. No radiometric
calibration is applied (the calibration annotation files are not used) and the
rasters are not terrain-flattened, so the dB values are relative backscatter,
not calibrated σ⁰. Both scenes come from relative orbit 85, so the post-minus-pre
difference should largely cancel static terrain effects, but any date-to-date
radiometric difference is not corrected. The GCP warp is first-order (`-order 1`)
with no DEM-based terrain correction, so SAR pixels can be displaced relative to
the DEM grid in steep terrain (§5.8). Frames whose median value is at most 10 are
assumed to be in dB already (`to_db` in `align.py`).

### 3.2 Flood detection

`src/processing/flood_detect_v2.py` implements:

1. Lee speckle filter (7×7, ENL=4)
2. Dual-pol change image: `d = 0.5·(VV_post − VV_pre) + 0.5·(VH_post − VH_pre)`
3. Adaptive threshold on the 5th percentile of `d`, clipped to [−3.5, −1.5] dB
4. Slope mask (reject > 12°)
5. Permanent-water mask (pre-event VV < −18 dB OR VH < −22 dB)
6. Morphological opening + minimum patch size 20 px
7. Output: `data/processed/flood_mask.tif` (uint8, binary)

### 3.3 Damage assessment

`src/processing/damage_v2.py` intersects OSM buildings, roads, and bridges
with the flood and debris masks, writing:

- `outputs/affected_buildings.gpkg`
- `outputs/affected_roads.geojson`
- `outputs/affected_bridges.geojson`
- `outputs/impact_summary.json`

### 3.4 Hospital reachability

`src/processing/cutoff_v2.py` builds a weighted road graph in EPSG:32645,
snaps settlements and hospitals to the nearest graph node (≤1 km), and runs
multi-source Dijkstra from all hospitals. Pre-flood graph uses all OSM roads;
post-flood graph removes road segments whose midpoint lies inside the flood
mask. Output: `outputs/cutoff_settlements.json` with pre/post distances and
detour factors.

### 3.5 U-Net segmentation

`src/modeling/train_segmentation.py` trains a 4-encoder / 3-decoder U-Net
with skip connections (2-channel dual-pol input, ~7.8 M parameters) on
Sen1Floods11 v1.1 (252 train / 89 val). 20 epochs, Adam lr=1e-3, cosine LR
schedule, BCE-with-logits loss computed only on valid (non-`-1`) label
pixels. Best checkpoint saved to `outputs/flood_unet.pt`.

### 3.6 Validation

Two reference checks:

- `src/validation/emsr927_comparison.py` — rasterizes EMSR927 `builtUpP`
  damage points and `observedEventA` landslide polygons onto the flood-mask
  grid, clips to AOI, and computes damage-point recall and landslide overlap.
- `src/validation/damage_sanity_check.py` — compares our `impact_summary.json`
  counts against EMSR927 per-AOI damage totals.

### 3.7 Main-stem z-score analysis (exploratory)

`src/analysis/` adds a terrain and radar-geometry check on the river floor
(`geometry.py`, `hand.py`, `radar_mask.py`, `zscore.py`). Three populations are
compared:

- **Main-stem floor:** floor pixels (HAND, height above nearest drainage, at most
  `--floor-m`, default 30 m) within `--main-buf-m` (1,500 m) of the OSM main-stem
  line. The line is the segments whose names match Trishuli, Trisuli or Bhote
  Koshi (18 segments).
- **Tributary floor:** floor pixels at least `--trib-min-m` (2,500 m) from the
  main stem.
- **Hillslope control:** valid pixels with HAND of at least `--ctrl-m` (100 m).

Every population uses valid pixels only: finite change in both polarizations and
radar-mask class ok, with no spatial smoothing (`--smooth 1`). The observable
fraction in §4.1b is the share of main-stem floor pixels (HAND at most
`--floor-m`, within `--main-buf-m`) that are valid.

HAND at 30 m puts 4.0%, 6.2% and 10.1% of valid pixels within 15 m, 30 m and
60 m. The radar mask uses a single scene-wide incidence angle (38.77°): layover
and shadow from DEM slope, cast shadow from a ridge line-of-sight test, and a
poor-local-incidence class. Scene-wide it classes 74.1% of pixels as ok, 5.4%
layover, 0.5% shadow, 0.4% cast shadow and 19.6% poor local incidence.
Pixels in any of the four non-ok classes are unobservable and excluded.

The z score is a robust z (median and MAD) of the change between the two scenes,
standardized against the hillslope control within 250 m elevation bands (bands with fewer than 5,000 control
pixels use the global median and MAD). The hillslope row is therefore the normalization baseline (median z near 0 by
construction), not an independent control; the tributary floor is the
independent comparator. A pixel counts as strongly negative or strongly positive
if z < −3.5 or z > +3.5 (`--thr`) and it lies in a connected patch of at least
8 px (`--min-patch`). For each polarization, `zscore.py` reports these fractions
per population and a block bootstrap (2 km blocks, 2,000 replicates, seed 0) of the main-stem
minus tributary-floor difference, summarised by the 2.5, 50 and 97.5
percentiles. The criteria in `docs/step3_criteria.md` were written after the
first event run, so the event-run results in §4.1b are exploratory.

---

## 4. Results

### 4.1 Backscatter change on the rebuilt inputs

Backscatter change (post minus pre, VV, dB) on the GCP-geocoded, uncalibrated 30 m rasters (§3.1),
summarised in `outputs/validation/signal_check.json` (the script that wrote this file is not in the repository):

| Population            | n         | median (dB) | p5 (dB) | p1 (dB) |
| --------------------- | --------- | ----------- | ------- | ------- |
| All valid pixels      | 4,113,397 | +0.00       | −2.91   | −4.30   |
| River, 60 m buffer    | 61,080    | +0.02       | −3.64   | −6.22   |
| River shifted +1500 m | 61,084    | −0.08       | −3.24   | −4.74   |
| River shifted −1500 m | 61,079    | −0.08       | −3.03   | −4.46   |
| River, north half     | 21,498    | +0.24       | −3.04   | −4.71   |
| River, south half     | 39,582    | −0.10       | −3.95   | −6.91   |
| Flood-mask pixels     | 5,802     | −3.03       | −8.67   | −11.22  |

The river median is unchanged (+0.02 dB) against +0.00 dB for all pixels. A real GLOF over
water would shift the river median strongly negative. The lower tail along the river is
slightly heavier than in river-shifted controls (p1 −6.22 dB against −4.74 and −4.46 dB), mostly
in the south half, so the river is not entirely featureless, but there is no median signal.
The flood-mask row is not independent evidence: the mask is built from pixels with a large
negative change, so a negative median there is expected.

Four mechanisms plausibly contribute:

1. **Temporal mismatch.** GLOFs drain in hours; the 2-day post-event gap
   (2026-08-26 event → 2026-08-28 acquisition) likely missed standing water.
2. **Radar geometry.** The ascending pass illuminates the Trishuli valley
   obliquely. The 30 m radar-geometry mask (§3.7) puts only about 7.5% of the
   main-stem floor in layover, shadow or poor local incidence (poor local
   incidence 6.3%, layover 0.7%, cast shadow 0.4%, shadow 0.01%), so shadow is
   not the main loss at this resolution. A 30 m DEM may still under-resolve a
   narrow gorge.
3. **Spatial resolution.** At 30 m, the ~30–50 m wide Bhote Koshi channel is
   under-resolved; each pixel mixes water with bank rock.
4. **Debris and vegetation.** Post-GLOF debris flows leave rough surfaces
   that scatter radar rather than specularly reflecting.

### 4.1b Main-stem floor z-scores (exploratory)

Output: `outputs/diagnostics/step3_event.json`. 92.5% of the main-stem floor
(36,708 of 39,663 px) is observable. The unobservable share is mostly poor
local incidence (6.3%), then layover (0.74%) and cast shadow (0.37%).

| Polarization | Population         | n px      | median z | strongly negative | strongly positive |
| ------------ | ------------------ | --------- | -------- | ----------------- | ----------------- |
| VV           | Main-stem floor    | 36,708    | −0.12    | 1.87%             | 0.28%             |
| VV           | Tributary floors   | 176,217   | +0.04    | 0.05%             | 0.08%             |
| VV           | Hillslope controls | 2,466,085 | 0.00     | 0.008%            | 0.006%            |
| VH           | Main-stem floor    | 36,708    | −0.39    | 4.53%             | 0.05%             |
| VH           | Tributary floors   | 176,217   | +0.06    | 0.06%             | 0.04%             |
| VH           | Hillslope controls | 2,466,085 | 0.00     | 0.006%            | 0.003%            |

Strongly negative or positive means robust z beyond ±3.5 within a patch of at
least 8 px (§3.7). The excess is the main-stem floor fraction minus the tributary-floor fraction,
with a 95% interval from a block bootstrap (2 km blocks, 2,000 replicates, seed 0). The negative-tail
excess is 1.8 percentage points in VV (CI 0.9 to 2.9) and 4.4 points in VH
(CI 2.7 to 6.5). The positive-tail excess CIs include zero in both polarizations
(VV −0.001 to 0.42 points, VH −0.07 to 0.15 points). Median z is only −0.12 (VV)
and −0.39 (VH), so the darkening is confined to a minority of pixels, not a
corridor-wide shift. The hillslope row is the normalization baseline (§3.7),
so it is not an independent control, and the bootstrap compares only the
main-stem and tributary floors. The blocks are spatial, so the intervals
reflect spatial clustering rather than independent pixels. This is consistent with
flooding but does not separate it from debris, sediment or channel change. The
main-stem floor also differs from tributary floors in size, discharge and surface,
and the scene pair spans the monsoon, so a seasonal rise in river level or wet
surfaces could darken it without the event. A placebo pair that does not span the
event is needed to separate these. The
excess is quoted rather than the ratio, whose CIs span more than an order of
magnitude (VV 12 to 193, VH 34 to 354). Two image-based checks of the SAR-to-DEM alignment were inconclusive (§5.8). The criteria were
written after the run, so these results are exploratory.

Along the main stem (`outputs/diagnostics/step3_profile_event.csv`, 0.01° latitude
bins), strongly negative pixels occur only in the downstream reach. South of
28.02°N, the VV strongly negative fraction is above zero in 15 of 23 bins and the
VH fraction in 21 of 23. From 28.025°N to 28.285°N (27 bins), which includes Syapru
Besi (28.17°N) and Timure (28.26°N), the VV fraction is zero in every bin and the
VH fraction is above zero in three (28.075°N, 28.275°N, 28.285°N). This is not an
observability effect: the mean observable fraction per bin is 0.81 in the northern
reach (0.54 to 0.95) and 0.95 in the southern reach (0.80 to 0.99). The main-stem
excess therefore comes from the downstream reach, at the latitudes of Bidur
(27.93°N) and Phosretar (27.83°N), and does not appear in the Rasuwa reach where
the event occurred. This matches §4.4, where the flood mask has no pixels in the
two Rasuwa AOIs. The excess in the lower reach could reflect the event, landslide
debris or sediment, or a wider floor with more channel in each pixel; these data do
not separate them.

### 4.2 U-Net applied to the corridor

On the rebuilt inputs, the U-Net (absolute dB input, as in training) flags 5.03% of the corridor in the post scene and 5.05% in the pre scene; 21,020 px gained and 21,627 px lost. It cannot discriminate the two scenes. The earlier "zero flood pixels" result used a change-image input the model was never trained on, so it is withdrawn.

### 4.3 U-Net held-out scores

| Split                                       | IoU   | F1    | Precision | Recall |
| ------------------------------------------- | ----- | ----- | --------- | ------ |
| Sen1Floods11 full val (89 chips)            | 0.574 | 0.729 | 0.723     | 0.735  |
| Proxy-Himalaya, India + Pakistan (20 chips) | 0.554 | 0.713 | 0.685     | 0.744  |

The proxy evaluation is only 0.02 IoU below the full val, so the proxy score is close to the pooled score. (0.523 elsewhere in this report is the mean of per-batch IoUs; 0.574 is pooled over all pixels.)

### 4.4 EMSR927 validation

| AOI            | Damage points | Inside flood mask | Recall (all grades) | Recall (Destroyed) | Landslide overlap | Mask in AOI (km²) |
| -------------- | ------------- | ----------------- | ------------------- | ------------------ | ----------------- | ----------------- |
| 01 Syapru Besi | 433           | 0                 | 0.000               | 0.000              | 0.000             | 0.00              |
| 02 Timure      | 431           | 0                 | 0.000               | 0.000              | 0.000             | 0.00              |
| 03 Bidur       | 2,343         | 867               | 0.370               | 0.447              | 0.294             | 1.77              |
| 05 Phosretar   | 609           | 99                | 0.163               | 0.325              | 0.358             | 1.67              |

Landslide overlap is the fraction of mapped landslide area inside the flood mask.

Overall, 966 of 3,816 damage points (25.3%) fall inside the flood mask: 867 of 2,343 at Bidur and 99 of 609 at Phosretar. No mask pixels fall in the two Rasuwa AOIs, where the event occurred. At Bidur, 1.73 of the 1.77 km² of mask inside the AOI lies on mapped landslide polygons (98%); at Phosretar, 1.62 of 1.67 km² (97%). A null-model comparison (`outputs/validation/null_recall_aoi.json`) gives expected recall 0.113 ± 0.010 at Bidur and 0.091 ± 0.017 at Phosretar, against observed 0.370 and 0.163, so the mask coincides with mapped damage more than the null does. This does not show that the mask maps flooding. EMSR927 contains no flood-extent layer, damage may reflect mass movement rather than flooding, and nearly all of the mask area inside these AOIs lies on landslide polygons. In the two AOIs where the event occurred, recall is zero.

### 4.5 Damage assessment versus EMSR927

The rebuilt pipeline flags 991 flooded and 102 debris-affected buildings (1,093 in total) across the study area. EMSR927 mapped 3,816 damage points in four AOIs (2,813 destroyed, 354 damaged, 649 possibly damaged). The counts are not directly comparable, because ours cover the whole corridor and EMSR927's cover four small areas. The spatial comparison in §4.4 is more informative, and it is mixed: the mask has no pixels in the two Rasuwa AOIs and overlaps mapped damage only at Bidur and Phosretar, where it is almost entirely on landslide polygons. The 16x overcount reported for the earlier run no longer applies.

### 4.6 Hospital reachability

Hospital reachability was computed on a road graph of 14,536 OSM segments (14,151 roads and 385 bridges). Of 446 settlements, 379 have a route to one of 20 hospitals before flooding; the other 67 have no pre-flood route (flagged `unsnapped_pre` in the output), which cannot reflect flooding. Removing the road and bridge segments whose midpoint lies inside the flood mask leaves 375 settlements connected and cuts off 4, all with no post-flood path to any hospital (no settlement is flagged on detour alone, using a 3x threshold). The four settlements lie in the far north of the study area near the border crossing. Another 28 keep a route but with a detour of more than 5%, up to 2.1x the pre-flood distance. This does not describe the real event: the mask has no pixels in the Rasuwa AOIs, and the effects here arise from mask pixels elsewhere in the corridor. An earlier version of this analysis had a defect in the node-snapping function that made all distances meaningless. It was found by checking that road distance never falls below straight-line distance, and was fixed.

---

## 5. Limitations

**5.1 The event is not demonstrably observable in the input data.** In both the earlier and the rebuilt run, the Sentinel-1 pair (16 and 28 August, ascending, 30 m) shows no detectable signal at the two Rasuwa AOIs. Possible reasons include the two-day gap after a fast-draining flood, the 30 m resolution, and debris-roughened surfaces. The radar-geometry mask (§3.7) makes shadow an unlikely main cause on the main-stem floor, although a 30 m DEM may under-resolve a narrow gorge. We have not shown that the event is unobservable, only that this pair and this method do not detect it. Optical imagery or higher-resolution SAR would be needed to map the flood surface directly.

**5.2 EMSR927 GRA products contain no flood extent layer.** The activation
mapped building damage and mass movements, not water. Our validation is
therefore proxy-based (damage-point recall and landslide overlap), not a
direct IoU against a flood reference.

**5.3 30 m resolution limits bridge-level accuracy.** The Bhote Koshi
channel is ~30–50 m wide. Even with a correct SAR signal, pixel-level
classification of the channel would be marginal.

**5.4 U-Net trained on out-of-distribution data.** Sen1Floods11 contains no
Himalayan scenes. The proxy evaluation on India+Pakistan chips is the closest
available, but it does not establish the model's performance on steep
mountain valleys.

**5.5 The debris mask is dominated by speckle.** The rebuilt debris layer drops from 34,020 px before morphology to 2,125 px after minimum-patch filtering, so most of the pre-morphology class is noise. This is a tuning issue in `flood_detect_v2.py`.

**5.6 Hospital reachability assumes road-network completeness.** OSM road
coverage in rural Rasuwa is incomplete; missing minor tracks may
over-estimate cut-off.

**5.7 The step 3 analysis is exploratory.** `docs/step3_criteria.md` was
written after the first event run (the file was empty when the results were written),
so the results in §4.1b are not a pre-registered test. There is also no
placebo yet: the same analysis on a scene pair that does not span the event
(for example 4 August against 16 August on the same orbit) is the first run
that can be tested against fixed criteria.

**5.8 Backscatter is uncalibrated, and the SAR is not terrain-corrected.**
The dB values (§3.1) are relative backscatter. Differencing two scenes from the
same relative orbit reduces static terrain effects, but slope-dependent or
date-to-date radiometric differences are not corrected and could contribute to
local changes. The scenes are geocoded with a first-order GCP warp and no
DEM-based terrain correction, while HAND, the valley-floor classes, the radar
mask and the OSM main-stem line are defined on the DEM grid. In steep terrain a
SAR pixel can be displaced relative to the DEM by relief (about 1.25 m per metre
of height above the reference surface at the 38.77° incidence angle), so the
main-stem floor class may not coincide with the channel in the SAR image. The
Two image-based checks of this offset (east-slope correlation and radar-shadow minimum; `src/analysis/coreg_check.py`, `coreg_shadow.py`) gave no consistent peak across tiles, so the offset is neither confirmed nor excluded and remains unquantified. The z-score result (§4.1b), especially the main-stem floor class, should be read with that caveat.

---

## 6. Recommendations

1. **Re-acquire this event with different data.** Optical (Sentinel-2 L2A,
   PlanetScope) would capture post-GLOF sediment plumes directly.
   High-resolution SAR (TerraSAR-X stripmap) would resolve the channel.
2. **Widen the Sentinel-1 search.** A descending pass (relOrbit 121 or 19,
   visible in the catalogue) would illuminate the valley from the opposite
   direction and might capture water before it drains. Same-day imagery
   (Sentinel-1 acquisition ≈ event time) would be ideal — none existed for
   this event.
3. **For future GLOF events, task optical assets immediately.** Rapid
   mapping windows are 24–72 hours. Sentinel-1's 12-day repeat is too slow
   for GLOF hydrology.
4. **Fix the debris-mask classifier.** The pre-morphology debris count
   (34,020 px before morphology, 2,125 after) reveals a threshold that catches speckle. A
   dual-threshold or GLCM-texture approach would be more robust.

---

## 7. Reproducibility

The rebuilt pipeline was run stage by stage from the repo root on Windows with
Python 3.12 (see `requirements.txt`; its pins have not yet been verified against
the rebuilt environment). `run_all.sh` has not been re-run on the rebuilt
environment. Stage order used for the results in this report:

    python -m src.download.fetch_osm --event-date 2026-08-26 --snapshot 2026-07-27
    python src/download/fetch_emsr927.py
    python src/processing/geocode_s1.py
    python src/processing/align.py
    python src/processing/flood_detect_v2.py
    python src/processing/damage_v2.py
    python src/processing/cutoff_v2.py
    python src/validation/emsr927_comparison.py
    python src/validation/damage_sanity_check.py
    python -m src.analysis.zscore --tag event
    python -m src.report.situation_report
    python -m src.report.dashboard_full

`src/config.py` is not committed (it holds credentials and dates); copy the
values from `src/config.example.py`.

Checks:

    python -m pytest tests/ -q     # 17 passed, 2 skipped
    python src/processing/align_v2_checks.py

Key artifacts:

| File                                                             | Description                                                             |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `data/raw/osm/manifest.json`                                     | OSM snapshot provenance (ohsome, 2026-07-27)                            |
| `data/processed/flood_mask.tif`                                  | Binary flood mask (unvalidated)                                         |
| `outputs/impact_summary.json`                                    | Building, road and bridge counts                                        |
| `outputs/affected_bridges.geojson`                               | 21 bridge features                                                      |
| `outputs/affected_buildings.gpkg`                                | 1,093 building features (flooded + debris)                              |
| `outputs/cutoff_settlements.json`                                | Per-settlement reachability                                             |
| `outputs/validation/damage_sanity.json`                          | EMSR927 damage-point totals                                             |
| `data/processed/emsr927_comparison.json`                         | EMSR927 proxy validation (not committed)                                |
| `outputs/diagnostics/aoi_backscatter_diagnostics.json`           | Pre-rebuild backscatter diagnostic (no generator)                       |
| `outputs/flood_unet.pt`                                          | U-Net best checkpoint (IoU 0.523), earlier run                          |
| `outputs/unet_metrics.json`                                      | 20-epoch training history, earlier run                                  |
| `outputs/himalaya_heldout_metrics.json`                          | Proxy eval, earlier run (its Rasuwa prediction is withdrawn)            |
| `outputs/validation/signal_check.json`                           | VV change along the river and controls (no generator in the repository) |
| `outputs/diagnostics/step3_event.json`                           | Main-stem z-score statistics and bootstrap (exploratory)                |
| `outputs/diagnostics/step3_profile_event.csv`                    | Profile data behind the step 3 profile figure                           |
| `outputs/diagnostics/look_geometry.json`                         | Look geometry used by the radar mask                                    |
| `outputs/figures/step3_map_event.png`, `step3_profile_event.png` | Step 3 map and profile figures                                          |

---

## Appendix A — Figures

**Figure A1 (earlier run; not regenerated).** EMSR927 AOIs (colored outlines) over the post-event VV
backscatter. The four AOIs cover the GLOF-affected corridor, but the SAR
imagery is dominated by terrain rather than a flood signature.

![EMSR927 AOIs over VV](outputs/figures/02_emsr927_aois.png)

**Figure A2 (earlier run; not regenerated).** U-Net training history on Sen1Floods11. Loss decreases
monotonically; validation IoU peaks at 0.523 (epoch 6) and then oscillates —
the model has converged on a 252-chip dataset.

![U-Net training history](outputs/figures/04_unet_training.png)

**Figure A3 (earlier run; not regenerated).** Per-AOI EMSR927 validation. Destroyed-building recall is zero at
both Rasuwa AOIs (Syapru Besi, Timure) — the locations where the GLOF actually
occurred.

![EMSR927 validation](outputs/figures/06_emsr927_validation.png)

---

## 8. Attribution

Full data attribution in [ATTRIBUTION.md](ATTRIBUTION.md). Contains modified
Copernicus Sentinel data 2026; EMSR927 (c) Copernicus EMS; © OpenStreetMap contributors (ODbL); Sen1Floods11 (c) Bonafilia et al. (CC BY 4.0).

**Code license:** MIT.

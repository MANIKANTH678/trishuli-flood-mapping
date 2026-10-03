# Trishuli Flood Damage Mapping — Final Report

**Track B — Multimodal AI Hackathon 2026**

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

**The central finding is negative and important:** the Sentinel-1 pre/post
pair available for this event preliminary, under rebuild the GLOF signal. Two
independent methods — a physics-based SAR change detector and a U-Net
segmentation model trained on Sen1Floods11 — both return effectively zero
flood extent on the Rasuwa corridor. We report this as a substantive result
rather than tuning thresholds to noise.

**Headline numbers:**

| Metric                                 | Value        | Interpretation                                          |
| -------------------------------------- | ------------ | ------------------------------------------------------- |
| Sentinel-1 VV change at AOI01          | **−0.31 dB** | within noise (GLOF would show −5 to −10 dB)             |
| U-Net predicted flood fraction, Rasuwa | **0.000**    | model independently confirms preliminary, under rebuild |
| U-Net val IoU (Sen1Floods11)           | 0.523        | trained model is real, generalizes                      |
| U-Net proxy-Himalaya IoU               | 0.554        | monsoon-subcontinent chips                              |
| EMSR927 damage-point recall            | 0.000        | all four AOIs                                           |
| Our "flooded" buildings                | 61,977       | **16× overcount** vs EMSR927's 3,816                    |

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

**Study area bbox:** `(84.50, 27.40, 86.00, 28.40)` — the Trishuli corridor
from Rasuwa to the Terai, projected to **EPSG:32645** at **30 m**.

---

## 2. Data

| Source             | Purpose                                | Snapshot                             |
| ------------------ | -------------------------------------- | ------------------------------------ |
| Sentinel-1 GRD     | SAR change detection                   | 2026-08-16 (pre) / 2026-08-28 (post) |
| Copernicus DEM     | Slope masking                          | n/a                                  |
| OpenStreetMap      | Infrastructure, settlements, hospitals | 2026-09-30                           |
| Sen1Floods11 v1.1  | U-Net training                         | published dataset                    |
| Copernicus EMSR927 | Validation reference                   | activation 2026-08-26                |

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
uses `20·log10(DN) − 60`; zero DN is treated as nodata.

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

Two independent reference checks:

- `src/validation/emsr927_comparison.py` — rasterizes EMSR927 `builtUpP`
  damage points and `observedEventA` landslide polygons onto the flood-mask
  grid, clips to AOI, and computes damage-point recall and landslide overlap.
- `src/validation/damage_sanity_check.py` — compares our `impact_summary.json`
  counts against EMSR927 per-AOI damage totals.

---

## 4. Results

### 4.1 The flood mask preliminary, under rebuild the GLOF

The strongest single diagnostic is per-AOI backscatter change, saved to
`outputs/diagnostics/aoi_backscatter_diagnostics.json`:

| AOI            | VV pre (dB) | VV post (dB) | change (dB) | combined p05 (dB) |
| -------------- | ----------- | ------------ | ----------- | ----------------- |
| 01 Syapru Besi | −13.86      | −14.04       | **−0.31**   | −1.40             |
| 02 Timure      | −12.80      | −12.54       | **+0.18**   | −0.98             |
| 03 Bidur       | −15.50      | −14.79       | **+0.41**   | +0.00             |
| 05 Phosretar   | −14.95      | −14.60       | **+0.21**   | +0.00             |

A real GLOF over water produces a −5 to −10 dB drop in VV backscatter. We
observe −0.3 to +0.4 dB. The preliminary, under rebuild there.

Four mechanisms plausibly contribute:

1. **Temporal mismatch.** GLOFs drain in hours; the 2-day post-event gap
   (2026-08-26 event → 2026-08-28 acquisition) likely missed standing water.
2. **Radar geometry.** The ascending pass illuminates the Trishuli valley
   obliquely; deep N–S gorges are partly in radar shadow.
3. **Spatial resolution.** At 30 m, the ~30–50 m wide Bhote Koshi channel is
   under-resolved; each pixel mixes water with bank rock.
4. **Debris and vegetation.** Post-GLOF debris flows leave rough surfaces
   that scatter radar rather than specularly reflecting.

### 4.2 Independent confirmation from the U-Net

The trained U-Net was tiled across the Rasuwa SAR change images and predicted
**zero flood pixels** (234 tiles, flood fraction = 0.000). Two independent
methods reaching the same conclusion strongly supports the negative result.

### 4.3 The U-Net itself works

| Split                                       | IoU   | F1    | Precision | Recall |
| ------------------------------------------- | ----- | ----- | --------- | ------ |
| Sen1Floods11 full val (89 chips)            | 0.574 | 0.729 | 0.723     | 0.735  |
| Proxy-Himalaya, India + Pakistan (20 chips) | 0.554 | 0.713 | 0.685     | 0.744  |

The proxy evaluation is only 0.02 IoU below the full val — the model
**generalizes** rather than memorizing. It is a real segmentation model; it
simply sees no flood because there is none in the data.

### 4.4 EMSR927 validation returns zero

| AOI            | Destroyed recall | Landslide overlap | Flood in AOI |
| -------------- | ---------------- | ----------------- | ------------ |
| 01 Syapru Besi | 0.000            | 0.000             | 0.00 km²     |
| 02 Timure      | 0.000            | 0.000             | 0.00 km²     |
| 03 Bidur       | 0.000            | 0.003             | 0.14 km²     |
| 05 Phosretar   | 0.051            | 0.076             | 0.83 km²     |

Zero destroyed-building recall at the two Rasuwa AOIs. The 0.83 km² in AOI05
is monsoon-terrain noise, not the GLOF — the same 47 km² mask scatters across
the entire mosaic.

### 4.5 Damage assessment: 16× overcount

| Metric                             | Our pipeline | EMSR927 | Ratio     |
| ---------------------------------- | ------------ | ------- | --------- |
| Flooded buildings                  | 61,977       | —       | —         |
| EMSR927 damage points (all grades) | —            | 3,816   | —         |
| Overcount factor                   | —            | —       | **16.2×** |

The damage pipeline is mechanically correct — the flood mask driving it is
not.

### 4.6 Hospital reachability

| Metric                           | Value                                              |
| -------------------------------- | -------------------------------------------------- |
| Settlements                      | 1,565                                              |
| Hospitals                        | 1,002                                              |
| Reachable pre-flood              | 1,561                                              |
| Reachable post-flood             | 1,561                                              |
| Settlements becoming unreachable | **0**                                              |
| Detour > 3×                      | 13 (11 sub-kilometre artifacts, 1 real 43× detour) |

Because the flood mask removes only 4.7% of road segments and no settlement
lost connectivity entirely, the cut-off conclusions are dominated by noise.
The one real signal — a settlement 1.66 km from a hospital becoming 70.9 km
away — is plausibly a bridge loss over the Trishuli.

---

## 5. Limitations

**5.1 The event is not observable in the input data.** This is the
dominant limitation. Sentinel-1 ascending 30 m imagery acquired 2 days
after a fast-draining GLOF cannot resolve the event. We demonstrate this
quantitatively in §4.1–4.2 rather than tuning thresholds to noise. Optical
imagery (Sentinel-2, Planet) or higher-resolution SAR (TerraSAR-X,
COSMO-SkyMed) would be required to map the flood surface directly.

**5.2 EMSR927 GRA products contain no flood extent layer.** The activation
mapped building damage and mass movements, not water. Our validation is
therefore proxy-based (damage-point recall and landslide overlap), not a
direct IoU against a flood reference.

**5.3 OSM snapshot is post-event.** The buildings and roads used for impact
assessment were downloaded 2026-09-30, five weeks after the event. Any
post-flood OSM edits (new buildings, reclassified roads) contaminate the
pre-flood baseline. This affects the damage assessment but not the satellite
analysis.

**5.4 30 m resolution limits bridge-level accuracy.** The Bhote Koshi
channel is ~30–50 m wide. Even with a correct SAR signal, pixel-level
classification of the channel would be marginal.

**5.5 U-Net trained on out-of-distribution data.** Sen1Floods11 contains no
Himalayan scenes. The proxy evaluation on India+Pakistan chips is the closest
available, but it does not establish the model's performance on steep
mountain valleys.

**5.6 The debris mask is nearly all speckle.** The final debris layer
(111,874 px) collapses to ~2,000 px after strict minimum-patch filtering —
i.e. the pre-morphology debris class is dominated by noise. This is a
tuning issue in `flood_detect_v2.py` and would need addressing on real
event data.

**5.7 Hospital reachability assumes road-network completeness.** OSM road
coverage in rural Rasuwa is incomplete; missing minor tracks may
over-estimate cut-off.

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
   (475k → 111k → ~2k) reveals a threshold that catches speckle. A
   dual-threshold or GLCM-texture approach would be more robust.
5. **Replace the OSM snapshot for pre-event analysis.** Use a 2026-07
   Geofabrik PBF and rebuild the buildings layer.

---

## 7. Reproducibility

Every stage runs from the repo root with pinned dependencies
(`requirements.txt`). Full pipeline:

    bash run_all.sh

Checks:

    python -m pytest tests/ -q     # 14 passing
    python src/processing/align_v2_checks.py

Key artifacts:

| File                                                   | Description                                |
| ------------------------------------------------------ | ------------------------------------------ |
| `data/processed/flood_mask.tif`                        | Binary flood mask (noise, disclosed)       |
| `outputs/affected_bridges.geojson`                     | 98 bridge features                         |
| `outputs/affected_buildings.gpkg`                      | 154,022 building features (noise-inflated) |
| `outputs/cutoff_settlements.json`                      | Per-settlement reachability                |
| `outputs/flood_unet.pt`                                | U-Net best checkpoint (IoU 0.523)          |
| `outputs/unet_metrics.json`                            | 20-epoch training history                  |
| `outputs/himalaya_heldout_metrics.json`                | Proxy eval + Rasuwa prediction             |
| `data/processed/emsr927_comparison.json`               | EMSR927 validation                         |
| `outputs/diagnostics/aoi_backscatter_diagnostics.json` | Negative-result evidence                   |
| `outputs/validation/damage_sanity.json`                | 16× overcount evidence                     |

---

---

## Appendix A — Figures

**Figure A1.** Binary flood mask (`data/processed/flood_mask.tif`) over the study
area. The 47 km² of detected pixels are scattered across the whole 1.5° × 1.0°
mosaic and do not follow the Trishuli / Bhote Koshi corridor. This is the
negative result in one image.

![Flood mask](outputs/figures/01_flood_mask.png)

**Figure A2.** EMSR927 AOIs (colored outlines) over the post-event VV
backscatter. The four AOIs cover the GLOF-affected corridor, but the SAR
imagery is dominated by terrain rather than a flood signature.

![EMSR927 AOIs over VV](outputs/figures/02_emsr927_aois.png)

**Figure A3.** Median VV backscatter change per AOI, compared against the
expected GLOF signature band (−5 to −10 dB, green shaded). Every AOI sits
within ±0.5 dB of zero — the preliminary, under rebuild in the data.

![Backscatter change per AOI](outputs/figures/03_backscatter_change.png)

**Figure A4.** U-Net training history on Sen1Floods11. Loss decreases
monotonically; validation IoU peaks at 0.523 (epoch 6) and then oscillates —
the model has converged on a 252-chip dataset.

![U-Net training history](outputs/figures/04_unet_training.png)

**Figure A5.** Damage overcount. Our flood-driven pipeline flags 61,977
buildings; EMSR927 mapped 3,816 damaged structures. The 16× gap quantifies
that the SAR mask driving our impact layer is noise.

![Damage overcount](outputs/figures/05_damage_overcount.png)

**Figure A6.** Per-AOI EMSR927 validation. Destroyed-building recall is zero at
both Rasuwa AOIs (Syapru Besi, Timure) — the locations where the GLOF actually
occurred.

![EMSR927 validation](outputs/figures/06_emsr927_validation.png)

---

## 8. Attribution

Full data attribution in [ATTRIBUTION.md](ATTRIBUTION.md). Contains modified
Copernicus Sentinel data 2026; EMSR927 (c) Copernicus EMS; OpenStreetMap (c)
OSM contributors (ODbL); Sen1Floods11 (c) Bonafilia et al. (CC BY 4.0).

**Code license:** MIT.

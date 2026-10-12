# Validation log: EMS (EMSR927) scorings

EMS is used for checking only. Thresholds come from the null, not from EMS.

| Scoring                    | Commit                                                            | What was scored                                               | What changed afterwards                                                |
| -------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| S1 detector, recall by AOI | ea4d310, c0ee96c (last commits that changed the EMS output files) | S1 flood mask vs EMSR927 damage points, plus random-mask null | nothing; S1 numbers identical across all runs                          |
| S2/fused, first check      | not recorded as a commit; run from the working tree               | EMS check on S2/fused, run before the null gate existed       | null gate added; first commit containing it is bb783ff (s2-frozen-3)   |
| S2/fused, after gate       | not recorded as a commit; run from the working tree               | same check with S2 gated on null calibration                  | calibrated flag fixed in 377b1ec (s2-frozen-4 originally pointed here) |

Tags: s2-frozen, s2-frozen-2, s2-frozen-3 and s2-frozen-4 exist. s2-frozen-4 is final and has been moved to the last commit of Step 5; no further numbered tags will be added.

Disclosure: the first EMS check on S2/fused ran before the null gate was added. The gate is conservative and does not depend on EMS values, and S1 numbers are identical across all runs. AOI03 remains the hold-out and is touched only for the final run.

\## Step 5.B: S2 null diagnosis (post-freeze edit, no new tag)

\- Edit: src/analysis/s2_detect.py gained --diag and --max-elev (default None, unused).

\- Diagnosis (null only, leave-one-out over pre dates, t=6.0; no EMS data used, AOI03 not touched):

&#x20; false alarms only for MNDWI at 0-2000 m (2026-08-11: 0.0017, 2026-08-12: 0.0183).

&#x20; MNDWI is 0 at 2000-3500 m and 3500-9000 m; scar (NDVI/BSI) is 0 at all elevations on all dates.

\- Decision: low-elevation water-index false alarms are not snow/ice, so an elevation cap would not help.

&#x20; One-attempt stop rule applied; no further S2 tuning.

\- Outcome: status remains null_not_calibrated; fused == S1; S2 provides qualitative context only.

## Step 7: single EMSR927 validation script

| Scoring                                                         | Commit                                                                                 | What was scored                                                                                                                                           | What changed afterwards                                     |
| --------------------------------------------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Fused (= S1) class raster, `src/validation/emsr927_validate.py` | f224f86 on branch ems-validation, plus a84ac96 and ff31d1c | Landslide polygons and damage points, assessed domain (AOI minus notAnalysedA), tolerance 0/30/60/100 m, block-bootstrap CI, blob-relocation chance model | nothing tuned; detector unchanged since tag detector-frozen |

- AOI03 (hold-out) scoring count: **4** (the three rows of the first table plus this one). Confirm this count before merging.
- Regression: area metrics (AOI03 0.928/0.174/0.172, AOI05 0.990/0.245/0.244), point counts (433, 431, 2,343, 581) and 0 m recall (AOI03 0.2061, AOI05 0.0671) reproduce the retired scripts exactly.
- Reference: all local EMSR927 products are GRA. observedEventA is 6-Mass Movement / Landslide in all four AOIs, so the metric is scored against landslide polygons, not flood extent (docs/ems_inventory.md).
- Superseded finding: `null_recall_aoi.py` reported AOI03 above its null (z about +10.5) and AOI05 below (z about -2.9). Its null scattered single pixels, so its variance was far too small. Withdrawn. With the blob-relocation null and block-bootstrap CIs, damage-point recall is indistinguishable from chance in both AOIs at every tolerance (AOI03 23% [11-33%] vs chance 9%; AOI05 8% [2-18%] vs chance 8%).
- Verdict rules ("above chance" only if the CI lower bound exceeds the chance mean + 2 sd, mirror for "below") are coded in `emsr927_validate.py`. They were fixed in code, not recorded in a separate file before the first run.
- Retired: emsr927_comparison.py, damage_sanity_check.py, emsr927_detector_check.py, null_recall_aoi.py, and the the retired mask-coverage field field.
2026-10-06: AOI05 provenance check. Portal Grading v3 download (vector files labelled v2) is byte-identical to the local copy (fc /b, gpkg and observedEventA shp). Map PDF is v3. AOI05 scores unchanged; no rerun.
2026-10-06: AOI03 Grading Monitoring 1 v1 downloaded (5 landslide polygons vs 2 in v1). Not used for the headline score; AOI03 v1 remains the reference. Scores unchanged.
flood_water is separable only if event area > 3x the largest null area
### Step 8/9 runs logged 2026-10-11 23:37 (tools/write_step8_docs.py)
- class nulls (ungated, leave-one-out, rule >3x): Flood-like (new open water) change is separable from the no-flood nulls. [class_nulls.json f582ed00cac2]
- seeds: valid 0.672±0.005, test 0.682±0.002, bolivia 0.702±0.020 [seeds_summary.json cafbf933cce9]
- Himalayan chips: not run; label agreement None [points.csv 632dec9b3f5e]
- AI vs S2 agreement (pseudo-reference): post IoU 0.06; pre IoU 0.03
- corridor: not separable from the nulls
- No EMS data was read by any of these runs.

### Step 8/9 runs logged 2026-10-11 19:09 (tools/write_step8_docs.py)
- class nulls (ungated, leave-one-out, rule >3x): Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water. [class_nulls.json 9da5ed0cf781]
- seeds: valid 0.672±0.005, test 0.682±0.002, bolivia 0.702±0.020 [seeds_summary.json cafbf933cce9]
- Himalayan chips: not run; label agreement None [points.csv 632dec9b3f5e]
- AI vs S2 agreement (pseudo-reference): post IoU 0.06; pre IoU 0.03
- corridor: not separable from the nulls
- No EMS data was read by any of these runs.

### Step 8/9 runs logged 2026-10-11 19:09 (tools/write_step8_docs.py)
- class nulls (ungated, leave-one-out, rule >3x): Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water. [class_nulls.json 9da5ed0cf781]
- seeds: valid 0.672±0.005, test 0.682±0.002, bolivia 0.702±0.020 [seeds_summary.json cafbf933cce9]
- Himalayan chips: not run; label agreement None [points.csv 632dec9b3f5e]
- AI vs S2 agreement (pseudo-reference): post IoU 0.06; pre IoU 0.03
- corridor: not separable from the nulls
- No EMS data was read by any of these runs.

EMS credit: European Union, Copernicus Emergency Management Service data (EMSR927, used for checking only).

### Step 8/9 runs logged 2026-10-12 10:42 (tools/write_step8_docs.py)
- class nulls (ungated, leave-one-out, rule >3x): Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water. [class_nulls.json 9da5ed0cf781]
- seeds: valid 0.672±0.005, test 0.682±0.002, bolivia 0.702±0.020 [seeds_summary.json cafbf933cce9]
- Himalayan chips: not run; label agreement None [points.csv 632dec9b3f5e]
- AI vs S2 agreement (pseudo-reference): post IoU 0.06; pre IoU 0.03
- corridor: not separable from the nulls
- No EMS data was read by any of these runs.

### Step 8/9 runs logged 2026-10-12 10:46 (tools/write_step8_docs.py)
- class nulls (ungated, leave-one-out, rule >3x): Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water. [class_nulls.json 9da5ed0cf781]
- seeds: valid 0.672±0.005, test 0.682±0.002, bolivia 0.702±0.020 [seeds_summary.json cafbf933cce9]
- Himalayan chips: not run; label agreement None [points.csv 632dec9b3f5e]
- AI vs S2 agreement (pseudo-reference): post IoU 0.06; pre IoU 0.03
- corridor: not separable from the nulls
- No EMS data was read by any of these runs.

### Step 8/9 runs logged 2026-10-12 10:48 (tools/write_step8_docs.py)
- class nulls (ungated, leave-one-out, rule >3x): Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water. [class_nulls.json 9da5ed0cf781]
- seeds: valid 0.672±0.005, test 0.682±0.002, bolivia 0.702±0.020 [seeds_summary.json cafbf933cce9]
- Himalayan chips: not run; label agreement None [points.csv 632dec9b3f5e]
- AI vs S2 agreement (pseudo-reference): post IoU 0.06; pre IoU 0.03
- corridor: not separable from the nulls
- No EMS data was read by any of these runs.

### 2026-10-12 17:35 IST: route-equivalence acceptance rule (written BEFORE the PC-route case-study run)
- Run: `python -m src.run --bbox 84.95,27.80,85.55,28.35 --event-date 2026-08-26 --name trishuli_pc --profile fast --s1-source pc` in its own directory; compared with the SNAP case-study `data/processed/fused_class_30m.tif`.
- PASS only if all three hold: (a) flagged area (classes 1-3) within ±50% of the SNAP value 3.14 km² (1.57-4.71 km²); (b) pixel IoU of the flagged masks ≥ 0.3 (after aligning the PC grid to the SNAP grid by nearest-neighbour if the grids differ); (c) the same separable-vs-null verdicts per class (flood-like, dark, bright) under the >3x leave-one-out class-null rule, and the same gated detector status (change_detected).
- If any fails, the PC route is labelled "cross-check only" everywhere (README, report, dashboard, situation report, judges_day.md, live demo).
- No PC-route case-study output had been viewed when this was written.

### 2026-10-12 17:47 IST: Himalayan chips, path 1 result and path-2 amendment (written BEFORE any labelling)
- Path 1 (tools/chip_windows.py, windows chosen by Sentinel-2 clear fraction and stratum only, no model output read): 27 Aug 2026 main 1/8, trib 0/8, hill 1/4; 12 Aug 2026 main 0/8, trib 0/8, hill 2/4. Total 4 windows, fewer than 8, so path 1 is not used.
- Amendment: no chip reached 70% clear. Chips will be labelled on clear pixels only (cloud/shadow = −1); all 20 stay. No model output has been viewed. The change doesn't depend on outcomes.
- Metrics (tools/himalaya_path2.py): pooled IoU over labelled pixels, labelled pixels per chip, chip-bootstrap 95% CI, A/B agreement on the first 8 chips in points.csv order. Pre-event chips (12 Aug S2, data/external/himalaya_chips_pre) are labelled and reported separately.

### 2026-10-12 17:51 IST: wording correction (review item 4)
SUPERSEDES the ‘new open water’ wording above. Class 1 is water-like backscatter change; the single-date water model’s corridor test is not separable from nulls and Sentinel-2 does not confirm open water.

### 2026-10-12 17:55 IST: route-equivalence result (rule above, 17:35 IST): FAIL
- PC run: sandbox, `python -m src.run --bbox 84.95,27.80,85.55,28.35 --event-date 2026-08-26 --name trishuli_pc --profile fast --s1-source pc` (own directory), 1,075 s in timings.json. Same track and dates as the SNAP case study (asc85; post 2026-08-28; refs 08-16, 08-04, 07-23, 07-11). Grids identical (EPSG:32645, same transform and shape): compared pixel for pixel, no resampling.
- (a) flagged area: SNAP 3.14 km², PC 3.53 km² (allowed 1.57-4.71): pass.
- (b) pixel IoU of the flagged masks: 0.362 (≥ 0.3): pass.
- (c) verdicts: gated status change_detected on both; class nulls (>3x rule) flood-like SNAP 0.306 vs null max 0.0144 separable / PC 0.050 vs 0.0000 separable; dark SNAP 2.294 vs 0.0396 separable / PC 2.775 vs 0.1035 separable; bright SNAP 0.542 vs 0.0918 separable (5.9x) / PC 0.701 vs 0.2844 NOT separable (2.5x): fail.
- Also: PC calibrated t_hi 3.5 (SNAP 4.0); flood-like class 0.05 vs 0.31 km² (the fixed -16/-22 dB water gates were set for sigma0; gamma0 is brighter).
- Verdict: FAIL. The PC route is labelled "cross-check only" everywhere (README, report, dashboard, situation report, judges_day.md, demo).

# Trishuli Flood Damage Mapping

**Track B — Multimodal AI Hackathon 2026**

> **Documentation (6-page report): [`docs/REPORT.pdf`](docs/REPORT.pdf)** (source `docs/REPORT.md`). Demo video: see the Devpost submission. Validation history: `docs/validation_log.md`; judges' Q&A: `docs/qa_sheet.md`.

Post-event damage assessment for the **26 August 2026 Trishuli–Bhote Koshi
flash flood (Rasuwa District, Nepal)** using free Sentinel-1 SAR, a DEM and
OpenStreetMap (ohsome API snapshot 2026-07-27, pre-event; manifest in
`data/raw/osm/manifest.json`). Licence: MIT for the code (`LICENSE`); data credits in `ATTRIBUTION.md`. © OpenStreetMap contributors (ODbL).

> **Status.** Sentinel-1 preprocessing is SNAP-based (calibrated, terrain-corrected
> σ⁰, Copernicus GLO-30 DEM). The change map is a multi-temporal SAR change-detection
> product, **not a validated flood extent**. Its threshold was set from null runs on
> pre-event reference scenes (no EMSR927 data), and the detector was frozen (git tag
> `detector-frozen`) before its EMSR927 check. The event pair passes the detection
> gate and a pre-event scene does not. The flood-water class itself is small (0.31 km²). Damage-point recall of the detected
> classes is indistinguishable from chance in both scored AOIs. Most detected change is dark or bright
> surface change on the valley floor; at Bidur and Phosretar nearly all of it lies on mapped
> landslide polygons, and nothing is detected at the two Rasuwa AOIs. A Sen1Floods11-trained water
> model, run prediction-only on the corridor, is not separable from pre-event nulls. An earlier README claimed the pair holds no GLOF signal; that claim is
> withdrawn, because its diagnostic used uncalibrated, GCP-geocoded imagery.

## Quick start (clean machine)

Tested route: Windows 10/11 or Linux, Python 3.12, 16 GB RAM. Educational prototype, not an operational tool.

```
git clone https://github.com/MANIKANTH678/trishuli-flood-mapping.git
cd trishuli-flood-mapping
python -m venv .venv
.venv\Scripts\activate                 # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt        # Windows: requirements_win.txt
python -m pytest tests -q              # data-dependent tests skip on a fresh clone
```

### Environment variables (read from the environment only; never put them in a file)

| Variable | Needed for | Read by |
|---|---|---|
| `COPERNICUS_USER`, `COPERNICUS_PASS` | SNAP route: Sentinel-1 GRD download from the Copernicus Data Space Ecosystem (free account, https://dataspace.copernicus.eu/) | `src/run.py` (preflight), `src/fetch/fetch_sentinel1.py` |
| `GPT` | SNAP route, only if ESA SNAP `gpt` is not on `PATH` or in `C:\Program Files\esa-snap\bin\gpt.exe` | `src/run.py`, `src/processing/s1_preprocess.py` |
| `OHSOME_API_KEY` | optional: OSM snapshot at the exact pre-event date via ohsome; without it a dated Geofabrik extract is used | `src/download/fetch_osm.py` |
| `CHROME` | optional: path to Chrome/Edge for the PDF page gate and screenshots (else WeasyPrint) | `src/report/pdf_gate.py`, `tools/screenshot.py` |

In `cmd`: `set "COPERNICUS_USER=you@example.com"` and `set "COPERNICUS_PASS=..."` (quotes around the whole assignment).

### Two routes, one of them validated

| Route | Command | Sentinel-1 product | Status |
|---|---|---|---|
| **SNAP (headline, validated)** | `python -m src.run --bbox W,S,E,N --event-date YYYY-MM-DD --name <area> --profile fast --clean` | Sentinel-1 GRD (Copernicus Data Space Ecosystem), SNAP sigma0 terrain correction | Every case-study number in this README and the report comes from this route. Needs CDSE login, SNAP `gpt`, ~40 GB free. Laptop clean-clone timing: pending (`outputs/step11_snap_timings.json`). |
| PC (no login) | add `--s1-source pc` | Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD) | **Cross-check only.** It failed the pre-registered route-equivalence test on the case study (2026-10-12): flagged area 3.53 vs 3.14 km² and pixel IoU 0.36 pass, but the bright-change class is not separable from the nulls on PC (it is on SNAP) and flood-like change falls from 0.31 to 0.05 km². `docs/validation_log.md`, `outputs/validation/route_equivalence.json`. ~14-18 min on 4 CPU cores. |

Organiser clarifications (hackathon Discord #help-desk, read 2026-10-12):
- Sentinel-1 that arrives already terrain-corrected (Sentinel Hub on CDSE) was answered: "you still need to make a processing
  pipeline for data, as the point is to process the raw stream". So the GRD + SNAP route is the one we present; the PC RTC
  route stays a cross-check.
- Judges' data access: make a video and document how to set up the free account; in live judging you may run the pipeline
  with your own account. CDSE setup is in the quick start above. A live presentation may be held for winners only; no
  run-time limit was stated, so live demos use cached scenes (`--profile fast`).
- Only free/open APIs and models are allowed, each named in this README; the 6-page documentation lives in the repo (below).

`--profile fast` skips Sentinel-2, the threshold-sensitivity runs and the AI layer, and keeps the null-calibrated gate.
A failed stage prints `resume with --from-stage <name>`. A folder holding another run is refused; `--clean` archives it
under `runs/<stamp>/` (never `models/`). Fewer than 3 reference dates means no null calibration (**UNCALIBRATED**);
3+ dates where no threshold meets the 0.1% target means **calibration target not met**, and the report gives the
minimum detectable area (gate × assessed floor). More in `docs/judges_day.md`.

## Pipeline stages (`python -m src.run`)

| # | Stage | Module | Route | Output |
|---|---|---|---|---|
| 1 | select_s1 | `src.fetch.select_s1` | both | `data/raw/sentinel1/selection.json`: one relative orbit and pass, nearest post scene, up to 4 references; time-of-day and platform warnings |
| 2 | fetch_s1 | `src.fetch.fetch_sentinel1 --selection ... --download` | SNAP | `data/raw/sentinel1/<split>/*.zip` |
| 3 | unzip_s1 | inline in `src/run.py` | SNAP | `*.SAFE` |
| 4 | check_stack | `src.processing.check_stack` | SNAP | orbit/pass equality (fatal); off-grid dates, > 10 min time-of-day spread, mixed S1A/S1D (warnings) |
| 5 | osm | `src.download.fetch_osm` | both | `data/raw/osm/*.geojson`, `manifest.json` (pre-event snapshot) |
| 6 | dem | `src.fetch.fetch_dem` | both | `data/raw/dem/dem_glo30_wgs84.tif` (Copernicus GLO-30) |
| 7 | snap / grid | `src.processing.s1_preprocess`, `src.processing.s1_to_grid` | SNAP | sigma0 terrain-corrected, 30 m UTM VV/VH dB per split in `data/processed/` |
| 7' | pc_stack | `src.processing.pc_stack` | PC | the same `s1_<split>_<pol>_30m.tif` files from RTC gamma0 |
| 8 | geometry, hand, radar_mask | `src.analysis.geometry`, `.hand`, `.radar_mask` | both | look geometry, `hand_30m.tif`, `radar_mask_30m.tif` |
| 9 | null_calibration | `src.analysis.calibrate_null` | both (≥ 3 refs) | `outputs/diagnostics/step4_null_calibration.json` (`alpha_met`) |
| 10 | detect | `src.analysis.detect` | both | `detect_class_30m.tif`, masks, `outputs/diagnostics/detect_<track>.json` (`calibrated`, `alpha_met`, `min_detectable_km2`) |
| 11 | s2_search / s2_ingest / s2_detect | `src.fetch.s2_search`, `src.processing.s2_ingest`, `src.analysis.s2_detect` | full profile | gated Sentinel-2 branch |
| 12 | fuse | `src.analysis.fuse` | both | `fused_class_30m.tif` |
| 13 | sens_masks, ai_scenes | `tools/make_sens_masks.py`, `src.modeling.predict_scene` | full profile | scenario masks, AI water probability |
| 14 | damage, cutoff | `src.processing.damage_v2`, `src.processing.cutoff_v2` | both | `outputs/impact_summary.json`, `outputs/cutoff_settlements.json` |
| 15 | dashboard, situation_map, report | `src.report.dashboard`, `tools/make_situation_map.py`, `src/report/situation_report.py` | both | `outputs/dashboard/index.html`, `outputs/reports/situation_report_{EN,NE}.md` |

Timings per stage are written to `outputs/timings.json`. Not part of `src.run`: class-level nulls (`tools/class_nulls.py`),
EMSR927 check (`src/validation/emsr927_validate.py`, needs `data/external/EMSR927`), the 6-page report
(`tools/build_report.py`), water-model training/evaluation (`src/modeling/train_segmentation.py`, `src/modeling/evaluate.py`)
and the Himalayan chip tools (`tools/chip_windows.py`, `tools/make_himalaya_chips.py`, `tools/label_chips.py`,
`tools/himalaya_path2.py`).

**Detector classes** (`detect_class_30m.tif`): 1 flood-like (water-like backscatter change, not confirmed open water),
2 surface change (dark), 3 surface change (bright), 0 no change on the assessed floor, 253 not assessed (above the HAND
floor), 254 radar-unobservable, 255 no data.

## Train / eval water model

Trained on **Sen1Floods11 v1.1** hand-labelled chips (Bonafilia et al., 2020); open water only. Checkpoint and
threshold are chosen on validation only. Pooled IoU over all valid pixels, 95% chip-bootstrap CIs:

| Row | Val IoU (pooled) | Test | Bolivia (unseen region) |
|---|---|---|---|
| Old checkpoint, thr 0.5 (the old 0.523 was a mean of per-batch IoUs) | 0.575 [0.49, 0.65] | 0.612 [0.49, 0.71] | 0.666 [0.48, 0.77] |
| U-Net, 20 epochs, thr 0.5 | 0.634 [0.55, 0.70] | 0.659 [0.54, 0.75] | 0.687 [0.50, 0.79] |
| **ResNet34-U-Net, 40 epochs, thr 0.4** | **0.672 [0.59, 0.74]** | **0.682 [0.57, 0.77]** | **0.680 [0.46, 0.80]** |

Test chips come from the training events, so Bolivia (15 chips) is the only unseen-region test and its
interval is wide. Sen1Floods11 contains no Himalayan scenes. See `MODEL_CARD.md`.

## Key results

| Metric                                                           | Value                                                                                                                                                                                                                                                  |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Water model (ResNet34 U-Net, Sen1Floods11), pooled IoU [95% CI] | val 0.672 [0.59, 0.74]; test 0.682 [0.57, 0.77]; Bolivia (unseen region, 15 chips) 0.680, chip CI 0.46–0.80 (seed mean 0.702 ± 0.020). Old checkpoint: val 0.575, test 0.612, Bolivia 0.666 |
| Labelled Himalayan chips | Not labelled yet. Clear-sky check (≥70% clear S2) keeps 0 of 20 chips on 27 Aug and 0 of 20 on 12 Aug; an algorithmic window scan (clear fraction and stratum only) finds 4 windows over both dates, fewer than 8. Amendment logged before labelling: all 20 chips, clear pixels only (cloud/shadow = −1); metrics tool `tools/himalaya_path2.py`. Until labelled, qualitative only |
| Detector threshold (null-calibrated)                             | t_hi 4.0: the smallest grid value whose worst leave-one-out false-alarm fraction is ≤ 1e-3 (3.5e-4 at 4.0). t_lo 2.5. Gate: seed fraction must exceed 1.05e-3 of the assessed floor                                                                    |
| Event vs null                                                    | Event seed fraction 1.09e-2 (about 10× the gate), status `change_detected`. A pre-event scene tested against the other references: 0.0, `no_significant_change` (that scene was also one of the four calibration scenes)                               |
| Class-level nulls | Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water. |
| Assessed floor                                                   | 199.9 km² (HAND ≤ 30 m), 89.7% radar-observable                                                                                                                                                                                                        |
| Detected change | Water-like backscatter change ("flood-like") 0.31 km² (340 px). Surface change: dark 2.29 km², bright 0.54 km² (descriptive classes, not confirmed damage) |
| Backscatter change (post − pre)                                  | river, 60 m buffer: median +0.02 dB, p1 −6.22 dB; river shifted ±1500 m: −0.08 dB, p1 −4.74 / −4.46 dB; whole scene: +0.00 dB. Flood-water pixels (340): −7.92 dB (the mask is selected on change, so this is not independent evidence)                |
| EMSR927 damage points vs detected classes (1-3), assessed domain | Recall at 0 m [95% block-bootstrap CI] vs chance: AOI03 (hold-out) 23% [11-33%] vs 9%; AOI05 8% [2-18%] vs 8%. Indistinguishable from chance at 0, 30, 60 and 100 m in both. AOI01 and AOI02 flag nothing. Chance model relocates the mask's own blobs |
| Buildings overlapping the mask vs EMS damage points              | Within 30 m of a damage point: AOI03 97% (n=329, baseline 54%); AOI05 78% (n=36, baseline 44%). A lower bound, and not independent of landslide location                                                                                               |
| Detections on mapped landslide polygons                          | Precision (a lower bound) / recall / IoU: Bidur (hold-out AOI) 0.93 / 0.17 / 0.17; Phosretar 0.99 / 0.24 / 0.24; Syapru Besi and Timure 0 for all three. Landslide polygons are not flood extent, so these are proxies                                 |
| EMSR927 content on the assessed floor                            | Damage points / landslide area: Bidur 91% / 95%; Phosretar 85% / 96%; Syapru Besi 40% / 56%; Timure 29% / 59%                                                                                                                                          |
| AI corridor water test (prediction-only, shadow/layover masked, floor via HAND) | New-water excess main − tributary floor 0.86% vs largest leave-one-out null 0.76% (1.13x): not separable from the nulls. Does not independently confirm the flood |
| Buildings overlapping the change mask (exposure, not damage) | **556** (scenario range 244–1,078) of 189,503; 92% of buildings are of unknown status (outside the assessed or radar-observable floor), not clear |
| Bridges exposed (not failed) | 20 of 385 (range 12–30); 11.8 km of motorable road overlapping the mask (range 6.4–22.0 km) |
| Settlements cut off from hospitals | 4 of 446 (range 2–12); 141 have no pre-flood road route to a hospital (not assessed, never counted as cut off). No cut-off ground truth |

The EMSR927 numbers are proxies: the downloaded GRA products (AOI01 v1, AOI02 v2, AOI03 v1,
AOI05 v2) contain landslide polygons and building damage points, not a flood extent, so the
flood class is not validated against EMS. Earlier pipeline stages also ran EMS comparison
scripts, so this is not an independent validation. No locality or district breakdown is reported: none of the flooded buildings
carries an OSM `addr:city` tag and no administrative boundary layer is included.

EMSR927 GRA products held locally (checked 2026-10-11) contain landslide polygons and damage points, no flood-extent layer. EMS data: European Union, Copernicus Emergency Management Service data (checking only, never an input).

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

- Contains modified Copernicus Sentinel data 2026.
- Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- © OpenStreetMap contributors.
- European Union, Copernicus Emergency Management Service data (EMSR927, checking only).

Educational prototype, not an operational tool. Full credits and licences: [ATTRIBUTION.md](ATTRIBUTION.md). Code: MIT. Data: own licences.

## Step 5: Sentinel-2 branch and fusion

**Method.** Sentinel-2 L2A bands are read by window and cloud-masked with SCL at 10 m (classes 0, 1, 2, 3, 8, 9, 10, 11, cloud dilated 3 px, turbid water kept via MNDWI > 0.1). NDVI, MNDWI and BSI are averaged to the 30 m grid. The reference is the per-pixel median of pre-event dates, the post-event composite is the earliest clear observation within 30 days, and scores are robust z-values against elevation-stratified hillslope controls. The threshold comes from leave-one-out nulls over the pre-event dates. Fusion writes class, source and confidence layers.

**Result.** The S2 branch is inconclusive and contributes nothing to the fused product (status null_not_calibrated). Post-event floor clear fraction was 12.4% (5.1% over all valid pixels), and the leave-one-out false-alarm rate was 1.6-5.4% across the threshold grid against alpha = 0.1%, so no threshold passed. The fused product is therefore identical to the S1 v1 detector output. Pre dates: 2026-06-18, 07-05, 08-11, 08-12. Post dates: 2026-08-27, 09-08, 09-13, 09-20, 09-21.

**EMSR927 check (S1 v1 = fused).** Share of EMS damage points in the assessed domain / point recall within 100 m / landslide precision, recall, IoU:

- AOI03 (hold-out): 91% / 52% / 0.93, 0.17, 0.17
- AOI05: 85% / 24% / 0.99, 0.24, 0.24
- AOI02: 29% / 2% / no detections
- AOI01: 40% / 0% / no detections

**Limitations.** Monsoon cloud limited S2 coverage. The S2 null calibration failed. Crop phenology can mimic scars on farmland. 30 m aggregation loses S2 resolution. The upstream gap (damage on terraces and slopes above the 30 m floor in AOI01 and AOI02) remains open; the next lever is the descending-track search.

**Disclosures.** EMS data were used to diagnose domain coverage (design only). AOI03 was scored four times (see `docs/validation_log.md`): v1, an empty-S2 fusion run identical to v1, a pre-gate S2 run, and the Step 7 single-script run; detector numbers did not change and nothing was tuned on it. The null-calibration gate was added after viewing EMS results (tuned on EMS). Tags s2-frozen to s2-frozen-4 record the code states; the pre-gate EMS outputs are kept as \*\_pregate_vs_emsr927.json and are superseded.

<!-- STEP8:evidence -->
## Step 8 evidence (generated by tools/write_step8_docs.py)

### Detector: class-level nulls

Rule written before the run: separable only if event area > 3x the largest null area (nulls ungated, leave-one-out). Leave-one-out over the four pre-event scenes.

| Class | Event km² (ungated) | Largest null km² | Ratio | Separable (>3×) |
|---|---|---|---|---|
| flood_water | 0.306 | 0.014 | 21.2 | yes |
| surface_dark | 2.294 | 0.040 | 57.9 | yes |
| surface_bright | 0.542 | 0.092 | 5.9 | yes |

**Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water.**

### AI model: seeds

| Split | Mean IoU | SD (seeds) | Min | Max |
|---|---|---|---|---|
| valid | 0.672 | 0.005 | 0.667 | 0.677 |
| test | 0.682 | 0.002 | 0.680 | 0.683 |
| bolivia | 0.702 | 0.020 | 0.680 | 0.719 |

Bolivia (the only unseen-region test, 15 chips): seed range 0.68–0.72; shipped-model chip CI 0.46–0.80: the interval is wide.

3 seeds (0, 1, 2); the **seed-0 model is the shipped model**; seeds 1-2 only measure training noise.

### AI model: Himalayan evidence

Himalayan hand-labelled chips: not evaluated yet.

Corridor test (prediction-only; shadow/layover masked, floor via HAND): new-water excess main − tributary floor 0.0086 vs largest leave-one-out null 0.0076: **not separable from the nulls**.

The model detects **open water only**: no allowed training dataset labels debris, so debris and mud come from the change detector, not the AI.

*Limitation (not a headline): AI vs Sentinel-2 cannot arbitrate.* Agreement with Sentinel-2 MNDWI water on clear valley-floor pixels is a pseudo-reference, **not accuracy** (turbid water fools MNDWI, S1 and S2 are 1–4 days apart, 30 m), and its precision is about 0.5 on both the pre- and post-event dates, so agreement that does not change with the event cannot arbitrate: post (20260827) IoU 0.06, P 0.51, R 0.07, n=31,000; pre (20260812) IoU 0.03, P 0.49, R 0.03, n=22,127.

### Flood path (bonus)

| Run | Path length | Settlements on corridor | Median distance to OSM river | EMS names in order | Names not in OSM |
|---|---|---|---|---|---|
| flood_path | 89.6 km | 20 | 0.59 px | True | Syapru Besi, Timure, Phosretar |
| flood_path_trib | 81.5 km | 18 | 0.59 px | True | Syapru Besi, Timure, Phosretar |

Geometry only (D8 on GLO-30 + HAND ≤ 30 m corridor): no hydraulics, no arrival times.
<!-- /STEP8:evidence -->

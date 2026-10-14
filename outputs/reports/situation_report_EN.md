# Situation Report — Trishuli / Bhote Koshi flood, 2026-08-26

> **PRELIMINARY** — generated 2026-10-14 from commit `886db8f`. Educational prototype, not an operational tool. Numbers change if the detector or inputs change.

## 1. Situation

Event date 2026-08-26, Trishuli / Bhote Koshi, Rasuwa, Nepal; Sentinel-1 2026-08-16 / 2026-08-28, Copernicus GLO-30, OSM. Detector status: **change_detected** (track asc85; VH robust-z change of pre (2026-08-16), placebo (2026-08-04), pre3 (2026-07-23), pre4 (2026-07-11) against post (2026-08-28), thresholds 4 / 2.5, calibrated against pre-event nulls, null false-alarm max 0.035%; minimum detectable area ≈ 0.21 km²). The mask is restricted to the HAND valley floor; the result is exposure to a detected mask, **not a validated flood extent and not damage**. Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water.

## 2. Detection signal

Step 3 test (pre → post; decreases by robust z at threshold 3.5): main floor (36,708 px, 93% radar-observable) against tributary floors (176,217 px) and hillslope controls. Placebo: placebo → pre.

| Band | Main floor decrease px | Tributary floor | Hillslope | Event excess, main − tributary [95% CI] | Placebo main floor; excess [95% CI] |
|---|---|---|---|---|---|
| VV | 1.87% | 0.05% | 0.01% | 1.79% [0.86%, 2.88%] | 0.00%; excess 0.00% [0.00%, 0.00%] |
| VH | 4.53% | 0.06% | 0.01% | 4.44% [2.67%, 6.46%] | 0.00%; excess 0.00% [0.00%, 0.00%] |

The main floor has more decrease pixels than the tributary floors in both bands, with 95% CIs above zero, and the placebo pair shows none. This is evidence of surface change along the main reach, not by itself of flooding. The river reach has a lower-tail excess over the shifted controls: evidence of surface change along the reach, not by itself of flooding. Water model (ResNet34 U-Net, Sen1Floods11, no Himalayan training scenes): unseen-region (Bolivia) IoU 0.68, 95% chip CI 0.46–0.80, 15 chips; 0.70 ± 0.02 over 3 training seeds. On this corridor its new-water excess is 0.86% against a pre-event null maximum of 0.76%: not separable from the nulls. Prediction-only; not independent evidence.

## 3. Exposure to the mask

| Item | Headline (base mask) | Scenario range |
|---|---|---|
| Flagged area | 3.14 km² (0.31 flood-like, 2.29 dark, 0.54 bright) | 1.66–5.48 km² |
| Buildings overlapping the mask | 556 (6 flood-like class, 550 other surface change) of 189,503 | 244–1,078 |
| Buildings within 30 m | 881 | 407–1,775 |
| Buildings with unknown status | 174,132 (92%) | n/a |
| Motorable road in mask | 11.8 km (118 segments) | 6.4–22.0 km |
| Bridges exposed (not failed) | 20 of 385 | 12–30 |
| Settlements cut off (no path to a hospital) | 4 of 446 | 2–12 |
| Settlements degraded (≥2× and ≥2 km longer) | 0 | 0–1 |
| Settlements not assessed (no pre-flood route) | 141 | n/a |

Range = 3 thresholds × mask ±1 px × bridges fail/survive. All 4 first breaks: 4 debris; the detector observed 28%–55% of each cut-off route. Cut-off covers only the 305 settlements with a pre-flood route; 18 of 20 hospitals were snapped to the road network.

## 4. Validation against Copernicus EMS (EMSR927)

Check only: EMS data is not an input to any number above. EMSR927 GRA products held locally (checked 2026-10-11) contain landslide polygons and damage points, no flood-extent layer. Domain: AOI minus notAnalysedA, restricted to pixels the detector observed. Chance: the mask's own blobs relocated at random (100 draws).

| AOI | Reference px | Debris P / R / IoU | Flood or debris P / R / IoU |
|---|---|---|---|
| AOI01 Syapru Besi | 694 | n/a / 0.000 / 0.000 | n/a / 0.000 / 0.000 |
| AOI02 Timure | 851 | n/a / 0.000 / 0.000 | n/a / 0.000 / 0.000 |
| AOI03 Bidur (hold-out) | 6,208 | 0.925 / 0.166 / 0.164 | 0.928 / 0.174 / 0.172 |
| AOI05 Phosretar | 4,826 | 0.988 / 0.200 / 0.200 | 0.990 / 0.245 / 0.244 |
| Pooled non-hold-out | 6,371 | 0.988 / 0.152 / 0.151 | 0.990 / 0.185 / 0.185 |
| Pooled hold-out | 6,208 | 0.925 / 0.166 / 0.164 | 0.928 / 0.174 / 0.172 |

| AOI | Assessed points | Recall 0 m | 30 m | 60 m | Flagged buildings within 30 m of a damage point vs all-building baseline |
|---|---|---|---|---|---|
| AOI01 Syapru Besi | 175 | 0.000 [0.00–0.00] n/a | 0.000 [0.00–0.00] n/a | 0.000 [0.00–0.00] n/a | n/a |
| AOI02 Timure | 125 | 0.000 [0.00–0.00] n/a | 0.000 [0.00–0.00] n/a | 0.008 [0.00–0.05] n/a | n/a |
| AOI03 Bidur (hold-out) | 2,133 | 0.226 [0.11–0.33] indistinguishable from chance | 0.345 [0.17–0.49] indistinguishable from chance | 0.417 [0.23–0.58] indistinguishable from chance | 97% (n=329) vs 54% |
| AOI05 Phosretar | 493 | 0.079 [0.02–0.18] indistinguishable from chance | 0.118 [0.04–0.26] indistinguishable from chance | 0.164 [0.06–0.33] indistinguishable from chance | 78% (n=36) vs 44% |

Verdict at 30 m: AOI01 n/a; AOI02 n/a; AOI03 indistinguishable from chance; AOI05 indistinguishable from chance. Association with damage points is not attribution to flooding. Every EMS scoring is listed in docs/validation_log.md; S1 parameters unchanged since tag detector-frozen.

## 5. Limitations

- Single Sentinel-1 track (asc85), 4 reference dates; the post scene is 2 days after the event, so a flash flood in a narrow gorge may already have drained.
- Only the valley floor is assessed (200 km², 90% usable). 92% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.
- Sentinel-2: 12% of the valley floor has clear post-event coverage and its status is null_not_calibrated, so S2 is excluded and the fused product equals the S1 product.
- No cause attribution: flood-like (water-like backscatter change), dark and bright classes are all surface change; this is exposure, not damage; bridges are exposed, never known to have failed.
- 30 m pixels mix narrow channels; OSM snapshot 2026-07-27 predates the event and rural areas are under-mapped, so missing buildings undercount exposure and missing tracks overstate cut-off (141 settlements have no pre-flood route).
- AI vs Sentinel-2 cannot arbitrate: S2 MNDWI agrees with the AI at precision 0.51 on the post date (20260827); S2 MNDWI agrees with the AI at precision 0.49 on the pre date (20260812). Agreement that does not change with the event says nothing about the event.
- EMSR927 GRA products held locally (checked 2026-10-11) contain landslide polygons and damage points, no flood-extent layer. The flood class is therefore not validated against EMS.

## 6. Next steps (in scope)

1. Add a second Sentinel-1 track or a closer post scene and rerun unchanged; the headline should stay inside the ranges above.
2. Check the 4 cut-off first-break points against field or imagery reports.
3. Refresh OSM after the event and rerun cut-off to separate missing roads from real loss.

## 7. Data sources

- Contains modified Copernicus Sentinel data 2026.
- Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- © OpenStreetMap contributors.
- European Union, Copernicus Emergency Management Service data (validation only).
- Sentinel-1 GRD (Copernicus Data Space Ecosystem), SNAP sigma0 terrain correction; OpenStreetMap snapshot 2026-07-27 (pre-event, ODbL v1.0)
- Sen1Floods11 v1.1, CC BY 4.0: Bonafilia et al. (2020), CVPR EarthVision workshop

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md). Educational prototype, not an operational tool.

# Situation Report — Trishuli / Bhote Koshi GLOF

> **PRELIMINARY** — generated 2026-10-06 from commit `a4f5529`. Numbers change if the detector or inputs change.

## 1. Situation

2026-08-26 flash flood (suspected GLOF), Trishuli / Bhote Koshi, Rasuwa, Nepal; Sentinel-1 2026-08-16 / 2026-08-28, Copernicus GLO-30, OSM. Detector status: **change_detected** (track asc85; VH robust-z change of pre, placebo, pre3, pre4 against post, thresholds 4 / 2.5, calibrated=True, null false-alarm max 0.035%). The mask is restricted to the HAND valley floor; the result is exposure to a detected mask, **not a validated flood extent**.

## 2. Detection signal

| VV change (post − pre), dB | n | p5 | p1 |
|---|---|---|---|
| all pixels | 4,113,397 | -2.91 | -4.30 |
| river, 60 m buffer | 61,080 | -3.64 | -6.22 |
| river, north (Rasuwa) half | 21,498 | -3.04 | -4.71 |
| river, south half | 39,582 | -3.95 | -6.91 |
| river shifted +1.5 km (control) | 61,084 | -3.24 | -4.74 |
| river shifted −1.5 km (control) | 61,079 | -3.03 | -4.46 |

River p1 -6.22 dB vs -4.60 dB for the controls (-1.62); p5 -3.64 vs -3.13. By reach: south half p1 -6.91 (-2.31), north half -4.71 (-0.11). The river reach has a lower-tail excess over the shifted controls: it is evidence of surface change along the reach, not by itself of flooding. The U-Net (Sen1Floods11) flags 5.03% of the corridor post and 5.05% pre: it does not separate the scenes and is not independent evidence.

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

Range = 3 thresholds × mask ±1 px × bridges fail/survive. All 4 first breaks: 4 debris; the detector observed 28%–55% of each cut-off route. Cut-off covers only the 305 assessable settlements; 18 of 20 hospitals were snapped to the road network.

## 4. Validation against Copernicus EMS (EMSR927)

Check only: EMS data is not an input to any number above. Reference: landslide polygons (observedEventA) and damage points; no flood-extent layer in the local GRA products. Domain: AOI minus notAnalysedA, restricted to pixels the detector observed. Chance: the mask's own blobs relocated at random (100 draws).

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

Verdict at 30 m: AOI01 n/a; AOI02 n/a; AOI03 indistinguishable from chance; AOI05 indistinguishable from chance. Association with damage points is not attribution to flooding. AOI03 was scored 4 times (docs/validation_log.md); S1 parameters unchanged since tag detector-frozen.

## 5. Limitations

- Single Sentinel-1 track (asc85), one pre/post pair; the post scene is 2 days after the event, so a flash flood in a narrow gorge may already have drained.
- Only the valley floor is assessed (200 km², 90% usable). 92% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.
- Sentinel-2 added nothing: coverage is about 12% and its null calibration failed, so S2 is excluded and the fused product equals the S1 product.
- No cause attribution: flood-like, dark and bright classes are all surface change; bridges are exposed, never known to have failed.
- 30 m pixels mix narrow channels; OSM snapshot 2026-07-27 predates the event and rural Rasuwa is under-mapped, so missing buildings undercount damage and missing tracks overstate cut-off (141 settlements have no pre-flood route).
- EMSR927 products held locally (GRA) contain no flood-extent layer: the reference is landslide polygons and damage points, so the flood class is not validated against EMS.

## 6. Next steps (in scope)

1. Add a second Sentinel-1 track or a closer post scene and rerun unchanged; the headline should stay inside the ranges above.
2. Check the 4 cut-off first-break points against field or imagery reports.
3. Refresh OSM after the event and rerun cut-off to separate missing roads from real loss.

## 7. Data sources

- Contains modified Copernicus Sentinel data 2026 (Sentinel-1 GRD, Copernicus Data Space Ecosystem)
- (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all rights reserved (Copernicus DEM GLO-30)
- (c) OpenStreetMap contributors, ODbL v1.0 (ohsome snapshot 2026-07-27, pre-event)
- Copernicus EMS Rapid Mapping, EMSR927 (validation only)
- Sen1Floods11 v1.1, CC BY 4.0: Bonafilia et al. (2020), CVPR EarthVision workshop

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md).

*Changelog: the `v0-baseline` run used post-event OSM and was discarded.*

# Situation Report — terai: Sentinel-1 change, event 2026-08-26

> **PRELIMINARY** — generated 2026-10-12 from commit `unknown` (git state unknown). Educational prototype, not an operational tool. Numbers change if the detector or inputs change.

## 1. Situation

Event date 2026-08-26, terai; Sentinel-1 2026-08-16 / 2026-08-28, Copernicus GLO-30, OSM. Sentinel-1 source: Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD) (cross-check only). Detector status: **no_significant_change** (track asc85; VH robust-z change of pre (2026-08-16), placebo (2026-08-04), pre3 (2026-07-23), pre4 (2026-07-11) against post (2026-08-28), thresholds 6 / 2.5, calibration target not met; minimum detectable area ≈ 17 km²). The mask is restricted to the HAND valley floor; the result is exposure to a detected mask, **not a validated flood extent and not damage**.

## 2. Detection signal

_Case-study evidence tables (Step 3 main-vs-tributary test) not available for this run: section skipped._

## 3. Exposure to the mask

| Item | Headline (base mask) | Scenario range |
|---|---|---|
| Flagged area | 0.00 km² (0.00 flood-like, 0.00 dark, 0.00 bright) | n/a |
| Buildings overlapping the mask | 0 (0 flood-like class, 0 other surface change) of 138,359 | n/a |
| Buildings within 30 m | 0 | n/a |
| Buildings with unknown status | 3,699 (3%) | n/a |
| Motorable road in mask | 0.0 km (0 segments) | n/a |
| Bridges exposed (not failed) | 0 of 276 | n/a |
| Settlements cut off (no path to a hospital) | 0 of 88 | n/a |
| Settlements degraded (≥2× and ≥2 km longer) | 0 | n/a |
| Settlements not assessed (no pre-flood route) | 1 | n/a |

Scenario ranges are n/a: the threshold-sensitivity runs were skipped (--profile fast). Cut-off covers only the 87 settlements with a pre-flood route; 36 of 36 hospitals were snapped to the road network.

## 4. Validation

_No Copernicus EMS products for this area in data/external: section skipped._

## 5. Limitations

- Sentinel-1 source: Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD). PC RTC gamma0 route: cross-check only. It failed the pre-registered route-equivalence test against the SNAP sigma0 case study (docs/validation_log.md, 2026-10-12), so these numbers are not the validated result.
- Calibration target not met: no detector threshold reached the 0.1% null false-alarm target in this area (largest grid value t_hi 6.0 used; null false-alarm maximum 0.20%). Minimum detectable area ≈ 17 km² (gate × assessed floor): a smaller event here would not be detected.
- Single Sentinel-1 track (asc85), 4 reference dates; the post scene is 2 days after the event, so a flash flood in a narrow gorge may already have drained.
- Only the valley floor is assessed (2864 km², 99% usable). 3% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.
- No cause attribution: flood-like (water-like backscatter change), dark and bright classes are all surface change; this is exposure, not damage; bridges are exposed, never known to have failed.
- 30 m pixels mix narrow channels; OSM snapshot 2026-07-01 predates the event and rural areas are under-mapped, so missing buildings undercount exposure and missing tracks overstate cut-off (1 settlement has no pre-flood route).

## 6. Next steps (in scope)

1. Add a second Sentinel-1 track or a closer post scene and rerun unchanged, with the threshold-sensitivity runs (--profile full) to get scenario ranges.
2. Refresh OSM after the event and rerun cut-off to separate missing roads from real loss.

## 7. Data sources

- Contains modified Copernicus Sentinel data 2026.
- Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.
- © OpenStreetMap contributors.
- Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD); OpenStreetMap snapshot 2026-07-01 (pre-event, ODbL v1.0)
- Sen1Floods11 v1.1, CC BY 4.0: Bonafilia et al. (2020), CVPR EarthVision workshop

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md). Educational prototype, not an operational tool.

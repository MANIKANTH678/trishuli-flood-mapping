# Situation report: Trishuli / Bhote Koshi, 2026-08-26

> PRELIMINARY, 2026-10-11, commit `c81474a` + uncommitted changes (DRAFT)

**Situation.** Flash flood (suspected GLOF) on 2026-08-26, Trishuli / Bhote Koshi, Rasuwa, Nepal. Sentinel-1 track asc85, 2026-08-16 / 2026-08-28: detector status **change_detected** (calibrated=True). Surface change was detected on the valley floor; it is **not attributed to flooding and not a validated flood extent**. Counts below are exposure to that mask. Flood-like (new open water) change is separable from the no-flood nulls.

| Key number | Headline | Scenario range |
|---|---|---|
| Flagged area | 3.14 km² | 1.66–5.48 km² |
| Buildings overlapping the mask (unknown status: 92%) | 556 (6 flood-like, 550 other change) | 244–1,078 |
| Motorable road in mask | 11.8 km | 6.4–22.0 km |
| Bridges exposed (not failed) | 20 of 385 | 12–30 |
| Settlements cut off (no path to hospital) | 4 of 446 | 2–12 |
| Settlements degraded | 0 | 0–1 |
| Settlements with no pre-flood route (not assessed) | 141 | n/a |

![map](situation_map.png)

**Limitations**

- Single Sentinel-1 track (asc85), one pre/post pair; the post scene is 2 days after the event, so a flash flood in a narrow gorge may already have drained.
- Only the valley floor is assessed (200 km², 90% usable). 92% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.
- No cause attribution: flood-like, dark and bright classes are all surface change; bridges are exposed, never known to have failed.
- Sentinel-2 added nothing: 12% of the valley floor has clear post-event S2 coverage and its status is null_not_calibrated (seed fraction 0.0006 vs gate 0.048), so S2 is excluded and the fused product equals the S1 product.

<small>Contains modified Copernicus Sentinel data 2026. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors. Educational prototype, not an operational tool.</small>

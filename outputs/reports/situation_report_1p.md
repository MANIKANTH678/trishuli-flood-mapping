# Situation report: Trishuli / Bhote Koshi flood, 2026-08-26

> PRELIMINARY, 2026-10-12, commit `98b5082` + uncommitted changes (DRAFT)

**Situation.** Event date 2026-08-26, Trishuli / Bhote Koshi, Rasuwa, Nepal. Sentinel-1 track asc85, 2026-08-16 / 2026-08-28: detector status **change_detected** (calibrated against pre-event nulls). Detected change on the valley floor is **not attributed to flooding, not a validated flood extent and not damage**. Counts below are exposure to that mask. Flood-like change (0.31 km² of water-like backscatter change) and surface change (2.29 km² dark, 0.54 km² bright) are each separable from all four pre-event nulls. An independent single-date water model could not separate the event from pre-event dates, and Sentinel-2 does not confirm open water.

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

- Single Sentinel-1 track (asc85), 4 reference dates; the post scene is 2 days after the event, so a flash flood in a narrow gorge may already have drained.
- Only the valley floor is assessed (200 km², 90% usable). 92% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.
- Sentinel-2: 12% of the valley floor has clear post-event coverage and its status is null_not_calibrated, so S2 is excluded and the fused product equals the S1 product.
- No cause attribution: flood-like (water-like backscatter change), dark and bright classes are all surface change; this is exposure, not damage; bridges are exposed, never known to have failed.

<small>Contains modified Copernicus Sentinel data 2026. Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. © OpenStreetMap contributors. European Union, Copernicus Emergency Management Service data. Educational prototype, not an operational tool.</small>

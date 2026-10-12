# EMSR927 inventory (accessed 2026-10-06)

Local products: Grading for AOI01 v1, AOI02 v2, AOI03 v1, AOI05 (files labelled v2, portal v3, identical); AOI03 Grading Monitoring 1 v1 in MON1_AOI03 (not used for headline).
No delineation / first-estimate / reference / monitoring products in data/external/EMSR927.
Layers used: areaOfInterestA, notAnalysedA (AOI03, AOI05 only), observedEventA, builtUpP.
observedEventA: event_type "6-Mass Movement", obj_desc "Landslide" in all AOIs.
Decision: no flood-extent layer in the downloaded GRA products; landslide polygons are the debris reference. Flood class is not validated against EMS.

Portal check (EMSR927 activation page, accessed 2026-10-06; activation status CLOSED):

| AOI   | Product              | Version | Delivered (UTC)  | Image acquisition (UTC)            | Local copy                                                                                                                            | Used in validation |
| ----- | -------------------- | ------- | ---------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| AOI01 | Grading              | v1      | 2026-08-27 19:03 | 2026-08-27 05:05                   | v1                                                                                                                                    | yes                |
| AOI02 | Grading              | v2      | 2026-08-28 17:10 | 2026-08-27 05:05                   | v2                                                                                                                                    | yes                |
| AOI03 | Grading              | v1      | 2026-08-29 02:57 | 2026-08-27 04:22, 2026-08-27 12:09 | v1                                                                                                                                    | yes (hold-out)     |
| AOI03 | Grading Monitoring 1 | v1      | 2026-08-31 01:07 | 2026-08-27 04:47, 2026-08-28 08:29 | downloaded to MON1_AOI03; 5 event polygons vs 2, 3,058 points vs 2,343 in v1 | no (sensitivity only) |                                                                                                                                | yes               |
| AOI04 | none published       | n/a     | n/a              | n/a                                | n/a                                                                                                                                   | n/a                |
| AOI05 | Grading              | v3      | 2026-09-04 10:42 | 2026-08-31 05:01, 2026-08-31 05:27 | vector files labelled v2, map v3; the gpkg downloaded from the portal Grading v3 card on 2026-10-06 is byte-identical to the local v2 | yes                |
| AOI06 | none published       | n/a     | n/a              | n/a                                | n/a                                                                                                                                   | n/a                |

Flood-extent reference: none. The portal lists only Grading and Grading Monitoring products (no delineation, first estimate or reference), checked on 2026-10-06.

EMS credit: European Union, Copernicus Emergency Management Service data (EMSR927, used for checking only).

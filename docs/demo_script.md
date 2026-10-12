# 3-minute demo script (no images of victims)

Route named on screen at every step. Validated numbers come from the **SNAP route** (Sentinel-1 GRD from CDSE, SNAP
sigma0). The Planetary Computer route (Sentinel-1 RTC, third-party processed from GRD) is shown only as a **cross-check**:
it failed the route-equivalence test (`docs/validation_log.md`, 2026-10-12). No photographs of people; maps and charts only.

| Time | Show | Say |
|---|---|---|
| 0:00-0:20 | Title, valley map (no photos) | 26 Aug 2026 flash flood, Trishuli / Bhote Koshi, Rasuwa. Question: where did the valley floor change, what is exposed, who lost road access to a hospital, from free satellite data only. |
| 0:20-0:50 | **Negative control** dashboard (same valley, event 2026-08-01; PC route, cross-check) | Same pipeline on a date with no flood: status `no_significant_change`, 0.00 km² in every class, and every downstream stage still ran. The detector can say "nothing here". |
| 0:50-1:50 | **Case study** dashboard (SNAP route). It opens zoomed on the flagged change. Toggle low/high scenarios, buildings, roads, bridges; click a cut-off settlement and its first-break marker | Status `change_detected`, calibrated against four pre-event nulls; minimum detectable area 0.21 km², the event is about 15× that. 3.14 km² flagged (0.31 water-like backscatter change, 2.29 dark, 0.54 bright), each class separable from the nulls. 556 buildings overlap (range 244–1,078); 4 of 446 settlements cut off from a hospital (range 2–12), of 305 assessable. Flagged pixels are drawn 2 px wider; numbers use the true mask. |
| 1:50-2:15 | `docs/judges_day.md` command line; Terai row of the report's robustness table | One command for a new area. In the Terai box no threshold met the false-alarm target: the report says "calibration target not met; minimum detectable area ≈ 17 km²" instead of claiming calibration. |
| 2:15-2:45 | Limitations (one-page situation report) | Exposure, not damage; valley floor only (unknown share shown); single track; no flood-extent reference (EMSR927 maps landslides); the AI water model does not confirm open water and has no labelled Himalayan test yet. |
| 2:45-3:00 | Attribution footer | The required Copernicus Sentinel, WorldDEM-30 and OpenStreetMap credits, Sen1Floods11, and the EMS credit (checking only). |

If asked to run live: run the PC route (`--s1-source pc`, about 15 min) and say on screen that it is a cross-check only.

EMS credit: European Union, Copernicus Emergency Management Service data (EMSR927, used for checking only).

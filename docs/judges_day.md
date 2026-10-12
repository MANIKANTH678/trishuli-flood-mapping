# Judges' day sheet (one page)

Educational prototype, not an operational tool. Everything below runs from the repo root.

## 1. Run a new area (headline route: CDSE + SNAP)

```
set COPERNICUS_USER=...            (environment only; never in a file)
set COPERNICUS_PASS=...
python -m src.run --bbox W,S,E,N --event-date YYYY-MM-DD --name <area> --profile fast --clean
```

- `--profile fast` skips Sentinel-2, the threshold-sensitivity runs and the AI layer but keeps the null-calibrated gate.
- A failed stage prints `resume with --from-stage <name>`; rerun the same command with that flag.
- A folder holding another run is refused; `--clean` archives it under `runs/<stamp>/` (never `models/`).
- Fewer than 3 reference dates means no null calibration: the report then says **UNCALIBRATED**.

## 2. No SNAP or CDSE login: the PC cross-check route

```
python -m src.run --bbox W,S,E,N --event-date YYYY-MM-DD --name <area> --profile fast --s1-source pc --clean
```

Planetary Computer Sentinel-1 RTC gamma0, streamed (no login, no SNAP, ~5 GB disk). OSM falls back to a dated Geofabrik
extract when `OHSOME_API_KEY` is not set (Nepal extract only: a box crossing into India is mapped on the Nepal side only).
Every output says **"PC RTC gamma0, cross-check route"**: present it as a cross-check, never as the SNAP headline.

## 3. Expected duration per stage (`outputs/timings.json`, seconds)

Measured on the Step 10 dry runs (Kaggle CPU, 4 cores, PC route, fast profile, 2026-10-12):

| Stage | Dry run 1: Trishuli box, 2026-08-01 | Dry run 2: Terai box, 2026-08-26 |
|---|---|---|
| select_s1 | 4 | 4 |
| osm (Geofabrik, 410 MB Nepal extract) | 126 | 109 |
| dem | 14 | 14 |
| pc_stack (5 dates × VV/VH) | 513 | 447 |
| geometry | 0 | 0 |
| hand | 19 | 73 |
| radar_mask | 53 | 50 |
| null_calibration | 21 | 15 |
| detect | 8 | 6 |
| fuse | 1 | 1 |
| damage | 16 | 8 |
| cutoff | 52 | 22 |
| dashboard | 10 | 3 |
| situation_map | 2 | 3 |
| report | 1 | 1 |
| **total** | **840 (14 min)** | **756 (12.6 min)** |

The SNAP route replaces `pc_stack` with download + SNAP + gridding of five GRD scenes (several GB); budget well over an hour
for it on a laptop and do not start it live unless it has been timed on that machine.

## 4. If something is down

- **CDSE down or slow:** use the PC route (section 2).
- **Everything online is down:** show the cached case study. `python -m src.run --restore runs/<stamp>` puts an archived run
  back; `outputs/dashboard/index.html` opens offline (Leaflet etc. are vendored; with no tiles choose "Plain background").
- **Sign-in-free fallbacks used:** Geofabrik for OSM (no ohsome key), PC for Sentinel-1, AWS Open Data for the GLO-30 DEM.

## 5. What to say

- Class 1 is **water-like backscatter change**, not open water. Outputs are **exposure**, not damage; bridges are **exposed**,
  not failed. Copernicus EMS (EMSR927) is used for checking only.
- Negative control (same valley, 2026-08-01, PC route): `no_significant_change`, all classes 0.00 km², every downstream stage
  completed with empty masks.

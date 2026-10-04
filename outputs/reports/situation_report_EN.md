# Situation Report — Trishuli / Bhote Koshi GLOF

> **PRELIMINARY** — generated 2026-10-04 from commit `459b759 + uncommitted changes`. Numbers will change if the detector or inputs change.

**Event:** 2026-08-26 flash flood (suspected GLOF), Rasuwa District, Nepal
**Status:** Post-event analysis. **On this Sentinel-1 pair, no flood signal could be detected.**

## 1. Situation

Copernicus EMS Rapid Mapping (EMSR927) mapped 3,816 damaged structures in four Areas of Interest (2,813 Destroyed, 354 Damaged, 649 Possibly damaged).

## 2. Key finding

On calibrated, terrain-corrected Sentinel-1 (σ⁰, Copernicus GLO-30), the 2026-08-16 / 2026-08-28 pair shows no detectable flood signal along the Trishuli or in the Rasuwa reach. **This pair cannot resolve the event; it does not show that no flood occurred.**

| VV change (post − pre), dB | n | median | p5 | p1 |
|---|---|---|---|---|
| all pixels | 4,113,397 | 0.00 | -2.91 | -4.30 |
| river, 60 m buffer | 61,080 | 0.02 | -3.64 | -6.22 |
| river, Rasuwa (north) half | 21,498 | 0.24 | -3.04 | -4.71 |
| river, south half | 39,582 | -0.10 | -3.95 | -6.91 |
| river shifted +1.5 km (control) | 61,084 | -0.08 | -3.24 | -4.74 |
| river shifted −1.5 km (control) | 61,079 | -0.08 | -3.03 | -4.46 |

A real flood over water would be expected to give a clearly negative river median. The Rasuwa half is no darker than the shifted controls.

The U-Net (Sen1Floods11) flags 5.03% of the corridor in the post scene and 5.05% in the pre scene; 21,020 px gained and 21,627 px lost. It cannot discriminate the two scenes, so it is **not** independent evidence either way.

## 3. Exposure to the detector's mask

The mask below is the thresholded dark tail of the VV change. It is **not a validated flood extent**; the figures show sensitivity of exposure to that mask.

| Item | Value |
|---|---|
| Flood mask | 5,802 px (5.22 km²) |
| Debris mask | 652 px (0.59 km²) |
| Buildings in mask | 991 flooded + 102 debris-affected (of 189,503) |
| Bridges in mask | 21 (of 385) |
| Settlements cut off | 4 of 446 (4 no path, 0 detour only; 20 hospitals) |

## 4. Comparison with EMSR927 damage points

Per AOI, the mask hit rate on EMSR927 damage points against a random mask of the same size placed on flat pixels inside the AOI:

| AOI | Damage points | Points in raster | Inside mask | Mask px in AOI | Flat px in AOI | Observed hit | Null (mean ± sd) |
|---|---|---|---|---|---|---|---|
| Syapru Besi | 433 | 433 | 0 | 0 | 163 | 0.000 | 0.000 ± 0.000 |
| Timure | 431 | 431 | 0 | 0 | 282 | 0.000 | 0.000 ± 0.000 |
| Bidur | 2,343 | 2,343 | 867 | 2,278 | 14,388 | 0.370 | 0.113 ± 0.010 |
| Phosretar | 609 | 581 | 99 | 2,544 | 13,058 | 0.170 | 0.091 ± 0.017 |

Where the mask has no or almost no pixels (see AOI rows), the miss is a coverage limit of the method, not a measured detection error. Where hit rates exceed the null, the mask is associated with damage in built-up lowlands; this does not distinguish flooding from other change.

## 5. Limitations

- The post scene is two days after the event; a flash flood in a narrow gorge may already have drained.
- 30 m pixels mix narrow channels; the slope filter removes almost all steep terrain.
- EMSR927 GRA products contain no flood-extent layer; validation is proxy only.
- The detector's threshold sits at its lower clip limit, so the mask is selected from noise-level change.
- Held-out U-Net IoU values come from an earlier run (Sen1Floods11 is not on disk).
- **OSM currency and completeness.** Infrastructure comes from the ohsome snapshot of 2026-07-27, the latest pre-event snapshot available (see `data/raw/osm/manifest.json`). Edits between 2026-07-27 and 2026-08-26 are not reflected, and OSM coverage of rural Rasuwa is incomplete: missing buildings undercount damage, and missing tracks can overstate cut-off.

## 6. Recommendations

1. Re-acquire with optical imagery (Sentinel-2, PlanetScope) or high-resolution SAR.
2. Task optical assets within 24–72 hours of future GLOF events.
3. Replace the threshold detector before reuse.

## 7. Data sources

- Sentinel-1 GRD (Copernicus Data Space Ecosystem), calibrated σ⁰, terrain-corrected with Copernicus GLO-30
- Copernicus EMS Rapid Mapping, EMSR927
- OpenStreetMap, ohsome snapshot 2026-07-27 (pre-event), ODbL
- Sen1Floods11 v1.1 (CC BY 4.0)

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md).

## Changelog

- The `v0-baseline` run used post-event OSM and was discarded.

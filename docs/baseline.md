## Previous run (superseded; not comparable to the rebuilt pipeline below)

- EMSR927 damage-point recall: 0.000
- Flooded buildings: 61,977
- Flood mask: 47 km²

## U-Net validation

- IoU 0.523 (mean of per-batch IoUs) and 0.574 (pooled)

## Rebuilt pipeline (ohsome pre-event OSM, snap bug fixed)

Generated 2026-10-04 from the rebuilt pipeline. Study area: bbox 84.95, 27.80, 85.55, 28.35 (Rasuwa corridor). OSM: ohsome API snapshot 2026-07-27, manifest in `data/raw/osm/manifest.json`.

| Metric                                    | New (ohsome pre-event, snap bug fixed) |
| ----------------------------------------- | -------------------------------------- |
| Buildings total                           | 189,503                                |
| Flooded / debris-affected buildings       | 991 / 102                              |
| Roads (excl. bridges) / flooded           | 14,151 / 83                            |
| Bridges / flooded                         | 385 / 21                               |
| Hospitals / settlements                   | 20 / 446                               |
| Settlements snapped to road graph         | 444                                    |
| Reachable pre / post flood                | 379 / 375                              |
| Not connected to any hospital (pre-flood) | 65                                     |
| Cut off by flood mask                     | 4                                      |
| Flood mask                                | 5,802 px (5.22 km²)                    |
| EMSR927 damage-point recall               | 966 of 3,816 (25.3%)                   |

Notes:

1. The earlier cut-off results (431/430/1 and 444/444/0) are invalid because of a snapping defect in `cutoff_v2.py`, fixed in commit fb7c624. Damage figures were unaffected.

2. The old and new columns are not comparable: the bbox was tightened to the Rasuwa corridor, OSM changed from a post-event download to a pre-event snapshot, and the flood mask was rebuilt.

3. The flood mask is unvalidated. The 966 damage points inside it are all at Bidur (867) and Phosretar (99); none fall in Syapru Besi or Timure. Inside the Bidur and Phosretar AOIs, about 97-98% of the mask area lies on mapped landslide polygons, so the recall is not evidence of flood detection (FINAL_REPORT section 4.4).

4. The 4 cut-off settlements are all in the far north near the border crossing and appear to be Tibetan-side villages (to be verified). 67 settlements have no pre-flood route (2 unsnapped, 65 on road fragments with no hospital connection); 104 road and bridge segments are removed by the mask.

## Geolocation, v0 vs new (indicative; measured relative to the new product)

- Pass: ASCENDING, relative orbit 85 (from align_v2_checks.py; all four scenes).
- Look geometry from the annotation XML (src/analysis/geometry.py): Ascending, heading
  -12.57 deg, incidence 38.77 deg at the bbox centre, toward-sensor azimuth 257.4 deg. The
  fitted relief azimuth (~260 deg) agrees. The fitted relief slope (0.90 m per m) is below
  the expected 1/tan(38.77 deg) = 1.25, so the per-band fit is qualitative only.
- v0 = GCP+affine geocoding, no terrain correction. Per-elevation-band correlation
  (tools/geoloc_by_elevation.py, 5 bands, 400-4000 m) fits two components, signs fixed
  (rows +south, cols +east):
  - height-dependent displacement ~0.9 m per m of height toward az ~260 deg (toward the
    ascending sensor);
  - rigid offset of about 3.5 km east and 0.4 km north (az ~84 deg). Cause not identified.
- Bulk single-shift result (690 m S, 3930 m E, 4.9 sigma) mixes both terms; not a valid offset.
- The fit cannot separate a rigid error in v0 from one in the new product. New 10 m product:
  river mean -10.47 dB vs scene -8.14 dB at zero offset; best-fit shift <= 50 m (OSM line error
  is comparable).
- NOT recorded: "v0 offset ~3 km" from the river check (result sat on the search boundary).

## Terrain and radar-geometry baselines

HAND (hand.py, 30 m): <=15 m 4.0%, <=30 m 6.2%, <=60 m 10.1% of valid pixels.
Radar mask (radar_mask.py, scene-wide, incidence 38.77 deg): ok 74.1%, layover 5.4%, shadow 0.5%, cast shadow 0.4%, poor local incidence 19.6%.

Note: hand.py carries the np.in1d shim for NumPy 2.5; the committed code includes it.

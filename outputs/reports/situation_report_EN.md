# Situation Report — Trishuli / Bhote Koshi GLOF

**Event:** 26 August 2026 flash flood (suspected GLOF), Rasuwa District, Nepal
**Report date:** 2026-10-02
**Issued by:** Trishuli Flood Damage Mapping project (Track B, Multimodal AI Hackathon 2026)
**Status:** Post-event analysis — **negative-result on satellite flood detection**

---

## 1. Situation

On 26 August 2026 a debris-laden flash flood struck the Bhote Koshi and
Trishuli river corridor draining south from the Nepal–China border. The
Copernicus EMS Rapid Mapping service was activated (EMSR927) and mapped
building damage in four Areas of Interest (AOIs):

- **AOI01 Syapru Besi** (Rasuwa) — 433 damaged structures
- **AOI02 Timure** (Rasuwa) — 431 damaged structures
- **AOI03 Bidur** (Nuwakot) — 2,343 damaged structures
- **AOI05 Phosretar** (Chitwan edge) — 609 damaged structures

Total: **3,816 damaged structures** (2,813 Destroyed, 354 Damaged, 649
Possibly damaged).

## 2. Key finding

**The available Sentinel-1 SAR imagery does not contain the flood signal.**

- Pre-event: 2026-08-16, post-event: 2026-08-28 (relOrbit 85, ascending).
- Median VV backscatter change across all four AOIs: **−0.31 to +0.41 dB**.
  A real flood over water produces −5 to −10 dB. The signal is within noise.
- A U-Net segmentation model trained on Sen1Floods11 independently predicts
  **zero flood pixels** across the Rasuwa corridor.

Two independent methods converge on the same conclusion. The pipeline is
correct; the data does not resolve the event.

## 3. What we produced

| Deliverable | Content | Confidence |
|---|---|---|
| Flood mask | 47 km² scattered wet terrain | ⚠️ **not the GLOF** |
| Affected bridges | 98 bridge features | ⚠️ mask-driven |
| Affected buildings | 154,022 features | ❌ **16× overcount** vs EMSR927 |
| Hospital cut-off | 13 settlements with >3× detour | ⚠️ mostly sub-km artifacts |
| U-Net | IoU 0.523 (val), 0.554 (proxy-Himalaya) | ✅ model is real |

## 4. Limitations

- Sentinel-1's 12-day repeat and 30 m resolution cannot resolve a fast-draining
  GLOF in a 30–50 m gorge.
- The ascending pass illuminates the valley obliquely; deep N–S gorges are
  partly in radar shadow.
- EMSR927 GRA products contain no flood extent layer — validation is proxy
  (building damage points and landslide overlap).
- OSM snapshot is post-event (2026-09-30), contaminating the pre-flood
  infrastructure baseline.

## 5. Recommendations

1. Re-acquire with optical imagery (Sentinel-2, PlanetScope) for sediment
   plumes, or with high-resolution SAR (TerraSAR-X) to resolve the channel.
2. Try the descending-pass Sentinel-1 scenes (relOrbit 121 or 19) if a
   shorter revisit becomes available.
3. For future GLOF events, task optical assets within 24–72 hours — the
   Sentinel-1 repeat cycle is too slow.
4. Fix the debris-mask classifier before re-use (currently speckle-dominated).

## 6. Data sources

- Sentinel-1 GRD (Copernicus Data Space Ecosystem) — relOrbit 85, ascending.
- Copernicus EMS Rapid Mapping — activation EMSR927.
- OpenStreetMap (ODbL) — buildings, roads, hospitals, settlements.
- Copernicus DEM / SRTM — 30 m slope mask.
- Sen1Floods11 v1.1 (CC BY 4.0) — U-Net training.

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md).
Full analysis: [FINAL_REPORT.md](../../FINAL_REPORT.md).

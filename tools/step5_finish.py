from pathlib import Path

def add(path, marker, text):
    p = Path(path)
    s = p.read_text(encoding="utf-8") if p.exists() else ""
    if marker in s:
        print(path, "already updated"); return
    p.write_text(s.rstrip("\n") + "\n\n" + text.strip("\n") + "\n", encoding="utf-8"); print(path, "updated")

add("run_all.sh", "s2_search", """
# Step 5: Sentinel-2 branch and fusion (order: detect, s2_detect, fuse, damage)
python -m src.fetch.s2_search --bbox "$BBOX" --event-date "$EVENT_DATE"
python -m src.processing.s2_ingest --bbox "$BBOX" --epsg "$EPSG" --dates 2026-06-18,2026-07-05,2026-08-11,2026-08-12,2026-08-27,2026-09-08,2026-09-13,2026-09-20,2026-09-21
python -m src.analysis.s2_detect --event "$EVENT_DATE"
python -m src.analysis.fuse
""")

add("ATTRIBUTION.md", "Earth Search", """
## Sentinel-2 access (Step 5)
Sentinel-2 L2A scenes were found and read through the Earth Search STAC API (Element 84), a mirror of Copernicus Sentinel-2 L2A data. The data are the same Copernicus Sentinel-2 products, so the Sentinel attribution above is unchanged.
""")

add("README.md", "Step 5: Sentinel-2", """
## Step 5: Sentinel-2 branch and fusion
**Method.** Sentinel-2 L2A bands are read by window and cloud-masked with SCL at 10 m (classes 0, 1, 2, 3, 8, 9, 10, 11, cloud dilated 3 px, turbid water kept via MNDWI > 0.1). NDVI, MNDWI and BSI are averaged to the 30 m grid. The reference is the per-pixel median of pre-event dates, the post-event composite is the earliest clear observation within 30 days, and scores are robust z-values against elevation-stratified hillslope controls. The threshold comes from leave-one-out nulls over the pre-event dates. Fusion writes class, source and confidence layers.

**Result.** The S2 branch is inconclusive and contributes nothing to the fused product (status null_not_calibrated). Post-event floor clear fraction was 12.4% (5.1% over all valid pixels), and the leave-one-out false-alarm rate was 1.6-5.4% across the threshold grid against alpha = 0.1%, so no threshold passed. The fused product is therefore identical to the S1 v1 detector output. Pre dates: 2026-06-18, 07-05, 08-11, 08-12. Post dates: 2026-08-27, 09-08, 09-13, 09-20, 09-21.

**EMSR927 check (S1 v1 = fused).** Share of EMS damage points in the assessed domain / point recall within 100 m / landslide precision, recall, IoU:
- AOI03 (hold-out): 91% / 52% / 0.93, 0.17, 0.17
- AOI05: 85% / 24% / 0.99, 0.24, 0.24
- AOI02: 29% / 2% / no detections
- AOI01: 40% / 0% / no detections

**Limitations.** Monsoon cloud limited S2 coverage. The S2 null calibration failed. Crop phenology can mimic scars on farmland. 30 m aggregation loses S2 resolution. The upstream gap (damage on terraces and slopes above the 30 m floor in AOI01 and AOI02) remains open; the next lever is the descending-track search.

**Disclosures.** EMS data were used to diagnose domain coverage (design only). AOI03 was scored three times: v1, an empty-S2 fusion run identical to v1, and a pre-gate S2 run; detector numbers did not change and nothing was tuned on it. The null-calibration gate was added after viewing EMS results (tuned on EMS). Tags s2-frozen to s2-frozen-4 record the code states; the pre-gate EMS outputs are kept as *_pregate_vs_emsr927.json and are superseded.
""")
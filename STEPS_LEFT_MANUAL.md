# What these files do NOT do (needs you)

1. **8C hand-labelled chips**: pick ~20 points BEFORE looking at predictions (main stem, tributaries, hillside shadow), label on clear 27 Aug S2, two annotators on a subset. Then `python -m src.modeling.evaluate --extra <chips_dir>`. State that the CI is wide.
2. **8D wording**: in README + MODEL_CARD, replace "proxy-Himalaya" and the 0.000 figure with seed table (outputs/diagnostics/seed_summary.md), class_nulls verdict (event > 3x max null?), ai_vs_s2 as *agreement, not accuracy*, and "detects open water only".
   - If flood_water is NOT separable, write: "the event signal is surface change, not open water".
3. **flood_path start points**: edit the two `--start lon,lat` in run_step8_9.bat to a point on the upper Bhote Koshi and one on a tributary inside your bbox. Check: path follows OSM river within 1-2 px; Syapru Besi, Timure, Bidur, Phosretar appear in downstream order.
4. **6-page report** (9.4) and **README quick start + 3-min video** (9.5).
5. **Commit** (9.6), then run `situation_report.py --final` only on a clean tree.

Install once: `pip install folium pysheds markdown pypdf`

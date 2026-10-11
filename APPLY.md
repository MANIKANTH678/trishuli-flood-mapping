# Steps 8-9: drop-in files for the trishuli-flood-mapping repo

Copy this folder over the repo root (paths match the repo), then in cmd from the repo root:

    run_step8_9.bat            full run (CPU parts + GPU seed training only if seeds are missing)
    run_step8_9.bat label      also opens the chip labeller (annotator A, then B on 8 chips)
    run_step8_9.bat label push and push after the commit

New: tools/class_nulls.py, seed_summary.py, ai_vs_s2.py, select_himalaya_points.py, make_himalaya_chips.py, label_chips.py,
chip_agreement.py, flood_path_check.py, make_scenario_figure.py, write_step8_docs.py, build_report.py, apply_patches.py,
src/report/pdf_gate.py, docs/demo_script.md, data/external/himalaya_chips/points.csv (pre-registered; do not edit).
Replaced: src/analysis/flood_path.py (NumPy-2 fix for pysheds, adds name_en), src/report/dashboard.py (CartoDB needs a key now:
OSM + satellite basemap; class-null line), src/report/situation_report.py (verbatim attribution, class-null line).
Delete the stray file "tools/make_himalaya_chips.py points.csv" (a filename with a space).
Chrome or Edge is used for PDFs and the screenshot; set CHROME=<path> if it is installed elsewhere.

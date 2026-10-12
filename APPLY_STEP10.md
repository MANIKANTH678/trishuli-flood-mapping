# Step 10: drop-in files for the trishuli-flood-mapping repo

Copy this folder over the repo root (every path matches the repo). Then, in cmd from the repo root:

    run_step10.bat            apply, regenerate the deliverables from the JSON outputs, run pytest, write the checks
    run_step10.bat push       same, then commit and push

`run_step10.bat` does, in order (it stops at the first failure):

1. installs the few packages the new code uses (markdown, pypdf, pysheds, folium 0.20.0, pystac-client, planetary-computer, odc-stac, osmium);
2. copies `outputs\ai\smp_resnet34\model.pt` to `models\flood_unet_resnet34.pt` (+ `threshold.json`) and writes the float16 copy
   `models\flood_unet_resnet34_fp16.pt` with `tools\export_fp16.py --check` (49 MB, under GitHub's 100 MB limit; the fp32 copy is git-ignored);
3. `git rm` on `src\report\dashboard_full.py` (the retired static page) and `tests\test_run_all_order.py`; deletes `outputs\dashboard.html`,
   `outputs\reports\project_preview.html` and the stray `tools\make_himalaya_chips.py points.csv`;
4. checks `.gitignore` no longer ignores `src/config.py` (it now reads credentials from the environment only) and stages it;
5. regenerates `outputs\dashboard\index.html`, the situation reports (EN, NE, one page), the Step 8 blocks in README / MODEL_CARD /
   FINAL_REPORT, `docs\REPORT.md/.pdf`, and `outputs\reports\dashboard.png` (if playwright is installed);
6. runs pytest into `pytest_step10.txt`;
7. runs the reviewer's stale-text findstr into `grep_stale_laptop.txt` (only `docs\validation_log.md` may hit: it is append-only history);
8. writes `requirements_lock_win.txt` (pip freeze) so the few `==X.*` lines in requirements.txt can be pinned exactly;
9. prints `git log --all --oneline -- src/config.py`.

## What changed

- **Attribution:** `src/report/attribution.py` holds the exact brief strings + the EMS credit; dashboard, situation reports, `docs/REPORT.md`,
  README and ATTRIBUTION.md use it; `tests/test_attribution.py` checks every deliverable, and the EMS credit wherever EMSR927 appears.
- **Wording:** the reviewer's class-null sentence everywhere; the withdrawn "open water" phrasing removed from the class-null line (test_no_stale_claims checks it);
  AI-vs-S2 moved out of the headlines to a limitation line; Bolivia quoted with its chip CI 0.46–0.80.
- **Dashboard:** `src/report/dashboard.py` is the only dashboard. Text from JSON, scenario / unobservable / flood-path layers,
  556 (244–1,078) overlapping buildings and 92% unknown status, disclaimer, dated EMSR927 wording, vendored Leaflet etc.
  (`src/report/vendor/` -> `outputs/dashboard/vendor/`), plain-background fallback with a tile-error note.
- **Flood path:** name:en before name, "within the study area", main stem + tributary runs.
- **Chips:** `tools/chip_clear.py`; 0 of 20 chips pass the 70% clear rule on 27 Aug and 0 of 20 on 12 Aug (pre-event chips cut with
  `tools/make_himalaya_chips.py --split pre`). Any chip result is **qualitative only**. Rules: `docs/chip_protocol.md`.
- **Hardening:** relaxed 6/12-day gates (warnings; orbit/pass still fatal), `src/fetch/select_s1.py` (+ test), selection-driven
  `fetch_sentinel1.py` with lazy env credentials, `src/config.py` reads `run.json`, optional case-study sections, `src/run.py`
  (fail-fast, timings, resume, dirty-folder refusal, `--clean` never touches `models/`), `run_all.sh` is a thin wrapper,
  `models/` + float16, pinned requirements, `docs/judges_day.md`.
- **PC cross-check route:** `python -m src.run ... --s1-source pc` (Planetary Computer Sentinel-1 RTC gamma0, no login, no SNAP;
  `src/processing/pc_stack.py`); OSM falls back to a dated Geofabrik extract without an ohsome key (`src/download/osm_geofabrik.py`).
  Outputs say "PC RTC gamma0, cross-check route"; never the SNAP headline.

## Still yours to do

- Run `run_step10.bat`, read `pytest_step10.txt` and `grep_stale_laptop.txt`.
- Chip labelling (humans only): with 0 chips passing the clear rule, report the chips as qualitative only.
- Paste the exact versions of the `==X.*` packages from `requirements_lock_win.txt` into `requirements.txt`.
- Push, then the clean-clone test from REVIEW.md 10.5.

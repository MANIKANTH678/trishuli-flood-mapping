# Applying Step 11 (trishuli-flood-mapping)

Built in the sandbox on 2026-10-12 against the laptop repo as synced to Drive: local `main` = `bf89060` ("Step 10 tidy"),
one commit after the pushed `42925be`. Only new or changed files are in `repo\`, at their repo paths.

## Run (Windows cmd)

```
cd <where you unzipped step11.zip>
set "COPERNICUS_USER=you@example.com"
set "COPERNICUS_PASS=your-password"
run_step11.bat C:\path\to\trishuli-flood-mapping clone
```

| Mode | What it does |
|---|---|
| (none) | copies `repo\` over the repo; `git rm` the stale `outputs/dashboard.html` and `outputs/doc_backups/dashboard_full.py.final.bak` (both still tracked at HEAD and carrying withdrawn wording); writes `outputs\step11_git_grep.txt` (`git status --short`, `git rev-parse --short HEAD`, the reviewer's `git grep ... HEAD`, `git log -3`); compares the six new pins with `pip freeze`; regenerates dashboard, situation reports and the 6-page report; runs pytest into `outputs\step11_pytest.txt` and stops on a failure |
| `clone` | + clean `git clone` of `origin` into `%TEMP%\trishuli_step11_clone`, Step 11 `src\`, `tools\`, `models\` copied in, then `python -m src.run --bbox 84.95,27.80,85.55,28.35 --event-date 2026-08-26 --name trishuli_snap_clean --profile fast` (CDSE + SNAP). Saves `outputs\step11_snap_timings.json`, `step11_snap_run.json`, `step11_snap_detect_asc85.json`, `step11_snap_run.log`. Needs ~40 GB free on the `%TEMP%` drive and SNAP `gpt` (or `set "GPT=..."`). |
| `clone cache` | + copies `data\raw\sentinel1\<split>\*.zip` from the repo into the clone first (skips the multi-GB download; the reviewer accepted cached scenes). If `src.run` then says "stale file", run `clone` without `cache`. |
| `push` | + `git add` of explicit Step 11 paths, commit, push; re-runs the grep on the new HEAD; tags `v1.0-submission` and pushes the tag **only if `git status --porcelain` is empty**, then runs `situation_report.py --final --one-page`. |

Run `clone` first and check the timings, then `push` (the push flag is `set "PUSH=1"` with quotes; the Step 10
trailing-space bug is fixed).

## What changed (review items)

1. **Route equivalence: FAIL** (rule in `docs/validation_log.md` 17:35 IST, before the run). PC flagged 3.53 vs SNAP
   3.14 km² (pass), IoU 0.362 (pass), bright class not separable on PC (2.5×) vs separable on SNAP (5.9×): fail. PC route
   labelled "cross-check only" in code (`src/config.py`, `src/run.py`, `src/processing/pc_stack.py`,
   `src/report/textbits.py`), README, report, dashboard, situation report, `docs/judges_day.md`, `docs/demo_script.md`.
   Sources line: "Sentinel-1 RTC (Planetary Computer sentinel-1-rtc, third-party processed from GRD)".
   `outputs/validation/route_equivalence.json`.
2. **Stack guards:** reviewer's time-of-day lines in `src/processing/check_stack.py` plus a mixed-platform warning;
   the same guards in the PC/CDSE selection (`src/fetch/select_s1.py` -> `src/processing/stack_guards.py`, recorded in
   `selection.json` as `acquisitions` / `warnings`). Dry run 1's 06-22 reference is Sentinel-1A (others Sentinel-1D, same
   relative orbit 85): `outputs/validation/dry_runs.json`.
3. **Calibration honesty:** module-level `calibration_flags()` in `src/analysis/detect.py` (reviewer's code), called by
   `detect.py`; `min_detectable_km2` in the detect JSON; reviewer's test verbatim (`tests/test_calibration_flags.py`).
   Report, dashboard and situation reports (EN + NE) say "calibration target not met; minimum detectable area ≈ N km²".
   Terai regenerated: `outputs/dryruns/terai/`. Case-study `detect_asc85.json` gained the three fields (same function,
   values unchanged otherwise).
4. **validation_log:** dated SUPERSEDES entry (verbatim), the route rule and result, the chip path-1 result and the path-2
   amendment (verbatim, timestamped, before labelling).
5. **Report template:** zero-count sentences omitted, plurals, "second track" sentence only with real scenario ranges, a
   one-scenario "range" shown as n/a, GRD/RTC label (`src/report/textbits.py`, tested in `tests/test_textbits.py`).
6. **Dashboard:** opens on the flagged pixels (`fit_bounds`, padding 40), 2-px dilated display copy (numbers use the true
   mask), radar-unobservable off by default, collapsible `<details open>` summary, "of 305 assessable" computed.
7. **Himalayan chips:** `tools/chip_windows.py` (reviewer's code + 4 bug fixes listed in its docstring): 27 Aug main 1/8,
   trib 0/8, hill 1/4; 12 Aug main 0/8, trib 0/8, hill 2/4 = 4 < 8, so **path 2**: amendment logged, metrics tool
   `tools/himalaya_path2.py` (labelled-pixel IoU, pixels per chip, chip bootstrap CI, A/B on the first 8 chips; pre-event
   chips with `--chips data/external/himalaya_chips_pre --tag pre`). Path-3 fallback figure
   `outputs/figures/himalaya_example_panels.png` (first six chips in file order; S2, S1, model probability). **Label the
   chips before opening that figure.**
8. **Release hygiene:** `LICENSE` (MIT, code only), six pins exact (newest release of each declared series; no laptop
   lock file was available, so step 4 of the runner prints any difference), README quick start / env vars / routes /
   stage table, `docs/qa_sheet.md`, `docs/demo_script.md`, report sections on the route test, dry runs and Terai MDA.
9. `docs/organiser_question.txt`: send it yourself; record the answers in README ("Answers: pending").

## Still for Bobby

- Run `run_step11.bat <repo> clone` and send `outputs\step11_snap_timings.json` (+ `step11_git_grep.txt`).
- Send `docs/organiser_question.txt`; put both answers in README.
- Label the 20 post-event chips (clear pixels only, cloud/shadow = −1; annotator B the first 8), and the pre-event chips
  separately, then `python tools/himalaya_path2.py` and `python tools/himalaya_path2.py --chips data/external/himalaya_chips_pre --tag pre`.
- `run_step11.bat <repo> push` once the tree is clean, for the `v1.0-submission` tag.

# Dry-run evidence (PC route, cross-check only)

- `negative_control/`: bbox 84.95,27.80,85.55,28.35, event 2026-08-01. Kaggle kernel pagoluvijay/trishuli-step10-dryruns v2
  (Step 10 code, 2026-10-12). `detect_asc85.json` predates Step 11, so it has no `min_detectable_km2`: gate × floor =
  0.000865 × 199.87 km² = 0.173 km² (alpha met).
- `terai/`: bbox 84.3,26.9,84.9,27.4, event 2026-08-26. Inputs from the same Kaggle run, repeated in the sandbox; Step 11
  re-ran `detect` onwards from the saved null calibration with the Step 11 code: `calibrated: false` (no threshold met the
  0.1% target), `min_detectable_km2: 17.37`. The situation reports were regenerated with the Step 11 templates
  (the header says "commit unknown" because the sandbox copy has no git).
- Platform / orbit / time table for every reference and post date: `outputs/validation/dry_runs.json`.
- `trishuli_pc_case_study/`: the Step 11 route-equivalence run (sandbox, PC route, case-study bbox and event; Step 10 detect code, so no `min_detectable_km2`: 0.00236 × 200.3 km² = 0.47 km²). Compared in `outputs/validation/route_equivalence.json`.

# Validation log: EMS (EMSR927) scorings

EMS is used for checking only. Thresholds come from the null, not from EMS.

| Scoring | Commit | What was scored | What changed afterwards |
|---|---|---|---|
| S1 detector, recall by AOI | ea4d310, c0ee96c (last commits that changed the EMS output files) | S1 flood mask vs EMSR927 damage points, plus random-mask null | nothing; S1 numbers identical across all runs |
| S2/fused, first check | not recorded as a commit; run from the working tree | EMS check on S2/fused, run before the null gate existed | null gate added; first commit containing it is bb783ff (s2-frozen-3) |
| S2/fused, after gate | not recorded as a commit; run from the working tree | same check with S2 gated on null calibration | calibrated flag fixed in 377b1ec (s2-frozen-4 originally pointed here) |

Tags: s2-frozen, s2-frozen-2, s2-frozen-3 and s2-frozen-4 exist. s2-frozen-4 is final and has been moved to the last commit of Step 5; no further numbered tags will be added.

Disclosure: the first EMS check on S2/fused ran before the null gate was added. The gate is conservative and does not depend on EMS values, and S1 numbers are identical across all runs. AOI03 remains the hold-out and is touched only for the final run.

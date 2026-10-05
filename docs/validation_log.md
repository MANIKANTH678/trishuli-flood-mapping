# Validation log: EMS (EMSR927) scorings

EMS is used for checking only. Thresholds come from the null, not from EMS.

| Scoring | Commit | What was scored | What changed afterwards |
|---|---|---|---|
| S1 detector | (fill from git log above) | S1 recall by AOI | none; S1 numbers identical across all runs |
| S2/fused, first check | 5542e38 / 5321bdb (s2-frozen, s2-frozen-2) | EMS check on S2/fused, run before the null gate existed | null gate added in bb783ff (s2-frozen-3) |
| S2/fused, after gate | bb783ff (s2-frozen-3) | same, gated on null calibration | calibrated flag fixed in 377b1ec (s2-frozen-4) |

Disclosure: four s2-frozen tags exist. The gate is conservative and does not depend on EMS values. AOI03 remains the hold-out and is touched only for the final run.

Status: written after the first event run (step3_event.json already generated).
The file was empty when the results were written. Not pre-registered.
The event run is exploratory. The parameter values below restate the defaults in
src/analysis/zscore.py used for that run; whether they were chosen before the
run is not recorded. Placebo and later runs are tested against these criteria.

## Criteria for subsequent runs

Observability

- Observable fraction of the main-stem floor >= 0.80. Observable means valid:
  finite change in both polarizations and radar-mask class ok.

Signal (VV and VH, both required)

- The 2.5th percentile of the main-stem minus tributary-floor difference in the
  strongly negative fraction is > 0, in both VV and VH.

Falsification check

- The 2.5th to 97.5th percentile interval of the main-stem minus
  tributary-floor difference in the strongly positive fraction includes 0, in
  both VV and VH.

Uncertainty

- Block bootstrap: 2 km blocks, 2,000 replicates, seed 0. Main-stem and
  tributary-floor blocks are resampled separately. Interval = 2.5th and 97.5th
  percentiles.

Definitions

- z: robust z (median/MAD) of the change between the two scenes, standardized
  per 250 m elevation band against the hillslope control (HAND >= 100 m). The
  hillslope control is the normalization baseline, not a test population.
- Strongly negative / positive: z < -3.5 / z > 3.5 in a connected patch of
  at least 8 px.
- Main floor: HAND <= 30 m, within 1500 m of the main stem.
  Tributary floor: HAND <= 30 m, at least 2500 m from it.
  All populations use valid pixels only.

Placebo

- The same analysis on a pair that does not span the event (same orbit, 12-day
  gap, same season) must fail the signal criteria. If more than one such pair
  is available, all must fail. If a placebo pair passes, the event result is
  not attributed to the event.

Interpretation limit

- Passing these criteria means main-stem darkening that the controls
  do not share. It does not separate flooding from debris, sediment
  or channel change.

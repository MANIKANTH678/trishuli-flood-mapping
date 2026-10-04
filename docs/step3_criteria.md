## Criteria for subsequent runs

Observability

- Observable fraction of the main-stem floor >= <MIN>.

Signal (each polarization, VV and VH)

- Lower bound of the 95% CI on the main_floor negative excess over
  trib_floor is > 0.
- Lower bound of the 95% CI on the main_floor negative excess over
  hillslope_ctrl is > 0.

Falsification check

- The positive-tail excess CI (main_floor vs controls) includes 0.

Uncertainty

- Bootstrap resamples at segment level (main-stem OSM segments).
  A pixel-level bootstrap is reported as optimistic.

Definitions

- z cutoff for frac_neg and frac_pos: <CUTOFF>.
- Controls: trib_floor, hillslope_ctrl.

Interpretation limit

- Passing these criteria means main-stem darkening that the controls
  do not share. It does not separate flooding from debris, sediment
  or channel change.

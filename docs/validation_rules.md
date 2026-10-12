# Validation rules (EMSR927, check-only)
Written 2026-10-06, after the first run. The verdict logic below was implemented in
src/validation/emsr927_validate.py before that run; this file documents it.

- Domain: assessed domain = AOI minus notAnalysedA, restricted to detector-observable pixels. Full-AOI numbers are a floor.
- Reference: landslide polygons (observedEventA) and builtUpP damage points. No flood-extent layer in the downloaded GRA products.
- Verdict per tolerance (0/30/60/100 m):
  - above chance: CI lower bound > chance mean + 2 sd
  - below chance: CI upper bound < chance mean - 2 sd
  - otherwise: indistinguishable from chance
- CI: 2,000-resample block bootstrap over 1 km blocks. Chance: 100 relocations of the mask's own blobs.
- No tuning on these results. Detector frozen at tag detector-frozen.

EMS credit: European Union, Copernicus Emergency Management Service data (EMSR927, used for checking only).

# Q&A sheet (judging day)

Short, honest answers. Every number is in a file named in brackets. Educational prototype, not an operational tool.

## 1. "What is your flood-extent reference?"
There is none. The Copernicus EMS activation EMSR927 products we hold are grading maps: landslide polygons
(`observedEventA` = 6-Mass Movement / Landslide in all four AOIs) and building damage points, no flood-extent layer
[`docs/ems_inventory.md`]. So class 1 is reported as **water-like backscatter change**, not a validated flood extent, and
EMS is used for checking only, never as an input or for tuning. What we can show instead: the change is separable from
four pre-event nulls under a rule written before the run [`outputs/validation/class_nulls.json`].

## 2. "AOI05 looks below chance?"
An early script (`null_recall_aoi.py`) said AOI05 was below its null (z ≈ −2.9) and AOI03 above. That null scattered single
pixels, so its variance was far too small; the finding is **withdrawn** [`docs/validation_log.md`, Step 7]. With the
blob-relocation chance model and 1 km block-bootstrap CIs, damage-point recall is **indistinguishable from chance** in both
scored AOIs at every tolerance: AOI05 8% [2–18%] vs chance 8% at 0 m, 0.118 [0.04–0.26] at 30 m; AOI03 (hold-out)
23% [11–33%] vs 9% at 0 m [`outputs/validation/emsr927_validation.json`]. We do not claim the detector finds EMS damage.

## 3. "Does the AI confirm open water?"
No, and we say so. The single-date water model (ResNet34 U-Net, Sen1Floods11) run on the corridor gives a new-water excess
of 0.86% against a largest pre-event null of 0.76% (1.13×): **not separable** [`outputs/validation/ai_corridor.json`].
Sentinel-2 agrees with the model at precision ≈ 0.5 on both a pre- and a post-event date, so it cannot arbitrate
[`outputs/validation/ai_vs_s2.json`]. Our AI evidence is: Sen1Floods11 test 0.682, Bolivia (unseen region, not Himalayan)
0.680 with chip CI 0.46–0.80. **No labelled Himalayan test exists yet**: no chip reached 70% clear Sentinel-2, an algorithmic
window scan found 4 clear windows (need 8), and the written amendment (clear pixels only, all 20 chips) was logged
before any labelling [`docs/validation_log.md`, `outputs/validation/himalaya_chip_windows.json`].

## 4. "Are your two Sentinel-1 routes equivalent?"
No. The pre-registered test on the case study **failed** [`outputs/validation/route_equivalence.json`]: flagged area
3.53 km² (PC RTC gamma0) vs 3.14 km² (SNAP sigma0) and pixel IoU 0.36 pass, but bright change is not separable from the
nulls on the PC route (2.5×) while it is on SNAP (5.9×), and flood-like change drops from 0.31 to 0.05 km², as expected
when fixed σ⁰ water gates (−16/−22 dB) meet terrain-flattened γ⁰. So the **SNAP route is the validated one** and the
Planetary Computer route ("Sentinel-1 RTC, third-party processed from GRD") is a **cross-check only**, including in a live demo.

## 5. "How do you know you didn't tune on your test data?"
- Detector thresholds come from leave-one-out nulls on pre-event scenes only (α = 0.1%), never from EMS; the detector was
  tagged `detector-frozen` before its first EMS check [`docs/validation_log.md`].
- AOI03 Bidur is the hold-out AOI; every scoring of it is counted in the validation log (count: 4).
- The class-null rule (> 3×), the route-equivalence rule and the chip rules (points, 70% clear, path-2 amendment) were
  written down, dated, before the runs they judge. The model threshold (0.4) was chosen on Sen1Floods11 validation only.
- Disclosed: the Step-3 criteria were written after the first event run, so that test is exploratory.

## 6. "How long does a run take?"
PC route, `--profile fast`, 4 CPU cores: 12.6–14.0 min on the Kaggle dry runs, 18 min in our sandbox (OSM extract
download dominated) [`outputs/validation/dry_runs.json`, `docs/judges_day.md`]. SNAP route on the laptop (clean clone,
CDSE + SNAP): **being timed** (`outputs/step11_snap_timings.json`); budget well over an hour, so live we would show the
cached SNAP case study and, if asked for a new area, run the PC route and label it a cross-check.

## 7. "What can't it do?"
- It does not attribute cause: flood-like, dark and bright are surface-change classes; no damage, no water depth.
- It only assesses the HAND ≤ 30 m valley floor; outside it (92% of buildings in Rasuwa) status is UNKNOWN, not safe.
- Radar layover/shadow is UNKNOWN. One track, one post scene (2 days after the event; a gorge flood may have drained).
- Small events: the minimum detectable area is 0.21 km² in the case study but 17 km² in the Terai box, where no
  threshold met the 0.1% false-alarm target ("calibration target not met").
- Bridges are exposed, never known failed; OSM is pre-event and incomplete (141 settlements have no pre-flood route).
- It is not real-time and not operational.

## 8. Likely follow-ups
- *Why is one reference date 7 days off?* Dry run 1's 2026-06-22 reference is Sentinel-1A; the others are Sentinel-1D on the
  same relative orbit 85 (S1A flew track 85 until 06-22, S1D from 06-29). Same geometry, different satellite; the stack
  checks now warn on mixed platforms and on acquisition times > 10 min apart.
- *Why 12-day gaps?* Sentinel-1's repeat on one track; the gate only requires the same relative orbit and pass.

EMS credit: European Union, Copernicus Emergency Management Service data (EMSR927, used for checking only).

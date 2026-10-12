# Himalayan chip protocol (fixed before any labelling)

These rules were written on 2026-10-11, before anyone labelled a chip or looked at a prediction for one. They do not
change after predictions are seen.

## Points and chips

- Points: `data/external/himalaya_chips/points.csv`, pre-registered by `tools/select_himalaya_points.py` (strata: main
  stem, tributaries, hillside shadow). Do not edit the file.
- Event chips: `python tools/make_himalaya_chips.py` cuts 256 × 256 px chips at 10 m from the post-event Sentinel-1
  scene (2026-08-28) and the 27 Aug 2026 Sentinel-2 L2A scene for labelling.
- Pre-event (no-event) chips: `python tools/make_himalaya_chips.py --split pre` cuts chips at the same points from the
  pre-event Sentinel-1 scene (2026-08-16) and the 12 Aug 2026 Sentinel-2 scene. They are tagged `<name>_pre`, live in
  `data/external/himalaya_chips_pre/`, and are always reported separately. They test river water against hillside
  shadow without an event. They say nothing about the event.

## Rule 1: clear sky first

- Run `python tools/chip_clear.py <S2 date>` (and `--chips data/external/himalaya_chips_pre/S1` for the pre chips).
- Drop any chip whose Sentinel-2 clear fraction on its labelling date is below **0.70**. List every dropped chip with
  its clear fraction in the report.
- Do this before labelling. A chip is never added back or dropped later.

## Rule 2: what the labels mean

Label from the Sentinel-2 image only (never from the S1 chip, the model output or EMS):

| Value | Meaning |
|---|---|
| 1 | open water, **including turbid / sediment-laden water** |
| 0 | not water |
| −1 | unsure (cloud, cloud shadow, mixed pixels, can't tell); ignored in scoring |

## Rule 3: no relabelling after predictions

- Never drop, relabel or edit a chip after seeing a prediction for it.
- If a label error is found later, log it in `docs/validation_log.md` with the date, and report both the original and the
  corrected score.

## Annotators

- Annotator A labels every chip that passed Rule 1: `python tools/label_chips.py --annotator A`.
- Annotator B, a second person, labels the first 8 usable chips in `points.csv` order: `python tools/label_chips.py --annotator B --subset 8`.
- Annotators label independently and do not compare masks until both are done.

## Scoring and reporting

- Score: `python -m src.modeling.evaluate --extra <chips_labelled.csv> --extra-s1 <S1 dir> --extra-lbl <Label_A dir>`
  with the shipped seed-0 model (`models/`).
- Report n (usable chips), pooled IoU with its 95% chip-bootstrap CI, and A/B agreement IoU (`tools/chip_agreement.py`).
- If n < 8, write "qualitative only" and give no headline IoU.
- Report event chips and pre-event chips in separate rows.

## Status on 2026-10-11 (before labelling)

`tools/chip_clear.py` gives **0 of 20** event chips at clear ≥ 0.70 on 2026-08-27, and 0 of 20 on 2026-08-12. The
pre-event chips use the same points, so the 12 Aug check applies to them too. All other S2 dates on disk (2026-06-18,
07-05, 08-11, 09-08, 09-13, 09-20, 09-21) also give 0 of 20. Under Rule 1, the Himalayan chip test is **not possible**
with the available Sentinel-2. Report it as "no usable chips (monsoon cloud), qualitative only" unless a clearer
labelling source is found. A new source would be a protocol change, and it must be logged here **before** any labelling.

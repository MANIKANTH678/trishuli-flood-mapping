import sys
p = "FINAL_REPORT.md"
raw = open(p, encoding="utf8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")

def swap(old, new):
    global t
    if t.count(old) != 1:
        sys.exit(f"anchor not found exactly once: {old[:60]!r}")
    t = t.replace(old, new)

swap("A placebo pair that does not span the\nevent is needed to separate these. The\nexcess is quoted",
     "The placebo pair in §4.1c tests part of this. The\nexcess is quoted")

SEC = """### 4.1c Placebo, sensitivity and landslide check

**Placebo.** The same analysis on 4 August against 16 August (same relative orbit 85,
ascending; `outputs/diagnostics/step3_placebo.json`) finds no strongly negative pixel
on the main-stem floor in either polarization, at any setting tried (floor 30, 15 and
60 m; z threshold 3.5, 3 and 4.5; 10 m with 3 x 3 smoothing). The largest main-stem
fraction of any kind in a placebo run is below 0.04% (VV, positive tail, floor 15 m).
The placebo scenes were processed with `--splits placebo` in `s1_preprocess.py` and
`s1_to_grid.py`.

**Sensitivity.** In the event pair (16 against 28 August), the negative-tail excess of
the main-stem floor over tributary floors (percentage points, 95% block-bootstrap
interval) has a lower bound above zero in every run:

| Run                        | VV           | VH           |
| -------------------------- | ------------ | ------------ |
| Base (floor 30 m, z 3.5)   | 0.86 to 2.88 | 2.67 to 6.46 |
| Floor 15 m                 | 1.20 to 4.12 | 3.41 to 8.74 |
| Floor 60 m                 | 0.55 to 1.97 | 1.72 to 4.36 |
| z 3                        | 1.55 to 4.41 | 4.25 to 9.17 |
| z 4.5                      | 0.26 to 1.24 | 0.78 to 2.62 |
| 10 m, 3 x 3 smoothing      | 0.94 to 2.88 | 2.93 to 6.50 |

The positive-tail excess is above zero only for VV at z = 3 (0.11 to 0.66 points). The
10 m run reuses the 30 m HAND and radar mask and the smoothing brings the data back to
about 30 m, so it checks consistency, not finer resolution. Along the profile, VH
negative pixels occur in 18 consecutive 0.01° bins from 27.805°N to 27.975°N and in
three more from 27.995°N to 28.015°N; the first bin is at the southern edge of the
study area, so how far the reach extends south is not known. Under
`docs/step3_criteria.md` the outcome is signal present (`docs/step3_outcome.md`),
subject to §5.7.

**Landslide polygons.** `src/validation/step3_landslide_check.py` compares the
main-stem floor exceedances (z < -3.5, patches of at least 8 px) with the EMSR927
`observedEventA` polygons, all typed mass movement / landslide (1 at Syapru Besi, 1 at
Timure, 2 at Bidur, 20 at Phosretar). Bidur was held out of the first run and added in
a final run, with no change to code or thresholds in between
(`outputs/validation/step3_landslide_check_final.json`).

| Main-stem floor pixels                     | n px   | VV strongly negative | VH strongly negative |
| ------------------------------------------ | ------ | -------------------- | -------------------- |
| On polygons, Syapru Besi and Timure        | 1,545  | 0                    | 0                    |
| On polygons, Phosretar                     | 4,826  | 353 (7.3%)           | 817 (16.9%)          |
| On polygons, Bidur (held out)              | 6,208  | 154 (2.5%)           | 429 (6.9%)           |
| Inside the four AOIs, off polygons         | 7,442  | 0                    | 1 (0.01%)            |
| Outside the four AOIs                      | 16,687 | 181 (1.1%)           | 417 (2.5%)           |

Three quarters of the main-stem floor exceedances (507 of 688 in VV, 1,246 of 1,664 in
VH) lie on mapped landslide polygons at Bidur and Phosretar. Almost none lie inside the
AOIs off the polygons, and the rest are outside the four AOIs, where there is no EMS
mapping to compare with. In the two Rasuwa AOIs, where the event occurred, 1,545
main-floor pixels lie on mapped polygons and none is an exceedance, so lying on a
polygon does not by itself produce the signal.

This matches §4.4, where the flood mask also lies 97 to 98% on landslide polygons at
these AOIs, so it is not independent support for flooding. EMSR927 has no flood-extent
layer (§5.2), so the check cannot say whether the darkening on the polygons is debris,
deposited sediment, standing water or a mixture. The polygons cover 63% of the
main-floor pixels inside the AOIs, so they are not a small target. The exceedances form
a few spatial clusters, so no significance test is reported. The quarter of exceedances
outside the AOIs is unexplained.

"""
swap("### 4.2 U-Net applied to the corridor", SEC + "### 4.2 U-Net applied to the corridor")

swap("**5.7 The step 3 analysis is exploratory.** `docs/step3_criteria.md` was\n"
     "written after the first event run (the file was empty when the results were written),\n"
     "so the results in §4.1b are not a pre-registered test. There is also no\n"
     "placebo yet: the same analysis on a scene pair that does not span the event\n"
     "(for example 4 August against 16 August on the same orbit) is the first run\n"
     "that can be tested against fixed criteria.",
     "**5.7 The step 3 analysis is partly exploratory.** `docs/step3_criteria.md` was\n"
     "written after the first event run (the file was empty when the results were written),\n"
     "so the decision thresholds were not fixed before the event result was seen. The\n"
     "placebo (4 August against 16 August, same orbit), the sensitivity runs and the\n"
     "landslide check (§4.1c) came after the criteria were in place, but each rests on a\n"
     "single scene pair. They cannot exclude a rain-driven or seasonal rise in river level\n"
     "between 16 and 28 August that was absent from 4 to 16 August. The landslide check is\n"
     "descriptive, with no significance test.")

out, n_tab, n_cmd = [], 0, 0
for l in t.split("\n"):
    out.append(l)
    if l.startswith("|") and "`outputs/diagnostics/look_geometry.json`" in l:
        out.append("| `outputs/diagnostics/step3_placebo.json` | Placebo pair (4 Aug vs 16 Aug) z-score statistics |")
        out.append("| `outputs/validation/step3_landslide_check_final.json` | Main-floor exceedances on and off EMSR927 landslide polygons |")
        n_tab += 1
    if l.strip() == "python -m src.analysis.zscore --tag event":
        ind = l[:len(l) - len(l.lstrip())]
        out.append(ind + "python -m src.analysis.zscore --first placebo --second pre --tag placebo")
        out.append(ind + "python -m src.analysis.zscore --tag event_masks --save-masks")
        out.append(ind + "python -m src.validation.step3_landslide_check --final --out outputs/validation/step3_landslide_check_final.json")
        n_cmd += 1
print("artifact rows inserted:", n_tab, "| command lines inserted:", n_cmd)
t = "\n".join(out)
open(p, "w", encoding="utf8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
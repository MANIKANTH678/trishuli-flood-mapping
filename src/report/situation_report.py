"""Build outputs/reports/situation_report_EN.md from pipeline JSON/rasters only."""
import datetime, json, subprocess, sys
from pathlib import Path
import numpy as np, rasterio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config

def die(msg): sys.exit(f"situation_report: {msg}")
def J(p): return json.loads((ROOT / p).read_text(encoding="utf-8"))
def git(*a): return subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT).stdout.strip()

# single source of truth for the OSM date
man = J("data/raw/osm/manifest.json")
snap = man["snapshot"]
if snap != config.OSM_SNAPSHOT_DATE:
    die(f"manifest snapshot {snap} != config.OSM_SNAPSHOT_DATE {config.OSM_SNAPSHOT_DATE}")
if snap >= config.FLOOD_DATE:
    die("OSM snapshot is not pre-event")

# refuse stale inputs
mask_p = ROOT / "data/processed/flood_mask.tif"
files = ["outputs/impact_summary.json", "outputs/cutoff_settlements.json",
         "outputs/validation/signal_check.json", "outputs/validation/unet_corridor.json"]
have_ems = ((ROOT / "data/external/EMSR927").is_dir()
            and (ROOT / "data/processed/emsr927_comparison.json").exists()
            and (ROOT / "outputs/validation/null_recall_aoi.json").exists())
if have_ems:
    files += ["data/processed/emsr927_comparison.json", "outputs/validation/null_recall_aoi.json"]
for f in files:
    if (ROOT / f).stat().st_mtime < mask_p.stat().st_mtime:
        die(f"{f} is older than flood_mask.tif; rerun that step")

try:
    imp = J("outputs/impact_summary.json")
    cut = J("outputs/cutoff_settlements.json")["summary"]
    emsr = J("data/processed/emsr927_comparison.json")["aois"] if have_ems else {}
    sig = J("outputs/validation/signal_check.json")
    nul = J("outputs/validation/null_recall_aoi.json") if have_ems else {}
    un = J("outputs/validation/unet_corridor.json")

    with rasterio.open(mask_p) as s:
        px = int((s.read(1) > 0).sum()); area = px * abs(s.res[0] * s.res[1]) / 1e6
    with rasterio.open(ROOT / "data/processed/debris_mask.tif") as s:
        dpx = int((s.read(1) > 0).sum()); darea = dpx * abs(s.res[0] * s.res[1]) / 1e6

    rows, tot = [], 0
    grades = {"Destroyed": 0, "Damaged": 0, "Possibly damaged": 0}
    for k, a in (emsr.items() if have_ems else []):
        dp = a["damage_points"]; n = nul[k.split("_")[0]]
        tot += dp["total"]
        for g in grades: grades[g] += dp["by_grade"][g]["total"]
        rows.append(f"| {a['locality']} | {dp['total']:,} | {n['points']:,} | {dp['inside_flood_mask']:,} | "
                    f"{n['mask_px']:,} | {n['flat_px']:,} | {n['observed']:.3f} | "
                    f"{n['null_mean']:.3f} ± {n['null_sd']:.3f} |")
    pct = lambda d: 100 * d["flood_px"] / d["covered_px"]
    commit = git("rev-parse", "--short", "HEAD") + (" + uncommitted changes" if git("status", "--porcelain") else "")

    ems_block = ""
    if have_ems:
        ems_block = f"""## 4. Validation against Copernicus EMS (EMSR927, check-only)

> Validation only. EMS data is not an input to any map or number above.

EMSR927 mapped {tot:,} damaged structures in four Areas of Interest ({grades['Destroyed']:,} Destroyed, {grades['Damaged']:,} Damaged, {grades['Possibly damaged']:,} Possibly damaged). Per AOI, the mask hit rate on EMSR927 damage points against a random mask of the same size placed on flat pixels inside the AOI:

| AOI | Damage points | Points in raster | Inside mask | Mask px in AOI | Flat px in AOI | Observed hit | Null (mean ± sd) |
|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + """

Where the mask has no or almost no pixels, the miss is a coverage limit of the method, not a measured detection error. Where hit rates exceed the null, the mask is associated with damage in built-up lowlands; this does not distinguish flooding from other change.
"""

    md = f"""# Situation Report — Trishuli / Bhote Koshi GLOF

> **PRELIMINARY** — generated {datetime.date.today()} from commit `{commit}`. Numbers will change if the detector or inputs change.

**Event:** {config.FLOOD_DATE} flash flood (suspected GLOF), Rasuwa District, Nepal
**Status:** Post-event analysis. **On this Sentinel-1 pair, no flood signal could be detected.**

## 1. Situation

Post-event analysis of the flash flood on the Trishuli / Bhote Koshi, built from system-derived maps only (Sentinel-1 and, where available, Sentinel-2). Copernicus EMS products are used for checking only and appear only in the labelled validation section, when present.

## 2. Key finding

On calibrated, terrain-corrected Sentinel-1 (σ⁰, Copernicus GLO-30), the {config.PRE_DATE} / {config.POST_DATE} pair shows no detectable flood signal along the Trishuli or in the Rasuwa reach. **This pair cannot resolve the event; it does not show that no flood occurred.**

| VV change (post − pre), dB | n | median | p5 | p1 |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | {sig[k]['n']:,} | {sig[k]['median']:.2f} | {sig[k]['p5']:.2f} | {sig[k]['p1']:.2f} |"
                for lab, k in [("all pixels", "all"), ("river, 60 m buffer", "river_60m"),
                               ("river, Rasuwa (north) half", "river_north_half"),
                               ("river, south half", "river_south_half"),
                               ("river shifted +1.5 km (control)", "river_shifted_1500m"),
                               ("river shifted −1.5 km (control)", "river_shifted_-1500m")]) + f"""

A real flood over water would be expected to give a clearly negative river median. The Rasuwa half is no darker than the shifted controls.

The U-Net (Sen1Floods11) flags {pct(un['post']):.2f}% of the corridor in the post scene and {pct(un['pre']):.2f}% in the pre scene; {un['new_water_px']:,} px gained and {un['lost_water_px']:,} px lost. It cannot discriminate the two scenes, so it is **not** independent evidence either way.

## 3. Exposure to the detector's mask

The mask below is the thresholded dark tail of the VV change. It is **not a validated flood extent**; the figures show sensitivity of exposure to that mask.

| Item | Value |
|---|---|
| Flood mask | {px:,} px ({area:.2f} km²) |
| Debris mask | {dpx:,} px ({darea:.2f} km²) |
| Buildings in mask | {imp['flooded_buildings']:,} flooded + {imp['debris_buildings']:,} debris-affected (of {imp['total_buildings']:,}) |
| Bridges in mask | {imp['flooded_bridges']:,} (of {imp['total_bridges']:,}) |
| Settlements cut off | {cut['cut_off']} of {cut['total_settlements']} ({cut['cut_off_no_path']} no path, {cut['cut_off_detour_only']} detour only; {cut['hospitals_total']} hospitals) |

{ems_block}

## 5. Limitations

- The post scene is two days after the event; a flash flood in a narrow gorge may already have drained.
- 30 m pixels mix narrow channels; the slope filter removes almost all steep terrain.
{'- EMSR927 GRA products contain no flood-extent layer; validation is proxy only.' if have_ems else ''}
- The detector's threshold sits at its lower clip limit, so the mask is selected from noise-level change.
- Held-out U-Net IoU values come from an earlier run (Sen1Floods11 is not on disk).
- **OSM currency and completeness.** Infrastructure comes from the ohsome snapshot of {snap}, the latest pre-event snapshot available (see `data/raw/osm/manifest.json`). Edits between {snap} and {config.FLOOD_DATE} are not reflected, and OSM coverage of rural Rasuwa is incomplete: missing buildings undercount damage, and missing tracks can overstate cut-off.

## 6. Recommendations

1. Re-acquire with optical imagery (Sentinel-2, PlanetScope) or high-resolution SAR.
2. Task optical assets within 24–72 hours of future GLOF events.
3. Replace the threshold detector before reuse.

## 7. Data sources

- Sentinel-1 GRD (Copernicus Data Space Ecosystem), calibrated σ⁰, terrain-corrected with Copernicus GLO-30
{'- Copernicus EMS Rapid Mapping, EMSR927 (validation only)' if have_ems else ''}
- OpenStreetMap, ohsome snapshot {snap} (pre-event), ODbL
- Sen1Floods11 v1.1 (CC BY 4.0)

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md).

## Changelog

- The `v0-baseline` run used post-event OSM and was discarded.
"""
except KeyError as e:
    die(f"missing key {e}; paste the JSON it came from")

out = ROOT / "outputs/reports/situation_report_EN.md"
out.write_text(md, encoding="utf-8")
print("wrote", out)
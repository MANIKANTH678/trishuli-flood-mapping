"""Build outputs/reports/situation_report_EN.md (one page) from pipeline JSON/rasters only.

    python src/report/situation_report.py            # draft: header says so if code/data are uncommitted
    python src/report/situation_report.py --final    # refuses to run unless the tree is clean (outputs/ excluded)

Nothing here is hard-coded status text: the detector status, thresholds, areas, counts and ranges are read from
the JSON files and the fused class raster. EMSR927 is optional; without it section "Validation" is left out.
"""
import argparse, datetime, json, subprocess, sys
from collections import Counter
from pathlib import Path
import numpy as np, rasterio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config

TRACK = "asc85"
FUSED = "data/processed/fused_class_30m.tif"
DETECT = f"outputs/diagnostics/detect_{TRACK}.json"
AOI_NAMES = {"AOI01": "Syapru Besi", "AOI02": "Timure", "AOI03": "Bidur", "AOI05": "Phosretar"}
TOL_S = 120                                       # files written by one run can differ by seconds
MAX_WORDS = 760                                   # rough one-page budget (tables count pipes as words)

def die(msg): sys.exit(f"situation_report: {msg}")
def J(p): return json.loads((ROOT / p).read_text(encoding="utf-8"))
def git(*a):
    try: return subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError): return None
def rg(r, key, default=None):
    v = (r or {}).get(key, default)
    return v if v is not None else default
def f3(v): return "n/a" if v is None else f"{v:.3f}"
def span(r, key, fmt="{:,}"):
    v = (r or {}).get(key)
    return "n/a" if not v else (fmt.format(v[0]) if v[0] == v[1] else f"{fmt.format(v[0])}–{fmt.format(v[1])}")

ap = argparse.ArgumentParser()
ap.add_argument("--final", action="store_true", help="require a clean working tree (outputs/ ignored)")
args = ap.parse_args()

# --- single source of truth for the OSM date --------------------------------------------------------------
man = J("data/raw/osm/manifest.json")
snap = man["snapshot"]
if snap != config.OSM_SNAPSHOT_DATE:
    die(f"manifest snapshot {snap} != config.OSM_SNAPSHOT_DATE {config.OSM_SNAPSHOT_DATE}")
if snap >= config.FLOOD_DATE:
    die("OSM snapshot is not pre-event")

# --- refuse stale inputs: everything must be newer than the fused class raster ------------------------------
mask_p = ROOT / FUSED
have_ems = ((ROOT / "data/external/EMSR927").is_dir() and (ROOT / "outputs/validation/null_recall_aoi.json").exists())
files = [DETECT, "outputs/impact_summary.json", "outputs/cutoff_settlements.json",
         "outputs/validation/signal_check.json", "outputs/validation/unet_corridor.json"]
if have_ems: files.append("outputs/validation/null_recall_aoi.json")
flood_p = ROOT / "data/processed/flood_mask.tif"      # detect -> fuse: detector-side files are checked against this
VS_FLOOD = {DETECT, "outputs/validation/signal_check.json", "outputs/validation/unet_corridor.json"}
for f in files:
    if not (ROOT / f).exists(): die(f"{f} is missing; rerun that step")
    ref = flood_p if f in VS_FLOOD else mask_p
    if ref.exists() and (ROOT / f).stat().st_mtime < ref.stat().st_mtime - TOL_S:
        die(f"{f} is older than {ref.name}; rerun that step")

# --- reproducibility: clean tree for the final report -------------------------------------------------------
dirty = git("status", "--porcelain", "--", ".", ":(exclude)outputs")
commit = git("rev-parse", "--short", "HEAD") or "unknown"
if args.final and dirty != "":
    die("working tree is not clean (outputs/ excluded); commit first so the numbers can be reproduced")
stamp = f"commit `{commit}`" + ("" if dirty == "" else " + uncommitted changes (DRAFT)" if dirty else " (git state unknown)")

try:
    det, imp = J(DETECT), J("outputs/impact_summary.json")
    cutj = J("outputs/cutoff_settlements.json")
    cut, setl, rngc = cutj["summary"], cutj["settlements"], cutj["sensitivity"]["range"]
    sig, un = J("outputs/validation/signal_check.json"), J("outputs/validation/unet_corridor.json")
    nul = J("outputs/validation/null_recall_aoi.json") if have_ems else {}

    # --- mask areas from the fused raster; scenario range from the sensitivity detector runs ---------------
    with rasterio.open(mask_p) as s:
        cls, pa = s.read(1), abs(s.res[0] * s.res[1]) / 1e6
    a1, a2, a3 = ((cls == c).sum() * pa for c in (1, 2, 3)); atot = a1 + a2 + a3
    areas = []
    for nm in ("low", "high"):
        p = ROOT / f"outputs/diagnostics/detect_sens_{nm}.json"
        if p.exists(): areas.append(sum(J(f"outputs/diagnostics/detect_sens_{nm}.json")["area_km2"].values()))
    area_rng = f"{min(areas):.2f}–{max(areas):.2f} km²" if len(areas) == 2 else "n/a"

    # --- detection signal: tails, not medians ---------------------------------------------------------------
    ctrl = [sig["river_shifted_1500m"], sig["river_shifted_-1500m"]]
    c1, c5 = (float(np.mean([c[k] for c in ctrl])) for k in ("p1", "p5"))
    riv, nh, sh = sig["river_60m"], sig["river_north_half"], sig["river_south_half"]
    tail = ("The river reach has a lower-tail excess over the shifted controls: it is evidence of surface change along the reach, "
            "not by itself of flooding." if riv["p1"] < c1 - 0.5 else
            "The river reach shows no clear lower-tail excess over the shifted controls.")
    sig_rows = "\n".join(f"| {lab} | {sig[k]['n']:,} | {sig[k]['p5']:.2f} | {sig[k]['p1']:.2f} |" for lab, k in [
        ("all pixels", "all"), ("river, 60 m buffer", "river_60m"), ("river, north (Rasuwa) half", "river_north_half"),
        ("river, south half", "river_south_half"), ("river shifted +1.5 km (control)", "river_shifted_1500m"),
        ("river shifted −1.5 km (control)", "river_shifted_-1500m")])
    pct = lambda d: 100 * d["flood_px"] / d["covered_px"]

    # --- exposure ---------------------------------------------------------------------------------------------
    b, rb, rr = imp["buildings"], imp["roads_bridges"]["exposure_by_tolerance"]["0m"], imp["sensitivity"]["range"]
    unknown = b["not_assessed"] + b["unobservable"]; unk_pct = 100 * unknown / b["total"]
    cut_n = cut["cut_off"]; deg_n = cut.get("hospital_degraded", 0)
    cut_set = [x for x in setl if x["hospital"]["status"] == "cut_off"]
    causes = Counter((x["first_break"] or {}).get("cause", "unknown") for x in cut_set)
    fr = [x["route_assessed_frac"] for x in cut_set if x.get("route_assessed_frac") is not None]
    cut_detail = (f"All {len(cut_set)} first breaks: " + ", ".join(f"{n} {c}" for c, n in causes.most_common()) +
                  (f"; the detector observed {min(fr):.0%}–{max(fr):.0%} of each cut-off route." if fr else ".")) if cut_set else \
                 "No settlement is cut off in the headline scenario."
    no_path = cut.get("hospital_no_pre_flood_path", 0)

    # --- validation (optional) ----------------------------------------------------------------------------------
    aois = {a: n for a, n in nul.items() if a.startswith("AOI")}
    def zs(n):
        return (n["observed"] - n["null_mean"]) / n["null_sd"] if n.get("null_sd") else None
    ems_rows = [f"| {a} {AOI_NAMES.get(a, '')}{' (hold-out)' if n.get('holdout') else ''} | {n['points']:,} | {n['assessed_points']:,} | {n['mask_px']:,} | "
                f"{f3(n['observed'])} | {f3(n['null_mean'])} ± {f3(n['null_sd'])} | {'n/a' if zs(n) is None else f'{zs(n):+.1f}'} |"
                for a, n in aois.items()]
    above = [a for a, n in aois.items() if zs(n) is not None and zs(n) > 2]
    below = [a for a, n in aois.items() if zs(n) is not None and zs(n) < -2]
    empty = [a for a, n in aois.items() if n["mask_px"] == 0]
    ems_read = (f"Above the null: {', '.join(above) or 'none'}. Below the null: {', '.join(below) or 'none'}. "
                f"No flagged pixels: {', '.join(empty) or 'none'} (a coverage limit, not a measured detection error). "
                "Association with damage points is not attribution to flooding.")
    ems_block = ("""Hit rate of the fused flagged mask (classes 1–3) on EMSR927 damage points, against 200 random masks of the same size on assessed floor pixels in each AOI. Check only: EMS data is not an input to any number above.

| AOI | Points | On assessed px | Flagged px | Observed hit | Null (mean ± sd) | z |
|---|---|---|---|---|---|---|
""" + "\n".join(ems_rows) + """

""" + ems_read + " AOI03 was scored 4 times (docs/validation_log.md); S1 parameters unchanged since tag detector-frozen.") if have_ems else None

    days = (datetime.date.fromisoformat(config.POST_DATE) - datetime.date.fromisoformat(config.FLOOD_DATE)).days
    lims = [f"Single Sentinel-1 track ({det['track']}), one pre/post pair; the post scene is {days} days after the event, so a flash flood in a narrow gorge may already have drained.",
            f"Only the valley floor is assessed ({det['floor_km2']:.0f} km², {det['usable_fraction_of_floor']:.0%} usable). {unk_pct:.0f}% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.",
            "Sentinel-2 added nothing: coverage is about 12% and its null calibration failed, so S2 is excluded and the fused product equals the S1 product.",
            "No cause attribution: flood-like, dark and bright classes are all surface change; bridges are exposed, never known to have failed.",
            f"30 m pixels mix narrow channels; OSM snapshot {snap} predates the event and rural Rasuwa is under-mapped, so missing buildings undercount damage and missing tracks overstate cut-off ({no_path} settlements have no pre-flood route)."]
    if have_ems: lims.append("EMSR927 GRA products contain no flood-extent layer; validation is proxy only.")

    sec = []
    sec.append(("Situation", f"""{config.FLOOD_DATE} flash flood (suspected GLOF), Trishuli / Bhote Koshi, Rasuwa, Nepal; Sentinel-1 {config.PRE_DATE} / {config.POST_DATE}, Copernicus GLO-30, OSM. Detector status: **{det['status']}** (track {det['track']}; VH robust-z change of {', '.join(det['refs'])} against {det['post']}, thresholds {det['t_hi']:g} / {det['t_lo']:g}, calibrated={det['calibrated']}, null false-alarm max {100 * det['null_far_max']:.3f}%). The mask is restricted to the HAND valley floor; the result is exposure to a detected mask, **not a validated flood extent**."""))
    sec.append(("Detection signal", f"""| VV change (post − pre), dB | n | p5 | p1 |
|---|---|---|---|
{sig_rows}

River p1 {riv['p1']:.2f} dB vs {c1:.2f} dB for the controls ({riv['p1'] - c1:+.2f}); p5 {riv['p5']:.2f} vs {c5:.2f}. By reach: south half p1 {sh['p1']:.2f} ({sh['p1'] - c1:+.2f}), north half {nh['p1']:.2f} ({nh['p1'] - c1:+.2f}). {tail} The U-Net (Sen1Floods11) flags {pct(un['post']):.2f}% of the corridor post and {pct(un['pre']):.2f}% pre: it does not separate the scenes and is not independent evidence."""))
    sec.append(("Exposure to the mask", f"""| Item | Headline (base mask) | Scenario range |
|---|---|---|
| Flagged area | {atot:.2f} km² ({a1:.2f} flood-like, {a2:.2f} dark, {a3:.2f} bright) | {area_rng} |
| Buildings overlapping the mask | {b['overlap']:,} ({b['overlap_flood']:,} flood, {b['overlap_debris']:,} debris) of {b['total']:,} | {span(rr, 'buildings_overlap')} |
| Buildings within 30 m | {b['within_30m']:,} | {span(rr, 'buildings_within_30m')} |
| Buildings with unknown status | {unknown:,} ({unk_pct:.0f}%) | n/a |
| Motorable road in mask | {rb['motorable_road_km']:.1f} km ({rb['roads']} segments) | {span(rr, 'motorable_road_km', '{:.1f}')} km |
| Bridges exposed (not failed) | {rb['bridges']} of {imp['total_bridges']} | {span(rr, 'bridges_exposed')} |
| Settlements cut off (no path to a hospital) | {cut_n} of {cut['total_settlements']} | {span(rngc, 'hospital_cut_off')} |
| Settlements degraded (≥2× and ≥2 km longer) | {deg_n} | {span(rngc, 'hospital_degraded')} |
| Settlements not assessed (no pre-flood route) | {no_path} | n/a |

Range = 3 thresholds × mask ±1 px × bridges fail/survive. {cut_detail} Cut-off covers only the {cut['total_settlements'] - no_path} assessable settlements; {cut.get('hospitals_snapped', '?')} of {cut['hospitals_total']} hospitals were reachable as destinations."""))
    if ems_block: sec.append(("Validation against Copernicus EMS (EMSR927)", ems_block))
    sec.append(("Limitations", "\n".join(f"- {x}" for x in lims)))
    sec.append(("Next steps (in scope)", f"""1. Add a second Sentinel-1 track or a closer post scene and rerun unchanged; the headline should stay inside the ranges above.
2. Check the {len(cut_set)} cut-off first-break points against field or imagery reports.
3. Refresh OSM after the event and rerun cut-off to separate missing roads from real loss."""))
    sec.append(("Data sources", f"""- Contains modified Copernicus Sentinel data 2026 (Sentinel-1 GRD, Copernicus Data Space Ecosystem)
- (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA; all rights reserved (Copernicus DEM GLO-30)
- (c) OpenStreetMap contributors, ODbL v1.0 (ohsome snapshot {snap}, pre-event){chr(10) + '- Copernicus EMS Rapid Mapping, EMSR927 (validation only)' if have_ems else ''}
- Sen1Floods11 v1.1, CC BY 4.0: Bonafilia et al. (2020), CVPR EarthVision workshop

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md)."""))

    body = "\n\n".join(f"## {i}. {t}\n\n{txt}" for i, (t, txt) in enumerate(sec, 1))
    md = f"""# Situation Report — Trishuli / Bhote Koshi GLOF

> **PRELIMINARY** — generated {datetime.date.today()} from {stamp}. Numbers change if the detector or inputs change.

{body}

*Changelog: the `v0-baseline` run used post-event OSM and was discarded.*
"""
except KeyError as e:
    die(f"missing key {e}; paste the JSON it came from")

md = "\n".join(l for i, l in enumerate(md.split("\n")) if l.strip() or i == 0 or md.split("\n")[i - 1].strip())
words = len(md.split())
if words > MAX_WORDS: print(f"situation_report: WARNING {words} words > {MAX_WORDS}; the report may not fit one page", file=sys.stderr)
out = ROOT / "outputs/reports/situation_report_EN.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(md, encoding="utf-8")
print("wrote", out, f"({words} words)")
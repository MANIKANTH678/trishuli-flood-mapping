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

REF_DATES = {"pre": config.PRE_DATE, "post": config.POST_DATE}   # add "placebo": "...", "pre3": "...", "pre4": "..."
def rd(n): return f"{n} ({REF_DATES[n]})" if n in REF_DATES else n
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
have_ems = ((ROOT / "data/external/EMSR927").is_dir() and (ROOT / "outputs/validation/emsr927_validation.json").exists())
files = [DETECT, "outputs/impact_summary.json", "outputs/cutoff_settlements.json",
         "outputs/validation/signal_check.json", "outputs/validation/unet_corridor.json"]
if have_ems: files.append("outputs/validation/emsr927_validation.json")
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
    s3e, s3p = J("outputs/diagnostics/step3_event.json"), J("outputs/diagnostics/step3_placebo.json")
    s2 = J("outputs/diagnostics/s2_detect.json")
    nul = J("outputs/validation/emsr927_validation.json") if have_ems else {}

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
    V, pooled = nul.get("aois", {}), nul.get("pooled_assessed_domain", {})
    def prf(s): return f"{f3(s['precision'])} / {f3(s['recall'])} / {f3(s['iou'])}"
    def pc(v): return "n/a" if v is None else f"{100 * v:.0f}%"
    seg_rows, pt_rows, verdicts = [], [], []
    for a, r in V.items():
        tag = f"{a} {AOI_NAMES.get(a, '')}{' (hold-out)' if r.get('holdout') else ''}"
        ev, dp, bp = r.get("event_area"), r.get("damage_points"), r.get("building_precision_proxy")
        if ev:
            seg_rows.append(f"| {tag} | {ev['ref_px_assessed']:,} | {prf(ev['debris']['assessed']['strict'])} | {prf(ev['flood_or_debris']['assessed']['strict'])} |")
        if dp:
            cells = []
            for tol in ("0", "30", "60"):
                v = dp["recall_assessed"].get(tol)
                if not v: cells.append("n/a"); continue
                lo, hi = v["ci95"]
                cells.append(f"{v['rate']:.3f} " + ("" if lo is None else f"[{lo:.2f}–{hi:.2f}] ") + v["verdict"])
            v30 = dp["recall_assessed"].get("30")
            if v30: verdicts.append(f"{a} {v30['verdict']}")
            fo, base = (bp or {}).get("flagged_overlap"), (bp or {}).get("baseline_all_assessed_buildings")
            prox = "n/a" if not fo or not base else f"{pc(fo['30'])} (n={fo['n']}) vs {pc(base['30'])}"
            pt_rows.append(f"| {tag} | {dp['n_assessed']:,} | {' | '.join(cells)} | {prox} |")
    for key, lab in (("non_holdout", "Pooled non-hold-out"), ("holdout", "Pooled hold-out")):
        g = pooled.get(key)
        if g: seg_rows.append(f"| {lab} | {g['debris']['tp'] + g['debris']['fn']:,} | {prf(g['debris'])} | {prf(g['flood_or_debris'])} |")
    ems_read = ("Verdict at 30 m: " + ("; ".join(verdicts) or "n/a") + ". Association with damage points is not attribution to flooding. "
                "AOI03 was scored 4 times (docs/validation_log.md); S1 parameters unchanged since tag detector-frozen.")
    ems_block = None
    if have_ems:
        ems_block = ("Check only: EMS data is not an input to any number above. Reference: landslide polygons (observedEventA) and damage points; no flood-extent layer in the local GRA products. "
                     "Domain: AOI minus notAnalysedA, restricted to pixels the detector observed. Chance: the mask's own blobs relocated at random (100 draws).\n\n"
                     "| AOI | Reference px | Debris P / R / IoU | Flood or debris P / R / IoU |\n|---|---|---|---|\n" + "\n".join(seg_rows) + "\n\n"
                     "| AOI | Assessed points | Recall 0 m | 30 m | 60 m | Flagged buildings within 30 m of a damage point vs all-building baseline |\n|---|---|---|---|---|---|\n"
                     + "\n".join(pt_rows) + "\n\n" + ems_read)

    days = (datetime.date.fromisoformat(config.POST_DATE) - datetime.date.fromisoformat(config.FLOOD_DATE)).days
    lims = [f"Single Sentinel-1 track ({det['track']}), one pre/post pair; the post scene is {days} days after the event, so a flash flood in a narrow gorge may already have drained.",
            f"Only the valley floor is assessed ({det['floor_km2']:.0f} km², {det['usable_fraction_of_floor']:.0%} usable). {unk_pct:.0f}% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.",
            f"Sentinel-2 added nothing: {s2['floor_clear_post_fraction']:.0%} of the valley floor has clear post-event S2 coverage and its status is {s2['status']} (seed fraction {s2['seed_fraction']:.4f} vs gate {s2['gate_threshold']:.3f}), so S2 is excluded and the fused product equals the S1 product.",
            "No cause attribution: flood-like, dark and bright classes are all surface change; bridges are exposed, never known to have failed.",
            f"30 m pixels mix narrow channels; OSM snapshot {snap} predates the event and rural Rasuwa is under-mapped, so missing buildings undercount damage and missing tracks overstate cut-off ({no_path} settlements have no pre-flood route)."]
    if have_ems: lims.append("EMSR927 products held locally (GRA) contain no flood-extent layer: the reference is landslide polygons and damage points, so the flood class is not validated against EMS.")

    sec = []
    sec.append(("Situation", f"""{config.FLOOD_DATE} flash flood (suspected GLOF), Trishuli / Bhote Koshi, Rasuwa, Nepal; Sentinel-1 {config.PRE_DATE} / {config.POST_DATE}, Copernicus GLO-30, OSM. Detector status: **{det['status']}** (track {det['track']}; VH robust-z change of {', '.join(rd(x) for x in det['refs'])} against {rd(det['post'])}, thresholds {det['t_hi']:g} / {det['t_lo']:g}, calibrated={det['calibrated']}, null false-alarm max {100 * det['null_far_max']:.3f}%). The mask is restricted to the HAND valley floor; the result is exposure to a detected mask, **not a validated flood extent**."""))
    def p2(v): return f"{100 * v:.2f}%"
    def s3row(band):
        e, p = s3e["stats"][band], s3p["stats"][band]
        eb, pb = s3e["bootstrap"][band]["neg"]["excess_ci"], s3p["bootstrap"][band]["neg"]["excess_ci"]
        return (f"| {band} | {p2(e['main_floor']['frac_neg'])} | {p2(e['trib_floor']['frac_neg'])} | {p2(e['hillslope_ctrl']['frac_neg'])} | "
                f"{p2(eb[1])} [{p2(eb[0])}, {p2(eb[2])}] | {p2(p['main_floor']['frac_neg'])}; excess {p2(pb[1])} [{p2(pb[0])}, {p2(pb[2])}] |")
    ev_ok = all(s3e["bootstrap"][b]["neg"]["excess_ci"][0] > 0 for b in ("VV", "VH"))
    pl_none = all(s3p["bootstrap"][b]["neg"]["excess_ci"][1] <= 0 for b in ("VV", "VH"))
    s3_read = (("The main floor has more decrease pixels than the tributary floors in both bands, with 95% CIs above zero" if ev_ok else
                "The main floor does not show a clear decrease excess over the tributary floors in both bands") +
               (", and the placebo pair shows none. " if pl_none else ", but the placebo pair also shows an excess, so this is not clean evidence. ") +
               "This is evidence of surface change along the main reach, not by itself of flooding. ")
    a3 = s3e["args"]
    sec.append(("Detection signal", f"""Step 3 test ({a3['first']} → {a3['second']}; pixels flagged as decreases by robust z at threshold {a3['thr']:g}): the main Trishuli / Bhote Koshi floor ({s3e['stats']['VV']['main_floor']['n_px']:,} px, {s3e['observability']['observable_fraction']:.0%} radar-observable) against tributary floors ({s3e['stats']['VV']['trib_floor']['n_px']:,} px) and hillslope controls. Placebo: {s3p['args']['first']} → {s3p['args']['second']} on the same geometry.

| Band | Main floor decrease px | Tributary floor | Hillslope | Event excess, main − tributary [95% CI] | Placebo main floor; excess [95% CI] |
|---|---|---|---|---|---|
{s3row('VV')}
{s3row('VH')}

{s3_read}The U-Net (Sen1Floods11) flags {pct(un['post']):.2f}% of the corridor post and {pct(un['pre']):.2f}% pre: it does not separate the scenes and is not independent evidence."""))
    sec.append(("Exposure to the mask", f"""| Item | Headline (base mask) | Scenario range |
|---|---|---|
| Flagged area | {atot:.2f} km² ({a1:.2f} flood-like, {a2:.2f} dark, {a3:.2f} bright) | {area_rng} |
| Buildings overlapping the mask | {b['overlap']:,} ({b['overlap_flood']:,} flood-like class, {b['overlap_debris']:,} other surface change) of {b['total']:,} | {span(rr, 'buildings_overlap')} |
| Buildings within 30 m | {b['within_30m']:,} | {span(rr, 'buildings_within_30m')} |
| Buildings with unknown status | {unknown:,} ({unk_pct:.0f}%) | n/a |
| Motorable road in mask | {rb['motorable_road_km']:.1f} km ({rb['roads']} segments) | {span(rr, 'motorable_road_km', '{:.1f}')} km |
| Bridges exposed (not failed) | {rb['bridges']} of {imp['total_bridges']} | {span(rr, 'bridges_exposed')} |
| Settlements cut off (no path to a hospital) | {cut_n} of {cut['total_settlements']} | {span(rngc, 'hospital_cut_off')} |
| Settlements degraded (≥2× and ≥2 km longer) | {deg_n} | {span(rngc, 'hospital_degraded')} |
| Settlements not assessed (no pre-flood route) | {no_path} | n/a |

Range = 3 thresholds × mask ±1 px × bridges fail/survive. {cut_detail} Cut-off covers only the {cut['total_settlements'] - no_path} assessable settlements; {cut.get('hospitals_snapped', '?')} of {cut['hospitals_total']} hospitals were snapped to the road network."""))
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
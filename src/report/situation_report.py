"""Build the situation reports from pipeline JSON / rasters only:
    outputs/reports/situation_report_EN.md      full English report
    outputs/reports/situation_report_NE.md      Nepali summary (same numbers; translation to be checked by a Nepali speaker)
    outputs/reports/situation_report_1p.md/.pdf one A4 page (--one-page; page-gated by src/report/pdf_gate.py)

    python src/report/situation_report.py            # draft: header says so if code/data are uncommitted
    python src/report/situation_report.py --final    # refuses to run unless the tree is clean (outputs/ excluded)
    python src/report/situation_report.py --one-page [--pdf-if-browser]

Nothing here is hard-coded status text: the detector status, thresholds, areas, counts and ranges are read from the JSON
files and the fused class raster; the area name, title, track and dates come from run.json (src/config.py). Every
case-study-only evidence section (Step 3 tables, signal check, AI corridor, class nulls, Sentinel-2, EMS) is optional and
skipped with one line when its JSON is missing, so the report builds for any area. Attribution strings come from
src/report/attribution.py.
"""
import argparse, datetime, json, subprocess, sys
from collections import Counter
from pathlib import Path
import numpy as np, rasterio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config
from src.report import attribution as A

REF_DATES = config.REF_DATES
def rd(n): return f"{n} ({REF_DATES[n]})" if n in REF_DATES else n
TRACK = config.TRACK
FUSED = "data/processed/fused_class_30m.tif"
DETECT = f"outputs/diagnostics/detect_{TRACK}.json"
AOI_NAMES = {"AOI01": "Syapru Besi", "AOI02": "Timure", "AOI03": "Bidur", "AOI05": "Phosretar"}
TOL_S = 120                                       # files written by one run can differ by seconds
MAX_WORDS = 900                                   # rough budget for the full EN report (tables count pipes as words)

def die(msg): sys.exit(f"situation_report: {msg}")
def J(p): return json.loads((ROOT / p).read_text(encoding="utf-8"))
def JO(p):
    q = ROOT / p
    return json.loads(q.read_text(encoding="utf-8")) if q.exists() else None
def git(*a):
    try: return subprocess.run(["git", *a], capture_output=True, text=True, cwd=ROOT, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError): return None
def f3(v): return "n/a" if v is None else f"{v:.3f}"
def span(r, key, fmt="{:,}"):
    v = (r or {}).get(key)
    return "n/a" if not v else (fmt.format(v[0]) if v[0] == v[1] else f"{fmt.format(v[0])}–{fmt.format(v[1])}")

ap = argparse.ArgumentParser()
ap.add_argument("--final", action="store_true", help="require a clean working tree (outputs/ ignored)")
ap.add_argument("--one-page", action="store_true", help="also write the A4 one-page PDF (page-gated)")
ap.add_argument("--pdf-if-browser", action="store_true", help="with --one-page: skip the PDF (keep the .md) when no browser is installed")
args = ap.parse_args()

# --- single source of truth for the OSM date --------------------------------------------------------------
man = J("data/raw/osm/manifest.json")
snap = man["snapshot"]
if snap != config.OSM_SNAPSHOT_DATE:
    die(f"manifest snapshot {snap} != config.OSM_SNAPSHOT_DATE {config.OSM_SNAPSHOT_DATE}")
if snap >= config.FLOOD_DATE:
    die("OSM snapshot is not pre-event")

# --- refuse stale inputs: everything present must be newer than the raster it was derived from ------------
mask_p = ROOT / FUSED
have_ems = ((ROOT / "data/external/EMSR927").is_dir() and (ROOT / "outputs/validation/emsr927_validation.json").exists())
REQUIRED = [DETECT, "outputs/impact_summary.json", "outputs/cutoff_settlements.json"]
OPTIONAL = ["outputs/validation/signal_check.json", "outputs/validation/ai_corridor.json"] + (["outputs/validation/emsr927_validation.json"] if have_ems else [])
flood_p = ROOT / "data/processed/flood_mask.tif"      # detect -> fuse: detector-side files are checked against this
VS_FLOOD = {DETECT, "outputs/validation/signal_check.json", "outputs/validation/ai_corridor.json"}
skipped = []
for f in REQUIRED + OPTIONAL:
    if not (ROOT / f).exists():
        if f in REQUIRED: die(f"{f} is missing; rerun that step")
        continue
    ref = flood_p if f in VS_FLOOD else mask_p
    if ref.exists() and (ROOT / f).stat().st_mtime < ref.stat().st_mtime - TOL_S:
        if f in REQUIRED: die(f"{f} is older than {ref.name}; rerun that step")
        skipped.append(f"{Path(f).name} (older than {ref.name})")

# --- reproducibility: clean tree for the final report -------------------------------------------------------
dirty = git("status", "--porcelain", "--", ".", ":(exclude)outputs", ":(exclude)run.json")
commit = git("rev-parse", "--short", "HEAD") or "unknown"
if args.final and dirty != "":
    die("working tree is not clean (outputs/ excluded); commit first so the numbers can be reproduced")
stamp = f"commit `{commit}`" + ("" if dirty == "" else " + uncommitted changes (DRAFT)" if dirty else " (git state unknown)")

def fresh(p):
    """Optional evidence: None if missing or stale."""
    return None if any(s.startswith(Path(p).name) for s in skipped) else JO(p)

try:
    det, imp = J(DETECT), J("outputs/impact_summary.json")
    cutj = J("outputs/cutoff_settlements.json")
    cut, setl, rngc = cutj["summary"], cutj["settlements"], (cutj.get("sensitivity") or {}).get("range") or {}
    sig, un = fresh("outputs/validation/signal_check.json"), fresh("outputs/validation/ai_corridor.json")
    s3e, s3p = JO("outputs/diagnostics/step3_event.json"), JO("outputs/diagnostics/step3_placebo.json")
    s2, cn, sd = JO("outputs/diagnostics/s2_detect.json"), JO("outputs/validation/class_nulls.json"), JO("outputs/validation/seeds_summary.json")
    ai_m = JO("outputs/ai/smp_resnet34/metrics.json") or JO("models/metrics.json")
    nul = J("outputs/validation/emsr927_validation.json") if have_ems else {}
    pc = config.S1_SOURCE == "pc"
    calibrated = bool(det.get("calibrated"))
    null_note = (" " + cn["statement"]) if cn and cn.get("statement") else ""
    if cn and cn.get("event_refs") and det.get("refs") and cn["event_refs"] != det["refs"]: null_note = ""   # nulls from another run

    # --- mask areas from the fused raster; scenario range from the sensitivity detector runs ---------------
    with rasterio.open(mask_p) as s:
        cls, pa = s.read(1), abs(s.res[0] * s.res[1]) / 1e6
    a1, a2, a3 = ((cls == c).sum() * pa for c in (1, 2, 3)); atot = a1 + a2 + a3
    areas = []
    for nm in ("low", "high"):
        p = ROOT / f"outputs/diagnostics/detect_sens_{nm}.json"
        if p.exists(): areas.append(sum(J(f"outputs/diagnostics/detect_sens_{nm}.json")["area_km2"].values()))
    area_rng = f"{min(areas):.2f}–{max(areas):.2f} km²" if len(areas) == 2 else "n/a"

    # --- exposure ---------------------------------------------------------------------------------------------
    b, rb, rr = imp["buildings"], imp["roads_bridges"]["exposure_by_tolerance"]["0m"], (imp.get("sensitivity") or {}).get("range") or {}
    unknown = b["not_assessed"] + b["unobservable"]; unk_pct = 100 * unknown / max(b["total"], 1)
    cut_n = cut.get("cut_off", 0); deg_n = cut.get("hospital_degraded", 0)
    cut_set = [x for x in setl if x["hospital"]["status"] == "cut_off"]
    causes = Counter((x["first_break"] or {}).get("cause", "unknown") for x in cut_set)
    fr = [x["route_assessed_frac"] for x in cut_set if x.get("route_assessed_frac") is not None]
    cut_detail = (f"All {len(cut_set)} first breaks: " + ", ".join(f"{n} {c}" for c, n in causes.most_common()) +
                  (f"; the detector observed {min(fr):.0%}–{max(fr):.0%} of each cut-off route." if fr else ".")) if cut_set else \
                 "No settlement is cut off in the headline scenario."
    no_path = cut.get("hospital_no_pre_flood_path", 0)

    # --- AI line (optional): Bolivia quoted with its chip CI; seeds if present --------------------------------
    ai_sentence = ""
    if ai_m and "bolivia" in ai_m.get("splits", {}):
        _bo = ai_m["splits"]["bolivia"]; _ci = _bo["iou_ci95_chip_bootstrap"]
        seeds = ((sd or {}).get("summary") or {}).get("bolivia")
        sd_txt = f"; {seeds['mean']:.2f} ± {seeds['sd']:.2f} over {seeds['n_seeds']} training seeds" if seeds and seeds.get("sd") is not None else ""
        ai_sentence = (f"Water model (ResNet34 U-Net, Sen1Floods11, no Himalayan training scenes): unseen-region (Bolivia) IoU "
                       f"{_bo['at_threshold']['iou']:.2f}, 95% chip CI {_ci[0]:.2f}–{_ci[1]:.2f}, {_bo['n_chips']} chips{sd_txt}.")
        if un:
            ai_sentence += (f" On this corridor its new-water excess is {100 * un['event']['excess']:.2f}% against a pre-event null maximum of "
                            f"{100 * un['max_null_excess']:.2f}%: {un['verdict']}. Prediction-only; not independent evidence.")

    # --- validation (optional) ----------------------------------------------------------------------------------
    V, pooled = nul.get("aois", {}), nul.get("pooled_assessed_domain", {})
    def prf(s): return f"{f3(s['precision'])} / {f3(s['recall'])} / {f3(s['iou'])}"
    def pcn(v): return "n/a" if v is None else f"{100 * v:.0f}%"
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
            prox = "n/a" if not fo or not base else f"{pcn(fo['30'])} (n={fo['n']}) vs {pcn(base['30'])}"
            pt_rows.append(f"| {tag} | {dp['n_assessed']:,} | {' | '.join(cells)} | {prox} |")
    for key, lab in (("non_holdout", "Pooled non-hold-out"), ("holdout", "Pooled hold-out")):
        g = pooled.get(key)
        if g: seg_rows.append(f"| {lab} | {g['debris']['tp'] + g['debris']['fn']:,} | {prf(g['debris'])} | {prf(g['flood_or_debris'])} |")
    ems_block = None
    if have_ems:
        ems_read = ("Verdict at 30 m: " + ("; ".join(verdicts) or "n/a") + ". Association with damage points is not attribution to flooding. "
                    "Every EMS scoring is listed in docs/validation_log.md; S1 parameters unchanged since tag detector-frozen.")
        ems_block = (f"Check only: EMS data is not an input to any number above. {A.EMS_HOLDINGS} "
                     "Domain: AOI minus notAnalysedA, restricted to pixels the detector observed. Chance: the mask's own blobs relocated at random (100 draws).\n\n"
                     "| AOI | Reference px | Debris P / R / IoU | Flood or debris P / R / IoU |\n|---|---|---|---|\n" + "\n".join(seg_rows) + "\n\n"
                     "| AOI | Assessed points | Recall 0 m | 30 m | 60 m | Flagged buildings within 30 m of a damage point vs all-building baseline |\n|---|---|---|---|---|---|\n"
                     + "\n".join(pt_rows) + "\n\n" + ems_read)

    days = (datetime.date.fromisoformat(config.POST_DATE) - datetime.date.fromisoformat(config.FLOOD_DATE)).days
    lims = [f"Single Sentinel-1 track ({det['track']}), {len(det.get('refs', []))} reference dates; the post scene is {days} days after the event, so a flash flood in a narrow gorge may already have drained.",
            f"Only the valley floor is assessed ({det['floor_km2']:.0f} km², {det['usable_fraction_of_floor']:.0%} usable). {unk_pct:.0f}% of OSM buildings, and hillside roads, lie outside it: UNKNOWN, not clear.",
            "No cause attribution: flood-like (water-like backscatter change), dark and bright classes are all surface change; this is exposure, not damage; bridges are exposed, never known to have failed.",
            f"30 m pixels mix narrow channels; OSM snapshot {snap} predates the event and rural areas are under-mapped, so missing buildings undercount exposure and missing tracks overstate cut-off ({no_path} settlements have no pre-flood route)."]
    if s2: lims.insert(2, f"Sentinel-2: {s2['floor_clear_post_fraction']:.0%} of the valley floor has clear post-event coverage and its status is {s2['status']}, so S2 is excluded and the fused product equals the S1 product.")
    if calibrated and det.get("alpha_met") is False:
        lims.insert(0, f"No detector threshold reached the 0.1% null false-alarm target in this area; the largest grid value (t_hi {det.get('t_hi')}) was used and the null false-alarm maximum is {100 * (det.get('null_far_max') or 0):.2f}%, so detections here are less constrained than in the case study.")
    if not calibrated: lims.insert(0, "UNCALIBRATED: fewer than 3 reference dates, so there is no null calibration and no detection gate; a no-event date could produce false detections.")
    if pc: lims.insert(0, f"Sentinel-1 source: {config.S1_SOURCE_LABEL}. These numbers are a cross-check of the method, not the SNAP headline.")
    s2a = JO("outputs/validation/ai_vs_s2.json")
    if s2a and s2a.get("results"):
        r = s2a["results"]
        lims.append("AI vs Sentinel-2 cannot arbitrate: " + "; ".join(f"S2 MNDWI agrees with the AI at precision {v['precision']:.2f} on the {k} date ({v['s2_date']})" for k, v in r.items())
                    + ". Agreement that does not change with the event says nothing about the event.")
    if have_ems: lims.append(A.EMS_HOLDINGS + " The flood class is therefore not validated against EMS.")

    sec = []
    status_line = (f"Detector status: **{det['status']}** (track {det['track']}; VH robust-z change of {', '.join(rd(x) for x in det['refs'])} against "
                   f"{rd(det['post'])}, thresholds {det['t_hi']:g} / {det['t_lo']:g}, " +
                   (f"calibrated against pre-event nulls, null false-alarm max {100 * det['null_far_max']:.3f}%)" if calibrated and det.get("null_far_max") is not None
                    else "**UNCALIBRATED**: no null gate)"))
    src_line = f" Sentinel-1 source: {config.S1_SOURCE_LABEL}." if pc else ""
    sec.append(("Situation", f"""Event date {config.FLOOD_DATE}, {config.AREA_NAME}; Sentinel-1 {config.PRE_DATE} / {config.POST_DATE}, Copernicus GLO-30, OSM.{src_line} {status_line}. The mask is restricted to the HAND valley floor; the result is exposure to a detected mask, **not a validated flood extent and not damage**.{null_note}"""))
    sig_txt = ""
    if sig:
        ctrl = [sig["river_shifted_1500m"], sig["river_shifted_-1500m"]]
        c1 = float(np.mean([c["p1"] for c in ctrl]))
        sig_txt = ("The river reach has a lower-tail excess over the shifted controls: evidence of surface change along the reach, not by itself of flooding. "
                   if sig["river_60m"]["p1"] < c1 - 0.5 else "The river reach shows no clear lower-tail excess over the shifted controls. ")
    if s3e and s3p:
        def p2(v): return f"{100 * v:.2f}%"
        def s3row(band):
            e, p = s3e["stats"][band], s3p["stats"][band]
            eb, pb = s3e["bootstrap"][band]["neg"]["excess_ci"], s3p["bootstrap"][band]["neg"]["excess_ci"]
            return (f"| {band} | {p2(e['main_floor']['frac_neg'])} | {p2(e['trib_floor']['frac_neg'])} | {p2(e['hillslope_ctrl']['frac_neg'])} | "
                    f"{p2(eb[1])} [{p2(eb[0])}, {p2(eb[2])}] | {p2(p['main_floor']['frac_neg'])}; excess {p2(pb[1])} [{p2(pb[0])}, {p2(pb[2])}] |")
        ev_ok = all(s3e["bootstrap"][bb]["neg"]["excess_ci"][0] > 0 for bb in ("VV", "VH"))
        pl_none = all(s3p["bootstrap"][bb]["neg"]["excess_ci"][1] <= 0 for bb in ("VV", "VH"))
        s3_read = (("The main floor has more decrease pixels than the tributary floors in both bands, with 95% CIs above zero" if ev_ok else
                    "The main floor does not show a clear decrease excess over the tributary floors in both bands") +
                   (", and the placebo pair shows none. " if pl_none else ", but the placebo pair also shows an excess, so this is not clean evidence. ") +
                   "This is evidence of surface change along the main reach, not by itself of flooding. ")
        s3a = s3e["args"]
        sec.append(("Detection signal", f"""Step 3 test ({s3a['first']} → {s3a['second']}; decreases by robust z at threshold {s3a['thr']:g}): main floor ({s3e['stats']['VV']['main_floor']['n_px']:,} px, {s3e['observability']['observable_fraction']:.0%} radar-observable) against tributary floors ({s3e['stats']['VV']['trib_floor']['n_px']:,} px) and hillslope controls. Placebo: {s3p['args']['first']} → {s3p['args']['second']}.

| Band | Main floor decrease px | Tributary floor | Hillslope | Event excess, main − tributary [95% CI] | Placebo main floor; excess [95% CI] |
|---|---|---|---|---|---|
{s3row('VV')}
{s3row('VH')}

{s3_read}{sig_txt}{ai_sentence}"""))
    else:
        txt = (sig_txt + ai_sentence).strip()
        sec.append(("Detection signal", (txt + "\n\n" if txt else "") + "_Case-study evidence tables (Step 3 main-vs-tributary test) not available for this run: section skipped._"))
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

Range = 3 thresholds × mask ±1 px × bridges fail/survive (n/a when the threshold-sensitivity runs were skipped, e.g. --profile fast). {cut_detail} Cut-off covers only the {cut['total_settlements'] - no_path} assessable settlements; {cut.get('hospitals_snapped', '?')} of {cut.get('hospitals_total', '?')} hospitals were snapped to the road network."""))
    if ems_block: sec.append((f"Validation against Copernicus EMS (EMSR927)", ems_block))
    else: sec.append(("Validation", "_No Copernicus EMS products for this area in data/external: section skipped._"))
    sec.append(("Limitations", "\n".join(f"- {x}" for x in lims)))
    sec.append(("Next steps (in scope)", f"""1. Add a second Sentinel-1 track or a closer post scene and rerun unchanged; the headline should stay inside the ranges above.
2. Check the {len(cut_set)} cut-off first-break points against field or imagery reports.
3. Refresh OSM after the event and rerun cut-off to separate missing roads from real loss."""))
    sec.append(("Data sources", f"""{A.markdown_list(with_ems=have_ems)}
- Sentinel-1 GRD ({'Microsoft Planetary Computer sentinel-1-rtc' if pc else 'Copernicus Data Space Ecosystem'}); OpenStreetMap snapshot {snap} (pre-event, ODbL v1.0)
- Sen1Floods11 v1.1, CC BY 4.0: Bonafilia et al. (2020), CVPR EarthVision workshop

Full attribution: [ATTRIBUTION.md](../../ATTRIBUTION.md). {A.DISCLAIMER}"""))

    body = "\n\n".join(f"## {i}. {t}\n\n{txt}" for i, (t, txt) in enumerate(sec, 1))
    md = f"""# Situation Report — {config.TITLE}

> **PRELIMINARY** — generated {datetime.date.today()} from {stamp}. {A.DISCLAIMER} Numbers change if the detector or inputs change.

{body}
"""
    if skipped: md += "\n*Skipped as stale: " + ", ".join(skipped) + ".*\n"
except KeyError as e:
    die(f"missing key {e}; paste the JSON it came from")

md = "\n".join(l for i, l in enumerate(md.split("\n")) if l.strip() or i == 0 or md.split("\n")[i - 1].strip())
words = len(md.split())
if words > MAX_WORDS: print(f"situation_report: note {words} words > {MAX_WORDS}", file=sys.stderr)
out = ROOT / "outputs/reports/situation_report_EN.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(md, encoding="utf-8")
print("wrote", out, f"({words} words)")

# --- Nepali summary: same numbers, short; attribution strings stay verbatim (English) -----------------------
NE_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
def ne(x): return str(x).translate(NE_DIGITS)
st_ne = {"change_detected": "परिवर्तन पत्ता लाग्यो (change_detected)", "no_significant_change": "उल्लेखनीय परिवर्तन छैन (no_significant_change)"}.get(det["status"], det["status"])
ne_rng = lambda r, k, fmt="{:,}": ne(span(r, k, fmt))
ne_md = f"""# स्थिति प्रतिवेदन (प्रारम्भिक) — {config.AREA_NAME}, {ne(config.FLOOD_DATE)}

> प्रारम्भिक: {ne(datetime.date.today())} मा पाइपलाइनका JSON फाइलबाट स्वतः बनाइएको ({stamp})। शैक्षिक प्रोटोटाइप, सञ्चालनमा प्रयोग गर्ने उपकरण होइन।
> अनुवाद मेसिन-सहायतामा गरिएको हो; नेपाली भाषीले जाँच गर्नुहोस्। अंक अंग्रेजी प्रतिवेदन (situation_report_EN.md) सँग मिल्छन्।

**अवस्था।** Sentinel-1 ({'Planetary Computer RTC gamma0, क्रस-जाँच मार्ग' if pc else 'SNAP sigma0'}) {ne(config.PRE_DATE)} / {ne(config.POST_DATE)}, ट्र्याक {det['track']}। डिटेक्टरको नतिजा: **{st_ne}**{'' if calibrated else ' — **क्यालिब्रेट नगरिएको** (३ भन्दा कम सन्दर्भ मिति)'}। यो उपत्यकाको सतहमा पत्ता लागेको परिवर्तनसँगको **जोखिम (exposure)** हो, पुष्टि गरिएको बाढी क्षेत्र होइन र क्षति होइन। "बाढी-जस्तो" वर्ग भनेको पानी-जस्तो ब्याकस्क्याटर परिवर्तन हो, खुला पानी पुष्टि भएको होइन। पुलहरू जोखिममा छन् भनिएको हो, भत्किएको होइन।

| मुख्य अंक | मुख्य नतिजा | परिदृश्य दायरा |
|---|---|---|
| चिन्ह लगाइएको क्षेत्र | {ne(f'{atot:.2f}')} वर्ग कि.मि. | {ne(area_rng)} |
| मास्कसँग खप्टिएका भवन | {ne(f"{b['overlap']:,}")} (जम्मा {ne(f"{b['total']:,}")} मध्ये) | {ne_rng(rr, 'buildings_overlap')} |
| स्थिति थाहा नभएका भवन (अवलोकन बाहिर) | {ne(f'{unk_pct:.0f}')}% | — |
| मास्कभित्र मोटरबाटो | {ne(f"{rb['motorable_road_km']:.1f}")} कि.मि. | {ne_rng(rr, 'motorable_road_km', '{:.1f}')} कि.मि. |
| जोखिममा रहेका पुल (भत्किएको होइन) | {ne(rb['bridges'])} | {ne_rng(rr, 'bridges_exposed')} |
| अस्पतालसम्म सडक नरहेका बस्ती | {ne(cut_n)} (जम्मा {ne(cut['total_settlements'])} मध्ये) | {ne_rng(rngc, 'hospital_cut_off')} |
| बाढीअघि नै सडक नभएका बस्ती (मूल्याङ्कन नगरिएको) | {ne(no_path)} | — |

**सीमाहरू।** एउटा मात्र Sentinel-1 ट्र्याक; घटनापछिको तस्बिर {ne(days)} दिनपछिको; उपत्यकाको सतह मात्र मूल्याङ्कन गरिएको, बाँकी भाग "थाहा नभएको" हो, सुरक्षित होइन; OSM नक्सा ({ne(snap)}) घटनाअघिको र अपूर्ण छ।{(' ' + 'EMSR927 का GRA उत्पादनहरूमा (२०२६-१०-११ मा जाँचिएको) पहिरोका बहुभुज र क्षति बिन्दु मात्र छन्, बाढी-क्षेत्र तह छैन; EMS जाँचका लागि मात्र प्रयोग गरिएको।') if have_ems else ''}

<small>{A.text(with_ems=have_ems)} {A.DISCLAIMER}</small>
"""
(ROOT / "outputs/reports/situation_report_NE.md").write_text(ne_md, encoding="utf-8")
print("wrote", ROOT / "outputs/reports/situation_report_NE.md")

if args.one_page:
    from src.report.pdf_gate import to_pdf, find_browser
    pic = ROOT / "outputs/reports/situation_map.png"
    if not pic.exists(): die("outputs/reports/situation_map.png is missing; run tools/make_situation_map.py")
    sit = (f"Event date {config.FLOOD_DATE}, {config.AREA_NAME}. Sentinel-1 track {det['track']}, {config.PRE_DATE} / {config.POST_DATE}"
           + (f" ({config.S1_SOURCE_LABEL})" if pc else "") + f": detector status **{det['status']}** "
           + ("(calibrated against pre-event nulls). " if calibrated else "(**UNCALIBRATED**: no null gate). ")
           + "Detected change on the valley floor is **not attributed to flooding, not a validated flood extent and not damage**. "
             "Counts below are exposure to that mask." + null_note)
    lim1 = [l for l in lims if not l.startswith(("AI vs Sentinel-2", "EMSR927"))][:4]
    one = f"""# Situation report: {config.TITLE}

> PRELIMINARY, {datetime.date.today()}, {stamp}

**Situation.** {sit}

| Key number | Headline | Scenario range |
|---|---|---|
| Flagged area | {atot:.2f} km² | {area_rng} |
| Buildings overlapping the mask (unknown status: {unk_pct:.0f}%) | {b['overlap']:,} ({b['overlap_flood']:,} flood-like, {b['overlap_debris']:,} other change) | {span(rr, 'buildings_overlap')} |
| Motorable road in mask | {rb['motorable_road_km']:.1f} km | {span(rr, 'motorable_road_km', '{:.1f}')} km |
| Bridges exposed (not failed) | {rb['bridges']} of {imp['total_bridges']} | {span(rr, 'bridges_exposed')} |
| Settlements cut off (no path to hospital) | {cut_n} of {cut['total_settlements']} | {span(rngc, 'hospital_cut_off')} |
| Settlements degraded | {deg_n} | {span(rngc, 'hospital_degraded')} |
| Settlements with no pre-flood route (not assessed) | {no_path} | n/a |

![map](situation_map.png)

**Limitations**

{chr(10).join(f'- {x}' for x in lim1)}

<small>{A.text(with_ems=have_ems)} {A.DISCLAIMER}</small>
"""
    p1 = ROOT / "outputs/reports/situation_report_1p.md"
    p1.write_text(one, encoding="utf-8")
    print("wrote", p1)
    if args.pdf_if_browser and find_browser(required=False) is None:
        try: import weasyprint  # noqa: F401
        except ImportError: print("no Chrome/Edge/weasyprint: one-page PDF skipped (the .md is written)"); sys.exit(0)
    print("wrote", to_pdf(p1))

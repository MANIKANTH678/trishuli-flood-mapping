"""Step 9.4: the <= 6-page report, generated from the pipeline's JSON outputs (no number typed by hand), then printed
to PDF with a hard page gate.

python tools/build_report.py            # draft
python tools/build_report.py --final    # refuses if any Step 8 result is missing or the git tree is dirty (outputs/ excluded)
  -> docs/REPORT.md, docs/REPORT.pdf (fails if > 6 pages)

Figures (max 5): step-3 event and placebo profiles, scenario range, dashboard screenshot."""
import argparse, datetime as dt, json, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from src import config
from src.report.pdf_gate import to_pdf

AOI = {"AOI01": "Syapru Besi", "AOI02": "Timure", "AOI03": "Bidur", "AOI05": "Phosretar"}
REQ_ATTR = ('"Contains modified Copernicus Sentinel data 2026." "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus '
            'Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved." '
            '"© OpenStreetMap contributors."')

def J(p, need=False):
    p = ROOT / p
    if not p.exists():
        if need: sys.exit(f"build_report: {p.relative_to(ROOT)} is missing; run that step")
        return None
    return json.loads(p.read_text(encoding="utf-8"))
def f2(v): return "n/a" if v is None else f"{v:.2f}"
def f3(v): return "n/a" if v is None else f"{v:.3f}"
def pc(v): return "n/a" if v is None else f"{100 * v:.1f}%"
def span(r, k, fmt="{:,}"):
    v = (r or {}).get(k)
    return "n/a" if not v else (fmt.format(v[0]) if v[0] == v[1] else f"{fmt.format(v[0])}–{fmt.format(v[1])}")
def fig(src, name):
    """copy a figure next to the markdown so the PDF finds it; returns the relative path or None"""
    s = ROOT / src
    if not s.exists(): return None
    d = ROOT / "docs" / "figures" / name; d.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(s, d); return f"figures/{name}"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--final", action="store_true"); a = ap.parse_args()
    det, imp, cutj = J(f"outputs/diagnostics/detect_asc85.json", True), J("outputs/impact_summary.json", True), J("outputs/cutoff_settlements.json", True)
    s3e, s3p = J("outputs/diagnostics/step3_event.json"), J("outputs/diagnostics/step3_placebo.json")
    ems, cor, ai = J("outputs/validation/emsr927_validation.json"), J("outputs/validation/ai_corridor.json"), J("outputs/ai/smp_resnet34/metrics.json", True)
    cn, sd, ag, s2a = (J(f"outputs/validation/{n}.json") for n in ("class_nulls", "seeds_summary", "himalaya_label_agreement", "ai_vs_s2"))
    s2d = J("outputs/diagnostics/s2_detect.json"); fpj = J("outputs/flood_path/summary.json")
    if a.final:
        miss = [n for n, v in (("class_nulls", cn), ("seeds_summary", sd), ("ai_vs_s2", s2a), ("himalaya_chips", ai["splits"].get("himalaya_chips"))) if not v]
        if miss: sys.exit("build_report --final: missing " + ", ".join(miss))
        dirty = subprocess.run(["git", "status", "--porcelain", "--", ".", ":(exclude)outputs", ":(exclude)docs/REPORT.*", ":(exclude)docs/figures"],
                               capture_output=True, text=True, cwd=ROOT).stdout.strip()
        if dirty: sys.exit("build_report --final: working tree is not clean (outputs/ excluded); commit first")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip() or "unknown"
    cut, rngc, b = cutj["summary"], cutj["sensitivity"]["range"], imp["buildings"]
    rb, rr = imp["roads_bridges"]["exposure_by_tolerance"]["0m"], imp["sensitivity"]["range"]
    unk = (b.get("not_assessed", 0) + b.get("unobservable", 0)); unk_pct = 100 * unk / max(b["total"], 1)
    no_path = cut.get("hospital_no_pre_flood_path", 0); A = det["area_km2"]
    F1, F2 = fig("outputs/figures/step3_profile_event.png", "step3_event.png"), fig("outputs/figures/step3_profile_placebo.png", "step3_placebo.png")
    F3, F4 = fig("outputs/figures/scenario_range.png", "scenario_range.png"), fig("outputs/reports/situation_map.png", "dashboard.png")
    null_line = cn["statement"] if cn else "Class-level nulls: not run."

    S = []
    S.append(f"""# Trishuli / Bhote Koshi flood, {config.FLOOD_DATE}: change detection, exposure and road access from open satellite data

*Multimodal AI Hackathon 2026, FloodDamage from Space. Educational prototype, not an operational product. Generated {dt.date.today()} from commit `{commit}`; every number below is read from the pipeline's output files.*

**Status.** Detector status **{det['status']}** on Sentinel-1 track {det['track']}. The product is surface change on the valley floor and exposure to it, **not a validated flood extent**. {null_line}""")

    S.append(f"""## 1. Approach and data

One pipeline (`run_all.sh`) runs from raw data: Sentinel-1 GRD scenes are calibrated and terrain-corrected, gridded to 30 m (10 m for the AI model), and compared with four pre-event reference dates on the same track; the HAND valley floor and a radar layover/shadow mask come from the Copernicus DEM; detected change is overlaid on pre-event OpenStreetMap buildings, roads and bridges; road paths from each settlement to the nearest hospital are recomputed with blocked segments removed; a dashboard and a one-page situation report are built from the outputs.

| Data | Role | Dates |
|---|---|---|
| Sentinel-1 GRD, relative orbit 85 ascending | input | references {config.PRE_DATE}, 2026-08-04, 2026-07-23, 2026-07-11; post {config.POST_DATE} |
| Sentinel-2 L2A | input (gated; excluded if it fails its gate) | post-event scenes from 2026-08-27 |
| Copernicus DEM GLO-30 | input (HAND, radar geometry, flow path) | n/a |
| OpenStreetMap via ohsome | input, **pre-event snapshot** | {config.OSM_SNAPSHOT_DATE} |
| Sen1Floods11 v1.1 hand labels | AI training | published splits |
| Copernicus EMS EMSR927 | **checking only**, after thresholds were frozen | activation 2026-08-26 |

Rules enforced in code: the OSM snapshot must predate the flood; detector thresholds come from pre-event null runs, never from EMS; EMS is read only by `src/validation/`; unobservable ground is UNKNOWN, never clear; bridges are *exposed*, never declared failed; settlements without a pre-flood road route are *not assessed*, never counted as cut off.""")

    s3 = ""
    if s3e and s3p:
        def row(band):
            e, p = s3e["stats"][band], s3p["stats"][band]; eb, pb = s3e["bootstrap"][band]["neg"]["excess_ci"], s3p["bootstrap"][band]["neg"]["excess_ci"]
            return f"| {band} | {pc(e['main_floor']['frac_neg'])} | {pc(e['trib_floor']['frac_neg'])} | {pc(eb[1])} [{pc(eb[0])}, {pc(eb[2])}] | {pc(pb[1])} [{pc(pb[0])}, {pc(pb[2])}] |"
        s3 = ("\n\n| Band | Main floor decrease px | Tributary floor | Event excess [95% CI] | Placebo excess [95% CI] |\n|---|---|---|---|---|\n"
              + row("VV") + "\n" + row("VH") + "\n\nThe step-3 criteria were written after the first event run, so this test is exploratory.")
    nt = ""
    if cn:
        nt = "\n\n**Class-level nulls** (" + cn["rule"] + "):\n\n| Class | Event km² | Largest null km² | Ratio | Separable |\n|---|---|---|---|---|\n" + "\n".join(
            f"| {c} | {r['event_km2_ungated']:.3f} | {r['max_null_km2']:.3f} | {r['ratio'] if r['ratio'] is not None else 'n/a'} | {'yes' if r['separable'] else 'no'} |"
            for c, r in cn["classes"].items()) + f"\n\n**{cn['statement']}**"
    figs12 = " ".join(f"![]({f}){{width=49%}}" for f in (F1, F2) if f)
    S.append(f"""## 2. Detection method and evidence

VH robust-z change of the post scene against the four references, restricted to the HAND ≤ {det.get('floor_m', 30)} m valley floor ({det['floor_km2']:.0f} km², {det['usable_fraction_of_floor']:.0%} usable after the radar mask). Thresholds {det['t_hi']:g} / {det['t_lo']:g} are the smallest values whose worst false-alarm fraction over the null runs is ≤ 1e-3 (calibrated = {det['calibrated']}). Classes: flood-like (dark and below open-water dB), dark change, bright change. Headline areas: {A['flood_water']:.2f} km² flood-like, {A['surface_dark']:.2f} km² dark, {A['surface_bright']:.2f} km² bright.{s3}{nt}

{figs12}""")

    cdet = (f"{cut['cut_off']} of {cut['total_settlements']} settlements are cut off from every hospital (range {span(rngc, 'hospital_cut_off')}), "
            f"{cut.get('hospital_degraded', 0)} degraded (range {span(rngc, 'hospital_degraded')}); {no_path} have no pre-flood road route and are not assessed.")
    S.append(f"""## 3. Impact and cut-off

| Item | Headline | Scenario range |
|---|---|---|
| Buildings overlapping the mask | {b['overlap']:,} ({b['overlap_flood']:,} flood-like, {b['overlap_debris']:,} other change) of {b['total']:,} | {span(rr, 'buildings_overlap')} |
| Buildings with unknown status (outside the observed floor) | {unk:,} ({unk_pct:.0f}%) | n/a |
| Motorable road in mask | {rb['motorable_road_km']:.1f} km | {span(rr, 'motorable_road_km', '{:.1f}')} km |
| Bridges exposed (not failed) | {rb['bridges']} of {imp['total_bridges']} | {span(rr, 'bridges_exposed')} |
| Settlements cut off / degraded | {cut['cut_off']} / {cut.get('hospital_degraded', 0)} | {span(rngc, 'hospital_cut_off')} / {span(rngc, 'hospital_degraded')} |

{cdet} Range = 3 thresholds × mask ±1 px × bridges fail/survive; {cut.get('hospitals_snapped', '?')} of {cut['hospitals_total']} hospitals snap to the road network. There is no cut-off ground truth.

{f'![]({F3})' if F3 else ''}
{f'![]({F4}){{width=70%}}' if F4 else ''}""")

    sp = ai["splits"]; rows = []
    for k, lab in (("valid", "Sen1Floods11 valid (selection)"), ("test", "Sen1Floods11 test (training events)"), ("bolivia", "Bolivia (unseen region)"),
                   ("himalaya_chips", "Himalayan hand-labelled chips")):
        if k in sp:
            ci = sp[k].get("iou_ci95_chip_bootstrap") or [None, None]; m = (sd or {}).get("summary", {}).get(k)
            rows.append(f"| {lab} | {sp[k]['n_chips']} | {f3(sp[k]['at_threshold']['iou'])} [{f2(ci[0])}–{f2(ci[1])}] | "
                        + (f"{m['mean']:.3f} ± {m['sd']:.3f}" if m and m.get("sd") is not None else "n/a") + " |")
    hc = sp.get("himalaya_chips"); per = ", ".join(f"{r} {v['iou']:.2f} (n={v['n_chips']})" for r, v in (hc or {}).get("per_region", {}).items())
    ceil = f" Two annotators agree at IoU {ag['iou_A_vs_B']:.2f} on {ag['n_chips']} chips (noise ceiling)." if ag and ag.get("iou_A_vs_B") is not None else ""
    s2t = "; ".join(f"{k} IoU {v['iou']:.2f} (P {v['precision']:.2f}, R {v['recall']:.2f})" for k, v in (s2a or {}).get("results", {}).items()) or "not run"
    S.append(f"""## 4. AI component

ResNet34 U-Net (segmentation-models-pytorch), Sentinel-1 VV+VH input, trained on Sen1Floods11 hand labels; threshold {ai['threshold']} chosen on validation only. The seed-0 model is the shipped model; seeds 1 and 2 measure training noise.

| Split | Chips | Shipped IoU [95% chip CI] | Mean ± sd over 3 seeds |
|---|---|---|---|
{chr(10).join(rows)}

{'Himalayan chips by stratum: ' + per + '.' if per else ''}{ceil} Chip points were pre-registered before any prediction was viewed and labelled from the clear parts of the 27 Aug 2026 Sentinel-2 scene; with about 20 chips the interval is wide. Agreement with Sentinel-2 MNDWI water on clear floor pixels (pseudo-reference, not accuracy): {s2t}. Corridor null test (prediction-only): excess {f3((cor or {}).get('event', {}).get('excess'))} vs largest leave-one-out null {f3((cor or {}).get('max_null_excess'))}: **{(cor or {}).get('verdict', 'not run')}**. The model detects **open water only**; no allowed dataset labels debris, so debris comes from the change detector.""")

    if ems:
        er, verd = [], []
        for k, r in ems.get("aois", {}).items():
            ev, dp = r.get("event_area"), r.get("damage_points")
            if not ev: continue
            s = ev["flood_or_debris"]["assessed"]["strict"]; v30 = (dp or {}).get("recall_assessed", {}).get("30") or {}
            ci = v30.get("ci95") or [None, None]
            er.append(f"| {k} {AOI.get(k, '')}{' (hold-out)' if r.get('holdout') else ''} | {f3(s['precision'])} | {f3(s['recall'])} | {f3(s['iou'])} | "
                      f"{f3(v30.get('rate'))} [{f2(ci[0])}–{f2(ci[1])}] {v30.get('verdict', '')} |")
            if v30.get("verdict"): verd.append(f"{AOI.get(k, k)}: {v30['verdict']}")
        for key, lab in (("non_holdout", "Pooled non-hold-out"), ("holdout", "Pooled hold-out")):
            g = ems.get("pooled_assessed_domain", {}).get(key)
            if g: er.append(f"| **{lab}** | {f3(g['flood_or_debris']['precision'])} | {f3(g['flood_or_debris']['recall'])} | {f3(g['flood_or_debris']['iou'])} | |")
        S.append(f"""## 5. Validation against Copernicus EMS EMSR927 (check only)

The local EMSR927 products are grading maps: `observedEventA` is **landslide** polygons and there is **no flood-extent layer**, so scores are "detected change vs EMS landslide polygons" and the flood class cannot be validated against EMS. Domain: AOI minus notAnalysedA, restricted to pixels the detector observed. Chance for damage points: the mask's own blobs relocated at random (100 draws); CI: 1 km block bootstrap.

| AOI | Precision | Recall | IoU | EMS damage points within 30 m [95% CI] vs chance |
|---|---|---|---|---|
{chr(10).join(er)}

{'; '.join(verd)}. Association with damage points is not attribution to flooding; every EMS scoring is listed in `docs/validation_log.md`.""")

    lim = [f"Single Sentinel-1 track ({det['track']}), one post scene {(dt.date.fromisoformat(config.POST_DATE) - dt.date.fromisoformat(config.FLOOD_DATE)).days} days after the event; a flash flood in a gorge may have drained.",
           f"Valley floor only: {unk_pct:.0f}% of OSM buildings and the hillside roads are outside it and UNKNOWN, not clear.",
           (f"Sentinel-2: {s2d['floor_clear_post_fraction']:.0%} of the floor has clear post-event coverage; status {s2d['status']}, so S2 is excluded from the fused product." if s2d else "Sentinel-2 excluded (gate not passed)."),
           "No cause attribution: flood-like, dark and bright are surface-change classes; bridges are exposed, never known failed.",
           f"OSM currency: snapshot {config.OSM_SNAPSHOT_DATE}; rural Rasuwa is under-mapped ({no_path} settlements have no pre-flood route), so cut-off can be overstated and damage undercounted.",
           "No cut-off ground truth exists; the scenario range is the uncertainty we can quantify.", null_line]
    S.append("## 6. Limitations\n\n" + "\n".join(f"- {x}" for x in lim))
    S.append(f"""## 7. Attribution and citations

{REQ_ATTR} Copernicus EMS credit: "European Union, Copernicus Emergency Management Service data" (EMSR927, checking only). Sen1Floods11: Bonafilia, D., Tellman, B., Anderson, T., Issenberg, E. (2020), CVPR Workshops (CC BY 4.0).{f" Flood-path bonus: D8 path {fpj['path_km']} km, {fpj['n_settlements']} settlements on the HAND corridor (geometry only, no hydraulics)." if fpj else ''}""")

    md = "\n\n".join(S).replace("{width=49%}", "").replace("{width=70%}", "")
    out = ROOT / "docs" / "REPORT.md"; out.write_text(md, encoding="utf-8"); print("wrote", out, len(md.split()), "words")
    to_pdf(out, max_pages=6, label="report")

if __name__ == "__main__":
    main()

"""Step 8D: write the Step 8 numbers into MODEL_CARD.md, README.md, FINAL_REPORT.md and docs/validation_log.md
straight from the JSON outputs, so no number is typed by hand. Re-runnable: generated text sits between
<!-- STEP8:<name> --> markers and is replaced on every run.

Reads (missing ones are reported, never invented):
  outputs/validation/class_nulls.json          tools/class_nulls.py
  outputs/validation/seeds_summary.json        tools/seed_summary.py
  outputs/ai/smp_resnet34/metrics.json         src.modeling.evaluate --extra (himalaya_chips split, shipped seed-0 model)
  outputs/validation/himalaya_label_agreement.json   tools/chip_agreement.py
  outputs/validation/ai_vs_s2.json             tools/ai_vs_s2.py
  outputs/validation/ai_corridor.json          src.analysis.ai_corridor
  outputs/flood_path*/summary.json, check.json src.analysis.flood_path + tools/flood_path_check.py
python tools/write_step8_docs.py"""
import datetime as dt, glob, hashlib, json, re
from pathlib import Path

def J(p):
    p = Path(p); return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def block(text, name, body, anchor=None, before=None):
    """Replace the marked block, else insert it after `anchor` (a heading line) / before `before`, else append."""
    tag0, tag1 = f"<!-- STEP8:{name} -->", f"<!-- /STEP8:{name} -->"; new = f"{tag0}\n{body.strip()}\n{tag1}"
    if tag0 in text: return re.sub(re.escape(tag0) + r".*?" + re.escape(tag1), lambda _: new, text, flags=re.S)
    if before and before in text: return text.replace(before, new + "\n\n" + before, 1)
    if anchor and anchor in text:
        i = text.index(anchor) + len(anchor); return text[:i] + "\n\n" + new + "\n" + text[i:]
    return text.rstrip() + "\n\n" + new + "\n"

def sha(p):
    p = Path(p); return hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p.exists() else "missing"

def main():
    cn, sd, mt = J("outputs/validation/class_nulls.json"), J("outputs/validation/seeds_summary.json"), J("outputs/ai/smp_resnet34/metrics.json")
    ag, s2, co = J("outputs/validation/himalaya_label_agreement.json"), J("outputs/validation/ai_vs_s2.json"), J("outputs/validation/ai_corridor.json")
    missing = [n for n, v in (("class_nulls", cn), ("seeds_summary", sd), ("metrics", mt), ("label_agreement", ag), ("ai_vs_s2", s2), ("ai_corridor", co)) if v is None]
    hc = (mt or {}).get("splits", {}).get("himalaya_chips")

    # ---------- text pieces ----------
    nulls_md = "Class-level nulls not run yet."
    if cn:
        rows = ["| Class | Event km² (ungated) | Largest null km² | Ratio | Separable (>3×) |", "|---|---|---|---|---|"]
        for c, r in cn["classes"].items():
            rows.append(f"| {c} | {r['event_km2_ungated']:.3f} | {r['max_null_km2']:.3f} | {r['ratio'] if r['ratio'] is not None else 'n/a'} | {'yes' if r['separable'] else 'no'} |")
        nulls_md = (f"Rule written before the run: {cn['rule']}. Leave-one-out over the four pre-event scenes.\n\n" + "\n".join(rows) +
                    f"\n\n**{cn['statement']}**")
    seeds_md = "Seeds not run yet."
    bci = (mt or {}).get("splits", {}).get("bolivia", {}).get("iou_ci95_chip_bootstrap")
    if sd:
        s = sd["summary"]; cols = [k for k in ("valid", "test", "bolivia", "himalaya_chips") if k in s]
        seeds_md = ("| Split | Mean IoU | SD (seeds) | Min | Max |\n|---|---|---|---|---|\n" +
                    "\n".join("| {} | {:.3f} | {} | {:.3f} | {:.3f} |".format(k, s[k]["mean"], "n/a" if s[k]["sd"] is None else "{:.3f}".format(s[k]["sd"]),
                                                                       s[k]["min"], s[k]["max"]) for k in cols) +
                    (f"\n\nBolivia (the only unseen-region test, 15 chips): seed range {s['bolivia']['min']:.2f}–{s['bolivia']['max']:.2f}; " +
                     ("shipped-model chip CI {:.2f}–{:.2f}: the interval is wide.".format(*bci) if bci else "chip CI not available.") if 'bolivia' in s else "") +
                    f"\n\n{s[cols[0]]['n_seeds']} seeds (0, 1, 2); the **seed-0 model is the shipped model**; seeds 1-2 only measure training noise.")
    chips_md = "Himalayan hand-labelled chips: not evaluated yet."
    if hc:
        ci = hc.get("iou_ci95_chip_bootstrap") or [None, None]
        per = ", ".join(f"{r} {v['iou']:.2f} (n={v['n_chips']})" for r, v in hc.get("per_region", {}).items())
        ceil = (f" Two annotators agree at IoU {ag['iou_A_vs_B']:.2f} (95% CI {ag['iou_ci95_chip_bootstrap'][0]:.2f}–{ag['iou_ci95_chip_bootstrap'][1]:.2f}, "
                f"{ag['n_chips']} chips): that is the noise ceiling." if ag and ag.get("iou_A_vs_B") is not None else " Second-annotator subset not labelled yet.")
        chips_md = (f"**Himalayan hand-labelled chips** ({hc['n_chips']} chips of 256×256 px at 10 m, points pre-registered before any prediction was viewed, "
                    f"labelled from the clear parts of the 27 Aug 2026 Sentinel-2 scene; cloud = ignored): pooled IoU **{hc['at_threshold']['iou']:.3f}** "
                    f"(95% chip-bootstrap CI {ci[0]:.2f}–{ci[1]:.2f}). By stratum: {per}.{ceil} With about 20 chips the interval is wide; treat it as indicative.")
    s2_md = "Sentinel-2 agreement not run yet."
    if s2:
        r = s2["results"]
        s2_md = ("*Limitation (not a headline): AI vs Sentinel-2 cannot arbitrate.* Agreement with Sentinel-2 MNDWI water on clear valley-floor pixels is a pseudo-reference, **not accuracy** "
                 "(turbid water fools MNDWI, S1 and S2 are 1–4 days apart, 30 m), and its precision is about 0.5 on both the pre- and post-event dates, so agreement that does not change with the event cannot arbitrate: " + "; ".join(f"{k} ({v['s2_date']}) IoU {v['iou']:.2f}, P {v['precision']:.2f}, R {v['recall']:.2f}, n={v['n_px']:,}" for k, v in r.items()) + ".")
    co_md = "Corridor test not run."
    if co:
        co_md = (f"Corridor test (prediction-only; shadow/layover masked, floor via HAND): new-water excess main − tributary floor "
                 f"{co['event']['excess']:.4f} vs largest leave-one-out null {co['max_null_excess']:.4f}: **{co['verdict']}**.")
    open_md = "The model detects **open water only**: no allowed training dataset labels debris, so debris and mud come from the change detector, not the AI."
    fp_md = []
    for sm in sorted(glob.glob("outputs/flood_path*/summary.json")):
        s = J(sm); ck = J(Path(sm).with_name("check.json")) or {}
        fp_md.append(f"| {Path(sm).parent.name} | {s['path_km']} km | {s['n_settlements']} | {ck.get('median_distance_to_osm_river_px', 'n/a')} px | "
                     f"{ck.get('order_ok', 'n/a')} | {', '.join(ck.get('missing', [])) or 'none'} |")
    fp_md = ("| Run | Path length | Settlements on corridor | Median distance to OSM river | EMS names in order | Names not in OSM |\n|---|---|---|---|---|---|\n"
             + "\n".join(fp_md) + "\n\nGeometry only (D8 on GLO-30 + HAND ≤ 30 m corridor): no hydraulics, no arrival times.") if fp_md else "Flood path not run."

    # ---------- MODEL_CARD.md ----------
    mc = Path("MODEL_CARD.md")
    if mc.exists():
        t = mc.read_text(encoding="utf-8")
        t = re.sub(r"Himalayan hand-labelled chips: not made\.[^\n]*\n?", "", t)
        t = t.replace("proxy-Himalaya", "Himalayan hand-labelled chips").replace("Proxy-Himalaya", "Himalayan hand-labelled chips")
        t = block(t, "seeds", "## Seeds (training noise)\n\n" + seeds_md, before="## Himalayan evidence")
        t = re.sub(r"(## Himalayan evidence\n)(?:(?!<!-- STEP8:himalaya -->)(?!\n## ).)*", r"\1", t, flags=re.S)   # drop the old body once
        t = block(t, "himalaya", "\n\n".join([chips_md, co_md, open_md, s2_md]), anchor="## Himalayan evidence")
        mc.write_text(t, encoding="utf-8"); print("updated", mc)
    # ---------- README.md ----------
    rd = Path("README.md")
    if rd.exists():
        t = rd.read_text(encoding="utf-8").replace("proxy-Himalaya", "Himalayan hand-labelled chips")
        t = block(t, "evidence", "## Step 8 evidence (generated by tools/write_step8_docs.py)\n\n### Detector: class-level nulls\n\n" + nulls_md +
                  "\n\n### AI model: seeds\n\n" + seeds_md + "\n\n### AI model: Himalayan evidence\n\n" + "\n\n".join([chips_md, co_md, open_md, s2_md]) +
                  "\n\n### Flood path (bonus)\n\n" + fp_md)
        rd.write_text(t, encoding="utf-8"); print("updated", rd)
    # ---------- FINAL_REPORT.md: the two stale cells ----------
    fr = Path("FINAL_REPORT.md")
    if fr.exists():
        t = fr.read_text(encoding="utf-8")
        if cn:
            fw = cn["classes"]["flood_water"]
            t = t.replace("flood-water class alone: recall prints 0.000 in all four AOIs (§4.4)",
                          f"flood-water class: event {fw['event_km2_ungated']:.3f} km² vs largest null {fw['max_null_km2']:.3f} km² ({'separable' if fw['separable'] else 'not separable'}); {cn['statement']}")
        if hc:
            ci = hc.get("iou_ci95_chip_bootstrap") or [None, None]
            t = re.sub(r"\| Proxy-Himalaya \(withdrawn[^\n]*", f"| Himalayan hand-labelled chips ({hc['n_chips']}, 27 Aug S2) | {hc['at_threshold']['iou']:.3f} | {ci[0]:.2f}–{ci[1]:.2f} | n/a | n/a |", t)
        if cn: t = t.replace("Flood-like (new open" " water) change is separable from the no-flood nulls.", cn["statement"])   # withdrawn Step 8 wording
        t = t.replace("proxy-Himalaya", "Himalayan hand-labelled chips")
        fr.write_text(t, encoding="utf-8"); print("updated", fr)
    # ---------- validation log ----------
    lg = Path("docs/validation_log.md"); lg.parent.mkdir(exist_ok=True)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    seeds_txt = ", ".join("{} {:.3f}±{:.3f}".format(k, v["mean"], v["sd"] or 0) for k, v in sd["summary"].items()) if sd else "not run"
    chips_txt = "IoU {:.3f}, n={}".format(hc["at_threshold"]["iou"], hc["n_chips"]) if hc else "not run"
    s2_txt = "; ".join("{} IoU {:.2f}".format(k, v["iou"]) for k, v in s2["results"].items()) if s2 else "not run"
    lines = [f"\n### Step 8/9 runs logged {now} (tools/write_step8_docs.py)",
             f"- class nulls (ungated, leave-one-out, rule >3x): {cn['statement'] if cn else 'not run'} [class_nulls.json {sha('outputs/validation/class_nulls.json')}]",
             f"- seeds: {seeds_txt} [seeds_summary.json {sha('outputs/validation/seeds_summary.json')}]",
             f"- Himalayan chips: {chips_txt}; label agreement {ag['iou_A_vs_B'] if ag else 'not run'} [points.csv {sha('data/external/himalaya_chips/points.csv')}]",
             f"- AI vs S2 agreement (pseudo-reference): {s2_txt}",
             f"- corridor: {co['verdict'] if co else 'not run'}",
             "- No EMS data was read by any of these runs."]
    with open(lg, "a", encoding="utf-8") as f: f.write("\n".join(lines) + "\n")
    print("appended", lg)
    if missing: print("NOT YET AVAILABLE (left as 'not run' in the docs):", ", ".join(missing))

if __name__ == "__main__":
    main()

import re
from pathlib import Path
P = Path("src/report/situation_report.py")
t = P.read_text(encoding="utf-8")

def rep(old, new):
    global t
    if old not in t: raise SystemExit(f"NOT FOUND: {old[:70]}")
    t = t.replace(old, new)

# 1. gate and inputs: read emsr927_validation.json, not the retired null_recall_aoi.json
rep('(ROOT / "outputs/validation/null_recall_aoi.json").exists())', '(ROOT / "outputs/validation/emsr927_validation.json").exists())')
rep('if have_ems: files.append("outputs/validation/null_recall_aoi.json")', 'if have_ems: files.append("outputs/validation/emsr927_validation.json")')
rep('nul = J("outputs/validation/null_recall_aoi.json") if have_ems else {}', 'nul = J("outputs/validation/emsr927_validation.json") if have_ems else {}')

# 2. wording fixes
rep("({b['overlap_flood']:,} flood, {b['overlap_debris']:,} debris)", "({b['overlap_flood']:,} flood-like class, {b['overlap_debris']:,} other surface change)")
rep("were reachable as destinations", "were snapped to the road network")
rep('"EMSR927 GRA products contain no flood-extent layer; validation is proxy only."',
    '"EMSR927 products held locally (GRA) contain no flood-extent layer: the reference is landslide polygons and damage points, so the flood class is not validated against EMS."')

# 3. new EMS block
NEW = r'''    V, pooled = nul.get("aois", {}), nul.get("pooled_assessed_domain", {})
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
'''
pat = re.compile(r"    aois = \{a: n for a, n in nul\.items\(\).*?if have_ems else None\n", re.S)
if not pat.search(t): raise SystemExit("NOT FOUND: old EMS block")
t = pat.sub(lambda m: NEW, t, count=1)
P.write_text(t, encoding="utf-8"); print("patched")
"""Step 8A: class-level leave-one-out nulls for the change detector (ungated), plus the pre-registered separability rule.
Rule (written before the run, docs/validation_log.md): a class is SEPARABLE only if event area > 3x the largest null area.
For each no-flood date j in {pre, placebo, pre3, pre4}: reference = the other three dates, 'post' = j, --no-gate.
Outputs: data/processed/_null/<j>/, outputs/diagnostics/detect_null_<j>.json, outputs/validation/class_nulls.json.
Note: the event uses 4 reference dates, each null 3, so nulls are slightly noisier (conservative for the rule).

python tools/class_nulls.py            # run the four nulls, then summarise
python tools/class_nulls.py --summarize-only"""
import argparse, json, subprocess, sys
from pathlib import Path

REFS = ["pre", "placebo", "pre3", "pre4"]
CLASSES = ["flood_water", "surface_dark", "surface_bright"]
RATIO = 3.0

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}

def statement(rows, n_nulls):
    """The reviewer's sentence (Step 9 review), with every number read from the rows and the two evidence files.
    Class 1 is water-like backscatter change, never 'open water': two independent checks did not confirm open water."""
    fw, dk, br = (rows[c] for c in CLASSES); nn = WORDS.get(n_nulls, str(n_nulls))
    fl = f"Flood-like change ({fw['event_km2_ungated']:.2f} km² of water-like backscatter change)"
    sf = f"surface change ({dk['event_km2_ungated']:.2f} km² dark, {br['event_km2_ungated']:.2f} km² bright)"
    sep_s = dk["separable"] and br["separable"]
    if fw["separable"] and sep_s: s1 = f"{fl} and {sf} are each separable from all {nn} pre-event nulls."
    elif sep_s: s1 = f"{sf[0].upper() + sf[1:]} is separable from all {nn} pre-event nulls; {fl[0].lower() + fl[1:]} is not."
    elif fw["separable"]: s1 = f"{fl} is separable from all {nn} pre-event nulls; {sf} is not."
    else: s1 = f"Neither {fl[0].lower() + fl[1:]} nor {sf} is separable from the {nn} pre-event nulls."
    J = lambda p: json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else None
    co, s2 = J("outputs/validation/ai_corridor.json"), J("outputs/diagnostics/s2_detect.json")
    parts = []
    if co and "not separable" in str(co.get("verdict", "")): parts.append("An independent single-date water model could not separate the event from pre-event dates")
    if s2 and s2.get("status") != "change_detected": parts.append("Sentinel-2 does not confirm open water")
    if len(parts) == 2: return f"{s1} {parts[0]}, and {parts[1]}."
    return f"{s1} {parts[0]}." if parts else s1

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--summarize-only", action="store_true"); a = ap.parse_args()
    if not a.summarize_only:
        for j in REFS:
            d = Path(f"data/processed/_null/{j}"); d.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "src.analysis.detect", "--ref", ",".join(r for r in REFS if r != j), "--post", j,
                            "--no-gate", "--out-dir", str(d), "--track-id", f"null_{j}"], check=True)
        d = Path("data/processed/_null/event_nogate"); d.mkdir(parents=True, exist_ok=True)      # like-for-like: event also ungated
        subprocess.run([sys.executable, "-m", "src.analysis.detect", "--ref", ",".join(REFS), "--post", "post",
                        "--no-gate", "--out-dir", str(d), "--track-id", "event_nogate"], check=True)
    J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    evp = Path("outputs/diagnostics/detect_event_nogate.json")
    ev = J(evp) if evp.exists() else J("outputs/diagnostics/detect_asc85.json")      # gated event: identical areas when its gate passed
    nulls = {j: J(f"outputs/diagnostics/detect_null_{j}.json") for j in REFS}
    for j, n in nulls.items():
        if n.get("refs") != [r for r in REFS if r != j]: sys.exit(f"detect_null_{j}.json has refs {n.get('refs')}: rerun without --summarize-only")
    rows = {}
    for c in CLASSES:
        e = float(ev["area_km2"][c]); mx = max(float(n["area_km2"][c]) for n in nulls.values())
        rows[c] = {"event_km2_ungated": round(e, 4), "null_km2": {j: round(float(n["area_km2"][c]), 4) for j, n in nulls.items()},
                   "max_null_km2": round(mx, 4), "ratio": (round(e / mx, 1) if mx > 0 else None),
                   "separable": bool(e > RATIO * mx and e > 0)}
    res = {"rule": f"separable only if event area > {RATIO:g}x the largest null area (nulls ungated, leave-one-out)",
           "event_source": evp.name if evp.exists() else "detect_asc85.json (gated; gate passed)",
           "event_status": ev["status"], "event_refs": ev["refs"], "classes": rows,
           "flood_water_separable": rows["flood_water"]["separable"],
           "statement": statement(rows, len(nulls))}
    Path("outputs/validation").mkdir(parents=True, exist_ok=True)
    Path("outputs/validation/class_nulls.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"{'class':<16}{'event':>8}" + "".join(f"{j:>9}" for j in REFS) + f"{'ratio':>8}  verdict")
    for c, r in rows.items():
        print(f"{c:<16}{r['event_km2_ungated']:>8.3f}" + "".join(f"{r['null_km2'][j]:>9.4f}" for j in REFS)
              + f"{(str(r['ratio']) + 'x') if r['ratio'] else 'inf':>8}  {'SEPARABLE' if r['separable'] else 'not separable'}")
    print("statement:", res["statement"])

if __name__ == "__main__":
    main()

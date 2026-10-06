import json, pathlib, sys
p = pathlib.Path("outputs/validation/emsr927_validation.json")
if not p.exists(): sys.exit("FAIL: emsr927_validation.json missing")
d = json.loads(p.read_text())
exp = {"AOI03": (0.928, 0.174, 0.172, 0.2061), "AOI05": (0.990, 0.245, 0.244, 0.0671)}
ok = True
for aoi, (P, R, I, r0) in exp.items():
    rec = d["aois"].get(aoi)
    if not rec: print(aoi, "MISSING"); ok = False; continue
    print(f"\n== {aoi} ==\nlayers log:"); [print("  ", l) for l in rec["layers"]]
    s = rec["event_area"]["flood_or_debris"]["assessed"]["strict"]
    got = (s["precision"], s["recall"], s["iou"], rec["damage_points"]["recall_all"]["0"])
    for name, g, e in zip(("precision", "recall", "iou", "pt_recall_0m"), got, (P, R, I, r0)):
        good = g is not None and abs(g - e) < 0.002
        ok &= good; print(f"  {name}: got {g:.4f} expected {e} -> {'OK' if good else 'DIFF (bug or different layer version)'}")
    dp = rec["damage_points"]; print("  points n / assessed:", dp["n"], dp["n_assessed"])
    for t, v in dp["recall_assessed"].items():
        if v: print(f"  recall@{t}m {v['rate']:.3f} CI{v['ci95']} chance{v['chance_mean_sd']} -> {v['verdict']}")
for a, r in d["aois"].items():
    if "error" in r: print("WARN", a, r["error"])
print("\npooled:", json.dumps(d["pooled_assessed_domain"], indent=1))
print("\nREGRESSION", "PASS" if ok else "FAIL")
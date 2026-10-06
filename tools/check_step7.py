import json
j = json.load(open("outputs/validation/emsr927_validation.json"))
old = {"AOI03": (0.928, 0.174, 0.172, 0.2061), "AOI05": (0.990, 0.245, 0.244, 0.0671)}
for aoi, rec in j["aois"].items():
    print("\n==", aoi, "holdout" if rec.get("holdout") else "")
    print("error:", rec.get("error"))
    for l in rec["layers"]: print("  layer:", l)
    ea = rec.get("event_area")
    if ea:
        s = ea["flood_or_debris"]["assessed"]["strict"]
        print("  flood_or_debris assessed strict P/R/IoU:", [round(s[k], 3) if s[k] is not None else None for k in ("precision", "recall", "iou")])
    dp = rec.get("damage_points")
    if dp:
        print("  n / n_assessed:", dp["n"], dp["n_assessed"], "| recall_all 0 m:", round(dp["recall_all"]["0"], 4))
        for t, v in dp["recall_assessed"].items():
            if v: print(f"  assessed {t} m:", round(v["rate"], 3), v["ci95"], v["verdict"])
    if aoi in old:
        print("  OLD P/R/IoU/recall0:", old[aoi])
print("\nPOOLED:", json.dumps(j["pooled_assessed_domain"], indent=1))
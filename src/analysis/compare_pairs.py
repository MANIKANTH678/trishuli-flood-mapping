import json
rows = [("event 16->28 Aug", "event"), ("placebo 4->16 Aug", "placebo"),
        ("ref 23 Jul->4 Aug", "ref_pre3_placebo"), ("ref 11->23 Jul", "ref_pre4_pre3")]
print(f"{'pair':20s} pol  main_neg%  trib_neg%  excess_ci (points)")
for lab, tag in rows:
    d = json.load(open(f"outputs/diagnostics/step3_{tag}.json"))
    for p in ("VV", "VH"):
        s = d["stats"][p]; lo, md, hi = d["bootstrap"][p]["neg"]["excess_ci"]
        print(f"{lab:20s} {p}  {s['main_floor']['frac_neg']*100:9.3f} "
              f"{s['trib_floor']['frac_neg']*100:10.3f}   {lo*100:.2f} to {hi*100:.2f}")
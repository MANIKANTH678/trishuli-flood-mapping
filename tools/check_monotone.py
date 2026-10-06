import json, pandas as pd
d = json.load(open("outputs/cutoff_settlements.json"))
df = pd.DataFrame(d["sensitivity"]["scenarios"]).fillna(0)
print(df.sort_values(["bridges", "thr", "morph"]).to_string(index=False))
bad = 0
def chk(label, a, b):
    global bad
    if a > b: bad += 1; print("VIOLATION:", label, a, ">", b)
for c in [c for c in df.columns if c.endswith("_cut_off")]:
    for br in ("fail", "survive"):
        for m in (-1, 0, 1):
            v = {t: df[(df.thr == t) & (df.morph == m) & (df.bridges == br)][c].iloc[0] for t in ("high", "base", "low")}
            chk(f"{c} thr {br} m{m} high<=base", v["high"], v["base"]); chk(f"{c} thr {br} m{m} base<=low", v["base"], v["low"])
        for t in ("high", "base", "low"):
            v = {m: df[(df.thr == t) & (df.morph == m) & (df.bridges == br)][c].iloc[0] for m in (-1, 0, 1)}
            chk(f"{c} {t} {br} morph -1<=0", v[-1], v[0]); chk(f"{c} {t} {br} morph 0<=1", v[0], v[1])
    for t in ("high", "base", "low"):
        for m in (-1, 0, 1):
            s = df[(df.thr == t) & (df.morph == m)].set_index("bridges")[c]
            chk(f"{c} {t} m{m} survive<=fail", s["survive"], s["fail"])
print("monotonicity OK" if not bad else f"{bad} violations")
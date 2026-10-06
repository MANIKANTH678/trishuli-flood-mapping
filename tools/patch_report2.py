from pathlib import Path
P = Path("src/report/situation_report.py")
t = P.read_text(encoding="utf-8")

def rep(old, new):
    global t
    if old not in t: raise SystemExit(f"NOT FOUND: {old[:80]}")
    t = t.replace(old, new, 1)

# 1. date lookup for split names (fill in placebo/pre3/pre4 once you know them)
rep('TRACK = "asc85"\n', '''REF_DATES = {"pre": config.PRE_DATE, "post": config.POST_DATE}   # add "placebo": "...", "pre3": "...", "pre4": "..."
def rd(n): return f"{n} ({REF_DATES[n]})" if n in REF_DATES else n
TRACK = "asc85"\n''')
rep("{', '.join(det['refs'])} against {det['post']}", "{', '.join(rd(x) for x in det['refs'])} against {rd(det['post'])}")

# 2. load Step 3 and S2 JSONs
rep('    sig, un = J("outputs/validation/signal_check.json"), J("outputs/validation/unet_corridor.json")\n',
    '''    sig, un = J("outputs/validation/signal_check.json"), J("outputs/validation/unet_corridor.json")
    s3e, s3p = J("outputs/diagnostics/step3_event.json"), J("outputs/diagnostics/step3_placebo.json")
    s2 = J("outputs/diagnostics/s2_detect.json")
''')

# 3. S2 sentence from s2_detect.json
rep('"Sentinel-2 added nothing: coverage is about 12% and its null calibration failed, so S2 is excluded and the fused product equals the S1 product.",',
    'f"Sentinel-2 added nothing: {s2[\'floor_clear_post_fraction\']:.0%} of the valley floor has clear post-event S2 coverage and its status is {s2[\'status\']} (seed fraction {s2[\'seed_fraction\']:.4f} vs gate {s2[\'gate_threshold\']:.3f}), so S2 is excluded and the fused product equals the S1 product.",')

# 4. Detection signal section from Step 3 (main vs tributary floor, bootstrap CI, placebo)
import re
pat = re.compile(r'    sec\.append\(\("Detection signal".*?independent evidence\."""\)\)\n', re.S)
if not pat.search(t): raise SystemExit("NOT FOUND: detection signal block")
NEW = r'''    def p2(v): return f"{100 * v:.2f}%"
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
'''
t = pat.sub(lambda m: NEW, t, count=1)
P.write_text(t, encoding="utf-8"); print("patched")
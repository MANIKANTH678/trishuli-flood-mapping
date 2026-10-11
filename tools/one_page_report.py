#!/usr/bin/env python3
"""One-page situation report built only from pipeline JSON outputs, with a hard 1-page PDF gate.
Usage: python -m tools.one_page_report [--map outputs/reports/situation_map.png] [--chrome PATH]
"""
import argparse, json, sys
from collections import Counter
from pathlib import Path
from tools.pdf_gate import to_pdf

ATTR = ("Contains modified Copernicus Sentinel data 2026. Produced using Copernicus WorldDEM-30 &copy; DLR e.V. 2010-2014 and &copy; Airbus Defence and "
        "Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. &copy; OpenStreetMap contributors.")

def J(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def rng(r, f="{:,}"):
    if r is None: return "n/a"
    if isinstance(r, (int, float)): return f.format(r)
    lo, hi = r[0], r[1]
    return f.format(lo) if lo == hi else f"{f.format(lo)}&ndash;{f.format(hi)}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default="outputs/reports/situation_map.png")
    ap.add_argument("--out", default="outputs/reports/situation_report_1p.md")
    ap.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    ap.add_argument("--event", default="Trishuli / Bhote Koshi flood, Aug 2026")
    a = ap.parse_args()
    det = J("outputs/diagnostics/detect_asc85.json"); imp = J("outputs/impact_summary.json"); cut = J("outputs/cutoff_settlements.json")
    ir, cr, bs = imp["sensitivity"]["range"], cut["sensitivity"]["range"], imp["buildings"]
    unk = (bs.get("not_assessed", 0) + bs.get("unobservable", 0)) / max(bs.get("total", 1), 1)
    st = Counter(s["hospital"]["status"] for s in cut.get("settlements", []))
    rows = [
        ("Flagged change area", f"{det.get('area_km2', 'n/a')} km&sup2;", "single track, valley floor (HAND &le; 30 m)"),
        ("Buildings overlapping the mask", rng(ir.get("buildings_overlap")), f"status unknown for {unk:.0%} of buildings"),
        ("Motorable road in mask", rng(ir.get("motorable_road_km"), "{:.1f}") + " km", "exposure, not confirmed damage"),
        ("Bridges exposed", rng(ir.get("bridges_exposed")), "exposed, not failed"),
        ("Settlements cut off from a hospital", rng(cr.get("hospital_cut_off")), "range: thresholds, mask &plusmn;1 px, bridge policy"),
        ("Settlements with a degraded route", rng(cr.get("hospital_degraded", st.get("degraded", 0))), "longer route still exists"),
        ("No pre-flood road route", str(st.get("no_pre_flood_path", 0)), "excluded from cut-off count"),
    ]
    md = [f"# Situation report: {a.event}",
          f"*Educational prototype, not an operational tool. Exposure to a detected change mask, not a validated flood extent.*",
          "## Situation",
          f"Sentinel-1 change detection over the valley floor. Detector status: **{det.get('status', 'n/a')}**. "
          f"Numbers below are exposure to the detected mask, each with its sensitivity range.",
          "## Key numbers", "| Indicator | Value | Note |", "|---|---|---|"]
    md += [f"| {r[0]} | {r[1]} | {r[2]} |" for r in rows]
    if Path(a.map).exists(): md += ["", f"![map]({Path(a.map).resolve().as_uri()})"]
    md += ["## Limitations",
           "- Single Sentinel-1 track (orbit 85 ascending); other geometries not used.",
           f"- Valley floor only (HAND &le; 30 m); {unk:.0%} of buildings have unknown status (not assessed or radar-unobservable).",
           "- No cause attribution: change may be water, debris or other surface change. The AI model detects open water only.",
           "- Sentinel-2 excluded from the fused map (calibration failed / cloud cover).",
           "", f"<small>{ATTR}</small>"]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text("\n".join(md), encoding="utf-8")
    pdf = to_pdf(a.out, chrome=a.chrome); print("wrote", pdf, "(1 page)")

if __name__ == "__main__":
    main()

"""P4: build a single-file HTML dashboard."""
import json, base64
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"

def b64(p):
    return base64.b64encode(Path(p).read_bytes()).decode()

stats  = json.load(open(OUT / "impact_stats.json"))
meta   = json.load(open(OUT / "model_meta.json"))
fi     = json.load(open(OUT / "feature_importance.json"))
cutoff = json.load(open(OUT / "cutoff_settlements.json"))
cutoff_only = [x for x in cutoff if x["cut_off"]]

imgs = {
    "flood_mask": b64(OUT / "flood_mask.png"),
    "susceptibility": b64(OUT / "susceptibility_preview.png"),
    "buildings": b64(OUT / "affected_buildings_map.png"),
    "roads": b64(OUT / "affected_roads_map.png"),
}

fi_rows = "\n".join(
    f"<tr><td>{k}</td><td>{v:.4f}</td></tr>"
    for k, v in sorted(fi.items(), key=lambda x: -x[1])
) if isinstance(fi, dict) else ""

co_rows = "\n".join(
    f"<tr><td>{x['name']}</td><td>{x['lat']:.4f}</td><td>{x['lon']:.4f}</td></tr>"
    for x in cutoff_only[:200]
)

html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Trishuli Flood Impact Dashboard</title>
<style>
body{{font:14px/1.5 system-ui;margin:2rem;max-width:1100px}}
img{{max-width:100%;border:1px solid #ddd;border-radius:6px;margin:.5rem 0}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #ddd;padding:.4rem .6rem;text-align:left}}
th{{background:#f5f5f5}}
.kpi{{display:inline-block;background:#eef;border-radius:8px;padding:.8rem 1.2rem;margin:.3rem}}
.kpi b{{display:block;font-size:1.4rem}}
</style></head><body>
<h1>Trishuli Flood Impact Dashboard</h1>

<h2>Impact summary</h2>
<div>
  <span class="kpi"><b>{stats['flooded_buildings']:,}</b>flooded buildings</span>
  <span class="kpi"><b>{stats['flooded_roads']:,}</b>flooded roads</span>
  <span class="kpi"><b>{stats['cutoff_settlements']}</b>cut-off settlements</span>
  <span class="kpi"><b>{stats['pct_buildings_flooded']}%</b>buildings hit</span>
  <span class="kpi"><b>{stats['pct_roads_flooded']}%</b>roads hit</span>
</div>

<h2>Flood mask</h2><img src="data:image/png;base64,{imgs['flood_mask']}">
<h2>Susceptibility (model output)</h2><img src="data:image/png;base64,{imgs['susceptibility']}">
<h2>Affected buildings</h2><img src="data:image/png;base64,{imgs['buildings']}">
<h2>Affected roads</h2><img src="data:image/png;base64,{imgs['roads']}">

<h2>Feature importance (XGBoost)</h2>
<table><tr><th>feature</th><th>gain</th></tr>{fi_rows}</table>

<h2>Cut-off settlements ({len(cutoff_only)})</h2>
<table><tr><th>name</th><th>lat</th><th>lon</th></tr>{co_rows}</table>

<h2>Model metadata</h2>
<pre>{json.dumps(meta, indent=2)}</pre>
</body></html>"""

(OUT / "dashboard.html").write_text(html, encoding="utf-8")
print("✅ outputs/dashboard.html written")

"""Build the dashboard from the committed outputs and check its contents."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report import dashboard_full as dash  # noqa: E402

SMALL_FILES = ["impact_stats.json", "model_meta.json", "feature_importance.json",
               "cutoff_settlements.json", "impact_by_district.csv"]


def _fixture_dir(tmp_path: Path) -> Path:
    for name in SMALL_FILES:
        shutil.copy(ROOT / "outputs" / name, tmp_path / name)
    return tmp_path


def test_build_without_images_still_produces_page(tmp_path):
    out = dash.build(_fixture_dir(tmp_path))
    html = out.read_text(encoding="utf-8")
    stats = json.loads((tmp_path / "impact_stats.json").read_text())

    assert html.startswith("<!doctype html>")
    assert f"{stats['flooded_buildings']:,}" in html
    assert f"{stats['cutoff_settlements']}" in html
    assert "not found" in html                 # missing figures are reported, not fatal
    assert "<script id=\"dash-data\"" in html
    assert "</script>" not in html.split('id="dash-data"')[1].split("</script>")[0]


def test_embedded_settlement_data_matches_source(tmp_path):
    out = dash.build(_fixture_dir(tmp_path))
    html = out.read_text(encoding="utf-8")
    blob = html.split('<script id="dash-data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(blob.replace("<\\/", "</"))
    source = json.loads((tmp_path / "cutoff_settlements.json").read_text())

    assert len(data["settlements"]) == len(source)
    assert sum(s["cut"] for s in data["settlements"]) == sum(x["cut_off"] for x in source)
    assert len(data["bbox"]) == 4


def test_settlement_record_parses_osm_style_names():
    rec = dash.settlement_record({"name": "hamlet_267564995", "lat": 28.18, "lon": 85.19, "cut_off": True})
    assert rec["type"] == "hamlet" and rec["id"] == "267564995" and rec["cut"]
    assert "267564995" in rec["label"]

    rec = dash.settlement_record({"name": "Betrawati", "lat": 27.9, "lon": 85.1})
    assert rec["label"] == "Betrawati" and rec["id"] == "" and not rec["cut"]


def test_feature_chart_is_sorted_svg():
    svg = dash.feature_chart_svg({"slope": 0.3, "vv_diff": 0.5, "aspect": 0.01})
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert svg.index("VV change") < svg.index("Slope") < svg.index("Aspect")


def test_values_are_html_escaped(tmp_path):
    d = _fixture_dir(tmp_path)
    settlements = json.loads((d / "cutoff_settlements.json").read_text())
    settlements.append({"name": "<img src=x onerror=alert(1)>", "lat": 28.0, "lon": 85.0, "cut_off": True})
    (d / "cutoff_settlements.json").write_text(json.dumps(settlements))
    html = dash.build(d).read_text(encoding="utf-8")
    assert "<img src=x onerror" not in html

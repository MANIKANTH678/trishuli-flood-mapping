"""Build the dashboard from the committed outputs and check its contents."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.report import dashboard_full as dash  # noqa: E402

SMALL_FILES = ["impact_summary.json", "cutoff_settlements.json"]


def _fixture_dir(tmp_path: Path) -> Path:
    for name in SMALL_FILES:
        shutil.copy(ROOT / "outputs" / name, tmp_path / name)
    return tmp_path

def _load_settlements(path):
    src = json.loads(path.read_text())
    return src["settlements"] if isinstance(src, dict) else src


def test_build_without_images_still_produces_page(tmp_path):
    out = dash.build(_fixture_dir(tmp_path))
    html = out.read_text(encoding="utf-8")
    impact = json.loads((tmp_path / "impact_summary.json").read_text())
    summary = json.loads((tmp_path / "cutoff_settlements.json").read_text())["summary"]

    assert html.startswith("<!doctype html>")
    assert f"{impact['flooded_buildings']:,}" in html
    assert f"{summary['total_settlements']:,}" in html
    assert "not found" in html                 # missing figures are reported, not fatal
    assert "<script id=\"dash-data\"" in html
    assert "</script>" not in html.split('id="dash-data"')[1].split("</script>")[0]

def test_embedded_settlement_data_matches_source(tmp_path):
    out = dash.build(_fixture_dir(tmp_path))
    html = out.read_text(encoding="utf-8")
    blob = html.split('<script id="dash-data" type="application/json">')[1].split("</script>")[0]
    data = json.loads(blob.replace("<\\/", "</"))
    source = _load_settlements(tmp_path / "cutoff_settlements.json")

    assert len(data["settlements"]) == len(source)
    assert sum(s["cut"] for s in data["settlements"]) == sum(1 for x in source if x["hospital"]["status"] == "cut_off")
    assert len(data["bbox"]) == 4


def test_settlement_record_parses_osm_style_names():
    rec = dash.settlement_record({"name": "hamlet_267564995", "lat": 28.18, "lon": 85.19, "cut_off": True})
    assert rec["type"] == "hamlet" and rec["id"] == "267564995" and rec["cut"]
    assert "267564995" in rec["label"]

    rec = dash.settlement_record({"name": "Betrawati", "lat": 27.9, "lon": 85.1})
    assert rec["label"] == "Betrawati" and rec["id"] == "" and not rec["cut"]



def test_values_are_html_escaped(tmp_path):
    d = _fixture_dir(tmp_path)
    src = json.loads((d / "cutoff_settlements.json").read_text())
    src["settlements"].append({"name": "<img src=x onerror=alert(1)>", "lat": 28.0, "lon": 85.0, "cut_off": True})
    (d / "cutoff_settlements.json").write_text(json.dumps(src))
    html = dash.build(d).read_text(encoding="utf-8")
    assert "<img src=x onerror" not in html

"""The folium dashboard (src/report/dashboard.py) is the deliverable: text from JSON, offline assets, attribution, toggles."""
import json, re, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.report import dashboard as D  # noqa: E402
from src.report import attribution as A  # noqa: E402

IMP = {"buildings": {"total": 1000, "overlap": 0, "overlap_flood": 0, "overlap_debris": 0, "not_assessed": 900, "unobservable": 50,
                     "assessed": 50, "within_30m": 0, "within_60m": 0},
       "roads_bridges": {"exposure_by_tolerance": {"0m": {"roads": 0, "road_km": 0.0, "motorable_road_km": 0.0, "bridges": 0}}},
       "total_bridges": 3, "sensitivity": {"scenarios": {}, "range": {}}}
DET = {"status": "no_significant_change", "track": "asc85", "calibrated": True, "area_km2": {"flood_water": 0.0, "surface_dark": 0.0, "surface_bright": 0.0}}

def test_headline_survives_empty_masks_and_missing_ranges():
    lines = D.headline(DET, IMP, {"summary": {"cut_off": 0, "total_settlements": 5}, "sensitivity": {"range": {}}, "settlements": []}, None, None, None)
    t = " ".join(lines)
    assert "no_significant_change" in t and "<b>0</b>" in t and "95%" in t and "range" not in t.split("Buildings")[1].split("&middot;")[0]

def test_headline_uses_overlap_and_range_not_the_flood_only_key():
    imp = json.loads(json.dumps(IMP)); imp["buildings"].update(overlap=556, overlap_flood=6, overlap_debris=550, total=189503,
                                                                   not_assessed=160971, unobservable=13161)
    imp["sensitivity"]["range"] = {"buildings_overlap": [244, 1078]}
    t = " ".join(D.headline(dict(DET, status="change_detected"), imp, None, None, None, None))
    assert "<b>556</b> (range 244&ndash;1,078)" in t and "92%" in t and "<b>6</b>" not in t

def test_uncalibrated_and_escaping():
    t = " ".join(D.headline(dict(DET, calibrated=False, status="<script>"), IMP, None, {"statement": "a<b"}, None, None))
    assert "UNCALIBRATED" in t and "<script>" not in t and "a&lt;b" in t

@pytest.mark.skipif(not (ROOT / "outputs/dashboard/index.html").exists(), reason="dashboard not built")
def test_built_page_is_offline_and_attributed():
    h = (ROOT / "outputs/dashboard/index.html").read_text(encoding="utf-8")
    assert not re.search(r'(?:src|href)="https?://[^"]+\.(?:js|css)"', h), "CDN asset not vendored"
    for rel in re.findall(r'(?:src|href)="(vendor/[^"]+)"', h): assert (ROOT / "outputs/dashboard" / rel).exists(), rel
    for s in A.REQUIRED: assert s in h
    assert A.DISCLAIMER in h and "Radar-unobservable" in h and "Scenario base threshold" in h and "Plain background (offline)" in h

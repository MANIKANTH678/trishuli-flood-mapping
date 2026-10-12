# tests/test_attribution.py  (Step 9 review; FILES extended to every deliverable)
import html, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["Contains modified Copernicus Sentinel data 2026.",
            "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.",
            "© OpenStreetMap contributors."]
FILES = ["README.md", "ATTRIBUTION.md", "docs/REPORT.md", "outputs/reports/situation_report_EN.md", "outputs/reports/situation_report_NE.md",
         "outputs/reports/situation_report_1p.md", "outputs/dashboard/index.html"]
EMS = "European Union, Copernicus Emergency Management Service data"

def norm(t): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))

def test_required_attribution_in_every_deliverable():
    for f in FILES:
        p = ROOT / f
        if p.exists():
            t = norm(p.read_text(encoding="utf-8"))
            for s in REQUIRED: assert s in t, f"{f} is missing: {s[:50]}"

def test_shared_constant_matches_the_brief():
    from src.report import attribution as A
    assert list(A.REQUIRED) == REQUIRED
    assert A.EMS == EMS
    assert all(s in norm(A.html(with_ems=True)) for s in REQUIRED + [EMS])

def test_ems_credit_wherever_ems_appears():
    for f in FILES:
        p = ROOT / f
        if p.exists():
            t = norm(p.read_text(encoding="utf-8"))
            if "EMSR927" in t: assert EMS in t, f"{f} mentions EMSR927 without the EMS credit"

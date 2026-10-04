"""Build outputs/presentation.pptx from the current pipeline outputs.

All numbers come from the same JSON / raster files the situation report uses, so the
deck cannot drift from the report. Run from anywhere:

    python src/report/slides.py
"""
import datetime
import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config  # noqa: E402


def J(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def mask_stats():
    import rasterio
    with rasterio.open(ROOT / "data/processed/flood_mask.tif") as s:
        px = int((s.read(1) > 0).sum())
        area = px * abs(s.res[0] * s.res[1]) / 1e6
    return px, area


imp = J("outputs/impact_summary.json")
cut = J("outputs/cutoff_settlements.json")["summary"]
nul = J("outputs/validation/null_recall_aoi.json")
px, area = mask_stats()
empty_aois = [k for k, v in nul.items() if v["mask_px"] == 0]

prs = Presentation()


def slide(title, lines, size=22):
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = title
    tf = s.placeholders[1].text_frame
    tf.text = lines[0]
    for line in lines[1:]:
        tf.add_paragraph().text = line
    for p in tf.paragraphs:
        p.font.size = Pt(size)


slide("Trishuli / Bhote Koshi flood: Sentinel-1 analysis",
      ["Calibrated, terrain-corrected SAR and OpenStreetMap exposure",
       "Preliminary and unvalidated",
       datetime.date.today().isoformat()])

slide("Problem",
      [f"• Suspected GLOF on {config.FLOOD_DATE}, Rasuwa District, Nepal",
       "• Can free Sentinel-1 data map flood extent and impact quickly?",
       "• EMSR927 mapped damaged structures but has no flood-extent layer"])

slide("Data",
      [f"• Sentinel-1 GRD VV/VH: {config.PRE_DATE} (pre), {config.POST_DATE} (post)",
       "• Copernicus GLO-30 DEM",
       f"• OpenStreetMap snapshot of {config.OSM_SNAPSHOT_DATE} (pre-event)",
       "• EMSR927 damage points, used only for validation"])

slide("Method",
      ["1. SNAP: orbit file, noise removal, sigma0, terrain correction",
       "2. Average to a 30 m grid (UTM 45N)",
       "3. Detect: mean VV/VH change below a threshold, flat land only",
       "4. Overlay on OSM and validate against EMSR927"])

slide("Key finding",
      ["• No detectable flood signal on this Sentinel-1 pair",
       "• River VV change in the Rasuwa reach is no darker than shifted controls",
       "• The pair cannot resolve the event; it does not show that no flood occurred"])

slide("Detector mask (unvalidated)",
      [f"• {px:,} px ({area:.2f} km²), scattered",
       "• Threshold clipped to -3.5 to -1.5 dB, slope under 12°, patches of 20+ px",
       "• Selected from noise-level change, so not a flood extent"])

slide("Exposure to the mask",
      [f"• Buildings: {imp['flooded_buildings']:,} of {imp['total_buildings']:,} "
       f"(+{imp['debris_buildings']:,} debris-affected)",
       f"• Road segments: {imp['flooded_roads']:,} of {imp['total_roads']:,}",
       f"• Bridges: {imp['flooded_bridges']:,} of {imp['total_bridges']:,}",
       f"• Settlements cut off: {cut['cut_off']} of {cut['total_settlements']}"])

slide("Validation",
      ["• Mask hit rate on EMSR927 damage points vs a random-mask null",
       f"• No mask pixels in {len(empty_aois)} of {len(nul)} AOIs: a coverage limit, "
       "not a detection error",
       "• U-Net (Sen1Floods11) cannot separate the two scenes, so it is not "
       "independent evidence"])

slide("Deliverables",
      ["• Interactive dashboard (outputs/dashboard.html)",
       "• Situation report and final report",
       "• Reproducible pipeline (run_all.sh)",
       "• Trained U-Net weights (flood_unet.pt)"])

slide("Limitations and next steps",
      ["• Post scene is two days after the event",
       "• 30 m pixels, steep terrain masked, OSM incomplete in rural Rasuwa",
       "• Next: Sentinel-2, PlanetScope or high-resolution SAR within 24-72 h",
       "• Replace the threshold detector before reuse"])

out = ROOT / "outputs/presentation.pptx"
prs.save(out)
print("wrote", out)
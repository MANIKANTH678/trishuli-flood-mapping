from pptx import Presentation

prs = Presentation()

def slide(title, content):
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = title
    s.placeholders[1].text = content

slide("Trishuli Flood Mapping — 2026",
      "Sentinel-1 SAR + Machine Learning\nP1 · P2 · P3 · P4\n2026-10-01")
slide("Problem",
      "• Trishuli / Bhote Koshi corridor flooding\n"
      "• Need rapid extent + impact mapping\n"
      "• 48-hour SAR-to-decision pipeline")
slide("Data",
      "• Sentinel-1 GRD (VV/VH) — 30 m\n"
      "• Copernicus DEM — 30 m\n"
      "• OpenStreetMap buildings & roads")
slide("Method",
      "1. Align DEM + S1 to 30 m UTM grid\n"
      "2. Detect flood: Δ VV < -1.5 dB\n"
      "3. Train XGBoost on 9 features\n"
      "4. Overlay on OSM for impact")
slide("Flood Detection (P2)",
      "• 22.66 km² observed flooded\n"
      "• Threshold -1.5 dB (clamped Otsu)\n"
      "• Slope & permanent water masked")
slide("Susceptibility Model (P3)",
      "• XGBoost, 9 features\n"
      "• AUC 0.998\n"
      "• Predicted 23.11 km² — 1.02× observed")
slide("Validation",
      "• F1 ~0.91\n"
      "• IoU ~0.84\n"
      "• 90%+ of observed flood captured")
slide("Impact (P1)",
      "• Buildings flooded: <FILL IN>\n"
      "• Road segments affected: <FILL IN>\n"
      "• Cut-off settlements: <FILL IN>")
slide("Deliverables",
      "• flood_dashboard_full.html\n"
      "• flood_model.joblib\n"
      "• FINAL_REPORT.pdf\n"
      "• Reproducible pipeline on GitHub")
slide("Limitations & Next Steps",
      "• Single-event training\n"
      "• 30 m misses sub-pixel urban flooding\n"
      "• Next: dual-orbit fusion, S2 validation")

prs.save("outputs/presentation.pptx")
print("✅ outputs/presentation.pptx")

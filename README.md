# Trishuli Flood Damage Mapping

Track B — Multimodal AI Hackathon 2026

Maps flood and debris damage from the 26 August 2026 Trishuli–Bhote Koshi
flood (Nepal) using free satellite data: Sentinel-1 radar change detection,
an XGBoost susceptibility model, and OpenStreetMap buildings, roads and
settlements.

**Headline results** (see `outputs/dashboard.html` and `FINAL_REPORT.md`):

| Metric | Value |
| --- | --- |
| Flooded buildings | 33,040 of 1,372,591 (2.4%) |
| Flooded road segments | 3,440 of 129,560 (2.7%) |
| Cut-off settlements | 172 of 1,565 (11.0%) |
| Susceptibility model | AUC 0.998, F1 0.58 at threshold 0.96 |

## Setup

```bash
python3 -m venv ~/flood-venv
source ~/flood-venv/bin/activate
pip install -r requirements.txt
```

Edit `src/config.py` for the bounding box, event dates and Copernicus
Dataspace credentials before downloading data.

## Pipeline

Each step is a module run with `python -m`. Steps 1–3 need the raw data under
`data/raw/`; steps 4–5 only need the files already committed in `outputs/`.

```bash
# 1. Download inputs
python -m src.download.dem              # 30 m DEM tiles
python -m src.download.osm_overpass     # OSM buildings, roads, places

# 2. Align and detect
python -m src.processing.align          # common 30 m grid, calibrated dB
python -m src.processing.align_post_vh  # VH patch for the post scene
python -m src.processing.flood_detect   # flood_mask.tif

# 3. Susceptibility model
python -m src.modeling.features         # terrain + SAR feature stack
python -m src.modeling.train            # XGBoost, writes model_meta.json
python -m src.modeling.predict          # susceptibility.tif

# 4. Impact statistics and static maps
python -m src.report.impact

# 5. Dashboard (standard library only — works without the geo stack)
python -m src.report.dashboard_full
```

## Dashboard

`outputs/dashboard.html` is a self-contained page: impact KPIs, the four
maps with a zoomable lightbox, the model card with feature importance, a
searchable table and interactive map of cut-off settlements, methods and
limitations, and links to every output file. Images are embedded, so it
works offline; only the settlement map tiles need a connection.

Open it directly in a browser, or serve the folder so the output-file links
resolve:

```bash
python -m http.server -d outputs 8000   # then visit http://localhost:8000/dashboard.html
```

## Tests

```bash
python -m pytest tests/
```

## Layout

```
src/
  config.py          bounding box, dates, CRS, paths
  download/          DEM and OpenStreetMap acquisition
  processing/        grid alignment and SAR flood detection
  modeling/          feature engineering, XGBoost training, prediction
  report/            impact statistics, static maps, HTML dashboard
outputs/             committed results of the latest run
```

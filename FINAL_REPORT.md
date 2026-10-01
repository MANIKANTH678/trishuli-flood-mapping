# Trishuli River Flood Impact Assessment

## Executive summary

We produced a 30 m flood mask using Sentinel-1 VV/VH change detection aligned
to a common DEM grid. An XGBoost susceptibility model was trained on terrain
+ SAR features. We intersected the flood mask with OpenStreetMap buildings,
roads, and settlements.

## Key numbers

- **Flooded buildings:** 33,040 / 1,372,591 (2.41%)
- **Flooded road segments:** 3,440 / 129,560 (2.66%)
- **Cut-off settlements:** 172 / 1,565 (11.0%)

## Data & methods

- Sentinel-1 GRD (pre/post), 30 m resampling, EPSG:32645
- DEM: 30 m
- Flood mask: threshold on VV/VH difference, calibrated dB
- Susceptibility model: XGBoost, see outputs/feature_importance.json
- Impact: point-in-polygon (buildings/roads midpoints) against flood mask
- Cut-off: graph connectivity on roads after removing flooded segments

## Figures

- outputs/flood_mask.png
- outputs/susceptibility_preview.png
- outputs/affected_buildings_map.png
- outputs/affected_roads_map.png
- Interactive dashboard: outputs/dashboard.html

## Limitations

- 30 m resolution smears small structures
- OSM completeness varies
- Cut-off detection uses midpoint sampling per segment

## Reproduce

python -m src.processing.align
python -m src.processing.flood_detect
python -m src.models.train_xgb
python -m src.processing.damage
python -m src.processing.cutoff
python -m src.report.impact
python -m src.report.dashboard_full

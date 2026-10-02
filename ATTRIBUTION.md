# Attribution

Data sources retain their own licenses; this project's MIT license covers code.

## Satellite data

### Sentinel-1 GRD
- **Products:** `S1D_IW_GRDH_1SDV`, relOrbit 85, ASCENDING
  - Pre:  `2026-08-16T12:21:16` / `12:21:41`
  - Post: `2026-08-28T12:21:16` / `12:21:41`
- **Source:** Copernicus Data Space Ecosystem — <https://dataspace.copernicus.eu/>
- **Credit:** Contains modified Copernicus Sentinel data 2026
- **License:** Copernicus Sentinel Data Terms and Conditions
  <https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice>

### DEM
- Mosaicked to 30 m EPSG:32645 from `data/raw/dem/`.
- If Copernicus DEM GLO-30: (c) DLR e.V. / Airbus DS, provided under COPERNICUS
  by the EU and ESA.
- If SRTM: NASA, public domain.

## Reference data

### Copernicus EMS Rapid Mapping — EMSR927
- **Activation:** EMSR927 — *Flood in Nepal* (GLOF, Rasuwa, 26 Aug 2026)
- **AOIs:** 01 Syapru Besi, 02 Timure, 03 Bidur, 05 Phosretar
- **Layers:** `builtUpP`, `observedEventA`, `areaOfInterestA`, `notAnalysedA`
- **Source:** <https://rapidmapping.emergency.copernicus.eu/>
- **License:** Copernicus EMS licence
  <https://emergency.copernicus.eu/mapping/download/legal>
- **Caveat:** GRA products contain landslide polygons and building-damage
  points but **no flood extent layer**. Validation is proxy-based.

## OpenStreetMap
- **Files:** buildings (1.37M), roads (130k), hospitals (1,002),
  settlements (1,565)
- **Sources:** Overpass API (<https://overpass-api.de/>) and Geofabrik
  (`nepal-latest.osm.pbf`, <https://download.geofabrik.de/asia/nepal.html>)
- **Snapshot:** OSM as of 2026-09-30 (file timestamps); **post-event** —
  flagged as a limitation for pre/post comparisons.
- **License:** (c) OpenStreetMap contributors, ODbL v1.0
  <https://www.openstreetmap.org/copyright>

## Training data

### Sen1Floods11 v1.1
- **Source:** <https://github.com/cloudtostreet/Sen1Floods11>
- **Splits:** 252 train / 89 val hand-labeled chips
- **Credit:** Bonafilia et al. (2020), *Sen1Floods11: a georeferenced dataset
  to train and test deep learning flood classifiers using Sentinel-1 data*,
  CVPR EarthVision workshop.
- **License:** CC BY 4.0

## Software
`rasterio`, `rioxarray`, `geopandas`, `pyogrio`, `shapely`, `pyproj`,
`networkx`, `scipy`, `scikit-image`, `numpy`, `pandas`, `torch`, `tqdm`,
`requests`, `pytest`. Versions pinned in `requirements.txt`. Each retains
its own license (BSD / MIT / Apache 2.0 / PSF).

## Papers referenced for threshold justification
- Twele, A., Cao, W., Plank, S., Martinis, S. (2016). *Sentinel-1-based flood
  mapping: a fully automated processing chain*, Int. J. Remote Sensing 37(13),
  2990-3004. (Basis for -1.5 dB change threshold.)
- Lee, J.-S. (1980). *Digital image enhancement and noise filtering by use of
  local statistics*, IEEE TPAMI. (Lee speckle filter.)
- Otsu, N. (1979). *A threshold selection method from gray-level histograms*,
  IEEE SMC. (Adaptive thresholding.)
- Ronneberger, O., Fischer, P., Brox, T. (2015). *U-Net: Convolutional Networks
  for Biomedical Image Segmentation*, MICCAI. (Model architecture.)

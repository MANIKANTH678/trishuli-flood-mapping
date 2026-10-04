# Attribution

Data sources retain their own licenses; this project's MIT license covers code.

## Satellite data

### Sentinel-1 GRD

- **Products:** `S1D_IW_GRDH_1SDV`, relOrbit 85, ASCENDING
  - Pre: `2026-08-16T12:21:16` / `12:21:41`
  - Post: `2026-08-28T12:21:16` / `12:21:41`
- **Source:** Copernicus Data Space Ecosystem — <https://dataspace.copernicus.eu/>
- **Credit:** Contains modified Copernicus Sentinel data 2026
- **License:** Copernicus Sentinel Data Terms and Conditions
  <https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice>

### DEM

- Copernicus DEM GLO-30, mosaicked to 30 m EPSG:32645 from `data/raw/dem/`.
- Credit: (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018,
  provided under COPERNICUS by the European Union and ESA; all rights reserved.

## Reference data

### Copernicus EMS Rapid Mapping — EMSR927

- **Activation:** EMSR927 — _Flood in Nepal_ (GLOF, Rasuwa, 26 Aug 2026)
- **AOIs:** 01 Syapru Besi, 02 Timure, 03 Bidur, 05 Phosretar
- **Layers:** `builtUpP`, `observedEventA`, `areaOfInterestA`, `notAnalysedA`
- **Source:** <https://rapidmapping.emergency.copernicus.eu/>
- **License:** Copernicus EMS licence
  <https://emergency.copernicus.eu/mapping/download/legal>
- **Caveat:** GRA products contain landslide polygons and building-damage
  points but **no flood extent layer**. Validation is proxy-based.

## OpenStreetMap

- **Files (area of interest):** buildings (189,503), roads (14,151),
  hospitals (20), settlements (446)
- **Sources:** Overpass API (<https://overpass-api.de/>) and Geofabrik
  (`nepal-latest.osm.pbf`, <https://download.geofabrik.de/asia/nepal.html>)
- **Snapshot:** OSM as of ohsome API snapshot 2026-07-27 (pre-event). Edits made
  between the snapshot and the 2026-08-26 event are not reflected.
- **License:** (c) OpenStreetMap contributors, ODbL v1.0
  <https://www.openstreetmap.org/copyright>

## Training data

### Sen1Floods11 v1.1

- **Source:** <https://github.com/cloudtostreet/Sen1Floods11>
- **Splits:** 252 train / 89 val hand-labeled chips
- **Credit:** Bonafilia et al. (2020), _Sen1Floods11: a georeferenced dataset
  to train and test deep learning flood classifiers using Sentinel-1 data_,
  CVPR EarthVision workshop.
- **License:** CC BY 4.0

## Software

`rasterio`, `rioxarray`, `geopandas`, `pyogrio`, `shapely`, `pyproj`,
`networkx`, `scipy`, `scikit-image`, `numpy`, `pandas`, `torch`, `tqdm`,
`requests`, `pytest`. Versions pinned in `requirements.txt`. Each retains
its own license (BSD / MIT / Apache 2.0 / PSF).

## Papers referenced for threshold justification

- Twele, A., Cao, W., Plank, S., Martinis, S. (2016). _Sentinel-1-based flood
  mapping: a fully automated processing chain_, Int. J. Remote Sensing 37(13),
  2990-3004. (Basis for -1.5 dB change threshold.)
- Lee, J.-S. (1980). _Digital image enhancement and noise filtering by use of
  local statistics_, IEEE TPAMI. (Lee speckle filter.)
- Otsu, N. (1979). _A threshold selection method from gray-level histograms_,
  IEEE SMC. (Adaptive thresholding.)
- Ronneberger, O., Fischer, P., Brox, T. (2015). _U-Net: Convolutional Networks
  for Biomedical Image Segmentation_, MICCAI. (Model architecture.)

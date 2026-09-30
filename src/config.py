"""Central configuration for the Trishuli flood mapping project."""

# Bounding box: (west, south, east, north) — Trishuli / Bhote Koshi corridor
BBOX = (84.50, 27.40, 86.00, 28.40)

# Event window
FLOOD_DATE = "2026-08-26"
PRE_DATE   = "2026-08-16"   # 12 days before (adjust to matching orbit track)
POST_DATE  = "2026-08-28"
S1_RELATIVE_ORBIT=None
S1_ORBIT_DIRECTION="ASCENDING"   # 12 days after  (adjust to matching orbit track)

# OSM snapshot (must be BEFORE the flood)
OSM_SNAPSHOT_DATE = "2026-07-27"

# Common CRS — UTM zone 45N covers all of Nepal
CRS = "EPSG:32645"

# Data directories
DEM_DIR       = "data/raw/dem"
S1_DIR        = "data/raw/s1"
S2_PRE_DIR    = "data/raw/s2/pre"
S2_POST_DIR   = "data/raw/s2/post"
OSM_DIR       = "data/raw/osm"
PROCESSED_DIR = "data/processed"
OUTPUT_DIR    = "outputs"

# Copernicus Dataspace credentials (fill in after registering)
COPERNICUS_USER = "your_email@example.com"
COPERNICUS_PASS = "your_password"

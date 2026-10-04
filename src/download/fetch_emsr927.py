"""Download EMSR927 GRA products into data/external/EMSR927/AOIxx/ (public, no login)."""
import io, re, sys, zipfile
from pathlib import Path
import requests

CODE = "EMSR927"
API = f"https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code={CODE}"
OUT = Path("data/external") / CODE

def find_paths(obj, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "downloadPath" and isinstance(v, str):
                found.append(v)
            else:
                find_paths(v, found)
    elif isinstance(obj, list):
        for v in obj:
            find_paths(v, found)

r = requests.get(API, timeout=60)
r.raise_for_status()
paths = []
find_paths(r.json(), paths)
gra = [p for p in paths if "GRA_PRODUCT" in p and p.endswith(".zip")]
print(f"{len(paths)} download paths, {len(gra)} GRA zips")
if not gra:
    sys.exit("No GRA zips found. Print the API JSON and check the structure.")

# keep the latest version per AOI
latest = {}
for p in gra:
    m = re.search(r"/(AOI\d+)/.*_v(\d+)\.zip$", p)
    if not m:
        continue
    aoi, ver = m.group(1), int(m.group(2))
    if aoi not in latest or ver > latest[aoi][0]:
        latest[aoi] = (ver, p)

for aoi, (ver, url) in sorted(latest.items()):
    print(f"{aoi} v{ver}: {url}")
    z = requests.get(url, timeout=300)
    z.raise_for_status()
    dest = OUT / aoi
    dest.mkdir(parents=True, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(z.content)).extractall(dest)
    print("   gpkg:", [f.name for f in dest.rglob("*.gpkg")] or "NONE FOUND")
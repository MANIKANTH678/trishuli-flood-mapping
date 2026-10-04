import argparse, json, sys
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument("--bbox", required=True)
w, s, e, n = map(float, ap.parse_args().bbox.split(","))
lon, lat = (w + e) / 2, (s + n) / 2
best, heading, pas = (np.inf, None), None, None
for safe in sorted(Path("data/raw/sentinel1/pre").glob("*.SAFE")):
    for ann in sorted(safe.glob("annotation/s1*-vv-*.xml")):
        root = ET.parse(ann).getroot()
        heading, pas = float(root.findtext(".//platformHeading")), root.findtext(".//pass")
        for pt in root.iter("geolocationGridPoint"):
            la, lo = float(pt.findtext("latitude")), float(pt.findtext("longitude"))
            d = (la - lat) ** 2 + ((lo - lon) * np.cos(np.radians(lat))) ** 2
            if d < best[0]:
                best = (d, float(pt.findtext("incidenceAngle")))
if best[1] is None: sys.exit("no annotation under data/raw/s1/pre/*.SAFE")
look = (heading + 90) % 360                      # right-looking
g = {"pass": pas, "heading_deg": heading, "incidence_deg": best[1],
     "look_azimuth_deg": look, "toward_sensor_azimuth_deg": (look + 180) % 360}
Path("outputs/diagnostics").mkdir(parents=True, exist_ok=True)
Path("outputs/diagnostics/look_geometry.json").write_text(json.dumps(g, indent=2)); print(g)
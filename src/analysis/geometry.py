import argparse, json, sys
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument("--bbox", required=True)
ap.add_argument("--ann-dir", help="folder of GRD product annotation XMLs (PC route: data/raw/sentinel1/pc_annotation/pre)")
args = ap.parse_args()
w, s, e, n = map(float, args.bbox.split(","))
lon, lat = (w + e) / 2, (s + n) / 2
best, heading, pas = (np.inf, None), None, None
anns = (sorted(Path(args.ann_dir).glob("*.xml")) if args.ann_dir else
        [x for safe in sorted(Path("data/raw/sentinel1/pre").glob("*.SAFE")) for x in sorted(safe.glob("annotation/s1*-vv-*.xml"))])
for ann in anns:
    if True:
        root = ET.parse(ann).getroot()
        if root.findtext(".//platformHeading") is None: print(f"skip {ann.name}: not a product annotation"); continue
        heading, pas = float(root.findtext(".//platformHeading")), root.findtext(".//pass")
        for pt in root.iter("geolocationGridPoint"):
            la, lo = float(pt.findtext("latitude")), float(pt.findtext("longitude"))
            d = (la - lat) ** 2 + ((lo - lon) * np.cos(np.radians(lat))) ** 2
            if d < best[0]:
                best = (d, float(pt.findtext("incidenceAngle")))
if best[1] is None: sys.exit(f"no annotation under {args.ann_dir or 'data/raw/sentinel1/pre/*.SAFE'}")
look = (heading + 90) % 360                      # right-looking
g = {"pass": pas, "heading_deg": heading, "incidence_deg": best[1],
     "look_azimuth_deg": look, "toward_sensor_azimuth_deg": (look + 180) % 360,
     "source": "PC GRD annotation" if args.ann_dir else "SAFE annotation"}
Path("outputs/diagnostics").mkdir(parents=True, exist_ok=True)
Path("outputs/diagnostics/look_geometry.json").write_text(json.dumps(g, indent=2)); print(g)
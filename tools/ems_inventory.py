import re
from pathlib import Path
import pyogrio

root = Path("data/external/EMSR927")
for f in sorted([*root.rglob("*.gpkg"), *root.rglob("*.shp"), *root.rglob("*.geojson")]):
    prod = (re.search(r"_(DEL|GRA|REF|FEP|MONIT\d*)_", f.name) or [None, "?"])[1]
    for name, gt in pyogrio.list_layers(f):
        info = pyogrio.read_info(f, layer=str(name)); cols = [c for c in info["fields"] if c in ("event_type", "obj_desc", "damage_gra")]
        vals = {}
        if cols and info["features"]:
            df = pyogrio.read_dataframe(f, layer=str(name), read_geometry=False, columns=cols)
            vals = {c: sorted(df[c].dropna().astype(str).unique())[:6] for c in cols}
        print(f"{f.relative_to(root)} | {prod} | {name} | {gt} | n={info['features']} | {vals}")
#!/usr/bin/env python3
import argparse, json
from pathlib import Path
import numpy as np, rasterio, geopandas as gpd, folium
from rasterio.warp import calculate_default_transform, reproject, Resampling
from src import config

COLORS = {1: (31, 119, 180, 230), 2: (230, 85, 13, 220), 3: (214, 39, 40, 220), 254: (110, 110, 110, 140)}
STATUS = {"cut_off": "red", "degraded": "orange", "reachable": "green", "no_pre_flood_path": "gray", "is_town": "blue"}
ATTR = ("Contains modified Copernicus Sentinel data 2026. Produced using Copernicus WorldDEM-30 &copy; DLR e.V. 2010-2014 and &copy; Airbus Defence and "
        "Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved. &copy; OpenStreetMap contributors.")

def class_overlay(path):
    with rasterio.open(path) as s:
        t, w, h = calculate_default_transform(s.crs, "EPSG:4326", s.width, s.height, *s.bounds)
        out = np.full((h, w), 255, np.uint8)
        reproject(s.read(1), out, src_transform=s.transform, src_crs=s.crs, src_nodata=255, dst_transform=t, dst_crs="EPSG:4326",
                  dst_nodata=255, resampling=Resampling.nearest)
    rgba = np.zeros((h, w, 4), np.uint8)
    for k, c in COLORS.items(): rgba[out == k] = c
    (west, north), (east, south) = t * (0, 0), t * (w, h)
    return rgba, [[south, west], [north, east]]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="data/processed/fused_class_30m.tif"); ap.add_argument("--sens-dir", default="data/processed/_sens")
    ap.add_argument("--flood-path", default="outputs/flood_path"); ap.add_argument("--out", default="outputs/dashboard/index.html")
    a = ap.parse_args(); J = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    imp, cut, det = J("outputs/impact_summary.json"), J("outputs/cutoff_settlements.json"), J("outputs/diagnostics/detect_asc85.json")
    rgba, bounds = class_overlay(a.cls)
    m = folium.Map(location=[(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2], zoom_start=11, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)          # CartoDB tiles now need an API key
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery (basemap only, not an input)", name="Satellite basemap", show=False).add_to(m)
    folium.raster_layers.ImageOverlay(rgba, bounds, name="Detected change (base) + radar-unobservable (grey)", opacity=1, zindex=3).add_to(m)
    for nm in ("low", "high"):
        p = Path(a.sens_dir) / nm / "fused_class_30m.tif"
        if p.exists():
            r2, b2 = class_overlay(str(p)); folium.raster_layers.ImageOverlay(r2, b2, name=f"Scenario: {nm} threshold", opacity=1, show=False, zindex=2).add_to(m)
    def geo(path, name, style, show=True):
        if Path(path).exists():
            g = gpd.read_file(path).to_crs(4326)
            if len(g): folium.GeoJson(g[["geometry"]].to_json(), name=name, style_function=lambda _: style, show=show).add_to(m)
    geo("outputs/affected_roads.geojson", "Motorable roads in mask", {"color": "#7a0177", "weight": 3})
    geo("outputs/affected_bridges.geojson", "Bridges exposed (not failed)", {"color": "#000000", "weight": 5})
    geo(f"{a.flood_path}/corridor.geojson", "Flood-path corridor", {"color": "#1f77b4", "weight": 1, "fillOpacity": 0.15}, show=False)
    geo(f"{a.flood_path}/path.geojson", "Flood path (D8)", {"color": "#08519c", "weight": 3}, show=False)
    if Path("outputs/affected_buildings.gpkg").exists():
        b = gpd.read_file("outputs/affected_buildings.gpkg").to_crs(4326); b = b[b["tier"] == "overlap"]
        folium.GeoJson(b[["geometry"]].to_json(), name=f"Buildings overlapping the mask ({len(b):,})",
                       style_function=lambda _: {"color": "#cc0000", "weight": 1, "fillOpacity": 0.5}).add_to(m)
    fg, fb_g = folium.FeatureGroup(name="Settlements by road access to a hospital").add_to(m), folium.FeatureGroup(name="First break on the route").add_to(m)
    for s in cut["settlements"]:
        h = s["hospital"]
        pop = (f"<b>{s['name']}</b><br>status: {h['status']}<br>to hospital: {h['pre_km']} km before, {h['post_km']} km after"
               f"<br>share of route observed by the detector: {s['route_assessed_frac']}")
        folium.CircleMarker([s["lat"], s["lon"]], radius=5 if h["status"] in ("cut_off", "degraded") else 3, color=STATUS.get(h["status"], "gray"),
                            fill=True, fill_opacity=0.8, popup=folium.Popup(pop, max_width=260)).add_to(fg)
        if s.get("first_break"):
            f = s["first_break"]; folium.Marker([f["lat"], f["lon"]], icon=folium.Icon(color="black", icon="remove"),
                                                popup=f"first break ({f['cause']}) on the route of {s['name']}").add_to(fb_g)
    if Path("data/raw/osm/hospitals.geojson").exists():
        for _, r in gpd.read_file("data/raw/osm/hospitals.geojson").to_crs(4326).iterrows():
            c = r.geometry.centroid; folium.Marker([c.y, c.x], icon=folium.Icon(color="blue", icon="plus"), popup=str(r.get("name") or "hospital")).add_to(m)
    rr, rc, bs = imp["sensitivity"]["range"], cut["sensitivity"]["range"], imp["buildings"]
    sp = lambda r: f"{r[0]:,}" if r[0] == r[1] else f"{r[0]:,}&ndash;{r[1]:,}"
    unk = (bs["not_assessed"] + bs["unobservable"]) / bs["total"]
    _cn = Path("outputs/validation/class_nulls.json")
    null_note = "" if not _cn.exists() else "<br><b>" + json.loads(_cn.read_text(encoding="utf-8"))["statement"] + "</b>"
    panel = (f"<div style='position:fixed;top:10px;left:50px;z-index:9999;background:#fff;padding:8px 12px;border:1px solid #888;font:12px sans-serif;max-width:380px'>"
             f"<b>Trishuli / Bhote Koshi flood, {config.FLOOD_DATE}</b> &mdash; <i>educational prototype, not an operational tool; exposure to a detected mask, "
             f"not a validated flood extent</i>{null_note}<br>Detector status: <b>{det['status']}</b> &middot; buildings overlapping the mask: <b>{sp(rr['buildings_overlap'])}</b> "
             f"(unknown status: {unk:.0%}) &middot; motorable road in mask: {rr['motorable_road_km'][0]:.1f}&ndash;{rr['motorable_road_km'][1]:.1f} km &middot; "
             f"bridges exposed: {sp(rr['bridges_exposed'])} &middot; settlements cut off from a hospital: <b>{sp(rc['hospital_cut_off'])}</b> "
             f"(range: thresholds, mask &plusmn;1 px, bridge policy)<br><span style='color:#1f77b4'>&#9632;</span> flood-like "
             f"<span style='color:#e6550d'>&#9632;</span> dark change <span style='color:#d62728'>&#9632;</span> bright change "
             f"<span style='color:#6e6e6e'>&#9632;</span> radar-unobservable</div>")
    foot = f"<div style='position:fixed;bottom:0;left:0;right:0;z-index:9999;background:rgba(255,255,255,.9);font:10px sans-serif;padding:2px 6px'>{ATTR}</div>"
    m.get_root().html.add_child(folium.Element(panel + foot)); folium.LayerControl(collapsed=False).add_to(m)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); m.save(a.out); print("wrote", a.out)

if __name__ == "__main__":
    main()
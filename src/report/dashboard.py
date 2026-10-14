#!/usr/bin/env python3
"""THE dashboard deliverable: outputs/dashboard/index.html (folium / Leaflet), built only from the pipeline's JSON and rasters.

    python -m src.report.dashboard [--out outputs/dashboard/index.html]

Every number and status on the page is read from a file (run.json, detect_<track>.json, impact_summary.json,
cutoff_settlements.json, class_nulls.json, emsr927_validation.json, flood_path*/summary.json); nothing is typed here.
Case-study-only inputs (class nulls, EMS, flood path, scenario masks) are optional: a missing file drops its line or
layer, so the page builds for any area. Leaflet, jQuery, Bootstrap, Font Awesome and the marker plugins are served
from outputs/dashboard/vendor/ (copied from src/report/vendor/), so the map draws with no internet; when basemap tiles
fail the page falls back to a plain background and says so. Replaces the retired static page src/report/dashboard_full.py."""
import argparse, html, json, re, shutil
from pathlib import Path
import numpy as np, rasterio, geopandas as gpd, folium
from scipy import ndimage as ndi
from rasterio.warp import calculate_default_transform, reproject, Resampling
from src import config
from src.report import attribution as A
from src.report import textbits as T

ROOT = Path(__file__).resolve().parents[2]
VENDOR_SRC = Path(__file__).resolve().parent / "vendor"
CLASS_RGBA = {1: (31, 119, 180, 230), 2: (230, 85, 13, 220), 3: (214, 39, 40, 220)}
UNOBS_RGBA, NOTASSESSED_RGBA = (90, 90, 90, 150), (200, 200, 200, 90)
STATUS = {"cut_off": "red", "degraded": "orange", "reachable": "green", "no_pre_flood_path": "gray", "is_town": "blue"}
BLANK_TILE = "data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
E = lambda s: html.escape(str(s), quote=True)


def J(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def to_4326(path):
    with rasterio.open(path) as s:
        t, w, h = calculate_default_transform(s.crs, "EPSG:4326", s.width, s.height, *s.bounds)
        out = np.full((h, w), 255, np.uint8)
        reproject(s.read(1), out, src_transform=s.transform, src_crs=s.crs, src_nodata=255, dst_transform=t, dst_crs="EPSG:4326",
                  dst_nodata=255, resampling=Resampling.nearest)
    (west, north), (east, south) = t * (0, 0), t * (w, h)
    return out, [[south, west], [north, east]]


def flag_bounds(cls_path):
    """[[south, west], [north, east]] (EPSG:4326) of the classes 1-3 pixels of the TRUE mask, or None when nothing is
    flagged. Computed on the native grid and transformed, so the view opens on the flagged change (review item 6)."""
    from rasterio.warp import transform_bounds
    with rasterio.open(cls_path) as s:
        out, t, crs = s.read(1), s.transform, s.crs
    flag = np.isin(out, (1, 2, 3))
    if not flag.any(): return None
    ys, xs = np.nonzero(flag); (w_, n_), (e_, s_) = t * (xs.min(), ys.min()), t * (xs.max() + 1, ys.max() + 1)
    w, s, e, n = transform_bounds(crs, "EPSG:4326", min(w_, e_), min(s_, n_), max(w_, e_), max(s_, n_))
    return [[s, w], [n, e]]


def display_classes(c, iterations=2):
    """Display-only copy: each flagged class dilated by `iterations` pixels so a 3 km² result is visible on a ~3,400 km²
    view. The numbers always use the true mask; this array is only ever coloured. Water-like (1) is drawn on top."""
    out = np.where(np.isin(c, (1, 2, 3)), c, 0).astype(np.uint8)
    for k in (3, 2, 1):
        vis = ndi.binary_dilation(c == k, iterations=iterations)
        out[vis & ((out == 0) | (k == 1))] = k
    return out


def rgba_of(cls, colors):
    rgba = np.zeros(cls.shape + (4,), np.uint8)
    for k, c in colors.items(): rgba[cls == k] = c
    return rgba


def span(r, key, fmt="{:,}"):
    v = (r or {}).get(key)
    if not v: return None
    return fmt.format(v[0]) if v[0] == v[1] else f"{fmt.format(v[0])}&ndash;{fmt.format(v[1])}"


def headline(det, imp, cutj, cn, ems, s2):
    """All panel text, from the JSON files only."""
    b = imp["buildings"]; rr = T.scenario_range(imp)
    rb = imp["roads_bridges"]["exposure_by_tolerance"]["0m"]
    cut = (cutj or {}).get("summary", {}); rc = ((cutj or {}).get("sensitivity") or {}).get("range") or {}
    unk = (b.get("not_assessed", 0) + b.get("unobservable", 0)) / max(b["total"], 1)
    rng = lambda key, fmt="{:,}": f" (range {span(rr, key, fmt)})" if span(rr, key, fmt) else ""
    L = []
    cal = E(T.cal_phrase(det))                        # Step 11: "calibration target not met; minimum detectable area ≈ N km²"
    L.append(f"Detector status: <b>{E(det['status'])}</b> &middot; track {E(det['track'])} &middot; {cal}")
    if config.S1_SOURCE == "pc":
        L.append(f"<b>Sentinel-1 source: {E(T.PC_SOURCE)}</b> &mdash; {E(T.PC_ROUTE_NOTE)}")
    area = det.get("area_km2", {})
    L.append(f"Flagged on the valley floor: {area.get('flood_water', 0):.2f} km&sup2; flood-like (water-like backscatter change), "
             f"{area.get('surface_dark', 0):.2f} km&sup2; dark change, {area.get('surface_bright', 0):.2f} km&sup2; bright change")
    L.append(f"Buildings overlapping the mask: <b>{b['overlap']:,}</b>{rng('buildings_overlap')} of {b['total']:,} "
             f"&middot; buildings of unknown status (outside the observed floor): <b>{unk:.0%}</b>")
    L.append(f"Motorable road in mask: {rb['motorable_road_km']:.1f} km{rng('motorable_road_km', '{:.1f}')} &middot; "
             f"bridges exposed (not failed): {rb['bridges']}{rng('bridges_exposed')}")
    if cut:
        sp = span(rc, "hospital_cut_off")
        tot, nop = cut.get("total_settlements", 0), cut.get("hospital_no_pre_flood_path", 0)
        L.append(f"Settlements with no road path to a hospital: <b>{cut.get('cut_off', 0)}</b>{f' (range {sp})' if sp else ''} of "
                 f"{tot:,}, of {tot - nop:,} assessable" + (f"; {T.plural(nop, 'settlement')} had no pre-flood route (not assessed)" if nop else ""))
    if rr: L.append("<i>Range = detector thresholds low/base/high" + (" &times; mask &plusmn;1 px &times; bridge policy" if rc else "") + ".</i>")
    if cn and cn.get("statement"): L.append(f"<b>{E(cn['statement'])}</b>")
    if s2 and s2.get("status") and s2.get("status") != "change_detected":
        L.append(f"Sentinel-2: {s2.get('floor_clear_post_fraction', 0):.0%} of the floor clear after the event, status {E(s2['status'])}; excluded.")
    if ems: L.append(E(A.EMS_HOLDINGS) + " EMS data is used for checking only.")
    return L


def flood_path_layer(m, d, label, color, show):
    d = Path(d); s = J(d / "summary.json")
    if not s or not (d / "path.geojson").exists(): return None
    fg = folium.FeatureGroup(name=f"Flood path, {label} ({s['path_km']} km within the study area)", show=show).add_to(m)
    if (d / "corridor.geojson").exists():
        folium.GeoJson(gpd.read_file(d / "corridor.geojson").to_crs(4326)[["geometry"]].to_json(),
                       style_function=lambda _: {"color": color, "weight": 1, "fillOpacity": 0.12}).add_to(fg)
    folium.GeoJson(gpd.read_file(d / "path.geojson").to_crs(4326)[["geometry"]].to_json(),
                   style_function=lambda _: {"color": color, "weight": 3}).add_to(fg)
    return s


def vendorize(out_html):
    """Copy src/report/vendor/ next to the page and point every CDN URL at it. Unknown URLs are reported, not fatal."""
    out_html = Path(out_html); vd = out_html.parent / "vendor"
    if VENDOR_SRC.exists():
        # Copy over in place: no rmtree, because Windows/Drive-synced folders often refuse to delete dirs (WinError 5).
        shutil.copytree(VENDOR_SRC, vd, dirs_exist_ok=True)
    t = out_html.read_text(encoding="utf-8"); missing = []
    def sub(mo):
        url = mo.group(2); rel = re.sub(r"^https?://", "", url).split("?")[0]
        if (vd / rel).exists(): return f'{mo.group(1)}vendor/{rel}{mo.group(3)}'
        missing.append(url); return mo.group(0)
    t = re.sub(r'((?:src|href)=")(https?://[^"]+\.(?:js|css))(")', sub, t)
    out_html.write_text(t, encoding="utf-8")
    if missing: print("WARNING: not vendored (page needs internet for these; run tools/vendor_assets.py):", *missing, sep="\n  ")
    return missing


TILE_FALLBACK_JS = """
<script>
(function(){
  function hook(){
    var maps = Object.keys(window).filter(function(k){return k.indexOf('map_')===0 && window[k] && window[k].eachLayer;});
    if(!maps.length){ return setTimeout(hook, 200); }
    var map = window[maps[0]], errors = 0, note = document.getElementById('tile-note');
    map.getContainer().style.background = '#e9eef2';
    map.eachLayer(function(l){
      if(l instanceof L.TileLayer && l.options && String(l._url).indexOf('data:') !== 0){
        l.on('tileerror', function(){
          errors += 1;
          if(errors >= 4 && note){ note.style.display = 'block'; }
        });
      }
    });
  }
  hook();
})();
</script>"""


def build(out="outputs/dashboard/index.html", cls="data/processed/fused_class_30m.tif", sens_dir="data/processed/_sens",
          flood_path="outputs/flood_path", flood_path_trib="outputs/flood_path_trib"):
    det = J(f"outputs/diagnostics/detect_{config.TRACK}.json")
    imp, cutj = J("outputs/impact_summary.json"), J("outputs/cutoff_settlements.json")
    if det is None or imp is None: raise SystemExit(f"dashboard: detect_{config.TRACK}.json and impact_summary.json are required")
    cn, ems, s2 = J("outputs/validation/class_nulls.json"), J("outputs/validation/emsr927_validation.json"), J("outputs/diagnostics/s2_detect.json")
    have_ems = bool(ems) and Path("data/external/EMSR927").is_dir()

    base, bounds = to_4326(cls)
    m = folium.Map(location=[(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2], zoom_start=11, tiles=None,
                   control_scale=True)
    folium.TileLayer(tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", subdomains="abcd", max_zoom=20,
                     attr="&copy; OpenStreetMap contributors &copy; CARTO", name="Street map (OpenStreetMap data, CARTO tiles)").add_to(m)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery (basemap only, not an input)", name="Satellite basemap", show=False).add_to(m)
    folium.TileLayer(tiles=BLANK_TILE, attr=" ", name="Plain background (offline)", show=False).add_to(m)

    # scenarios: base shown, low / high as toggles (classes 1-3 only)
    scen = {"base": (base, bounds)}
    for nm in ("low", "high"):
        p = Path(sens_dir) / nm / "fused_class_30m.tif"
        if p.exists(): scen[nm] = to_4326(str(p))
    for nm in ("low", "base", "high"):
        if nm not in scen: continue
        c, bb = scen[nm]
        lab = {"base": "Scenario base threshold (headline)", "low": "Scenario low threshold (more change)",
               "high": "Scenario high threshold (less change)"}[nm]
        folium.raster_layers.ImageOverlay(rgba_of(display_classes(c), CLASS_RGBA), bb, name=lab + " (drawn 2 px wider)", opacity=1,
                                          show=(nm == "base"), zindex=3).add_to(m)
    folium.raster_layers.ImageOverlay(rgba_of(base, {254: UNOBS_RGBA}), bounds, name="Radar-unobservable (layover / shadow): UNKNOWN",
                                      opacity=1, show=False, zindex=2).add_to(m)
    folium.raster_layers.ImageOverlay(rgba_of(base, {253: NOTASSESSED_RGBA}), bounds, name="Outside the assessed valley floor: UNKNOWN",
                                      opacity=1, show=False, zindex=1).add_to(m)

    fp_main = flood_path_layer(m, flood_path, "main stem", "#08519c", False)
    fp_trib = flood_path_layer(m, flood_path_trib, "tributary", "#6a51a3", False)

    def geo(path, name, style, show=True):
        if Path(path).exists():
            g = gpd.read_file(path)
            if len(g): folium.GeoJson(g.to_crs(4326)[["geometry"]].to_json(), name=name, style_function=lambda _: style, show=show).add_to(m)
    geo("outputs/affected_roads.geojson", "Motorable roads in the mask", {"color": "#7a0177", "weight": 3})
    geo("outputs/affected_bridges.geojson", "Bridges exposed (not failed)", {"color": "#000000", "weight": 5})
    if Path("outputs/affected_buildings.gpkg").exists():
        bl = gpd.read_file("outputs/affected_buildings.gpkg"); bl = bl[bl["tier"] == "overlap"]
        if len(bl):
            folium.GeoJson(bl.to_crs(4326)[["geometry"]].to_json(), name=f"Buildings overlapping the mask ({len(bl):,})",
                           style_function=lambda _: {"color": "#cc0000", "weight": 1, "fillOpacity": 0.5}).add_to(m)
    if cutj and cutj.get("settlements"):
        fg = folium.FeatureGroup(name="Settlements by road access to a hospital").add_to(m)
        fb = folium.FeatureGroup(name="First break on the pre-flood route").add_to(m)
        for s in cutj["settlements"]:
            h = s["hospital"]
            pop = (f"<b>{E(s['name'])}</b><br>status: {E(h['status'])}<br>to hospital: {E(h['pre_km'])} km before, {E(h['post_km'])} km after"
                   f"<br>share of route observed by the detector: {E(s.get('route_assessed_frac'))}")
            folium.CircleMarker([s["lat"], s["lon"]], radius=5 if h["status"] in ("cut_off", "degraded") else 3, color=STATUS.get(h["status"], "gray"),
                                fill=True, fill_opacity=0.8, popup=folium.Popup(pop, max_width=260)).add_to(fg)
            if s.get("first_break"):
                f = s["first_break"]
                folium.Marker([f["lat"], f["lon"]], icon=folium.Icon(color="black", icon="remove"),
                              popup=f"first break ({E(f['cause'])}) on the route of {E(s['name'])}").add_to(fb)
    if Path("data/raw/osm/hospitals.geojson").exists():
        hs = gpd.read_file("data/raw/osm/hospitals.geojson")
        if len(hs):
            fh = folium.FeatureGroup(name="Hospitals (OSM, pre-event)").add_to(m)
            for _, r in hs.to_crs(4326).iterrows():
                c = r.geometry.centroid
                folium.Marker([c.y, c.x], icon=folium.Icon(color="blue", icon="plus"), popup=E(r.get("name") or "hospital")).add_to(fh)

    lines = headline(det, imp, cutj, cn, have_ems and ems, s2)
    fp = [f"{lab}: {s['path_km']} km, {s['n_settlements']} settlements on the corridor (geometry only)" for lab, s in
          (("main stem", fp_main), ("tributary", fp_trib)) if s]
    if fp: lines.append("Flood path within the study area &mdash; " + "; ".join(fp) + ".")
    legend = ("<span style='color:#1f77b4'>&#9632;</span> flood-like (water-like backscatter change) "
              "<span style='color:#e6550d'>&#9632;</span> dark change <span style='color:#d62728'>&#9632;</span> bright change "
              "<span style='color:#5a5a5a'>&#9632;</span> radar-unobservable")
    panel = (f"<div id='hdr' style='position:fixed;top:10px;left:50px;z-index:9999;background:#fff;padding:8px 12px;border:1px solid #888;"
             f"font:12px/1.35 sans-serif;max-width:430px;max-height:70vh;overflow:auto'>"
             f"<details open><summary><b>Summary</b></summary>"
             f"<b>{E(config.TITLE)}</b><br><i>{E(A.DISCLAIMER)} Exposure to a detected change mask, not a validated flood extent "
             f"and not damage.</i><br>" + "<br>".join(lines) + f"<br>{legend}"
             f"<br><i>Flagged pixels are drawn 2 px wider so they are visible; every number uses the true mask.</i></details>"
             f"<div id='tile-note' style='display:none;margin-top:4px;color:#a50'>Basemap tiles could not load (offline?): choose "
             f"&ldquo;Plain background (offline)&rdquo;. All analysis layers are embedded in this file.</div></div>")
    foot = (f"<div style='position:fixed;bottom:0;left:0;right:0;z-index:9999;background:rgba(255,255,255,.92);font:10px sans-serif;padding:2px 6px'>"
            f"{A.html(with_ems=have_ems)} {E(A.DISCLAIMER)}</div>")
    m.get_root().html.add_child(folium.Element(panel + foot + TILE_FALLBACK_JS))
    folium.LayerControl(collapsed=False).add_to(m)
    fb_ = flag_bounds(cls)
    m.fit_bounds(fb_ if fb_ else bounds, padding=(40, 40))      # open on the flagged change, else on the whole area
    Path(out).parent.mkdir(parents=True, exist_ok=True); m.save(out)
    vendorize(out)
    print("wrote", out)
    return Path(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cls", default="data/processed/fused_class_30m.tif"); ap.add_argument("--sens-dir", default="data/processed/_sens")
    ap.add_argument("--flood-path", default="outputs/flood_path"); ap.add_argument("--flood-path-trib", default="outputs/flood_path_trib")
    ap.add_argument("--out", default="outputs/dashboard/index.html")
    a = ap.parse_args()
    build(a.out, a.cls, a.sens_dir, a.flood_path, a.flood_path_trib)


if __name__ == "__main__":
    main()

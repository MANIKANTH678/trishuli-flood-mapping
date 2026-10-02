"""Full Folium dashboard: flood mask + susceptibility + impact layers."""
import os, sys, json
import numpy as np
import rioxarray
import folium
from folium.plugins import MarkerCluster
import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import PROCESSED_DIR, OUTPUT_DIR as OUTPUTS_DIR


def main():
    roads     = gpd.read_file(os.path.join(OUTPUTS_DIR, "affected_roads.geojson"))
    buildings = gpd.read_file(os.path.join(OUTPUTS_DIR, "affected_buildings.gpkg"))
    b_flooded = buildings[buildings["flooded"]]
    with open(os.path.join(OUTPUTS_DIR, "cutoff_settlements.json")) as f:
        cutoffs = json.load(f)

    cx = b_flooded.geometry.centroid.x.mean() if len(b_flooded) else 85.0
    cy = b_flooded.geometry.centroid.y.mean() if len(b_flooded) else 28.0

    m = folium.Map(location=[cy, cx], zoom_start=11, tiles="OpenStreetMap")

    folium.GeoJson(
        roads.to_crs(4326),
        name="Flooded roads",
        style_function=lambda f: {"color": "red", "weight": 2},
    ).add_to(m)

    cluster = MarkerCluster(name="Affected buildings").add_to(m)
    for _, r in b_flooded.to_crs(4326).iterrows():
        pt = r.geometry.centroid
        folium.CircleMarker([pt.y, pt.x], radius=2,
                            color="orange", fill=True,
                            fill_opacity=0.7).add_to(cluster)

    grp = folium.FeatureGroup(name="⚠️ Cut-off settlements").add_to(m)
    for s in cutoffs:
        if s["cut_off"]:
            folium.Marker(
                [s["lat"], s["lon"]],
                popup=f"<b>{s['name']}</b><br>CUT OFF",
                icon=folium.Icon(color="red", icon="warning-sign"),
            ).add_to(grp)

    # P2 flood mask overlay
    try:
        mask = rioxarray.open_rasterio(
            os.path.join(PROCESSED_DIR, "flood_mask.tif"), masked=True
        ).squeeze()
        bnds = mask.rio.bounds()
        folium.raster_layers.ImageOverlay(
            image=np.where(mask.values == 1, 1, np.nan),
            bounds=[[bnds[1], bnds[0]], [bnds[3], bnds[2]]],
            colormap=lambda x: (0, 0.4, 1, 0.5),
            name="Observed flood (P2)",
        ).add_to(m)
    except Exception as e:
        print(f"⚠️  P2 layer skipped: {e}")

    folium.LayerControl().add_to(m)
    out = os.path.join(OUTPUTS_DIR, "flood_dashboard_full.html")
    m.save(out)
    print(f"✅ {out}")


if __name__ == "__main__":
    main()

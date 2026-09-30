"""Convert the clipped OSM PBF to GeoJSON layers for the flood project."""
import os
import pyrosm

PBF = "data/raw/osm/trishuli_corridor.osm.pbf"
OUT = "data/raw/osm"
os.makedirs(OUT, exist_ok=True)

print(f"📖 Reading {PBF} ...")
osm = pyrosm.OSM(PBF)

# ── Roads ─────────────────────────────────────────────────────────
print("\n🛣  Extracting roads ...")
roads = osm.get_network(network_type="all")
roads.to_file(f"{OUT}/roads.geojson", driver="GeoJSON")
print(f"   ✅ {len(roads)} road segments")

# ── Buildings ─────────────────────────────────────────────────────
print("\n🏠 Extracting buildings ...")
buildings = osm.get_buildings()
if buildings is not None and len(buildings) > 0:
    buildings.to_file(f"{OUT}/buildings.geojson", driver="GeoJSON")
    print(f"   ✅ {len(buildings)} buildings")
else:
    print("   ⚠️ No buildings found")

# ── Settlements + hospitals via custom filter ─────────────────────
print("\n📍 Extracting place nodes (settlements) ...")
try:
    places = osm.get_data_by_custom_criteria(
        custom_filter={"place": ["village", "town", "city", "hamlet"]},
        filter_type="keep",
        keep_nodes=True,
        keep_ways=False,
        keep_relations=False,
    )
    if places is not None and len(places) > 0:
        places.to_file(f"{OUT}/settlements.geojson", driver="GeoJSON")
        print(f"   ✅ {len(places)} settlements")
    else:
        print("   ⚠️ No settlements found")
except Exception as e:
    print(f"   ❌ {e}")

print("\n🏥 Extracting hospitals/clinics ...")
try:
    hospitals = osm.get_pois(
        custom_filter={"amenity": ["hospital", "clinic", "doctors"]},
    )
    if hospitals is not None and len(hospitals) > 0:
        hospitals.to_file(f"{OUT}/hospitals.geojson", driver="GeoJSON")
        print(f"   ✅ {len(hospitals)} health facilities")
    else:
        print("   ⚠️ No hospitals found")
except Exception as e:
    print(f"   ❌ {e}")

print("\n🎉 Done.")

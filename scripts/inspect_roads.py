import json

with open("scripts/nominatim_roads_raw.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for key, items in data.items():
    print(f"=== {key} ({len(items)} items) ===")
    for i, it in enumerate(items):
        g = it.get("geojson", {})
        coords = g.get("coordinates", [])
        print(f"  [{i}] osm_id={it.get('osm_id')} osm_type={it.get('osm_type')} class={it.get('class')}/{it.get('type')}")
        print(f"      display: {it.get('display_name')}")
        print(f"      geom_type: {g.get('type')} coords_len: {len(coords)}")
        if coords:
            if g.get("type") == "LineString":
                print(f"      start: {coords[0]}, end: {coords[-1]}")
            elif g.get("type") == "MultiLineString":
                print(f"      lines: {len(coords)}, start: {coords[0][0]}, end: {coords[-1][-1]}")

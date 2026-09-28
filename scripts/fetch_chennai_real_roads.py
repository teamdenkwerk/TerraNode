import httpx
import json

query = """
[out:json][timeout:30];
(
  way["highway"~"primary|secondary|tertiary|trunk"](13.033,80.224,13.049,80.245);
  way["waterway"](13.033,80.224,13.049,80.245);
);
out geom;
"""

endpoints = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

headers = {
    "User-Agent": "TerraNodeGeospatial/2026.1 (urban-gis-recon)",
    "Content-Type": "application/x-www-form-urlencoded"
}

for ep in endpoints:
    try:
        print(f"Trying {ep}...")
        r = httpx.post(ep, data={"data": query}, headers=headers, timeout=25.0)
        print("Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            elements = data.get("elements", [])
            print(f"Success! {len(elements)} elements retrieved.")
            with open("scripts/chennai_osm_raw.json", "w", encoding="utf-8") as f:
                json.dump(elements, f, indent=2)
            break
    except Exception as e:
        print("Error on", ep, e)

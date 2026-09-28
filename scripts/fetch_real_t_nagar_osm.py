import urllib.request
import urllib.parse
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

query = """
[out:json][timeout:25];
(
  way["highway"]["name"~"Usman|Thyagaraya|Chetty|Venkatanarayana|Doraiswamy|Burkit|Pondy"](13.033,80.225,13.049,80.245);
);
out geom;
"""

mirrors = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

for url in mirrors:
    print(f"Trying {url}...")
    try:
        req = urllib.request.Request(
            url,
            data=f"data={urllib.parse.quote(query)}".encode("utf-8"),
            headers={"User-Agent": "TerraNode-GIS/2026.1 (urban-gis-recon)"}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elements = data.get("elements", [])
            print(f"Success! Found {len(elements)} elements from {url}")
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name", "Unnamed")
                geom = el.get("geometry", [])
                print(f"- {name} ({tags.get('highway')}, {len(geom)} pts)")
                if "Usman" in name and geom:
                    print(f"  Sample: {geom[0]} to {geom[-1]}")
            with open("scripts/osm_t_nagar_roads.json", "w", encoding="utf-8") as f:
                json.dump(elements, f, indent=2)
            break
    except Exception as e:
        print(f"Failed {url}: {e}")

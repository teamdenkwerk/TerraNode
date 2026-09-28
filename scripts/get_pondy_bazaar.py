import urllib.request
import urllib.parse
import json

queries = [
    'Pondy Bazaar Chennai',
    'Thyagaraya Road T Nagar Chennai',
    'Sir Theagaraya Road T Nagar',
    'G N Chetty Road T Nagar Chennai',
    'Panagal Park Chennai'
]

results = {}
for q in queries:
    url = f'https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&format=json&polygon_geojson=1&limit=3'
    req = urllib.request.Request(url, headers={'User-Agent': 'TerraNode-GIS/2026.1'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results[q] = data
            print(f"=== {q} ({len(data)} items) ===")
            for it in data:
                g = it.get('geojson', {})
                print(f"  osm_id={it.get('osm_id')} type={g.get('type')} pts={len(g.get('coordinates', []))} name={it.get('display_name')[:70]}")
                if g.get('type') == 'LineString':
                    print("    start:", g.get('coordinates')[0], "end:", g.get('coordinates')[-1])
    except Exception as e:
        print(q, e)

with open('scripts/pondy_bazaar_raw.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)

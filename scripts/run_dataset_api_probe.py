import httpx
import json

base_url = "http://127.0.0.1:8000"
client = httpx.Client()

# 1. Get current active dataset
r = client.get(f"{base_url}/api/datasets/active")
print("1. Active dataset:", r.status_code, r.json().get("dataset_id"), r.json().get("city"))

# 2. Get sample package
r = client.get(f"{base_url}/api/datasets/sample-package/chennai")
print("2. Chennai sample package:", r.status_code, r.json().get("city"), "Entities:", r.json().get("entities_count"))

# 3. List all datasets
r = client.get(f"{base_url}/api/datasets")
print("3. Datasets count:", r.status_code, len(r.json()))
for d in r.json():
    print(f"   - {d['city']} ({d['aoi']}): status={d['dataset_status']}, is_active={d['is_active']}")

# 4. Switch to Chennai
r = client.post(f"{base_url}/api/datasets/active", json={"dataset_id": "chennai-tnagar"})
print("4. Switch to Chennai:", r.status_code, r.json().get("message"))

# 5. Verify active is now Chennai
r = client.get(f"{base_url}/api/datasets/active")
print("5. Active is now:", r.json().get("city"), r.json().get("aoi"))

# 6. Verify GET /entities gives Chennai entities!
r = client.get(f"{base_url}/entities?limit=5")
print("6. GET /entities count:", len(r.json()), "Sample UID:", r.json()[0]["canonical_uid"])

# 7. Switch back to Bengaluru
r = client.post(f"{base_url}/api/datasets/active", json={"dataset_id": "bengaluru-ward112"})
print("7. Restored to Bengaluru:", r.json().get("message"))

# 8. Verify GET /entities gives Bengaluru entities!
r = client.get(f"{base_url}/entities?limit=5")
print("8. GET /entities count:", len(r.json()), "Sample UID:", r.json()[0]["canonical_uid"])

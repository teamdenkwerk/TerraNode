"""
scripts/verify_workspace_replacement.py

End-to-End Live Verification of the City / AOI Dataset Import & Active Workspace System.
Tests:
1. Active Workspace Check (Default: Bengaluru)
2. Pre-Scan Analysis of CHENNAI_DATA (15-category standard structure)
3. Safe Replacement Import (Chennai becomes ACTIVE, Bengaluru becomes ARCHIVED)
4. Strict Geometrical Scoping (Parcels & Infrastructure)
5. Guardrail: Malformed Import Rejection (Current active area strictly preserved)
6. Instant Area Switching (Switch back to Bengaluru)
"""

import httpx
import json

BASE_URL = "http://127.0.0.1:8000"


def main():
    print("\n" + "=" * 75)
    print("TERRANODE: CITY / AOI DATASET IMPORT & WORKSPACE REPLACEMENT VERIFICATION")
    print("=" * 75)

    with httpx.Client(timeout=10.0) as client:
        # STEP 1: Verify Default Active Area is Bengaluru
        r1 = client.get(f"{BASE_URL}/api/datasets/active")
        assert r1.status_code == 200, f"Failed GET /api/datasets/active: {r1.status_code}"
        d1 = r1.json()
        print(f"[STEP 1] Default Active Dataset: {d1['city']} — {d1['aoi']} (ID: {d1['dataset_id']}, Status: {d1['dataset_status']})")
        assert d1["city"] == "Bengaluru"
        assert d1["dataset_status"] == "ACTIVE"

        # STEP 2: Pre-Scan CHENNAI_DATA Folder
        r2 = client.post(f"{BASE_URL}/api/datasets/scan", json={"folder_path": "data/sample_packages/CHENNAI_DATA"})
        assert r2.status_code == 200, f"Failed POST /api/datasets/scan: {r2.status_code}"
        scan_rep = r2.json()
        print(f"[STEP 2] Pre-Scan Completed: Area: {scan_rep['area']}, Folders: {scan_rep['folders_count']}, Files: {scan_rep['files_count']}")
        print(f"         Detected Layers ({len(scan_rep['detected_layers'])}): {[l['category'] for l in scan_rep['detected_layers']]}")
        assert scan_rep["valid"] is True
        assert scan_rep["area"] == "Chennai"
        assert scan_rep["requires_replacement_confirmation"] is True

        # STEP 3: Replace Active Workspace with Chennai Package
        chennai_import_payload = {
            "dataset_id": "chennai-tnagar",
            "name": "Chennai — T. Nagar Commercial AOI",
            "city": "Chennai",
            "aoi": "T. Nagar AOI",
            "crs": scan_rep["crs_detected"],
            "bbox": scan_rep["bbox"],
            "center": scan_rep["center"],
            "replace_active": True,
            "actor": "Chief Town Planner",
            "entities": [
                {
                    "id": "MAA-201",
                    "surveyNumber": "TS-401/1A",
                    "wardNo": "Ward 134",
                    "zone": "T. Nagar",
                    "status": "reconciled",
                    "confidence": 98,
                    "area": 485.0,
                    "landUse": "Commercial",
                    "centroid": [13.0418, 80.2341],
                    "coordinates": [[13.0415, 80.2338], [13.0421, 80.2338], [13.0421, 80.2344], [13.0415, 80.2344]],
                }
            ],
        }
        r3 = client.post(f"{BASE_URL}/api/datasets/import", json=chennai_import_payload)
        assert r3.status_code == 200, f"Failed POST /api/datasets/import: {r3.status_code}"
        import_res = r3.json()
        print(f"[STEP 3] Workspace Replaced: {import_res['message']}")
        assert import_res["active_dataset"]["city"] == "Chennai"

        # Verify active dataset is now Chennai
        r3_active = client.get(f"{BASE_URL}/api/datasets/active")
        d3_active = r3_active.json()
        assert d3_active["city"] == "Chennai"
        print(f"         Active Area confirmed: {d3_active['city']} — {d3_active['aoi']} (Status: {d3_active['dataset_status']})")

        # STEP 4: Verify Infrastructure & Entity Scoping (Zero Mixed Geometries)
        r4_roads = client.get(f"{BASE_URL}/api/infrastructure/features?layer_type=road")
        roads = r4_roads.json()["features"]
        road_names = [f["properties"]["metadata"].get("road_name") for f in roads]
        print(f"[STEP 4] Scoped Chennai Roads: {road_names}")
        assert any("Usman Road" in str(r) for r in road_names)
        assert not any("Old Airport Road" in str(r) for r in road_names), "LEAK: Bengaluru road found in Chennai workspace!"

        r4_ent = client.get(f"{BASE_URL}/entities")
        entities = r4_ent.json()
        uids = [e["canonical_uid"] for e in entities]
        print(f"         Scoped Chennai Entities: {uids}")
        assert any("MAA" in str(u) for u in uids)
        assert not any("BLD-1028" in str(u) for u in uids), "LEAK: Bengaluru building found in Chennai workspace!"

        # STEP 5: Safe Replacement Guardrail (Malformed Import Rejection)
        bad_payload = {
            "dataset_id": "broken-package",
            "city": "",
            "aoi": "",
            "replace_active": True,
            "entities": [],
        }
        r5_bad = client.post(f"{BASE_URL}/api/datasets/import", json=bad_payload)
        assert r5_bad.status_code == 400
        print(f"[STEP 5] Guardrail Verified: Malformed import rejected with HTTP {r5_bad.status_code} ({r5_bad.json()['detail']})")

        # Verify Chennai is STILL active (untouched by failed import)
        r5_active = client.get(f"{BASE_URL}/api/datasets/active")
        assert r5_active.json()["city"] == "Chennai"
        print("         Safe Workspace state preserved: Chennai remains 100% active.")

        # STEP 6: Switch Active Workspace back to Bengaluru
        r6_switch = client.post(f"{BASE_URL}/api/datasets/active", json={"dataset_id": "bengaluru-ward112"})
        assert r6_switch.status_code == 200
        print(f"[STEP 6] Switched back to Bengaluru: {r6_switch.json()['message']}")

        # Verify Bengaluru is now active
        r6_active = client.get(f"{BASE_URL}/api/datasets/active")
        assert r6_active.json()["city"] == "Bengaluru"

        r6_roads = client.get(f"{BASE_URL}/api/infrastructure/features?layer_type=road")
        blr_roads = [f["properties"]["metadata"].get("road_name") for f in r6_roads.json()["features"]]
        print(f"         Restored Bengaluru Roads: {blr_roads}")
        assert any("Old Airport" in str(r) or "100 Feet" in str(r) for r in blr_roads)
        assert not any("Usman Road" in str(r) for r in blr_roads), "LEAK: Chennai road found in Bengaluru workspace!"

    print("\n" + "=" * 75)
    print("ALL 6 END-TO-END WORKSPACE IMPORT & REPLACEMENT VERIFICATIONS PASSED!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()

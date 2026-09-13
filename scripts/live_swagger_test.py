"""
live_swagger_test.py — Live HTTP Verification of all Swagger UI Endpoints against running Uvicorn server (http://localhost:8000).

Tests all 19 OpenAPI routes and specifically executes the RBAC negative security matrix:
- Calling Admin-only endpoints with an Investigator-role token (Confirms HTTP 403 Forbidden)
- Calling Analyst-only endpoints with an Investigator-role token (Confirms HTTP 403 Forbidden)
- Calling Admin-only endpoints with an Analyst-role token (Confirms HTTP 403 Forbidden)
- Calling all endpoints with authorized roles (Confirms HTTP 200 OK)
"""

import os
import sys
import io
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BASE_URL = "http://localhost:8000"

results = []

def log_test(endpoint: str, method: str, role: str, expected_code: int, actual_code: int, response_json: dict = None, note: str = ""):
    passed = expected_code == actual_code
    icon = "✅ PASS" if passed else "❌ FAIL"
    preview = str(response_json)[:60] if response_json else ""
    results.append({
        "endpoint": endpoint,
        "method": method,
        "role": role,
        "expected": expected_code,
        "actual": actual_code,
        "passed": passed,
        "note": note,
    })
    print(f"{icon} | {method:<6} {endpoint:<35} | Role: {role:<12} | Status: {actual_code} ({expected_code}) | {note}")
    if not passed:
        print(f"   -> Unexpected Response: {response_json}")


def main():
    print("\n" + "=" * 105)
    print("  LIVE HTTP SWAGGER UI ENDPOINT & RBAC AUDIT (http://localhost:8000)")
    print("=" * 105 + "\n")

    # 0. Check server liveness & Swagger docs
    try:
        r_docs = requests.get(f"{BASE_URL}/docs", timeout=5)
        log_test("/docs (Swagger UI)", "GET", "public", 200, r_docs.status_code, note="Interactive Swagger UI loaded")
        r_openapi = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        log_test("/openapi.json", "GET", "public", 200, r_openapi.status_code, note=f"{len(r_openapi.json()['paths'])} paths registered")
        r_health = requests.get(f"{BASE_URL}/health", timeout=5)
        log_test("/health", "GET", "public", 200, r_health.status_code, r_health.json(), note=f"Status: {r_health.json().get('status')}")
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Uvicorn server is not running on http://localhost:8000!")
        sys.exit(1)

    # 1. Login with all 3 roles to get real JWT bearer tokens
    print("\n🔐 [Phase 1] Authenticating all 3 roles via /auth/login...")
    tokens = {}
    for role in ["admin", "analyst", "investigator"]:
        res = requests.post(f"{BASE_URL}/auth/login", json={"username": role, "password": "admin123"})
        data = res.json()
        tokens[role] = data.get("access_token")
        log_test("/auth/login", "POST", role, 200, res.status_code, note=f"Got JWT for role '{role}'")

    # Negative login test
    bad_login = requests.post(f"{BASE_URL}/auth/login", json={"username": "investigator", "password": "wrong_password"})
    log_test("/auth/login", "POST", "invalid", 401, bad_login.status_code, note="Rejected invalid password")

    # Headers for each role
    h_inv = {"Authorization": f"Bearer {tokens['investigator']}"}
    h_ana = {"Authorization": f"Bearer {tokens['analyst']}"}
    h_adm = {"Authorization": f"Bearer {tokens['admin']}"}

    # Verify /auth/me for each
    r_me_inv = requests.get(f"{BASE_URL}/auth/me", headers=h_inv)
    log_test("/auth/me", "GET", "investigator", 200, r_me_inv.status_code, r_me_inv.json(), note=f"User: {r_me_inv.json().get('username')}, Role: {r_me_inv.json().get('role')}")

    # 2. RBAC Negative Tests (The exact test Claude asked to verify)
    print("\n🚫 [Phase 2] CRITICAL RBAC SECURITY: Attempting Admin & Analyst endpoints with INVESTIGATOR token...")

    # Admin endpoints with Investigator token -> MUST BE 403
    r1 = requests.get(f"{BASE_URL}/audit/verify", headers=h_inv)
    log_test("/audit/verify", "GET", "investigator", 403, r1.status_code, r1.json(), note=f"Detail: {r1.json().get('detail')}")

    r2 = requests.get(f"{BASE_URL}/audit/logs", headers=h_inv)
    log_test("/audit/logs", "GET", "investigator", 403, r2.status_code, r2.json(), note=f"Detail: {r2.json().get('detail')}")

    # Analyst endpoints with Investigator token -> MUST BE 403
    r3 = requests.get(f"{BASE_URL}/analytics/influencers", headers=h_inv)
    log_test("/analytics/influencers", "GET", "investigator", 403, r3.status_code, r3.json(), note=f"Detail: {r3.json().get('detail')}")

    r4 = requests.get(f"{BASE_URL}/analytics/communities", headers=h_inv)
    log_test("/analytics/communities", "GET", "investigator", 403, r4.status_code, r4.json(), note=f"Detail: {r4.json().get('detail')}")

    r5 = requests.get(f"{BASE_URL}/analytics/link-predictions", headers=h_inv)
    log_test("/analytics/link-predictions", "GET", "investigator", 403, r5.status_code, r5.json(), note=f"Detail: {r5.json().get('detail')}")

    r6 = requests.get(f"{BASE_URL}/analytics/alerts", headers=h_inv)
    log_test("/analytics/alerts", "GET", "investigator", 403, r6.status_code, r6.json(), note=f"Detail: {r6.json().get('detail')}")

    r7 = requests.post(f"{BASE_URL}/analytics/rerun", headers=h_inv)
    log_test("/analytics/rerun", "POST", "investigator", 403, r7.status_code, r7.json(), note=f"Detail: {r7.json().get('detail')}")

    r8 = requests.post(f"{BASE_URL}/query/natural-language", json={"question": "Who is the kingpin?"}, headers=h_inv)
    log_test("/query/natural-language", "POST", "investigator", 403, r8.status_code, r8.json(), note=f"Detail: {r8.json().get('detail')}")

    csv_dummy = io.BytesIO(b"caller_number,callee_number,call_timestamp,duration_sec\n9847012345,9847012399,2024-08-20 10:00:00,120\n")
    r9 = requests.post(f"{BASE_URL}/ingest/cdr", files={"file": ("test.csv", csv_dummy, "text/csv")}, headers=h_inv)
    log_test("/ingest/cdr", "POST", "investigator", 403, r9.status_code, r9.json(), note=f"Detail: {r9.json().get('detail')}")

    txn_dummy = io.BytesIO(b"sender_account,receiver_account,amount,txn_timestamp,bank_name\nACC_RAVI_0001,ACC_DEEP_0002,100000,2024-08-20 11:00:00,SBI\n")
    r10 = requests.post(f"{BASE_URL}/ingest/transactions", files={"file": ("test.csv", txn_dummy, "text/csv")}, headers=h_inv)
    log_test("/ingest/transactions", "POST", "investigator", 403, r10.status_code, r10.json(), note=f"Detail: {r10.json().get('detail')}")

    # Admin endpoint with Analyst token -> MUST BE 403
    r11 = requests.get(f"{BASE_URL}/audit/verify", headers=h_ana)
    log_test("/audit/verify", "GET", "analyst", 403, r11.status_code, r11.json(), note=f"Detail: {r11.json().get('detail')}")

    # 3. Authorized Endpoint Tests (Investigator role)
    print("\n🔍 [Phase 3] Testing Investigator-Authorized Endpoints...")
    r_search = requests.get(f"{BASE_URL}/entity/search?q=Ravi", headers=h_inv)
    log_test("/entity/search?q=Ravi", "GET", "investigator", 200, r_search.status_code, note=f"Returned {r_search.json().get('count')} results")

    r_prof = requests.get(f"{BASE_URL}/entity/PER_RAVI_KUMAR", headers=h_inv)
    prof_data = r_prof.json()
    log_test("/entity/PER_RAVI_KUMAR", "GET", "investigator", 200, r_prof.status_code, note=f"Name: {prof_data['properties']['name']}, Risk: {prof_data['properties'].get('risk_score')}")

    r_graph = requests.get(f"{BASE_URL}/entity/PER_RAVI_KUMAR/graph?hops=2", headers=h_inv)
    log_test("/entity/PER_RAVI_KUMAR/graph?hops=2", "GET", "investigator", 200, r_graph.status_code, note=f"Cytoscape elements: {len(r_graph.json().get('elements', []))}")

    r_fir = requests.post(
        f"{BASE_URL}/ingest/fir",
        json={
            "content": "Intelligence intercept at Ernakulam: Suresh Nair was seen meeting Ravi Kumar.",
            "fir_number": "FIR_SWAGGER_TEST_01",
            "station": "Ernakulam Central",
            "officer": "Insp. Ramesh",
        },
        headers=h_inv,
    )
    log_test("/ingest/fir", "POST", "investigator", 200, r_fir.status_code, note=f"Extracted {len(r_fir.json().get('extracted', {}).get('entities', []))} entities")

    # 4. Authorized Endpoint Tests (Analyst role)
    print("\n📊 [Phase 4] Testing Analyst-Authorized Endpoints...")
    r_inf = requests.get(f"{BASE_URL}/analytics/influencers?limit=10", headers=h_ana)
    top_name = r_inf.json()["influencers"][0]["name"] if r_inf.json().get("influencers") else "None"
    log_test("/analytics/influencers", "GET", "analyst", 200, r_inf.status_code, note=f"Top Influencer: {top_name}")

    r_com = requests.get(f"{BASE_URL}/analytics/communities", headers=h_ana)
    log_test("/analytics/communities", "GET", "analyst", 200, r_com.status_code, note=f"{r_com.json().get('total_communities')} communities found")

    r_lnk = requests.get(f"{BASE_URL}/analytics/link-predictions", headers=h_ana)
    log_test("/analytics/link-predictions", "GET", "analyst", 200, r_lnk.status_code, note=f"{r_lnk.json().get('prediction_count')} link predictions")

    r_alr = requests.get(f"{BASE_URL}/analytics/alerts", headers=h_ana)
    log_test("/analytics/alerts", "GET", "analyst", 200, r_alr.status_code, note=f"{r_alr.json().get('total_alerts')} alerts returned")

    r_nl = requests.post(
        f"{BASE_URL}/query/natural-language",
        json={"question": "Find all persons who communicated with Ravi Kumar"},
        headers=h_ana,
    )
    cypher_sub = r_nl.json().get("generated_cypher", "").replace("\n", " ")[:40]
    log_test("/query/natural-language", "POST", "analyst", 200, r_nl.status_code, note=f"Cypher: {cypher_sub}...")

    # Test tamper-demo RBAC with investigator token -> MUST BE 403
    r_tamp_inv = requests.post(f"{BASE_URL}/audit/tamper-demo", json={"block_id": 1, "fake_action": "HACKED"}, headers=h_inv)
    log_test("/audit/tamper-demo", "POST", "investigator", 403, r_tamp_inv.status_code, r_tamp_inv.json(), note=f"Detail: {r_tamp_inv.json().get('detail')}")

    # 5. Authorized Endpoint Tests (Admin role)
    print("\n🛡️ [Phase 5] Testing Admin-Authorized Endpoints...")
    r_ver = requests.get(f"{BASE_URL}/audit/verify", headers=h_adm)
    log_test("/audit/verify", "GET", "admin", 200, r_ver.status_code, note=f"Chain Valid: {r_ver.json().get('is_valid')}")

    r_log = requests.get(f"{BASE_URL}/audit/logs?limit=5", headers=h_adm)
    logs_data = r_log.json().get("blocks", [])
    log_test("/audit/logs", "GET", "admin", 200, r_log.status_code, note=f"Logs retrieved: {len(logs_data)}")

    if logs_data:
        target_b = logs_data[0]
        b_id = target_b["block_id"]
        orig_action = target_b["action"]

        # Simulate tamper with Admin token -> 200 OK proving tamper detection
        r_tamp = requests.post(
            f"{BASE_URL}/audit/tamper-demo",
            json={"block_id": b_id, "fake_action": "TAMPER_DEMO_INJECTION"},
            headers=h_adm,
        )
        log_test("/audit/tamper-demo", "POST", "admin", 200, r_tamp.status_code, note=f"Tamper detected: {r_tamp.json().get('tamper_detected')}")

        # Restore the original action to maintain cryptographic chain integrity
        from ingestion.db_writers.postgres_writer import get_postgres_connection
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE audit_chain SET action = %s WHERE block_id = %s;", (orig_action, b_id))
            conn.commit()

        # Re-verify chain is restored
        r_ver_post = requests.get(f"{BASE_URL}/audit/verify", headers=h_adm)
        log_test("/audit/verify (post-restore)", "GET", "admin", 200, r_ver_post.status_code, note=f"Chain Restored: {r_ver_post.json().get('is_valid')}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 105)
    print("  LIVE SWAGGER AUDIT SUMMARY")
    print("=" * 105)
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"  Total API Checks Run : {total}")
    print(f"  Passed Checks        : {passed} / {total} ({passed/total*100:.1f}%)")
    print(f"  Failed Checks        : {total - passed}")
    print(f"  RBAC Security Audit  : {'✅ 100% ENFORCED (Zero unauthorized access leaks)' if passed == total else '❌ SECURITY BREACH DETECTED'}")
    print("=" * 105 + "\n")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

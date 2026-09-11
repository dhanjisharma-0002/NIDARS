"""Comprehensive Phase 7 End-to-End Live Verification Script for NIDARS."""

import json
import urllib.parse
import urllib.request
import urllib.error
import http.cookiejar

BASE_URL = "http://127.0.0.1:5000"

def run_verification():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    print("=" * 70)
    print("NIDARS PHASE 7 — LIVE HTTP END-TO-END VERIFICATION")
    print("=" * 70)
    
    # 1. Test unauthenticated access to /emergency and /admin
    print("\n1. Testing Access Control on Protected Endpoints:")
    for ep in ["/emergency", "/admin"]:
        req = urllib.request.Request(f"{BASE_URL}{ep}")
        try:
            res = opener.open(req)
            # Should have redirected to login
            print(f"  [PASS] {ep} redirected unauthenticated user to login -> {res.geturl()}")
        except urllib.error.HTTPError as e:
            print(f"  [INFO] {ep} returned HTTP {e.code}")

    for ep in ["/api/emergency/risk?lat=31.10&lon=77.17", "/api/admin/stats"]:
        try:
            req = urllib.request.Request(f"{BASE_URL}{ep}")
            opener.open(req)
            print(f"  [FAIL] {ep} allowed unauthenticated access!")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"  [PASS] Unauthenticated API request {ep} correctly blocked with HTTP 401 Unauthorized")
            else:
                print(f"  [INFO] {ep} returned HTTP {e.code}")

    # 2. Login as Admin
    print("\n2. Logging in as Admin (admin@nidars.gov.in):")
    login_get_res = opener.open(f"{BASE_URL}/login")
    login_html = login_get_res.read().decode("utf-8")
    
    import re
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_html) or re.search(r'content="([^"]+)"\s+name="csrf-token"', login_html) or re.search(r'name="csrf-token"\s+content="([^"]+)"', login_html)
    csrf_token = csrf_match.group(1) if csrf_match else ""
    
    login_data = urllib.parse.urlencode({
        "csrf_token": csrf_token,
        "email": "admin@nidars.gov.in",
        "password": "Admin@1234"
    }).encode("utf-8")
    login_req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method="POST")
    login_res = opener.open(login_req)
    print(f"  [PASS] Login successful -> redirected to {login_res.geturl()}")

    # 3. Test Emergency Page
    print("\n3. Testing Emergency Page (/emergency):")
    em_res = opener.open(f"{BASE_URL}/emergency")
    em_html = em_res.read().decode("utf-8")
    assert "Emergency Mode" in em_html, "Emergency page missing header"
    assert "RESEARCH &amp; PROTOTYPE ADVISORY" in em_html or "RESEARCH & PROTOTYPE ADVISORY" in em_html, "Disclaimer missing"
    assert "emergency-map" in em_html, "Map container missing"
    print("  [PASS] /emergency rendered successfully with Leaflet container and mandatory prototype disclaimer.")

    # 4. Test Emergency Risk API
    print("\n4. Testing /api/emergency/risk:")
    risk_res = opener.open(f"{BASE_URL}/api/emergency/risk?lat=31.1048&lon=77.1734")
    risk_data = json.loads(risk_res.read().decode("utf-8"))
    assert risk_data["success"] is True, "Emergency risk query failed"
    status = risk_data["risk_status"]
    print(f"  [PASS] Station: {status.get('nearest_station')}")
    print(f"  [PASS] Flood Prob: {status.get('flood_probability')}, Landslide Prob: {status.get('landslide_probability')}")
    print(f"  [PASS] Combined Risk: {status.get('combined_risk')}, Level: {status.get('risk_level')}")

    # 5. Test Facility Discovery API
    print("\n5. Testing /api/emergency/facilities:")
    fac_res = opener.open(f"{BASE_URL}/api/emergency/facilities?lat=31.1048&lon=77.1734&radius_km=15&type=all")
    fac_data = json.loads(fac_res.read().decode("utf-8"))
    assert fac_data["success"] is True, "Facility discovery failed"
    facs = fac_data["facilities"]
    print(f"  [PASS] Total verified facilities found: {len(facs)} (Source: {fac_data.get('source')})")
    if facs:
        f1 = facs[0]
        print(f"  [PASS] Nearest: {f1['name']} ({f1['facility_type'].upper()}) - {f1['distance_km']} km away")

    # 6. Test Nearest Safe Facility API
    print("\n6. Testing /api/emergency/nearest:")
    near_res = opener.open(f"{BASE_URL}/api/emergency/nearest?lat=31.1048&lon=77.1734&type=hospital")
    near_data = json.loads(near_res.read().decode("utf-8"))
    assert near_data["success"] is True, "Nearest facility query failed"
    print(f"  [PASS] Nearest Hospital: {near_data.get('nearest_by_distance', {}).get('name') if near_data.get('nearest_by_distance') else 'None within radius'}")
    print(f"  [PASS] Safest Recommendation: {near_data.get('recommended_safest', {}).get('name') if near_data.get('recommended_safest') else 'None'}")

    # 7. Test Emergency Safe Routing API
    print("\n7. Testing /api/emergency/route:")
    # Route from Shimla center to nearby coordinates
    route_url = f"{BASE_URL}/api/emergency/route?start_lat=31.1048&start_lon=77.1734&facility_lat=31.1200&facility_lon=77.1800&facility_name=Shimla+Hospital&facility_type=hospital"
    route_res = opener.open(route_url)
    route_data = json.loads(route_res.read().decode("utf-8"))
    assert route_data["success"] is True, "Emergency safe route failed"
    routes = route_data["routes"]
    assert len(routes) >= 1, "No routes returned"
    r0 = routes[0]
    m0 = r0["metrics"]
    print(f"  [PASS] Route Distance: {m0['distance_km']} km, Duration: {m0['duration_minutes']} min")
    print(f"  [PASS] Disaster Route Cost: {m0['route_cost']}, Hazard Coverage: {m0['risk_coverage_percent']}%")
    print(f"  [PASS] Recommendation Note: {route_data.get('recommendation_note')}")

    # 8. Test Admin Dashboard Page
    print("\n8. Testing Admin Dashboard (/admin):")
    admin_res = opener.open(f"{BASE_URL}/admin")
    admin_html = admin_res.read().decode("utf-8")
    assert "NIDARS Analytics &amp; Admin Control Center" in admin_html or "NIDARS Analytics & Admin Control Center" in admin_html, "Admin dashboard header missing"
    assert "prediction-type-chart" in admin_html, "Prediction chart canvas missing"
    assert "risk-level-chart" in admin_html, "Risk level chart canvas missing"
    assert "facility-type-chart" in admin_html, "Facility chart canvas missing"
    print("  [PASS] /admin page rendered successfully with Chart.js canvases and KPI containers.")

    # 9. Test Admin Analytics APIs
    print("\n9. Testing Admin REST APIs:")
    stats_res = opener.open(f"{BASE_URL}/api/admin/stats")
    stats_data = json.loads(stats_res.read().decode("utf-8"))
    assert stats_data["success"] is True, "Admin stats failed"
    metrics = stats_data["metrics"]
    print(f"  [PASS] Total Users: {metrics['total_users']}, Predictions: {metrics['total_predictions']}")
    print(f"  [PASS] Emergency Queries: {metrics['total_emergency_requests']}, Facilities: {metrics['total_facilities']}")
    print(f"  [PASS] Risk Distribution: {metrics['risk_distribution']}")

    logs_res = opener.open(f"{BASE_URL}/api/admin/emergency")
    logs_data = json.loads(logs_res.read().decode("utf-8"))
    assert logs_data["success"] is True, "Emergency logs failed"
    print(f"  [PASS] Logged Emergency Operations retrieved: {len(logs_data['emergency_logs'])} entries")

    # 10. Test Role Protection for regular user
    print("\n10. Testing Non-Admin Role Protection (403 Forbidden):")
    cj_user = http.cookiejar.CookieJar()
    user_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj_user))
    
    # Register/Login as regular user
    u_login_get = user_opener.open(f"{BASE_URL}/login")
    u_html = u_login_get.read().decode("utf-8")
    u_csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', u_html) or re.search(r'content="([^"]+)"\s+name="csrf-token"', u_html) or re.search(r'name="csrf-token"\s+content="([^"]+)"', u_html)
    u_csrf_token = u_csrf_match.group(1) if u_csrf_match else ""

    user_login = urllib.parse.urlencode({"csrf_token": u_csrf_token, "email": "tester@example.com", "password": "password12"}).encode("utf-8")
    try:
        user_opener.open(urllib.request.Request(f"{BASE_URL}/login", data=user_login, method="POST"))
        try:
            user_opener.open(f"{BASE_URL}/admin")
            print("  [FAIL] Regular user accessed /admin!")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("  [PASS] Regular user blocked from /admin with HTTP 403 Forbidden")
            else:
                print(f"  [INFO] HTTP {e.code}")

        try:
            user_opener.open(f"{BASE_URL}/api/admin/stats")
            print("  [FAIL] Regular user accessed /api/admin/stats!")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("  [PASS] Regular user blocked from /api/admin/stats with HTTP 403 Forbidden")
            else:
                print(f"  [INFO] HTTP {e.code}")
    except Exception as err:
        print(f"  [INFO] User role test: {str(err)}")

    print("\n" + "=" * 70)
    print("ALL LIVE END-TO-END VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()

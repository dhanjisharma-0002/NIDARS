"""Measure response times for NIDARS key endpoints."""

import http.cookiejar
import json
import time
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:5000"

def run_bench():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # Login
    login_get = opener.open(f"{BASE_URL}/login")
    login_html = login_get.read().decode("utf-8")
    import re
    m = re.search(r'id="csrf_token"\s+name="csrf_token"\s+type="hidden"\s+value="([^"]+)"', login_html) or re.search(r'name="csrf_token"\s+[^>]*value="([^"]+)"', login_html) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', login_html)
    token = m.group(1) if m else ""
    data = urllib.parse.urlencode({"csrf_token": token, "email": "admin@nidars.gov.in", "password": "Admin@1234"}).encode("utf-8")
    opener.open(urllib.request.Request(f"{BASE_URL}/login", data=data, method="POST"))

    print("=" * 60)
    print("NIDARS LOCAL ENDPOINT RESPONSE TIME BENCHMARK")
    print("=" * 60)

    endpoints = [
        ("GET /api/health", f"{BASE_URL}/api/health", None),
        ("GET /api/gis/risk", f"{BASE_URL}/api/gis/risk?hazard=combined", None),
        (
            "POST /api/predict/flood",
            f"{BASE_URL}/api/predict/flood",
            {
                "rainfall_24h": 120.0,
                "rainfall_72h": 210.0,
                "rainfall_7d": 350.0,
                "temperature": 26.0,
                "wind_speed": 4.5,
                "air_pressure": 1008.2,
                "elevation": 450.0,
                "latitude": 28.6139,
                "longitude": 77.2090,
            }
        ),
        ("GET /api/emergency/risk", f"{BASE_URL}/api/emergency/risk?lat=31.1048&lon=77.1734", None),
        ("GET /api/admin/stats", f"{BASE_URL}/api/admin/stats", None),
    ]

    for name, url, payload in endpoints:
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            if payload:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-CSRFToken": token}
                )
            else:
                req = urllib.request.Request(url)
            res = opener.open(req)
            _ = res.read()
            dt = (time.perf_counter() - t0) * 1000
            times.append(dt)
        avg_t = sum(times) / len(times)
        min_t = min(times)
        print(f"{name:30s} | Avg: {avg_t:6.2f} ms | Min: {min_t:6.2f} ms (HTTP {res.status})")

    print("=" * 60)

if __name__ == "__main__":
    run_bench()

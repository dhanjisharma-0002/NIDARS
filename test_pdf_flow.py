"""Comprehensive PDF Generation & Prediction History Flow Verification Test."""
import io
import json
from app import create_app
from extensions import db
from models.prediction import PredictionHistory

app = create_app()
client = app.test_client()

def test_full_flow():
    print("==================================================")
    print("Testing NIDARS Prediction History & PDF Flow...")
    print("==================================================")

    # 1. Test Invalid Prediction ID (e.g. 999999 or 2 if not in db)
    res_inv = client.get("/api/reports/disaster?prediction_id=999999")
    print(f"1. Non-existent ID 999999 status: {res_inv.status_code}")
    assert res_inv.status_code == 404, f"Expected 404, got {res_inv.status_code}"
    inv_data = json.loads(res_inv.data)
    print(f"   Response JSON: {inv_data}")
    assert inv_data["success"] is False
    assert "Prediction record was not found" in inv_data["message"]
    print("   [PASS] Non-existent ID returns 404 with expected JSON.")

    # 2. Create Real Flood Prediction
    flood_payload = {
        "latitude": 30.0668,
        "longitude": 79.0193,
        "rainfall_24h": 95.5,
        "rainfall_72h": 180.2,
        "rainfall_7d": 240.0,
        "elevation": 550.0,
        "temperature": 24.5,
        "humidity": 88.0,
        "soil_moisture": 78.0,
        "water_level": 4.8,
        "river_discharge": 1100.0,
        "flow_velocity": 2.4,
        "vegetation_cover": 0.35,
        "urban_density": 0.45,
        "drainage_density": 0.40,
        "upstream_precipitation": 120.0,
        "reservoir_level": 75.0,
        "wind_speed": 6.2,
        "air_pressure": 1008.0,
        "location_name": "Rudraprayag River Basin"
    }
    res_flood = client.post("/api/predict/flood", json=flood_payload)
    print(f"\n2. Flood Prediction status: {res_flood.status_code}")
    assert res_flood.status_code == 200, f"Expected 200, got {res_flood.status_code}"
    flood_data = json.loads(res_flood.data)
    flood_pred_id = flood_data.get("prediction_id") or flood_data.get("id")
    print(f"   Generated Prediction ID: {flood_pred_id}")
    print(f"   Risk Level: {flood_data.get('risk_level')}, Probability: {flood_data.get('probability')}")
    assert flood_pred_id is not None, "Flood prediction must return a real prediction_id"
    print("   [PASS] Flood prediction saved to database and returned valid prediction_id.")

    # 3. Download PDF using that prediction_id
    res_pdf = client.get(f"/api/reports/disaster?prediction_id={flood_pred_id}")
    print(f"\n3. PDF Report Request for ID #{flood_pred_id} status: {res_pdf.status_code}")
    assert res_pdf.status_code == 200, f"Expected 200, got {res_pdf.status_code}"
    assert "application/pdf" in res_pdf.content_type, f"Expected application/pdf, got {res_pdf.content_type}"
    assert res_pdf.data.startswith(b"%PDF-"), f"Expected %PDF- header, got: {res_pdf.data[:10]}"
    print(f"   PDF Size: {len(res_pdf.data)} bytes")
    print(f"   Content-Disposition: {res_pdf.headers.get('Content-Disposition')}")
    print("   [PASS] PDF successfully generated and returned valid %PDF- binary payload.")

    # 4. Create Real Landslide Prediction
    landslide_payload = {
        "latitude": 31.1048,
        "longitude": 77.1734,
        "rainfall_24h": 120.0,
        "rainfall_72h": 220.0,
        "rainfall_7d": 310.0,
        "temperature": 18.5,
        "wind_speed": 12.0,
        "air_pressure": 1005.0,
        "elevation": 2200.0,
        "location_name": "Shimla Slope Corridor"
    }
    res_landslide = client.post("/api/predict/landslide", json=landslide_payload)
    print(f"\n4. Landslide Prediction status: {res_landslide.status_code}")
    assert res_landslide.status_code == 200, f"Expected 200, got {res_landslide.status_code}"
    landslide_data = json.loads(res_landslide.data)
    landslide_pred_id = landslide_data.get("prediction_id") or landslide_data.get("id")
    print(f"   Generated Prediction ID: {landslide_pred_id}")
    print(f"   Risk Level: {landslide_data.get('risk_level')}, Probability: {landslide_data.get('probability')}")
    assert landslide_pred_id is not None, "Landslide prediction must return a real prediction_id"
    print("   [PASS] Landslide prediction saved to database and returned valid prediction_id.")

    # 5. Download PDF for Landslide
    res_landslide_pdf = client.get(f"/api/reports/disaster?prediction_id={landslide_pred_id}")
    print(f"\n5. PDF Report Request for Landslide ID #{landslide_pred_id} status: {res_landslide_pdf.status_code}")
    assert res_landslide_pdf.status_code == 200
    assert "application/pdf" in res_landslide_pdf.content_type
    assert res_landslide_pdf.data.startswith(b"%PDF-")
    print(f"   PDF Size: {len(res_landslide_pdf.data)} bytes")
    print("   [PASS] Landslide PDF generated successfully.")

    # 6. Direct query param PDF generation
    res_direct_pdf = client.get("/api/reports/disaster?location_name=Dehradun+Valley&latitude=30.3165&longitude=78.0322&rainfall_24h=75.0&elevation=640")
    print(f"\n6. Direct Param PDF status: {res_direct_pdf.status_code}")
    assert res_direct_pdf.status_code == 200
    assert "application/pdf" in res_direct_pdf.content_type
    assert res_direct_pdf.data.startswith(b"%PDF-")
    print(f"   PDF Size: {len(res_direct_pdf.data)} bytes")
    print("   [PASS] Direct parameters PDF generated successfully.")

    # 7. Recent Predictions API
    res_recent = client.get("/api/predictions/recent")
    print(f"\n7. Recent Predictions API status: {res_recent.status_code}")
    assert res_recent.status_code == 200
    recent_data = json.loads(res_recent.data)
    preds = recent_data.get("predictions", [])
    print(f"   Retrieved {len(preds)} recent predictions from database.")
    assert len(preds) >= 2, "Should contain the recently saved predictions"
    for p in preds[:2]:
        print(f"   - ID: {p.get('id')}, Type: {p.get('prediction_type')}, Risk: {p.get('risk_level')}")
    print("   [PASS] Recent predictions API returns authentic persisted database records.")

    # 8. Explain API
    res_explain = client.get(f"/api/prediction/{flood_pred_id}/explain")
    print(f"\n8. Explain API for ID #{flood_pred_id} status: {res_explain.status_code}")
    assert res_explain.status_code == 200
    explain_data = json.loads(res_explain.data)
    assert explain_data["success"] is True
    assert "explainability" in explain_data
    print(f"   Top factor: {explain_data['explainability'].get('top_factors', [{}])[0]}")
    print("   [PASS] Explain API functions accurately for saved prediction records.")

    print("\n==================================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("==================================================")

if __name__ == "__main__":
    test_full_flow()

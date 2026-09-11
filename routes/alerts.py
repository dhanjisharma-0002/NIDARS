"""Early Warning and Advisory routes and APIs for NIDARS Phase 10."""

from datetime import datetime, timezone

from flask import jsonify, render_template, request

from extensions import csrf
from routes.main import api_bp, main_bp
from services.advisory_service import (
    DISCLAIMER_TEXT,
    generate_live_station_alerts,
    get_advisory_summary_stats,
    get_alert_by_id_or_code,
    sync_alerts_to_history,
)


@main_bp.route("/alerts")
def alerts_page():
    """Render the AI-Based Early Warning & Advisory System dashboard."""
    return render_template("alerts.html")


@api_bp.route("/alerts", methods=["GET"])
def api_get_alerts():
    """Query real-time hazard early warning alerts with flexible filtering.

    Query parameters:
      - hazard / hazard_type: 'flood', 'landslide', 'combined', 'all' (default: 'all')
      - state: 2-letter state code e.g. 'HP', 'JK', 'UP', 'BR'
      - district: district name substring
      - risk_level / level: 'CRITICAL', 'HIGH', 'MODERATE', 'LOW'
      - min_level: minimum severity filter e.g. 'MODERATE'
      - limit: maximum number of alerts to return (default: all)
    """
    hazard = request.args.get("hazard") or request.args.get("hazard_type") or "all"
    state = request.args.get("state")
    district = request.args.get("district")
    risk_level = request.args.get("risk_level") or request.args.get("level")
    min_level = request.args.get("min_level")
    limit_str = request.args.get("limit")

    limit = None
    if limit_str:
        try:
            limit = max(1, int(limit_str))
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Parameter 'limit' must be a positive integer.",
                "disclaimer": DISCLAIMER_TEXT,
            }), 400

    try:
        alerts = generate_live_station_alerts(
            hazard_type=hazard,
            state=state,
            district=district,
            min_risk_level=min_level,
            risk_level=risk_level,
            limit=limit,
        )
        return jsonify({
            "success": True,
            "count": len(alerts),
            "filters": {
                "hazard": hazard,
                "state": state,
                "district": district,
                "risk_level": risk_level,
                "min_level": min_level,
                "limit": limit,
            },
            "alerts": alerts,
            "disclaimer": DISCLAIMER_TEXT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"Failed to generate advisory alerts: {str(exc)}",
            "disclaimer": DISCLAIMER_TEXT,
        }), 500


@api_bp.route("/alerts/summary", methods=["GET"])
def api_get_alerts_summary():
    """Retrieve aggregate early warning statistics and risk distributions."""
    try:
        summary = get_advisory_summary_stats()
        return jsonify({
            "success": True,
            "summary": summary,
            "disclaimer": DISCLAIMER_TEXT,
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"Failed to calculate advisory summary: {str(exc)}",
            "disclaimer": DISCLAIMER_TEXT,
        }), 500


@api_bp.route("/alerts/<alert_id>", methods=["GET"])
def api_get_alert_detail(alert_id):
    """Retrieve detailed telemetry, advisory text, and precautions for a specific alert."""
    alert = get_alert_by_id_or_code(alert_id)
    if not alert:
        return jsonify({
            "success": False,
            "error": f"Alert with ID or station code '{alert_id}' was not found.",
            "disclaimer": DISCLAIMER_TEXT,
        }), 404

    return jsonify({
        "success": True,
        "alert": alert,
        "disclaimer": DISCLAIMER_TEXT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


@api_bp.route("/alerts/sync", methods=["POST"])
@csrf.exempt
def api_sync_alerts():
    """Snapshot current high-risk alerts into database history."""
    try:
        saved = sync_alerts_to_history(min_level="MODERATE")
        return jsonify({
            "success": True,
            "saved_count": saved,
            "message": f"Successfully synchronized {saved} active advisory events to history.",
            "disclaimer": DISCLAIMER_TEXT,
        })
    except Exception as exc:
        return jsonify({
            "success": False,
            "error": f"Failed to sync advisory events: {str(exc)}",
            "disclaimer": DISCLAIMER_TEXT,
        }), 500

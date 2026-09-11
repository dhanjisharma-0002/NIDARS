"""Admin Dashboard, Analytics, and System Management routes for NIDARS."""

from __future__ import annotations

from functools import wraps
from typing import Any, Dict

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from models.emergency_facility import EmergencyFacility
from models.emergency_request import EmergencyRequest
from models.location import Location
from models.prediction import PredictionHistory
from models.user import ROLE_ADMIN, User
from routes.main import api_bp, main_bp


def admin_required(fn):
    """Decorator to restrict routes to users with the 'admin' role."""
    @wraps(fn)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "errors": ["Authentication required."]}), 401
            flash("Please log in with administrator credentials.", "warning")
            return redirect(url_for("auth.login", next=request.path))

        if not current_user.is_admin():
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "errors": ["Administrator privileges required."]}), 403
            flash("Access denied. Administrator privileges required.", "danger")
            return render_template("errors/403.html"), 403

        return fn(*args, **kwargs)

    return decorated_view


@main_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard_view():
    """Render the main Admin Dashboard page with analytics cards and charts."""
    return render_template("admin/dashboard.html")


@api_bp.route("/admin/stats", methods=["GET"])
@login_required
@admin_required
def get_admin_stats():
    """Retrieve comprehensive system metrics and prediction statistics from MySQL."""
    try:
        total_users = User.query.count()
        total_predictions = PredictionHistory.query.count()
        flood_predictions = PredictionHistory.query.filter_by(prediction_type="flood").count()
        landslide_predictions = PredictionHistory.query.filter_by(prediction_type="landslide").count()

        total_emergency_requests = EmergencyRequest.query.count()
        total_facilities = EmergencyFacility.query.filter_by(is_active=True).count()
        hospital_count = EmergencyFacility.query.filter_by(facility_type="hospital", is_active=True).count()
        police_count = EmergencyFacility.query.filter_by(facility_type="police", is_active=True).count()
        shelter_count = EmergencyFacility.query.filter_by(facility_type="shelter", is_active=True).count()

        # Risk distribution analytics across logged predictions
        high_risk_count = 0
        critical_risk_count = 0
        moderate_risk_count = 0
        low_risk_count = 0

        recent_preds = PredictionHistory.query.order_by(PredictionHistory.created_at.desc()).limit(500).all()
        for p in recent_preds:
            if isinstance(p.result_json, dict):
                lvl = str(p.result_json.get("risk_level", "")).upper()
                if lvl == "CRITICAL":
                    critical_risk_count += 1
                elif lvl == "HIGH":
                    high_risk_count += 1
                elif lvl == "MODERATE":
                    moderate_risk_count += 1
                elif lvl == "LOW":
                    low_risk_count += 1

        # Emergency request types breakdown
        req_types = db.session.query(
            EmergencyRequest.request_type, func.count(EmergencyRequest.id)
        ).group_by(EmergencyRequest.request_type).all()
        emergency_by_type = {rt[0]: rt[1] for rt in req_types}

        return jsonify({
            "success": True,
            "metrics": {
                "total_users": total_users,
                "total_predictions": total_predictions,
                "flood_predictions": flood_predictions,
                "landslide_predictions": landslide_predictions,
                "total_emergency_requests": total_emergency_requests,
                "total_facilities": total_facilities,
                "facilities_by_type": {
                    "hospitals": hospital_count,
                    "police": police_count,
                    "shelters": shelter_count,
                },
                "risk_distribution": {
                    "LOW": low_risk_count,
                    "MODERATE": moderate_risk_count,
                    "HIGH": high_risk_count,
                    "CRITICAL": critical_risk_count,
                },
                "emergency_request_breakdown": emergency_by_type,
            },
        }), 200
    except Exception as err:
        current_app.logger.exception("Failed to retrieve admin analytics stats.")
        return jsonify({"success": False, "errors": [f"Database error: {str(err)}"]}), 500


@api_bp.route("/admin/predictions", methods=["GET"])
@login_required
@admin_required
def get_admin_predictions():
    """Retrieve recent prediction history records without exposing sensitive user hashes."""
    try:
        limit = min(100, max(1, int(request.args.get("limit", 20))))
        records = PredictionHistory.query.order_by(PredictionHistory.created_at.desc()).limit(limit).all()

        results = []
        for r in records:
            u_email = r.user.email if r.user else "Anonymous"
            u_name = r.user.name if r.user else "Guest"
            results.append({
                "id": r.id,
                "user_name": u_name,
                "user_email": u_email,
                "prediction_type": r.prediction_type,
                "status": r.status,
                "result": r.result_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return jsonify({
            "success": True,
            "total": len(results),
            "predictions": results,
        }), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [str(err)]}), 500


@api_bp.route("/admin/emergency", methods=["GET"])
@login_required
@admin_required
def get_admin_emergency_logs():
    """Retrieve recent emergency mode queries and operations."""
    try:
        limit = min(100, max(1, int(request.args.get("limit", 20))))
        logs = EmergencyRequest.query.order_by(EmergencyRequest.created_at.desc()).limit(limit).all()

        results = []
        for item in logs:
            results.append({
                "id": item.id,
                "user_id": item.user_id,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "request_type": item.request_type,
                "facility_type": item.facility_type,
                "risk_level": item.risk_level,
                "flood_probability": item.flood_probability,
                "landslide_probability": item.landslide_probability,
                "result_summary": item.result_summary,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            })

        return jsonify({
            "success": True,
            "total": len(results),
            "emergency_logs": results,
        }), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [str(err)]}), 500


@api_bp.route("/admin/facilities", methods=["GET"])
@login_required
@admin_required
def get_admin_facilities():
    """Retrieve verified cached emergency facilities."""
    try:
        f_type = request.args.get("type")
        query = EmergencyFacility.query.filter_by(is_active=True)
        if f_type and f_type in ("hospital", "police", "shelter"):
            query = query.filter_by(facility_type=f_type)

        records = query.order_by(EmergencyFacility.id.desc()).limit(100).all()
        return jsonify({
            "success": True,
            "total": len(records),
            "facilities": [r.to_dict() for r in records],
        }), 200
    except Exception as err:
        return jsonify({"success": False, "errors": [str(err)]}), 500


# =========================================================================
# Phase 15: Citizen Incident Management
# =========================================================================

@main_bp.route("/admin/incidents")
@login_required
@admin_required
def admin_incidents_view():
    """Render the Admin Incident Management console UI."""
    from models.incident import VALID_INCIDENT_TYPES, VALID_SEVERITIES, VALID_STATUSES
    return render_template(
        "admin/incidents.html",
        incident_types=VALID_INCIDENT_TYPES,
        severities=VALID_SEVERITIES,
        statuses=VALID_STATUSES,
    )


@api_bp.route("/admin/incidents", methods=["GET"])
@login_required
@admin_required
def get_admin_incidents():
    """Retrieve filtered incident reports for admin triage."""
    from services.incident_service import get_admin_incident_reports

    inc_type = request.args.get("incident_type") or request.args.get("type")
    status = request.args.get("status")
    severity = request.args.get("severity")
    is_verified_raw = request.args.get("verified") or request.args.get("is_verified")
    is_verified = None
    if is_verified_raw is not None and is_verified_raw.strip() != "":
        is_verified = is_verified_raw.lower() in ("1", "true", "yes")

    search = request.args.get("q") or request.args.get("search")
    limit = min(200, max(1, request.args.get("limit", 100, type=int)))
    reports = get_admin_incident_reports(
        incident_type=inc_type,
        status=status,
        severity=severity,
        is_verified=is_verified,
        search=search,
        limit=limit,
    )
    return jsonify({
        "success": True,
        "total": len(reports),
        "incidents": reports,
    }), 200


@api_bp.route("/admin/incidents/<int:incident_id>/status", methods=["PATCH"])
@login_required
@admin_required
def patch_incident_status(incident_id):
    """Admin update incident status, verification flag, and notes."""
    from services.incident_service import update_incident_status

    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    is_verified = payload.get("is_verified")
    admin_notes = payload.get("admin_notes")

    result = update_incident_status(
        incident_id=incident_id,
        status=status,
        is_verified=is_verified,
        admin_notes=admin_notes,
    )
    http_status = result.pop("http_status", 200 if result.get("success") else 400)
    return jsonify(result), http_status


@api_bp.route("/admin/incidents/<int:incident_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_incident(incident_id):
    """Admin delete inappropriate/spam report."""
    from services.incident_service import delete_incident_report

    result = delete_incident_report(incident_id)
    http_status = result.pop("http_status", 200 if result.get("success") else 400)
    return jsonify(result), http_status


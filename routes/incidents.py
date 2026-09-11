"""Incident reporting web routes and REST API endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from models.incident import VALID_INCIDENT_TYPES, VALID_SEVERITIES
from routes.main import api_bp, main_bp
from services.incident_service import (
    create_incident_report,
    get_incidents_geojson,
    get_user_incident_reports,
)


@main_bp.route("/report-incident")
@login_required
def report_incident_view():
    """Render the Citizen Incident Reporting form UI."""
    return render_template(
        "report_incident.html",
        incident_types=VALID_INCIDENT_TYPES,
        severities=VALID_SEVERITIES,
    )


@main_bp.route("/my-reports")
@login_required
def my_reports_view():
    """Render the user's submitted disaster incident history UI."""
    return render_template("my_reports.html")


@api_bp.route("/incidents", methods=["POST"])
@login_required
def submit_incident():
    """Submit a new citizen disaster incident report."""
    if request.is_json:
        form_data = request.get_json(silent=True) or {}
        file = None
    else:
        form_data = request.form.to_dict()
        file = request.files.get("photo")

    result = create_incident_report(
        user_id=current_user.id,
        form_data=form_data,
        file=file,
    )
    status = result.pop("http_status", 201 if result.get("success") else 400)
    return jsonify(result), status


@api_bp.route("/incidents/my", methods=["GET"])
@login_required
def get_my_incidents():
    """Retrieve all reports submitted by the logged-in user."""
    limit = min(100, max(1, request.args.get("limit", 50, type=int)))
    reports = get_user_incident_reports(user_id=current_user.id, limit=limit)
    return jsonify({
        "success": True,
        "count": len(reports),
        "total": len(reports),
        "incidents": reports,
    })


@api_bp.route("/gis/incidents", methods=["GET"])
def get_gis_incidents():
    """Public GeoJSON endpoint providing citizen incidents for GIS Map layer.

    Distinguishes verified vs unverified reports and does not expose sensitive user data.
    """
    incident_type = request.args.get("type")
    verified_only = request.args.get("verified_only", "false").lower() in ("1", "true", "yes")
    status = request.args.get("status")

    geojson_data = get_incidents_geojson(
        incident_type=incident_type,
        verified_only=verified_only,
        status=status,
    )
    return jsonify(geojson_data), 200


@api_bp.route("/incidents/types", methods=["GET"])
def get_incident_types():
    """Get canonical incident types and severity choices."""
    return jsonify({
        "success": True,
        "incident_types": list(VALID_INCIDENT_TYPES),
        "severities": list(VALID_SEVERITIES),
        "severity_levels": list(VALID_SEVERITIES),
    }), 200

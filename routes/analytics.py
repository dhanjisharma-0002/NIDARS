"""Advanced Analytics web view and REST API routes for NIDARS."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import current_user

from routes.main import api_bp, main_bp
from services.analytics_service import (
    export_analytics_csv,
    get_analytics_overview,
    get_available_districts_list,
    get_risk_rankings,
    get_temporal_trends,
)


@main_bp.route("/analytics")
def analytics_view():
    """Render the Advanced Analytics Disaster Intelligence Command Dashboard."""
    districts = get_available_districts_list("ALL")
    return render_template("analytics.html", districts=districts)


@api_bp.route("/analytics/overview", methods=["GET"])
def api_analytics_overview():
    """Get high-level disaster analytics KPIs, risk distributions, and state metrics."""
    state = request.args.get("state", "ALL")
    district = request.args.get("district", "ALL")
    hazard = request.args.get("hazard", "combined").lower()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    risk_level = request.args.get("risk_level", "ALL").upper()

    data = get_analytics_overview(
        state=state,
        district=district,
        hazard=hazard,
        start_date=start_date,
        end_date=end_date,
        risk_level=risk_level,
    )
    return jsonify(data), 200


@api_bp.route("/analytics/trends", methods=["GET"])
def api_analytics_trends():
    """Get monthly seasonality, multi-year patterns, and weather risk correlations."""
    state = request.args.get("state", "ALL")
    district = request.args.get("district", "ALL")
    hazard = request.args.get("hazard", "combined").lower()

    data = get_temporal_trends(
        state=state,
        district=district,
        hazard=hazard,
    )
    return jsonify(data), 200


@api_bp.route("/analytics/rankings", methods=["GET"])
def api_analytics_rankings():
    """Get calculated risk rankings for states, districts, and locations."""
    state = request.args.get("state", "ALL")
    district = request.args.get("district", "ALL")
    hazard = request.args.get("hazard", "combined").lower()
    limit = min(100, max(5, request.args.get("limit", 20, type=int)))

    data = get_risk_rankings(
        state=state,
        district=district,
        hazard=hazard,
        limit=limit,
    )
    return jsonify(data), 200


@api_bp.route("/analytics/districts", methods=["GET"])
def api_analytics_districts():
    """Get dynamic list of authentic districts for selected state."""
    state = request.args.get("state", "ALL")
    districts = get_available_districts_list(state=state)
    return jsonify({
        "success": True,
        "state": state,
        "districts": districts,
    }), 200


@api_bp.route("/analytics/export/csv", methods=["GET"])
def api_analytics_export_csv():
    """Stream sanitized CSV analytical report for offline inspection."""
    dataset_type = request.args.get("type", "rankings").lower()
    state = request.args.get("state", "ALL")
    district = request.args.get("district", "ALL")
    hazard = request.args.get("hazard", "combined").lower()

    csv_content = export_analytics_csv(
        dataset_type=dataset_type,
        state=state,
        district=district,
        hazard=hazard,
    )

    filename = f"nidars_analytics_{dataset_type}_{hazard}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

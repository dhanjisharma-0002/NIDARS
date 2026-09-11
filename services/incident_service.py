"""Application service for Phase 15 Citizen Incident Reporting.

Handles validation, secure image uploads, database persistence,
GeoJSON map formatting, and administrative lifecycle triage.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from extensions import db
from models.incident import (
    STATUS_REPORTED,
    STATUS_RESOLVED,
    STATUS_UNDER_REVIEW,
    STATUS_VERIFIED,
    VALID_INCIDENT_TYPES,
    VALID_SEVERITIES,
    VALID_STATUSES,
    IncidentReport,
)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Magic header signatures for common image formats
IMAGE_MAGIC_HEADERS = (
    b"\xff\xd8\xff",  # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"RIFF",  # WEBP (RIFF....WEBP)
    b"GIF87a",  # GIF
    b"GIF89a",  # GIF
)


def _validate_image_file(file: Optional[FileStorage]) -> Tuple[Optional[str], List[str]]:
    """Validate uploaded photo file for allowed extensions, size, and magic bytes."""
    if not file or not file.filename:
        return None, []

    errors = []
    filename = secure_filename(file.filename)
    if not filename:
        return None, ["Invalid image filename."]

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return None, [
            f"Unsupported file type '{ext}'. Allowed image types: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        ]

    # Check file content header
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)

    if size > MAX_IMAGE_SIZE_BYTES:
        return None, [f"Image file exceeds the 5 MB maximum limit ({size / (1024*1024):.1f} MB)."]

    header = file.read(12)
    file.seek(0)

    is_valid_image = any(header.startswith(sig) for sig in IMAGE_MAGIC_HEADERS) or (
        b"WEBP" in header
    )
    if not is_valid_image:
        return None, ["Invalid image file header. Uploaded file does not appear to be a valid image."]

    # Generate unique filename to avoid collision or overwrite
    unique_name = f"incident_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}.{ext}"
    return unique_name, []


def validate_incident_payload(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Validate citizen incident submission fields."""
    errors = []
    cleaned = {}

    # Location Name
    loc = str(data.get("location_name") or data.get("location") or "").strip()
    if not loc:
        errors.append("Location name or description is required.")
    elif len(loc) > 255:
        errors.append("Location name cannot exceed 255 characters.")
    else:
        cleaned["location_name"] = loc

    # Latitude
    lat_val = data.get("latitude")
    if lat_val is None or str(lat_val).strip() == "":
        errors.append("Latitude is required.")
    else:
        try:
            lat = float(lat_val)
            if not (-90.0 <= lat <= 90.0):
                errors.append("Latitude must be a valid coordinate between -90.0 and 90.0.")
            else:
                cleaned["latitude"] = lat
        except (ValueError, TypeError):
            errors.append("Latitude must be a valid numeric coordinate.")

    # Longitude
    lon_val = data.get("longitude")
    if lon_val is None or str(lon_val).strip() == "":
        errors.append("Longitude is required.")
    else:
        try:
            lon = float(lon_val)
            if not (-180.0 <= lon <= 180.0):
                errors.append("Longitude must be a valid coordinate between -180.0 and 180.0.")
            else:
                cleaned["longitude"] = lon
        except (ValueError, TypeError):
            errors.append("Longitude must be a valid numeric coordinate.")

    # Incident Type
    inc_type = str(data.get("incident_type") or "").strip()
    matched_type = None
    for vt in VALID_INCIDENT_TYPES:
        if vt.lower() == inc_type.lower():
            matched_type = vt
            break

    if not matched_type:
        errors.append(
            f"Invalid incident type '{inc_type}'. Must be one of: {', '.join(VALID_INCIDENT_TYPES)}."
        )
    else:
        cleaned["incident_type"] = matched_type

    # Severity
    sev = str(data.get("severity") or "Moderate").strip()
    matched_sev = None
    for vs in VALID_SEVERITIES:
        if vs.lower() == sev.lower():
            matched_sev = vs
            break

    if not matched_sev:
        errors.append(
            f"Invalid severity '{sev}'. Must be one of: {', '.join(VALID_SEVERITIES)}."
        )
    else:
        cleaned["severity"] = matched_sev

    # Description
    desc = str(data.get("description") or "").strip()
    if not desc:
        errors.append("Description is required.")
    elif len(desc) < 5:
        errors.append("Description must be at least 5 characters long.")
    elif len(desc) > 5000:
        errors.append("Description cannot exceed 5000 characters.")
    else:
        cleaned["description"] = desc

    # Incident Date/Time
    date_val = data.get("incident_date") or data.get("datetime")
    if date_val:
        try:
            cleaned["incident_date"] = datetime.fromisoformat(str(date_val).replace("Z", "+00:00"))
        except Exception:
            cleaned["incident_date"] = datetime.now(timezone.utc)
    else:
        cleaned["incident_date"] = datetime.now(timezone.utc)

    return cleaned, errors


def create_incident_report(
    user_id: int,
    form_data: Dict[str, Any],
    file: Optional[FileStorage] = None,
) -> Dict[str, Any]:
    """Validate and persist a citizen disaster report."""
    cleaned, errors = validate_incident_payload(form_data)

    photo_filename = None
    if file and file.filename:
        photo_filename, file_errors = _validate_image_file(file)
        if file_errors:
            errors.extend(file_errors)

    if errors:
        return {
            "success": False,
            "error": "; ".join(errors),
            "errors": errors,
            "incident": None,
            "http_status": 400,
        }

    # Save photo file if uploaded
    if file and photo_filename:
        upload_dir = Path(current_app.config.get("INCIDENT_UPLOAD_DIR", current_app.root_path + "/static/uploads/incidents"))
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / photo_filename
        file.save(str(file_path))

    report = IncidentReport(
        user_id=user_id,
        location_name=cleaned["location_name"],
        latitude=cleaned["latitude"],
        longitude=cleaned["longitude"],
        incident_type=cleaned["incident_type"],
        severity=cleaned["severity"],
        description=cleaned["description"],
        photo_filename=photo_filename,
        status=STATUS_REPORTED,
        is_verified=False,
        incident_date=cleaned["incident_date"],
    )

    try:
        db.session.add(report)
        db.session.commit()
        db.session.refresh(report)
        return {
            "success": True,
            "message": "Incident report submitted successfully.",
            "incident": report.to_dict(),
            "http_status": 201,
        }
    except Exception as err:
        db.session.rollback()
        current_app.logger.exception("Failed to create incident report.")
        err_msg = f"Database error: {str(err)}"
        return {
            "success": False,
            "error": err_msg,
            "errors": [err_msg],
            "http_status": 500,
        }


def get_user_incident_reports(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieve incident reports submitted by a specific user."""
    reports = (
        IncidentReport.query.filter_by(user_id=user_id)
        .order_by(IncidentReport.created_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in reports]


def get_incidents_geojson(
    incident_type: Optional[str] = None,
    verified_only: bool = False,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate GeoJSON FeatureCollection of incident reports for GIS map display."""
    query = IncidentReport.query

    if verified_only:
        query = query.filter_by(is_verified=True)

    if incident_type and incident_type.lower() != "all":
        query = query.filter(db.func.lower(IncidentReport.incident_type) == incident_type.lower())

    if status and status.lower() != "all":
        query = query.filter(db.func.lower(IncidentReport.status) == status.lower())

    reports = query.order_by(IncidentReport.created_at.desc()).limit(200).all()

    features = [r.to_geojson_feature() for r in reports]
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total": len(features),
            "verified_count": sum(1 for f in features if f["properties"]["is_verified"]),
            "unverified_count": sum(1 for f in features if not f["properties"]["is_verified"]),
            "disclaimer": "User-reported incidents represent community observations and should not be interpreted as official government disaster advisories.",
        },
    }


def get_admin_incident_reports(
    incident_type: Optional[str] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    is_verified: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Retrieve filtered incident reports for administrative triage."""
    query = IncidentReport.query

    if incident_type and incident_type.lower() != "all":
        query = query.filter(db.func.lower(IncidentReport.incident_type) == incident_type.lower())

    if status and status.lower() != "all":
        query = query.filter(db.func.lower(IncidentReport.status) == status.lower())

    if severity and severity.lower() != "all":
        query = query.filter(db.func.lower(IncidentReport.severity) == severity.lower())

    if is_verified is not None:
        query = query.filter(IncidentReport.is_verified == is_verified)

    if search and search.strip():
        search_term = f"%{search.strip().lower()}%"
        query = query.filter(
            db.or_(
                db.func.lower(IncidentReport.location_name).like(search_term),
                db.func.lower(IncidentReport.description).like(search_term),
                db.func.lower(IncidentReport.incident_type).like(search_term),
            )
        )

    reports = query.order_by(IncidentReport.created_at.desc()).limit(limit).all()
    return [r.to_dict(include_admin_details=True) for r in reports]


def update_incident_status(
    incident_id: int,
    status: Optional[str] = None,
    is_verified: Optional[bool] = None,
    admin_notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin update of report status and verification."""
    report = db.session.get(IncidentReport, incident_id)
    if not report:
        err = "Incident report not found."
        return {"success": False, "error": err, "errors": [err], "http_status": 404}

    if status:
        matched_status = None
        for vs in VALID_STATUSES:
            if vs.lower() == status.strip().lower():
                matched_status = vs
                break
        if not matched_status:
            err = f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}."
            return {
                "success": False,
                "error": err,
                "errors": [err],
                "http_status": 400,
            }
        report.status = matched_status
        if matched_status == STATUS_VERIFIED:
            report.is_verified = True

    if is_verified is not None:
        report.is_verified = bool(is_verified)
        if report.is_verified and report.status == STATUS_REPORTED:
            report.status = STATUS_VERIFIED

    if admin_notes is not None:
        report.admin_notes = admin_notes.strip()

    report.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
        return {
            "success": True,
            "message": "Incident report updated successfully.",
            "incident": report.to_dict(include_admin_details=True),
            "http_status": 200,
        }
    except Exception as err:
        db.session.rollback()
        err_msg = f"Database error: {str(err)}"
        return {"success": False, "error": err_msg, "errors": [err_msg], "http_status": 500}


def delete_incident_report(incident_id: int) -> Dict[str, Any]:
    """Admin deletion of inappropriate or invalid report."""
    report = db.session.get(IncidentReport, incident_id)
    if not report:
        err = "Incident report not found."
        return {"success": False, "error": err, "errors": [err], "http_status": 404}

    # Remove photo file if exists
    if report.photo_filename:
        upload_dir = Path(current_app.config.get("INCIDENT_UPLOAD_DIR", current_app.root_path + "/static/uploads/incidents"))
        file_path = upload_dir / report.photo_filename
        if file_path.is_file():
            try:
                file_path.unlink()
            except Exception:
                pass

    try:
        db.session.delete(report)
        db.session.commit()
        return {
            "success": True,
            "message": f"Incident report #{incident_id} deleted successfully.",
            "http_status": 200,
        }
    except Exception as err:
        db.session.rollback()
        err_msg = f"Database error: {str(err)}"
        return {"success": False, "error": err_msg, "errors": [err_msg], "http_status": 500}

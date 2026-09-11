/**
 * NIDARS — Admin Incident Management Client Logic
 */
(function () {
    "use strict";

    var currentIncidentId = null;
    var cachedReports = [];

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function showAlert(msg, type) {
        var el = document.getElementById("admin-incident-alert");
        if (!el) return;
        el.innerHTML = `
            <div class="alert alert-${type || 'info'} alert-dismissible fade show" role="alert">
                <span>${msg}</span>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
    }

    function fetchAdminIncidents() {
        var type = document.getElementById("filter-type").value;
        var status = document.getElementById("filter-status").value;
        var severity = document.getElementById("filter-severity").value;
        var verified = document.getElementById("filter-verified").value;

        var params = new URLSearchParams();
        if (type && type !== "all") params.append("type", type);
        if (status && status !== "all") params.append("status", status);
        if (severity && severity !== "all") params.append("severity", severity);
        if (verified && verified !== "all") params.append("verified", verified);

        var tbody = document.getElementById("admin-incidents-tbody");
        var countBadge = document.getElementById("admin-reports-count");

        fetch("/api/admin/incidents?" + params.toString())
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to load admin queue");
                return res.json();
            })
            .then(function (data) {
                cachedReports = data.incidents || [];
                if (countBadge) countBadge.textContent = cachedReports.length + " Reports in Queue";

                if (cachedReports.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="9" class="text-center py-4 text-muted">
                                No incident reports matching the selected filters.
                            </td>
                        </tr>
                    `;
                    return;
                }

                var html = "";
                cachedReports.forEach(function (r) {
                    var sevClass = (r.severity || "moderate").toLowerCase();
                    var statusClass = (r.status || "reported").toLowerCase().replace(/\s+/g, "-");
                    var dateStr = r.created_at ? new Date(r.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' }) : "—";
                    var coords = `${r.latitude.toFixed(3)}°N, ${r.longitude.toFixed(3)}°E`;

                    html += `
                        <tr>
                            <td><strong class="text-muted">#${r.id}</strong></td>
                            <td><strong>⚠️ ${r.incident_type}</strong></td>
                            <td>
                                <div>${r.location_name}</div>
                                <span class="text-muted font-monospace small" style="font-size: 0.72rem;">${coords}</span>
                            </td>
                            <td><span class="risk-chip risk-${sevClass}">${r.severity}</span></td>
                            <td>
                                <div class="small fw-semibold text-white">${r.user_name}</div>
                                <span class="text-muted small" style="font-size: 0.72rem;">${r.user_email || ""}</span>
                            </td>
                            <td><span class="badge bg-secondary status-badge status-${statusClass}">${r.status}</span></td>
                            <td>
                                ${r.is_verified
                                    ? '<span class="badge bg-success bg-opacity-25 text-success">🛡️ Verified</span>'
                                    : '<span class="badge bg-warning bg-opacity-25 text-warning">⏳ Unverified</span>'
                                }
                            </td>
                            <td class="text-muted small">${dateStr}</td>
                            <td class="text-end">
                                <button class="btn btn-xs btn-outline-info btn-review" data-id="${r.id}">
                                    🔍 Triage
                                </button>
                            </td>
                        </tr>
                    `;
                });

                tbody.innerHTML = html;

                // Bind triage button handlers
                tbody.querySelectorAll(".btn-review").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        var id = parseInt(this.getAttribute("data-id"), 10);
                        openReviewModal(id);
                    });
                });
            })
            .catch(function (err) {
                console.warn("Failed to load admin incidents:", err);
                if (tbody) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="9" class="text-center py-4 text-danger">
                                Failed to fetch queue from server.
                            </td>
                        </tr>
                    `;
                }
            });
    }

    function openReviewModal(id) {
        currentIncidentId = id;
        var r = cachedReports.find(function (item) { return item.id === id; });
        if (!r) return;

        document.getElementById("modal-incident-id").textContent = r.id;
        document.getElementById("modal-type").textContent = r.incident_type;
        var sevElem = document.getElementById("modal-sev");
        if (sevElem) {
            sevElem.textContent = r.severity;
            sevElem.className = "risk-chip risk-" + (r.severity || "moderate").toLowerCase();
        }
        document.getElementById("modal-loc").textContent = r.location_name;
        document.getElementById("modal-coords").textContent = `${r.latitude.toFixed(6)}°N, ${r.longitude.toFixed(6)}°E`;
        document.getElementById("modal-desc").textContent = r.description;

        var photoCont = document.getElementById("modal-photo-container");
        var photoImg = document.getElementById("modal-photo");
        if (r.photo_url && photoCont && photoImg) {
            photoImg.src = r.photo_url;
            photoCont.style.display = "block";
        } else if (photoCont) {
            photoCont.style.display = "none";
        }

        document.getElementById("modal-status-select").value = r.status || "Reported";
        document.getElementById("modal-verified-switch").checked = !!r.is_verified;
        document.getElementById("modal-admin-notes").value = r.admin_notes || "";

        var modalEl = document.getElementById("adminIncidentModal");
        if (modalEl && typeof bootstrap !== "undefined") {
            var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            modal.show();
        }
    }

    function saveIncidentStatus() {
        if (!currentIncidentId) return;

        var status = document.getElementById("modal-status-select").value;
        var isVerified = document.getElementById("modal-verified-switch").checked;
        var adminNotes = document.getElementById("modal-admin-notes").value;

        fetch("/api/admin/incidents/" + currentIncidentId + "/status", {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            credentials: "same-origin",
            body: JSON.stringify({
                status: status,
                is_verified: isVerified,
                admin_notes: adminNotes,
            }),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    showAlert(`Incident #${currentIncidentId} updated to '${status}' successfully.`, "success");
                    var modalEl = document.getElementById("adminIncidentModal");
                    if (modalEl && typeof bootstrap !== "undefined") {
                        var modal = bootstrap.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                    }
                    fetchAdminIncidents();
                } else {
                    showAlert((data.errors || ["Failed to update incident."]).join(" "), "danger");
                }
            })
            .catch(function () {
                showAlert("Network communication error.", "danger");
            });
    }

    function deleteCurrentIncident() {
        if (!currentIncidentId) return;
        if (!confirm(`Are you sure you want to delete Incident #${currentIncidentId}? This action cannot be undone.`)) {
            return;
        }

        fetch("/api/admin/incidents/" + currentIncidentId, {
            method: "DELETE",
            headers: {
                "X-CSRFToken": csrfToken(),
            },
            credentials: "same-origin",
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.success) {
                    showAlert(`Incident #${currentIncidentId} was deleted.`, "warning");
                    var modalEl = document.getElementById("adminIncidentModal");
                    if (modalEl && typeof bootstrap !== "undefined") {
                        var modal = bootstrap.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                    }
                    fetchAdminIncidents();
                } else {
                    showAlert((data.errors || ["Failed to delete incident."]).join(" "), "danger");
                }
            })
            .catch(function () {
                showAlert("Network communication error.", "danger");
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        fetchAdminIncidents();

        var btnFilter = document.getElementById("btn-apply-filters");
        if (btnFilter) btnFilter.addEventListener("click", fetchAdminIncidents);

        var btnReset = document.getElementById("btn-reset-filters");
        if (btnReset) {
            btnReset.addEventListener("click", function () {
                document.getElementById("filter-type").value = "all";
                document.getElementById("filter-status").value = "all";
                document.getElementById("filter-severity").value = "all";
                document.getElementById("filter-verified").value = "all";
                fetchAdminIncidents();
            });
        }

        var btnSave = document.getElementById("btn-save-incident");
        if (btnSave) btnSave.addEventListener("click", saveIncidentStatus);

        var btnDelete = document.getElementById("btn-delete-incident");
        if (btnDelete) btnDelete.addEventListener("click", deleteCurrentIncident);
    });
})();

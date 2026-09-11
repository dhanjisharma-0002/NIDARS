/**
 * NIDARS — User Submitted Incident Reports Client Logic
 */
(function () {
    "use strict";

    function loadMyReports() {
        var tbody = document.getElementById("my-reports-tbody");
        var countBadge = document.getElementById("my-reports-count");
        if (!tbody) return;

        fetch("/api/incidents/my")
            .then(function (res) {
                if (!res.ok) throw new Error("Failed to load your reports");
                return res.json();
            })
            .then(function (data) {
                var list = data.incidents || [];
                if (countBadge) countBadge.textContent = list.length + " Reports Logged";

                if (list.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="8" class="text-center py-4 text-muted">
                                <span>No incidents reported yet.</span>
                                <div class="mt-2">
                                    <a href="/report-incident" class="btn btn-sm btn-danger-emergency">
                                        📢 Submit First Report
                                    </a>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                var html = "";
                list.forEach(function (item) {
                    var sevClass = (item.severity || "moderate").toLowerCase();
                    var statusClass = (item.status || "reported").toLowerCase().replace(/\s+/g, "-");
                    var isVerified = item.is_verified;
                    var dateStr = item.created_at ? new Date(item.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : "—";
                    var coords = `${item.latitude.toFixed(4)}°N, ${item.longitude.toFixed(4)}°E`;
                    var photoHtml = item.photo_url
                        ? `<button class="btn btn-xs btn-outline-info btn-photo" data-photo="${item.photo_url}" title="View Photo">📷 View</button>`
                        : `<span class="text-muted small">None</span>`;

                    html += `
                        <tr>
                            <td><strong>⚠️ ${item.incident_type}</strong></td>
                            <td>${item.location_name}</td>
                            <td><span class="text-muted font-monospace small">${coords}</span></td>
                            <td><span class="risk-chip risk-${sevClass}">${item.severity}</span></td>
                            <td><span class="badge bg-secondary status-badge status-${statusClass}">${item.status}</span></td>
                            <td>
                                ${isVerified
                                    ? '<span class="badge bg-success bg-opacity-25 text-success border border-success border-opacity-25">🛡️ Verified</span>'
                                    : '<span class="badge bg-warning bg-opacity-25 text-warning border border-warning border-opacity-25">⏳ Unverified</span>'
                                }
                            </td>
                            <td class="text-muted small">${dateStr}</td>
                            <td class="text-end">${photoHtml}</td>
                        </tr>
                    `;
                });

                tbody.innerHTML = html;

                // Photo preview click handler
                tbody.querySelectorAll(".btn-photo").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        var url = this.getAttribute("data-photo");
                        var modalImg = document.getElementById("modal-photo-img");
                        var modalEl = document.getElementById("photoModal");
                        if (modalImg && modalEl && typeof bootstrap !== "undefined") {
                            modalImg.src = url;
                            var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                            modal.show();
                        }
                    });
                });
            })
            .catch(function (err) {
                console.warn("My reports load error:", err);
                if (tbody) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="8" class="text-center py-4 text-danger">
                                Failed to retrieve incident reports. Please refresh the page.
                            </td>
                        </tr>
                    `;
                }
            });
    }

    document.addEventListener("DOMContentLoaded", function () {
        loadMyReports();
    });
})();

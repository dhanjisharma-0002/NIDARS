/**
 * NIDARS Phase 7 — Admin Dashboard & Analytics Controller
 * Loads real system metrics, prediction histories, and emergency activity
 * from the database and renders Chart.js visualizations.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const btnRefreshStats = document.getElementById("btn-refresh-stats");
    const statsSpinner = document.getElementById("stats-spinner");

    // KPI Elements
    const statTotalUsers = document.getElementById("stat-total-users");
    const statTotalPredictions = document.getElementById("stat-total-predictions");
    const statFloodCount = document.getElementById("stat-flood-count");
    const statLandslideCount = document.getElementById("stat-landslide-count");
    const statEmergencyCount = document.getElementById("stat-emergency-count");
    const statFacilityCount = document.getElementById("stat-facility-count");
    const statHighRiskCount = document.getElementById("stat-high-risk-count");
    const statCriticalRiskCount = document.getElementById("stat-critical-risk-count");

    // Table Elements
    const emergencyLogsTbody = document.getElementById("emergency-logs-tbody");
    const emergencyLogBadge = document.getElementById("emergency-log-badge");
    const predictionLogsTbody = document.getElementById("prediction-logs-tbody");
    const predictionLogBadge = document.getElementById("prediction-log-badge");

    // Chart Variables
    let predictionChart = null;
    let riskChart = null;
    let facilityChart = null;

    async function loadDashboardData() {
        if (statsSpinner) statsSpinner.classList.remove("d-none");

        try {
            await Promise.all([
                fetchStats(),
                fetchEmergencyLogs(),
                fetchPredictionLogs()
            ]);
        } catch (err) {
            console.error("Error loading dashboard data:", err);
        } finally {
            if (statsSpinner) statsSpinner.classList.add("d-none");
        }
    }

    async function fetchStats() {
        try {
            const res = await fetch("/api/admin/stats");
            if (res.status === 401 || res.status === 403) {
                alert("Unauthorized. Admin privileges required.");
                return;
            }

            const data = await res.json();
            if (!data.success) {
                console.error("Failed to load admin stats:", data.errors);
                return;
            }

            const s = data.metrics || data.data || {};

            // Update KPI cards
            statTotalUsers.textContent = s.total_users ?? 0;
            statTotalPredictions.textContent = s.total_predictions ?? 0;
            statFloodCount.textContent = s.flood_predictions ?? 0;
            statLandslideCount.textContent = s.landslide_predictions ?? 0;
            statEmergencyCount.textContent = s.total_emergency_requests ?? 0;
            statFacilityCount.textContent = s.total_facilities ?? s.total_cached_facilities ?? 0;

            const rDist = s.risk_distribution || {};
            statHighRiskCount.textContent = rDist["HIGH"] ?? 0;
            statCriticalRiskCount.textContent = rDist["CRITICAL"] ?? 0;

            // Render Charts
            renderPredictionChart(s.flood_predictions, s.landslide_predictions);
            renderRiskChart(rDist);
            renderFacilityChart(s.facilities_by_type || s.facility_distribution || {});

        } catch (err) {
            console.error("Error fetching stats:", err);
        }
    }

    function renderPredictionChart(floodCount, landslideCount) {
        const ctx = document.getElementById("prediction-type-chart");
        const emptyBox = document.getElementById("pred-chart-empty");
        const wrapper = document.getElementById("pred-chart-wrapper");

        const total = (floodCount || 0) + (landslideCount || 0);
        if (total === 0) {
            wrapper.classList.add("d-none");
            emptyBox.classList.remove("d-none");
            return;
        }

        wrapper.classList.remove("d-none");
        emptyBox.classList.add("d-none");

        if (predictionChart) predictionChart.destroy();

        predictionChart = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: ["Flood Inquiries", "Landslide Inquiries"],
                datasets: [{
                    data: [floodCount || 0, landslideCount || 0],
                    backgroundColor: ["#0d6efd", "#ffc107"],
                    borderWidth: 1,
                    borderColor: "#1a1d20"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#ccc", font: { size: 11 } }
                    }
                }
            }
        });
    }

    function renderRiskChart(riskDist) {
        const ctx = document.getElementById("risk-level-chart");
        const emptyBox = document.getElementById("risk-chart-empty");
        const wrapper = document.getElementById("risk-chart-wrapper");

        const labels = ["Low", "Moderate", "High", "Critical"];
        const counts = [
            riskDist["LOW"] || riskDist["low"] || 0,
            riskDist["MODERATE"] || riskDist["moderate"] || 0,
            riskDist["HIGH"] || riskDist["high"] || 0,
            riskDist["CRITICAL"] || riskDist["critical"] || 0
        ];

        const total = counts.reduce((a, b) => a + b, 0);
        if (total === 0) {
            wrapper.classList.add("d-none");
            emptyBox.classList.remove("d-none");
            return;
        }

        wrapper.classList.remove("d-none");
        emptyBox.classList.add("d-none");

        if (riskChart) riskChart.destroy();

        riskChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Inquiries",
                    data: counts,
                    backgroundColor: ["#198754", "#ffc107", "#fd7e14", "#dc3545"],
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { color: "#aaa" }, grid: { color: "rgba(255,255,255,0.05)" } },
                    y: {
                        beginAtZero: true,
                        ticks: { color: "#aaa", stepSize: 1 },
                        grid: { color: "rgba(255,255,255,0.05)" }
                    }
                }
            }
        });
    }

    function renderFacilityChart(facDist) {
        const ctx = document.getElementById("facility-type-chart");
        const emptyBox = document.getElementById("facility-chart-empty");
        const wrapper = document.getElementById("facility-chart-wrapper");

        const hospitals = facDist["hospitals"] || facDist["hospital"] || 0;
        const police = facDist["police"] || 0;
        const shelters = facDist["shelters"] || facDist["shelter"] || 0;

        const total = hospitals + police + shelters;
        if (total === 0) {
            wrapper.classList.add("d-none");
            emptyBox.classList.remove("d-none");
            return;
        }

        wrapper.classList.remove("d-none");
        emptyBox.classList.add("d-none");

        if (facilityChart) facilityChart.destroy();

        facilityChart = new Chart(ctx, {
            type: "pie",
            data: {
                labels: ["Hospitals", "Police Stations", "Shelters"],
                datasets: [{
                    data: [hospitals, police, shelters],
                    backgroundColor: ["#dc3545", "#0d6efd", "#198754"],
                    borderWidth: 1,
                    borderColor: "#1a1d20"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#ccc", font: { size: 11 } }
                    }
                }
            }
        });
    }

    async function fetchEmergencyLogs() {
        try {
            const res = await fetch("/api/admin/emergency?limit=20");
            const data = await res.json();

            const logs = data.emergency_logs || data.data || [];
            emergencyLogBadge.textContent = `${logs.length} Logs`;

            if (logs.length === 0) {
                emergencyLogsTbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted small">No emergency records logged yet.</td></tr>`;
                return;
            }

            emergencyLogsTbody.innerHTML = "";
            logs.forEach(log => {
                const tr = document.createElement("tr");
                const timeStr = log.created_at ? new Date(log.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--";

                let riskBadge = "bg-secondary";
                const lvl = (log.risk_level || "").toUpperCase();
                if (lvl === "LOW") riskBadge = "bg-success";
                else if (lvl === "MODERATE") riskBadge = "bg-warning text-dark";
                else if (lvl === "HIGH") riskBadge = "bg-orange text-white" || "bg-danger";
                else if (lvl === "CRITICAL") riskBadge = "bg-danger";

                tr.innerHTML = `
                    <td class="text-muted small">${timeStr}</td>
                    <td><span class="badge bg-dark border border-secondary text-info">${log.request_type || "search"}</span></td>
                    <td class="small">${log.latitude ? parseFloat(log.latitude).toFixed(3) : "--"}, ${log.longitude ? parseFloat(log.longitude).toFixed(3) : "--"}</td>
                    <td><span class="badge ${riskBadge}">${lvl || "N/A"}</span></td>
                `;
                emergencyLogsTbody.appendChild(tr);
            });

        } catch (err) {
            console.error("Error fetching emergency logs:", err);
            emergencyLogsTbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-danger small">Failed to load logs.</td></tr>`;
        }
    }

    async function fetchPredictionLogs() {
        try {
            const res = await fetch("/api/admin/predictions?limit=20");
            const data = await res.json();

            const preds = data.predictions || data.data || [];
            predictionLogBadge.textContent = `${preds.length} Logs`;

            if (preds.length === 0) {
                predictionLogsTbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-muted small">No prediction records available.</td></tr>`;
                return;
            }

            predictionLogsTbody.innerHTML = "";
            preds.forEach(p => {
                const tr = document.createElement("tr");
                const timeStr = p.created_at ? new Date(p.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--";

                let riskBadge = "bg-secondary";
                const resObj = p.result || {};
                const lvl = (resObj.risk_level || p.risk_level || "").toUpperCase();
                if (lvl === "LOW") riskBadge = "bg-success";
                else if (lvl === "MODERATE") riskBadge = "bg-warning text-dark";
                else if (lvl === "HIGH") riskBadge = "bg-danger";
                else if (lvl === "CRITICAL") riskBadge = "bg-danger";

                const typeBadge = p.prediction_type === "flood" ? "bg-primary" : "bg-warning text-dark";

                tr.innerHTML = `
                    <td class="text-muted small">${timeStr}</td>
                    <td><span class="badge ${typeBadge}">${(p.prediction_type || "hazard").toUpperCase()}</span></td>
                    <td class="small text-truncate" style="max-width: 140px;">${p.user_email || "User"}</td>
                    <td><span class="badge ${riskBadge}">${lvl || "N/A"}</span></td>
                `;
                predictionLogsTbody.appendChild(tr);
            });

        } catch (err) {
            console.error("Error fetching prediction logs:", err);
            predictionLogsTbody.innerHTML = `<tr><td colspan="4" class="text-center py-3 text-danger small">Failed to load predictions.</td></tr>`;
        }
    }

    if (btnRefreshStats) {
        btnRefreshStats.addEventListener("click", loadDashboardData);
    }

    // Initial Load
    loadDashboardData();
});

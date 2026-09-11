/**
 * NIDARS — Phase 16: Advanced Analytics & Disaster Intelligence Dashboard
 * Powers multi-dimensional Chart.js visualizations, authentic data aggregation,
 * state & district rankings, seasonality patterns, and CSV export streaming.
 */

(function () {
    "use strict";

    // Chart instances
    var charts = {
        stateRisk: null,
        riskDistribution: null,
        monthlySeasonality: null,
        topDistricts: null,
        weatherCorrelation: null,
    };

    // Filter states
    var currentFilters = {
        state: "ALL",
        district: "ALL",
        hazard: "combined",
        period: "all",
        riskLevel: "ALL",
    };

    var cachedLocationsData = [];

    // --- DOM Loaded Initialization ---
    document.addEventListener("DOMContentLoaded", function () {
        setupFilterListeners();
        setupExportListeners();
        loadAllAnalyticsData();
    });

    // --- Filter Event Handlers ---
    function setupFilterListeners() {
        var stateSelect = document.getElementById("analytics-state-select");
        if (stateSelect) {
            stateSelect.addEventListener("change", function (e) {
                currentFilters.state = e.target.value;
                currentFilters.district = "ALL";
                updateDistrictDropdown(currentFilters.state);
                loadAllAnalyticsData();
            });
        }

        var districtSelect = document.getElementById("analytics-district-select");
        if (districtSelect) {
            districtSelect.addEventListener("change", function (e) {
                currentFilters.district = e.target.value;
                loadAllAnalyticsData();
            });
        }

        var hazardBtns = document.querySelectorAll(".hazard-btn");
        hazardBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                hazardBtns.forEach(function (b) { b.classList.remove("active"); });
                btn.classList.add("active");
                currentFilters.hazard = btn.getAttribute("data-hazard") || "combined";
                loadAllAnalyticsData();
            });
        });

        var periodSelect = document.getElementById("analytics-period-select");
        if (periodSelect) {
            periodSelect.addEventListener("change", function (e) {
                currentFilters.period = e.target.value;
                loadAllAnalyticsData();
            });
        }

        var riskSelect = document.getElementById("analytics-risk-select");
        if (riskSelect) {
            riskSelect.addEventListener("change", function (e) {
                currentFilters.riskLevel = e.target.value;
                loadAllAnalyticsData();
            });
        }

        var resetBtn = document.getElementById("reset-filters-btn");
        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                currentFilters = {
                    state: "ALL",
                    district: "ALL",
                    hazard: "combined",
                    period: "all",
                    riskLevel: "ALL",
                };
                if (stateSelect) stateSelect.value = "ALL";
                if (districtSelect) districtSelect.value = "ALL";
                if (periodSelect) periodSelect.value = "all";
                if (riskSelect) riskSelect.value = "ALL";
                hazardBtns.forEach(function (b) {
                    if (b.getAttribute("data-hazard") === "combined") b.classList.add("active");
                    else b.classList.remove("active");
                });
                updateDistrictDropdown("ALL");
                loadAllAnalyticsData();
            });
        }

        var refreshBtn = document.getElementById("refresh-analytics-btn");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", function () {
                loadAllAnalyticsData();
            });
        }

        var tableSearch = document.getElementById("locations-table-search");
        if (tableSearch) {
            tableSearch.addEventListener("input", function (e) {
                var query = e.target.value.toLowerCase().trim();
                filterLocationsTable(query);
            });
        }
    }

    // --- CSV Export Handlers ---
    function setupExportListeners() {
        var exportLinks = document.querySelectorAll(".export-csv-link");
        exportLinks.forEach(function (link) {
            link.addEventListener("click", function (e) {
                e.preventDefault();
                var exportType = link.getAttribute("data-export-type") || "rankings";
                var url = "/api/analytics/export/csv?type=" + encodeURIComponent(exportType) +
                    "&state=" + encodeURIComponent(currentFilters.state) +
                    "&district=" + encodeURIComponent(currentFilters.district) +
                    "&hazard=" + encodeURIComponent(currentFilters.hazard);
                window.location.href = url;
            });
        });
    }

    // --- Dynamic District Dropdown Updater ---
    function updateDistrictDropdown(stateCode) {
        var districtSelect = document.getElementById("analytics-district-select");
        if (!districtSelect) return;

        fetch("/api/analytics/districts?state=" + encodeURIComponent(stateCode))
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data && data.success && data.districts) {
                    districtSelect.innerHTML = '<option value="ALL" selected>All Districts</option>';
                    data.districts.forEach(function (d) {
                        var opt = document.createElement("option");
                        opt.value = d;
                        opt.textContent = d;
                        districtSelect.appendChild(opt);
                    });
                }
            })
            .catch(function () {});
    }

    // --- Main Data Loading Coordinator ---
    function loadAllAnalyticsData() {
        var spinner = document.getElementById("refresh-spinner");
        if (spinner) spinner.classList.remove("d-none");

        var queryParams = "?state=" + encodeURIComponent(currentFilters.state) +
            "&district=" + encodeURIComponent(currentFilters.district) +
            "&hazard=" + encodeURIComponent(currentFilters.hazard) +
            "&risk_level=" + encodeURIComponent(currentFilters.riskLevel);

        Promise.all([
            fetch("/api/analytics/overview" + queryParams).then(function (r) { return r.json(); }),
            fetch("/api/analytics/trends" + queryParams).then(function (r) { return r.json(); }),
            fetch("/api/analytics/rankings" + queryParams).then(function (r) { return r.json(); }),
        ]).then(function (results) {
            if (spinner) spinner.classList.add("d-none");
            var overviewData = results[0];
            var trendsData = results[1];
            var rankingsData = results[2];

            if (overviewData && overviewData.success) {
                updateKpis(overviewData.kpis);
                renderStateRiskChart(overviewData.state_metrics);
                renderRiskDistributionChart(overviewData.distribution);
            }

            if (trendsData && trendsData.success) {
                renderMonthlySeasonalityChart(trendsData.seasonality);
                renderWeatherCorrelationChart(trendsData.weather_correlations);
            }

            if (rankingsData && rankingsData.success) {
                renderTopDistrictsChart(rankingsData.district_rankings);
                renderLocationsTable(rankingsData.location_rankings);
                renderStatesTable(rankingsData.state_rankings);
            }
        }).catch(function (err) {
            if (spinner) spinner.classList.add("d-none");
            console.error("Failed to load analytics data:", err);
        });
    }

    // --- KPI Renderers ---
    function updateKpis(kpis) {
        if (!kpis) return;

        var elTotal = document.getElementById("kpi-total-evaluations");
        var elMeanRisk = document.getElementById("kpi-mean-risk");
        var elRiskBadge = document.getElementById("kpi-risk-badge");
        var elFloodProb = document.getElementById("kpi-flood-prob");
        var elLandslideProb = document.getElementById("kpi-landslide-prob");
        var elActiveAlerts = document.getElementById("kpi-active-alerts");
        var elCitizenIncidents = document.getElementById("kpi-citizen-incidents");
        var elHighestDistrict = document.getElementById("kpi-highest-district");
        var elHighestScore = document.getElementById("kpi-highest-score");

        if (elTotal) elTotal.textContent = Number(kpis.total_evaluations || 0).toLocaleString();
        if (elMeanRisk) elMeanRisk.textContent = (kpis.mean_composite_risk || 0).toFixed(4);
        if (elFloodProb) elFloodProb.textContent = ((kpis.mean_flood_probability || 0) * 100).toFixed(1) + "%";
        if (elLandslideProb) elLandslideProb.textContent = ((kpis.mean_landslide_probability || 0) * 100).toFixed(1) + "%";
        if (elActiveAlerts) elActiveAlerts.textContent = kpis.active_alerts_count || 0;
        if (elCitizenIncidents) elCitizenIncidents.textContent = kpis.citizen_incidents_count || 0;
        if (elHighestDistrict) elHighestDistrict.textContent = kpis.highest_risk_district || "--";
        if (elHighestScore) elHighestScore.textContent = (kpis.highest_risk_score || 0).toFixed(4);

        if (elRiskBadge) {
            var lvl = kpis.composite_risk_level || "LOW";
            elRiskBadge.textContent = lvl;
            elRiskBadge.className = "badge " + getBadgeClass(lvl);
        }
    }

    function getBadgeClass(level) {
        if (level === "CRITICAL") return "bg-danger text-white";
        if (level === "HIGH") return "bg-warning text-dark";
        if (level === "MODERATE") return "bg-info text-dark";
        return "bg-success text-white";
    }

    // --- Chart 1: State Risk Bar Chart ---
    function renderStateRiskChart(stateMetrics) {
        var ctx = document.getElementById("stateRiskChart");
        if (!ctx || typeof Chart === "undefined") return;

        if (charts.stateRisk) {
            charts.stateRisk.destroy();
        }

        var labels = (stateMetrics || []).map(function (s) { return s.state_code; });
        var combinedRisks = (stateMetrics || []).map(function (s) { return s.combined_risk; });
        var floodRisks = (stateMetrics || []).map(function (s) { return s.flood_risk; });
        var landslideRisks = (stateMetrics || []).map(function (s) { return s.landslide_risk; });

        charts.stateRisk = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Combined Risk",
                        data: combinedRisks,
                        backgroundColor: "rgba(245, 158, 11, 0.8)",
                        borderColor: "#f59e0b",
                        borderWidth: 1.5,
                        borderRadius: 4,
                    },
                    {
                        label: "Flood Risk (RF)",
                        data: floodRisks,
                        backgroundColor: "rgba(56, 189, 248, 0.6)",
                        borderColor: "#38bdf8",
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: "Landslide Risk (GB)",
                        data: landslideRisks,
                        backgroundColor: "rgba(239, 68, 68, 0.6)",
                        borderColor: "#ef4444",
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "top",
                        labels: { color: "#cbd5e1", font: { size: 11 } },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return context.dataset.label + ": " + Number(context.parsed.y).toFixed(4);
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.06)" },
                        ticks: { color: "#94a3b8", font: { size: 11 } },
                    },
                    y: {
                        min: 0,
                        max: 1.0,
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: { color: "#94a3b8", font: { size: 11 } },
                    },
                },
            },
        });
    }

    // --- Chart 2: Severity Distribution Doughnut Chart ---
    function renderRiskDistributionChart(distribution) {
        var ctx = document.getElementById("riskDistributionChart");
        if (!ctx || typeof Chart === "undefined" || !distribution) return;

        if (charts.riskDistribution) {
            charts.riskDistribution.destroy();
        }

        charts.riskDistribution = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: distribution.labels,
                datasets: [
                    {
                        data: distribution.counts,
                        backgroundColor: [
                            "rgba(34, 197, 94, 0.85)",   // Low (Green)
                            "rgba(245, 158, 11, 0.85)",  // Moderate (Amber)
                            "rgba(239, 68, 68, 0.85)",   // High (Red)
                            "rgba(168, 85, 247, 0.85)",  // Critical (Purple)
                        ],
                        borderColor: "#0f172a",
                        borderWidth: 2,
                        hoverOffset: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: { color: "#cbd5e1", boxWidth: 12, font: { size: 10 } },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                var count = context.parsed;
                                var pct = distribution.percentages[context.dataIndex] || 0;
                                return " " + context.label + ": " + count + " records (" + pct + "%)";
                            },
                        },
                    },
                },
                cutout: "62%",
            },
        });
    }

    // --- Chart 3: Monthly Seasonality Area Chart ---
    function renderMonthlySeasonalityChart(seasonality) {
        var ctx = document.getElementById("monthlySeasonalityChart");
        if (!ctx || typeof Chart === "undefined" || !seasonality) return;

        if (charts.monthlySeasonality) {
            charts.monthlySeasonality.destroy();
        }

        charts.monthlySeasonality = new Chart(ctx, {
            type: "line",
            data: {
                labels: seasonality.labels,
                datasets: [
                    {
                        label: "Mean Rainfall (mm)",
                        data: seasonality.rainfall,
                        borderColor: "#38bdf8",
                        backgroundColor: "rgba(56, 189, 248, 0.18)",
                        fill: true,
                        tension: 0.35,
                        yAxisID: "yRain",
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                    {
                        label: "Calculated Joint Risk Score",
                        data: seasonality.combined_risk,
                        borderColor: "#ef4444",
                        backgroundColor: "transparent",
                        borderWidth: 2.5,
                        borderDash: [4, 4],
                        tension: 0.35,
                        yAxisID: "yRisk",
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        position: "top",
                        labels: { color: "#cbd5e1", font: { size: 11 } },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.06)" },
                        ticks: { color: "#94a3b8", font: { size: 11 } },
                    },
                    yRain: {
                        type: "linear",
                        position: "left",
                        title: { display: true, text: "Rainfall (mm)", color: "#38bdf8" },
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: { color: "#38bdf8" },
                    },
                    yRisk: {
                        type: "linear",
                        position: "right",
                        min: 0,
                        max: 1.0,
                        title: { display: true, text: "Risk Index", color: "#ef4444" },
                        grid: { drawOnChartArea: false },
                        ticks: { color: "#ef4444" },
                    },
                },
            },
        });
    }

    // --- Chart 4: Top 10 High-Risk Districts Horizontal Bar ---
    function renderTopDistrictsChart(districts) {
        var ctx = document.getElementById("topDistrictsChart");
        if (!ctx || typeof Chart === "undefined" || !districts) return;

        if (charts.topDistricts) {
            charts.topDistricts.destroy();
        }

        var top10 = districts.slice(0, 10);
        var labels = top10.map(function (d) { return d.district + " (" + d.state_code + ")"; });
        var data = top10.map(function (d) { return d.combined_risk; });

        charts.topDistricts = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Combined Risk",
                        data: data,
                        backgroundColor: data.map(function (val) {
                            if (val >= 0.75) return "rgba(168, 85, 247, 0.85)";
                            if (val >= 0.50) return "rgba(239, 68, 68, 0.85)";
                            if (val >= 0.25) return "rgba(245, 158, 11, 0.85)";
                            return "rgba(34, 197, 94, 0.85)";
                        }),
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return " Risk Score: " + Number(context.parsed.x).toFixed(4);
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        min: 0,
                        max: 1.0,
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: { color: "#94a3b8", font: { size: 10 } },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: "#e2e8f0", font: { size: 11 } },
                    },
                },
            },
        });
    }

    // --- Chart 5: Weather Parameter Correlation Chart ---
    function renderWeatherCorrelationChart(weatherPoints) {
        var ctx = document.getElementById("weatherCorrelationChart");
        if (!ctx || typeof Chart === "undefined" || !weatherPoints) return;

        if (charts.weatherCorrelation) {
            charts.weatherCorrelation.destroy();
        }

        var labels = weatherPoints.map(function (_, idx) { return "#" + (idx + 1); });
        var rainfallData = weatherPoints.map(function (p) { return p.rainfall; });
        var pressureData = weatherPoints.map(function (p) { return p.air_pressure; });
        var riskScores = weatherPoints.map(function (p) { return p.risk_score; });

        charts.weatherCorrelation = new Chart(ctx, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Observed Rainfall (mm)",
                        data: rainfallData,
                        borderColor: "#38bdf8",
                        backgroundColor: "rgba(56, 189, 248, 0.2)",
                        borderWidth: 1.5,
                        pointRadius: 2,
                        yAxisID: "yRain",
                    },
                    {
                        label: "Air Pressure (hPa)",
                        data: pressureData,
                        borderColor: "#a855f7",
                        backgroundColor: "transparent",
                        borderWidth: 1.5,
                        pointRadius: 2,
                        yAxisID: "yPressure",
                    },
                    {
                        label: "Disaster Risk Index",
                        data: riskScores,
                        borderColor: "#f59e0b",
                        backgroundColor: "transparent",
                        borderWidth: 2,
                        pointRadius: 2.5,
                        yAxisID: "yRisk",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        position: "top",
                        labels: { color: "#cbd5e1", font: { size: 11 } },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { display: false },
                    },
                    yRain: {
                        type: "linear",
                        position: "left",
                        title: { display: true, text: "Rainfall (mm)", color: "#38bdf8" },
                        grid: { color: "rgba(255, 255, 255, 0.05)" },
                        ticks: { color: "#38bdf8" },
                    },
                    yPressure: {
                        type: "linear",
                        position: "right",
                        min: 980,
                        max: 1030,
                        title: { display: true, text: "Pressure (hPa)", color: "#a855f7" },
                        grid: { drawOnChartArea: false },
                        ticks: { color: "#a855f7" },
                    },
                    yRisk: {
                        type: "linear",
                        position: "right",
                        min: 0,
                        max: 1.0,
                        title: { display: true, text: "Risk (0-1)", color: "#f59e0b" },
                        grid: { drawOnChartArea: false },
                        ticks: { color: "#f59e0b" },
                    },
                },
            },
        });
    }

    // --- Table 1: Locations Ranking Table ---
    function renderLocationsTable(locations) {
        var tbody = document.getElementById("locations-table-body");
        if (!tbody) return;

        cachedLocationsData = locations || [];

        if (cachedLocationsData.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No location records match current filter criteria.</td></tr>';
            return;
        }

        var html = [];
        cachedLocationsData.forEach(function (loc, index) {
            var rank = index + 1;
            var rankBadge = rank <= 3 ? '<span class="badge bg-danger rounded-pill">' + rank + '</span>' : '<span class="text-muted">' + rank + '</span>';
            var lvlClass = getBadgeClass(loc.risk_level);

            html.push('<tr>');
            html.push('  <td>' + rankBadge + '</td>');
            html.push('  <td><strong class="text-light">' + escapeHtml(loc.location_name) + '</strong></td>');
            html.push('  <td><span class="badge bg-secondary">' + escapeHtml(loc.state_code) + '</span></td>');
            html.push('  <td>' + escapeHtml(loc.district) + '</td>');
            html.push('  <td class="text-end text-muted">' + (loc.elevation ? loc.elevation.toFixed(0) + 'm' : '--') + '</td>');
            html.push('  <td class="text-end fw-bold text-warning">' + Number(loc.combined_risk).toFixed(4) + '</td>');
            html.push('  <td class="text-center"><span class="badge ' + lvlClass + '">' + escapeHtml(loc.risk_level) + '</span></td>');
            html.push('  <td class="text-center"><a href="/route-optimizer?dest_lat=' + loc.latitude + '&dest_lon=' + loc.longitude + '" class="btn btn-xs btn-outline-primary" style="font-size: 0.72rem;">Route</a></td>');
            html.push('</tr>');
        });

        tbody.innerHTML = html.join("");
    }

    function filterLocationsTable(query) {
        var tbody = document.getElementById("locations-table-body");
        if (!tbody) return;

        var filtered = cachedLocationsData.filter(function (loc) {
            return (loc.location_name || "").toLowerCase().indexOf(query) !== -1 ||
                (loc.district || "").toLowerCase().indexOf(query) !== -1 ||
                (loc.state_code || "").toLowerCase().indexOf(query) !== -1;
        });

        if (filtered.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No matching stations found.</td></tr>';
            return;
        }

        var html = [];
        filtered.forEach(function (loc, index) {
            var rank = index + 1;
            var rankBadge = rank <= 3 ? '<span class="badge bg-danger rounded-pill">' + rank + '</span>' : '<span class="text-muted">' + rank + '</span>';
            var lvlClass = getBadgeClass(loc.risk_level);

            html.push('<tr>');
            html.push('  <td>' + rankBadge + '</td>');
            html.push('  <td><strong class="text-light">' + escapeHtml(loc.location_name) + '</strong></td>');
            html.push('  <td><span class="badge bg-secondary">' + escapeHtml(loc.state_code) + '</span></td>');
            html.push('  <td>' + escapeHtml(loc.district) + '</td>');
            html.push('  <td class="text-end text-muted">' + (loc.elevation ? loc.elevation.toFixed(0) + 'm' : '--') + '</td>');
            html.push('  <td class="text-end fw-bold text-warning">' + Number(loc.combined_risk).toFixed(4) + '</td>');
            html.push('  <td class="text-center"><span class="badge ' + lvlClass + '">' + escapeHtml(loc.risk_level) + '</span></td>');
            html.push('  <td class="text-center"><a href="/route-optimizer?dest_lat=' + loc.latitude + '&dest_lon=' + loc.longitude + '" class="btn btn-xs btn-outline-primary" style="font-size: 0.72rem;">Route</a></td>');
            html.push('</tr>');
        });

        tbody.innerHTML = html.join("");
    }

    // --- Table 2: States Ranking Table ---
    function renderStatesTable(states) {
        var tbody = document.getElementById("states-table-body");
        if (!tbody) return;

        if (!states || states.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No state records available.</td></tr>';
            return;
        }

        var html = [];
        states.forEach(function (st, index) {
            var rank = index + 1;
            var rankBadge = rank <= 3 ? '<span class="badge bg-danger rounded-pill">' + rank + '</span>' : '<span class="text-muted">' + rank + '</span>';
            var lvlClass = getBadgeClass(st.risk_level);

            html.push('<tr>');
            html.push('  <td>' + rankBadge + '</td>');
            html.push('  <td><strong>' + escapeHtml(st.state_name) + '</strong> <small class="text-muted">(' + escapeHtml(st.state_code) + ')</small></td>');
            html.push('  <td class="text-end text-info">' + Number(st.flood_risk).toFixed(4) + '</td>');
            html.push('  <td class="text-end text-danger">' + Number(st.landslide_risk).toFixed(4) + '</td>');
            html.push('  <td class="text-end fw-bold text-warning">' + Number(st.combined_risk).toFixed(4) + '</td>');
            html.push('  <td class="text-end text-light fw-semibold">' + (st.dfsi_score ? Number(st.dfsi_score).toFixed(2) : '--') + '</td>');
            html.push('  <td class="text-center"><span class="badge ' + lvlClass + '">' + escapeHtml(st.risk_level) + '</span></td>');
            html.push('</tr>');
        });

        tbody.innerHTML = html.join("");
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

})();

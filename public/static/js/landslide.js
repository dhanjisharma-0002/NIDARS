/**
 * NIDARS — Landslide ML Assessment Client Logic
 * Handles preset loading, submission to /api/predict/landslide, and calibrated gauge rendering.
 */
(function () {
    "use strict";

    var form = document.getElementById("landslide-form");
    if (!form) return;

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function setStatus(text, ok) {
        var chip = document.getElementById("landslide-status-chip");
        if (!chip) return;
        chip.querySelector("span:last-child").textContent = text;
        chip.className = "system-status-pill " + (ok ? "online" : "offline");
    }

    // Set circular gauge progress
    function updateGauge(probability, riskLevel) {
        var circle = document.getElementById("landslide-gauge-circle");
        var probElem = document.getElementById("landslide-probability");
        var riskElem = document.getElementById("landslide-risk");
        if (!circle || !probElem || !riskElem) return;

        var pct = Math.min(100, Math.max(0, probability * 100));
        var circumference = 2 * Math.PI * 70; // ~439.82
        var offset = circumference - (pct / 100) * circumference;

        circle.style.strokeDashoffset = offset;

        var strokeColor = "#10b981";
        var badgeClass = "low";

        var level = (riskLevel || "").toUpperCase();
        if (level === "CRITICAL" || probability >= 0.75) {
            strokeColor = "#ef4444";
            badgeClass = "critical";
        } else if (level === "HIGH" || probability >= 0.10) {
            strokeColor = "#f97316";
            badgeClass = "high";
        } else if (level === "MODERATE" || probability >= 0.02) {
            strokeColor = "#f59e0b";
            badgeClass = "moderate";
        }

        circle.style.stroke = strokeColor;
        probElem.textContent = (probability * 100).toFixed(2) + "%";
        riskElem.textContent = riskLevel || "LOW";
        riskElem.className = "risk-badge " + badgeClass;
    }

    // Presets Handlers
    function setupPresets() {
        var btnHimalayan = document.getElementById("preset-himalayan");
        var btnValley = document.getElementById("preset-valley");
        var btnPlains = document.getElementById("preset-plains");

        if (btnHimalayan) {
            btnHimalayan.addEventListener("click", function () {
                form.rainfall_24h.value = "110.0";
                form.rainfall_72h.value = "240.0";
                form.rainfall_7d.value = "410.0";
                form.temperature.value = "16.0";
                form.wind_speed.value = "14.5";
                form.air_pressure.value = "982.0";
                form.elevation.value = "2276";
                form.latitude.value = "31.1048"; // Shimla, HP
                form.longitude.value = "77.1734";
            });
        }

        if (btnValley) {
            btnValley.addEventListener("click", function () {
                form.rainfall_24h.value = "45.0";
                form.rainfall_72h.value = "95.0";
                form.rainfall_7d.value = "160.0";
                form.temperature.value = "19.0";
                form.wind_speed.value = "8.0";
                form.air_pressure.value = "990.0";
                form.elevation.value = "2050";
                form.latitude.value = "32.2432"; // Manali, HP
                form.longitude.value = "77.1892";
            });
        }

        if (btnPlains) {
            btnPlains.addEventListener("click", function () {
                form.rainfall_24h.value = "5.0";
                form.rainfall_72h.value = "10.0";
                form.rainfall_7d.value = "15.0";
                form.temperature.value = "32.0";
                form.wind_speed.value = "5.0";
                form.air_pressure.value = "1010.0";
                form.elevation.value = "216";
                form.latitude.value = "28.6139"; // Delhi
                form.longitude.value = "77.2090";
            });
        }
    }

    var explainChart = null;

    function renderExplainability(explainData) {
        var row = document.getElementById("landslide-explainability-row");
        var factorsList = document.getElementById("landslide-factors-list");
        var canvas = document.getElementById("landslide-explain-chart");
        if (!row || !factorsList || !canvas || !explainData) return;

        row.style.display = "flex";

        // Render Top Contributing Factors list
        var factors = explainData.top_contributing_factors || [];
        var html = "";
        factors.forEach(function (f) {
            var impactClass = (f.impact || "low").toLowerCase();
            var dirClass = (f.direction || "neutral").toLowerCase();
            var dirIcon = f.direction === "POSITIVE" ? "▲" : (f.direction === "NEGATIVE" ? "▼" : "•");
            var scorePct = Math.abs(f.contribution_score * 100).toFixed(1) + "%";

            html += `
                <div class="factor-item-card">
                    <div class="factor-header">
                        <span class="factor-name">
                            <span>🔹</span> ${f.label}
                        </span>
                        <span class="contrib-badge ${impactClass}">
                            ${f.impact} CONTRIBUTION
                        </span>
                    </div>
                    <div class="factor-details">
                        <span>Observed: <strong>${f.current_value} ${f.unit}</strong> (Baseline: ${f.baseline_value} ${f.unit})</span>
                        <span class="direction-tag ${dirClass}">
                            ${dirIcon} ${f.direction_label || f.direction} (${scorePct})
                        </span>
                    </div>
                </div>
            `;
        });
        factorsList.innerHTML = html;

        // Render Horizontal Bar Chart
        if (typeof Chart === "undefined") return;

        if (explainChart) {
            explainChart.destroy();
        }

        var chartData = explainData.chart_data || {};
        var labels = chartData.labels || [];
        var values = chartData.contributions || [];
        var colors = chartData.colors || [];

        explainChart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Contribution Influence (%)",
                        data: values,
                        backgroundColor: colors,
                        borderRadius: 4,
                        borderWidth: 0,
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
                            label: function (ctx) {
                                var val = ctx.parsed.x || 0;
                                var sign = val > 0 ? "+" : "";
                                return " Influence: " + sign + val.toFixed(1) + "% (" + (val > 0 ? "Increases Risk" : (val < 0 ? "Decreases Risk" : "Neutral")) + ")";
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { color: "rgba(255, 255, 255, 0.08)" },
                        ticks: {
                            color: "#94a3b8",
                            font: { size: 11 },
                            callback: function (val) {
                                return val + "%";
                            },
                        },
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: "#f1f5f9", font: { size: 12, weight: "500" } },
                    },
                },
            },
        });
    }

    // Form Submission
    form.addEventListener("submit", function (event) {
        event.preventDefault();

        var payload = {
            rainfall_24h: form.rainfall_24h.value,
            rainfall_72h: form.rainfall_72h.value,
            rainfall_7d: form.rainfall_7d.value,
            temperature: form.temperature.value,
            wind_speed: form.wind_speed.value,
            air_pressure: form.air_pressure.value,
            elevation: form.elevation.value,
            latitude: form.latitude.value,
            longitude: form.longitude.value,
        };

        var message = document.getElementById("landslide-message");
        var btnPredict = document.getElementById("btn-predict-landslide");
        if (message) message.textContent = "Computing Gradient Boosting landslide probability…";
        if (btnPredict) btnPredict.disabled = true;

        fetch("/api/predict/landslide", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken(),
            },
            credentials: "same-origin",
            body: JSON.stringify(payload),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                if (btnPredict) btnPredict.disabled = false;
                var data = result.data;
                setStatus("Model Status: " + (data.model_status || "unknown").toUpperCase(), data.model_status === "trained");

                if (!data.success) {
                    document.getElementById("landslide-probability").textContent = "—";
                    document.getElementById("landslide-risk").textContent = "Error";
                    document.getElementById("landslide-risk").className = "risk-badge critical";
                    if (message) message.textContent = (data.errors || ["Prediction request failed."]).join(" ");
                    var explainRow = document.getElementById("landslide-explainability-row");
                    if (explainRow) explainRow.style.display = "none";
                    return;
                }

                var prob = data.prediction.landslide_probability;
                var risk = data.prediction.risk_level;
                updateGauge(prob, risk);
                if (message) message.textContent = data.threshold_note || "Landslide probability calculated.";

                // Show PDF Report Download Button
                var reportBtnBox = document.getElementById("landslide-report-btn-box");
                if (reportBtnBox) {
                    reportBtnBox.style.display = "block";
                    var btnDownload = document.getElementById("btn-download-landslide-report");
                    if (btnDownload) {
                        btnDownload.onclick = function () {
                            var url = "/api/reports/disaster?location_name=" + encodeURIComponent("Landslide Assessment Zone") +
                                "&latitude=" + encodeURIComponent(payload.latitude) +
                                "&longitude=" + encodeURIComponent(payload.longitude) +
                                "&elevation=" + encodeURIComponent(payload.elevation) +
                                "&rainfall_24h=" + encodeURIComponent(payload.rainfall_24h) +
                                "&rainfall_72h=" + encodeURIComponent(payload.rainfall_72h) +
                                "&rainfall_7d=" + encodeURIComponent(payload.rainfall_7d) +
                                "&temperature=" + encodeURIComponent(payload.temperature) +
                                "&wind_speed=" + encodeURIComponent(payload.wind_speed) +
                                "&air_pressure=" + encodeURIComponent(payload.air_pressure) +
                                "&landslide_probability=" + encodeURIComponent(prob) +
                                "&risk_level=" + encodeURIComponent(risk);
                            window.location.href = url;
                        };
                    }
                }

                if (data.explainability) {
                    renderExplainability(data.explainability);
                }
            })
            .catch(function () {
                if (btnPredict) btnPredict.disabled = false;
                if (message) message.textContent = "Unable to connect to the Landslide ML service.";
                setStatus("Service Unreachable", false);
            });
    });

    document.addEventListener("DOMContentLoaded", function () {
        setupPresets();
        setStatus("Gradient Boosting Classifier Active", true);
    });
})();


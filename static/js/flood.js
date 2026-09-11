/**
 * NIDARS — Flood ML Prediction Client Logic
 * Handles preset filling, submission to /api/predict/flood, and circular gauge animation.
 */
(function () {
    "use strict";

    var form = document.getElementById("flood-form");
    if (!form) return;

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function setStatus(text, ok) {
        var chip = document.getElementById("model-status-chip");
        if (!chip) return;
        chip.querySelector("span:last-child").textContent = text;
        chip.className = "system-status-pill " + (ok ? "online" : "offline");
    }

    // Set circular gauge progress (stroke-dashoffset: 440 is 0%, 0 is 100%)
    function updateGauge(probability, riskLevel) {
        var circle = document.getElementById("gauge-circle");
        var probElem = document.getElementById("flood-probability");
        var riskElem = document.getElementById("flood-risk");
        if (!circle || !probElem || !riskElem) return;

        var pct = Math.min(100, Math.max(0, probability * 100));
        var circumference = 2 * Math.PI * 70; // ~439.82
        var offset = circumference - (pct / 100) * circumference;

        circle.style.strokeDashoffset = offset;

        var strokeColor = "#10b981";
        var badgeClass = "low";

        var level = (riskLevel || "").toUpperCase();
        if (level === "CRITICAL" || pct >= 75) {
            strokeColor = "#ef4444";
            badgeClass = "critical";
        } else if (level === "HIGH" || pct >= 50) {
            strokeColor = "#f97316";
            badgeClass = "high";
        } else if (level === "MODERATE" || pct >= 25) {
            strokeColor = "#f59e0b";
            badgeClass = "moderate";
        }

        circle.style.stroke = strokeColor;
        probElem.textContent = pct.toFixed(1) + "%";
        riskElem.textContent = riskLevel || "LOW";
        riskElem.className = "risk-badge " + badgeClass;
    }

    // Presets Handlers
    function setupPresets() {
        var btnHeavy = document.getElementById("preset-heavy");
        var btnMod = document.getElementById("preset-mod");
        var btnDry = document.getElementById("preset-dry");

        if (btnHeavy) {
            btnHeavy.addEventListener("click", function () {
                form.rainfall_24h.value = "145.0";
                form.rainfall_72h.value = "280.5";
                form.rainfall_7d.value = "460.0";
                form.temperature.value = "27.5";
                form.wind_speed.value = "18.2";
                form.air_pressure.value = "998.0";
                form.elevation.value = "85";
                form.latitude.value = "25.5941"; // Patna, Bihar
                form.longitude.value = "85.1376";
            });
        }

        if (btnMod) {
            btnMod.addEventListener("click", function () {
                form.rainfall_24h.value = "42.0";
                form.rainfall_72h.value = "88.0";
                form.rainfall_7d.value = "150.0";
                form.temperature.value = "29.0";
                form.wind_speed.value = "9.5";
                form.air_pressure.value = "1006.0";
                form.elevation.value = "128";
                form.latitude.value = "26.8467"; // Lucknow, UP
                form.longitude.value = "80.9462";
            });
        }

        if (btnDry) {
            btnDry.addEventListener("click", function () {
                form.rainfall_24h.value = "2.0";
                form.rainfall_72h.value = "5.0";
                form.rainfall_7d.value = "12.0";
                form.temperature.value = "34.0";
                form.wind_speed.value = "6.0";
                form.air_pressure.value = "1012.0";
                form.elevation.value = "216";
                form.latitude.value = "28.6139"; // Delhi
                form.longitude.value = "77.2090";
            });
        }
    }

    var explainChart = null;

    function renderExplainability(explainData) {
        var row = document.getElementById("flood-explainability-row");
        var factorsList = document.getElementById("flood-factors-list");
        var canvas = document.getElementById("flood-explain-chart");
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

        var message = document.getElementById("flood-message");
        var btnPredict = document.getElementById("btn-predict-flood");
        if (message) message.textContent = "Computing Random Forest risk score…";
        if (btnPredict) btnPredict.disabled = true;

        fetch("/api/predict/flood", {
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
                    document.getElementById("flood-probability").textContent = "—";
                    document.getElementById("flood-risk").textContent = "Error";
                    document.getElementById("flood-risk").className = "risk-badge critical";
                    if (message) message.textContent = (data.errors || ["Prediction request failed."]).join(" ");
                    var explainRow = document.getElementById("flood-explainability-row");
                    if (explainRow) explainRow.style.display = "none";
                    return;
                }

                var prob = data.prediction.flood_probability;
                var risk = data.prediction.risk_level;
                updateGauge(prob, risk);
                if (message) message.textContent = data.threshold_note || "Prediction evaluated successfully.";

                // Show PDF Report Download Button
                var reportBtnBox = document.getElementById("flood-report-btn-box");
                if (reportBtnBox) {
                    reportBtnBox.style.display = "block";
                    var btnDownload = document.getElementById("btn-download-flood-report");
                    if (btnDownload) {
                        btnDownload.onclick = function () {
                            var url = "/api/reports/disaster?location_name=" + encodeURIComponent("Flood Assessment Zone") +
                                "&latitude=" + encodeURIComponent(payload.latitude) +
                                "&longitude=" + encodeURIComponent(payload.longitude) +
                                "&elevation=" + encodeURIComponent(payload.elevation) +
                                "&rainfall_24h=" + encodeURIComponent(payload.rainfall_24h) +
                                "&rainfall_72h=" + encodeURIComponent(payload.rainfall_72h) +
                                "&rainfall_7d=" + encodeURIComponent(payload.rainfall_7d) +
                                "&temperature=" + encodeURIComponent(payload.temperature) +
                                "&wind_speed=" + encodeURIComponent(payload.wind_speed) +
                                "&air_pressure=" + encodeURIComponent(payload.air_pressure) +
                                "&flood_probability=" + encodeURIComponent(prob) +
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
                if (message) message.textContent = "Unable to connect to the Flood ML service.";
                setStatus("Service Unreachable", false);
            });
    });

    document.addEventListener("DOMContentLoaded", function () {
        setupPresets();
        // Check health/model status
        setStatus("Classifier Loaded", true);
    });
})();


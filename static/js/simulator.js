/**
 * NIDARS — Phase 13: What-If Disaster Risk Simulator Controller
 * Interactive scenario simulation and Chart.js comparison for environmental conditions.
 */

(function () {
    "use strict";

    var comparisonChart = null;

    var PRESETS_DATA = {
        heavy_rainfall: {
            rainfall_24h_delta: 50.0,
            rainfall_72h_delta: 100.0,
            rainfall_7d_delta: 150.0,
        },
        extreme_rainfall: {
            rainfall_24h_delta: 150.0,
            rainfall_72h_delta: 250.0,
            rainfall_7d_delta: 400.0,
        },
        high_wind: {
            wind_speed_delta: 45.0,
            air_pressure_delta: -15.0,
            rainfall_24h_delta: 25.0,
        },
        low_pressure: {
            air_pressure_delta: -30.0,
            rainfall_24h_delta: 40.0,
            rainfall_72h_delta: 80.0,
        },
    };

    var FEATURE_KEYS = [
        "rainfall_24h",
        "rainfall_72h",
        "rainfall_7d",
        "temperature",
        "wind_speed",
        "air_pressure",
        "elevation",
        "latitude",
        "longitude",
    ];

    function initSimulator() {
        setupEventListeners();
        updateDeltaBadges();
    }

    function setupEventListeners() {
        // Form submit
        var form = document.getElementById("simulator-form");
        if (form) {
            form.addEventListener("submit", function (e) {
                e.preventDefault();
                runSimulation();
            });
        }

        // Copy Baseline to Scenario button
        var copyBtn = document.getElementById("copy-baseline-btn");
        if (copyBtn) {
            copyBtn.addEventListener("click", function () {
                copyBaselineToScenario();
            });
        }

        // Preset scenario buttons
        var presetBtns = document.querySelectorAll(".preset-btn");
        presetBtns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                var presetId = btn.getAttribute("data-preset");
                applyPreset(presetId);
            });
        });

        // Station baseline selector
        var stationSelect = document.getElementById("station-baseline-select");
        if (stationSelect) {
            stationSelect.addEventListener("change", function (e) {
                var val = e.target.value;
                if (!val) return;
                try {
                    var feats = JSON.parse(val);
                    loadStationFeatures(feats);
                } catch (err) {
                    console.error("Failed to parse station features JSON", err);
                }
            });
        }

        // Listen for input changes in both current and scenario fields to update delta badges
        FEATURE_KEYS.forEach(function (key) {
            var currInput = document.getElementById("curr_" + key);
            var scenInput = document.getElementById("scen_" + key);

            if (currInput) {
                currInput.addEventListener("input", updateDeltaBadges);
            }
            if (scenInput) {
                scenInput.addEventListener("input", updateDeltaBadges);
            }
        });
    }

    function copyBaselineToScenario() {
        FEATURE_KEYS.forEach(function (key) {
            var currInput = document.getElementById("curr_" + key);
            var scenInput = document.getElementById("scen_" + key);
            if (currInput && scenInput) {
                scenInput.value = currInput.value;
            }
        });
        updateDeltaBadges();
    }

    function loadStationFeatures(feats) {
        FEATURE_KEYS.forEach(function (key) {
            if (feats[key] !== undefined) {
                var currInput = document.getElementById("curr_" + key);
                var scenInput = document.getElementById("scen_" + key);
                if (currInput) currInput.value = feats[key];
                if (scenInput) scenInput.value = feats[key];
            }
        });
        updateDeltaBadges();
    }

    function applyPreset(presetId) {
        var preset = PRESETS_DATA[presetId];
        if (!preset) return;

        // Start scenario from current baseline
        copyBaselineToScenario();

        // Apply deltas
        if (preset.rainfall_24h_delta) {
            var el24 = document.getElementById("scen_rainfall_24h");
            if (el24) el24.value = Math.max(0, (Number(el24.value) || 0) + preset.rainfall_24h_delta);
        }
        if (preset.rainfall_72h_delta) {
            var el72 = document.getElementById("scen_rainfall_72h");
            if (el72) el72.value = Math.max(0, (Number(el72.value) || 0) + preset.rainfall_72h_delta);
        }
        if (preset.rainfall_7d_delta) {
            var el7d = document.getElementById("scen_rainfall_7d");
            if (el7d) el7d.value = Math.max(0, (Number(el7d.value) || 0) + preset.rainfall_7d_delta);
        }
        if (preset.wind_speed_delta) {
            var elWind = document.getElementById("scen_wind_speed");
            if (elWind) elWind.value = Math.max(0, (Number(elWind.value) || 0) + preset.wind_speed_delta);
        }
        if (preset.air_pressure_delta) {
            var elPress = document.getElementById("scen_air_pressure");
            if (elPress) elPress.value = Math.max(500, (Number(elPress.value) || 1013) + preset.air_pressure_delta);
        }

        updateDeltaBadges();

        // Auto-run simulation when a preset is chosen
        runSimulation();
    }

    function updateDeltaBadges() {
        FEATURE_KEYS.forEach(function (key) {
            var currInput = document.getElementById("curr_" + key);
            var scenInput = document.getElementById("scen_" + key);
            var badge = document.getElementById("delta_" + key);

            if (currInput && scenInput && badge) {
                var cVal = Number(currInput.value) || 0;
                var sVal = Number(scenInput.value) || 0;
                var delta = roundTo(sVal - cVal, 2);

                if (Math.abs(delta) < 0.001) {
                    badge.textContent = "±0";
                    badge.className = "badge bg-secondary small text-xs";
                } else if (delta > 0) {
                    badge.textContent = "+" + delta;
                    badge.className = "badge bg-danger small text-xs";
                } else {
                    badge.textContent = "" + delta;
                    badge.className = "badge bg-info small text-xs";
                }
            }
        });
    }

    function collectPayload(prefix) {
        var obj = {};
        for (var i = 0; i < FEATURE_KEYS.length; i++) {
            var key = FEATURE_KEYS[i];
            var el = document.getElementById(prefix + "_" + key);
            if (!el || el.value.trim() === "") {
                return null;
            }
            var num = Number(el.value);
            if (isNaN(num)) {
                return null;
            }
            obj[key] = num;
        }
        return obj;
    }

    function getSelectedHazardFocus() {
        var radios = document.querySelectorAll('input[name="hazard_focus"]');
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].checked) {
                return radios[i].value;
            }
        }
        return "combined";
    }

    function getCsrfToken() {
        if (typeof window.getCsrfToken === "function") {
            return window.getCsrfToken();
        }
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function runSimulation() {
        hideError();

        var currentPayload = collectPayload("curr");
        var scenarioPayload = collectPayload("scen");

        if (!currentPayload || !scenarioPayload) {
            showError("Please enter valid numeric inputs for all environmental variables.");
            return;
        }

        var hazardType = getSelectedHazardFocus();
        var requestBody = {
            current: currentPayload,
            scenario: scenarioPayload,
            hazard_type: hazardType,
        };

        setLoading(true);

        fetch("/api/simulator/simulate", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
            body: JSON.stringify(requestBody),
        })
            .then(function (res) {
                if (res.status === 401) {
                    showError("Authentication required. Please log in.");
                    throw new Error("Unauthorized");
                }
                return res.json().then(function (data) {
                    return { status: res.status, data: data };
                });
            })
            .then(function (result) {
                setLoading(false);
                if (result.status !== 200 || !result.data.success) {
                    var msg = (result.data.errors && result.data.errors.join(", ")) || "Simulation failed.";
                    showError(msg);
                    return;
                }

                renderSimulationResults(result.data);
            })
            .catch(function (err) {
                setLoading(false);
                if (err.message !== "Unauthorized") {
                    showError("Simulation request failed: " + err.message);
                }
            });
    }

    function renderSimulationResults(data) {
        var section = document.getElementById("simulation-results-section");
        if (!section) return;

        section.style.display = "block";

        // Impact Banner
        var headline = document.getElementById("impact-headline");
        var pill = document.getElementById("impact-pill");

        if (headline) headline.textContent = data.impact_summary || "";
        if (pill) {
            if (data.impact_direction === "INCREASED") {
                pill.className = "badge bg-danger px-3 py-2 fs-6";
                pill.textContent = "▲ RISK INCREASED (+" + data.primary_delta_pct_points + "%)";
            } else if (data.impact_direction === "DECREASED") {
                pill.className = "badge bg-success px-3 py-2 fs-6";
                pill.textContent = "▼ RISK REDUCED (" + data.primary_delta_pct_points + "%)";
            } else {
                pill.className = "badge bg-secondary px-3 py-2 fs-6";
                pill.textContent = "■ NO CHANGE";
            }
        }

        // Combined Risk Card
        var comb = data.combined || {};
        setText("comb-curr-val", comb.current_risk !== undefined ? (comb.current_risk * 100).toFixed(1) + "%" : "--");
        setText("comb-scen-val", comb.simulated_risk !== undefined ? (comb.simulated_risk * 100).toFixed(1) + "%" : "--");
        setText("comb-level-shift", (comb.current_risk_level || "LOW") + " → " + (comb.simulated_risk_level || "LOW"));
        setText(
            "comb-delta-val",
            (comb.delta_pct_points >= 0 ? "+" : "") + comb.delta_pct_points + " pts (" + (comb.relative_change_pct >= 0 ? "+" : "") + comb.relative_change_pct + "%)"
        );

        // Flood Risk Card
        var flood = data.flood || {};
        setText("flood-curr-val", flood.current_probability !== undefined ? (flood.current_probability * 100).toFixed(1) + "%" : "--");
        setText("flood-scen-val", flood.simulated_probability !== undefined ? (flood.simulated_probability * 100).toFixed(1) + "%" : "--");
        setText("flood-level-shift", (flood.current_risk_level || "LOW") + " → " + (flood.simulated_risk_level || "LOW"));
        setText("flood-delta-val", (flood.delta_pct_points >= 0 ? "+" : "") + flood.delta_pct_points + " pts");

        // Landslide Risk Card
        var ls = data.landslide || {};
        setText("ls-curr-val", ls.current_probability !== undefined ? (ls.current_probability * 100).toFixed(1) + "%" : "--");
        setText("ls-scen-val", ls.simulated_probability !== undefined ? (ls.simulated_probability * 100).toFixed(1) + "%" : "--");
        setText("ls-level-shift", (ls.current_risk_level || "LOW") + " → " + (ls.simulated_risk_level || "LOW"));
        setText("ls-delta-val", (ls.delta_pct_points >= 0 ? "+" : "") + ls.delta_pct_points + " pts");

        // Feature Deltas Table
        var tbody = document.getElementById("sim-deltas-table-body");
        if (tbody && data.feature_deltas) {
            tbody.innerHTML = "";
            data.feature_deltas.forEach(function (item) {
                var tr = document.createElement("tr");
                var deltaClass = item.delta > 0 ? "text-danger" : (item.delta < 0 ? "text-info" : "text-muted");
                var deltaPrefix = item.delta > 0 ? "+" : "";

                tr.innerHTML = [
                    "<td><strong>" + escapeHtml(item.label) + "</strong></td>",
                    "<td>" + item.current_value + " " + escapeHtml(item.unit) + "</td>",
                    "<td>" + item.scenario_value + " " + escapeHtml(item.unit) + "</td>",
                    "<td class='" + deltaClass + " fw-bold'>" + deltaPrefix + item.delta + " " + escapeHtml(item.unit) + "</td>",
                ].join("");
                tbody.appendChild(tr);
            });
        }

        // Render Chart.js
        renderComparisonChart(data);

        // Wire PDF Report Download Button
        var btnDownloadReport = document.getElementById("btn-download-simulator-report");
        if (btnDownloadReport) {
            btnDownloadReport.onclick = function () {
                var scen = data.scenario_features || {};
                var comb = data.combined || {};
                var flood = data.flood || {};
                var ls = data.landslide || {};

                var url = "/api/reports/disaster?location_name=" + encodeURIComponent("Simulation Scenario Evaluation") +
                    "&latitude=" + encodeURIComponent(scen.latitude !== undefined ? scen.latitude : 30.0) +
                    "&longitude=" + encodeURIComponent(scen.longitude !== undefined ? scen.longitude : 77.0) +
                    "&elevation=" + encodeURIComponent(scen.elevation !== undefined ? scen.elevation : 500) +
                    "&rainfall_24h=" + encodeURIComponent(scen.rainfall_24h !== undefined ? scen.rainfall_24h : 0) +
                    "&rainfall_72h=" + encodeURIComponent(scen.rainfall_72h !== undefined ? scen.rainfall_72h : 0) +
                    "&rainfall_7d=" + encodeURIComponent(scen.rainfall_7d !== undefined ? scen.rainfall_7d : 0) +
                    "&temperature=" + encodeURIComponent(scen.temperature !== undefined ? scen.temperature : 25) +
                    "&wind_speed=" + encodeURIComponent(scen.wind_speed !== undefined ? scen.wind_speed : 10) +
                    "&air_pressure=" + encodeURIComponent(scen.air_pressure !== undefined ? scen.air_pressure : 1010) +
                    "&flood_probability=" + encodeURIComponent(flood.simulated_probability !== undefined ? flood.simulated_probability : 0) +
                    "&landslide_probability=" + encodeURIComponent(ls.simulated_probability !== undefined ? ls.simulated_probability : 0) +
                    "&combined_risk=" + encodeURIComponent(comb.simulated_risk !== undefined ? comb.simulated_risk : 0) +
                    "&risk_level=" + encodeURIComponent(comb.simulated_risk_level || "MODERATE");
                window.location.href = url;
            };
        }

        // Smooth scroll to results
        section.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function renderComparisonChart(data) {
        var canvas = document.getElementById("simComparisonChart");
        if (!canvas || typeof Chart === "undefined") return;

        var ctx = canvas.getContext("2d");

        if (comparisonChart) {
            comparisonChart.destroy();
        }

        var labels = ["Flood Hazard", "Landslide Hazard", "Combined Multi-Hazard"];
        var currentData = [
            (data.flood.current_probability || 0) * 100,
            (data.landslide.current_probability || 0) * 100,
            (data.combined.current_risk || 0) * 100,
        ];
        var scenarioData = [
            (data.flood.simulated_probability || 0) * 100,
            (data.landslide.simulated_probability || 0) * 100,
            (data.combined.simulated_risk || 0) * 100,
        ];

        comparisonChart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Current Baseline (%)",
                        data: currentData,
                        backgroundColor: "rgba(100, 116, 139, 0.7)",
                        borderColor: "#94a3b8",
                        borderWidth: 1.5,
                        borderRadius: 4,
                    },
                    {
                        label: "Simulated Scenario (%)",
                        data: scenarioData,
                        backgroundColor: "rgba(139, 92, 246, 0.8)",
                        borderColor: "#a855f7",
                        borderWidth: 1.5,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            color: "rgba(255, 255, 255, 0.08)",
                        },
                        ticks: {
                            color: "#94a3b8",
                            callback: function (val) {
                                return val + "%";
                            },
                        },
                    },
                    x: {
                        grid: {
                            display: false,
                        },
                        ticks: {
                            color: "#cbd5e1",
                            font: {
                                weight: "600",
                            },
                        },
                    },
                },
                plugins: {
                    legend: {
                        labels: {
                            color: "#e2e8f0",
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return context.dataset.label + ": " + Number(context.raw).toFixed(1) + "%";
                            },
                        },
                    },
                },
            },
        });
    }

    function setLoading(isLoading) {
        var spinner = document.getElementById("sim-btn-spinner");
        var btn = document.getElementById("run-sim-btn");
        if (spinner) spinner.className = isLoading ? "spinner-border spinner-border-sm" : "spinner-border spinner-border-sm d-none";
        if (btn) btn.disabled = isLoading;
    }

    function showError(msg) {
        var banner = document.getElementById("sim-error-banner");
        if (banner) {
            banner.textContent = msg;
            banner.style.display = "block";
        }
    }

    function hideError() {
        var banner = document.getElementById("sim-error-banner");
        if (banner) {
            banner.style.display = "none";
        }
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function roundTo(num, dec) {
        var factor = Math.pow(10, dec);
        return Math.round(num * factor) / factor;
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

    document.addEventListener("DOMContentLoaded", function () {
        initSimulator();
    });
})();

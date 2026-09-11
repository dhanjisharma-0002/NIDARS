/**
 * NIDARS — Weather Monitoring Client Logic
 * Handles station queries, GPS coordinates, Chart.js trends, and Leaflet weather network map.
 */
(function () {
    "use strict";

    var allStations = [];
    var weatherMap = null;
    var markersLayer = null;
    var tempChart = null;
    var rainChart = null;
    var windChart = null;

    var currentSelectedStation = "Shimla";

    // --- Load Available Stations ---
    function loadStations() {
        fetch("/api/weather/stations")
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data.success) return;
                allStations = data.stations || [];
                populateStationDropdown("ALL");
                initWeatherMap(allStations);
                // Load default weather
                loadWeatherForStation(currentSelectedStation);
            })
            .catch(function (err) {
                console.warn("Error loading station list:", err);
                loadWeatherForStation("Shimla");
            });
    }

    function populateStationDropdown(stateCode) {
        var select = document.getElementById("weather-station-select");
        if (!select) return;

        select.innerHTML = "";
        var filtered = allStations;
        if (stateCode && stateCode !== "ALL") {
            filtered = allStations.filter(function (s) { return s.state_code === stateCode; });
        }

        filtered.forEach(function (s) {
            var opt = document.createElement("option");
            opt.value = s.station_name;
            opt.textContent = s.station_name + " (" + s.state_code + ") — " + Math.round(s.elevation) + "m";
            if (s.station_name.toLowerCase() === currentSelectedStation.toLowerCase()) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
    }

    // --- Fetch Live Weather Data ---
    function loadWeatherForStation(stationName) {
        currentSelectedStation = stationName;
        fetchWeather("/api/weather?station=" + encodeURIComponent(stationName));
    }

    function loadWeatherForCoordinates(lat, lon, name) {
        var url = "/api/weather?lat=" + lat + "&lon=" + lon;
        if (name) url += "&name=" + encodeURIComponent(name);
        fetchWeather(url);
    }

    function fetchWeather(endpoint) {
        showLoadingState();

        fetch(endpoint)
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, data: data };
                });
            })
            .then(function (result) {
                if (!result.ok || !result.data.success) {
                    showErrorState(result.data.error || "Unable to fetch live meteorological data.");
                    return;
                }
                renderWeatherData(result.data);
            })
            .catch(function (err) {
                showErrorState("Network connection to weather service failed.");
            });
    }

    function showLoadingState() {
        var tempElem = document.getElementById("hero-temperature");
        if (tempElem) tempElem.innerHTML = '<span class="spinner-border spinner-border-sm text-info"></span>';
    }

    function showErrorState(msg) {
        var banner = document.getElementById("weather-alert-banner");
        if (banner) {
            banner.className = "alert alert-danger d-flex align-items-center justify-content-between py-2 px-3 mb-4 shadow-sm";
            document.getElementById("alert-icon").textContent = "⚠️";
            document.getElementById("alert-title").textContent = "WEATHER SERVICE NOTICE";
            document.getElementById("alert-advisory").textContent = msg;
            var badge = document.getElementById("alert-badge");
            badge.textContent = "SERVICE UNAVAILABLE";
            badge.className = "risk-badge critical";
        }
    }

    // --- Render Data on Dashboard ---
    function renderWeatherData(data) {
        var loc = data.location || {};
        var curr = data.current || {};
        var risks = data.risk_indicators || {};
        var trends = data.hourly_trends || {};

        // 1. Hero Card
        document.getElementById("hero-station-name").textContent = loc.station_name + " Station";
        document.getElementById("hero-station-region").textContent = 
            (loc.state_name || "North India") + " · District: " + (loc.district || "Regional") + " · Elev: " + Math.round(loc.elevation || 0) + "m";
        document.getElementById("hero-weather-icon").textContent = curr.icon || "☀️";
        document.getElementById("hero-temperature").innerHTML = 
            curr.temperature_c.toFixed(1) + '<span style="font-size: 2rem; color: var(--brand-accent);">°C</span>';
        document.getElementById("hero-feels-like").textContent = curr.feels_like_c.toFixed(1) + "°C";
        document.getElementById("hero-condition").textContent = curr.condition || "Fair";
        document.getElementById("badge-station-coords").textContent = 
            loc.latitude.toFixed(4) + "°N, " + loc.longitude.toFixed(4) + "°E";

        try {
            var dt = new Date(curr.last_updated);
            document.getElementById("hero-last-updated").textContent = "Updated: " + dt.toLocaleTimeString();
        } catch (e) {
            document.getElementById("hero-last-updated").textContent = "Updated: Just now";
        }

        // 2. Alert Banner
        var banner = document.getElementById("weather-alert-banner");
        var alertBadge = document.getElementById("alert-badge");
        var overallStatus = risks.overall_status || "LOW";

        if (overallStatus === "CRITICAL") {
            banner.className = "alert alert-danger d-flex align-items-center justify-content-between py-2 px-3 mb-4 shadow-sm";
            document.getElementById("alert-icon").textContent = "🚨";
            document.getElementById("alert-title").textContent = "SEVERE METEOROLOGICAL ALERT";
            alertBadge.className = "risk-badge critical";
        } else if (overallStatus === "HIGH") {
            banner.className = "alert alert-warning d-flex align-items-center justify-content-between py-2 px-3 mb-4 shadow-sm";
            document.getElementById("alert-icon").textContent = "⚠️";
            document.getElementById("alert-title").textContent = "ELEVATED WEATHER WARNING";
            alertBadge.className = "risk-badge high";
        } else if (overallStatus === "MODERATE") {
            banner.className = "alert alert-warning d-flex align-items-center justify-content-between py-2 px-3 mb-4 shadow-sm";
            document.getElementById("alert-icon").textContent = "🌦️";
            document.getElementById("alert-title").textContent = "WEATHER ADVISORY ACTIVE";
            alertBadge.className = "risk-badge moderate";
        } else {
            banner.className = "alert alert-success d-flex align-items-center justify-content-between py-2 px-3 mb-4 shadow-sm";
            document.getElementById("alert-icon").textContent = "🛡️";
            document.getElementById("alert-title").textContent = "NORMAL METEOROLOGICAL CONDITIONS";
            alertBadge.className = "risk-badge low";
        }
        alertBadge.textContent = overallStatus + " RISK";
        document.getElementById("alert-advisory").textContent = risks.advisory || "Normal baseline weather conditions.";

        // 3. Metric Cards
        document.getElementById("stat-rainfall-rate").innerHTML = 
            curr.precipitation_mm.toFixed(1) + ' <span style="font-size: 1rem; color: var(--text-muted);">mm/h</span>';
        document.getElementById("stat-rainfall-desc").textContent = risks.rainfall_description || "Normal (< 10 mm/day)";
        var rainBadge = document.getElementById("badge-rainfall-risk");
        rainBadge.textContent = risks.rainfall_alert || "NORMAL";
        rainBadge.className = "risk-badge " + (risks.rainfall_alert || "low").toLowerCase();

        document.getElementById("stat-humidity").innerHTML = 
            curr.relative_humidity_pct.toFixed(0) + '<span style="font-size: 1rem; color: var(--text-muted);">%</span>';

        document.getElementById("stat-wind-speed").innerHTML = 
            curr.wind_speed_ms.toFixed(1) + ' <span style="font-size: 1rem; color: var(--text-muted);">m/s</span>';
        document.getElementById("stat-wind-dir").textContent = 
            "Direction: " + Math.round(curr.wind_direction_deg) + "° (" + curr.wind_direction_cardinal + ") · " + curr.wind_speed_kmh.toFixed(1) + " km/h";
        var windBadge = document.getElementById("badge-wind-risk");
        windBadge.textContent = risks.wind_alert || "LIGHT";
        windBadge.className = "risk-badge " + (risks.wind_alert || "low").toLowerCase();

        document.getElementById("stat-pressure").innerHTML = 
            curr.air_pressure_hpa.toFixed(1) + ' <span style="font-size: 1rem; color: var(--text-muted);">hPa</span>';
        document.getElementById("stat-pressure-desc").textContent = risks.pressure_description || "Stable Surface Pressure";
        var pressBadge = document.getElementById("badge-pressure-risk");
        pressBadge.textContent = risks.pressure_alert || "STABLE";
        pressBadge.className = "risk-badge " + (risks.pressure_alert || "low").toLowerCase();

        // 4. Render Chart.js Trends
        renderTrendCharts(trends);
    }

    // --- Render Chart.js 24-Hour Trends ---
    function renderTrendCharts(trends) {
        var labels = trends.timestamps || [];
        var temps = trends.temperature || [];
        var rains = trends.precipitation || [];
        var winds = trends.wind_speed || [];

        // Temperature Chart
        var ctxTemp = document.getElementById("chart-weather-temp");
        if (ctxTemp && typeof Chart !== "undefined") {
            if (tempChart) tempChart.destroy();
            tempChart = new Chart(ctxTemp, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Temperature (°C)",
                        data: temps,
                        borderColor: "#38bdf8",
                        backgroundColor: "rgba(56, 189, 248, 0.12)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 2,
                        borderWidth: 2,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: "#94a3b8", maxTicksLimit: 6, font: { size: 10 } }, grid: { display: false } },
                        y: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.06)" } }
                    }
                }
            });
        }

        // Precipitation Chart
        var ctxRain = document.getElementById("chart-weather-rain");
        if (ctxRain && typeof Chart !== "undefined") {
            if (rainChart) rainChart.destroy();
            rainChart = new Chart(ctxRain, {
                type: "bar",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Hourly Rain (mm)",
                        data: rains,
                        backgroundColor: "#06b6d4",
                        borderRadius: 3,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: "#94a3b8", maxTicksLimit: 6, font: { size: 10 } }, grid: { display: false } },
                        y: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.06)" }, beginAtZero: true }
                    }
                }
            });
        }

        // Wind Chart
        var ctxWind = document.getElementById("chart-weather-wind");
        if (ctxWind && typeof Chart !== "undefined") {
            if (windChart) windChart.destroy();
            windChart = new Chart(ctxWind, {
                type: "line",
                data: {
                    labels: labels,
                    datasets: [{
                        label: "Wind Speed (m/s)",
                        data: winds,
                        borderColor: "#f59e0b",
                        backgroundColor: "rgba(245, 158, 11, 0.12)",
                        fill: true,
                        tension: 0.35,
                        pointRadius: 2,
                        borderWidth: 2,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { color: "#94a3b8", maxTicksLimit: 6, font: { size: 10 } }, grid: { display: false } },
                        y: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.06)" }, beginAtZero: true }
                    }
                }
            });
        }
    }

    // --- Initialize Leaflet Weather Map ---
    function initWeatherMap(stations) {
        var mapElem = document.getElementById("weather-stations-map");
        if (!mapElem || typeof L === "undefined") return;

        var northIndiaCenter = [30.0, 78.5];
        weatherMap = L.map("weather-stations-map", {
            scrollWheelZoom: false,
        }).setView(northIndiaCenter, 6);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors | NIDARS Weather',
            maxZoom: 19,
        }).addTo(weatherMap);

        markersLayer = L.layerGroup().addTo(weatherMap);

        stations.forEach(function (st) {
            var marker = L.circleMarker([st.latitude, st.longitude], {
                radius: 6,
                fillColor: "#38bdf8",
                color: "#ffffff",
                weight: 1,
                opacity: 0.9,
                fillOpacity: 0.85,
            }).addTo(markersLayer);

            var popupContent = `
                <div style="font-size: 0.8rem; line-height: 1.4;">
                    <strong style="color: #38bdf8;">${st.station_name} Station</strong>
                    <div style="color: #94a3b8; font-size: 0.72rem; margin-bottom: 4px;">${st.state_name} &middot; ${st.district}</div>
                    <div style="display:flex; justify-content:space-between; gap:10px;">
                        <span>Elevation:</span> <strong>${Math.round(st.elevation)}m</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; gap:10px;">
                        <span>Coordinates:</span> <span>${st.latitude.toFixed(2)}°N, ${st.longitude.toFixed(2)}°E</span>
                    </div>
                    <button class="btn btn-xs btn-outline-custom w-100 mt-2 btn-map-select-station" data-station="${st.station_name}">
                        Load Live Weather
                    </button>
                </div>
            `;
            marker.bindPopup(popupContent);
        });

        // Delegate popup button clicks
        weatherMap.on("popupopen", function () {
            var btns = document.querySelectorAll(".btn-map-select-station");
            btns.forEach(function (btn) {
                btn.addEventListener("click", function () {
                    var stName = btn.getAttribute("data-station");
                    if (stName) {
                        var select = document.getElementById("weather-station-select");
                        if (select) select.value = stName;
                        loadWeatherForStation(stName);
                        weatherMap.closePopup();
                    }
                });
            });
        });

        setTimeout(function () {
            weatherMap.invalidateSize();
        }, 300);
    }

    // --- Setup Event Listeners ---
    function setupEventListeners() {
        // State Filter Change
        var stateSelect = document.getElementById("weather-state-select");
        if (stateSelect) {
            stateSelect.addEventListener("change", function () {
                var selectedState = stateSelect.value;
                populateStationDropdown(selectedState);
                var select = document.getElementById("weather-station-select");
                if (select && select.value) {
                    loadWeatherForStation(select.value);
                }
            });
        }

        // Station Select Change
        var stationSelect = document.getElementById("weather-station-select");
        if (stationSelect) {
            stationSelect.addEventListener("change", function () {
                loadWeatherForStation(stationSelect.value);
            });
        }

        // Search Input (Enter key or input match)
        var searchInput = document.getElementById("weather-search-input");
        if (searchInput) {
            searchInput.addEventListener("keypress", function (e) {
                if (e.key === "Enter") {
                    var q = searchInput.value.trim().toLowerCase();
                    var match = allStations.find(function (s) {
                        return s.station_name.toLowerCase().includes(q) || s.district.toLowerCase().includes(q);
                    });
                    if (match) {
                        var select = document.getElementById("weather-station-select");
                        if (select) select.value = match.station_name;
                        loadWeatherForStation(match.station_name);
                    }
                }
            });
        }

        // Refresh Button
        var btnRefresh = document.getElementById("btn-refresh-weather");
        if (btnRefresh) {
            btnRefresh.addEventListener("click", function () {
                loadWeatherForStation(currentSelectedStation);
            });
        }

        // GPS Location Button
        var btnGps = document.getElementById("btn-weather-gps");
        if (btnGps) {
            btnGps.addEventListener("click", function () {
                var spinner = document.getElementById("gps-spinner");
                if (spinner) spinner.classList.remove("d-none");
                btnGps.disabled = true;

                if (!navigator.geolocation) {
                    alert("Geolocation is not supported by your browser.");
                    if (spinner) spinner.classList.add("d-none");
                    btnGps.disabled = false;
                    return;
                }

                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        if (spinner) spinner.classList.add("d-none");
                        btnGps.disabled = false;
                        var lat = pos.coords.latitude;
                        var lon = pos.coords.longitude;
                        loadWeatherForCoordinates(lat, lon, "Your GPS Location");
                    },
                    function (err) {
                        if (spinner) spinner.classList.add("d-none");
                        btnGps.disabled = false;
                        alert("Unable to acquire GPS coordinates: " + err.message);
                    },
                    { timeout: 8000 }
                );
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        setupEventListeners();
        loadStations();
    });
})();

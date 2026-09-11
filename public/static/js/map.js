/**
 * NIDARS — Phase 11: Advanced GIS Intelligence Command Center
 * Multi-layer GIS engine with 10 toggleable layers, ML risk heatmaps,
 * professional popups, real-time statistics HUD, and advanced geospatial controls.
 */

(function () {
    "use strict";

    // Core Map & Layer State
    var map = null;
    var layers = {
        combined_risk: null,
        flood_risk: null,
        landslide_risk: null,
        weather_stations: null,
        hospitals: null,
        police: null,
        shelters: null,
        route: null,
        district_boundaries: null,
        rivers: null,
        citizen_incidents: null,
    };

    var heatmapLayer = null;
    var userLocationMarker = null;
    var userAccuracyCircle = null;

    // Data Caches
    var rawGeojsonData = null;
    var rawRiversData = null;
    var rawBoundariesData = null;
    var rawFacilitiesData = null;
    var rawIncidentsData = null;

    // Active Filters & States
    var currentHazard = "combined";
    var currentState = "ALL";
    var currentDistrict = "ALL";
    var currentRiskLevel = "ALL";
    var searchQuery = "";
    var currentHeatmapMode = "combined";
    var isHeatmapActive = false;
    var heatmapRadius = 32;

    var RISK_COLORS = {
        LOW: "#22c55e",
        MODERATE: "#f59e0b",
        HIGH: "#ef4444",
        CRITICAL: "#a855f7",
    };

    var RISK_RADII = {
        LOW: 8,
        MODERATE: 10,
        HIGH: 12,
        CRITICAL: 14,
    };

    var NORTH_INDIA_CENTER = [29.5, 79.5];
    var NORTH_INDIA_ZOOM = 6;

    // --- Initialization ---

    function initGisMap() {
        var mapContainer = document.getElementById("map");
        if (!mapContainer || typeof L === "undefined") {
            return;
        }

        map = L.map("map", {
            center: NORTH_INDIA_CENTER,
            zoom: NORTH_INDIA_ZOOM,
            minZoom: 4,
            maxZoom: 18,
            zoomControl: true,
        });

        // OpenStreetMap Dark Theme Tile Layer
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors | NIDARS GIS Intelligence',
        }).addTo(map);

        // Initialize Layer Groups
        layers.combined_risk = L.layerGroup().addTo(map);
        layers.flood_risk = L.layerGroup();
        layers.landslide_risk = L.layerGroup();
        layers.weather_stations = L.layerGroup().addTo(map);
        layers.hospitals = L.layerGroup().addTo(map);
        layers.police = L.layerGroup();
        layers.shelters = L.layerGroup();
        layers.route = L.layerGroup().addTo(map);
        layers.district_boundaries = L.layerGroup().addTo(map);
        layers.rivers = L.layerGroup().addTo(map);
        layers.citizen_incidents = L.layerGroup().addTo(map);

        window.setTimeout(function () {
            map.invalidateSize();
        }, 250);

        setupEventListeners();
        fetchAllGisLayers();
    }

    // --- Event Listeners & UI Binding ---

    function setupEventListeners() {
        // Hazard Model Selector
        var hazardSelect = document.getElementById("hazard-mode-select");
        if (hazardSelect) {
            hazardSelect.addEventListener("change", function (e) {
                currentHazard = e.target.value;
                updateLegend();
                fetchGisRiskData();
            });
        }

        // State Geographic Filter
        var stateSelect = document.getElementById("state-filter-select");
        if (stateSelect) {
            stateSelect.addEventListener("change", function (e) {
                currentState = e.target.value;
                currentDistrict = "ALL";
                populateDistrictDropdown();
                applyClientFilters();
            });
        }

        // District Filter
        var districtSelect = document.getElementById("district-filter-select");
        if (districtSelect) {
            districtSelect.addEventListener("change", function (e) {
                currentDistrict = e.target.value;
                applyClientFilters();
            });
        }

        // Station Quick Jump
        var stationJumpSelect = document.getElementById("station-jump-select");
        if (stationJumpSelect) {
            stationJumpSelect.addEventListener("change", function (e) {
                var stationName = e.target.value;
                if (!stationName) return;
                jumpToStation(stationName);
            });
        }

        // Search Input with Debouncing
        var searchInput = document.getElementById("station-search-input");
        if (searchInput) {
            var searchDebounceTimer = null;
            searchInput.addEventListener("input", function (e) {
                clearTimeout(searchDebounceTimer);
                searchDebounceTimer = setTimeout(function () {
                    searchQuery = e.target.value.trim().toLowerCase();
                    applyClientFilters();
                }, 200);
            });
        }

        // Clear Search Button
        var clearSearchBtn = document.getElementById("clear-search-btn");
        if (clearSearchBtn) {
            clearSearchBtn.addEventListener("click", function () {
                if (searchInput) {
                    searchInput.value = "";
                    searchQuery = "";
                    applyClientFilters();
                }
            });
        }

        // Risk Filter Buttons
        var levelButtons = document.querySelectorAll(".risk-filter-btn");
        levelButtons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                levelButtons.forEach(function (b) { b.classList.remove("active"); });
                btn.classList.add("active");
                currentRiskLevel = btn.getAttribute("data-level") || "ALL";
                applyClientFilters();
            });
        });

        // Layer Toggle Switches
        var layerSwitches = document.querySelectorAll(".layer-toggle");
        layerSwitches.forEach(function (sw) {
            sw.addEventListener("change", function (e) {
                var layerKey = sw.getAttribute("data-layer");
                var isChecked = sw.checked;
                toggleMapLayer(layerKey, isChecked);
                updateActiveLayersBadge();
            });
        });

        // Heatmap Toggle Switch
        var heatmapSwitch = document.getElementById("toggle-heatmap-switch");
        var heatmapOptionsBox = document.getElementById("heatmap-options-box");
        if (heatmapSwitch) {
            heatmapSwitch.addEventListener("change", function (e) {
                isHeatmapActive = e.target.checked;
                if (heatmapOptionsBox) {
                    heatmapOptionsBox.style.display = isHeatmapActive ? "block" : "none";
                }
                renderHeatmap();
            });
        }

        // Heatmap Mode Buttons
        var heatmapModeButtons = document.querySelectorAll(".heatmap-mode-btn");
        heatmapModeButtons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                heatmapModeButtons.forEach(function (b) { b.classList.remove("active"); });
                btn.classList.add("active");
                currentHeatmapMode = btn.getAttribute("data-mode") || "combined";
                renderHeatmap();
            });
        });

        // Heatmap Radius Slider
        var heatmapRadiusSlider = document.getElementById("heatmap-radius-slider");
        if (heatmapRadiusSlider) {
            heatmapRadiusSlider.addEventListener("input", function (e) {
                heatmapRadius = parseInt(e.target.value, 10) || 32;
                renderHeatmap();
            });
        }

        // Refresh Map Button
        var refreshBtn = document.getElementById("refresh-map-btn");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", function () {
                fetchAllGisLayers();
            });
        }

        // Reset Map View Button
        var resetBtn = document.getElementById("map-reset-btn");
        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                map.flyTo(NORTH_INDIA_CENTER, NORTH_INDIA_ZOOM, { duration: 1.2 });
            });
        }

        // Fullscreen Button
        var fullscreenBtn = document.getElementById("map-fullscreen-btn");
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener("click", function () {
                toggleMapFullscreen();
            });
        }

        // Locate User GPS Button
        var locateBtn = document.getElementById("locate-user-btn");
        if (locateBtn) {
            locateBtn.addEventListener("click", function () {
                locateUserPosition();
            });
        }
    }

    // --- Layer Management ---

    function toggleMapLayer(layerKey, isVisible) {
        var layerGroup = layers[layerKey];
        if (!layerGroup || !map) return;

        if (isVisible) {
            if (!map.hasLayer(layerGroup)) {
                map.addLayer(layerGroup);
            }
        } else {
            if (map.hasLayer(layerGroup)) {
                map.removeLayer(layerGroup);
            }
        }
    }

    function updateActiveLayersBadge() {
        var count = 0;
        Object.keys(layers).forEach(function (k) {
            if (layers[k] && map.hasLayer(layers[k])) {
                count++;
            }
        });
        if (isHeatmapActive) count++;

        var badge = document.getElementById("active-layers-badge");
        if (badge) {
            badge.textContent = "Active: " + count;
        }
    }

    // --- Data Fetching Engine ---

    function fetchAllGisLayers() {
        showLoading(true, "Loading Spatial Intelligence Grid...");
        Promise.all([
            fetchGisRiskDataPromise(),
            fetchGisStatsPromise(),
            fetchGisFacilitiesPromise(),
            fetchGisRiversPromise(),
            fetchGisBoundariesPromise(),
            fetchGisIncidentsPromise(),
        ]).then(function () {
            showLoading(false);
            populateStationJumpDropdown();
            populateDistrictDropdown();
            applyClientFilters();
            renderDistrictBoundaries();
            renderRiversLayer();
            renderFacilitiesLayer();
            renderCitizenIncidentsLayer();
            renderHeatmap();
            updateActiveLayersBadge();
        }).catch(function (err) {
            showLoading(false);
            showError("GIS Layer Synchronization Notice: " + (err.message || "Loaded cached spatial layers."));
        });
    }

    function fetchGisRiskDataPromise() {
        var url = "/api/gis/risk?hazard=" + encodeURIComponent(currentHazard);
        return fetch(url)
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP error " + res.status);
                return res.json();
            })
            .then(function (geojson) {
                rawGeojsonData = geojson;
            });
    }

    function fetchGisRiskData() {
        showLoading(true, "Evaluating ML Hazard Models...");
        fetchGisRiskDataPromise()
            .then(function () {
                return fetchGisStatsPromise();
            })
            .then(function () {
                showLoading(false);
                applyClientFilters();
                renderHeatmap();
            })
            .catch(function () {
                showLoading(false);
            });
    }

    function fetchGisStatsPromise() {
        var url = "/api/gis/stats?hazard=" + encodeURIComponent(currentHazard);
        return fetch(url)
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (stats) {
                if (stats && stats.success) {
                    updateTopStatsHud(stats);
                }
            })
            .catch(function () {});
    }

    function fetchGisFacilitiesPromise() {
        return fetch("/api/gis/facilities?type=all")
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (facilitiesGeojson) {
                rawFacilitiesData = facilitiesGeojson;
            })
            .catch(function () {});
    }

    function fetchGisRiversPromise() {
        return fetch("/api/gis/rivers")
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (riversGeojson) {
                rawRiversData = riversGeojson;
            })
            .catch(function () {});
    }

    function fetchGisBoundariesPromise() {
        return fetch("/api/gis/boundaries")
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (boundariesGeojson) {
                rawBoundariesData = boundariesGeojson;
            })
            .catch(function () {});
    }

    function fetchGisIncidentsPromise() {
        return fetch("/api/gis/incidents")
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (incidentsGeojson) {
                rawIncidentsData = incidentsGeojson;
            })
            .catch(function () {});
    }

    // --- Station & Feature Rendering with Client Filtering ---

    function applyClientFilters() {
        if (!rawGeojsonData || !rawGeojsonData.features) return;

        // Clear marker layers
        if (layers.combined_risk) layers.combined_risk.clearLayers();
        if (layers.flood_risk) layers.flood_risk.clearLayers();
        if (layers.landslide_risk) layers.landslide_risk.clearLayers();
        if (layers.weather_stations) layers.weather_stations.clearLayers();

        var features = rawGeojsonData.features;
        var visibleCount = 0;
        var lowCount = 0;
        var modCount = 0;
        var highCount = 0;
        var critCount = 0;

        features.forEach(function (feature) {
            var props = feature.properties || {};
            var coords = feature.geometry.coordinates; // [lon, lat]

            // State filter
            if (currentState !== "ALL") {
                if (props.state !== currentState && props.state_name !== currentState) {
                    return;
                }
            }

            // District filter
            if (currentDistrict !== "ALL") {
                if ((props.district || "").toUpperCase() !== currentDistrict.toUpperCase()) {
                    return;
                }
            }

            // Risk level filter
            var riskLevel = (props.risk_level || "LOW").toUpperCase();
            if (currentRiskLevel !== "ALL" && riskLevel !== currentRiskLevel) {
                return;
            }

            // Search query filter (station name, district)
            if (searchQuery) {
                var stationName = (props.station || "").toLowerCase();
                var districtName = (props.district || "").toLowerCase();
                if (stationName.indexOf(searchQuery) === -1 && districtName.indexOf(searchQuery) === -1) {
                    return;
                }
            }

            visibleCount++;
            if (riskLevel === "LOW") lowCount++;
            else if (riskLevel === "MODERATE") modCount++;
            else if (riskLevel === "HIGH") highCount++;
            else if (riskLevel === "CRITICAL") critCount++;

            // Create Visual Markers for each Risk Layer
            renderStationRiskMarkers(props, coords, riskLevel);
        });

        // Update Top HUD Counter displays with active filtered counts
        updateFilteredStatsHud(visibleCount, lowCount, modCount, highCount, critCount);
    }

    function renderStationRiskMarkers(props, coords, riskLevel) {
        var lat = coords[1];
        var lon = coords[0];
        var color = RISK_COLORS[riskLevel] || "#22c55e";
        var radius = RISK_RADII[riskLevel] || 8;

        var popupContent = buildStationPopupHtml(props, coords, color);

        // 1. Combined Risk Marker
        if (layers.combined_risk) {
            var combMarker = L.circleMarker([lat, lon], {
                radius: radius,
                fillColor: color,
                color: "#ffffff",
                weight: 1.5,
                opacity: 0.95,
                fillOpacity: 0.85,
            });
            combMarker.bindTooltip(
                "<strong>" + escapeHtml(props.station) + "</strong> (" + escapeHtml(props.state) + ")<br/>" +
                "Combined Risk: <span style='color:" + color + "; font-weight:700;'>" + riskLevel + " (" + Number(props.combined_risk).toFixed(3) + ")</span>",
                { direction: "top", offset: [0, -6] }
            );
            combMarker.bindPopup(popupContent, { maxWidth: 330, minWidth: 280, className: "nidars-gis-popup" });
            combMarker.addTo(layers.combined_risk);
        }

        // 2. Flood Risk Marker
        if (layers.flood_risk) {
            var floodLevel = props.flood_risk_level || riskLevel;
            var floodColor = RISK_COLORS[floodLevel] || "#06b6d4";
            var floodMarker = L.circleMarker([lat, lon], {
                radius: radius,
                fillColor: floodColor,
                color: "#ffffff",
                weight: 1.5,
                opacity: 0.95,
                fillOpacity: 0.85,
            });
            floodMarker.bindTooltip(
                "<strong>" + escapeHtml(props.station) + "</strong><br/>" +
                "Flood P(flood): <span style='color:" + floodColor + "; font-weight:700;'>" + Number(props.flood_probability).toFixed(3) + "</span>",
                { direction: "top", offset: [0, -6] }
            );
            floodMarker.bindPopup(popupContent, { maxWidth: 330, minWidth: 280, className: "nidars-gis-popup" });
            floodMarker.addTo(layers.flood_risk);
        }

        // 3. Landslide Risk Marker
        if (layers.landslide_risk) {
            var lsLevel = props.landslide_risk_level || riskLevel;
            var lsColor = RISK_COLORS[lsLevel] || "#f59e0b";
            var lsMarker = L.circleMarker([lat, lon], {
                radius: radius,
                fillColor: lsColor,
                color: "#ffffff",
                weight: 1.5,
                opacity: 0.95,
                fillOpacity: 0.85,
            });
            lsMarker.bindTooltip(
                "<strong>" + escapeHtml(props.station) + "</strong><br/>" +
                "Landslide P(ls): <span style='color:" + lsColor + "; font-weight:700;'>" + Number(props.landslide_probability).toFixed(4) + "</span>",
                { direction: "top", offset: [0, -6] }
            );
            lsMarker.bindPopup(popupContent, { maxWidth: 330, minWidth: 280, className: "nidars-gis-popup" });
            lsMarker.addTo(layers.landslide_risk);
        }

        // 4. Weather Station Observation Marker
        if (layers.weather_stations) {
            var stationIcon = L.divIcon({
                className: "custom-station-icon",
                html: "<div style='background: rgba(6, 182, 212, 0.25); border: 2px solid #06b6d4; border-radius: 50%; width: 22px; height: 22px; display:flex; align-items:center; justify-content:center; font-size:12px;'>🌦️</div>",
                iconSize: [22, 22],
                iconAnchor: [11, 11],
            });
            var stationMarker = L.marker([lat, lon], { icon: stationIcon });
            stationMarker.bindTooltip(
                "<strong>" + escapeHtml(props.station) + " Met Station</strong><br/>" +
                "24h Rain: " + props.rainfall_24h + " mm | Temp: " + props.temperature + " &deg;C",
                { direction: "top", offset: [0, -10] }
            );
            stationMarker.bindPopup(popupContent, { maxWidth: 330, minWidth: 280, className: "nidars-gis-popup" });
            stationMarker.addTo(layers.weather_stations);
        }
    }

    // --- Authentic Emergency Facilities Layer Rendering ---

    function renderFacilitiesLayer() {
        if (!rawFacilitiesData || !rawFacilitiesData.features) return;

        if (layers.hospitals) layers.hospitals.clearLayers();
        if (layers.police) layers.police.clearLayers();
        if (layers.shelters) layers.shelters.clearLayers();

        rawFacilitiesData.features.forEach(function (feat) {
            var props = feat.properties || {};
            var coords = feat.geometry.coordinates; // [lon, lat]
            var lat = coords[1];
            var lon = coords[0];
            var fType = (props.facility_type || "hospital").toLowerCase();

            var iconEmoji = "🏥";
            var iconBorderColor = "#ef4444";
            var targetLayer = layers.hospitals;

            if (fType === "police") {
                iconEmoji = "🚓";
                iconBorderColor = "#3b82f6";
                targetLayer = layers.police;
            } else if (fType === "shelter") {
                iconEmoji = "🏠";
                iconBorderColor = "#10b981";
                targetLayer = layers.shelters;
            }

            var facIcon = L.divIcon({
                className: "facility-marker-icon",
                html: "<div style='background: rgba(15, 23, 42, 0.85); border: 2px solid " + iconBorderColor + "; border-radius: 50%; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; font-size: 13px; box-shadow: 0 2px 8px rgba(0,0,0,0.5);'>" + iconEmoji + "</div>",
                iconSize: [26, 26],
                iconAnchor: [13, 13],
            });

            var facMarker = L.marker([lat, lon], { icon: facIcon });

            var facPopupHtml = [
                "<div class='gis-popup-card'>",
                "  <div class='gis-popup-header'>",
                "    <div>",
                "      <h6 class='gis-popup-title mb-0'>" + escapeHtml(props.name) + "</h6>",
                "      <small class='text-muted'>" + escapeHtml(fType.toUpperCase()) + " &bull; Verified</small>",
                "    </div>",
                "    <span class='gis-badge' style='background:" + iconBorderColor + ";'>" + escapeHtml(fType) + "</span>",
                "  </div>",
                "  <div class='gis-popup-body'>",
                "    <div class='small mb-1'><strong>Address:</strong> <span class='text-light'>" + escapeHtml(props.address || "Not specified") + "</span></div>",
                "    <div class='small mb-1'><strong>Contact:</strong> <span class='text-info'>" + escapeHtml(props.phone || "112 / Emergency") + "</span></div>",
                "    <div class='small mb-2'><strong>Hours:</strong> <span class='text-muted'>" + escapeHtml(props.opening_hours || "24/7") + "</span></div>",
                "    <div class='d-grid gap-1 mt-2'>",
                "      <a href='/route-optimizer?dest_lat=" + lat + "&dest_lon=" + lon + "' class='btn btn-xs btn-primary'><span>🛣️</span> Route to Facility</a>",
                "    </div>",
                "  </div>",
                "</div>",
            ].join("");

            facMarker.bindPopup(facPopupHtml, { maxWidth: 300, minWidth: 250, className: "nidars-gis-popup" });
            facMarker.bindTooltip("<strong>" + escapeHtml(props.name) + "</strong> (" + fType.toUpperCase() + ")", { direction: "top", offset: [0, -12] });

            if (targetLayer) {
                facMarker.addTo(targetLayer);
            }
        });
    }

    // --- Authentic Hydrography Rivers Layer Rendering ---

    function renderRiversLayer() {
        if (!rawRiversData || !layers.rivers) return;
        layers.rivers.clearLayers();

        var riversGeoJsonLayer = L.geoJSON(rawRiversData, {
            style: function () {
                return {
                    color: "#38bdf8",
                    weight: 3.5,
                    opacity: 0.85,
                    dashArray: "6, 4",
                };
            },
            onEachFeature: function (feature, layer) {
                var props = feature.properties || {};
                layer.bindTooltip(
                    "<strong>🌊 " + escapeHtml(props.name || "River") + "</strong><br/>" +
                    "<span class='text-muted'>Basin:</span> " + escapeHtml(props.basin || "North India") + "<br/>" +
                    "<span class='text-muted'>Flood Risk:</span> <span class='text-warning'>" + escapeHtml(props.flood_vulnerability || "Monitored") + "</span>",
                    { direction: "center", sticky: true }
                );
            },
        });

        riversGeoJsonLayer.addTo(layers.rivers);
    }

    // --- Authentic District Boundaries Layer Rendering ---

    function renderDistrictBoundaries() {
        if (!rawBoundariesData || !layers.district_boundaries) return;
        layers.district_boundaries.clearLayers();

        var boundsLayer = L.geoJSON(rawBoundariesData, {
            style: function (feature) {
                var code = (feature.properties && feature.properties.state_code) || "";
                var strokeColor = "#3b82f6";
                if (code === "HP") strokeColor = "#10b981";
                if (code === "UP") strokeColor = "#f59e0b";
                if (code === "BR") strokeColor = "#a855f7";

                return {
                    color: strokeColor,
                    weight: 1.8,
                    opacity: 0.65,
                    fillColor: strokeColor,
                    fillOpacity: 0.04,
                    dashArray: "4, 4",
                };
            },
            onEachFeature: function (feature, layer) {
                var props = feature.properties || {};
                layer.bindTooltip(
                    "<strong>🗺️ " + escapeHtml(props.state_name || "Region") + "</strong> (" + escapeHtml(props.state_code || "") + ")<br/>" +
                    "<small class='text-muted'>" + escapeHtml(props.primary_hazard || "Disaster Monitoring Zone") + "</small>",
                    { sticky: true }
                );
            },
        });

        boundsLayer.addTo(layers.district_boundaries);
    }

    // --- Phase 15: Citizen Incident Reports Layer Rendering ---

    function renderCitizenIncidentsLayer() {
        if (!rawIncidentsData || !rawIncidentsData.features || !layers.citizen_incidents) return;
        layers.citizen_incidents.clearLayers();

        rawIncidentsData.features.forEach(function (feat) {
            var props = feat.properties || {};
            var coords = feat.geometry.coordinates; // [lon, lat]
            if (!coords || coords.length < 2) return;
            var lat = coords[1];
            var lon = coords[0];

            var isVerified = props.is_verified === true || props.status === "Verified";
            var severity = (props.severity || "Moderate").toUpperCase();
            var incidentType = props.incident_type || "Incident";
            var status = props.status || "Reported";

            // Determine visual styling based on verification and severity
            var markerBg = isVerified ? "rgba(16, 185, 129, 0.95)" : "rgba(245, 158, 11, 0.95)";
            var markerBorder = isVerified ? "#34d399" : "#fbbf24";
            var iconEmoji = isVerified ? "🛡️" : "⚠️";

            if (props.incident_type === "Flooded Road" || props.incident_type === "Waterlogging") {
                iconEmoji = isVerified ? "🌊" : "⚠️";
            } else if (props.incident_type === "Landslide") {
                iconEmoji = isVerified ? "⛰️" : "⚠️";
            } else if (props.incident_type === "Road Blockage" || props.incident_type === "Bridge Issue") {
                iconEmoji = isVerified ? "🚧" : "⚠️";
            }

            var incidentIcon = L.divIcon({
                className: "citizen-incident-marker",
                html: "<div style='background: " + (isVerified ? "rgba(6, 78, 59, 0.9)" : "rgba(120, 53, 15, 0.9)") + "; border: 2px solid " + markerBorder + "; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 0 10px " + (isVerified ? "rgba(16, 185, 129, 0.6)" : "rgba(245, 158, 11, 0.6)") + ";'>" + iconEmoji + "</div>",
                iconSize: [30, 30],
                iconAnchor: [15, 15],
            });

            var marker = L.marker([lat, lon], { icon: incidentIcon });

            var statusBadgeClass = "bg-warning text-dark";
            if (status === "Verified") statusBadgeClass = "bg-success text-white";
            else if (status === "Under Review") statusBadgeClass = "bg-info text-dark";
            else if (status === "Resolved") statusBadgeClass = "bg-secondary text-white";

            var severityBadgeClass = "bg-secondary";
            if (severity === "CRITICAL") severityBadgeClass = "bg-danger";
            else if (severity === "HIGH") severityBadgeClass = "bg-warning text-dark";
            else if (severity === "MODERATE") severityBadgeClass = "bg-info text-dark";
            else if (severity === "LOW") severityBadgeClass = "bg-success";

            var bannerHtml = isVerified ?
                "<div class='p-2 mb-2 rounded' style='background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; font-size: 0.76rem;'>" +
                "  <strong>🛡️ VERIFIED CITIZEN REPORT</strong>" +
                "  <div style='font-size: 0.68rem; opacity: 0.85;'>Verified by Emergency Disaster Coordination.</div>" +
                "</div>" :
                "<div class='p-2 mb-2 rounded' style='background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); color: #fbbf24; font-size: 0.76rem;'>" +
                "  <strong>⚠️ USER REPORTED — UNVERIFIED</strong>" +
                "  <div style='font-size: 0.68rem; opacity: 0.85;'>Community observation under administrative review.</div>" +
                "</div>";

            var photoHtml = "";
            if (props.photo_url) {
                photoHtml = "<div class='mt-2 mb-2 text-center'><a href='" + escapeHtml(props.photo_url) + "' target='_blank' rel='noopener noreferrer'><img src='" + escapeHtml(props.photo_url) + "' alt='Incident Photo' style='max-width: 100%; max-height: 120px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.15); object-fit: cover;' /></a><div class='text-muted small mt-1' style='font-size:0.65rem;'>Click to expand photo</div></div>";
            }

            var popupHtml = [
                "<div class='gis-popup-card' style='max-width: 290px;'>",
                "  <div class='gis-popup-header'>",
                "    <div>",
                "      <h6 class='gis-popup-title mb-0'>" + escapeHtml(props.incident_type || "Incident") + "</h6>",
                "      <small class='text-muted'>" + escapeHtml(props.location || "Observation Point") + "</small>",
                "    </div>",
                "    <span class='badge " + statusBadgeClass + "'>" + escapeHtml(status) + "</span>",
                "  </div>",
                "  <div class='gis-popup-body pt-2'>",
                bannerHtml,
                "    <div class='d-flex justify-content-between align-items-center mb-2'>",
                "      <span class='small text-muted'>Severity:</span>",
                "      <span class='badge " + severityBadgeClass + "'>" + escapeHtml(severity) + "</span>",
                "    </div>",
                "    <div class='small mb-2 text-light' style='line-height: 1.35;'>" + escapeHtml(props.description || "No additional description provided.") + "</div>",
                photoHtml,
                "    <div class='small text-muted mb-2' style='font-size: 0.7rem;'>",
                "      <div><strong>Coordinates:</strong> " + lat.toFixed(4) + "°N, " + lon.toFixed(4) + "°E</div>",
                "      <div><strong>Reported:</strong> " + escapeHtml(props.reported_at || "Recent") + "</div>",
                "    </div>",
                "    <div class='p-1 rounded bg-dark border border-secondary text-muted small text-center' style='font-size: 0.65rem;'>",
                "      <em>⚠️ User-reported incidents represent community observations and should not be interpreted as official government disaster advisories.</em>",
                "    </div>",
                "    <div class='d-grid gap-1 mt-2'>",
                "      <a href='/route-optimizer?dest_lat=" + lat + "&dest_lon=" + lon + "' class='btn btn-xs btn-outline-warning' style='font-size: 0.72rem;'><span>⚠️</span> Inspect Route Safety Around Area</a>",
                "    </div>",
                "  </div>",
                "</div>",
            ].join("");

            marker.bindPopup(popupHtml, { maxWidth: 310, minWidth: 260, className: "nidars-gis-popup" });
            marker.bindTooltip("<strong>" + escapeHtml(props.incident_type) + "</strong> &bull; " + (isVerified ? "Verified" : "User Report"), { direction: "top", offset: [0, -14] });

            marker.addTo(layers.citizen_incidents);
        });
    }

    // --- Heatmap Visualization Engine ---

    function renderHeatmap() {
        if (heatmapLayer && map.hasLayer(heatmapLayer)) {
            map.removeLayer(heatmapLayer);
            heatmapLayer = null;
        }

        if (!isHeatmapActive || !rawGeojsonData || !rawGeojsonData.features) {
            return;
        }

        if (typeof L.heatLayer !== "function") {
            console.warn("Leaflet.heat plugin not loaded, using circle marker representation.");
            return;
        }

        var heatPoints = [];
        rawGeojsonData.features.forEach(function (feat) {
            var coords = feat.geometry.coordinates; // [lon, lat]
            var props = feat.properties || {};
            var intensity = 0.5;

            if (currentHeatmapMode === "flood") {
                intensity = Math.min(1.0, Math.max(0.05, props.flood_probability || 0));
            } else if (currentHeatmapMode === "landslide") {
                // Scale landslide probability for heat intensity
                intensity = Math.min(1.0, Math.max(0.05, (props.landslide_probability || 0) * 4.0));
            } else {
                intensity = Math.min(1.0, Math.max(0.05, props.combined_risk || 0));
            }

            heatPoints.push([coords[1], coords[0], intensity]);
        });

        var gradientConfig = {
            0.2: "#06b6d4",
            0.4: "#22c55e",
            0.6: "#f59e0b",
            0.8: "#ef4444",
            1.0: "#a855f7",
        };

        if (currentHeatmapMode === "flood") {
            gradientConfig = { 0.2: "#38bdf8", 0.5: "#0284c7", 0.75: "#f59e0b", 1.0: "#ef4444" };
        } else if (currentHeatmapMode === "landslide") {
            gradientConfig = { 0.2: "#22c55e", 0.5: "#f59e0b", 0.8: "#ea580c", 1.0: "#dc2626" };
        }

        heatmapLayer = L.heatLayer(heatPoints, {
            radius: heatmapRadius,
            blur: 20,
            maxZoom: 12,
            max: 1.0,
            gradient: gradientConfig,
        });

        heatmapLayer.addTo(map);
    }

    // --- Station Popup Card HTML Builder ---

    function buildStationPopupHtml(props, coords, color) {
        var floodPct = Math.round((props.flood_probability || 0) * 100);
        var landslidePct = Math.round((props.landslide_probability || 0) * 100);
        var combinedPct = Math.round((props.combined_risk || 0) * 100);

        var activeRiskTitle = "Combined Risk";
        var activeScore = props.combined_risk;
        if (props.hazard === "flood") {
            activeRiskTitle = "Flood Risk";
            activeScore = props.flood_probability;
        } else if (props.hazard === "landslide") {
            activeRiskTitle = "Landslide Risk";
            activeScore = props.landslide_probability;
        }

        var lat = Number(coords[1]).toFixed(4);
        var lon = Number(coords[0]).toFixed(4);

        return [
            "<div class='gis-popup-card'>",
            "  <div class='gis-popup-header'>",
            "    <div>",
            "      <h6 class='gis-popup-title mb-0'>" + escapeHtml(props.station) + "</h6>",
            "      <small class='text-muted'>" + escapeHtml(props.district) + ", " + escapeHtml(props.state_name || props.state) + "</small>",
            "    </div>",
            "    <span class='gis-badge' style='background:" + color + ";'>" + escapeHtml(props.risk_level) + "</span>",
            "  </div>",
            "  <div class='gis-popup-body'>",
            "    <div class='d-flex justify-content-between align-items-center mb-2'>",
            "      <span class='small text-muted'>" + activeRiskTitle + ":</span>",
            "      <strong style='color:" + color + "; font-size:1rem;'>" + Number(activeScore).toFixed(4) + " (" + escapeHtml(props.risk_level) + ")</strong>",
            "    </div>",
            "    <div class='gis-bars'>",
            "      <div class='mb-1'>",
            "        <div class='d-flex justify-content-between small' style='font-size:0.75rem;'>",
            "          <span>🌊 P(Flood)</span><span>" + Number(props.flood_probability).toFixed(4) + "</span>",
            "        </div>",
            "        <div class='progress' style='height: 5px;'>",
            "          <div class='progress-bar bg-info' role='progressbar' style='width: " + Math.min(100, Math.max(0, floodPct)) + "%;'></div>",
            "        </div>",
            "      </div>",
            "      <div class='mb-1'>",
            "        <div class='d-flex justify-content-between small' style='font-size:0.75rem;'>",
            "          <span>⛰️ P(Landslide)</span><span>" + Number(props.landslide_probability).toFixed(4) + "</span>",
            "        </div>",
            "        <div class='progress' style='height: 5px;'>",
            "          <div class='progress-bar bg-warning' role='progressbar' style='width: " + Math.min(100, Math.max(0, landslidePct)) + "%;'></div>",
            "        </div>",
            "      </div>",
            "      <div class='mb-2'>",
            "        <div class='d-flex justify-content-between small' style='font-size:0.75rem;'>",
            "          <span>⚡ Combined Index</span><span>" + Number(props.combined_risk).toFixed(4) + "</span>",
            "        </div>",
            "        <div class='progress' style='height: 5px;'>",
            "          <div class='progress-bar' role='progressbar' style='width: " + Math.min(100, Math.max(0, combinedPct)) + "%; background-color:" + color + ";'></div>",
            "        </div>",
            "      </div>",
            "    </div>",
            "    <div class='gis-met-grid mb-2'>",
            "      <div><small class='text-muted'>24h Rain:</small> <strong>" + props.rainfall_24h + " mm</strong></div>",
            "      <div><small class='text-muted'>72h Rain:</small> <strong>" + props.rainfall_72h + " mm</strong></div>",
            "      <div><small class='text-muted'>7d Rain:</small> <strong>" + props.rainfall_7d + " mm</strong></div>",
            "      <div><small class='text-muted'>Temp:</small> <strong>" + props.temperature + " &deg;C</strong></div>",
            "      <div><small class='text-muted'>Elevation:</small> <strong>" + props.elevation_m + " m</strong></div>",
            "      <div><small class='text-muted'>Pressure:</small> <strong>" + props.air_pressure + " hPa</strong></div>",
            "    </div>",
            "    <div class='d-flex justify-content-between align-items-center text-muted small mb-2' style='font-size:0.7rem;'>",
            "      <span>Obs: " + escapeHtml(props.observation_date || "Live Observation") + "</span>",
            "      <span>Lat: " + lat + ", Lon: " + lon + "</span>",
            "    </div>",
            "    <div class='d-flex gap-1'>",
            "      <a href='/route-optimizer?dest_lat=" + lat + "&dest_lon=" + lon + "' class='btn btn-xs btn-primary flex-fill'><span>🛣️</span> Route Here</a>",
            "      <a href='/emergency?lat=" + lat + "&lon=" + lon + "' class='btn btn-xs btn-danger flex-fill'><span>🚨</span> Emergency</a>",
            "    </div>",
            "  </div>",
            "</div>",
        ].join("");
    }

    // --- Dynamic Dropdown Helpers ---

    function populateStationJumpDropdown() {
        var jumpSelect = document.getElementById("station-jump-select");
        if (!jumpSelect || !rawGeojsonData || !rawGeojsonData.features) return;

        jumpSelect.innerHTML = "<option value='' selected>Jump to Station (64)...</option>";
        var sorted = rawGeojsonData.features.slice().sort(function (a, b) {
            var nameA = (a.properties.station || "").toLowerCase();
            var nameB = (b.properties.station || "").toLowerCase();
            return nameA.localeCompare(nameB);
        });

        sorted.forEach(function (feat) {
            var props = feat.properties;
            var opt = document.createElement("option");
            opt.value = props.station;
            opt.textContent = props.station + " (" + props.state + " - " + props.district + ")";
            jumpSelect.appendChild(opt);
        });
    }

    function populateDistrictDropdown() {
        var distSelect = document.getElementById("district-filter-select");
        if (!distSelect || !rawGeojsonData || !rawGeojsonData.features) return;

        distSelect.innerHTML = "<option value='ALL' selected>All Districts</option>";
        var districtsSet = {};

        rawGeojsonData.features.forEach(function (feat) {
            var props = feat.properties || {};
            if (currentState !== "ALL" && props.state !== currentState && props.state_name !== currentState) {
                return;
            }
            if (props.district) {
                districtsSet[props.district] = true;
            }
        });

        var distList = Object.keys(districtsSet).sort();
        distList.forEach(function (d) {
            var opt = document.createElement("option");
            opt.value = d;
            opt.textContent = d;
            distSelect.appendChild(opt);
        });
    }

    function jumpToStation(stationName) {
        if (!rawGeojsonData || !rawGeojsonData.features) return;
        for (var i = 0; i < rawGeojsonData.features.length; i++) {
            var feat = rawGeojsonData.features[i];
            if (feat.properties && feat.properties.station === stationName) {
                var coords = feat.geometry.coordinates; // [lon, lat]
                map.flyTo([coords[1], coords[0]], 11, { duration: 1.2 });
                return;
            }
        }
    }

    // --- Geolocation & User Positioning ---

    function locateUserPosition() {
        if (!navigator.geolocation) {
            showError("Geolocation is not supported by your browser.");
            return;
        }

        showLoading(true, "Acquiring GPS Satellite Position...");
        navigator.geolocation.getCurrentPosition(
            function (pos) {
                showLoading(false);
                var lat = pos.coords.latitude;
                var lon = pos.coords.longitude;
                var accuracy = pos.coords.accuracy;

                if (userLocationMarker && map.hasLayer(userLocationMarker)) {
                    map.removeLayer(userLocationMarker);
                }
                if (userAccuracyCircle && map.hasLayer(userAccuracyCircle)) {
                    map.removeLayer(userAccuracyCircle);
                }

                userAccuracyCircle = L.circle([lat, lon], {
                    radius: accuracy,
                    color: "#3b82f6",
                    fillColor: "#3b82f6",
                    fillOpacity: 0.15,
                    weight: 1.5,
                }).addTo(map);

                var userIcon = L.divIcon({
                    className: "user-loc-icon",
                    html: "<div style='background: #3b82f6; border: 3px solid #ffffff; border-radius: 50%; width: 22px; height: 22px; box-shadow: 0 0 14px #3b82f6;'></div>",
                    iconSize: [22, 22],
                    iconAnchor: [11, 11],
                });

                userLocationMarker = L.marker([lat, lon], { icon: userIcon }).addTo(map);
                userLocationMarker.bindPopup(
                    "<div class='p-2 text-center'>" +
                    "  <strong class='text-info'>📍 Your Current Location</strong><br/>" +
                    "  <small class='text-muted'>Lat: " + lat.toFixed(4) + ", Lon: " + lon.toFixed(4) + "</small><br/>" +
                    "  <small class='text-muted'>GPS Accuracy: &plusmn;" + Math.round(accuracy) + " m</small><br/>" +
                    "  <a href='/emergency?lat=" + lat.toFixed(4) + "&lon=" + lon.toFixed(4) + "' class='btn btn-xs btn-danger-emergency mt-2 w-100'>🚨 Emergency Check Here</a>" +
                    "</div>",
                    { className: "nidars-gis-popup" }
                ).openPopup();

                map.flyTo([lat, lon], 10, { duration: 1.2 });
            },
            function (err) {
                showLoading(false);
                showError("Unable to acquire location: " + err.message);
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
        );
    }

    // --- Fullscreen Toggle ---

    function toggleMapFullscreen() {
        var mapContainer = document.querySelector(".map-command-layout");
        var iconEl = document.getElementById("fullscreen-icon");
        if (!mapContainer) return;

        if (!document.fullscreenElement) {
            if (mapContainer.requestFullscreen) {
                mapContainer.requestFullscreen();
            } else if (mapContainer.webkitRequestFullscreen) {
                mapContainer.webkitRequestFullscreen();
            }
            if (iconEl) iconEl.textContent = "✕";
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
            if (iconEl) iconEl.textContent = "⛶";
        }
        window.setTimeout(function () {
            map.invalidateSize();
        }, 200);
    }

    // --- Top HUD Statistics Updaters ---

    function updateTopStatsHud(stats) {
        if (!stats) return;
        var totalEl = document.getElementById("stat-monitored-stations");
        var lowEl = document.getElementById("stat-low-count");
        var modEl = document.getElementById("stat-mod-count");
        var highEl = document.getElementById("stat-high-count");
        var critEl = document.getElementById("stat-crit-count");

        if (totalEl) totalEl.textContent = stats.monitored_stations || 64;
        if (stats.risk_counts) {
            if (lowEl) lowEl.textContent = stats.risk_counts.low;
            if (modEl) modEl.textContent = stats.risk_counts.moderate;
            if (highEl) highEl.textContent = stats.risk_counts.high;
            if (critEl) critEl.textContent = stats.risk_counts.critical;
        }
    }

    function updateFilteredStatsHud(visible, low, mod, high, crit) {
        var lowEl = document.getElementById("stat-low-count");
        var modEl = document.getElementById("stat-mod-count");
        var highEl = document.getElementById("stat-high-count");
        var critEl = document.getElementById("stat-crit-count");

        if (lowEl) lowEl.textContent = low;
        if (modEl) modEl.textContent = mod;
        if (highEl) highEl.textContent = high;
        if (critEl) critEl.textContent = crit;
    }

    function updateLegend() {
        var legendSubtitle = document.getElementById("legend-hazard-subtitle");
        var legendLandslideNote = document.getElementById("legend-landslide-note");
        if (legendSubtitle) {
            if (currentHazard === "flood") {
                legendSubtitle.textContent = "Flood Risk Model (Random Forest)";
            } else if (currentHazard === "landslide") {
                legendSubtitle.textContent = "Landslide Risk Model (Gradient Boosting, Phase 4.1 thresholds)";
            } else {
                legendSubtitle.textContent = "Combined Joint Risk (50% Flood + 50% Landslide)";
            }
        }
        if (legendLandslideNote) {
            legendLandslideNote.style.display = (currentHazard === "landslide") ? "block" : "none";
        }
    }

    // --- Draggable, Resizable & Collapsible GIS Legend Control ---

    function initDraggableResizableLegend() {
        var legendEl = document.getElementById("gis-floating-legend");
        var headerEl = document.getElementById("gis-legend-header");
        if (!legendEl || !headerEl) return;

        // Prevent Leaflet map interactions through the legend
        if (typeof L !== "undefined" && L.DomEvent) {
            L.DomEvent.disableClickPropagation(legendEl);
            L.DomEvent.disableScrollPropagation(legendEl);
        }

        var decreaseBtn = document.getElementById("legend-decrease-btn");
        var increaseBtn = document.getElementById("legend-increase-btn");
        var resetBtn = document.getElementById("legend-reset-btn");
        var scaleLabel = document.getElementById("legend-scale-label");
        var collapseBtn = document.getElementById("legend-collapse-btn");
        var collapseIcon = document.getElementById("legend-collapse-icon");

        var SCALES = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5];
        var currentScaleIndex = 3; // default 1.0 (100%)
        var isCollapsed = false;

        var isDragging = false;
        var startPointerX = 0;
        var startPointerY = 0;
        var startLeft = 0;
        var startTop = 0;
        var activePointerId = null;

        // Restore persisted scale from localStorage
        try {
            var savedScale = localStorage.getItem("nidars_gis_legend_scale");
            if (savedScale) {
                var parsedScale = parseFloat(savedScale);
                for (var i = 0; i < SCALES.length; i++) {
                    if (Math.abs(SCALES[i] - parsedScale) < 0.05) {
                        currentScaleIndex = i;
                        break;
                    }
                }
            }
        } catch (e) {
            console.warn("Could not read legend scale from localStorage:", e);
        }

        // Restore persisted collapsed state from localStorage
        try {
            var savedCollapsed = localStorage.getItem("nidars_gis_legend_collapsed");
            if (savedCollapsed === "true") {
                isCollapsed = true;
            }
        } catch (e) {
            console.warn("Could not read legend collapsed state from localStorage:", e);
        }

        // Apply scale & collapsed initial state
        applyLegendScale(SCALES[currentScaleIndex], false);
        applyLegendCollapsed(isCollapsed, false);

        // Restore persisted position from localStorage
        restoreLegendPosition();

        // 1. Dragging Implementation via Pointer Events
        headerEl.addEventListener("pointerdown", function (e) {
            // Do not initiate drag if user clicked on control buttons
            if (e.target.closest(".legend-header-controls") || e.target.closest("button")) {
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            isDragging = true;
            activePointerId = e.pointerId;
            startPointerX = e.clientX;
            startPointerY = e.clientY;

            // Compute current offset relative to map viewport parent
            var viewport = document.querySelector(".map-viewport") || legendEl.parentElement;
            var viewportRect = viewport.getBoundingClientRect();
            var legendRect = legendEl.getBoundingClientRect();

            startLeft = legendRect.left - viewportRect.left;
            startTop = legendRect.top - viewportRect.top;

            legendEl.classList.add("is-dragging");

            try {
                headerEl.setPointerCapture(e.pointerId);
            } catch (err) {}

            if (map && map.dragging) {
                map.dragging.disable();
            }
        });

        headerEl.addEventListener("pointermove", function (e) {
            if (!isDragging || e.pointerId !== activePointerId) return;

            e.preventDefault();
            e.stopPropagation();

            var dx = e.clientX - startPointerX;
            var dy = e.clientY - startPointerY;

            var newLeft = startLeft + dx;
            var newTop = startTop + dy;

            clampAndSetLegendPosition(newLeft, newTop);
        });

        function handlePointerUp(e) {
            if (!isDragging) return;
            if (e && e.pointerId && activePointerId && e.pointerId !== activePointerId) return;

            isDragging = false;
            legendEl.classList.remove("is-dragging");

            if (activePointerId && headerEl.releasePointerCapture) {
                try {
                    headerEl.releasePointerCapture(activePointerId);
                } catch (err) {}
            }
            activePointerId = null;

            if (map && map.dragging) {
                map.dragging.enable();
            }

            saveLegendPosition();
        }

        headerEl.addEventListener("pointerup", handlePointerUp);
        headerEl.addEventListener("pointercancel", handlePointerUp);
        window.addEventListener("pointerup", handlePointerUp);

        // 2. Resize Controls Implementation
        if (decreaseBtn) {
            decreaseBtn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (currentScaleIndex > 0) {
                    currentScaleIndex--;
                    applyLegendScale(SCALES[currentScaleIndex], true);
                }
            });
        }

        if (increaseBtn) {
            increaseBtn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                if (currentScaleIndex < SCALES.length - 1) {
                    currentScaleIndex++;
                    applyLegendScale(SCALES[currentScaleIndex], true);
                }
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                currentScaleIndex = 3; // 100%
                applyLegendScale(SCALES[currentScaleIndex], true);
            });
        }

        // 3. Collapse / Expand Control Implementation
        if (collapseBtn) {
            collapseBtn.addEventListener("click", function (e) {
                e.preventDefault();
                e.stopPropagation();
                isCollapsed = !isCollapsed;
                applyLegendCollapsed(isCollapsed, true);
            });
        }

        function applyLegendScale(scale, shouldSave) {
            legendEl.style.transform = "scale(" + scale + ")";
            legendEl.style.transformOrigin = "top left";
            if (scaleLabel) {
                scaleLabel.textContent = Math.round(scale * 100) + "%";
            }
            if (shouldSave) {
                try {
                    localStorage.setItem("nidars_gis_legend_scale", scale.toString());
                } catch (e) {}
            }
            // Ensure scaling doesn't push legend out of map viewport
            var currentPos = getLegendCurrentPosition();
            clampAndSetLegendPosition(currentPos.left, currentPos.top);
        }

        function applyLegendCollapsed(collapsed, shouldSave) {
            if (collapsed) {
                legendEl.classList.add("collapsed");
                if (collapseIcon) collapseIcon.textContent = "▼";
                if (collapseBtn) collapseBtn.setAttribute("aria-label", "Expand legend");
            } else {
                legendEl.classList.remove("collapsed");
                if (collapseIcon) collapseIcon.textContent = "▲";
                if (collapseBtn) collapseBtn.setAttribute("aria-label", "Collapse legend");
            }
            if (shouldSave) {
                try {
                    localStorage.setItem("nidars_gis_legend_collapsed", collapsed ? "true" : "false");
                } catch (e) {}
            }
        }

        function clampAndSetLegendPosition(left, top) {
            var viewport = document.querySelector(".map-viewport") || legendEl.parentElement;
            if (!viewport) return;

            var viewportWidth = viewport.clientWidth;
            var viewportHeight = viewport.clientHeight;
            var scale = SCALES[currentScaleIndex] || 1.0;

            var legendWidth = legendEl.offsetWidth * scale;
            var legendHeight = legendEl.offsetHeight * scale;

            var minLeft = 10;
            var maxLeft = Math.max(minLeft, viewportWidth - legendWidth - 10);
            var minTop = 50; // below top HUD
            var maxTop = Math.max(minTop, viewportHeight - legendHeight - 10);

            var clampedLeft = Math.max(minLeft, Math.min(maxLeft, left));
            var clampedTop = Math.max(minTop, Math.min(maxTop, top));

            legendEl.style.left = clampedLeft + "px";
            legendEl.style.top = clampedTop + "px";
            legendEl.style.right = "auto";
            legendEl.style.bottom = "auto";
        }

        function getLegendCurrentPosition() {
            var viewport = document.querySelector(".map-viewport") || legendEl.parentElement;
            var viewportRect = viewport ? viewport.getBoundingClientRect() : { left: 0, top: 0 };
            var legendRect = legendEl.getBoundingClientRect();
            return {
                left: legendRect.left - viewportRect.left,
                top: legendRect.top - viewportRect.top,
            };
        }

        function saveLegendPosition() {
            try {
                var pos = getLegendCurrentPosition();
                localStorage.setItem("nidars_gis_legend_position", JSON.stringify({
                    left: Math.round(pos.left),
                    top: Math.round(pos.top),
                }));
            } catch (e) {}
        }

        function restoreLegendPosition() {
            try {
                var savedPos = localStorage.getItem("nidars_gis_legend_position");
                if (savedPos) {
                    var parsed = JSON.parse(savedPos);
                    if (typeof parsed.left === "number" && typeof parsed.top === "number") {
                        clampAndSetLegendPosition(parsed.left, parsed.top);
                        return;
                    }
                }
            } catch (e) {}

            // Default position: bottom right
            window.setTimeout(function () {
                var viewport = document.querySelector(".map-viewport") || legendEl.parentElement;
                if (viewport) {
                    var scale = SCALES[currentScaleIndex] || 1.0;
                    var defaultLeft = viewport.clientWidth - (legendEl.offsetWidth * scale) - 24;
                    var defaultTop = viewport.clientHeight - (legendEl.offsetHeight * scale) - 24;
                    clampAndSetLegendPosition(defaultLeft, defaultTop);
                }
            }, 100);
        }

        // Re-clamp on window resize
        window.addEventListener("resize", function () {
            var pos = getLegendCurrentPosition();
            clampAndSetLegendPosition(pos.left, pos.top);
        });
    }

    // --- UI Helpers ---

    function showLoading(isLoading, msg) {
        var loader = document.getElementById("map-loading-indicator");
        var msgEl = document.getElementById("loading-message");
        if (loader) {
            loader.style.display = isLoading ? "flex" : "none";
        }
        if (msgEl && msg) {
            msgEl.textContent = msg;
        }
    }

    function showError(msg) {
        var errorBanner = document.getElementById("map-error-banner");
        if (errorBanner) {
            errorBanner.textContent = msg;
            errorBanner.style.display = "block";
            window.setTimeout(function () {
                errorBanner.style.display = "none";
            }, 6000);
        }
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
        initGisMap();
        initDraggableResizableLegend();
    });
})();


/**
 * NIDARS — Phase 12: Multi-Route Intelligence Controller
 * Upgrades OSRM routing with multi-route comparison across Distance, Hazard Risks,
 * Safety Score, Coverage, and Risk-Adjusted Cost with Shortest, Safest, and Balanced modes.
 */

(function () {
    "use strict";

    var map = null;
    var routesLayer = null;
    var markersLayer = null;
    var currentRoutesData = null;
    var selectedRouteIdx = 0;
    var activeMode = "safest";
    var routePolylines = [];

    var MODE_DESCRIPTIONS = {
        safest: "🛡️ <em>Safest:</em> Prioritizes lowest risk-adjusted cost ($Distance + Distance \\times Penalty \\times Risk$).",
        shortest: "⚡ <em>Shortest:</em> Prioritizes minimum road travel distance regardless of hazard level.",
        balanced: "⚖️ <em>Balanced:</em> Optimal multi-objective compromise between distance and hazard mitigation.",
    };

    var COLOR_PALETTE = {
        safest: "#10b981",    // Emerald
        shortest: "#0ea5e9",  // Sky Blue
        balanced: "#a855f7",  // Purple
        alternative: "#94a3b8" // Slate
    };

    function initRoutingMap() {
        var container = document.getElementById("route-map");
        if (!container || typeof L === "undefined") {
            return;
        }

        var northIndiaCenter = [29.5, 79.5];
        map = L.map("route-map", {
            center: northIndiaCenter,
            zoom: 6,
            minZoom: 4,
            maxZoom: 18,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors | OSRM Driving | NIDARS Prototype',
        }).addTo(map);

        routesLayer = L.featureGroup().addTo(map);
        markersLayer = L.featureGroup().addTo(map);

        window.setTimeout(function () {
            map.invalidateSize();
        }, 250);

        setupEventListeners();
    }

    function setupEventListeners() {
        var form = document.getElementById("route-form");
        if (form) {
            form.addEventListener("submit", function (e) {
                e.preventDefault();
                findSafeRoute();
            });
        }

        var clearBtn = document.getElementById("clear-route-btn");
        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                clearRoute();
            });
        }

        // Mode Radio Selector
        var modeRadios = document.querySelectorAll('input[name="routing_mode"]');
        modeRadios.forEach(function (radio) {
            radio.addEventListener("change", function (e) {
                if (e.target.checked) {
                    activeMode = e.target.value;
                    var descEl = document.getElementById("mode-description-text");
                    if (descEl && MODE_DESCRIPTIONS[activeMode]) {
                        descEl.innerHTML = MODE_DESCRIPTIONS[activeMode];
                    }

                    if (currentRoutesData && currentRoutesData.routes && currentRoutesData.routes.length > 0) {
                        // Switch active route to the one recommended for this mode
                        if (activeMode === "shortest" && currentRoutesData.shortest_route_index !== undefined) {
                            selectedRouteIdx = currentRoutesData.shortest_route_index;
                        } else if (activeMode === "balanced" && currentRoutesData.balanced_route_index !== undefined) {
                            selectedRouteIdx = currentRoutesData.balanced_route_index;
                        } else {
                            selectedRouteIdx = currentRoutesData.safest_route_index || 0;
                        }
                        updateSelectedRoute();
                    }
                }
            });
        });

        var presetSelect = document.getElementById("preset-corridors");
        if (presetSelect) {
            presetSelect.addEventListener("change", function (e) {
                var val = e.target.value;
                if (!val) return;
                var parts = val.split(",");
                if (parts.length === 4) {
                    document.getElementById("start_lat").value = parts[0];
                    document.getElementById("start_lon").value = parts[1];
                    document.getElementById("end_lat").value = parts[2];
                    document.getElementById("end_lon").value = parts[3];
                }
            });
        }

        var fwSlider = document.getElementById("flood_weight");
        var fwVal = document.getElementById("flood-weight-val");
        if (fwSlider && fwVal) {
            fwSlider.addEventListener("input", function (e) {
                fwVal.textContent = Number(e.target.value).toFixed(2);
            });
        }

        var lwSlider = document.getElementById("landslide_weight");
        var lwVal = document.getElementById("landslide-weight-val");
        if (lwSlider && lwVal) {
            lwSlider.addEventListener("input", function (e) {
                lwVal.textContent = Number(e.target.value).toFixed(2);
            });
        }
    }

    function findSafeRoute() {
        hideError();
        var sLat = document.getElementById("start_lat").value.trim();
        var sLon = document.getElementById("start_lon").value.trim();
        var eLat = document.getElementById("end_lat").value.trim();
        var eLon = document.getElementById("end_lon").value.trim();

        if (!sLat || !sLon || !eLat || !eLon) {
            showError("Please enter valid numeric start and destination coordinates.");
            return;
        }

        var fw = document.getElementById("flood_weight").value;
        var lw = document.getElementById("landslide_weight").value;
        var rad = document.getElementById("station_radius_km").value;

        var url = "/api/routing/route?" +
            "start_lat=" + encodeURIComponent(sLat) +
            "&start_lon=" + encodeURIComponent(sLon) +
            "&end_lat=" + encodeURIComponent(eLat) +
            "&end_lon=" + encodeURIComponent(eLon) +
            "&flood_weight=" + encodeURIComponent(fw) +
            "&landslide_weight=" + encodeURIComponent(lw) +
            "&station_radius_km=" + encodeURIComponent(rad) +
            "&mode=" + encodeURIComponent(activeMode);

        setLoading(true);

        fetch(url)
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
                    var msg = (result.data.errors && result.data.errors.join(", ")) || "Routing request failed.";
                    showError(msg);
                    return;
                }

                currentRoutesData = result.data;
                selectedRouteIdx = result.data.recommended_route_index || 0;

                renderRoutesOnMap(result.data);
                renderRouteCards(result.data);
            })
            .catch(function (err) {
                setLoading(false);
                if (err.message !== "Unauthorized") {
                    showError("Failed to reach routing service: " + err.message);
                }
            });
    }

    function renderRoutesOnMap(data) {
        routesLayer.clearLayers();
        markersLayer.clearLayers();
        routePolylines = [];

        var routes = data.routes || [];
        if (!routes.length) return;

        // Origin and Destination markers
        var sLat = data.origin.latitude;
        var sLon = data.origin.longitude;
        var eLat = data.destination.latitude;
        var eLon = data.destination.longitude;

        var startMarker = L.circleMarker([sLat, sLon], {
            radius: 9,
            fillColor: "#22c55e",
            color: "#ffffff",
            weight: 2,
            opacity: 1,
            fillOpacity: 1,
        }).bindPopup("<strong>Origin (Start Location)</strong><br/>Lat: " + sLat + ", Lon: " + sLon);

        var endMarker = L.circleMarker([eLat, eLon], {
            radius: 9,
            fillColor: "#ef4444",
            color: "#ffffff",
            weight: 2,
            opacity: 1,
            fillOpacity: 1,
        }).bindPopup("<strong>Destination (Target Location)</strong><br/>Lat: " + eLat + ", Lon: " + eLon);

        markersLayer.addLayer(startMarker);
        markersLayer.addLayer(endMarker);

        // Render each candidate route polyline
        routes.forEach(function (r, idx) {
            var isSelected = (idx === selectedRouteIdx);
            var isSafest = (idx === data.safest_route_index);
            var isShortest = (idx === data.shortest_route_index);
            var isBalanced = (idx === data.balanced_route_index);

            var baseColor = isSafest ? COLOR_PALETTE.safest : (isShortest ? COLOR_PALETTE.shortest : (isBalanced ? COLOR_PALETTE.balanced : COLOR_PALETTE.alternative));

            var geom = r.geometry;
            if (geom && geom.coordinates) {
                var latLngs = geom.coordinates.map(function (c) {
                    return [c[1], c[0]];
                });

                var polyline = L.polyline(latLngs, {
                    color: isSelected ? baseColor : "#64748b",
                    weight: isSelected ? 6 : 4,
                    opacity: isSelected ? 0.95 : 0.60,
                    dashArray: (!isSelected && isShortest) ? "6, 8" : null,
                });

                var m = r.metrics || {};
                var popupHtml = [
                    "<div class='p-1'>",
                    "  <strong class='text-uppercase'>" + escapeHtml(r.summary || "Route #" + (idx + 1)) + "</strong>",
                    "  <hr class='my-1 border-secondary'/>",
                    "  <div>Distance: <strong>" + m.distance_km + " km</strong></div>",
                    "  <div>Duration: <strong>" + formatDuration(m.duration_minutes) + "</strong></div>",
                    "  <div>Safety Score: <strong>" + (m.safety_score !== undefined ? m.safety_score : "--") + " / 100</strong></div>",
                    "  <div>Risk Coverage: <strong>" + m.risk_coverage_percent + "%</strong></div>",
                    "  <div>Combined Risk: <strong>" + Number(m.average_combined_risk).toFixed(4) + " (" + (m.risk_level || "UNKNOWN") + ")</strong></div>",
                    "  <div>Risk-Adjusted Cost: <strong>" + m.route_cost + "</strong></div>",
                    "</div>",
                ].join("");

                polyline.bindPopup(popupHtml);

                polyline.on("click", function () {
                    selectedRouteIdx = idx;
                    updateSelectedRoute();
                });

                routesLayer.addLayer(polyline);
                routePolylines.push({ polyline: polyline, baseColor: baseColor, index: idx });
            }
        });

        // Draw station points along active route
        renderActiveRouteStations();

        if (routesLayer.getLayers().length > 0) {
            map.fitBounds(routesLayer.getBounds(), { padding: [40, 40] });
        }
    }

    function renderActiveRouteStations() {
        if (!currentRoutesData || !currentRoutesData.routes) return;
        var r = currentRoutesData.routes[selectedRouteIdx];
        if (!r || !r.sampled_points) return;

        // Clear existing station markers while preserving origin/destination
        markersLayer.eachLayer(function (layer) {
            if (layer.options && layer.options.isStationMarker) {
                markersLayer.removeLayer(layer);
            }
        });

        var seenStations = {};
        r.sampled_points.forEach(function (pt) {
            if (pt.is_covered && pt.nearest_station && !seenStations[pt.nearest_station]) {
                seenStations[pt.nearest_station] = true;
                var stMarker = L.circleMarker([pt.latitude, pt.longitude], {
                    radius: 6,
                    fillColor: "#38bdf8",
                    color: "#ffffff",
                    weight: 1,
                    opacity: 0.9,
                    fillOpacity: 0.8,
                    isStationMarker: true,
                }).bindPopup(
                    "<strong>Hazard Station Corridor</strong><br/>" +
                    "Nearest: <strong>" + escapeHtml(pt.nearest_station) + "</strong> (" + escapeHtml(pt.station_state) + ")<br/>" +
                    "Station Dist: " + pt.distance_to_station_km + " km<br/>" +
                    "P(Flood): " + pt.flood_probability + "<br/>" +
                    "P(Landslide): " + pt.landslide_probability + "<br/>" +
                    "Combined Risk: " + pt.combined_risk
                );
                markersLayer.addLayer(stMarker);
            }
        });
    }

    function updateSelectedRoute() {
        if (!currentRoutesData || !currentRoutesData.routes) return;

        // Update polylines styling
        routePolylines.forEach(function (item) {
            var isSel = (item.index === selectedRouteIdx);
            var isShortest = (item.index === currentRoutesData.shortest_route_index);

            item.polyline.setStyle({
                color: isSel ? item.baseColor : "#64748b",
                weight: isSel ? 6 : 4,
                opacity: isSel ? 0.95 : 0.55,
                dashArray: (!isSel && isShortest) ? "6, 8" : null,
            });

            if (isSel) {
                item.polyline.bringToFront();
            }
        });

        // Re-render station points for selected route
        renderActiveRouteStations();

        // Update Card Highlighting
        var cards = document.querySelectorAll(".multi-route-card");
        cards.forEach(function (card, idx) {
            if (idx === selectedRouteIdx) {
                card.classList.add("active-route");
            } else {
                card.classList.remove("active-route");
            }
        });
    }

    function renderRouteCards(data) {
        var container = document.getElementById("route-results-container");
        var list = document.getElementById("route-cards-list");
        var recNote = document.getElementById("rec-note");
        var recBadge = document.getElementById("rec-confidence-badge");
        var recTitle = document.getElementById("rec-title");
        var countBadge = document.getElementById("routes-count-badge");

        if (!container || !list) return;

        container.style.display = "block";
        list.innerHTML = "";

        var routes = data.routes || [];
        countBadge.textContent = routes.length + (routes.length === 1 ? " Candidate Route" : " Routes Compared");

        // Mode title and recommendation note
        var modeTitles = {
            safest: "RECOMMENDED SAFEST ROUTE",
            shortest: "RECOMMENDED SHORTEST ROUTE",
            balanced: "RECOMMENDED BALANCED ROUTE",
        };
        if (recTitle) {
            recTitle.textContent = modeTitles[activeMode] || "RECOMMENDED ROUTE";
        }

        if (recNote) {
            recNote.textContent = data.recommendation_note || "";
        }

        if (recBadge) {
            recBadge.textContent = (data.recommendation_confidence || "HIGH") + " CONFIDENCE";
            recBadge.className = "badge " + (data.recommendation_confidence === "HIGH" ? "bg-success" : "bg-warning text-dark");
        }

        var safestIdx = data.safest_route_index !== undefined ? data.safest_route_index : 0;
        var shortestIdx = data.shortest_route_index !== undefined ? data.shortest_route_index : 0;
        var balancedIdx = data.balanced_route_index !== undefined ? data.balanced_route_index : 0;

        routes.forEach(function (r, idx) {
            var isSelected = (idx === selectedRouteIdx);
            var isSafest = (idx === safestIdx);
            var isShortest = (idx === shortestIdx);
            var isBalanced = (idx === balancedIdx);
            var m = r.metrics || {};

            var card = document.createElement("div");
            card.className = "multi-route-card mb-2 " + (isSelected ? "active-route" : "");
            card.setAttribute("data-route-index", idx);

            // Badges
            var badgesHtml = "";
            if (isSafest) {
                badgesHtml += "<span class='badge bg-success me-1'>SAFE ROUTE</span>";
            }
            if (isShortest) {
                badgesHtml += "<span class='badge bg-info text-dark me-1'>SHORTEST</span>";
            }
            if (isBalanced && !isSafest && !isShortest) {
                badgesHtml += "<span class='badge bg-primary me-1'>BALANCED</span>";
            }
            if (!isSafest && !isShortest && !isBalanced) {
                badgesHtml += "<span class='badge bg-secondary me-1'>ALTERNATIVE</span>";
            }

            var safetyScore = m.safety_score !== undefined ? m.safety_score : 100;
            var scoreClass = safetyScore >= 80 ? "score-high" : (safetyScore >= 50 ? "score-mid" : "score-low");

            var floodChip = "<span class='risk-chip " + getRiskChipClass(m.flood_risk_level) + "'>" + (m.flood_risk_level || "LOW") + " (" + Number(m.average_flood_risk).toFixed(3) + ")</span>";
            var landslideChip = "<span class='risk-chip " + getRiskChipClass(m.landslide_risk_level) + "'>" + (m.landslide_risk_level || "LOW") + " (" + Number(m.average_landslide_risk).toFixed(3) + ")</span>";
            var combinedChip = "<span class='risk-chip " + getRiskChipClass(m.risk_level) + "'>" + (m.risk_level || "LOW") + " (" + Number(m.average_combined_risk).toFixed(3) + ")</span>";

            card.innerHTML = [
                "<div class='d-flex align-items-center justify-content-between mb-2'>",
                "  <div class='d-flex align-items-center gap-1 flex-wrap'>" + badgesHtml + "<strong class='small text-light'>" + escapeHtml(r.summary || "Route " + (idx + 1)) + "</strong></div>",
                "  <span class='safety-score-pill " + scoreClass + "'>🛡️ Safety: " + safetyScore + " / 100</span>",
                "</div>",
                "<div class='row g-2 small mb-2 text-light'>",
                "  <div class='col-6'>",
                "    <span class='text-muted'>Distance:</span> <strong>" + m.distance_km + " km</strong>",
                "  </div>",
                "  <div class='col-6'>",
                "    <span class='text-muted'>Est. Duration:</span> <strong>" + formatDuration(m.duration_minutes) + "</strong>",
                "  </div>",
                "  <div class='col-6'>",
                "    <span class='text-muted'>Flood Risk:</span> " + floodChip,
                "  </div>",
                "  <div class='col-6'>",
                "    <span class='text-muted'>Landslide Risk:</span> " + landslideChip,
                "  </div>",
                "  <div class='col-6'>",
                "    <span class='text-muted'>Combined Risk:</span> " + combinedChip,
                "  </div>",
                "  <div class='col-6'>",
                "    <span class='text-muted'>Risk-Adjusted Cost:</span> <strong>" + m.route_cost + "</strong>",
                "  </div>",
                "</div>",
                "<div class='d-flex align-items-center justify-content-between mb-1 text-muted' style='font-size: 0.72rem;'>",
                "  <span>Station Hazard Coverage</span>",
                "  <strong class='text-light'>" + m.risk_coverage_percent + "%</strong>",
                "</div>",
                "<div class='progress mb-2' style='height: 5px; background: rgba(255, 255, 255, 0.1);'>",
                "  <div class='progress-bar bg-success' style='width: " + m.risk_coverage_percent + "%'></div>",
                "</div>",
                "<div class='d-flex align-items-center justify-content-between' style='font-size: 0.68rem;'>",
                "  <span class='text-muted'>" + m.covered_points + " of " + m.total_points + " sampled points &le; 50km</span>",
                "  <span class='text-info fw-semibold'>Click to focus route &rarr;</span>",
                "</div>"
            ].join("");

            card.addEventListener("click", function () {
                selectedRouteIdx = idx;
                updateSelectedRoute();
            });

            list.appendChild(card);
        });
    }

    function clearRoute() {
        document.getElementById("start_lat").value = "";
        document.getElementById("start_lon").value = "";
        document.getElementById("end_lat").value = "";
        document.getElementById("end_lon").value = "";
        document.getElementById("preset-corridors").value = "";

        if (routesLayer) routesLayer.clearLayers();
        if (markersLayer) markersLayer.clearLayers();
        routePolylines = [];
        currentRoutesData = null;

        var container = document.getElementById("route-results-container");
        if (container) container.style.display = "none";
        hideError();
    }

    function formatDuration(minutes) {
        if (!minutes || minutes <= 0) return "0 min";
        var hrs = Math.floor(minutes / 60);
        var mins = Math.round(minutes % 60);
        if (hrs > 0) {
            return hrs + " hr " + (mins > 0 ? mins + " min" : "");
        }
        return mins + " min";
    }

    function getRiskChipClass(level) {
        if (!level) return "risk-low";
        var l = level.toUpperCase();
        if (l === "CRITICAL") return "risk-critical";
        if (l === "HIGH") return "risk-high";
        if (l === "MODERATE") return "risk-moderate";
        return "risk-low";
    }

    function setLoading(isLoading) {
        var spinner = document.getElementById("route-btn-spinner");
        var mapLoader = document.getElementById("route-map-loading");
        var btn = document.getElementById("find-route-btn");

        if (spinner) spinner.className = isLoading ? "spinner-border spinner-border-sm" : "spinner-border spinner-border-sm d-none";
        if (mapLoader) mapLoader.style.display = isLoading ? "flex" : "none";
        if (btn) btn.disabled = isLoading;
    }

    function showError(msg) {
        var banner = document.getElementById("route-error-banner");
        if (banner) {
            banner.textContent = msg;
            banner.style.display = "block";
        }
    }

    function hideError() {
        var banner = document.getElementById("route-error-banner");
        if (banner) {
            banner.style.display = "none";
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
        initRoutingMap();
    });
})();

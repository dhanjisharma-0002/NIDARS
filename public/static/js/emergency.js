/**
 * NIDARS Phase 14 — Emergency Evacuation Center & Safe Zone Analysis Controller
 * Manages geolocation, localized disaster risk assessment, safe zone ranking,
 * OSRM road corridor evaluation, Leaflet GIS visualization, and Evacuation Mode.
 */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const userLatInput = document.getElementById("user_lat");
    const userLonInput = document.getElementById("user_lon");
    const searchRadiusSelect = document.getElementById("search_radius");
    const chkShelter = document.getElementById("chk-shelter");
    const chkHospital = document.getElementById("chk-hospital");
    const chkPolice = document.getElementById("chk-police");

    const btnUseLocation = document.getElementById("btn-use-location");
    const locationSpinner = document.getElementById("location-spinner");
    const evacuationForm = document.getElementById("evacuation-form");
    const btnEvacuate = document.getElementById("btn-evacuate");
    const evacSpinner = document.getElementById("evac-spinner");
    const btnRefreshRisk = document.getElementById("btn-refresh-risk");

    // Risk Indicators
    const statFloodProb = document.getElementById("stat-flood-prob");
    const statLandslideProb = document.getElementById("stat-landslide-prob");
    const statCombinedRisk = document.getElementById("stat-combined-risk");
    const statNearestStation = document.getElementById("stat-nearest-station");
    const statRiskLevel = document.getElementById("stat-risk-level");
    const statRiskDesc = document.getElementById("stat-risk-desc");

    // Hero Recommended Safe Zone
    const heroCard = document.getElementById("recommended-safezone-hero");
    const heroFacName = document.getElementById("hero-fac-name");
    const heroFacType = document.getElementById("hero-fac-type");
    const heroFacScore = document.getElementById("hero-fac-score");
    const heroFacAddr = document.getElementById("hero-fac-addr");
    const heroFacReason = document.getElementById("hero-fac-reason");
    const heroFacDist = document.getElementById("hero-fac-dist");
    const heroFacEta = document.getElementById("hero-fac-eta");
    const heroFacDestRisk = document.getElementById("hero-fac-dest-risk");
    const heroFacRouteRisk = document.getElementById("hero-fac-route-risk");
    const btnStartHeroRoute = document.getElementById("btn-start-hero-route");
    const btnDetailsHeroRoute = document.getElementById("btn-details-hero-route");

    // Evacuation Mode
    const btnToggleEvacuationMode = document.getElementById("btn-toggle-evacuation-mode");
    const evacModeBtnText = document.getElementById("evac-mode-btn-text");
    const evacModeHud = document.getElementById("evacuation-mode-hud");
    const hudRiskLevel = document.getElementById("hud-risk-level");
    const hudDestName = document.getElementById("hud-dest-name");
    const hudDistEta = document.getElementById("hud-dist-eta");
    const hudRouteRisk = document.getElementById("hud-route-risk");
    const btnHudShowRoute = document.getElementById("btn-hud-show-route");
    const btnHudExitMode = document.getElementById("btn-hud-exit-mode");

    // Destination Directory
    const facilityCountBadge = document.getElementById("facility-count-badge");
    const facilityStateMessage = document.getElementById("facility-state-message");
    const facilityItemsContainer = document.getElementById("facility-items");
    const routeStatusBadge = document.getElementById("route-status-badge");

    // Active Route Overview
    const activeRouteCard = document.getElementById("active-route-card");
    const btnCloseRouteCard = document.getElementById("btn-close-route-card");
    const flowOriginCoords = document.getElementById("flow-origin-coords");
    const flowDestName = document.getElementById("flow-dest-name");
    const routeMetricDist = document.getElementById("route-metric-dist");
    const routeMetricDur = document.getElementById("route-metric-dur");
    const routeMetricRisk = document.getElementById("route-metric-risk");
    const routeMetricFlood = document.getElementById("route-metric-flood");
    const routeMetricLandslide = document.getElementById("route-metric-landslide");
    const routeMetricScore = document.getElementById("route-metric-score");

    // Modal
    const facilityModalElem = document.getElementById("facilityDetailModal");
    let facilityModal = null;
    if (facilityModalElem && window.bootstrap && window.bootstrap.Modal) {
        facilityModal = new bootstrap.Modal(facilityModalElem);
    }

    // State Variables
    let map = null;
    let userMarker = null;
    let facilityMarkersLayer = null;
    let routesLayerGroup = null;
    let gisOverlayLayer = null;

    let isEvacuationModeActive = false;
    let currentEvacuationData = null;
    let activeSelectedDestination = null;

    // --- CSRF Token Helper ---
    function getCsrfToken() {
        if (typeof window.getCsrfToken === "function") {
            return window.getCsrfToken();
        }
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    // --- 1. Initialize Map ---
    function initMap() {
        const startLat = parseFloat(userLatInput.value) || 31.1048;
        const startLon = parseFloat(userLonInput.value) || 77.1734;

        map = L.map("emergency-map", {
            center: [startLat, startLon],
            zoom: 13,
            zoomControl: true,
        });

        // OpenStreetMap Dark/Standard Tile Layer
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | NIDARS'
        }).addTo(map);

        facilityMarkersLayer = L.layerGroup().addTo(map);
        routesLayerGroup = L.layerGroup().addTo(map);
        gisOverlayLayer = L.layerGroup().addTo(map);

        updateUserMarker(startLat, startLon);
        initDraggableLegend();
    }

    function updateUserMarker(lat, lon) {
        if (!map) return;
        if (userMarker) {
            map.removeLayer(userMarker);
        }

        const userIcon = L.divIcon({
            className: "origin-loc-marker",
            html: `
                <div style="position:relative; width:26px; height:26px;">
                    <div style="position:absolute; width:26px; height:26px; border-radius:50%; background:rgba(220,53,69,0.3); animation:pulse 1.8s infinite;"></div>
                    <div style="position:absolute; top:4px; left:4px; width:18px; height:18px; border-radius:50%; background:#dc3545; border:3px solid #fff; box-shadow:0 0 10px rgba(0,0,0,0.6);"></div>
                </div>
            `,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        });

        userMarker = L.marker([lat, lon], { icon: userIcon, zIndexOffset: 1000 })
            .addTo(map)
            .bindPopup(`<strong>📍 Current Location (Origin)</strong><br>Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}`);
    }

    // Draggable Legend
    function initDraggableLegend() {
        const legend = document.getElementById("emergency-map-legend");
        if (!legend) return;

        let isDragging = false;
        let startX, startY, initialLeft, initialTop;

        legend.style.cursor = "move";

        legend.addEventListener("mousedown", (e) => {
            if (e.target.tagName === "BUTTON" || e.target.tagName === "INPUT") return;
            isDragging = true;
            startX = e.clientX;
            startY = e.clientY;
            const rect = legend.getBoundingClientRect();
            initialLeft = rect.left;
            initialTop = rect.top;
            e.preventDefault();
        });

        window.addEventListener("mousemove", (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            legend.style.position = "fixed";
            legend.style.left = `${initialLeft + dx}px`;
            legend.style.top = `${initialTop + dy}px`;
            legend.style.bottom = "auto";
            legend.style.right = "auto";
        });

        window.addEventListener("mouseup", () => {
            isDragging = false;
        });
    }

    // --- 2. Location & Coordinate Handlers ---
    if (btnUseLocation) {
        btnUseLocation.addEventListener("click", () => {
            if (!navigator.geolocation) {
                alert("Browser geolocation is not supported by your browser. Please enter coordinates manually.");
                return;
            }

            locationSpinner.classList.remove("d-none");
            btnUseLocation.disabled = true;

            navigator.geolocation.getCurrentPosition(
                (position) => {
                    locationSpinner.classList.add("d-none");
                    btnUseLocation.disabled = false;

                    const lat = parseFloat(position.coords.latitude.toFixed(6));
                    const lon = parseFloat(position.coords.longitude.toFixed(6));
                    userLatInput.value = lat;
                    userLonInput.value = lon;

                    updateUserMarker(lat, lon);
                    map.setView([lat, lon], 13);
                    runEvacuationAnalysis(lat, lon);
                },
                (err) => {
                    locationSpinner.classList.add("d-none");
                    btnUseLocation.disabled = false;
                    let msg = "Location permission denied. Please enter coordinates manually.";
                    if (err.code === err.TIMEOUT) msg = "Geolocation request timed out. Please enter coordinates manually.";
                    else if (err.code === err.POSITION_UNAVAILABLE) msg = "Location information is unavailable.";
                    alert(msg);
                },
                { timeout: 10000, enableHighAccuracy: true }
            );
        });
    }

    // Form submission
    evacuationForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const lat = parseFloat(userLatInput.value);
        const lon = parseFloat(userLonInput.value);

        if (isNaN(lat) || lat < -90 || lat > 90) {
            alert("Please enter a valid decimal latitude between -90.0 and +90.0 degrees.");
            return;
        }
        if (isNaN(lon) || lon < -180 || lon > 180) {
            alert("Please enter a valid decimal longitude between -180.0 and +180.0 degrees.");
            return;
        }

        updateUserMarker(lat, lon);
        map.setView([lat, lon], 13);
        runEvacuationAnalysis(lat, lon);
    });

    if (btnRefreshRisk) {
        btnRefreshRisk.addEventListener("click", () => {
            const lat = parseFloat(userLatInput.value);
            const lon = parseFloat(userLonInput.value);
            if (!isNaN(lat) && !isNaN(lon)) {
                loadCurrentRisk(lat, lon);
            }
        });
    }

    // Map Helper Buttons
    const btnCenterUser = document.getElementById("btn-center-user");
    if (btnCenterUser) {
        btnCenterUser.addEventListener("click", () => {
            const lat = parseFloat(userLatInput.value);
            const lon = parseFloat(userLonInput.value);
            if (map && !isNaN(lat) && !isNaN(lon)) {
                map.setView([lat, lon], 14);
            }
        });
    }

    const btnFitAll = document.getElementById("btn-fit-all");
    if (btnFitAll) {
        btnFitAll.addEventListener("click", () => {
            fitMapToAllElements();
        });
    }

    // --- 3. Core Evacuation Analysis Fetcher ---
    async function runEvacuationAnalysis(lat, lon) {
        const radius = parseFloat(searchRadiusSelect.value) || 25.0;
        const selectedTypes = [];
        if (chkShelter && chkShelter.checked) selectedTypes.push("shelter");
        if (chkHospital && chkHospital.checked) selectedTypes.push("hospital");
        if (chkPolice && chkPolice.checked) selectedTypes.push("police");

        if (selectedTypes.length === 0) {
            alert("Please select at least one facility type (Shelter, Hospital, or Police).");
            return;
        }

        evacSpinner.classList.remove("d-none");
        btnEvacuate.disabled = true;
        routeStatusBadge.className = "badge bg-warning text-dark";
        routeStatusBadge.textContent = "Analyzing Safe Zones...";

        facilityStateMessage.classList.remove("d-none");
        facilityStateMessage.innerHTML = `
            <div class="spinner-border text-danger mb-2" role="status"></div>
            <p class="mb-0 text-light">Calculating safe zones and road evacuation corridors within ${radius} km...</p>
        `;
        facilityItemsContainer.innerHTML = "";
        heroCard.classList.add("d-none");
        activeRouteCard.classList.add("d-none");

        try {
            const payload = {
                latitude: Number(lat),
                longitude: Number(lon),
                max_distance_km: Number(radius),
                facility_types: selectedTypes,
            };

            const headers = { "Content-Type": "application/json" };
            const csrf = getCsrfToken();
            if (csrf) {
                headers["X-CSRFToken"] = csrf;
            }

            const res = await fetch("/api/emergency/evacuation", {
                method: "POST",
                headers: headers,
                body: JSON.stringify(payload),
            });

            const data = await res.json();
            evacSpinner.classList.add("d-none");
            btnEvacuate.disabled = false;

            if (!data.success || res.status >= 400) {
                let errMsg = "Emergency analysis could not be completed. Please try again.";
                if (data.error === "INVALID_COORDINATES" || (data.errors && data.errors.some(e => e.toLowerCase().includes("latitude") || e.toLowerCase().includes("longitude")))) {
                    errMsg = data.message || "Please enter valid latitude (-90 to 90) and longitude (-180 to 180).";
                } else if (data.error === "NO_FACILITIES") {
                    errMsg = "No suitable emergency facilities were found nearby.";
                } else if (data.error === "ROUTING_UNAVAILABLE") {
                    errMsg = "Evacuation route service is temporarily unavailable.";
                } else if (data.error === "RISK_UNAVAILABLE") {
                    errMsg = "Risk assessment is temporarily unavailable.";
                } else if (data.message) {
                    errMsg = data.message;
                } else if (data.errors && data.errors[0]) {
                    errMsg = data.errors[0];
                }

                console.error("[EVAC ERROR]", res.status, data);

                facilityStateMessage.innerHTML = `
                    <div class="text-danger mb-2 fs-3">⚠️</div>
                    <p class="text-danger mb-0">${errMsg}</p>
                `;
                facilityCountBadge.textContent = "Error";
                routeStatusBadge.className = "badge bg-danger";
                routeStatusBadge.textContent = "Analysis Failed";
                return;
            }

            currentEvacuationData = data;

            // Render Current Risk KPIs
            renderCurrentRisk(data.current_risk);

            // Render Safe Destinations
            const destinations = data.destinations || [];
            facilityCountBadge.textContent = `${destinations.length} Found`;

            if (destinations.length === 0) {
                facilityStateMessage.classList.remove("d-none");
                facilityStateMessage.innerHTML = `
                    <span class="fs-2 d-block mb-2">ℹ️</span>
                    <p class="mb-0 text-white">${data.message || "No verified facilities found within search radius."}</p>
                    <small class="text-secondary">Try expanding search radius to 25 km or 50 km.</small>
                `;
                facilityMarkersLayer.clearLayers();
                routesLayerGroup.clearLayers();
                routeStatusBadge.className = "badge bg-secondary";
                routeStatusBadge.textContent = "No Facilities";
                return;
            }

            facilityStateMessage.classList.add("d-none");

            // Recommended Hero Card
            const recommended = data.recommended_destination || destinations[0];
            renderRecommendedHero(recommended);

            // Alternative Ranked Cards
            renderDestinationCards(destinations);

            // Map Rendering
            renderMapFacilitiesAndRoutes(destinations, data.routes || []);

            // Update Evacuation Mode HUD if active
            updateEvacuationModeHUD(data.current_risk, recommended);

            routeStatusBadge.className = "badge bg-success";
            routeStatusBadge.textContent = "Evacuation Route Active";

        } catch (err) {
            console.error("Evacuation analysis error:", err);
            evacSpinner.classList.add("d-none");
            btnEvacuate.disabled = false;
            facilityStateMessage.innerHTML = `
                <div class="text-danger mb-2 fs-3">❌</div>
                <p class="text-danger mb-0">Evacuation analysis service temporarily unreachable.</p>
                <small class="text-secondary">Please verify connection or check official government broadcasts.</small>
            `;
            routeStatusBadge.className = "badge bg-danger";
            routeStatusBadge.textContent = "Network Error";
        }
    }

    // --- 4. Render Current Risk KPIs ---
    function renderCurrentRisk(risk) {
        if (!risk) return;
        const fProb = risk.flood_probability !== null && risk.flood_probability !== undefined ? `${(risk.flood_probability * 100).toFixed(1)}%` : "N/A";
        const lProb = risk.landslide_probability !== null && risk.landslide_probability !== undefined ? `${(risk.landslide_probability * 100).toFixed(1)}%` : "N/A";
        const cRisk = risk.combined_risk !== null && risk.combined_risk !== undefined ? `${(risk.combined_risk * 100).toFixed(1)}%` : "Regional";

        statFloodProb.textContent = fProb;
        statLandslideProb.textContent = lProb;
        statCombinedRisk.textContent = cRisk;

        statNearestStation.textContent = risk.nearest_station
            ? `Station: ${risk.nearest_station} (${risk.station_distance_km || 0} km)`
            : "Station: Regional Baseline";

        const lvl = (risk.risk_level || "UNKNOWN").toUpperCase();
        let badgeClass = "bg-secondary";
        if (lvl === "LOW") badgeClass = "bg-success";
        else if (lvl === "MODERATE") badgeClass = "bg-warning text-dark";
        else if (lvl === "HIGH") badgeClass = "bg-orange text-white";
        else if (lvl === "CRITICAL") badgeClass = "bg-danger";

        statRiskLevel.innerHTML = `<span class="badge ${badgeClass} px-2 py-1">${lvl}</span>`;
        statRiskDesc.textContent = risk.is_covered ? "Live spatial model assessment" : "Outside direct station radius";
    }

    async function loadCurrentRisk(lat, lon) {
        try {
            const res = await fetch(`/api/emergency/risk?lat=${lat}&lon=${lon}`);
            const data = await res.json();
            if (data.success && data.risk_status) {
                renderCurrentRisk(data.risk_status);
            }
        } catch (e) {
            console.warn("Could not load current risk:", e);
        }
    }

    // --- 5. Render Recommended Hero Safe Zone ---
    function renderRecommendedHero(facility) {
        if (!facility) {
            heroCard.classList.add("d-none");
            return;
        }

        heroFacName.textContent = facility.name || "Safe Destination";
        heroFacType.textContent = (facility.facility_type || "Shelter").toUpperCase();
        heroFacScore.textContent = facility.overall_score !== undefined ? facility.overall_score.toFixed(2) : "Optimal";
        heroFacAddr.textContent = `📍 ${facility.address || "Address not available"}`;
        heroFacReason.textContent = facility.reason || "Lowest combined destination and route hazard exposure.";
        heroFacDist.textContent = `${facility.distance_km.toFixed(1)} km`;
        heroFacEta.textContent = `${facility.duration_minutes.toFixed(0)} min`;
        heroFacDestRisk.textContent = (facility.destination_risk_level || "LOW").toUpperCase();
        heroFacRouteRisk.textContent = (facility.route_risk_level || "LOW").toUpperCase();

        btnStartHeroRoute.onclick = () => {
            selectAndDisplayRoute(facility);
        };

        btnDetailsHeroRoute.onclick = () => {
            showFacilityDetailsModal(facility);
        };

        heroCard.classList.remove("d-none");

        // Automatically show route visualization for recommended safe zone
        selectAndDisplayRoute(facility);
    }

    // --- 6. Render Alternative Ranked Cards ---
    function renderDestinationCards(destinations) {
        facilityItemsContainer.innerHTML = "";

        destinations.forEach((fac) => {
            let icon = "🏠";
            let typeBadgeClass = "badge-shelter";
            if (fac.facility_type === "hospital") {
                icon = "🏥";
                typeBadgeClass = "badge-hospital";
            } else if (fac.facility_type === "police") {
                icon = "👮";
                typeBadgeClass = "badge-police";
            }

            const isRec = fac.is_recommended;
            const card = document.createElement("div");
            card.className = `card facility-card p-2 border ${isRec ? "border-success bg-success bg-opacity-10" : "border-secondary"} text-light`;
            card.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <div class="d-flex align-items-center gap-1">
                        <span class="badge ${isRec ? "bg-success" : "bg-secondary"}" style="font-size: 0.65rem;">#${fac.rank || 1}</span>
                        <span class="badge ${typeBadgeClass} text-uppercase" style="font-size: 0.65rem;">${icon} ${fac.facility_type}</span>
                    </div>
                    <span class="badge bg-dark border border-secondary text-info" style="font-size: 0.72rem;">Score: ${fac.overall_score !== undefined ? fac.overall_score.toFixed(2) : '--'}</span>
                </div>
                <h6 class="mb-1 text-white fw-bold text-truncate" title="${fac.name || 'Facility'}">${fac.name || "Emergency Facility"}</h6>
                <div class="small text-muted mb-1 text-truncate">📍 ${fac.address || 'Address not available'}</div>
                <div class="d-flex justify-content-between align-items-center small text-secondary mb-2" style="font-size: 0.75rem;">
                    <span>Dist: <strong class="text-white">${fac.distance_km.toFixed(1)} km</strong> (~${fac.duration_minutes.toFixed(0)}m)</span>
                    <span>Corridor: <strong class="${fac.route_risk_level === 'LOW' ? 'text-success' : 'text-warning'}">${fac.route_risk_level || 'LOW'}</strong></span>
                </div>
                <div class="small text-light bg-black bg-opacity-30 p-1 rounded mb-2" style="font-size: 0.7rem;">
                    <em>${fac.reason || 'Safe evacuation corridor.'}</em>
                </div>
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-xs btn-outline-secondary flex-grow-1 btn-card-details" style="font-size: 0.75rem;">
                        📋 Details
                    </button>
                    <button type="button" class="btn btn-xs ${isRec ? 'btn-success' : 'btn-primary'} flex-grow-1 btn-card-route" style="font-size: 0.75rem;">
                        🧭 Safe Route
                    </button>
                </div>
            `;

            card.querySelector(".btn-card-details").addEventListener("click", () => {
                showFacilityDetailsModal(fac);
            });

            card.querySelector(".btn-card-route").addEventListener("click", () => {
                selectAndDisplayRoute(fac);
            });

            facilityItemsContainer.appendChild(card);
        });
    }

    // --- 7. Map Rendering ---
    function renderMapFacilitiesAndRoutes(destinations, routes) {
        facilityMarkersLayer.clearLayers();
        routesLayerGroup.clearLayers();

        const bounds = L.latLngBounds();
        if (userMarker) {
            bounds.extend(userMarker.getLatLng());
        }

        // Draw alternative routes first (gray / dashed)
        routes.forEach((r) => {
            if (!r.is_recommended && r.geometry && r.geometry.coordinates) {
                const latlngs = r.geometry.coordinates.map(c => [c[1], c[0]]);
                const poly = L.polyline(latlngs, {
                    color: "#6c757d",
                    weight: 3,
                    opacity: 0.65,
                    dashArray: "6, 8",
                    lineJoin: "round"
                }).addTo(routesLayerGroup);
                bounds.extend(poly.getBounds());
            }
        });

        // Draw recommended route on top (bright cyan/blue)
        const recRoute = routes.find(r => r.is_recommended) || routes[0];
        if (recRoute && recRoute.geometry && recRoute.geometry.coordinates) {
            const latlngs = recRoute.geometry.coordinates.map(c => [c[1], c[0]]);
            const poly = L.polyline(latlngs, {
                color: "#0dcaf0",
                weight: 6,
                opacity: 0.95,
                lineJoin: "round"
            }).addTo(routesLayerGroup);
            bounds.extend(poly.getBounds());
        }

        // Render Facility Markers
        destinations.forEach((fac) => {
            const isRec = fac.is_recommended;
            let color = isRec ? "#198754" : "#ffc107";
            let iconText = "🛡️";

            if (!isRec) {
                if (fac.facility_type === "hospital") {
                    color = "#dc3545";
                    iconText = "🏥";
                } else if (fac.facility_type === "police") {
                    color = "#0d6efd";
                    iconText = "👮";
                } else {
                    iconText = "🏠";
                }
            }

            const facIcon = L.divIcon({
                className: "custom-fac-marker",
                html: `
                    <div style="background:${color}; color:#fff; width:${isRec ? '30px' : '24px'}; height:${isRec ? '30px' : '24px'}; border-radius:${isRec ? '50%' : '6px'}; border:2px solid #fff; box-shadow:0 3px 8px rgba(0,0,0,0.5); display:flex; align-items:center; justify-content:center; font-size:${isRec ? '14px' : '11px'}; font-weight:bold;">
                        ${iconText}
                    </div>
                `,
                iconSize: isRec ? [30, 30] : [24, 24],
                iconAnchor: isRec ? [15, 15] : [12, 12]
            });

            const marker = L.marker([fac.latitude, fac.longitude], { icon: facIcon, zIndexOffset: isRec ? 500 : 100 })
                .bindPopup(`
                    <div style="min-width: 200px;">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="badge" style="background:${color};">${(fac.facility_type || 'Facility').toUpperCase()}</span>
                            <span class="badge bg-dark text-info">Score: ${fac.overall_score !== undefined ? fac.overall_score.toFixed(2) : '--'}</span>
                        </div>
                        <h6 style="margin: 4px 0 2px 0; font-size: 13px; font-weight: bold;">${fac.name || "Unnamed"}</h6>
                        <div style="font-size: 11px; color: #555;">Dist: ${fac.distance_km.toFixed(1)} km (~${fac.duration_minutes.toFixed(0)} min)</div>
                        <div style="font-size: 11px; color: #666; margin-bottom: 6px;">${fac.address || ""}</div>
                        <div style="font-size: 10px; color: #0d6efd; margin-bottom: 6px;"><em>${fac.reason || ''}</em></div>
                        <button class="btn btn-sm btn-primary w-100 py-1" onclick="window.emergencySelectRouteById(${fac.id || -1}, '${encodeURIComponent(fac.name || 'Facility')}')">Select Evacuation Route</button>
                    </div>
                `);

            facilityMarkersLayer.addLayer(marker);
            bounds.extend([fac.latitude, fac.longitude]);
        });

        if (bounds.isValid() && map) {
            map.fitBounds(bounds, { padding: [40, 40] });
        }
    }

    function fitMapToAllElements() {
        if (!map) return;
        const bounds = L.latLngBounds();
        if (userMarker) bounds.extend(userMarker.getLatLng());
        facilityMarkersLayer.eachLayer(layer => {
            if (layer.getLatLng) bounds.extend(layer.getLatLng());
        });
        routesLayerGroup.eachLayer(layer => {
            if (layer.getBounds) bounds.extend(layer.getBounds());
        });
        if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [40, 40] });
        }
    }

    // Global hook for popup route selection
    window.emergencySelectRouteById = (facId, encName) => {
        const decodedName = decodeURIComponent(encName);
        if (currentEvacuationData && currentEvacuationData.destinations) {
            const found = currentEvacuationData.destinations.find(d => d.id === facId || d.name === decodedName);
            if (found) {
                selectAndDisplayRoute(found);
            }
        }
    };

    // --- 8. Route Selection & Schematic Display ---
    function selectAndDisplayRoute(facility) {
        activeSelectedDestination = facility;

        // Highlight selected route on map
        routesLayerGroup.clearLayers();

        // Re-draw all alternative routes dashed gray
        if (currentEvacuationData && currentEvacuationData.destinations) {
            currentEvacuationData.destinations.forEach(dest => {
                if (dest.id !== facility.id && dest.route_geometry && dest.route_geometry.coordinates) {
                    const latlngs = dest.route_geometry.coordinates.map(c => [c[1], c[0]]);
                    L.polyline(latlngs, {
                        color: "#6c757d",
                        weight: 3,
                        opacity: 0.60,
                        dashArray: "6, 8"
                    }).addTo(routesLayerGroup);
                }
            });
        }

        // Draw active route thick cyan
        if (facility.route_geometry && facility.route_geometry.coordinates) {
            const latlngs = facility.route_geometry.coordinates.map(c => [c[1], c[0]]);
            const activePoly = L.polyline(latlngs, {
                color: "#0dcaf0",
                weight: 6,
                opacity: 0.95
            }).addTo(routesLayerGroup);

            map.fitBounds(activePoly.getBounds(), { padding: [50, 50] });
        } else {
            map.setView([facility.latitude, facility.longitude], 14);
        }

        // Update Schematic Flow
        const uLat = parseFloat(userLatInput.value) || 31.1048;
        const uLon = parseFloat(userLonInput.value) || 77.1734;
        flowOriginCoords.textContent = `${uLat.toFixed(3)}°N, ${uLon.toFixed(3)}°E`;
        flowDestName.textContent = facility.name || "Safe Destination";

        routeMetricDist.textContent = `${facility.distance_km.toFixed(1)} km`;
        routeMetricDur.textContent = `${facility.duration_minutes.toFixed(0)} min`;
        routeMetricRisk.textContent = (facility.route_risk_level || "LOW").toUpperCase();
        routeMetricRisk.className = facility.route_risk_level === "LOW" ? "fw-bold fs-5 text-success" : "fw-bold fs-5 text-warning";
        routeMetricFlood.textContent = facility.flood_exposure || "LOW";
        routeMetricLandslide.textContent = facility.landslide_exposure || "LOW";
        routeMetricScore.textContent = facility.overall_score !== undefined ? facility.overall_score.toFixed(2) : "0.00";

        activeRouteCard.classList.remove("d-none");
        routeStatusBadge.className = "badge bg-success";
        routeStatusBadge.textContent = `Route: ${facility.name}`;

        // Scroll route card into view if needed
        activeRouteCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    if (btnCloseRouteCard) {
        btnCloseRouteCard.addEventListener("click", () => {
            activeRouteCard.classList.add("d-none");
        });
    }

    // --- 9. Evacuation Mode Implementation (PART 14) ---
    function toggleEvacuationMode() {
        isEvacuationModeActive = !isEvacuationModeActive;
        const workspace = document.getElementById("emergency-workspace");

        if (isEvacuationModeActive) {
            evacModeBtnText.textContent = "Exit Evacuation Mode";
            btnToggleEvacuationMode.className = "btn btn-sm btn-outline-danger d-flex align-items-center gap-2 fw-bold";
            evacModeHud.classList.remove("d-none");
            workspace.classList.add("evacuation-mode-active");

            // Populate HUD
            if (currentEvacuationData) {
                const rec = currentEvacuationData.recommended_destination;
                updateEvacuationModeHUD(currentEvacuationData.current_risk, rec);
            }

            // Expand map view
            if (map) {
                setTimeout(() => map.invalidateSize(), 200);
            }
        } else {
            evacModeBtnText.textContent = "Activate Evacuation Mode";
            btnToggleEvacuationMode.className = "btn btn-sm btn-danger text-white d-flex align-items-center gap-2 fw-bold";
            evacModeHud.classList.add("d-none");
            workspace.classList.remove("evacuation-mode-active");
            if (map) {
                setTimeout(() => map.invalidateSize(), 200);
            }
        }
    }

    function updateEvacuationModeHUD(risk, rec) {
        if (!hudRiskLevel) return;
        if (risk) {
            hudRiskLevel.textContent = (risk.risk_level || "UNKNOWN").toUpperCase();
        }
        if (rec) {
            hudDestName.textContent = rec.name || "Safe Destination";
            hudDistEta.textContent = `${rec.distance_km.toFixed(1)} km / ~${rec.duration_minutes.toFixed(0)} min`;
            hudRouteRisk.textContent = (rec.route_risk_level || "LOW").toUpperCase();
        }
    }

    if (btnToggleEvacuationMode) {
        btnToggleEvacuationMode.addEventListener("click", toggleEvacuationMode);
    }
    if (btnHudExitMode) {
        btnHudExitMode.addEventListener("click", toggleEvacuationMode);
    }
    if (btnHudShowRoute) {
        btnHudShowRoute.addEventListener("click", () => {
            if (activeSelectedDestination) {
                selectAndDisplayRoute(activeSelectedDestination);
            } else if (currentEvacuationData && currentEvacuationData.recommended_destination) {
                selectAndDisplayRoute(currentEvacuationData.recommended_destination);
            }
        });
    }

    // --- 10. Authentic Facility Details Modal (PART 15) ---
    function showFacilityDetailsModal(facility) {
        if (!facility) return;

        let icon = "🏠";
        if (facility.facility_type === "hospital") icon = "🏥";
        else if (facility.facility_type === "police") icon = "👮";

        document.getElementById("modal-fac-icon").textContent = icon;
        document.getElementById("modal-fac-name").textContent = facility.name || "Emergency Facility";
        document.getElementById("modal-fac-type").textContent = (facility.facility_type || "Facility").toUpperCase();
        document.getElementById("modal-fac-source").textContent = facility.source || "OpenStreetMap";
        document.getElementById("modal-fac-address").textContent = facility.address || "Not available";
        document.getElementById("modal-fac-phone").textContent = facility.phone || "Not available";
        document.getElementById("modal-fac-hours").textContent = facility.opening_hours || "Not available";
        document.getElementById("modal-fac-coords").textContent = `${facility.latitude.toFixed(4)}°N, ${facility.longitude.toFixed(4)}°E`;
        document.getElementById("modal-fac-risk").textContent = `${(facility.destination_risk_level || 'LOW').toUpperCase()} (${((facility.destination_risk || 0) * 100).toFixed(1)}%)`;
        document.getElementById("modal-fac-score").textContent = facility.overall_score !== undefined ? facility.overall_score.toFixed(2) : "Optimal";

        const btnRouteHere = document.getElementById("btn-modal-route-here");
        btnRouteHere.onclick = () => {
            if (facilityModal) facilityModal.hide();
            selectAndDisplayRoute(facility);
        };

        if (facilityModal) {
            facilityModal.show();
        }
    }

    // --- 11. Initial Startup ---
    initMap();
    const initialLat = parseFloat(userLatInput.value);
    const initialLon = parseFloat(userLonInput.value);
    if (!isNaN(initialLat) && !isNaN(initialLon)) {
        loadCurrentRisk(initialLat, initialLon);
        runEvacuationAnalysis(initialLat, initialLon);
    }
});

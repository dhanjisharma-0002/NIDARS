/**
 * NIDARS — Citizen Incident Reporting Client Logic
 * Manages Leaflet coordinate picker, geolocation auto-detect, and form submission.
 */
(function () {
    "use strict";

    var form = document.getElementById("incident-form");
    if (!form) return;

    var pickerMap = null;
    var pinMarker = null;

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    }

    function showAlert(message, type) {
        var container = document.getElementById("incident-alert-container");
        if (!container) return;

        container.innerHTML = `
            <div class="alert alert-${type || 'info'} alert-dismissible fade show" role="alert">
                <span>${message}</span>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    function setCoordinates(lat, lon, updateMarker) {
        var latInput = document.getElementById("latitude");
        var lonInput = document.getElementById("longitude");
        if (latInput) latInput.value = parseFloat(lat).toFixed(6);
        if (lonInput) lonInput.value = parseFloat(lon).toFixed(6);

        if (updateMarker && pickerMap) {
            var latLng = [parseFloat(lat), parseFloat(lon)];
            if (!pinMarker) {
                pinMarker = L.marker(latLng, { draggable: true }).addTo(pickerMap);
                pinMarker.on("dragend", function (e) {
                    var pos = e.target.getLatLng();
                    setCoordinates(pos.lat, pos.lng, false);
                });
            } else {
                pinMarker.setLatLng(latLng);
            }
            pickerMap.panTo(latLng);
        }
    }

    function initPickerMap() {
        var mapEl = document.getElementById("picker-map");
        if (!mapEl || typeof L === "undefined") return;

        var defaultCenter = [29.5, 78.5]; // North India center
        pickerMap = L.map("picker-map", {
            zoomControl: true,
            scrollWheelZoom: true,
        }).setView(defaultCenter, 6);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors | NIDARS Incidents',
            maxZoom: 19,
        }).addTo(pickerMap);

        pickerMap.on("click", function (e) {
            setCoordinates(e.latlng.lat, e.latlng.lng, true);
        });

        // Sync map if inputs change manually
        var latInput = document.getElementById("latitude");
        var lonInput = document.getElementById("longitude");
        function syncFromInputs() {
            var lat = parseFloat(latInput.value);
            var lon = parseFloat(lonInput.value);
            if (!isNaN(lat) && !isNaN(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
                setCoordinates(lat, lon, true);
            }
        }
        if (latInput) latInput.addEventListener("change", syncFromInputs);
        if (lonInput) lonInput.addEventListener("change", syncFromInputs);
    }

    function setupPresetsAndGeolocation() {
        var btnGeo = document.getElementById("btn-geolocate");
        var btnShimla = document.getElementById("btn-preset-shimla");
        var btnLucknow = document.getElementById("btn-preset-lucknow");
        var btnPatna = document.getElementById("btn-preset-patna");

        if (btnGeo) {
            btnGeo.addEventListener("click", function () {
                if ("geolocation" in navigator) {
                    btnGeo.disabled = true;
                    btnGeo.innerHTML = "<span>⏳</span> Locating…";
                    navigator.geolocation.getCurrentPosition(
                        function (position) {
                            btnGeo.disabled = false;
                            btnGeo.innerHTML = "<span>🎯</span> Use Current GPS Location";
                            setCoordinates(position.coords.latitude, position.coords.longitude, true);
                        },
                        function (err) {
                            btnGeo.disabled = false;
                            btnGeo.innerHTML = "<span>🎯</span> Use Current GPS Location";
                            showAlert("Unable to retrieve GPS coordinates: " + err.message, "warning");
                        },
                        { timeout: 10000, enableHighAccuracy: true }
                    );
                } else {
                    showAlert("Geolocation is not supported by your browser.", "warning");
                }
            });
        }

        if (btnShimla) {
            btnShimla.addEventListener("click", function () {
                setCoordinates(31.1048, 77.1734, true);
                var loc = document.getElementById("location_name");
                if (loc && !loc.value) loc.value = "Shimla Mall Road & Highway Junction, HP";
            });
        }

        if (btnLucknow) {
            btnLucknow.addEventListener("click", function () {
                setCoordinates(26.8467, 80.9462, true);
                var loc = document.getElementById("location_name");
                if (loc && !loc.value) loc.value = "Gomti Riverbank Sector 4, Lucknow, UP";
            });
        }

        if (btnPatna) {
            btnPatna.addEventListener("click", function () {
                setCoordinates(25.5941, 85.1376, true);
                var loc = document.getElementById("location_name");
                if (loc && !loc.value) loc.value = "Patna Bypass near Ganga Bridge, Bihar";
            });
        }
    }

    // Handle Form Submission
    form.addEventListener("submit", function (e) {
        e.preventDefault();

        var btnSubmit = document.getElementById("btn-submit-report");
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = "<span>⏳</span> Submitting Report…";
        }

        var formData = new FormData(form);

        fetch("/api/incidents", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrfToken(),
            },
            credentials: "same-origin",
            body: formData,
        })
            .then(function (res) {
                return res.json().then(function (data) {
                    return { ok: res.ok, status: res.status, data: data };
                });
            })
            .then(function (result) {
                if (btnSubmit) {
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = "<span>🚀</span> SUBMIT INCIDENT REPORT";
                }

                if (result.ok && result.data.success) {
                    showAlert("Incident report submitted successfully! Redirecting to your reports...", "success");
                    form.reset();
                    setTimeout(function () {
                        window.location.href = "/my-reports";
                    }, 1200);
                } else {
                    var errors = (result.data.errors || ["An error occurred during submission."]).join("<br>");
                    showAlert(errors, "danger");
                }
            })
            .catch(function (err) {
                if (btnSubmit) {
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = "<span>🚀</span> SUBMIT INCIDENT REPORT";
                }
                showAlert("Network connection error. Please try again.", "danger");
            });
    });

    document.addEventListener("DOMContentLoaded", function () {
        initPickerMap();
        setupPresetsAndGeolocation();

        // Set default datetime to now
        var dtInput = document.getElementById("incident_date");
        if (dtInput && !dtInput.value) {
            var now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            dtInput.value = now.toISOString().slice(0, 16);
        }
    });
})();

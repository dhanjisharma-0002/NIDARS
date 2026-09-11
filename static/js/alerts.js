/**
 * NIDARS Phase 10 — AI-Based Early Warning & Advisory System Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    let distributionChart = null;
    let allAlerts = [];

    const stateFilter = document.getElementById('filter-state');
    const hazardFilter = document.getElementById('filter-hazard');
    const levelFilter = document.getElementById('filter-level');
    const searchFilter = document.getElementById('filter-search');
    const refreshBtn = document.getElementById('btn-refresh-alerts');
    const syncBtn = document.getElementById('btn-sync-alerts');

    const alertsContainer = document.getElementById('alerts-container');
    const alertCountLabel = document.getElementById('alert-count-label');
    const lastUpdatedLabel = document.getElementById('last-updated-label');
    const topRiskList = document.getElementById('top-risk-list');
    const timelineContainer = document.getElementById('timeline-stream-container');

    const kpiCritical = document.getElementById('kpi-critical');
    const kpiHigh = document.getElementById('kpi-high');
    const kpiModerate = document.getElementById('kpi-moderate');
    const kpiTotal = document.getElementById('kpi-total');

    // Modal elements
    const detailModal = new bootstrap.Modal(document.getElementById('alertDetailModal'));
    const modalBanner = document.getElementById('modal-banner');
    const modalHazardType = document.getElementById('modal-hazard-type');
    const modalRiskLevel = document.getElementById('modal-risk-level');
    const modalProbability = document.getElementById('modal-probability');
    const modalSubLabel = document.getElementById('modal-sub-label');
    const modalAdvisoryText = document.getElementById('modal-advisory-text');
    const modalPrecautionsList = document.getElementById('modal-precautions-list');
    const modalTelemetryGrid = document.getElementById('modal-telemetry-grid');

    const HAZARD_ICONS = {
        flood: '🌊',
        landslide: '⛰️',
        combined: '⚡'
    };

    const LEVEL_COLORS = {
        CRITICAL: '#ef4444',
        HIGH: '#f97316',
        MODERATE: '#eab308',
        LOW: '#22c55e'
    };

    /**
     * Fetch summary and active alerts from backend
     */
    let currentFetchController = null;

    async function loadAlertsData() {
        if (currentFetchController) {
            currentFetchController.abort();
        }
        currentFetchController = new AbortController();
        const signal = currentFetchController.signal;

        alertsContainer.innerHTML = `
            <div class="text-center py-5 text-muted">
                <div class="spinner-border spinner-border-sm text-primary mb-2" role="status"></div>
                <div>Evaluating real-time early warning telemetry...</div>
            </div>
        `;

        const hazardVal = hazardFilter ? hazardFilter.value : 'all';
        const stateVal = stateFilter ? stateFilter.value : '';
        const levelVal = levelFilter ? levelFilter.value : '';

        const queryParams = new URLSearchParams();
        if (hazardVal) queryParams.set('hazard', hazardVal);
        if (stateVal) queryParams.set('state', stateVal);
        if (levelVal) queryParams.set('risk_level', levelVal);

        try {
            const [summaryRes, alertsRes] = await Promise.all([
                fetch('/api/alerts/summary', { signal }),
                fetch(`/api/alerts?${queryParams.toString()}`, { signal })
            ]);

            if (!summaryRes.ok || !alertsRes.ok) {
                throw new Error(`Server returned HTTP ${summaryRes.status}/${alertsRes.status}`);
            }

            const summaryData = await summaryRes.json();
            const alertsData = await alertsRes.json();

            if (summaryData.success && summaryData.summary) {
                updateKPIs(summaryData.summary);
                try {
                    renderDistributionChart(summaryData.summary.distribution);
                } catch (chartErr) {
                    console.warn("Chart rendering failed:", chartErr);
                }
                renderTopRiskLocations(summaryData.summary.top_risk_locations);
            } else {
                topRiskList.innerHTML = '<div class="text-muted small">No risk-ranked locations are currently available.</div>';
            }

            if (alertsData.success && Array.isArray(alertsData.alerts)) {
                allAlerts = alertsData.alerts;
                renderAlertsFeed(allAlerts);
                renderTimeline(allAlerts.slice(0, 6));
                lastUpdatedLabel.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
            } else {
                alertsContainer.innerHTML = `
                    <div class="alert alert-danger bg-dark text-danger border-danger">
                        ${alertsData.error || 'Early warning telemetry is temporarily unavailable.'}
                    </div>
                `;
            }
        } catch (err) {
            if (err.name === 'AbortError') return;
            console.error("Alerts data fetch error:", err);
            alertsContainer.innerHTML = `
                <div class="alert alert-danger bg-dark text-danger border-danger">
                    Early warning telemetry is temporarily unavailable.
                </div>
            `;
            topRiskList.innerHTML = '<div class="text-muted small">No risk-ranked locations are currently available.</div>';
            if (timelineContainer) {
                timelineContainer.innerHTML = '<div class="text-muted small">Advisory stream temporarily unavailable.</div>';
            }
        }
    }

    /**
     * Update KPI counter cards
     */
    function updateKPIs(summary) {
        if (!summary) return;
        kpiCritical.textContent = summary.critical_count || 0;
        kpiHigh.textContent = summary.high_count || 0;
        kpiModerate.textContent = summary.moderate_count || 0;
        kpiTotal.textContent = summary.total_monitored_stations || 64;
    }

    /**
     * Render Active Alerts cards
     */
    function renderAlertsFeed(alerts) {
        const query = (searchFilter ? searchFilter.value : '').trim().toLowerCase();
        const filtered = alerts.filter(a => {
            if (!query) return true;
            return (a.station_name && a.station_name.toLowerCase().includes(query)) ||
                   (a.district && a.district.toLowerCase().includes(query)) ||
                   (a.state_name && a.state_name.toLowerCase().includes(query)) ||
                   (a.alert_code && a.alert_code.toLowerCase().includes(query));
        });

        alertCountLabel.textContent = filtered.length;

        if (filtered.length === 0) {
            alertsContainer.innerHTML = `
                <div class="card bg-dark border-secondary-subtle p-5 text-center text-muted">
                    <div class="fs-1 mb-2">🛡️</div>
                    <h5 class="text-white">No active advisories match the selected filters.</h5>
                    <p class="small mb-0">No meteorological stations matched the selected criteria with elevated hazard thresholds.</p>
                </div>
            `;
            return;
        }

        alertsContainer.innerHTML = filtered.map(a => {
            const lvlClass = a.risk_level.toLowerCase();
            const badgeClass = `badge-${lvlClass}`;
            const icon = HAZARD_ICONS[a.hazard_type] || '⚡';
            const probPct = parseFloat(a.probability_pct || (a.probability * 100).toFixed(1));

            return `
                <div class="alert-card level-${lvlClass} p-3">
                    <div class="d-flex flex-column flex-sm-row justify-content-between align-items-sm-start gap-2 mb-2">
                        <div>
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <span class="fs-5">${icon}</span>
                                <h4 class="h6 fw-bold text-white mb-0">${a.station_name}</h4>
                                <span class="badge bg-secondary-subtle text-white-50 small">${a.district}, ${a.state_code}</span>
                            </div>
                            <div class="text-muted small">Code: <span class="font-monospace text-secondary">${a.alert_code}</span></div>
                        </div>
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge ${badgeClass} px-2.5 py-1 text-uppercase fw-bold">${a.risk_level} RISK</span>
                            <span class="fw-bold fs-6 text-white">${a.probability_pct}</span>
                        </div>
                    </div>

                    <!-- Progress Indicator -->
                    <div class="custom-progress mb-3">
                        <div class="h-100" style="width: ${probPct}%; background-color: ${a.badge_color};"></div>
                    </div>

                    <!-- Advisory Text -->
                    <p class="small text-white-50 mb-3">${a.advisory}</p>

                    <!-- Telemetry & Action Row -->
                    <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 pt-2 border-top border-secondary-subtle">
                        <div class="d-flex flex-wrap gap-1">
                            <span class="telemetry-chip text-white-50">🌧️ 24h: <strong class="text-white">${a.telemetry.rainfall_24h || 0} mm</strong></span>
                            <span class="telemetry-chip text-white-50">💨 Wind: <strong class="text-white">${a.telemetry.wind_speed || 0} m/s</strong></span>
                            <span class="telemetry-chip text-white-50">🏔️ Elev: <strong class="text-white">${a.elevation || 0} m</strong></span>
                        </div>
                        <button class="btn btn-outline-light btn-sm py-0 px-2 small btn-view-detail" data-alert-id="${a.alert_code}">
                            View Details &rarr;
                        </button>
                    </div>
                </div>
            `;
        }).join('');

        // Attach modal click handlers
        document.querySelectorAll('.btn-view-detail').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.currentTarget.getAttribute('data-alert-id');
                const alertItem = allAlerts.find(item => item.alert_code === id);
                if (alertItem) {
                    openDetailModal(alertItem);
                }
            });
        });
    }

    /**
     * Render Top 5 Highest Risk Locations
     */
    function renderTopRiskLocations(locations) {
        if (!locations || locations.length === 0) {
            topRiskList.innerHTML = '<div class="text-muted small">No risk-ranked locations are currently available.</div>';
            return;
        }

        topRiskList.innerHTML = locations.map((loc, idx) => {
            const color = LEVEL_COLORS[loc.risk_level] || '#94a3b8';
            return `
                <div class="d-flex justify-content-between align-items-center p-2 rounded-2" style="background: rgba(255,255,255,0.03);">
                    <div class="d-flex align-items-center gap-2">
                        <span class="fw-bold text-muted small">${idx + 1}.</span>
                        <div>
                            <div class="fw-bold text-white small">${loc.station_name}</div>
                            <div class="text-muted" style="font-size: 0.75rem;">${loc.district}, ${loc.state_code}</div>
                        </div>
                    </div>
                    <div class="text-end">
                        <span class="badge" style="background: ${color}20; color: ${color}; border: 1px solid ${color}40;">
                            ${loc.probability_pct}
                        </span>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Render Risk Distribution Chart
     */
    function renderDistributionChart(distribution) {
        if (!distribution) return;
        const canvas = document.getElementById('riskDistributionChart');
        if (!canvas) return;
        if (typeof Chart === 'undefined') {
            console.warn("Chart.js is not loaded; skipping distribution chart.");
            return;
        }
        const ctx = canvas.getContext('2d');
        const dataValues = [
            distribution.CRITICAL || 0,
            distribution.HIGH || 0,
            distribution.MODERATE || 0,
            distribution.LOW || 0
        ];

        if (distributionChart) {
            distributionChart.data.datasets[0].data = dataValues;
            distributionChart.update();
            return;
        }

        distributionChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Critical', 'High', 'Moderate', 'Low'],
                datasets: [{
                    data: dataValues,
                    backgroundColor: ['#ef4444', '#f97316', '#eab308', '#22c55e'],
                    borderColor: '#1e293b',
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#94a3b8',
                            boxWidth: 12,
                            padding: 10,
                            font: { size: 11 }
                        }
                    }
                },
                cutout: '70%'
            }
        });
    }

    /**
     * Render Timeline / Activity Stream
     */
    function renderTimeline(alerts) {
        if (!alerts || alerts.length === 0) {
            timelineContainer.innerHTML = '<div class="text-muted small">No recent advisory transitions.</div>';
            return;
        }

        timelineContainer.innerHTML = alerts.map(a => {
            const icon = HAZARD_ICONS[a.hazard_type] || '⚡';
            return `
                <div class="timeline-item">
                    <div class="fw-bold text-white">${icon} ${a.station_name} &bull; <span style="color: ${a.badge_color};">${a.risk_level}</span></div>
                    <div class="text-muted" style="font-size: 0.78rem;">${a.district}, ${a.state_code} &mdash; Probability: ${a.probability_pct}</div>
                </div>
            `;
        }).join('');
    }

    /**
     * Open Detail Modal
     */
    function openDetailModal(alert) {
        const color = LEVEL_COLORS[alert.risk_level] || '#94a3b8';
        modalBanner.style.backgroundColor = `${color}15`;
        modalBanner.style.border = `1px solid ${color}40`;

        modalHazardType.textContent = `${alert.hazard_type.toUpperCase()} HAZARD DOMAIN`;
        modalRiskLevel.textContent = `${alert.risk_level} RISK LEVEL`;
        modalRiskLevel.style.color = color;
        modalProbability.textContent = alert.probability_pct;
        modalProbability.style.color = color;

        modalSubLabel.textContent = `Location: ${alert.station_name}, District ${alert.district}, ${alert.state_name} (${alert.alert_code})`;
        modalAdvisoryText.textContent = alert.advisory;

        // Precautions
        if (alert.precautions && alert.precautions.length > 0) {
            modalPrecautionsList.innerHTML = alert.precautions.map(p => `
                <li class="d-flex align-items-start gap-2 text-white-50">
                    <span class="text-warning">⚠️</span>
                    <span>${p}</span>
                </li>
            `).join('');
        } else {
            modalPrecautionsList.innerHTML = '<li class="text-muted">Standard baseline caution.</li>';
        }

        // Telemetry Grid
        const tel = alert.telemetry || {};
        modalTelemetryGrid.innerHTML = `
            <div class="col-6 col-md-4">
                <div class="p-2 rounded-2 bg-secondary-subtle">
                    <div class="text-muted" style="font-size: 0.72rem;">24H RAINFALL</div>
                    <div class="fw-bold text-white">${tel.rainfall_24h || 0} mm</div>
                </div>
            </div>
            <div class="col-6 col-md-4">
                <div class="p-2 rounded-2 bg-secondary-subtle">
                    <div class="text-muted" style="font-size: 0.72rem;">72H CUMULATIVE</div>
                    <div class="fw-bold text-white">${tel.rainfall_72h || 0} mm</div>
                </div>
            </div>
            <div class="col-6 col-md-4">
                <div class="p-2 rounded-2 bg-secondary-subtle">
                    <div class="text-muted" style="font-size: 0.72rem;">7D TOTAL</div>
                    <div class="fw-bold text-white">${tel.rainfall_7d || 0} mm</div>
                </div>
            </div>
            <div class="col-6 col-md-4">
                <div class="p-2 rounded-2 bg-secondary-subtle">
                    <div class="text-muted" style="font-size: 0.72rem;">SURFACE TEMP</div>
                    <div class="fw-bold text-white">${tel.temperature || 0} &deg;C</div>
                </div>
            </div>
            <div class="col-6 col-md-4">
                <div class="p-2 rounded-2 bg-secondary-subtle">
                    <div class="text-muted" style="font-size: 0.72rem;">WIND SPEED</div>
                    <div class="fw-bold text-white">${tel.wind_speed || 0} m/s</div>
                </div>
            </div>
            <div class="col-6 col-md-4">
                <div class="p-2 rounded-2 bg-secondary-subtle">
                    <div class="text-muted" style="font-size: 0.72rem;">ELEVATION</div>
                    <div class="fw-bold text-white">${alert.elevation || 0} m</div>
                </div>
            </div>
        `;

        detailModal.show();
    }

    // Event Listeners
    [stateFilter, hazardFilter, levelFilter].forEach(elem => {
        elem.addEventListener('change', loadAlertsData);
    });

    let searchDebounceTimer = null;
    searchFilter.addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            renderAlertsFeed(allAlerts);
        }, 250);
    });

    refreshBtn.addEventListener('click', loadAlertsData);

    syncBtn.addEventListener('click', async () => {
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<span>⏳</span> Syncing...';
        try {
            const res = await fetch('/api/alerts/sync', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                alert(`Sync Complete: ${data.message}`);
            } else {
                alert(`Sync Failed: ${data.error}`);
            }
        } catch (err) {
            alert(`Network error during sync: ${err.message}`);
        } finally {
            syncBtn.disabled = false;
            syncBtn.innerHTML = '<span>🔄</span> Sync History';
        }
    });

    // Initial Load
    loadAlertsData();
});

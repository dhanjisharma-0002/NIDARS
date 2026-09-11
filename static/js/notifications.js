/**
 * NIDARS — Phase 18: Notification and Alert Center Client Controller.
 * Manages live notification polling, dropdown rendering, mark-as-read actions,
 * and Web Browser Push Notifications with explicit user consent.
 */

(function () {
    "use strict";

    var bellBtn = document.getElementById("nav-notifications-btn");
    var badge = document.getElementById("nav-notification-badge");
    var listContainer = document.getElementById("notifications-list-container");
    var btnMarkAll = document.getElementById("btn-mark-all-read");
    var btnBrowserAlerts = document.getElementById("btn-enable-browser-alerts");

    // If notification UI is not present (e.g. unauthenticated guest), exit cleanly
    if (!bellBtn || !badge || !listContainer) {
        return;
    }

    var knownIds = new Set();
    var isFirstLoad = true;

    function getCsrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
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

    function updateBadge(count) {
        if (!badge) return;
        var unread = parseInt(count, 10) || 0;
        if (unread > 0) {
            badge.textContent = unread > 99 ? "99+" : unread;
            badge.style.display = "flex";
            badge.classList.add("pulse");
        } else {
            badge.textContent = "0";
            badge.style.display = "none";
            badge.classList.remove("pulse");
        }
    }

    function getRiskBadgeHtml(riskLevel) {
        var lvl = (riskLevel || "MODERATE").toUpperCase();
        var cls = "bg-warning text-dark";
        if (lvl === "CRITICAL") cls = "bg-purple text-white";
        else if (lvl === "HIGH") cls = "bg-danger text-white";
        else if (lvl === "LOW") cls = "bg-success text-white";

        return '<span class="badge ' + cls + '" style="font-size: 0.65rem; padding: 0.2rem 0.4rem;">' + escapeHtml(lvl) + "</span>";
    }

    function getTypeIcon(notifType) {
        var t = (notifType || "").toLowerCase();
        if (t.indexOf("flood") !== -1) return "🌊";
        if (t.indexOf("landslide") !== -1) return "⛰️";
        if (t.indexOf("route") !== -1) return "🛣️";
        if (t.indexOf("emergency") !== -1) return "🚨";
        return "⚠️";
    }

    function renderNotifications(notifications, unreadCount) {
        updateBadge(unreadCount);

        if (!listContainer) return;

        if (!notifications || notifications.length === 0) {
            listContainer.innerHTML = [
                '<div class="notification-empty-box">',
                '<div style="font-size: 1.8rem; margin-bottom: 0.5rem;">✨</div>',
                '<div class="small fw-semibold text-light">No Active Advisories</div>',
                '<div class="small text-muted" style="font-size: 0.75rem;">All monitored regional zones are currently within baseline safety limits.</div>',
                "</div>",
            ].join("");
            return;
        }

        var html = "";
        notifications.forEach(function (item) {
            var isUnread = !item.is_read;
            var itemCls = "notification-item" + (isUnread ? " unread" : " text-opacity-75");
            var icon = getTypeIcon(item.notification_type);
            var riskBadge = getRiskBadgeHtml(item.risk_level);
            var timeStr = item.created_at_human || (item.created_at ? new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");

            html += [
                '<div class="' + itemCls + '" id="notif-item-' + item.id + '">',
                '  <div class="notification-item-header">',
                '    <div class="d-flex align-items-center gap-2">',
                '      <span style="font-size: 1rem;">' + icon + '</span>',
                '      <span class="notification-item-title">' + escapeHtml(item.title) + "</span>",
                "    </div>",
                '    <span class="notification-item-time">' + escapeHtml(timeStr) + "</span>",
                "  </div>",
                '  <p class="notification-item-msg">' + escapeHtml(item.message) + "</p>",
                '  <div class="notification-item-footer">',
                '    <div class="d-flex align-items-center gap-1">',
                '      <span class="text-muted small" style="font-size: 0.7rem;">📍 ' + escapeHtml(item.location_name || "Regional") + "</span>",
                "      " + riskBadge,
                "    </div>",
                isUnread
                    ? '    <button type="button" class="btn-mark-read" data-id="' + item.id + '">✓ Mark Read</button>'
                    : '    <span class="text-muted small" style="font-size: 0.68rem;">Read</span>',
                "  </div>",
                "</div>",
            ].join("");

            // Check if we should trigger a browser push notification for new arrivals
            if (!isFirstLoad && isUnread && !knownIds.has(item.id)) {
                dispatchBrowserNotification(item);
            }
            knownIds.add(item.id);
        });

        listContainer.innerHTML = html;

        // Attach click listeners to mark individual items as read
        var readBtns = listContainer.querySelectorAll(".btn-mark-read");
        readBtns.forEach(function (btn) {
            btn.addEventListener("click", function (e) {
                e.stopPropagation();
                var notifId = btn.getAttribute("data-id");
                markSingleRead(notifId);
            });
        });
    }

    function fetchNotifications() {
        fetch("/api/notifications?limit=25", {
            method: "GET",
            headers: { "Accept": "application/json" },
            credentials: "same-origin",
        })
            .then(function (res) {
                if (!res.ok) throw new Error("HTTP " + res.status);
                return res.json();
            })
            .then(function (data) {
                if (data.success) {
                    renderNotifications(data.notifications, data.unread_count);
                    isFirstLoad = false;
                }
            })
            .catch(function (err) {
                console.warn("[NIDARS Notifications] Failed to fetch notifications:", err);
            });
    }

    function pollStats() {
        fetch("/api/notifications/stats", {
            method: "GET",
            headers: { "Accept": "application/json" },
            credentials: "same-origin",
        })
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (data) {
                if (data && data.success) {
                    var currBadgeCount = parseInt(badge.textContent, 10) || 0;
                    if (data.unread_count !== currBadgeCount) {
                        fetchNotifications();
                    }
                }
            })
            .catch(function () {
                // Silently ignore polling hiccups
            });
    }

    function markSingleRead(notifId) {
        if (!notifId) return;
        fetch("/api/notifications/" + notifId + "/read", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                if (data.success) {
                    var el = document.getElementById("notif-item-" + notifId);
                    if (el) {
                        el.classList.remove("unread");
                        el.classList.add("text-opacity-75");
                        var footerBtn = el.querySelector(".btn-mark-read");
                        if (footerBtn) {
                            var span = document.createElement("span");
                            span.className = "text-muted small";
                            span.style.fontSize = "0.68rem";
                            span.textContent = "Read";
                            footerBtn.parentNode.replaceChild(span, footerBtn);
                        }
                    }
                    updateBadge(data.unread_count);
                }
            })
            .catch(function (err) {
                console.error("Failed to mark notification as read", err);
            });
    }

    function markAllRead() {
        fetch("/api/notifications/read-all", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            credentials: "same-origin",
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                if (data.success) {
                    var items = listContainer.querySelectorAll(".notification-item.unread");
                    items.forEach(function (item) {
                        item.classList.remove("unread");
                        item.classList.add("text-opacity-75");
                        var footerBtn = item.querySelector(".btn-mark-read");
                        if (footerBtn) {
                            var span = document.createElement("span");
                            span.className = "text-muted small";
                            span.style.fontSize = "0.68rem";
                            span.textContent = "Read";
                            footerBtn.parentNode.replaceChild(span, footerBtn);
                        }
                    });
                    updateBadge(0);
                }
            })
            .catch(function (err) {
                console.error("Failed to mark all as read", err);
            });
    }

    // Web Browser Notifications Integration
    function initBrowserNotificationControls() {
        if (!btnBrowserAlerts) return;

        if (!("Notification" in window)) {
            btnBrowserAlerts.style.display = "none";
            return;
        }

        updateBrowserAlertButtonState();

        btnBrowserAlerts.addEventListener("click", function (e) {
            e.stopPropagation();
            if (Notification.permission === "default") {
                Notification.requestPermission().then(function (permission) {
                    updateBrowserAlertButtonState();
                    if (permission === "granted") {
                        try {
                            new Notification("NIDARS Disaster Alerts Enabled", {
                                body: "You will now receive desktop notifications for urgent risk threshold advisories.",
                                icon: "/static/img/nidars-badge.png",
                            });
                        } catch (err) {
                            // Browser notification fallback
                        }
                    }
                });
            } else if (Notification.permission === "granted") {
                // Already enabled
                btnBrowserAlerts.textContent = "✓ Push On";
            }
        });
    }

    function updateBrowserAlertButtonState() {
        if (!btnBrowserAlerts) return;
        if (Notification.permission === "granted") {
            btnBrowserAlerts.textContent = "✓ Push On";
            btnBrowserAlerts.className = "btn btn-sm btn-outline-success py-0 px-2";
            btnBrowserAlerts.title = "Browser Push Alerts Active";
        } else if (Notification.permission === "denied") {
            btnBrowserAlerts.textContent = "Push Blocked";
            btnBrowserAlerts.className = "btn btn-sm btn-outline-secondary py-0 px-2 disabled";
            btnBrowserAlerts.title = "Push notifications blocked in browser site permissions";
        } else {
            btnBrowserAlerts.textContent = "Push Alerts";
            btnBrowserAlerts.className = "btn btn-sm btn-outline-info py-0 px-2";
            btnBrowserAlerts.title = "Click to Enable Web Browser Push Alerts";
        }
    }

    function dispatchBrowserNotification(item) {
        if (!("Notification" in window) || Notification.permission !== "granted") {
            return;
        }

        try {
            var title = "⚠️ NIDARS: " + item.title;
            var options = {
                body: item.message || "A new risk advisory has been issued.",
                icon: "/static/img/nidars-badge.png",
                tag: "nidars-notif-" + item.id,
            };
            var notif = new Notification(title, options);
            notif.onclick = function () {
                window.focus();
                this.close();
            };
        } catch (err) {
            console.warn("Could not display native desktop notification", err);
        }
    }

    // Attach Event Listeners
    if (btnMarkAll) {
        btnMarkAll.addEventListener("click", function (e) {
            e.stopPropagation();
            markAllRead();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initBrowserNotificationControls();
        fetchNotifications();

        // Background polling every 30 seconds
        setInterval(pollStats, 30000);
    });
})();

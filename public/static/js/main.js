/**
 * NIDARS — Global Core JavaScript & UI Utilities
 * AI Disaster Risk & Safe Route Optimization Platform
 */

(function () {
    "use strict";

    // --- Theme Management (Dark / Light Mode) ---
    function initTheme() {
        var savedTheme = localStorage.getItem("nidars_theme") || "dark";
        setTheme(savedTheme, false);

        var desktopToggle = document.getElementById("theme-toggle-btn");
        var mobileToggle = document.getElementById("mobile-theme-toggle");

        function handleToggle() {
            var currentTheme = document.documentElement.getAttribute("data-bs-theme") || "dark";
            var nextTheme = currentTheme === "dark" ? "light" : "dark";
            setTheme(nextTheme, true);
            localStorage.setItem("nidars_theme", nextTheme);
        }

        if (desktopToggle) {
            desktopToggle.addEventListener("click", handleToggle);
        }
        if (mobileToggle) {
            mobileToggle.addEventListener("click", handleToggle);
        }
    }

    function setTheme(theme, broadcast) {
        document.documentElement.setAttribute("data-bs-theme", theme);
        var icons = document.querySelectorAll(".theme-icon");
        icons.forEach(function (icon) {
            icon.textContent = theme === "dark" ? "🌙" : "☀️";
        });

        if (broadcast) {
            var evt = new CustomEvent("nidars-theme-changed", { detail: { theme: theme } });
            document.dispatchEvent(evt);
        }
    }

    // --- Global Toast Notification Utility ---
    window.NidarsToast = {
        show: function (message, type, duration) {
            var container = document.getElementById("nidars-toast-container");
            if (!container) return;

            type = type || "info"; // 'success', 'danger', 'warning', 'info'
            duration = duration || 4000;

            var icon = "ℹ️";
            if (type === "success") icon = "✅";
            else if (type === "danger") icon = "⚠️";
            else if (type === "warning") icon = "⚡";

            var toastId = "toast-" + Date.now() + "-" + Math.floor(Math.random() * 1000);
            var toastEl = document.createElement("div");
            toastEl.className = "toast nidars-toast toast-" + type + " align-items-center show mb-2";
            toastEl.id = toastId;
            toastEl.setAttribute("role", "alert");
            toastEl.setAttribute("aria-live", "assertive");
            toastEl.setAttribute("aria-atomic", "true");

            toastEl.innerHTML = [
                '<div class="d-flex p-2 align-items-center justify-content-between gap-2">',
                '  <div class="d-flex align-items-center gap-2 small">',
                '    <span style="font-size: 1.1rem;">' + icon + '</span>',
                '    <div class="toast-body p-0 fw-semibold">' + message + '</div>',
                '  </div>',
                '  <button type="button" class="btn-close btn-close-white me-1 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>',
                '</div>',
            ].join("");

            container.appendChild(toastEl);

            var bsToast = new bootstrap.Toast(toastEl, { delay: duration, autohide: true });
            bsToast.show();

            toastEl.addEventListener("hidden.bs.toast", function () {
                if (toastEl.parentNode) toastEl.parentNode.removeChild(toastEl);
            });
        },
    };

    // --- Global Confirmation Dialog Helper ---
    window.NidarsConfirm = {
        show: function (options) {
            options = options || {};
            var modalEl = document.getElementById("nidarsConfirmModal");
            if (!modalEl || typeof bootstrap === "undefined") {
                if (window.confirm(options.message || "Are you sure?")) {
                    if (typeof options.onConfirm === "function") options.onConfirm();
                }
                return;
            }

            var titleEl = document.getElementById("nidars-confirm-title");
            var iconEl = document.getElementById("nidars-confirm-icon");
            var msgEl = document.getElementById("nidars-confirm-message");
            var okBtn = document.getElementById("nidars-confirm-ok-btn");
            var cancelBtn = document.getElementById("nidars-confirm-cancel-btn");

            if (titleEl) titleEl.textContent = options.title || "Confirm Action";
            if (iconEl) iconEl.textContent = options.icon || "⚠️";
            if (msgEl) msgEl.textContent = options.message || "Are you sure you want to proceed?";
            if (okBtn) {
                okBtn.textContent = options.confirmText || "Confirm";
                okBtn.className = "btn btn-sm " + (options.confirmClass || "btn-danger");
            }
            if (cancelBtn) cancelBtn.textContent = options.cancelText || "Cancel";

            var bsModal = new bootstrap.Modal(modalEl);

            // Handle confirm click
            function handleConfirm() {
                okBtn.removeEventListener("click", handleConfirm);
                bsModal.hide();
                if (typeof options.onConfirm === "function") {
                    options.onConfirm();
                }
            }

            okBtn.addEventListener("click", handleConfirm);
            bsModal.show();
        },
    };

    // --- Live System Status Checker (/api/health) ---
    function checkSystemHealth() {
        var statusPill = document.getElementById("system-status-pill");
        var statusText = document.getElementById("system-status-text");
        var mobilePill = document.getElementById("mobile-system-status");
        var chip = document.getElementById("app-status-chip");
        var jsonBox = document.getElementById("health-json");
        var hint = document.getElementById("health-hint");

        fetch("/api/health")
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("HTTP error " + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                if (statusPill) {
                    statusPill.className = "system-status-pill online d-none d-xl-inline-flex";
                    if (statusText) statusText.textContent = "SYSTEM ONLINE";
                }
                if (mobilePill) {
                    mobilePill.className = "system-status-pill online";
                }
                if (chip) {
                    chip.textContent = "Service running";
                    chip.classList.remove("is-down");
                    chip.classList.add("is-ok");
                }
                if (hint) {
                    hint.textContent = data.status || "running";
                }
                if (jsonBox) {
                    jsonBox.textContent = JSON.stringify(data, null, 2);
                }
            })
            .catch(function () {
                if (statusPill) {
                    statusPill.className = "system-status-pill offline d-none d-xl-inline-flex";
                    if (statusText) statusText.textContent = "SERVICE DEGRADED";
                }
                if (mobilePill) {
                    mobilePill.className = "system-status-pill offline";
                }
                if (chip) {
                    chip.textContent = "Service unreachable";
                    chip.classList.remove("is-ok");
                    chip.classList.add("is-down");
                }
                if (hint) {
                    hint.textContent = "Unreachable";
                }
                if (jsonBox) {
                    jsonBox.textContent = "Unable to reach /api/health.";
                }
            });
    }

    // --- Responsive Mobile Navbar Collapse ---
    function setupMobileNav() {
        var navCollapse = document.getElementById("mainNav");
        if (!navCollapse) return;

        var navLinks = navCollapse.querySelectorAll(".nav-link:not(.dropdown-toggle)");
        navLinks.forEach(function (link) {
            link.addEventListener("click", function () {
                if (window.innerWidth < 1200 && typeof bootstrap !== "undefined") {
                    var bsCollapse = bootstrap.Collapse.getInstance(navCollapse);
                    if (bsCollapse) bsCollapse.hide();
                }
            });
        });
    }

    // --- CSRF Helper ---
    window.getCsrfToken = function () {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute("content") : "";
    };

    // --- Number Counter Animation ---
    window.animateCounter = function (element, target, duration) {
        if (!element) return;
        var start = 0;
        var steps = 30;
        var stepDuration = duration / steps;
        var increment = target / steps;
        var current = 0;

        var timer = setInterval(function () {
            current += increment;
            if (current >= target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(current);
            }
        }, stepDuration);
    };

    // --- Movable Hamburger Navigation System ---
    function initMovableNav() {
        var wrapper = document.getElementById("nidarsMovableNavWrapper");
        var button = document.getElementById("nidarsHamburgerBtn");
        var menu = document.getElementById("nidarsNavMenu");
        var backdrop = document.getElementById("nidarsMenuBackdrop");
        var closeBtn = document.getElementById("nidarsMenuCloseBtn");
        var hint = document.getElementById("nidarsDragHint");

        if (!wrapper || !button || !menu) return;

        var STORAGE_KEY_TOP = "nidar_hamburger_top";
        var STORAGE_KEY_HINT = "nidar_hamburger_hint_seen";
        var MIN_TOP = 70;
        var MIN_BOTTOM = 20;
        var DEFAULT_TOP = 75;
        var BUTTON_HEIGHT = 44;

        // Check first-use hint status
        if (localStorage.getItem(STORAGE_KEY_HINT) === "true") {
            if (hint) hint.classList.add("is-hidden");
        }

        // Clamp vertical position safely within viewport
        function getSafeTop(targetTop) {
            var maxTop = window.innerHeight - BUTTON_HEIGHT - MIN_BOTTOM;
            if (maxTop < MIN_TOP) maxTop = MIN_TOP;
            return Math.max(MIN_TOP, Math.min(maxTop, targetTop));
        }

        // Restore saved position or use default
        var savedTop = localStorage.getItem(STORAGE_KEY_TOP);
        var initialTop = savedTop ? parseInt(savedTop, 10) : DEFAULT_TOP;
        if (isNaN(initialTop)) initialTop = DEFAULT_TOP;
        var currentTop = getSafeTop(initialTop);
        wrapper.style.top = currentTop + "px";

        // Dynamically position opened menu attached to the button
        function updateMenuPosition() {
            if (!menu.classList.contains("is-open")) return;
            var menuHeight = menu.offsetHeight || 420;
            var winH = window.innerHeight;
            var maxMenuTop = winH - menuHeight - MIN_BOTTOM;
            var targetMenuTop = currentTop;
            if (targetMenuTop > maxMenuTop) {
                targetMenuTop = Math.max(MIN_TOP, maxMenuTop);
            }
            menu.style.top = targetMenuTop + "px";
        }

        function openMenu() {
            menu.classList.add("is-open");
            if (backdrop) backdrop.classList.add("is-open");
            button.classList.add("is-active");
            button.setAttribute("aria-expanded", "true");
            button.setAttribute("aria-label", "Close navigation menu");
            updateMenuPosition();
            if (hint && !hint.classList.contains("is-hidden")) {
                hint.classList.add("is-hidden");
                localStorage.setItem(STORAGE_KEY_HINT, "true");
            }
        }

        function closeMenu() {
            menu.classList.remove("is-open");
            if (backdrop) backdrop.classList.remove("is-open");
            button.classList.remove("is-active");
            button.setAttribute("aria-expanded", "false");
            button.setAttribute("aria-label", "Open navigation menu");
        }

        function toggleMenu() {
            if (menu.classList.contains("is-open")) {
                closeMenu();
            } else {
                openMenu();
            }
        }

        // Vertical Drag Handlers via Pointer Events (Mouse + Touch)
        var isPointerDown = false;
        var isDragging = false;
        var startY = 0;
        var startTop = 0;
        var DRAG_THRESHOLD = 8; // px threshold to distinguish drag vs click

        function onPointerDown(e) {
            // Only primary button (left click) or touch
            if (e.button !== undefined && e.button !== 0) return;
            isPointerDown = true;
            isDragging = false;
            startY = e.clientY;
            startTop = currentTop;
            try {
                button.setPointerCapture(e.pointerId);
            } catch (err) {}
        }

        function onPointerMove(e) {
            if (!isPointerDown) return;
            var deltaY = e.clientY - startY;

            if (!isDragging && Math.abs(deltaY) > DRAG_THRESHOLD) {
                isDragging = true;
                button.classList.add("is-dragging");
                if (hint && !hint.classList.contains("is-hidden")) {
                    hint.classList.add("is-hidden");
                    localStorage.setItem(STORAGE_KEY_HINT, "true");
                }
            }

            if (isDragging) {
                e.preventDefault();
                var newTop = getSafeTop(startTop + deltaY);
                currentTop = newTop;
                wrapper.style.top = newTop + "px";
                updateMenuPosition();
            }
        }

        function onPointerUp(e) {
            if (!isPointerDown) return;
            isPointerDown = false;
            try {
                button.releasePointerCapture(e.pointerId);
            } catch (err) {}

            if (isDragging) {
                button.classList.remove("is-dragging");
                localStorage.setItem(STORAGE_KEY_TOP, currentTop.toString());
                // Prevent click handler from firing right after a drag
                setTimeout(function () {
                    isDragging = false;
                }, 60);
            } else {
                toggleMenu();
            }
        }

        function onPointerCancel() {
            isPointerDown = false;
            isDragging = false;
            button.classList.remove("is-dragging");
        }

        button.addEventListener("pointerdown", onPointerDown);
        button.addEventListener("pointermove", onPointerMove);
        button.addEventListener("pointerup", onPointerUp);
        button.addEventListener("pointercancel", onPointerCancel);

        // Close button click
        if (closeBtn) {
            closeBtn.addEventListener("click", closeMenu);
        }

        // Backdrop click closes menu
        if (backdrop) {
            backdrop.addEventListener("click", closeMenu);
        }

        // ESC key closes menu
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && menu.classList.contains("is-open")) {
                closeMenu();
                button.focus();
            }
        });

        // Close menu on link navigation click (for smooth SPA / page transition feel)
        var menuLinks = menu.querySelectorAll(".nidars-menu-item");
        menuLinks.forEach(function (link) {
            link.addEventListener("click", function () {
                closeMenu();
            });
        });

        // On window resize: keep button and menu clamped within new viewport bounds
        window.addEventListener("resize", function () {
            currentTop = getSafeTop(currentTop);
            wrapper.style.top = currentTop + "px";
            updateMenuPosition();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initTheme();
        checkSystemHealth();
        setupMobileNav();
        initMovableNav();
    });
})();

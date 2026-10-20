/**
 * SOU Ride - Client Utilities & Interactive Behaviors
 * Ahmedabad, Gujarat, India - Campus Mobility Platform
 */

document.addEventListener("DOMContentLoaded", () => {
    // 0. Theme Synchronization
    const currentTheme = localStorage.getItem("sou_ride_theme") || "purple";
    document.querySelectorAll(".theme-select-dropdown").forEach(select => {
        select.value = currentTheme;
        select.addEventListener("change", (e) => {
            const chosen = e.target.value;
            document.documentElement.setAttribute("data-theme", chosen);
            localStorage.setItem("sou_ride_theme", chosen);
            document.querySelectorAll(".theme-select-dropdown").forEach(other => {
                other.value = chosen;
            });
        });
    });

    // 1. Mobile Sidebar Navigation
    const mobileMenuBtn = document.getElementById("mobileMenuBtn");
    const sidebar = document.getElementById("sidebar");
    const sidebarOverlay = document.getElementById("sidebarOverlay");

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener("click", () => {
            sidebar.classList.toggle("open");
            if (sidebarOverlay) sidebarOverlay.classList.toggle("active");
        });
    }

    if (sidebarOverlay) {
        sidebarOverlay.addEventListener("click", () => {
            if (sidebar) sidebar.classList.remove("open");
            sidebarOverlay.classList.remove("active");
        });
    }

    // 2. Alert Dismissal
    document.querySelectorAll(".alert-close").forEach(btn => {
        btn.addEventListener("click", () => {
            const alert = btn.closest(".alert");
            if (alert) {
                alert.style.opacity = "0";
                setTimeout(() => alert.remove(), 250);
            }
        });
    });

    // Auto-dismiss success flash after 5 seconds
    setTimeout(() => {
        document.querySelectorAll(".alert-success").forEach(alert => {
            alert.style.opacity = "0";
            setTimeout(() => alert.remove(), 250);
        });
    }, 5000);

    // 3. Location Preset Chips (Click chip to populate form input)
    document.querySelectorAll(".location-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const targetInputId = chip.dataset.targetInput;
            const targetVal = chip.dataset.locationValue;
            if (targetInputId && targetVal) {
                const input = document.getElementById(targetInputId);
                if (input) {
                    input.value = targetVal;
                    input.focus();
                }
            }
        });
    });

    // 4. Prototype SOS Modal Toggle
    const sosModalBtn = document.getElementById("sosModalBtn");
    const sosModalOverlay = document.getElementById("sosModalOverlay");
    const sosModalClose = document.getElementById("sosModalClose");

    if (sosModalBtn && sosModalOverlay) {
        sosModalBtn.addEventListener("click", (e) => {
            e.preventDefault();
            sosModalOverlay.classList.add("active");
        });
    }

    if (sosModalClose && sosModalOverlay) {
        sosModalClose.addEventListener("click", () => {
            sosModalOverlay.classList.remove("active");
        });
    }

    if (sosModalOverlay) {
        sosModalOverlay.addEventListener("click", (e) => {
            if (e.target === sosModalOverlay) {
                sosModalOverlay.classList.remove("active");
            }
        });
    }

    // 5. Leaflet Map Initialization for Ahmedabad / SOU Commute
    initLeafletMaps();
});

// Map Coordinates & Known Ahmedabad Hubs
const SOU_CAMPUS_COORDS = [23.0886, 72.5348]; // Silver Oak University, Gota, Ahmedabad
const AHMEDABAD_LOCATIONS_MAP = {
    "silver oak university": [23.0886, 72.5348],
    "gota": [23.0900, 72.5300],
    "vaishno devi": [23.1120, 72.5440],
    "chandkheda": [23.1100, 72.5850],
    "ranip": [23.0780, 72.5750],
    "vastrapur": [23.0350, 72.5290],
    "geeta mandir": [23.0130, 72.5890],
    "kalupur": [23.0270, 72.6010],
    "gandhinagar": [23.2156, 72.6369],
    "science city": [23.0780, 72.5020],
    "navrangpura": [23.0360, 72.5590],
    "bopal": [23.0330, 72.4680]
};

function initLeafletMaps() {
    const mapElement = document.getElementById("leafletRouteMap");
    if (!mapElement) return;

    if (typeof L === "undefined") {
        console.warn("Leaflet library not loaded, showing fallback display.");
        return;
    }

    try {
        const sourceName = (mapElement.dataset.source || "Silver Oak University").toLowerCase();
        const destName = (mapElement.dataset.destination || "Geeta Mandir").toLowerCase();

        // Find nearest coordinate matches or default
        let sourceCoords = SOU_CAMPUS_COORDS;
        let destCoords = [23.0130, 72.5890]; // Geeta Mandir default

        for (const [key, coords] of Object.entries(AHMEDABAD_LOCATIONS_MAP)) {
            if (sourceName.includes(key)) sourceCoords = coords;
            if (destName.includes(key)) destCoords = coords;
        }

        const map = L.map("leafletRouteMap").setView(SOU_CAMPUS_COORDS, 12);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 18
        }).addTo(map);

        // Custom Markers
        const sourceMarker = L.marker(sourceCoords).addTo(map)
            .bindPopup(`<b>Pickup Point</b><br>${mapElement.dataset.source || 'SOU Campus'}`)
            .openPopup();

        const destMarker = L.marker(destCoords).addTo(map)
            .bindPopup(`<b>Destination</b><br>${mapElement.dataset.destination || 'Drop-off'}`);

        // Route Polyline
        const polyline = L.polyline([sourceCoords, destCoords], {
            color: "#6D28D9",
            weight: 4,
            opacity: 0.8,
            dashArray: "6, 8"
        }).addTo(map);

        map.fitBounds(polyline.getBounds(), { padding: [40, 40] });

        // Hide fallback overlay
        const fallback = mapElement.querySelector(".map-fallback");
        if (fallback) fallback.style.display = "none";

    } catch (err) {
        console.warn("Error rendering Leaflet map:", err);
    }
}

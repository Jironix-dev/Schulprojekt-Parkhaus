// Aktualisiere die aktuelle Zeit
function updateTime() {
    const now = new Date();
    
    // Formatiere Zeit (HH:MM:SS)
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    document.getElementById("current-time").innerText = `${hours}:${minutes}:${seconds}`;
    
    // Formatiere Datum (DD.MM.YYYY)
    const day = String(now.getDate()).padStart(2, '0');
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const year = now.getFullYear();
    document.getElementById("current-date").innerText = `${day}.${month}.${year}`;
}

// Live-Feed Management - nutze Motion JPEG Stream (nicht einzelne Frames!)
function initializeLiveFeed() {
    const feedImg = document.getElementById("live-feed-img");
    if (feedImg) {
        // Nutze den Motion JPEG Stream direkt - NICHT updateLiveFeed aufrufen!
        feedImg.src = "/api/stream";
        feedImg.style.display = "block";
    }
}

// Nur für Debugging: Einzelnen Frame abrufen (optional)
function getStaticFrame() {
    const feedImg = document.getElementById("live-feed-img");
    if (feedImg) {
        feedImg.src = "/api/camera/frame?t=" + Date.now();
    }
}

// Modal-Funktionen
function openModal(modalType) {
    const modalId = `modal-${modalType}`;
    const modal = document.getElementById(modalId);
    
    if (modal) {
        modal.classList.add('active');
        loadModalData(modalType);
    }
}

function closeModal(modalType) {
    const modalId = `modal-${modalType}`;
    const modal = document.getElementById(modalId);
    
    if (modal) {
        modal.classList.remove('active');
    }
}

// Schließe Modal beim Klick außerhalb
document.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
});

// Lade Modal-Daten basierend auf Typ
async function loadModalData(modalType) {
    let endpoint = '';
    let listId = '';
    
    switch(modalType) {
        case 'costs':
            endpoint = '/api/widget/costs';
            listId = 'costs-list';
            break;
        case 'durations':
            endpoint = '/api/widget/durations';
            listId = 'durations-list';
            break;
        case 'plate-recognition':
            endpoint = '/api/widget/plate-recognition';
            listId = 'plate-recognition-list';
            break;
        case 'status':
            endpoint = '/api/widget/status';
            listId = 'status-list';
            break;
        case 'known-vehicles':
            endpoint = '/api/widget/known-vehicles';
            listId = 'known-vehicles-list';
            break;
        case 'stats':
            loadStatsModal();
            return;
        default:
            return;
    }
    
    try {
        const response = await fetch(endpoint);
        const data = await response.json();
        
        displayModalData(modalType, data, listId);
    } catch (error) {
        console.error(`Fehler beim Laden von ${modalType}:`, error);
        document.getElementById(listId).innerHTML = '<p class="loading">Fehler beim Laden der Daten</p>';
    }
}

// Zeige Modal-Daten an
function displayModalData(modalType, data, listId) {
    const container = document.getElementById(listId);
    
    if (!data.vehicles || data.vehicles.length === 0) {
        container.innerHTML = '<p class="loading">Keine Fahrzeuge im Parkhaus</p>';
        return;
    }
    
    let html = '';
    
    switch(modalType) {
        case 'costs':
            data.vehicles.forEach(v => {
                html += `
                    <div class="data-item">
                        <div class="data-item-main">
                            <span class="data-item-plate">${v.license_plate}</span>
                            <span class="data-item-secondary">Eingabe: ${new Date(v.entry_time).toLocaleString('de-DE')}</span>
                        </div>
                        <div>
                            <div class="data-item-value highlight">${v.cost_calculated.toFixed(2)} €</div>
                            <span class="data-item-secondary">${v.payment_confirmed ? '✓ Bezahlt' : 'Ausstehend'}</span>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
            document.getElementById('total-costs').innerText = data.total.toFixed(2);
            break;
            
        case 'durations':
            data.vehicles.forEach(v => {
                html += `
                    <div class="data-item">
                        <div class="data-item-main">
                            <span class="data-item-plate">${v.license_plate}</span>
                            <span class="data-item-secondary">Eingabe: ${new Date(v.entry_time).toLocaleString('de-DE')}</span>
                        </div>
                        <div>
                            <div class="data-item-value">${v.parking_duration_formatted}</div>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
            document.getElementById('avg-duration').innerText = data.average_duration_minutes.toFixed(1);
            break;
            
        case 'plate-recognition':
            data.vehicles.forEach(v => {
                html += `
                    <div class="data-item">
                        <div class="data-item-main">
                            <span class="data-item-plate">${v.license_plate}</span>
                            <span class="data-item-secondary">Erkannt: ${v.detected_plate || 'N/A'}</span>
                        </div>
                        <div style="text-align: right;">
                            <div class="data-item-value">${v.confidence_score}%</div>
                            <span class="data-item-secondary">${v.detection_count} Erkennungen</span>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
            document.getElementById('avg-confidence').innerText = data.average_confidence.toFixed(1);
            break;
            
        case 'status':
            data.vehicles.forEach(v => {
                html += `
                    <div class="data-item">
                        <div class="data-item-main">
                            <span class="data-item-plate">${v.license_plate}</span>
                            <span class="data-item-secondary">Status: ${v.vehicle_status}</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="data-item-value">${v.total_sessions} Sessions</span>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
            break;
            
        case 'known-vehicles':
            data.vehicles.forEach(v => {
                const lastSeen = v.last_seen_at ? new Date(v.last_seen_at).toLocaleString('de-DE') : 'Unbekannt';
                const firstSeen = v.first_seen_at ? new Date(v.first_seen_at).toLocaleString('de-DE') : 'Unbekannt';
                html += `
                    <div class="data-item">
                        <div class="data-item-main">
                            <span class="data-item-plate">${v.license_plate}</span>
                            <span class="data-item-secondary">Status: ${v.status}</span>
                            <span class="data-item-secondary" style="font-size: 0.8em;">Zuletzt: ${lastSeen}</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="data-item-value">${v.total_sessions}</span>
                            <span class="data-item-secondary">Sessions</span>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
            document.getElementById('known-vehicles-count').innerText = data.count;
            break;
            break;
    }
}

// Lade Statistiken Modal
function loadStatsModal() {
    fetch('/api/status')
    .then(res => res.json())
    .then(data => {
        document.getElementById('modal-entries').innerText = data.today_stats.entries_today;
        document.getElementById('modal-exits').innerText = data.today_stats.exits_today;
        document.getElementById('modal-revenue').innerText = data.today_stats.revenue_today.toFixed(2) + ' €';
    })
    .catch(err => console.error('Fehler:', err));
}

function update() {
    fetch("/api/status")
    .then(res => res.json())
    .then(data => {
        // Kapazität aktualisieren
        document.getElementById("total-spaces").innerText = data.parking_capacity.total_spaces;
        document.getElementById("occupied-spaces").innerText = data.parking_capacity.occupied_spaces;
        document.getElementById("available-spaces").innerText = data.parking_capacity.available_spaces;
        document.getElementById("occupancy-rate").innerText = data.parking_capacity.occupancy_rate + "%";
        
        // Aktive Session aktualisieren
        if (data.active_session) {
            document.getElementById("plate").innerText = data.active_session.license_plate;
            document.getElementById("duration").innerText = data.active_session.parking_duration_minutes + " Min";
            document.getElementById("entry-time").innerText = data.active_session.entry_time.substring(0, 16);
            document.getElementById("confidence").innerText = (data.active_session.confidence_score ? (data.active_session.confidence_score * 100).toFixed(1) + "%" : "N/A");
            document.getElementById("cost").innerText = parseFloat(data.active_session.cost_calculated).toFixed(2) + " €";
            document.getElementById("status").innerText = data.active_session.status;
            document.getElementById("status").className = "value status-" + data.active_session.status;
        }
        
        // Heutige Statistiken aktualisieren
        document.getElementById("entries-today").innerText = data.today_stats.entries_today;
        document.getElementById("exits-today").innerText = data.today_stats.exits_today;
        document.getElementById("revenue-today").innerText = parseFloat(data.today_stats.revenue_today).toFixed(2) + "€";
        
        // Letzte Aktualisierung
        document.getElementById("last-update").innerText = new Date().toLocaleString('de-DE');
    })
    .catch(err => console.error("Fehler beim Laden des Status:", err));
}

function pay() {
    fetch("/api/payment", { method: "POST" })
    .then(res => res.json())
    .then(response => {
        if (response.status === "success") {
            alert("Zahlung bestätigt!");
        } else {
            alert("Fehler: " + response.message);
        }
        update();
    })
    .catch(err => console.error("Fehler bei der Zahlung:", err));
}

// ==================== PLATE RECOGNITION FUNCTIONS ====================

/**
 * Erkennt Kennzeichen im aktuellen Live-Feed
 */
async function recognizePlate() {
    const resultDiv = document.getElementById("recognition-result");
    resultDiv.classList.remove("visible");
    resultDiv.innerHTML = '<p style="text-align:center; color:#fff;">⏳ Erkenne...</p>';
    resultDiv.classList.add("visible");
    
    try {
        const response = await fetch("/api/recognition/detect-plate", {
            method: "POST"
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayRecognitionResult(data);
        } else {
            showRecognitionError(data.error || "Erkennungsfehler");
        }
    } catch (error) {
        showRecognitionError("Fehler beim Verbinden: " + error.message);
    }
}

/**
 * Erkennt Kennzeichen in hochgeladenem Bild
 */
async function recognizeUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const resultDiv = document.getElementById("recognition-result");
    resultDiv.classList.remove("visible");
    resultDiv.innerHTML = '<p style="text-align:center; color:#fff;">⏳ Erkenne...</p>';
    resultDiv.classList.add("visible");
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await fetch("/api/recognition/upload-image", {
            method: "POST",
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayRecognitionResult(data);
        } else {
            showRecognitionError(data.error || "Erkennungsfehler");
        }
    } catch (error) {
        showRecognitionError("Fehler beim Upload: " + error.message);
    }
}

/**
 * Zeigt Erkennungsergebnisse an
 */
function displayRecognitionResult(data) {
    const resultDiv = document.getElementById("recognition-result");
    
    // Update Stats
    document.getElementById("recognized-plate").innerText = data.detected_plate || "-";
    document.getElementById("yolo-confidence").innerText = (data.plate_confidence * 100).toFixed(1) + "%";
    document.getElementById("ocr-confidence").innerText = (data.ocr_confidence * 100).toFixed(1) + "%";
    document.getElementById("combined-confidence").innerText = (data.combined_confidence * 100).toFixed(1) + "%";
    
    // Build Result HTML
    let html = '<div class="result-images">';
    
    if (data.vehicle_snapshot) {
        html += `<img src="${data.vehicle_snapshot}" alt="Fahrzeug" class="result-image" onclick="showDetailModal('${encodeURIComponent(JSON.stringify(data))}')" style="cursor:pointer;">`;
    }
    
    if (data.plate_image) {
        html += `<img src="${data.plate_image}" alt="Kennzeichen" class="result-image" onclick="showDetailModal('${encodeURIComponent(JSON.stringify(data))}')" style="cursor:pointer;">`;
    }
    
    html += '</div>';
    html += `<button class="btn btn-recognize" onclick="showDetailModal('${encodeURIComponent(JSON.stringify(data))}')">📷 Details anzeigen</button>`;
    
    resultDiv.innerHTML = html;
    resultDiv.classList.add("visible");
}

/**
 * Zeigt Error Message an
 */
function showRecognitionError(message) {
    const resultDiv = document.getElementById("recognition-result");
    resultDiv.innerHTML = `<p style="text-align:center; color:#ffcccc;">❌ ${message}</p>`;
    resultDiv.classList.add("visible");
}

/**
 * Zeigt Detail-Modal mit allen Ergebnissen
 */
function showDetailModal(encodedData) {
    const data = JSON.parse(decodeURIComponent(encodedData));
    
    // Setze Bilder
    if (data.vehicle_snapshot) {
        document.getElementById("detail-vehicle-snapshot").src = data.vehicle_snapshot;
    }
    if (data.plate_image) {
        document.getElementById("detail-plate-image").src = data.plate_image;
    }
    if (data.annotated_frame) {
        document.getElementById("detail-annotated-frame").src = data.annotated_frame;
    }
    
    // Setze Infos
    document.getElementById("detail-plate-text").innerText = data.detected_plate || "-";
    document.getElementById("detail-yolo-conf").innerText = (data.plate_confidence * 100).toFixed(2) + "%";
    document.getElementById("detail-ocr-conf").innerText = (data.ocr_confidence * 100).toFixed(2) + "%";
    document.getElementById("detail-combined-conf").innerText = (data.combined_confidence * 100).toFixed(2) + "%";
    
    if (data.plate_region) {
        const region = data.plate_region;
        document.getElementById("detail-region").innerText = 
            `X: ${region.x1}-${region.x2}, Y: ${region.y1}-${region.y2} (${region.width}×${region.height}px)`;
    }
    
    document.getElementById("detail-timestamp").innerText = data.timestamp || "-";
    
    // Öffne Modal
    openModal("recognition-details");
}

// Initialisiere bei Page Load
window.addEventListener('DOMContentLoaded', function() {
    initializeLiveFeed();
    updateTime();
    setInterval(updateTime, 1000);
    update();
    setInterval(update, 5000);
});

// Initial updates
updateTime();
update();
initializeLiveFeed();  // Initialize Motion JPEG Stream once

// Update Zeit jede Sekunde
setInterval(updateTime, 1000);

// Update Dashboard-Daten alle 2 Sekunden
setInterval(update, 2000);

// Motion JPEG Stream läuft kontinuierlich - kein periodisches Update nötig!
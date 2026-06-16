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
        case 'dauerparker':
            endpoint = '/api/widget/dauerparker';
            listId = 'dauerparker-list';
            break;
        case 'pricing':
            // Kostenmodell ist statisch, keine Daten laden nötig
            return;
        case 'protocol':
            // Protokoll laden
            loadProtocolModal();
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

        case 'dauerparker':
            data.vehicles.forEach(v => {
                const registered = v.registered_at ? new Date(v.registered_at).toLocaleString('de-DE') : 'Unbekannt';
                html += `
                    <div class="data-item known-vehicle-item">
                        <div class="data-item-main">
                            <span class="data-item-plate">${v.license_plate}</span>
                            <span class="data-item-secondary">Registriert: ${registered}</span>
                            <span class="data-item-secondary" style="font-size: 0.8em;">${v.notes || 'Keine Notizen'}</span>
                        </div>
                        <div style="text-align: right; display: flex; gap: 10px; align-items: center;">
                            <button class="btn-delete-vehicle" onclick="deleteDauerparker('${v.license_plate}')" title="Löschen">✕</button>
                        </div>
                    </div>
                `;
            });
            container.innerHTML = html;
            document.getElementById('dauerparker-count').innerText = data.count;
            break;
            break;
    }
}

// Lade Statistiken Modal
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
        console.log("Recognition Response:", data); // Debug

        // Zeige Ergebnisse wenn Kennzeichen erkannt wurde (gültig ODER ungültig)
        if (data.detected_plate && data.detected_plate.trim() !== "") {
            displayRecognitionResult(data);
        } else {
            showRecognitionError(data.error || "Keine Kennzeichen erkannt");
        }
    } catch (error) {
        console.error("Recognition Error:", error); // Debug
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

        // Zeige Ergebnisse wenn Kennzeichen erkannt wurde (gültig ODER ungültig)
        if (data.detected_plate && data.detected_plate.trim() !== "") {
            displayRecognitionResult(data);
        } else {
            showRecognitionError(data.error || "Keine Kennzeichen erkannt");
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

    console.log("Displaying result:", data); // Debug
    console.log("Detected Plate:", data.detected_plate); // Debug
    console.log("Plate Valid:", data.plate_valid); // Debug

    // Update Stats
    const plateElement = document.getElementById("recognized-plate");
    if (plateElement) {
        // Zeige Platte an und markiere, wenn ungültig
        if (data.plate_valid === false) {
            plateElement.innerText = `${data.detected_plate} ❌`;
            plateElement.style.color = "#ff6b6b";
            console.log("Kennzeichen ist UNGÜLTIG"); // Debug
        } else if (data.plate_valid === true) {
            plateElement.innerText = `${data.detected_plate} ✓`;
            plateElement.style.color = "#51cf66";
            console.log("Kennzeichen ist GÜLTIG"); // Debug
        } else {
            plateElement.innerText = data.detected_plate || "-";
            plateElement.style.color = "#ffd93d";
            console.log("Kennzeichen Status: UNBEKANNT"); // Debug
        }
        console.log("Updated plate element to:", plateElement.innerText); // Debug
    } else {
        console.error("recognized-plate element not found!"); // Debug
    }

    document.getElementById("yolo-confidence").innerText = (data.plate_confidence * 100).toFixed(1) + "%";
    document.getElementById("ocr-confidence").innerText = (data.ocr_confidence * 100).toFixed(1) + "%";
    document.getElementById("combined-confidence").innerText = (data.combined_confidence * 100).toFixed(1) + "%";

    // Build Result HTML - mit Status-Hinweis
    let html = '<div class="result-images">';

    // Status-Hinweis
    if (data.plate_valid === false) {
        html += '<div style="background:#ff6b6b; color:white; padding:10px; border-radius:8px; margin-bottom:10px; text-align:center; font-weight:bold;">❌ UNGÜLTIGES KENNZEICHEN ERKANNT!</div>';
    } else if (data.plate_valid === true) {
        html += '<div style="background:#51cf66; color:white; padding:10px; border-radius:8px; margin-bottom:10px; text-align:center; font-weight:bold;">✓ Gültiges Kennzeichen</div>';
    }

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

// ==================== PLATE INPUT VALIDATION & ADD VEHICLE ====================

// Regex Pattern für Kennzeichen: Buchstabe, Leerzeichen, 4 Ziffern
const PLATE_PATTERN = /^[A-Z]\s\d{4}$/;

function validatePlateInput(inputElement) {
    let value = inputElement.value.toUpperCase();
    const hint = document.getElementById('plate-hint');
    const button = document.querySelector('.btn-add-plate');

    // Entferne ungültige Zeichen (nur A-Z, 0-9 und Leerzeichen erlaubt)
    value = value.replace(/[^A-Z0-9\s]/g, '');

    // Entferne mehrfache Leerzeichen
    value = value.replace(/\s{2,}/g, ' ');

    // Automatische Formatierung: Leerzeichen nach dem 1. Zeichen einfügen
    if (value.length > 1 && value[1] !== ' ' && value[0] !== ' ') {
        value = value[0] + ' ' + value.substring(1);
    }

    // Entferne Leerzeichen am Anfang
    value = value.replace(/^\s+/, '');

    // Maximal 6 Zeichen (A + Leerzeichen + 4 Ziffern)
    if (value.length > 6) {
        value = value.substring(0, 6);
    }

    inputElement.value = value;

    // Validiere das Format
    if (value === '') {
        inputElement.classList.remove('valid', 'invalid');
        hint.classList.remove('valid', 'invalid');
        hint.textContent = 'Format: Buchstabe Leerzeichen 4 Ziffern (z.B. A 1234)';
        button.disabled = true;
    } else if (PLATE_PATTERN.test(value)) {
        inputElement.classList.remove('invalid');
        inputElement.classList.add('valid');
        hint.classList.remove('invalid');
        hint.classList.add('valid');
        hint.textContent = '✓ Format gültig';
        button.disabled = false;
    } else {
        inputElement.classList.remove('valid');
        inputElement.classList.add('invalid');
        hint.classList.remove('valid');
        hint.classList.add('invalid');

        if (value.length === 1) {
            hint.textContent = 'Gib noch ein Leerzeichen und 4 Ziffern ein';
        } else if (value.length < 6 && value.includes(' ')) {
            hint.textContent = `Noch ${6 - value.length} Zeichen nötig`;
        } else {
            hint.textContent = '✗ Format ungültig (z.B. A 1234)';
        }
        button.disabled = true;
    }
}

async function addNewDauerparker() {
    const input = document.getElementById('new-plate-input');
    const license_plate = input.value.toUpperCase().trim();
    const messageDiv = document.getElementById('add-plate-message');

    // Validiere Format
    if (!PLATE_PATTERN.test(license_plate)) {
        messageDiv.textContent = '✗ Ungültiges Format! Verwende: A 1234';
        messageDiv.classList.remove('success');
        messageDiv.classList.add('error');
        return;
    }

    try {
        const response = await fetch('/api/widget/add-dauerparker', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ license_plate: license_plate })
        });

        const data = await response.json();

        if (data.success) {
            messageDiv.textContent = `✓ ${data.message}`;
            messageDiv.classList.remove('error');
            messageDiv.classList.add('success');
            input.value = '';
            input.classList.remove('valid', 'invalid');

            // Aktualisiere die Liste nach 1 Sekunde
            setTimeout(() => {
                loadModalData('dauerparker');
            }, 1000);
        } else {
            messageDiv.textContent = `✗ ${data.message}`;
            messageDiv.classList.remove('success');
            messageDiv.classList.add('error');
        }
    } catch (error) {
        messageDiv.textContent = `✗ Fehler beim Hinzufügen: ${error.message}`;
        messageDiv.classList.remove('success');
        messageDiv.classList.add('error');
        console.error('Fehler:', error);
    }
}

async function deleteDauerparker(license_plate) {
    // Bestätigung vor dem Löschen
    if (!confirm(`Bist du sicher, dass du "${license_plate}" als Dauerparker löschen möchtest?`)) {
        return;
    }

    try {
        const response = await fetch('/api/widget/delete-dauerparker', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ license_plate: license_plate })
        });

        const data = await response.json();

        if (data.success) {
            console.log(`✓ Dauerparker gelöscht: ${license_plate}`);
            // Aktualisiere die Liste nach dem Löschen
            loadModalData('dauerparker');
        } else {
            alert(`✗ Fehler beim Löschen: ${data.message}`);
            console.error('Fehler:', data.message);
        }
    } catch (error) {
        alert(`✗ Fehler beim Löschen: ${error.message}`);
        console.error('Fehler:', error);
    }
}

// ==================== PROTOCOL MODAL ====================

// Speichere aktuell gefilterte Daten für schnelle Filter-Umschaltung
let protocolData = [];
let currentProtocolFilter = 'all';

async function loadProtocolModal() {
    try {
        const response = await fetch('/api/widget/detection-protocol');
        const data = await response.json();

        protocolData = data.detections || [];
        document.getElementById('protocol-count').innerText = data.count;

        // Zeige die Daten mit aktuellem Filter
        displayProtocol(currentProtocolFilter);
    } catch (error) {
        console.error('Fehler beim Laden des Protokolls:', error);
        document.getElementById('protocol-list').innerHTML = `
            <tr>
                <td colspan="5" class="loading">Fehler beim Laden</td>
            </tr>
        `;
    }
}

function displayProtocol(filter = 'all') {
    currentProtocolFilter = filter;
    const tbody = document.getElementById('protocol-list');

    fetch('/api/entry/requests')
        .then(response => response.json())
        .then(data => {
            if (!data.data || data.data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="loading">Keine Anfragen vorhanden</td>
                    </tr>
                `;
                return;
            }

            // Filtere Daten
            const filteredData = data.data.filter(req => {
                if (filter === 'pending') return req.approval_status === 'pending';
                if (filter === 'approved') return req.approval_status === 'approved';
                if (filter === 'rejected') return req.approval_status === 'rejected';
                return true;
            });

            if (filteredData.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="loading">Keine Ergebnisse für diesen Filter</td>
                    </tr>
                `;
                return;
            }

            // Baue Tabelle
            let html = '';
            filteredData.forEach(request => {
                const dateTime = new Date(request.detected_at);
                const time = dateTime.toLocaleTimeString('de-DE', {
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });

                let statusText = '';
                let statusClass = '';
                if (request.approval_status === 'pending') {
                    statusText = 'Ausstehend';
                    statusClass = 'status-pending';
                } else if (request.approval_status === 'approved') {
                    statusText = '✅ Genehmigt';
                    statusClass = 'status-valid';
                } else if (request.approval_status === 'rejected') {
                    statusText = '❌ Abgelehnt';
                    statusClass = 'status-invalid';
                }

                const confidenceClass = request.ocr_confidence >= 85
                    ? 'confidence-high'
                    : request.ocr_confidence >= 70
                    ? 'confidence-medium'
                    : 'confidence-low';

                const dauerparkerBadge = request.is_dauerparker
                    ? '<span class="dauerparker-badge">🏠 Dauerparker</span>'
                    : '-';

                let actionBtns = '';
                if (request.approval_status === 'pending') {
                    actionBtns = `
                        <div class="action-buttons">
                            <button class="btn-approve" onclick="approveEntry(${request.id})">Annehmen</button>
                            <button class="btn-reject" onclick="rejectEntry(${request.id})">Ablehnen</button>
                        </div>
                    `;
                } else {
                    actionBtns = '-';
                }

                html += `
                    <tr>
                        <td>${time}</td>
                        <td><strong>${request.license_plate}</strong></td>
                        <td><span class="${statusClass}">${statusText}</span></td>
                        <td><span class="${confidenceClass}">${request.ocr_confidence.toFixed(1)}%</span></td>
                        <td>${dauerparkerBadge}</td>
                        <td>${actionBtns}</td>
                    </tr>
                `;
            });

            tbody.innerHTML = html;

            // Update Filter Buttons
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.getAttribute('data-filter') === filter) {
                    btn.classList.add('active');
                }
            });

            // Zähle ausstehende Anfragen
            const pendingCount = data.data.filter(r => r.approval_status === 'pending').length;
            document.getElementById('protocol-count').textContent = pendingCount;
        })
        .catch(error => {
            console.error('Fehler beim Laden der Entry Requests:', error);
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="error">Fehler beim Laden</td>
                </tr>
            `;
        });
}

function filterEntries(filter) {
    displayProtocol(filter);
}

function filterProtocol(filter) {
    displayProtocol(filter);
}
// ==================== ENTRY REQUEST MANAGEMENT ====================

async function approveEntry(requestId) {
    try {
        const response = await fetch(`/api/entry/approve/${requestId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            console.log(`✓ Entry #${requestId} genehmigt`);
            // Aktualisiere die Protokoll-Tabelle
            displayProtocol('pending');
        } else {
            alert(`✗ Fehler: ${data.message}`);
        }
    } catch (error) {
        alert(`✗ Fehler beim Genehmigen: ${error.message}`);
        console.error('Fehler:', error);
    }
}

async function rejectEntry(requestId) {
    if (!confirm('Bist du sicher, dass du diese Anfrage ablehnen möchtest?')) {
        return;
    }

    try {
        const response = await fetch(`/api/entry/reject/${requestId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.status === 'success') {
            console.log(`✓ Entry #${requestId} abgelehnt`);
            // Aktualisiere die Protokoll-Tabelle
            displayProtocol('pending');
        } else {
            alert(`✗ Fehler: ${data.message}`);
        }
    } catch (error) {
        alert(`✗ Fehler beim Ablehnen: ${error.message}`);
        console.error('Fehler:', error);
    }
}

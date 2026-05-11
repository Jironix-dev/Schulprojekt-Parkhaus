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
        
        // Ausstehende Zahlungen aktualisieren
        document.getElementById("pending-count").innerText = data.pending_payments.pending_count;
        document.getElementById("pending-amount").innerText = parseFloat(data.pending_payments.total_amount_pending).toFixed(2) + " €";
        
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

// Initial updates
updateTime();
update();

// Update Zeit jede Sekunde
setInterval(updateTime, 1000);

// Update Dashboard-Daten alle 2 Sekunden
setInterval(update, 2000);
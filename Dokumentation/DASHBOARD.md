# 📊 Parkhaus Dashboard - Dokumentation

## Übersicht

Das Parkhaus Dashboard ist eine moderne, echtzeit-basierte Web-Anwendung zur Überwachung und Verwaltung eines Parkhauses. Es bietet eine benutzerfreundliche Schnittstelle zur Anzeige von Fahrzeuginformationen, Parkplatzauslastung, Zahlungsverwaltung und Statistiken.

**Startseite:** `http://localhost:8000`

---

## 🎯 Hauptfunktionalitäten

### 1. **Echtzeit-Parkplatz-Überwachung**
- Live-Anzeige der verfügbaren und belegten Parkplätze
- Auslastungsrate in Prozent
- Automatische Aktualisierung alle 2 Sekunden

### 2. **Aktive Session-Verwaltung**
- Anzeige des aktuell parkenden Fahrzeugs
- Automatische Kostenberechnung
- Parkdauer-Tracking
- Zahlungsbestätigungs-Button

### 3. **Tagesstatistiken**
- Anzahl Ein- und Ausfahrten pro Tag
- Tageseinnahmen
- Automatische Berechnung

### 4. **Zahlungsverwaltung**
- Ausstehende Zahlungen anzeigen
- Zahlung bestätigen
- Datenbankaktualisierung bei Bestätigung

### 5. **Fahrzeugverlauf**
- Zuletzt erkannte Fahrzeuge anzeigen
- Status pro Fahrzeug
- Anzahl der Parkplatz-Sessions

### 6. **Live-Uhrzeit**
- Aktuelle Uhrzeit (HH:MM:SS) in der Kopfzeile
- Aktuelles Datum (DD.MM.YYYY)
- Aktualisierung jede Sekunde

---

## 📋 Datenfelder & Bedeutung

### 📊 Parkplatz-Auslastung

| Feld | Beschreibung | Quelle |
|------|-------------|--------|
| **Gesamtplätze** | Maximale Anzahl der Parkplätze | `parking_capacity.total_spaces` |
| **Besetzt** | Aktuell belegte Parkplätze | `parking_capacity.occupied_spaces` |
| **Frei** | Verfügbare Parkplätze | Berechnet: `total - occupied` |
| **Auslastung (%)** | Prozentuale Auslastung | Berechnet: `(occupied / total) * 100` |

**Datenbank-Tabelle:** `parking_capacity`

---

### 🚙 Aktuelle Session

| Feld | Beschreibung | Datentyp |
|------|-------------|----------|
| **Kennzeichen** | Fahrzeugleuchtkennzeichen (z.B. "B 1234") | STRING |
| **Parkdauer** | Dauer seit Einfahrt in Minuten | FLOAT |
| **Eintritt** | Zeitpunkt der Einfahrt | TIMESTAMP |
| **Confidence** | Erkennungssicherheit des YOLO-Modells (0-100%) | FLOAT |
| **Kosten** | Berechnete Parkgebühr | FLOAT (€) |
| **Status** | aktueller Status (parked/paid/etc) | STRING |

**Datenbank-Tabellen:** 
- `parking_sessions` - Parkplatz-Sessions
- `vehicles` - Fahrzeuginformationen
- `plate_detections` - YOLO-Erkennungsdaten

**Kostenkalkulation:**
```
- 0-30 Sekunden: €2.00
- 31-60 Sekunden: €3.50
- 61-90 Sekunden: €5.00
- Jede weitere 30 Sekunden: +€1.50
```

---

### 📈 Heutige Statistiken

| Feld | Beschreibung | Berechnung |
|------|-------------|-----------|
| **Einfahrten** | Fahrzeuge, die heute eingfahren sind | COUNT(entry_time) nach Datum |
| **Ausfahrten** | Fahrzeuge, die heute ausgefahren sind | COUNT(exit_time) nach Datum |
| **Einnahmen** | Gesamtsumme eingezogener Zahlungen heute | SUM(cost_paid) mit payment_confirmed=1 |

**Datenbank-Tabelle:** `parking_sessions`

---

### 💰 Ausstehende Zahlungen

| Feld | Beschreibung | Berechnung |
|------|-------------|-----------|
| **Fahrzeuge** | Anzahl mit unbezahlten Sessions | COUNT(*) WHERE payment_confirmed=0 |
| **Gesamtbetrag** | Summe aller ausstehenden Zahlungen | SUM(cost_calculated - cost_paid) |

**Datenbank-Tabelle:** `parking_sessions`

---

### 🚗 Zuletzt erkannte Fahrzeuge

| Feld | Beschreibung | Quelle |
|------|-------------|--------|
| **Kennzeichen** | Fahrzeugleuchtkennzeichen | `vehicles.license_plate` |
| **Status** | Fahrzeugstatus (pending/approved/blocked) | `vehicles.status` |
| **Sessions** | Gesamtanzahl Parkplatz-Sessionen | COUNT(parking_sessions) |

**Datenbank-Tabelle:** `vehicles`, `parking_sessions`

---

## 🛠️ API-Endpoints

### `GET /`
**Beschreibung:** Rendert das Dashboard-HTML  
**Parameter:** Keine  
**Response:** HTML-Seite mit Dashboard

---

### `GET /api/status`
**Beschreibung:** Ruft alle Dashboard-Daten als JSON ab  
**Parameter:** Keine  
**Response:**
```json
{
  "parking_capacity": {
    "total_spaces": 50,
    "occupied_spaces": 12,
    "available_spaces": 38,
    "occupancy_rate": 24.0,
    "last_updated": "2026-05-11T14:30:00"
  },
  "active_session": {
    "session_id": 1,
    "license_plate": "B 1234",
    "entry_time": "2026-05-11T10:15:00",
    "exit_time": null,
    "status": "parked",
    "cost_calculated": 5.00,
    "cost_paid": 0.0,
    "payment_confirmed": false,
    "confidence_score": 0.95,
    "parking_duration_minutes": 135.5
  },
  "pending_payments": {
    "pending_count": 3,
    "total_amount_pending": 12.50
  },
  "today_stats": {
    "entries_today": 45,
    "exits_today": 42,
    "revenue_today": 185.50
  },
  "recent_vehicles": [...],
  "timestamp": "2026-05-11T14:30:15"
}
```

---

### `POST /api/payment`
**Beschreibung:** Bestätigt die Zahlung für die aktuelle Session  
**Parameter:** Keine  
**Response:**
```json
{
  "message": "OK",
  "status": "success"
}
```

**Datenbankänderung:**
- `payment_confirmed` → 1
- `payment_confirmed_at` → aktuelles Timestamp
- `cost_paid` → cost_calculated
- `status` → "paid"

---

### `GET /logs`
**Beschreibung:** Zeigt Seite mit Transaktionslogs  
**Parameter:** Keine  
**Response:** HTML-Seite mit Logs

---

## 🗄️ Datenbankstruktur

### Verwendete Tabellen

#### `parking_capacity`
```sql
- id: INTEGER PRIMARY KEY
- total_spaces: INTEGER (Standard: 50)
- occupied_spaces: INTEGER
- last_updated: TIMESTAMP
```

#### `parking_sessions`
```sql
- id: INTEGER PRIMARY KEY
- vehicle_id: INTEGER (FK → vehicles)
- entry_time: TIMESTAMP
- exit_time: TIMESTAMP (NULL = parked)
- status: TEXT (parked/payment_pending/paid)
- cost_calculated: REAL
- cost_paid: REAL
- payment_confirmed: INTEGER (0/1)
- parking_duration_minutes: INTEGER
```

#### `vehicles`
```sql
- id: INTEGER PRIMARY KEY
- license_plate: TEXT (UNIQUE, Format: "A 1234")
- status: TEXT (pending/approved/blocked)
- registered_at: TIMESTAMP
- last_seen_at: TIMESTAMP
```

#### `plate_detections`
```sql
- id: INTEGER PRIMARY KEY
- image_id: INTEGER (FK → images)
- detected_plate: TEXT
- confidence_score: REAL (0-1)
- detected_at: TIMESTAMP
```

#### `images`
```sql
- id: INTEGER PRIMARY KEY
- image_path: TEXT
- captured_at: TIMESTAMP
- image_type: TEXT
- detected_plate: TEXT
- confidence_score: REAL
```

---

## 🔄 Datenfluss

```
┌─────────────────┐
│  YOLO-Modell    │ (Erkennung von Kennzeichen)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Database       │ (Speichern von Fahrzeug & Erkennung)
│ - vehicles      │
│ - parking_sessions
│ - plate_detections
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Dashboard      │ (Echtzeitanzeige)
│  Service        │ (Abfragen & Berechnungen)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI        │ (API-Endpoints)
│  - /            │
│  - /api/status  │
│  - /api/payment │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Browser        │ (Dashboard-Anzeige)
│  - HTML/CSS/JS  │ (Live-Updates alle 2 Sekunden)
└─────────────────┘
```

---

## 🚀 Verwendung

### Dashboard starten
```bash
cd C:\Users\kevin\Desktop\Schulprojekt-Parkhaus\Dashboard
python app.py
```

Server läuft auf: `http://localhost:8000`

### Browser öffnen
```
http://localhost:8000
```

### Automatische Updates
- **Zeit:** Jede 1 Sekunde
- **Dashboard-Daten:** Jede 2 Sekunden
- **Browser-Cache:** Wird ignoriert

---

## 🎨 Dashboard-Layout

```
┌─────────────────────────────────────────┐
│  🚗 Parkhaus Dashboard    [14:30:15]    │ ← Live-Uhr
│                           [11.05.2026]  │
├─────────────────────────────────────────┤
│  📊 Parkplatz-Auslastung                │
│  [50 Total] [12 Besetzt] [38 Frei] [24%]
├─────────────────────────────────────────┤
│  🚙 Aktuelle Session                    │
│  Kennzeichen: B 1234                    │
│  Parkdauer: 135.5 Min                   │
│  Kosten: 5.00 €        [Bezahlung bestätigen] │
├─────────────────────────────────────────┤
│  📈 Heute                               │
│  [45 Einfahrten] [42 Ausfahrten] [185.50€]
├─────────────────────────────────────────┤
│  💰 Ausstehende Zahlungen               │
│  3 Fahrzeuge - 12.50 €                  │
├─────────────────────────────────────────┤
│  🚗 Zuletzt erkannt                     │
│  [B 1234] [approved] [5 Sessions]       │
│  [C 5678] [pending]  [2 Sessions]       │
│  ...                                    │
└─────────────────────────────────────────┘
```

---

## 🔧 Technische Details

### Frontend
- **HTML5** - Struktur
- **CSS3** - Styling (Gradient, Glasmorphism)
- **JavaScript** - Interaktivität & Live-Updates
- **Fetch-API** - Kommunikation mit Backend

### Backend
- **FastAPI** - Web-Framework
- **Jinja2** - Template-Engine
- **SQLite** - Datenbank
- **Python 3.11+** - Laufzeitumgebung

### Abhängigkeiten
```
fastapi
uvicorn[standard]
jinja2
sqlite3 (built-in)
```

---

## 📱 Responsive Design

Das Dashboard ist **vollständig responsive** und passt sich an verschiedene Bildschirmgrößen an:

- **Desktop** (1920x1080+): Vollständiger Multi-Column-Layout
- **Tablet** (768-1024px): 2-Column Layout
- **Mobil** (<768px): Single-Column Layout

---

## ⚙️ Konfiguration

### Datenbankpfad
```python
DB_PATH = Path(__file__).parent.parent / 'data' / 'parkhaus.db'
```

### Server
- **Host:** 0.0.0.0 (Alle Netzwerkschnittstellen)
- **Port:** 8000
- **Auto-Reload:** Aus (Production)

### Update-Intervalle
- **Zeit-Update:** 1 Sekunde
- **Daten-Update:** 2 Sekunden

---

## 🐛 Troubleshooting

### Problem: "Internal Server Error"
**Lösung:**
1. Datenbank-Verbindung überprüfen
2. Tabellen existieren? (`init_database.py` ausführen)
3. Log-Ausgabe in Terminal prüfen

### Problem: Dashboard zeigt keine Daten
**Lösung:**
1. `http://localhost:8000/api/status` im Browser öffnen
2. JSON-Response prüfen
3. Datenbank enthält Daten? (SQL-Client öffnen)

### Problem: Zeit aktualisiert sich nicht
**Lösung:**
1. Browser-Cache leeren (Ctrl+Shift+Del)
2. Browser-Konsole prüfen (F12)
3. JavaScript-Fehler? (Console-Tab)

---

## 📞 Support & Weitere Dokumentation

Siehe auch:
- `DATABASE.md` - Datenbankstruktur
- `KENNZEICHEN_VALIDIERUNG.md` - Kennzeichen-Format
- `KOSTENBERECHNUNG.md` - Gebührenmodell
- `README.md` - Projekt-Übersicht

---

**Letzte Aktualisierung:** 11.05.2026  
**Version:** 1.0.0  
**Status:** ✅ Production Ready

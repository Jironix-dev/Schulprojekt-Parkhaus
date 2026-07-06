# Parkhaus-Datenbank Dokumentation

## Kennzeichen-Format

**WICHTIG:** Nur Kennzeichen nach folgendem Schema sind gültig:
- **1 Buchstabe (A-Z)** + **Leerzeichen** + **4 Ziffern (0-9)**
- Beispiele: `A 1234`, `Z 9999`, `M 0000`
- Ungültig: `AB 1234`, `A1234`, `A 123`, `1 1234`, alte Formate (`AB-CD 123`)

Fahrzeuge mit ungültigen Kennzeichen dürfen NICHT einfahren und werden abgelehnt.

## Datenbankstruktur

Die SQLite-Datenbank für das Parkhaus-System besteht aus **6 Tabellen**:

### 1. **vehicles** - Fahrzeugverwaltung
Speichert alle Fahrzeuge und deren Status

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PRIMARY KEY | Eindeutige ID |
| license_plate | TEXT UNIQUE | Kennzeichen (eindeutig, Format: `A 1234`) |
| is_valid_format | INTEGER | 1=gültig, 0=ungültig |
| status | TEXT | Status: pending, approved, blocked, unknown |
| registered_at | TIMESTAMP | Registrierungsdatum |
| first_seen_at | TIMESTAMP | Erste Erkennung |
| last_seen_at | TIMESTAMP | Letzte Erkennung |
| notes | TEXT | Notizen/Beschreibung |
| is_blocked | INTEGER | 1=gesperrt, 0=nicht gesperrt |

**Status-Werte:**
- `pending`: Wartet auf Freigabe durch Dashboard
- `approved`: Freigegeben - darf einfahren
- `blocked`: Gesperrt - Einfahrt verweigert
- `unknown`: Unbekanntes Fahrzeug

---

### 2. **parking_sessions** - Parkplatz-Sessionen
Speichert jeden Ein- und Ausfahrts-Vorgang

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PRIMARY KEY | Eindeutige ID |
| vehicle_id | INTEGER FK | Verweis auf vehicles.id |
| entry_time | TIMESTAMP | Einfahrtszeit |
| exit_time | TIMESTAMP | Ausfahrtszeit (NULL=noch parkend) |
| entry_image_id | INTEGER FK | Bild bei Einfahrt |
| exit_image_id | INTEGER FK | Bild bei Ausfahrt |
| status | TEXT | parked, payment_pending, payment_confirmed, exited |
| parking_duration_minutes | INTEGER | Parkdauer in Minuten |
| cost_calculated | REAL | Berechnete Parkgebühr |
| cost_paid | REAL | Gezahlter Betrag |
| payment_confirmed | INTEGER | 1=bezahlt, 0=nicht bezahlt |
| payment_confirmed_at | TIMESTAMP | Zeitpunkt der Bezahlung |
| notes | TEXT | Notizen |

---

### 3. **images** - Bildspeicherung
Speichert Metadaten zu erfassten Bildern

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PRIMARY KEY | Eindeutige ID |
| image_path | TEXT | Dateipfad zum Bild |
| captured_at | TIMESTAMP | Aufnahmezeitpunkt |
| image_type | TEXT | entry, exit, plate_crop, roi |
| detected_plate | TEXT | Erkanntes Kennzeichen |
| confidence_score | REAL | Erkennungs-Genauigkeit (0-1) |
| notes | TEXT | Notizen |

---

### 4. **plate_detections** - Kennzeichen-Erkennungen
Speichert OCR-Erkennungen für jedes Bild

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PRIMARY KEY | Eindeutige ID |
| image_id | INTEGER FK | Verweis auf images.id |
| detected_plate | TEXT | Erkanntes Kennzeichen |
| raw_ocr_text | TEXT | Roher OCR-Text |
| confidence_score | REAL | OCR-Genauigkeit (0-1) |
| is_valid | INTEGER | 1=gültig, 0=ungültig |
| detected_at | TIMESTAMP | Erkennungszeitpunkt |
| notes | TEXT | Notizen |

---

### 5. **parking_capacity** - Parkplatz-Kapazität
Speichert aktuelle Auslastung

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PRIMARY KEY | Eindeutige ID |
| total_spaces | INTEGER | Gesamtzahl Parkplätze (default: 50) |
| occupied_spaces | INTEGER | Aktuell belegte Plätze |
| last_updated | TIMESTAMP | Letzte Aktualisierung |

---

### 6. **system_logs** - Systemverwaltung
Speichert alle Systemevents

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| id | INTEGER PRIMARY KEY | Eindeutige ID |
| event_type | TEXT | INIT, ENTRY, EXIT, PAYMENT, ERROR, etc. |
| vehicle_id | INTEGER FK | Verweis auf vehicles.id (optional) |
| message | TEXT | Event-Beschreibung |
| timestamp | TIMESTAMP | Ereignis-Zeitpunkt |

---

## Relationen (Foreign Keys)

```
vehicles (1) ─── (n) parking_sessions
  ↓                      ↓
  └─── (n) system_logs  └─── (1) images (entry)
                        └─── (1) images (exit)
                              ↓
                        (1) ─── (n) plate_detections
```

---

## Verwendung der Query-Funktionen

### Fahrzeugverwaltung (VehicleQueries)
```python
from backend.database.queries import VehicleQueries

# Neues Fahrzeug hinzufügen
vehicle_id = VehicleQueries.add_vehicle('AB-CD 123', 'Audi A4')

# Fahrzeug nach Kennzeichen finden
vehicle = VehicleQueries.get_vehicle_by_plate('AB-CD 123')

# Fahrzeug freigeben
VehicleQueries.approve_vehicle(vehicle_id)

# Fahrzeug sperren
VehicleQueries.block_vehicle(vehicle_id, 'Verdachtsfahrzeug')

# Ausstehende Fahrzeuge abrufen
pending = VehicleQueries.get_pending_vehicles()
```

### Parkplatz-Verwaltung (ParkingQueries)
```python
from backend.database.queries import ParkingQueries

# Neue Session starten
session_id = ParkingQueries.create_session(vehicle_id, entry_image_id)

# Aktive Session finden
session = ParkingQueries.get_active_session(vehicle_id)

# Session beenden
ParkingQueries.end_session(session_id, exit_image_id, cost=5.50)

# Bezahlung bestätigen
ParkingQueries.confirm_payment(session_id, amount=5.50)

# Kapazität aktualisieren
ParkingQueries.update_capacity()

# Kapazität abrufen
capacity = ParkingQueries.get_capacity()
```

### Bildverwaltung (ImageQueries)
```python
from backend.database.queries import ImageQueries

# Bild speichern
image_id = ImageQueries.add_image(
    'data/plates/AB-CD123_2025-05-04.jpg', 
    'plate_crop', 
    'AB-CD 123', 
    0.95
)

# Kennzeichen-Erkennung speichern
ImageQueries.add_detection(image_id, 'AB-CD 123', 'A8-CD 123', 0.92)
```

### System-Verwaltung (SystemQueries)
```python
from backend.database.queries import SystemQueries

# Event protokollieren
SystemQueries.log_event('ENTRY', 'Fahrzeug eingefahren', vehicle_id)

# Systemlogs abrufen
logs = SystemQueries.get_logs(limit=100)

# Statistiken abrufen
stats = SystemQueries.get_statistics()
```

---

## Datenbank initialisieren

Führe folgendes aus um die Datenbank zu erstellen:

```bash
cd c:\Users\kevin\Desktop\Schulprojekt-Parkhaus
python init_database.py
```

Dies erstellt:
- SQLite-Datenbankdatei unter `data/parkhaus.db`
- Alle notwendigen Tabellen
- Beispieldaten zum Testen

---

## Datenbankpfad

```
c:\Users\kevin\Desktop\Schulprojekt-Parkhaus\data\parkhaus.db
```

Die Datenbank wird automatisch unter `data/` abgelegt (wie in der Projektstruktur vorgegeben).

---

## Typischer Workflow

1. **Fahrzeug erkennt Einfahrt:**
   - Kamera erfasst ROI
   - YOLO11 erkennt Kennzeichen → `images` + `plate_detections`
   - Fahrzeug in `vehicles` suchen

2. **Bekanntes Fahrzeug (status='approved'):**
   - Neue `parking_sessions` erstellen
   - Status: 'parked'
   - Schranke öffnen, grüne Ampel

3. **Unbekanntes Fahrzeug (status='pending'):**
   - Im Dashboard anzeigen
   - Benutzer genehmigt oder sperrt
   - Entsprechender Status wird gesetzt

4. **Fahrzeug möchte ausfahren:**
   - Zweite Foto erfasst
   - Kennzeichen erkannt
   - `parking_sessions.exit_time` setzen
   - Parkdauer + Kosten berechnen
   - Im Dashboard: Bezahlung abwarten

5. **Bezahlung bestätigt:**
   - `confirm_payment()` aufrufen
   - Status: 'payment_confirmed'
   - Schranke öffnen

---

## Sicherung und Wartung

Die Datenbank sollte regelmäßig gesichert werden:

```bash
# Sicherung erstellen
copy data\parkhaus.db data\parkhaus_backup.db
```

Für Produktion empfohlen:
- Regelmäßige Backups
- Alte Logs archivieren (>30 Tage)
- Indizes auf häufig abgefragten Feldern

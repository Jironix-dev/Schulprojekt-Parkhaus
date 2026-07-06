# Schulprojekt Parkhaus - Projektdokumentation

Diese README fasst das komplette Parkhaus-Projekt zusammen. Sie beschreibt den Zweck, die Ordnerstruktur, die wichtigsten Abläufe, die Datenbank, das Dashboard, die Kennzeichenerkennung, die MQTT-Steuerung und typische Wartungsaufgaben.

Die alten Einzeldokumente liegen zur Nachverfolgung im Ordner `Dokumentation/Archiv/`. Die zentrale und aktuelle Dokumentation ist diese Datei.

## 1. Projektziel

Das Projekt ist ein Parkhaus-System mit automatischer Kennzeichenerkennung. Ein Raspberry Pi betreibt das Dashboard, die Kamera, die Datenbank und die Logik. Ein ESP32 steuert Ampeln und Schranken über MQTT.

Das System soll:

- Kennzeichen per Kamera erkennen.
- Fahrzeuge anhand des Kennzeichens verwalten.
- Einfahrten und Ausfahrten protokollieren.
- Dauerparker automatisch erkennen.
- Normale Kennzeichen nach Genehmigung als bekannt speichern.
- Die aktuelle Parkhausbelegung anzeigen.
- Bei vollem Parkhaus jede Einfahrt sperren.
- Parkgebühren berechnen und Zahlungen bestätigen.
- Ampel und Schranke per MQTT steuern.

## 2. Technischer Überblick

| Bereich | Aufgabe | Wichtige Dateien |
|---|---|---|
| Dashboard | Weboberfläche und API | `Dashboard/app.py`, `Dashboard/routes.py`, `Dashboard/templates/index.html`, `Dashboard/static/script.js` |
| Backend | Geschäftslogik für Einfahrt, Ausfahrt, Zahlungen und Status | `backend/services/dashboard_service.py`, `backend/services/exit_service.py`, `backend/services/payment.py` |
| Datenbank | SQLite-Verbindung, Tabellen und Abfragen | `backend/database/db.py`, `backend/database/models.py`, `backend/database/queries.py` |
| Kennzeichenerkennung | YOLO, OCR und Bildverarbeitung | `AI/plate_recognizer.py`, `AI/ocr_handler.py`, `AI/image_processor.py`, `backend/services/plate_recognition_service.py` |
| MQTT | Kommunikation mit ESP32 | `Dashboard/mqtt_parking_control.py`, `MQTT/MQTT_Programm_ESP32.py` |
| Daten | SQLite-Datenbank | `data/parkhaus.db` |

## 3. Projektstruktur

```text
Schulprojekt-Parkhaus/
├── AI/
│   ├── YOLO-Modell/
│   │   └── best.pt
│   ├── image_processor.py
│   ├── ocr_handler.py
│   ├── plate_detection_models.py
│   └── plate_recognizer.py
├── Dashboard/
│   ├── app.py
│   ├── livefeed.py
│   ├── mqtt_parking_control.py
│   ├── routes.py
│   ├── static/
│   │   ├── script.js
│   │   └── style.css
│   └── templates/
│       ├── index.html
│       └── logs.html
├── MQTT/
│   └── MQTT_Programm_ESP32.py
├── backend/
│   ├── database/
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── queries.py
│   │   └── validators.py
│   └── services/
│       ├── dashboard_service.py
│       ├── exit_service.py
│       ├── ocr_correction.py
│       ├── payment.py
│       └── plate_recognition_service.py
├── data/
│   └── parkhaus.db
├── Dokumentation/
│   ├── README.md
│   └── Archiv/
├── camera_capture.py
├── init_database.py
├── pyproject.toml
├── requirements.txt
└── uv.lock
```

## 4. Installation und Start

### Voraussetzungen

- Python 3.11 oder neuer
- Raspberry Pi 5 für den Hardwarebetrieb
- Kamera am Raspberry Pi
- Mosquitto MQTT-Broker, wenn der ESP32 angebunden wird
- Tesseract OCR
- Trainiertes YOLO-Modell unter `AI/YOLO-Modell/best.pt`

### Python-Umgebung aktivieren

Im Projekt existiert eine virtuelle Umgebung `.venv`.

```bash
source .venv/bin/activate
```

Falls die Umgebung neu aufgebaut werden muss:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Alternativ kann das Projekt mit `uv` gestartet werden, wenn `uv` installiert ist:

```bash
uv sync
uv run python Dashboard/app.py
```

### Datenbank initialisieren

```bash
python3 init_database.py
```

Die SQLite-Datenbank liegt unter:

```text
data/parkhaus.db
```

### Dashboard starten

```bash
python3 Dashboard/app.py
```

Das Dashboard ist danach erreichbar unter:

```text
http://localhost:8000
```

Auf einem Raspberry Pi im Netzwerk kann statt `localhost` die IP-Adresse des Pi verwendet werden.

## 5. Dashboard

Das Dashboard ist die zentrale Bedienoberfläche. Es zeigt:

- Livebild der Kamera
- aktuelle Kennzeichenerkennung
- Parkplatz-Auslastung
- offene Zahlungen
- Dauerparker
- Protokoll der Einfahrten und Ausfahrten
- MQTT-Status und letzte MQTT-Meldungen

Die Oberfläche aktualisiert wichtige Daten automatisch über die API.

### Parkplatz-Auslastung

Die Kapazität wird aus der Tabelle `parking_capacity` gelesen.

Wichtige Felder:

| Anzeige | Bedeutung |
|---|---|
| Gesamtplätze | maximale Anzahl Parkplätze |
| Besetzt | aktive Park-Sessions ohne Ausfahrtszeit |
| Frei | `Gesamtplätze - Besetzt`, mindestens 0 |
| Auslastung | Prozentwert der Belegung |

Wenn keine freien Plätze mehr vorhanden sind, zeigt das Dashboard:

```text
Parkhaus voll - Einfahrt gesperrt
```

Dann darf kein Fahrzeug einfahren, auch kein Dauerparker.

## 6. Parkhauskapazität ändern

Die aktuelle Kapazität steht in der Datenbank, nicht nur im Code.

Beispiel: Kapazität auf 10 setzen:

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); db.execute(\"UPDATE parking_capacity SET total_spaces = 10, last_updated = datetime('now', 'localtime') WHERE id = 1\"); db.commit(); db.close()"
```

Prüfen:

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); print(db.execute('SELECT total_spaces, occupied_spaces FROM parking_capacity WHERE id = 1').fetchone()); db.close()"
```

Hinweis: Die Kapazität sollte nicht kleiner als die aktuell belegten Plätze gesetzt werden. Das System verhindert zwar weitere Einfahrten, aber eine realistische Anzeige ist sauberer.

### Fahrzeugdaten leeren

Wenn alle bekannten Kennzeichen, Dauerparker, aktiven Parkvorgänge und Ein-/Ausfahrtsanfragen gelöscht werden sollen, kann die Datenbank zurückgesetzt werden.

Vorher sollte das Dashboard beendet werden, damit währenddessen keine neuen Einträge geschrieben werden.

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); db.executescript(\"DELETE FROM exit_requests; DELETE FROM entry_requests; DELETE FROM parking_sessions; DELETE FROM vehicles; UPDATE parking_capacity SET occupied_spaces = 0, last_updated = datetime('now', 'localtime') WHERE id = 1;\"); db.commit(); db.close()"
```

Prüfen:

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); print('vehicles:', db.execute('SELECT COUNT(*) FROM vehicles').fetchone()[0]); print('sessions:', db.execute('SELECT COUNT(*) FROM parking_sessions').fetchone()[0]); print('entry_requests:', db.execute('SELECT COUNT(*) FROM entry_requests').fetchone()[0]); print('exit_requests:', db.execute('SELECT COUNT(*) FROM exit_requests').fetchone()[0]); print('capacity:', db.execute('SELECT total_spaces, occupied_spaces FROM parking_capacity WHERE id = 1').fetchone()); db.close()"
```

Wenn zusätzlich auch die gespeicherten Erkennungsbilder und OCR-Protokolle gelöscht werden sollen:

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); db.executescript(\"DELETE FROM plate_detections; DELETE FROM images;\"); db.commit(); db.close()"
```

## 7. Einfahrtslogik

Die Einfahrt wird in `Dashboard/routes.py` und `backend/services/dashboard_service.py` verarbeitet.

### Ablauf bei erkanntem Kennzeichen

1. Kamera erkennt Kennzeichen.
2. Kennzeichen wird validiert und normalisiert.
3. System prüft, ob das Fahrzeug bereits im Parkhaus ist.
4. System prüft, ob das Parkhaus voll ist.
5. Danach entscheidet das System:
   - Dauerparker: automatische Freigabe, wenn Platz frei ist.
   - Bekanntes genehmigtes Kennzeichen: automatische Freigabe, wenn Platz frei ist.
   - Neues Kennzeichen: wartet im Dashboard auf manuelle Genehmigung.
   - Volles Parkhaus: Anfrage wird abgelehnt.

### Regel bei vollem Parkhaus

Wenn `occupied_spaces >= total_spaces`, gilt:

- keine automatische Einfahrt
- keine manuelle Genehmigung
- keine Session-Erstellung
- keine MQTT-Sequenz für Schranke/Ampel
- Protokolleintrag mit `Parkhaus voll - Einfahrt gesperrt`

Die Schutzprüfung liegt zusätzlich direkt vor dem Erstellen einer Parksession. Dadurch bleibt das System auch dann sicher, wenn eine andere Stelle im Code eine Session starten möchte.

## 8. Ausfahrtslogik

Die Ausfahrt wird hauptsächlich in `backend/services/exit_service.py` verarbeitet.

Grundidee:

1. Kennzeichen wird erkannt.
2. System sucht eine aktive Parksession.
3. Bei Dauerparkern kann die Ausfahrt ohne Zahlung erlaubt werden.
4. Bei normalen Fahrzeugen wird geprüft, ob die Zahlung bestätigt wurde.
5. Wenn die Ausfahrt erlaubt ist, wird die Session beendet.
6. Die belegten Plätze werden aktualisiert.
7. MQTT startet die Ausfahrtssequenz für Ampel und Schranke.

### Ausfahrtsfenster nach Zahlung

Nach einer bestätigten Zahlung hat ein normales Fahrzeug 3 Minuten Zeit, um auszufahren.

Wenn diese 3 Minuten ablaufen, ohne dass die Ausfahrt abgeschlossen wurde:

- wird die Zahlung automatisch wieder zurückgesetzt,
- das Fahrzeug erscheint wieder bei den offenen Zahlungen,
- der neue Gebührenzeitraum beginnt ab dem Ablauf des Ausfahrtsfensters,
- die erneute Berechnung startet dadurch wieder frisch ab diesem Zeitpunkt.

Die automatische Prüfung läuft beim Abrufen der Dashboarddaten. Dadurch muss das Kennzeichen nicht erst erneut an der Schranke erkannt werden, damit das Fahrzeug wieder zahlungspflichtig wird.

## 9. Dauerparker

Dauerparker sind Fahrzeuge mit dem Status:

```text
dauerparker
```

Sie können im Dashboard hinzugefügt und gelöscht werden.

Wichtig:

- Dauerparker fahren automatisch ein, wenn das Parkhaus nicht voll ist.
- Dauerparker müssen keine Parkgebühr bezahlen.
- Bei vollem Parkhaus werden auch Dauerparker abgelehnt.

## 10. Kennzeichenformat

Das Projekt akzeptiert nur ein vereinfachtes Kennzeichenformat:

```text
[A-Z] [0-9]{4}
```

Beispiele:

| Kennzeichen | Status |
|---|---|
| `A 1234` | gültig |
| `Z 9999` | gültig |
| `M 0000` | gültig |
| `AB 1234` | ungültig |
| `A1234` | ungültig |
| `A 123` | ungültig |

Die Validierung liegt in:

```text
backend/database/validators.py
```

Ungültige Kennzeichen werden nicht zur Einfahrt freigegeben.

Bei der automatischen Live-Erkennung muss ein ungültig gelesenes Kennzeichen nicht erst aus dem Bild genommen werden. Solange es sichtbar bleibt, startet das System nach 5 Sekunden automatisch einen neuen Erkennungsversuch.

## 11. Kostenberechnung

Die Gebühren werden in `backend/services/payment.py` berechnet.

Tarif:

| Parkdauer | Gebühr |
|---|---|
| 0 bis 30 Sekunden | 2,00 EUR |
| 31 bis 60 Sekunden | 3,50 EUR |
| 61 bis 90 Sekunden | 5,00 EUR |
| jede weiteren 30 Sekunden | +1,50 EUR |

Die Berechnung arbeitet in Sekunden. Das ist praktisch für Tests, weil man nicht minutenlang warten muss.

Für die normale Parkdauer wird weiterhin die Einfahrtszeit verwendet. Für die Gebührenberechnung gibt es zusätzlich den Gebührenstart `billing_started_at`.

Normalerweise entspricht `billing_started_at` der Einfahrtszeit. Wenn ein bezahltes Fahrzeug das 3-Minuten-Ausfahrtsfenster verpasst, wird `billing_started_at` auf den Ablaufzeitpunkt dieses Fensters gesetzt. Die nächste Zahlung berechnet dann nur die Zeit seit diesem neuen Gebührenstart.

Beispiele:

| Dauer | Preis |
|---|---|
| 15 Sekunden | 2,00 EUR |
| 31 Sekunden | 3,50 EUR |
| 90 Sekunden | 5,00 EUR |
| 91 Sekunden | 6,50 EUR |

## 12. Datenbank

Die SQLite-Datenbank liegt unter:

```text
data/parkhaus.db
```

Die Tabellen werden in `backend/database/models.py` definiert.

Bestehende Datenbanken werden beim Start über `backend/database/db.py` einfach migriert. Fehlt zum Beispiel `billing_started_at` in `parking_sessions`, wird die Spalte automatisch ergänzt.

### Wichtige Tabellen

| Tabelle | Aufgabe |
|---|---|
| `vehicles` | bekannte Fahrzeuge, Dauerparker, Status |
| `parking_sessions` | aktive und abgeschlossene Parkvorgänge |
| `images` | Bild-Metadaten |
| `plate_detections` | OCR-Erkennungen |
| `parking_capacity` | Gesamtplätze und belegte Plätze |
| `system_logs` | technische Systemereignisse |
| `entry_requests` | Einfahrtsanfragen |
| `exit_requests` | Ausfahrtsversuche |

### `vehicles`

| Feld | Bedeutung |
|---|---|
| `license_plate` | Kennzeichen |
| `status` | `pending`, `approved`, `dauerparker`, `blocked` |
| `first_seen_at` | erstes Erkennen |
| `last_seen_at` | letztes Erkennen |
| `notes` | Notizen |

### `parking_sessions`

| Feld | Bedeutung |
|---|---|
| `vehicle_id` | Fahrzeug |
| `entry_time` | Einfahrtszeit |
| `billing_started_at` | Startzeitpunkt für die aktuelle Gebührenberechnung |
| `exit_time` | Ausfahrtszeit, `NULL` bedeutet aktiv |
| `status` | Sessionstatus |
| `cost_calculated` | berechnete Kosten |
| `cost_paid` | bezahlter Betrag |
| `payment_confirmed` | Zahlung bestätigt |

### `parking_capacity`

| Feld | Bedeutung |
|---|---|
| `total_spaces` | Gesamtzahl der Parkplätze |
| `occupied_spaces` | aktuell belegte Plätze |
| `last_updated` | letzte Aktualisierung |

`occupied_spaces` wird aus aktiven Sessions synchronisiert.

## 13. Kennzeichenerkennung

Die Kennzeichenerkennung kombiniert:

- YOLO für die Position des Kennzeichens im Bild
- OCR für den Text auf dem Kennzeichen
- Nachbearbeitung und Validierung im Backend

Wichtige Dateien:

```text
AI/plate_recognizer.py
AI/ocr_handler.py
AI/image_processor.py
backend/services/plate_recognition_service.py
Dashboard/livefeed.py
```

Das Dashboard kann:

- das aktuelle Livebild auswerten
- Bilder hochladen und auswerten
- Fahrzeugbild, Kennzeichen-Ausschnitt und Bounding Box anzeigen
- Konfidenzwerte anzeigen
- ungültige Live-Erkennungen nach 5 Sekunden automatisch erneut prüfen, solange das Kennzeichen sichtbar bleibt

## 14. MQTT und ESP32

MQTT verbindet Dashboard und ESP32.

Der Raspberry Pi sendet Befehle an den Broker. Der ESP32 empfängt sie und steuert Ampeln und Schranken.

### Dashboard-MQTT

Datei:

```text
Dashboard/mqtt_parking_control.py
```

Wichtige Einstellungen:

| Einstellung | Wert |
|---|---|
| Broker | `localhost` |
| Port | `1883` |
| Client-ID | `parkhaus_dashboard` |

### Topics

| Topic | Aufgabe |
|---|---|
| `ampel/einfahrt` | Ampel Einfahrt steuern |
| `ampel/ausfahrt` | Ampel Ausfahrt steuern |
| `schranke/einfahrt` | Schranke Einfahrt steuern |
| `schranke/ausfahrt` | Schranke Ausfahrt steuern |
| `esp32/heartbeat/ping` | Dashboard pingt ESP32 |
| `esp32/heartbeat/pong` | ESP32 antwortet |

### ESP32

Datei:

```text
MQTT/MQTT_Programm_ESP32.py
```

Auf dem ESP32 muss der MQTT-Broker als IP-Adresse eingetragen werden. Nicht `localhost` verwenden, weil `localhost` auf dem ESP32 der ESP32 selbst wäre.

## 15. API-Übersicht

Die wichtigsten API-Endpunkte aus `Dashboard/routes.py`:

| Methode | Pfad | Aufgabe |
|---|---|---|
| `GET` | `/` | Dashboard anzeigen |
| `GET` | `/logs` | Logseite anzeigen |
| `GET` | `/api/status` | Dashboard-Status als JSON |
| `GET` | `/api/health` | Systemstatus prüfen |
| `POST` | `/api/payment` | Zahlung für aktuelle Session bestätigen |
| `POST` | `/api/payment/{session_id}` | Zahlung für bestimmte Session bestätigen |
| `GET` | `/api/widget/costs` | offene Kosten |
| `GET` | `/api/widget/parking-occupancy` | aktuelle Belegung |
| `GET` | `/api/widget/durations` | Parkdauerübersicht |
| `GET` | `/api/widget/plate-recognition` | letzte Erkennung |
| `GET` | `/api/widget/dauerparker` | Dauerparkerliste |
| `POST` | `/api/widget/add-dauerparker` | Dauerparker hinzufügen |
| `POST` | `/api/widget/delete-dauerparker` | Dauerparker löschen |
| `GET` | `/api/widget/detection-protocol` | Einfahrtsprotokoll |
| `GET` | `/api/widget/protocol-preview` | letzte Aktion |
| `GET` | `/api/widget/mqtt-monitor` | MQTT-Monitor |
| `GET` | `/api/stream` | Kamerastream |
| `GET` | `/api/camera/status` | Kamerastatus |
| `POST` | `/api/recognition/detect-plate` | Kennzeichen im Livebild erkennen |
| `POST` | `/api/recognition/upload-image` | Bild hochladen und erkennen |
| `GET` | `/api/recognition/statistics` | Erkennungsstatistiken |
| `GET` | `/api/recognition/status` | Status der Erkennung |
| `GET` | `/api/recognition/auto-status` | automatische Erkennung |
| `POST` | `/api/recognition/reset-statistics` | Erkennungsstatistik zurücksetzen |
| `POST` | `/api/entry/save-request` | Einfahrtsanfrage speichern |
| `GET` | `/api/entry/requests` | Einfahrtsanfragen laden |
| `GET` | `/api/exit/requests` | Ausfahrtsversuche laden |
| `POST` | `/api/entry/approve/{request_id}` | Einfahrt genehmigen |
| `POST` | `/api/entry/reject/{request_id}` | Einfahrt ablehnen |

## 16. Typische Bedienabläufe

### Neues normales Kennzeichen

1. Fahrzeug fährt vor die Einfahrt.
2. Kamera erkennt Kennzeichen.
3. Wenn das Kennzeichen unbekannt ist, erscheint es im Protokoll als ausstehend.
4. Benutzer klickt im Dashboard auf `Annehmen`.
5. Wenn ein Parkplatz frei ist, wird die Einfahrt genehmigt.
6. Fahrzeug wird als bekannt gespeichert.
7. Schranke und Ampel starten per MQTT.

### Bekanntes Kennzeichen

1. Fahrzeug wird erkannt.
2. Kennzeichen ist bereits `approved`.
3. Wenn ein Parkplatz frei ist, startet die Einfahrt automatisch.
4. Wenn das Parkhaus voll ist, wird die Einfahrt abgelehnt.

### Dauerparker

1. Fahrzeug wird erkannt.
2. Kennzeichen hat Status `dauerparker`.
3. Wenn ein Parkplatz frei ist, startet die Einfahrt automatisch.
4. Wenn das Parkhaus voll ist, wird die Einfahrt abgelehnt.

### Ausfahrt mit Zahlung

1. Fahrzeug steht an der Ausfahrt.
2. Kennzeichen wird erkannt.
3. System berechnet die Kosten.
4. Benutzer bestätigt die Zahlung im Dashboard.
5. Danach wird die Ausfahrt für 3 Minuten freigegeben.
6. Fährt das Fahrzeug in dieser Zeit aus, wird die Session beendet.
7. Läuft die Zeit ab, wird die Zahlung automatisch zurückgesetzt und der neue Gebührenzeitraum startet ab dem Ablaufzeitpunkt.

## 17. Wartung und nützliche Befehle

### Syntax prüfen

```bash
python3 -m py_compile Dashboard/app.py Dashboard/routes.py Dashboard/livefeed.py backend/services/dashboard_service.py backend/services/exit_service.py backend/services/payment.py
```

### Datenbankwert anzeigen

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); print(db.execute('SELECT * FROM parking_capacity').fetchall()); db.close()"
```

### Aktive Sessions anzeigen

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); print(db.execute('SELECT id, vehicle_id, entry_time, billing_started_at, exit_time, status, payment_confirmed FROM parking_sessions WHERE exit_time IS NULL').fetchall()); db.close()"
```

### Dashboard starten

```bash
source .venv/bin/activate
python3 Dashboard/app.py
```

## 18. Häufige Probleme

### `sqlite3: command not found`

Das Terminalprogramm `sqlite3` ist nicht installiert. Die Datenbank kann trotzdem mit Python bearbeitet werden:

```bash
python3 -c "import sqlite3; db=sqlite3.connect('data/parkhaus.db'); print(db.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()); db.close()"
```

### Dashboard startet nicht wegen `SyntaxError`

Syntax prüfen:

```bash
python3 -m py_compile Dashboard/app.py Dashboard/routes.py backend/services/dashboard_service.py
```

Die Fehlermeldung nennt Datei und Zeile.

### ESP32 reagiert nicht

Prüfen:

- Läuft Mosquitto auf dem Raspberry Pi?
- Stimmen Broker-IP und Port im ESP32-Skript?
- Stimmen die MQTT-Topics in Dashboard und ESP32 überein?
- Ist der ESP32 im selben Netzwerk?
- Antwortet der Heartbeat im Dashboard?

### Kennzeichen wird nicht erkannt

Prüfen:

- Ist das YOLO-Modell vorhanden?
- Ist Tesseract installiert?
- Ist die Kamera erreichbar?
- Ist das Kennzeichen im richtigen Format?
- Sind Licht, Abstand und Fokus ausreichend?

## 19. Wichtigste Dateien zum Weiterentwickeln

| Änderung | Datei |
|---|---|
| Dashboard-Layout | `Dashboard/templates/index.html` |
| Dashboard-Interaktion | `Dashboard/static/script.js` |
| Dashboard-Design | `Dashboard/static/style.css` |
| API-Routen | `Dashboard/routes.py` |
| Einfahrt, Dauerparker, Kapazität | `backend/services/dashboard_service.py` |
| Ausfahrt | `backend/services/exit_service.py` |
| Kostenmodell | `backend/services/payment.py` |
| Datenbanktabellen | `backend/database/models.py` |
| Datenbankverbindung | `backend/database/db.py` |
| Kennzeichenformat | `backend/database/validators.py` |
| MQTT Dashboard | `Dashboard/mqtt_parking_control.py` |
| MQTT ESP32 | `MQTT/MQTT_Programm_ESP32.py` |

## 20. Aktueller Projektstand

Das Projekt besitzt aktuell:

- FastAPI-Dashboard
- SQLite-Datenbank
- Kamera-Livefeed
- Kennzeichenerkennung mit YOLO und OCR
- Einfahrtsfreigabe über Dashboard
- automatische Einfahrt für bekannte Kennzeichen und Dauerparker
- Sperre bei vollem Parkhaus
- Ausfahrtslogik mit Zahlung
- Dauerparkerverwaltung
- MQTT-Steuerung für ESP32, Ampeln und Schranken
- Protokolle für Einfahrt und Ausfahrt

Damit ist das System als Schulprojekt gut erklärbar, vorführbar und erweiterbar.

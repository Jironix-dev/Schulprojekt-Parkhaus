# Kostenberechnung - Parkhaus-System

## Tarif-Modell

Das Parkhaus verwendet ein gestaffeltes Gebührensystem basierend auf Parkdauer **in Sekunden**:

| Parkdauer | Gebühr |
|-----------|---------|
| 0 - 30 Sekunden | 2,00 EUR |
| 31 - 60 Sekunden | 3,50 EUR |
| 61 - 90 Sekunden | 5,00 EUR |
| Jede weiteren 30 Sekunden | + 1,50 EUR |

## Kostenbeispiele

- **15 Sekunden** → 2,00 EUR
- **30 Sekunden** → 2,00 EUR
- **31 Sekunden** → 3,50 EUR
- **60 Sekunden (1 Minute)** → 3,50 EUR
- **90 Sekunden (1,5 Minuten)** → 5,00 EUR
- **91 Sekunden** → 6,50 EUR (5,00 + 1×1,50)
- **300 Sekunden (5 Minuten)** → 15,50 EUR (5,00 + 7×1,50)
- **3600 Sekunden (1 Stunde)** → 180,50 EUR (5,00 + 117×1,50)

## Implementierung

### PaymentCalculator

Die Hauptklasse für Kostenberechnungen. Sie berechnet Kosten **immer nach Sekunden**:

```python
from backend.services.payment import PaymentCalculator

# Berechne Kosten für 150 Sekunden
cost = PaymentCalculator.calculate_from_seconds(150)
# Ergebnis: 8.00 EUR
```

**Verfügbare Methoden:**

- `calculate_from_seconds(parking_seconds: int) -> float`
  - Berechnet Kosten basierend auf Sekunden
  - Dies ist die einzige Berechnungsmethode und wird von der Datenbank-Integration verwendet

### DatabasePaymentCalculator

Diese Klasse **liest Ein- und Ausfahrtszeiten direkt aus der Datenbank** und berechnet Kosten automatisch:

#### 1. Kosten berechnen (ohne speichern)
```python
from backend.services import DatabasePaymentCalculator

cost = DatabasePaymentCalculator.calculate_cost_for_session(session_id=3)
# Ergebnis: 45.50 EUR (wenn Parkdauer bekannt)
# Ergebnis: None (wenn Session noch aktiv oder nicht existiert)
```

#### 2. Kosten berechnen UND in Datenbank speichern
```python
success, cost, message = DatabasePaymentCalculator.calculate_and_update_session(session_id=3)

if success:
    print(message)  # "Kosten berechnet und gespeichert: 45.50 EUR"
    print(f"Kosten: {cost:.2f} EUR")
else:
    print(message)  # Fehler-Nachricht
```

#### 3. Detaillierte Session-Informationen abrufen
```python
info = DatabasePaymentCalculator.get_session_cost_info(session_id=3)

# Ergebnis:
# {
#     'session_id': 3,
#     'entry_time': datetime(...),
#     'exit_time': datetime(...),
#     'is_active': False,
#     'calculated_cost': 45.50,
#     'stored_cost': 45.50,
#     'duration_seconds': 900,
#     'duration_minutes': 15.0,
#     'duration_hours': 0.25
# }
```

## Workflow im Parkhaus

### 1. Fahrzeug fährt ein → Session erstellen
```python
from backend.database.queries import ParkingQueries

session_id = ParkingQueries.create_session(vehicle_id=1)
# Entry-Zeit wird automatisch gesetzt
```

### 2. Fahrzeug parkt → Zeit vergeht
```python
# Fahrzeug ist aktiv in Parkhaus_
# Kosten werden noch nicht berechnet
```

### 3. Fahrzeug möchte ausfahren → Session beenden
```python
# Option A: Automatische Kostenberechnung (EMPFOHLEN)
# Kosten werden aus Datenbank berechnet und automatisch gespeichert
ParkingQueries.end_session(session_id=session_id)
# Der Preis wird basierend auf den Ein-/Ausfahrtszeiten berechnet!

# Option B: Kosten manuell berechnen und übergeben
from backend.services import DatabasePaymentCalculator
cost = DatabasePaymentCalculator.calculate_cost_for_session(session_id)
ParkingQueries.end_session(session_id=session_id, cost=cost)
```

### 4. Bezahlung abwickeln
```python
# Abrufen wie viel zu zahlen ist
info = DatabasePaymentCalculator.get_session_cost_info(session_id)
amount_to_pay = info['calculated_cost']

# Bezahlung bestätigen
success = ParkingQueries.confirm_payment(
    session_id=session_id,
    amount=amount_to_pay
)

if success:
    print("Zahlung erfolgreich - Schranke öffnet")
else:
    print("Zahlung abgelehnt")
```

## Vollständiger Code-Beispiel

```python
from backend.database import db, ParkingQueries, VehicleQueries
from backend.services import DatabasePaymentCalculator

# Datenbank verbinden
db.connect()

# 1. Fahrzeug registrieren
vehicle_id = VehicleQueries.add_vehicle('A 1234', 'Mein Auto')
VehicleQueries.approve_vehicle(vehicle_id)

# 2. Session erstellen (Einfahrt)
session_id = ParkingQueries.create_session(vehicle_id=vehicle_id)
print(f"Session {session_id} erstellt - Auto fährt ein")

# 3. Auto parkt (Zeit vergeht)
# ... 15 Minuten später ...

# 4. Auto möchte rausfahren
# Kosten werden automatisch berechnet und gespeichert
ParkingQueries.end_session(session_id=session_id)
print("Session beendet - Kosten berechnet")

# 5. Kosten-Informationen abrufen
info = DatabasePaymentCalculator.get_session_cost_info(session_id)
print(f"Parkdauer: {info['duration_minutes']:.1f} Minuten")
print(f"Zu zahlender Betrag: {info['calculated_cost']:.2f} EUR")

# 6. Zahlung
success = ParkingQueries.confirm_payment(
    session_id=session_id,
    amount=info['calculated_cost']
)

if success:
    print("✓ Zahlung erfolgreich - Ausfahrt freigegeben")

db.close()
```

**Ausgabe:**
```
Session 1 erstellt - Auto fährt ein
Session beendet - Kosten berechnet
Parkdauer: 15.0 Minuten
Zu zahlender Betrag: 45.50 EUR
✓ Zahlung erfolgreich - Ausfahrt freigegeben
```

## Fehlerbehandlung

### Aktive Session (keine Ausfahrtszeit)
```python
# Wenn Auto noch parkt, kann nicht berechnet werden
cost = DatabasePaymentCalculator.calculate_cost_for_session(session_id)
# Ergebnis: None

info = DatabasePaymentCalculator.get_session_cost_info(session_id)
print(info['is_active'])  # True
```

### Session nicht existiert
```python
cost = DatabasePaymentCalculator.calculate_cost_for_session(999)
# Ergebnis: None

info = DatabasePaymentCalculator.get_session_cost_info(999)
# Ergebnis: {'error': 'Session 999 nicht gefunden'}
```

## Architektur

Die Kostenberechnung ist nach folgenden Prinzipien gebaut:

**Schlank & Effizient:**
- Nur eine Berechnungsmethode: `calculate_from_seconds()`
- Direkte Berechnung ohne Umwandlungen
- `math.ceil` für Rundung bei Zusatzgebühren

**Datenbankintegriert:**
- `DatabasePaymentCalculator` liest direkt aus `parking_sessions`-Tabelle
- Ein- und Ausfahrtszeiten sind die Quelle der Wahrheit
- Kosten werden **nur nach Sekunden** berechnet

**Automatisiert:**
- `ParkingQueries.end_session()` berechnet Kosten automatisch
- Keine manuellen Berechnungen im Code nötig
- Fehlerbehandlung eingebaut

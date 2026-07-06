# Kennzeichen-Validierung

## Gültiges Format

Nur Kennzeichen mit folgendem Format werden akzeptiert:

```
[A-Z] [0-9]{4}
```

**Bedeutung:**
- `[A-Z]` = Genau 1 Großbuchstabe (A bis Z)
- ` ` = Ein Leerzeichen
- `[0-9]{4}` = Genau 4 Ziffern (0 bis 9)

## Gültige Beispiele

| Format | Erkennung |
|--------|-----------|
| `A 1234` | ✓ Gültig |
| `Z 9999` | ✓ Gültig |
| `M 0000` | ✓ Gültig |
| `a 1234` | ✓ Wird zu `A 1234` normalisiert |
| `  A 1234  ` | ✓ Wird trimmt und zu `A 1234` normalisiert |

## Ungültige Beispiele (werden abgelehnt)

| Format | Grund |
|--------|-------|
| `AB 1234` | 2 Buchstaben statt 1 |
| `1 1234` | Ziffer statt Buchstabe |
| `A1234` | Kein Leerzeichen |
| `A  1234` | 2 Leerzeichen statt 1 |
| `A 123` | Nur 3 Ziffern statt 4 |
| `A 12345` | 5 Ziffern statt 4 |
| `AB-CD 123` | Altes deutsches Format (ungültig) |
| `XY-ZA 456` | Altes deutsches Format (ungültig) |
| `a-1234` | Mit Bindestrich (ungültig) |

## Verwendung in Code

### Validierungsfunktion

```python
from backend.database.validators import PlateValidator

# Prüfen ob Kennzeichen gültig ist
plate = "A 1234"
is_valid = PlateValidator.is_valid(plate)
# Ergebnis: True

# Ungültiges Kennzeichen
invalid_plate = "AB 1234"
is_valid = PlateValidator.is_valid(invalid_plate)
# Ergebnis: False
```

### Normalisierung

```python
from backend.database.validators import PlateValidator

# Normalisiert (Großbuchstaben, trimmt Whitespace)
normalized = PlateValidator.normalize("  a 1234  ")
# Ergebnis: "A 1234"
```

### Validieren und Normalisieren

```python
from backend.database.validators import PlateValidator

is_valid, normalized = PlateValidator.validate_and_normalize("  m 5678  ")
# is_valid = True
# normalized = "M 5678"

is_valid, normalized = PlateValidator.validate_and_normalize("AB 1234")
# is_valid = False
# normalized = "AB 1234" (unverändert)
```

### Fahrzeug hinzufügen

```python
from backend.database.queries import VehicleQueries

# Gültiges Kennzeichen
vehicle_id = VehicleQueries.add_vehicle('A 1234', 'Mercedes')
# Erfolg: vehicle_id = 1

# Ungültiges Kennzeichen
vehicle_id = VehicleQueries.add_vehicle('AB-CD 123', 'Audi')
# Fehler: vehicle_id = None, Fehlermeldung wird gedruckt
```

## Automatische Normalisierung

Die Datenbank normalisiert Kennzeichen automatisch bei:
1. **Fahrzeughinzufügung**: Kennzeichen wird zu Großbuchstaben konvertiert und Leerzeichen gekürzt
2. **Bilderfassung**: Erkannte Kennzeichen werden normalisiert
3. **Fahrzeugsuche**: Suchanfrage wird normalisiert (z.B. `m 1111` findet `M 1111`)

## Datenbankintegration

In der `vehicles`-Tabelle gibt es ein Feld `is_valid_format`:
- `1` = Kennzeichen hat gültiges Format
- `0` = Kennzeichen hat ungültiges Format

Beispiel SQL-Abfrage:
```sql
SELECT * FROM vehicles WHERE is_valid_format = 1 AND status = 'approved';
```

## Workflow bei Fahrzeugerkennung

1. **Kamera erfasst Kennzeichen**
   - OCR erkennt Text (z.B. "AB CD 123" oder "A1234")

2. **Validierung läuft automatisch**
   ```python
   is_valid, normalized = PlateValidator.validate_and_normalize(ocr_text)
   ```

3. **Gültig (z.B. "A 1234")**
   - Fahrzeug wird in Datenbank gesucht
   - Wenn bekannt & approved → Schranke öffnet
   - Wenn unbekannt → Im Dashboard zur Freigabe anstehen

4. **Ungültig (z.B. "AB 1234")**
   - Fahrzeug wird NICHT hinzugefügt
   - Fehlermeldung wird geloggt
   - Schranke bleibt geschlossen
   - Optional: Dashboard zeigt Fehler an

## Logging

Bei ungültigen Kennzeichen wird folgende Meldung geloggt:

```
[FEHLER] Ungültiges Kennzeichen: 'AB-CD 123'
[INFO] Schema erforderlich: 1 Buchstabe + Leerzeichen + 4 Ziffern (z.B. 'A 1234')
```

## Testing

Die Validierungsfunktionen können einfach getestet werden:

```python
from backend.database.validators import VALID_PLATES, INVALID_PLATES

# Test valider Kennzeichen
for plate in VALID_PLATES:
    assert PlateValidator.is_valid(plate), f"{plate} sollte gültig sein"

# Test ungültiger Kennzeichen
for plate in INVALID_PLATES:
    assert not PlateValidator.is_valid(plate), f"{plate} sollte ungültig sein"
```

---

**Wichtig:** Diese Validierung ist die erste Sicherheitsebene. Alle Kennzeichen in der Datenbank sollten dieses Format erfüllen!

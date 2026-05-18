# 🚨 AI - Kennzeichen-Erkennungssystem

Dieses Modul implementiert ein vollständiges Kennzeichen-Erkennungssystem mit **YOLO** (Objekt-Erkennung) und **Tesseract OCR** (Text-Erkennung).

## 📦 Module

| Modul | Beschreibung |
|-------|-------------|
| `plate_recognizer.py` | Zentrale Erkennungslogik (YOLO + OCR Integration) |
| `image_processor.py` | Bildbearbeitung, Snapshots und Speicherung |
| `ocr_handler.py` | Tesseract OCR mit Preprocessing |
| `plate_detection_models.py` | Datenklassen und Ergebnisstrukturen |
| `__init__.py` | Package-Exporte für einfachen Import |
| `demo_recognition.py` | 📚 Quick-Start Demo mit 5 Beispielen |
| `test_integration.py` | ✅ Integrations-Tests für alle Komponenten |

## 🚀 Quick Start

### 1. Dependencies installieren
```bash
pip install -r ../requirements.txt
```

### 2. Tesseract OCR installieren
**Windows:** https://github.com/UB-Mannheim/tesseract/wiki  
**Linux:** `sudo apt-get install tesseract-ocr`  
**macOS:** `brew install tesseract`

### 3. YOLO-Modell platzieren
```
AI/YOLO-Modell/train/weights/best.pt  # Dein trainiertes Modell
```

### 4. System testen
```bash
python AI/test_integration.py
```

### 5. Demo ausführen
```bash
python AI/demo_recognition.py
```

## 💡 Verwendung

### Einfaches Beispiel
```python
from AI import PlateRecognizer
import cv2

# Lade Bild
frame = cv2.imread("parkhaus.jpg")

# Erkenne Kennzeichen
recognizer = PlateRecognizer()
result = recognizer.detect_plate_in_frame(frame)

if result.success:
    print(f"Kennzeichen: {result.detected_plate}")
    print(f"Konfidenz: {result.get_combined_confidence():.2%}")
```

### Im Dashboard
- Button **"🔍 Jetzt erkennen"** für Live-Feed Erkennung
- Button **"📤 Bild hochladen"** für Bild-Upload
- Klick auf Ergebnis für **Details-Modal**

## 📊 Erkennungs-Ergebnisse

Jede Erkennung gibt zurück:

```json
{
  "success": true,
  "detected_plate": "B-AB 1234",
  "plate_confidence": 0.95,
  "ocr_confidence": 0.92,
  "combined_confidence": 0.9383,
  "vehicle_snapshot": "data:image/jpeg;base64,...",
  "plate_image": "data:image/jpeg;base64,...",
  "annotated_frame": "data:image/jpeg;base64,...",
  "plate_region": {
    "x1": 100, "y1": 200, "x2": 300, "y2": 280,
    "width": 200, "height": 80
  }
}
```

## 📁 Output-Verzeichnisse

Erkannte Bilder werden automatisch gespeichert unter:

```
AI/detection_results/
├── snapshots/       # Fahrzeug-Fotos
├── plates/          # Ausgeschnittene Kennzeichen
└── annotated/       # Mit Bounding Boxes
```

## ⚙️ Konfiguration

### Konfidenz-Schwellenwert
```python
recognizer = PlateRecognizer(conf_threshold=0.5)  # 50% Minimum
```

### OCR Sprache
```python
from AI import OCRHandler
ocr = OCRHandler(lang='eng')  # Englisch statt Deutsch
```

### Modell-Pfad
```python
recognizer = PlateRecognizer(
    model_path="/custom/path/to/best.pt"
)
```

## 🔍 Debugging

### Service Status prüfen
```bash
curl http://localhost:8000/api/recognition/status
```

### Statistiken abrufen
```bash
curl http://localhost:8000/api/recognition/statistics
```

### Erkennungsergebnisse
```
POST /api/recognition/detect-plate        # Live-Feed
POST /api/recognition/upload-image        # Bild-Upload
```

## 📚 Dokumentation

Umfassende Dokumentation: [`Dokumentation/KENNZEICHEN_ERKENNUNGSSYSTEM.md`](../Dokumentation/KENNZEICHEN_ERKENNUNGSSYSTEM.md)

**Inhalte:**
- Detaillierte Setup-Anleitung
- API-Referenz mit Beispielen
- Konfigurationsoptionen
- Troubleshooting
- Performance-Tipps

## 📈 Performance

| Komponente | Laufzeit |
|------------|----------|
| YOLO Detection | ~50-100ms |
| OCR | ~100-300ms |
| Total (mit Preprocessing) | ~200-400ms |

**Mit GPU:** 2-3x schneller

## 🐛 Troubleshooting

**Tesseract nicht gefunden?**
```python
# Setze Path manuell (Windows)
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**YOLO-Modell nicht geladen?**
- Prüfe Pfad: `AI/YOLO-Modell/train/weights/best.pt`
- Überprüfe: `pip install --upgrade ultralytics`

**Schlechte OCR-Ergebnisse?**
- Höhere Bildauflösung nutzen
- Kontrast verbessern
- Preprocessing-Optionen nutzen

## 🔗 Integration

Das System ist vollständig ins Dashboard integriert:

1. **Erkennungs-Panel** nach dem Live-Feed
2. **API-Endpoints** für Erkennung
3. **Detail-Modal** mit allen Bildern
4. **Statistiken** im Dashboard

## 📝 Beispiel-Workflow

```python
# 1. Import
from AI import PlateRecognizer

# 2. Initialisiere
recognizer = PlateRecognizer()

# 3. Erkenne
result = recognizer.detect_plate_in_frame(frame)

# 4. Verarbeite Ergebnis
if result.success:
    plate = result.detected_plate
    confidence = result.get_combined_confidence()
    # Nutze plate und confidence...
else:
    print(f"Fehler: {result.error}")
```

## 📄 Dateien

- `plate_recognizer.py` (380 Zeilen) - Hauptlogik
- `image_processor.py` (280 Zeilen) - Bildverarbeitung
- `ocr_handler.py` (320 Zeilen) - OCR Integration
- `plate_detection_models.py` (280 Zeilen) - Datenmodelle
- `demo_recognition.py` (270 Zeilen) - Demo
- `test_integration.py` (290 Zeilen) - Tests
- `__init__.py` (20 Zeilen) - Exporte

**Gesamt: ~1.850 Zeilen Production Code**

## ✅ Status

- ✅ YOLO Integration
- ✅ OCR Integration  
- ✅ Bildverarbeitung
- ✅ Dashboard Integration
- ✅ API Endpoints
- ✅ Statistiken
- ✅ Error Handling
- ✅ Dokumentation

## 🎯 Nächste Schritte (Optional)

- [ ] Datenbank-Integration für Ergebnisse speichern
- [ ] Echtzeit-Erkennung in Video-Stream
- [ ] Erkennungshistorie im Dashboard
- [ ] Batch-Processing Optionen
- [ ] GPU-Beschleunigung
- [ ] Custom Training Pipeline
- [ ] Model Quantization

---

**Version:** 1.0.0  
**Status:** ✅ Produktionsreif  
**Letztes Update:** 2024-05-18
